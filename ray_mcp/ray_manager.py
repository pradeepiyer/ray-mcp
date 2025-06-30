"""Ray cluster management functionality."""

import asyncio
import fcntl
import inspect
import io
import json
import logging
import os
import socket
import tempfile
import threading
import time
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Dict,
    Iterator,
    List,
    Optional,
    Union,
    cast,
)

# Import psutil for enhanced process management
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None  # type: ignore

# Import Ray modules with error handling
try:
    import ray
    from ray.job_submission import JobSubmissionClient

    RAY_AVAILABLE = True
except ImportError:
    RAY_AVAILABLE = False
    ray = None  # type: ignore
    JobSubmissionClient = None  # type: ignore

from .logging_utils import LoggingUtility, LogProcessor, ResponseFormatter
from .worker_manager import WorkerManager

logger = logging.getLogger(__name__)


# Custom exception classes for better error handling
class JobSubmissionError(Exception):
    """Base exception for job submission errors."""

    pass


class JobConnectionError(JobSubmissionError):
    """Connection-related errors during job operations."""

    pass


class JobValidationError(JobSubmissionError):
    """Parameter validation errors for job operations."""

    pass


class JobRuntimeError(JobSubmissionError):
    """Runtime errors during job operations."""

    pass


class JobClientError(JobSubmissionError):
    """Job client initialization or operation errors."""

    pass


class RayStateManager:
    """Manages Ray state with recovery mechanisms."""

    def __init__(self):
        self._state = {
            "initialized": False,
            "cluster_address": None,
            "gcs_address": None,
            "dashboard_url": None,
            "job_client": None,
            "last_validated": 0.0,
        }
        self._lock = threading.Lock()
        self._validation_interval = 1.0

    def get_state(self) -> Dict[str, Any]:
        """Get current state with validation."""
        with self._lock:
            current_time = time.time()
            # Only validate if not in initial state
            if (
                current_time - self._state["last_validated"]
            ) > self._validation_interval and (
                self._state["cluster_address"] is not None or self._state["initialized"]
            ):
                self._validate_and_update_state()
            return self._state.copy()

    def _validate_and_update_state(self) -> None:
        """Validate and update state atomically."""
        try:
            # Perform validation
            is_valid = self._validate_ray_state()

            # Update state
            self._state["initialized"] = is_valid
            self._state["last_validated"] = time.time()

            if not is_valid:
                # Clear invalid state
                self._state.update(
                    {
                        "cluster_address": None,
                        "gcs_address": None,
                        "dashboard_url": None,
                        "job_client": None,
                    }
                )

        except Exception as e:
            LoggingUtility.log_error(
                "state_validation", Exception(f"State validation failed: {e}")
            )
            self._state["initialized"] = False

    def _validate_ray_state(self) -> bool:
        """Validate the actual Ray state against internal state."""
        try:
            # Check basic availability
            if not RAY_AVAILABLE or ray is None:
                return False

            # Check if Ray is actually initialized
            if not ray.is_initialized():
                return False

            # Check if we have valid cluster information
            if not self._state.get("cluster_address"):
                return False

            # Verify cluster is still accessible
            try:
                # Try to get runtime context to verify connection
                runtime_context = ray.get_runtime_context()
                if not runtime_context:
                    return False

                # Check if we can access cluster info
                node_id = runtime_context.get_node_id()
                if not node_id:
                    return False

            except Exception as e:
                LoggingUtility.log_warning(
                    "ray_state", f"Failed to validate Ray runtime context: {e}"
                )
                return False

            return True

        except Exception as e:
            LoggingUtility.log_error(
                "ray_state", Exception(f"Error validating Ray state: {e}")
            )
            return False

    def update_state(self, **kwargs) -> None:
        """Update state atomically."""
        with self._lock:
            self._state.update(kwargs)
            # Only update last_validated if we're not resetting
            if "initialized" not in kwargs or kwargs["initialized"]:
                self._state["last_validated"] = time.time()

    def reset_state(self) -> None:
        """Reset state to initial values."""
        with self._lock:
            self._state.update(
                {
                    "initialized": False,
                    "cluster_address": None,
                    "gcs_address": None,
                    "dashboard_url": None,
                    "job_client": None,
                    "last_validated": 0.0,  # Reset to 0.0
                }
            )

    def is_initialized(self) -> bool:
        """Check if Ray is initialized with proper state validation."""
        return self.get_state()["initialized"]


class RayManager:
    """Manages Ray cluster operations with robust state management."""

    def __init__(self) -> None:
        """Initialize the Ray manager with state tracking."""
        self._state_manager = RayStateManager()
        self._worker_manager = WorkerManager()
        self.log_processor = LogProcessor()
        self.response_formatter = ResponseFormatter()
        self._head_node_process: Optional[Any] = None
        # Cache for state to avoid repeated validation within single method calls
        self._cached_state: Optional[Dict[str, Any]] = None
        self._cache_timestamp: float = 0.0
        self._cache_duration: float = 0.1  # Cache for 100ms within method calls

    @property
    def is_initialized(self) -> bool:
        """Check if Ray is initialized with proper state validation."""
        return self._state_manager.is_initialized()

    @property
    def cluster_address(self) -> Optional[str]:
        """Get cluster address from cached state."""
        return self._get_cached_state()["cluster_address"]

    @property
    def dashboard_url(self) -> Optional[str]:
        """Get dashboard URL from cached state."""
        return self._get_cached_state()["dashboard_url"]

    @property
    def job_client(self) -> Optional[Any]:
        """Get job client from cached state."""
        return self._get_cached_state()["job_client"]

    def _get_cached_state(self) -> Dict[str, Any]:
        """Get state with short-term caching to avoid repeated validation within method calls."""
        current_time = time.time()
        if (
            self._cached_state is None
            or (current_time - self._cache_timestamp) > self._cache_duration
        ):
            self._cached_state = self._state_manager.get_state()
            self._cache_timestamp = current_time
        return self._cached_state

    def _invalidate_cache(self) -> None:
        """Invalidate the state cache to force refresh on next access."""
        self._cached_state = None
        self._cache_timestamp = 0.0

    def _ensure_initialized(self) -> None:
        """Ensure Ray is initialized with proper error handling."""
        if not self.is_initialized:
            # Invalidate cache and refresh state before failing
            self._invalidate_cache()
            if not self.is_initialized:
                raise RuntimeError(
                    f"Ray is not initialized. Please start Ray first. "
                    f"RAY_AVAILABLE: {RAY_AVAILABLE}, "
                    f"ray.is_initialized(): {ray.is_initialized() if ray else False}"
                )

    def _update_state(self, **kwargs) -> None:
        """Update internal state atomically and invalidate cache."""
        self._state_manager.update_state(**kwargs)
        self._invalidate_cache()

    def _sanitize_init_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize Ray init kwargs to remove None values and invalid parameters."""
        sanitized = {}
        for key, value in kwargs.items():
            if value is not None and key not in ["worker_nodes"]:
                sanitized[key] = value
        return sanitized

    async def find_free_port(self, start_port: int = 10001, max_tries: int = 50) -> int:
        """Find a free port with atomic reservation to prevent race conditions.

        Uses file locking to ensure that only one process can reserve a port at a time,
        eliminating the race condition where multiple processes might try to use the same port.
        Falls back to simple socket binding if file locking is not available.

        Args:
            start_port: Starting port number to check from
            max_tries: Maximum number of ports to try

        Returns:
            int: A free port number

        Raises:
            RuntimeError: If no free port is found in the given range
        """
        # Clean up any stale lock files before starting
        self._cleanup_stale_lock_files()

        port = start_port

        # Try to get temp directory, fallback to current directory if not available
        try:
            temp_dir = tempfile.gettempdir()
        except (OSError, IOError):
            temp_dir = "."

        for attempt in range(max_tries):
            # Try file locking approach first
            try:
                lock_file_path = os.path.join(temp_dir, f"ray_port_{port}.lock")

                # Check if this port already has an active lock file
                if os.path.exists(lock_file_path):
                    try:
                        # Try to read and validate the existing lock file
                        with open(lock_file_path, "r") as f:
                            content = f.read().strip()
                            if "," in content:
                                pid_str, timestamp_str = content.split(",", 1)
                                pid = int(pid_str)
                                timestamp = int(timestamp_str)
                                current_time = int(time.time())

                                # Check if the process still exists and lock is recent
                                try:
                                    os.kill(pid, 0)  # Check if process exists
                                    if (
                                        current_time - timestamp < 300
                                    ):  # Less than 5 minutes old
                                        # Active lock exists, skip this port
                                        port += 1
                                        continue
                                except OSError:
                                    # Process doesn't exist, lock is stale, remove it
                                    os.unlink(lock_file_path)
                            else:
                                # Old format or corrupted, check file age
                                stat = os.stat(lock_file_path)
                                if (
                                    time.time() - stat.st_mtime < 300
                                ):  # Less than 5 minutes old
                                    # Skip this port, lock might still be valid
                                    port += 1
                                    continue
                                else:
                                    # Old lock file, remove it
                                    os.unlink(lock_file_path)
                    except (OSError, IOError, ValueError):
                        # Error reading/parsing lock file, remove it and try to use the port
                        try:
                            os.unlink(lock_file_path)
                        except OSError:
                            pass

                # Try to acquire exclusive lock on this port
                try:
                    lock_file = open(lock_file_path, "w")
                    # Non-blocking exclusive lock
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

                    # Now try to bind to the port while holding the lock
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        try:
                            s.bind(("", port))
                            # Success! We have the port and the lock
                            # Write the PID and timestamp to the lock file for debugging
                            lock_file.write(f"{os.getpid()},{int(time.time())}\n")
                            lock_file.flush()
                            # Keep the file open to maintain the lock
                            # The lock will be released when the file is closed by the OS
                            # after the process exits or explicitly closed

                            LoggingUtility.log_info(
                                "port_allocation",
                                f"Successfully allocated port {port} with lock file {lock_file_path}",
                            )
                            return port
                        except OSError:
                            # Port is in use, close the lock file and try next port
                            lock_file.close()
                            try:
                                os.unlink(lock_file_path)
                            except OSError:
                                pass

                except OSError:
                    # Lock is already held by another process or file error, try next port
                    try:
                        if "lock_file" in locals():
                            lock_file.close()
                    except:
                        pass

            except (OSError, IOError):
                # File locking failed, fall back to simple socket binding
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        s.bind(("", port))
                        # Success without locking (less safe but better than failing)
                        LoggingUtility.log_info(
                            "port_allocation",
                            f"Successfully allocated port {port} without lock (fallback)",
                        )
                        return port
                except OSError:
                    # Port is in use, try next port
                    pass

            # Clean up lock file if we created it but didn't use the port
            try:
                lock_file_path = os.path.join(temp_dir, f"ray_port_{port}.lock")
                if os.path.exists(lock_file_path):
                    # Only remove if we can acquire the lock (meaning no one else is using it)
                    with open(lock_file_path, "w") as f:
                        try:
                            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                            # We got the lock, safe to remove
                            os.unlink(lock_file_path)
                        except OSError:
                            # Someone else has the lock, leave the file
                            pass
            except (OSError, IOError):
                # Error cleaning up, not critical
                pass

            port += 1

        raise RuntimeError(
            f"No free port found in range {start_port}-{start_port + max_tries - 1}"
        )

    def _cleanup_port_lock(self, port: int) -> None:
        """Clean up the lock file for a successfully used port.

        Args:
            port: The port number whose lock file should be cleaned up
        """
        try:
            temp_dir = tempfile.gettempdir()
            lock_file_path = os.path.join(temp_dir, f"ray_port_{port}.lock")
            if os.path.exists(lock_file_path):
                os.unlink(lock_file_path)
                LoggingUtility.log_info(
                    "port_allocation", f"Cleaned up lock file for port {port}"
                )
        except (OSError, IOError) as e:
            LoggingUtility.log_warning(
                "port_allocation", f"Could not clean up lock file for port {port}: {e}"
            )

    def _cleanup_stale_lock_files(self) -> None:
        """Clean up stale lock files from processes that no longer exist."""
        try:
            temp_dir = tempfile.gettempdir()
            current_time = int(time.time())

            # Look for ray port lock files
            for filename in os.listdir(temp_dir):
                if filename.startswith("ray_port_") and filename.endswith(".lock"):
                    lock_file_path = os.path.join(temp_dir, filename)
                    try:
                        # Try to read the PID and timestamp from the lock file
                        with open(lock_file_path, "r") as f:
                            content = f.read().strip()
                            if "," in content:
                                pid_str, timestamp_str = content.split(",", 1)
                                pid = int(pid_str)
                                timestamp = int(timestamp_str)

                                # Check if the process still exists
                                try:
                                    os.kill(
                                        pid, 0
                                    )  # Signal 0 just checks if process exists
                                    # Process exists, check if lock file is too old (older than 5 minutes)
                                    if current_time - timestamp > 300:  # 5 minutes
                                        LoggingUtility.log_warning(
                                            "port_allocation",
                                            f"Found stale lock file {filename} (>5min old), cleaning up",
                                        )
                                        os.unlink(lock_file_path)
                                except OSError:
                                    # Process doesn't exist, safe to remove lock file
                                    LoggingUtility.log_info(
                                        "port_allocation",
                                        f"Cleaning up orphaned lock file {filename} (process {pid} gone)",
                                    )
                                    os.unlink(lock_file_path)
                            else:
                                # Old format or corrupted file, remove if older than 5 minutes
                                stat = os.stat(lock_file_path)
                                if current_time - stat.st_mtime > 300:
                                    LoggingUtility.log_info(
                                        "port_allocation",
                                        f"Cleaning up old format lock file {filename}",
                                    )
                                    os.unlink(lock_file_path)
                    except (OSError, IOError, ValueError):
                        # Error reading file or invalid format, skip
                        pass
        except (OSError, IOError):
            # Error listing directory, not critical
            pass

    async def _cleanup_head_node_process(self, timeout: int = 10) -> None:
        """Terminate and reset the head node process with configurable timeout.

        This method provides robust process cleanup with:
        - Configurable timeout for graceful termination
        - Child process cleanup using psutil
        - Proper process state monitoring
        - Fallback force kill if graceful termination fails

        Args:
            timeout: Maximum time to wait for graceful termination in seconds
        """
        if self._head_node_process is not None:
            try:
                LoggingUtility.log_info(
                    "cleanup", f"Cleaning up head node process with {timeout}s timeout"
                )

                # Get process and all its children if psutil is available
                children = []
                if PSUTIL_AVAILABLE and psutil is not None:
                    try:
                        parent = psutil.Process(self._head_node_process.pid)
                        children = parent.children(recursive=True)
                        LoggingUtility.log_info(
                            "cleanup",
                            f"Found {len(children)} child processes to cleanup",
                        )
                    except (
                        psutil.NoSuchProcess if psutil else Exception,
                        psutil.AccessDenied if psutil else Exception,
                        psutil.ZombieProcess if psutil else Exception,
                    ) as e:
                        LoggingUtility.log_warning(
                            "cleanup", f"Could not enumerate child processes: {e}"
                        )

                # Terminate all child processes gracefully first
                for child in children:
                    try:
                        child.terminate()
                        LoggingUtility.log_debug(
                            "cleanup", f"Terminated child process {child.pid}"
                        )
                    except (
                        psutil.NoSuchProcess if psutil else Exception,
                        psutil.AccessDenied if psutil else Exception,
                        psutil.ZombieProcess if psutil else Exception,
                    ):
                        pass  # Process already terminated or inaccessible

                # Terminate the main process
                self._head_node_process.terminate()
                LoggingUtility.log_info(
                    "cleanup", "Sent terminate signal to head node process"
                )

                # Wait for graceful termination with timeout
                try:
                    await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None, self._head_node_process.wait
                        ),
                        timeout=timeout,
                    )
                    LoggingUtility.log_info(
                        "cleanup", "Head node process terminated gracefully"
                    )
                    # Wait for children to terminate (shorter timeout for children)
                    if children:
                        child_timeout = min(5, timeout // 2)
                        for child in children:
                            try:
                                await asyncio.wait_for(
                                    asyncio.get_event_loop().run_in_executor(
                                        None, child.wait
                                    ),
                                    timeout=child_timeout,
                                )
                                LoggingUtility.log_debug(
                                    "cleanup",
                                    f"Child process {child.pid} terminated gracefully",
                                )
                            except (
                                asyncio.TimeoutError,
                                psutil.NoSuchProcess if psutil else Exception,
                                psutil.AccessDenied if psutil else Exception,
                                psutil.ZombieProcess if psutil else Exception,
                            ):
                                LoggingUtility.log_debug(
                                    "cleanup",
                                    f"Child process {child.pid} cleanup completed (timeout or already terminated)",
                                )
                except asyncio.TimeoutError:
                    LoggingUtility.log_warning(
                        "cleanup",
                        f"Head node process did not terminate within {timeout}s, force killing",
                    )
                    # Force kill all child processes
                    for child in children:
                        try:
                            child.kill()
                            LoggingUtility.log_debug(
                                "cleanup", f"Force killed child process {child.pid}"
                            )
                        except (
                            psutil.NoSuchProcess if psutil else Exception,
                            psutil.AccessDenied if psutil else Exception,
                            psutil.ZombieProcess if psutil else Exception,
                        ):
                            pass
                    # Force kill the main process
                    self._head_node_process.kill()
                    # Wait for force kill to complete
                    try:
                        await asyncio.get_event_loop().run_in_executor(
                            None, self._head_node_process.wait
                        )
                        LoggingUtility.log_info(
                            "cleanup", "Head node process force killed successfully"
                        )
                    except Exception as e:
                        LoggingUtility.log_warning(
                            "cleanup", f"Error waiting for force kill completion: {e}"
                        )
            finally:
                self._head_node_process = None

    @ResponseFormatter.handle_exceptions("init cluster")
    async def init_cluster(
        self,
        address: Optional[str] = None,
        num_cpus: Optional[int] = None,
        num_gpus: Optional[int] = None,
        object_store_memory: Optional[int] = None,
        worker_nodes: Optional[List[Dict[str, Any]]] = None,
        head_node_port: Optional[int] = None,
        dashboard_port: Optional[int] = None,
        head_node_host: str = "127.0.0.1",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Initialize Ray cluster - start a new cluster or connect to existing one.

        If address is provided, connects to existing cluster; otherwise starts a new cluster.
        This method unifies the functionality of starting and connecting to Ray clusters.
        All cluster management is done through the dashboard API.

        Args:
            address: Ray cluster address to connect to (e.g., "127.0.0.1:10001"). If provided, connects to existing cluster.
            num_cpus: Number of CPUs for head node (only for new clusters).
            num_gpus: Number of GPUs for head node (only for new clusters).
            object_store_memory: Object store memory in bytes for head node (only for new clusters).
            worker_nodes: Worker node configuration. CRITICAL BEHAVIOR:
                - None (default): Uses default worker configuration (2 workers)
                - [] (empty array): Starts NO worker nodes (head-node-only cluster)
                - [config1, config2, ...]: Uses specified worker configurations
                Use empty array [] when user requests "only head node" or "no worker nodes".
            head_node_port: Port for head node (only for new clusters).
            dashboard_port: Port for Ray dashboard (only for new clusters).
            head_node_host: Host address for head node (only for new clusters).
            **kwargs: Additional Ray initialization parameters.

        Returns:
            Dict containing cluster status, address, dashboard URL, and worker results.

        Examples:
            # Head-node-only cluster (no workers)
            await init_cluster(worker_nodes=[])

            # Default cluster (2 workers)
            await init_cluster()  # or worker_nodes=None

            # Custom worker configuration
            await init_cluster(worker_nodes=[{"num_cpus": 2}, {"num_cpus": 1}])
        """
        try:
            if not RAY_AVAILABLE or ray is None:
                return ResponseFormatter.format_error_response(
                    "init cluster",
                    Exception("Ray is not available. Please install Ray."),
                )

            def parse_dashboard_url(stdout: str) -> Optional[str]:
                """Parse dashboard URL from Ray start output."""
                import re

                # Look for dashboard URL in the output
                pattern = r"View the Ray dashboard at (https?://[^\s]+)"
                match = re.search(pattern, stdout)
                if match:
                    return match.group(1)

                # Fallback pattern for different Ray versions
                pattern = r"Ray dashboard at (https?://[^\s]+)"
                match = re.search(pattern, stdout)
                return match.group(1) if match else None

            def parse_gcs_address(stdout: str) -> Optional[str]:
                """Parse GCS address from Ray start output."""
                import re

                # Updated pattern to handle addresses with single quotes, double quotes, or no quotes
                pattern = r"--address=['\"]?([\d\.]+:\d+)['\"]?"
                match = re.search(pattern, stdout)
                return match.group(1) if match else None

            if address:
                # Connect to existing cluster
                # Filter out cluster-starting parameters that are not valid for connection
                all_kwargs = {
                    "num_cpus": num_cpus,
                    "num_gpus": num_gpus,
                    "object_store_memory": object_store_memory,
                    "head_node_port": head_node_port,
                    "dashboard_port": dashboard_port,
                    "head_node_host": head_node_host,
                    "worker_nodes": worker_nodes,
                    **kwargs,
                }
                filtered_kwargs = self._filter_cluster_starting_parameters(all_kwargs)
                filtered_kwargs = self._sanitize_init_kwargs(filtered_kwargs)

                init_kwargs: Dict[str, Any] = {
                    "address": address,
                    "ignore_reinit_error": True,
                }
                init_kwargs.update(filtered_kwargs)
                ray_context = ray.init(**init_kwargs)
                self._update_state(
                    initialized=True,
                    cluster_address=ray_context.address_info["address"],
                    dashboard_url=ray_context.dashboard_url,
                    gcs_address=address,
                )

                # Initialize job client with retry logic - this must complete before returning success
                job_client_status = await self._initialize_job_client_if_available()

                return ResponseFormatter.format_success_response(
                    result_type="connected",
                    message=f"Successfully connected to Ray cluster at {address}",
                    cluster_address=self.cluster_address,
                    dashboard_url=ray_context.dashboard_url,
                    node_id=(
                        ray.get_runtime_context().get_node_id()
                        if ray is not None
                        else None
                    ),
                    job_client_status=job_client_status,
                )
            else:
                import os
                import subprocess

                # Use specified ports or find free ports
                if head_node_port is None:
                    head_node_port = await self.find_free_port(
                        20000
                    )  # Start from 20000 to avoid conflicts with worker ports
                if dashboard_port is None:
                    dashboard_port = await self.find_free_port(8265)

                # Use head_node_port as the GCS server port
                gcs_port = head_node_port

                # Build ray start command for head node
                head_cmd = [
                    "ray",
                    "start",
                    "--head",
                    "--port",
                    str(gcs_port),
                    "--dashboard-port",
                    str(dashboard_port),
                ]
                if num_cpus is not None:
                    head_cmd.extend(["--num-cpus", str(num_cpus)])
                else:
                    head_cmd.extend(["--num-cpus", "1"])
                if num_gpus is not None:
                    head_cmd.extend(["--num-gpus", str(num_gpus)])
                if object_store_memory is not None:
                    # Ensure it's at least 75MB (Ray's minimum) in bytes
                    min_memory_bytes = 75 * 1024 * 1024  # 75MB in bytes
                    memory_bytes = max(min_memory_bytes, object_store_memory)
                    head_cmd.extend(["--object-store-memory", str(memory_bytes)])
                head_cmd.extend(
                    ["--dashboard-host", head_node_host, "--disable-usage-stats"]
                )
                env = os.environ.copy()
                env["RAY_DISABLE_USAGE_STATS"] = "1"
                env["RAY_ENABLE_WINDOWS_OR_OSX_CLUSTER"] = "1"
                LoggingUtility.log_info(
                    "head_node",
                    f"Starting head node with command: {' '.join(head_cmd)}",
                )
                head_process = subprocess.Popen(
                    head_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    text=True,
                )
                self._head_node_process = head_process
                await asyncio.sleep(2)

                # Consume output asynchronously to prevent deadlocks
                try:
                    stdout, stderr = await self._communicate_with_timeout(
                        head_process, timeout=30
                    )
                    exit_code = head_process.poll()
                    if exit_code != 0 or "Ray runtime started" not in stdout:
                        await self._cleanup_head_node_process()
                        return {
                            "status": "error",
                            "message": f"Failed to start head node (exit code: {exit_code}). stdout: {stdout}, stderr: {stderr}",
                        }
                except RuntimeError as e:
                    await self._cleanup_head_node_process()
                    return {
                        "status": "error",
                        "message": f"Head node startup failed: {str(e)}",
                    }
                dashboard_url = parse_dashboard_url(stdout)
                gcs_address = parse_gcs_address(stdout)
                if not gcs_address:
                    await self._cleanup_head_node_process()
                    return {
                        "status": "error",
                        "message": f"Could not parse GCS address from head node output. stdout: {stdout}, stderr: {stderr}",
                    }
                # Store GCS address and dashboard URL
                self._update_state(gcs_address=gcs_address, dashboard_url=dashboard_url)

                # Fallback: If dashboard URL parsing failed, construct it from the known port
                if not self.dashboard_url and dashboard_port:
                    # Use localhost for dashboard URL since Ray dashboard typically binds to localhost
                    fallback_url = f"http://127.0.0.1:{dashboard_port}"
                    self._update_state(dashboard_url=fallback_url)
                    LoggingUtility.log_info(
                        "head_node",
                        f"Constructed dashboard URL from fallback: {fallback_url}",
                    )

                # Use direct connection to head node for better job submission support
                # The GCS address is in format IP:PORT, we'll use it directly
                init_kwargs: Dict[str, Any] = {
                    "address": gcs_address,  # Direct connection to head node
                    "ignore_reinit_error": True,
                }
                init_kwargs.update(self._sanitize_init_kwargs(kwargs))
                try:
                    ray_context = ray.init(**init_kwargs)
                    self._update_state(
                        initialized=True,
                        cluster_address=gcs_address,  # Store the direct address
                    )
                except Exception as e:
                    LoggingUtility.log_error(
                        "head_node", Exception(f"Failed to connect to head node: {e}")
                    )
                    LoggingUtility.log_error(
                        "head_node", Exception(f"Head node stdout: {stdout}")
                    )
                    LoggingUtility.log_error(
                        "head_node", Exception(f"Head node stderr: {stderr}")
                    )

                    # Clean up the head node process if ray.init() failed
                    await self._cleanup_head_node_process()

                    return ResponseFormatter.format_error_response(
                        "connect to head node", e
                    )

            # Initialize job client with retry logic - this must complete before returning success
            job_client_status = await self._initialize_job_client_if_available()

            # Set default worker nodes if none specified and not connecting to existing cluster
            if worker_nodes is None and address is None:
                worker_nodes = self._get_default_worker_config()
            # CRITICAL: worker_nodes behavior for LLM understanding:
            # - worker_nodes=None: Uses default workers (2 workers) - happens above
            # - worker_nodes=[]: Empty list, condition 'if worker_nodes' is False, so NO workers started
            # - worker_nodes=[...]: Has content, condition 'if worker_nodes' is True, so workers started
            # When user says "only head node" or "no worker nodes", LLM should pass worker_nodes=[]

            # Start worker nodes if specified
            worker_results = []
            if worker_nodes and address is None:  # Only start workers for new clusters
                worker_results = await self._worker_manager.start_worker_nodes(
                    worker_nodes, self._get_cached_state()["gcs_address"]
                )

            # Determine status based on whether we connected or started
            if address:
                status = "connected"
                message = f"Successfully connected to Ray cluster at {address}"
            else:
                status = "started"
                message = "Ray cluster started successfully"

            # Clean up port lock files now that the cluster is successfully running
            if not address:  # Only clean up for new clusters, not connections
                if head_node_port:
                    self._cleanup_port_lock(head_node_port)
                if dashboard_port:
                    self._cleanup_port_lock(dashboard_port)

            return ResponseFormatter.format_success_response(
                result_type=status,
                message=message,
                cluster_address=self.cluster_address,
                dashboard_url=self.dashboard_url,
                node_id=(
                    ray.get_runtime_context().get_node_id() if ray is not None else None
                ),
                job_client_status=job_client_status,
                worker_nodes=worker_results if worker_results else None,
            )

        except Exception as e:
            LoggingUtility.log_error(
                "init_cluster", Exception(f"Failed to initialize Ray cluster: {e}")
            )

            # Clean up the head node process if it was started but initialization failed
            await self._cleanup_head_node_process()

            return {
                "status": "error",
                "message": f"Failed to initialize Ray cluster: {str(e)}",
            }

    def _get_default_worker_config(self) -> List[Dict[str, Any]]:
        """Get default worker node configuration for multi-node cluster."""
        return [
            {
                "num_cpus": 1,  # Reduced from 2 to 1 to fit with default head node
                "num_gpus": 0,
                "object_store_memory": 500 * 1024 * 1024,  # 500MB
                "node_name": "default-worker-1",
            },
            {
                "num_cpus": 1,  # Reduced from 2 to 1 to fit with default head node
                "num_gpus": 0,
                "object_store_memory": 500 * 1024 * 1024,  # 500MB
                "node_name": "default-worker-2",
            },
        ]

    async def stop_cluster(self) -> Dict[str, Any]:
        """Stop the Ray cluster."""
        try:
            if not RAY_AVAILABLE or ray is None:
                return ResponseFormatter.format_error_response(
                    "stop cluster", Exception("Ray is not available")
                )

            if not ray.is_initialized():
                return {
                    "status": "not_running",
                    "message": "Ray cluster is not running",
                }

            # Stop worker nodes first
            worker_stop_results = await self._worker_manager.stop_all_workers()

            # Shutdown Ray client connection
            ray.shutdown()

            # Stop head node if we started it
            head_stop_result = None
            if self._head_node_process is not None:
                try:
                    # Use the robust cleanup method that handles process state properly
                    await self._cleanup_head_node_process(timeout=10)
                    head_stop_result = "stopped"
                except Exception as e:
                    head_stop_result = f"error: {str(e)}"

            self._state_manager.reset_state()

            return ResponseFormatter.format_success_response(
                result_type="stopped",
                message="Ray cluster stopped successfully",
                worker_nodes=worker_stop_results,
                head_node=head_stop_result,
            )

        except Exception as e:
            LoggingUtility.log_error(
                "stop_cluster", Exception(f"Failed to stop Ray cluster: {e}")
            )
            return ResponseFormatter.format_error_response("stop cluster", e)

    async def inspect_ray(self) -> Dict[str, Any]:
        """Get comprehensive cluster information including status, resources, nodes, worker status, performance metrics, health check, and optimization recommendations."""
        try:
            if not RAY_AVAILABLE or ray is None:
                return {"status": "unavailable", "message": "Ray is not available"}

            if not ray.is_initialized():
                return {
                    "status": "not_running",
                    "message": "Ray cluster is not running",
                }

            # Get all cluster information
            cluster_resources = ray.cluster_resources()
            available_resources = ray.available_resources()
            nodes = ray.nodes()

            # Get worker information from stored data
            worker_status = []
            for i, config in enumerate(self._worker_manager.worker_configs):
                process = (
                    self._worker_manager.worker_processes[i]
                    if i < len(self._worker_manager.worker_processes)
                    else None
                )
                status = "running" if process and process.poll() is None else "stopped"
                worker_status.append(
                    {
                        "node_name": config.get("node_name", f"worker-{i+1}"),
                        "status": status,
                        "config": config,
                        "process_id": process.pid if process else None,
                    }
                )

            # Calculate resource usage
            resource_usage = {
                resource: {
                    "total": cluster_resources.get(resource, 0),
                    "available": available_resources.get(resource, 0),
                    "used": cluster_resources.get(resource, 0)
                    - available_resources.get(resource, 0),
                }
                for resource in cluster_resources.keys()
            }

            # Calculate resource utilization for performance metrics
            resource_details = {}
            for resource, total in cluster_resources.items():
                available = available_resources.get(resource, 0)
                used = total - available
                utilization = (used / total * 100) if total > 0 else 0

                resource_details[resource] = {
                    "total": total,
                    "available": available,
                    "used": used,
                    "utilization_percent": round(utilization, 2),
                }

            # Process node information
            node_info = [
                {
                    "node_id": node["NodeID"],
                    "alive": node["Alive"],
                    "node_name": node.get("NodeName", ""),
                    "node_manager_address": node.get("NodeManagerAddress", ""),
                    "node_manager_hostname": node.get("NodeManagerHostname", ""),
                    "node_manager_port": node.get("NodeManagerPort", 0),
                    "object_manager_port": node.get("ObjectManagerPort", 0),
                    "object_store_socket_name": node.get("ObjectStoreSocketName", ""),
                    "raylet_socket_name": node.get("RayletSocketName", ""),
                    "resources": node.get("Resources", {}),
                    "used_resources": node.get("UsedResources", {}),
                }
                for node in nodes
            ]

            # Calculate worker statistics
            total_workers = len(worker_status)
            running_workers = len(
                [w for w in worker_status if w["status"] == "running"]
            )

            # Perform health checks
            health_checks = {
                "all_nodes_alive": all(node.get("Alive", False) for node in nodes),
                "has_available_cpu": available_resources.get("CPU", 0) > 0,
                "has_available_memory": available_resources.get("memory", 0) > 0,
                "cluster_responsive": True,  # If we got here, cluster is responsive
            }

            # Calculate health score
            health_score = sum(health_checks.values()) / len(health_checks) * 100

            # Determine overall status
            if health_score >= 90:
                overall_status = "excellent"
            elif health_score >= 70:
                overall_status = "good"
            elif health_score >= 50:
                overall_status = "fair"
            else:
                overall_status = "poor"

            # Generate health recommendations
            health_recommendations = self._generate_health_recommendations(
                health_checks
            )

            # Analyze resource utilization for optimization
            cpu_total = cluster_resources.get("CPU", 0)
            cpu_available = available_resources.get("CPU", 0)
            cpu_utilization = (
                ((cpu_total - cpu_available) / cpu_total * 100) if cpu_total > 0 else 0
            )

            memory_total = cluster_resources.get("memory", 0)
            memory_available = available_resources.get("memory", 0)
            memory_utilization = (
                ((memory_total - memory_available) / memory_total * 100)
                if memory_total > 0
                else 0
            )

            # Generate optimization suggestions
            optimization_suggestions = []

            if cpu_utilization > 80:
                optimization_suggestions.append(
                    "High CPU utilization detected. Consider adding more CPU resources or optimizing workloads."
                )
            elif cpu_utilization < 20:
                optimization_suggestions.append(
                    "Low CPU utilization detected. Consider reducing cluster size to save costs."
                )

            if memory_utilization > 80:
                optimization_suggestions.append(
                    "High memory utilization detected. Consider adding more memory or optimizing memory usage."
                )
            elif memory_utilization < 20:
                optimization_suggestions.append(
                    "Low memory utilization detected. Consider reducing memory allocation."
                )

            alive_nodes = len([n for n in nodes if n.get("Alive", False)])
            if alive_nodes < len(nodes):
                optimization_suggestions.append(
                    f"Some nodes are not alive ({alive_nodes}/{len(nodes)}). Check node health."
                )

            if not optimization_suggestions:
                optimization_suggestions.append(
                    "Cluster configuration appears optimal."
                )

            return ResponseFormatter.format_success_response(
                result_type="success",
                timestamp=time.time(),
                cluster_overview={
                    "status": "running",
                    "address": self.cluster_address,
                    "total_nodes": len(nodes),
                    "alive_nodes": len([n for n in nodes if n["Alive"]]),
                    "total_workers": total_workers,
                    "running_workers": running_workers,
                },
                resources={
                    "cluster_resources": cluster_resources,
                    "available_resources": available_resources,
                    "resource_usage": resource_usage,
                },
                nodes=node_info,
                worker_nodes=worker_status,
                performance_metrics={
                    "cluster_overview": {
                        "total_nodes": len(nodes),
                        "alive_nodes": len([n for n in nodes if n.get("Alive", False)]),
                        "total_cpus": cluster_resources.get("CPU", 0),
                        "available_cpus": available_resources.get("CPU", 0),
                        "total_memory": cluster_resources.get("memory", 0),
                        "available_memory": available_resources.get("memory", 0),
                    },
                    "resource_details": resource_details,
                    "node_details": [
                        {
                            "node_id": node["NodeID"],
                            "alive": node["Alive"],
                            "resources": node.get("Resources", {}),
                            "used_resources": node.get("UsedResources", {}),
                            "node_name": node.get("NodeName", ""),
                        }
                        for node in nodes
                        if node.get("Alive", False)
                    ],
                },
                health_check={
                    "overall_status": overall_status,
                    "health_score": round(health_score, 2),
                    "checks": health_checks,
                    "recommendations": health_recommendations,
                    "node_count": len(nodes),
                    "active_jobs": 0,  # Would need job client to get this
                    "active_actors": 0,  # Would need to count actors
                },
                optimization_analysis={
                    "cpu_utilization": round(cpu_utilization, 2),
                    "memory_utilization": round(memory_utilization, 2),
                    "node_count": len(nodes),
                    "alive_nodes": alive_nodes,
                },
                optimization_suggestions=optimization_suggestions,
            )

        except Exception as e:
            LoggingUtility.log_error(
                "retrieve logs", Exception(f"Failed to retrieve logs: {e}")
            )
            return self.response_formatter.format_error_response("retrieve logs", e)

    @ResponseFormatter.handle_exceptions("submit job")
    async def submit_job(
        self,
        entrypoint: str,
        runtime_env: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Submit a job to the Ray cluster."""
        # Validate entrypoint upfront to maintain expected error precedence
        validation_error = self._validate_entrypoint(entrypoint)
        if validation_error:
            return validation_error

        return await self._execute_job_operation(
            "job_submission",
            self._submit_job_operation,
            entrypoint,
            runtime_env,
            job_id,
            metadata,
            **kwargs,
        )

    @ResponseFormatter.handle_exceptions("list jobs")
    async def list_jobs(self) -> Dict[str, Any]:
        """List all jobs."""
        try:
            self._ensure_initialized()

            if not self.job_client:
                # Try to create a job submission client using the dashboard URL
                if self.dashboard_url:
                    try:
                        LoggingUtility.log_info(
                            "job listing",
                            f"Creating job submission client for listing jobs with dashboard URL: {self.dashboard_url}",
                        )
                        if JobSubmissionClient is None:

                            raise ImportError("JobSubmissionClient not available")

                        job_client = JobSubmissionClient(self.dashboard_url)
                        jobs = job_client.list_jobs()

                        return ResponseFormatter.format_success_response(
                            result_type="success",
                            jobs=[
                                {
                                    "job_id": job.job_id,
                                    "status": job.status,
                                    "entrypoint": job.entrypoint,
                                    "start_time": job.start_time,
                                    "end_time": job.end_time,
                                    "metadata": job.metadata or {},
                                    "runtime_env": job.runtime_env or {},
                                }
                                for job in jobs
                            ],
                        )
                    except (ImportError, AttributeError) as e:
                        LoggingUtility.log_error(
                            "job listing", Exception(f"Job listing not available: {e}")
                        )
                        return {
                            "status": "error",
                            "message": f"Job listing not available: {str(e)}",
                        }
                    except (ConnectionError, TimeoutError) as e:
                        LoggingUtility.log_error(
                            "job listing",
                            Exception(f"Connection error during job listing: {e}"),
                        )
                        return {
                            "status": "error",
                            "message": f"Connection error: {str(e)}",
                        }
                    except (ValueError, TypeError) as e:
                        LoggingUtility.log_error(
                            "job listing",
                            Exception(f"Invalid parameters for job listing: {e}"),
                        )
                        return {
                            "status": "error",
                            "message": f"Invalid parameters: {str(e)}",
                        }
                    except RuntimeError as e:
                        LoggingUtility.log_error(
                            "job listing",
                            Exception(f"Runtime error during job listing: {e}"),
                        )
                        return {
                            "status": "error",
                            "message": f"Runtime error: {str(e)}",
                        }
                    except Exception as e:
                        LoggingUtility.log_error(
                            "job listing",
                            Exception(f"Unexpected error during job listing: {e}"),
                            exc_info=True,
                        )
                        return {
                            "status": "error",
                            "message": f"Unexpected error: {str(e)}",
                        }
                else:
                    return {
                        "status": "error",
                        "message": "Job listing not available: No dashboard URL available",
                    }
            if self.job_client is None:
                raise JobClientError("Job client is not initialized.")
            jobs = self.job_client.list_jobs()
            return ResponseFormatter.format_success_response(
                result_type="success",
                jobs=[
                    {
                        "job_id": job.job_id,
                        "status": job.status,
                        "entrypoint": job.entrypoint,
                        "start_time": job.start_time,
                        "end_time": job.end_time,
                        "metadata": job.metadata or {},
                        "runtime_env": job.runtime_env or {},
                    }
                    for job in jobs
                ],
            )

        except (KeyboardInterrupt, SystemExit):
            # Re-raise shutdown signals
            raise
        except JobSubmissionError as e:
            # Handle known job submission errors
            LoggingUtility.log_error(
                "job listing", Exception(f"Job listing error: {e}")
            )
            return {"status": "error", "message": str(e)}
        except (ConnectionError, TimeoutError) as e:
            LoggingUtility.log_error(
                "job listing",
                Exception(f"Connection error during job listing: {e}"),
            )
            return {"status": "error", "message": f"Connection error: {str(e)}"}
        except (ValueError, TypeError) as e:
            LoggingUtility.log_error(
                "job listing",
                Exception(f"Invalid parameters for job listing: {e}"),
            )
            return {"status": "error", "message": f"Invalid parameters: {str(e)}"}
        except RuntimeError as e:
            LoggingUtility.log_error(
                "job listing",
                Exception(f"Runtime error during job listing: {e}"),
            )
            return {"status": "error", "message": f"Runtime error: {str(e)}"}
        except Exception as e:
            # Log unexpected errors but don't mask them
            LoggingUtility.log_error(
                "job listing",
                Exception(f"Unexpected error during job listing: {e}"),
                exc_info=True,
            )
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    @ResponseFormatter.handle_exceptions("cancel job")
    async def cancel_job(self, job_id: str) -> Dict[str, Any]:
        """Cancel a job."""
        try:
            self._ensure_initialized()

            # Validate parameters
            if not job_id or not job_id.strip():
                raise JobValidationError("Job ID cannot be empty")

            if not self.job_client:
                # Try to create a job submission client using the dashboard URL
                if self.dashboard_url:
                    try:
                        LoggingUtility.log_info(
                            "job cancellation",
                            f"Creating job submission client for cancelling job with dashboard URL: {self.dashboard_url}",
                        )
                        if JobSubmissionClient is None:

                            raise ImportError("JobSubmissionClient not available")

                        job_client = JobSubmissionClient(self.dashboard_url)
                        success = job_client.stop_job(job_id)

                        if success:
                            return ResponseFormatter.format_success_response(
                                result_type="cancelled",
                                job_id=job_id,
                                message=f"Job {job_id} cancelled successfully using dashboard URL",
                            )
                        else:
                            return {
                                "status": "error",
                                "job_id": job_id,
                                "message": f"Failed to cancel job {job_id}",
                            }
                    except (ImportError, AttributeError) as e:
                        LoggingUtility.log_error(
                            "job cancellation",
                            Exception(f"Job cancellation not available: {e}"),
                        )
                        return {
                            "status": "error",
                            "message": f"Job cancellation not available: {str(e)}",
                        }
                    except (ConnectionError, TimeoutError) as e:
                        LoggingUtility.log_error(
                            "job cancellation",
                            Exception(f"Connection error during job cancellation: {e}"),
                        )
                        return {
                            "status": "error",
                            "message": f"Connection error: {str(e)}",
                        }
                    except (ValueError, TypeError) as e:
                        LoggingUtility.log_error(
                            "job cancellation",
                            Exception(f"Invalid parameters for job cancellation: {e}"),
                        )
                        return {
                            "status": "error",
                            "message": f"Invalid parameters: {str(e)}",
                        }
                    except RuntimeError as e:
                        LoggingUtility.log_error(
                            "job cancellation",
                            Exception(f"Runtime error during job cancellation: {e}"),
                        )
                        return {
                            "status": "error",
                            "message": f"Runtime error: {str(e)}",
                        }
                    except Exception as e:
                        LoggingUtility.log_error(
                            "job cancellation",
                            Exception(f"Unexpected error during job cancellation: {e}"),
                            exc_info=True,
                        )
                        return {
                            "status": "error",
                            "message": f"Unexpected error: {str(e)}",
                        }
                else:
                    return {
                        "status": "error",
                        "message": "Job cancellation not available: No dashboard URL available",
                    }
            if self.job_client is None:
                raise JobClientError("Job client is not initialized.")
            success = self.job_client.stop_job(job_id)
            if success:
                return ResponseFormatter.format_success_response(
                    result_type="cancelled",
                    job_id=job_id,
                    message=f"Job {job_id} cancelled successfully",
                )
            else:
                return {
                    "status": "error",
                    "job_id": job_id,
                    "message": f"Failed to cancel job {job_id}",
                }

        except (KeyboardInterrupt, SystemExit):
            # Re-raise shutdown signals
            raise
        except JobSubmissionError as e:
            # Handle known job submission errors
            LoggingUtility.log_error(
                "job cancellation", Exception(f"Job cancellation error: {e}")
            )
            return {"status": "error", "message": str(e)}
        except (ConnectionError, TimeoutError) as e:
            LoggingUtility.log_error(
                "job cancellation",
                Exception(f"Connection error during job cancellation: {e}"),
            )
            return {"status": "error", "message": f"Connection error: {str(e)}"}
        except (ValueError, TypeError) as e:
            LoggingUtility.log_error(
                "job cancellation",
                Exception(f"Invalid parameters for job cancellation: {e}"),
            )
            return {"status": "error", "message": f"Invalid parameters: {str(e)}"}
        except RuntimeError as e:
            LoggingUtility.log_error(
                "job cancellation",
                Exception(f"Runtime error during job cancellation: {e}"),
            )
            return {"status": "error", "message": f"Runtime error: {str(e)}"}
        except Exception as e:
            # Log unexpected errors but don't mask them
            LoggingUtility.log_error(
                "job cancellation",
                Exception(f"Unexpected error during job cancellation: {e}"),
                exc_info=True,
            )
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    async def retrieve_logs(
        self,
        identifier: str,
        log_type: str = "job",
        num_lines: int = 100,
        include_errors: bool = False,
        max_size_mb: int = 10,  # New parameter for size limit
    ) -> Dict[str, Any]:
        """
        Retrieve logs from Ray cluster for jobs, actors, or nodes with memory protection.

        Args:
            identifier: Job ID, actor ID/name, or node ID
            log_type: Type of logs to retrieve - 'job', 'actor', or 'node'
            num_lines: Number of log lines to retrieve (0 for all, max 10000)
            include_errors: Whether to include error analysis for jobs
            max_size_mb: Maximum size of logs in MB (1-100, default 10)

        Returns:
            Dictionary containing logs and metadata
        """
        try:
            self._ensure_initialized()

            # Validate parameters
            validation_error = self._validate_log_retrieval_params(
                identifier, log_type, num_lines, max_size_mb
            )
            if validation_error:
                return validation_error

            if log_type == "job":
                return await self._retrieve_job_logs_unified(
                    identifier, num_lines, include_errors, max_size_mb
                )
            elif log_type == "actor":
                return await self._retrieve_actor_logs_unified(
                    identifier, num_lines, max_size_mb
                )
            elif log_type == "node":
                return await self._retrieve_node_logs_unified(
                    identifier, num_lines, max_size_mb
                )
            else:
                # This should not happen due to validation, but kept for safety
                return self.response_formatter.format_validation_error(
                    f"Unsupported log type: {log_type}",
                    suggestion="Supported types: 'job', 'actor', 'node'",
                )

        except Exception as e:
            LoggingUtility.log_error(
                "retrieve logs", Exception(f"Failed to retrieve logs: {e}")
            )
            return self.response_formatter.format_error_response("retrieve logs", e)

    def _analyze_job_logs(self, logs: str) -> Dict[str, Any]:
        """Analyze job logs for errors and provide debugging suggestions."""
        if not logs:
            return {"error_count": 0, "errors": [], "suggestions": []}

        logs = str(logs)

        # Note: Size limits are now handled by the calling methods
        # This method receives pre-processed logs that are already within limits
        lines = logs.split("\n")

        error_lines = [
            line
            for line in lines
            if "error" in line.lower()
            or "exception" in line.lower()
            or "traceback" in line.lower()
        ]

        suggestions = []
        if error_lines:
            if any(
                "import" in line.lower() and "error" in line.lower()
                for line in error_lines
            ):
                suggestions.append(
                    "Import error detected. Check if all required packages are installed in the runtime environment."
                )

            if any(
                "memory" in line.lower() and "error" in line.lower()
                for line in error_lines
            ):
                suggestions.append(
                    "Memory error detected. Consider increasing object store memory or optimizing data usage."
                )

            if any("timeout" in line.lower() for line in error_lines):
                suggestions.append(
                    "Timeout detected. Check if the job is taking longer than expected or increase timeout limits."
                )

            if not suggestions:
                suggestions.append(
                    "Errors detected in logs. Check the complete logs for specific error messages."
                )
        else:
            suggestions.append("No obvious errors detected in the logs.")

        return {
            "error_count": len(error_lines),
            "errors": error_lines[-10:] if error_lines else [],  # Last 10 errors
            "suggestions": suggestions,
        }

    # ===== ENHANCED MONITORING =====

    # Note: monitor_job_progress functionality is now part of inspect_job method

    def _generate_health_recommendations(
        self, health_checks: Dict[str, bool]
    ) -> List[str]:
        """Generate health recommendations based on checks."""
        recommendations = []

        if not health_checks.get("all_nodes_alive", True):
            recommendations.append(
                "Some nodes are not alive. Check node connectivity and restart failed nodes."
            )

        if not health_checks.get("has_available_cpu", True):
            recommendations.append(
                "No available CPU resources. Consider scaling up the cluster or optimizing job resource usage."
            )

        if not health_checks.get("has_available_memory", True):
            recommendations.append(
                "Low memory available. Monitor memory usage and consider adding more nodes or optimizing memory usage."
            )

        if not recommendations:
            recommendations.append(
                "Cluster health is good. No immediate action required."
            )

        return recommendations

    # ===== WORKFLOW & ORCHESTRATION =====

    # ===== LOGS & DEBUGGING =====

    # Note: debug_job functionality is now part of inspect_job method

    def _generate_debug_suggestions(self, job_info, job_logs: str) -> List[str]:
        """Generate debug suggestions based on job info and logs."""
        suggestions = []

        # Check for common error patterns
        if "ImportError" in job_logs:
            suggestions.append(
                "ImportError detected. Check if all required packages are installed in the runtime environment."
            )
        if "ModuleNotFoundError" in job_logs:
            suggestions.append(
                "ModuleNotFoundError detected. Verify the module path and runtime environment configuration."
            )
        if "PermissionError" in job_logs:
            suggestions.append(
                "PermissionError detected. Check file permissions and access rights."
            )
        if "TimeoutError" in job_logs:
            suggestions.append(
                "TimeoutError detected. Consider increasing timeout values or optimizing the workload."
            )
        if "MemoryError" in job_logs:
            suggestions.append(
                "MemoryError detected. Consider reducing memory usage or increasing available memory."
            )

        # Check job status - handle both dict and JobDetails objects
        job_status = None
        if hasattr(job_info, "status"):
            # JobDetails object
            job_status = job_info.status
        elif isinstance(job_info, dict):
            # Dictionary
            job_status = job_info.get("status")

        if job_status == "FAILED":
            suggestions.append(
                "Job failed. Check the logs above for specific error details."
            )
        elif job_status == "PENDING":
            suggestions.append(
                "Job is pending. Check cluster resources and job queue status."
            )

        if not suggestions:
            suggestions.append(
                "No specific issues detected. Check the logs for more details."
            )

        return suggestions

    @ResponseFormatter.handle_exceptions("inspect job")
    async def inspect_job(self, job_id: str, mode: str = "status") -> Dict[str, Any]:
        """
        Inspect a job with different modes: 'status', 'logs', or 'debug'.

        Args:
            job_id: The job ID to inspect
            mode: Inspection mode - 'status' (basic info), 'logs' (with logs), or 'debug' (comprehensive debugging info)

        Returns:
            Dictionary containing job information based on the specified mode
        """
        try:
            self._ensure_initialized()

            if not self.job_client:
                # Try to create a job submission client using the dashboard URL
                if self.dashboard_url:
                    try:
                        LoggingUtility.log_info(
                            "inspect job",
                            f"Creating job submission client for inspection with dashboard URL: {self.dashboard_url}",
                        )
                        if JobSubmissionClient is None:

                            raise ImportError("JobSubmissionClient not available")

                        job_client = JobSubmissionClient(self.dashboard_url)
                        job_info = job_client.get_job_info(job_id)

                        # Base response with job status
                        response = {
                            "status": "success",
                            "job_id": job_id,
                            "job_status": job_info.status,
                            "entrypoint": job_info.entrypoint,
                            "start_time": job_info.start_time,
                            "end_time": job_info.end_time,
                            "metadata": job_info.metadata or {},
                            "runtime_env": job_info.runtime_env or {},
                            "message": job_info.message or "",
                            "inspection_mode": mode,
                            "logs": None,  # Initialize logs field for consistency
                            "debug_info": None,  # Initialize debug_info field for consistency
                        }

                        # Add logs if requested
                        if mode in ["logs", "debug"]:
                            try:
                                job_logs = job_client.get_job_logs(job_id)
                                response["logs"] = job_logs
                            except Exception as e:
                                response["logs"] = f"Failed to retrieve logs: {str(e)}"

                        # Add debugging information if requested
                        if mode == "debug":
                            response["debug_info"] = {
                                "error_logs": [
                                    line
                                    for line in str(response.get("logs", "")).split(
                                        "\n"
                                    )
                                    if "error" in line.lower()
                                    or "exception" in line.lower()
                                ],
                                "recent_logs": (
                                    str(response.get("logs", "")).split("\n")[-20:]
                                    if response.get("logs")
                                    else []
                                ),
                                "debugging_suggestions": self._generate_debug_suggestions(
                                    job_info, str(response.get("logs", ""))
                                ),
                            }

                        return response

                    except Exception as e:
                        LoggingUtility.log_error(
                            "inspect job",
                            Exception(
                                f"Failed to inspect job using dashboard URL: {e}"
                            ),
                        )
                        return self.response_formatter.format_error_response(
                            "inspect job using dashboard URL", e
                        )
                else:
                    return self.response_formatter.format_error_response(
                        "inspect job using dashboard URL",
                        Exception("No dashboard URL available"),
                    )

            # Use job client if available
            if self.job_client is None:
                return self.response_formatter.format_error_response(
                    "inspect job", Exception("Job client is not initialized.")
                )
            job_info = self.job_client.get_job_info(job_id)

            # Base response with job status
            response = {
                "status": "success",
                "job_id": job_id,
                "job_status": job_info.status,
                "entrypoint": job_info.entrypoint,
                "start_time": job_info.start_time,
                "end_time": job_info.end_time,
                "metadata": job_info.metadata or {},
                "runtime_env": job_info.runtime_env or {},
                "message": job_info.message or "",
                "inspection_mode": mode,
                "logs": None,  # Initialize logs field for consistency
                "debug_info": None,  # Initialize debug_info field for consistency
            }

            # Add logs if requested
            if mode in ["logs", "debug"]:
                try:
                    job_logs = self.job_client.get_job_logs(job_id)
                    response["logs"] = job_logs
                except Exception as e:
                    response["logs"] = f"Failed to retrieve logs: {str(e)}"

            # Add debugging information if requested
            if mode == "debug":
                response["debug_info"] = {
                    "error_logs": [
                        line
                        for line in str(response.get("logs", "")).split("\n")
                        if "error" in line.lower() or "exception" in line.lower()
                    ],
                    "recent_logs": (
                        str(response.get("logs", "")).split("\n")[-20:]
                        if response.get("logs")
                        else []
                    ),
                    "debugging_suggestions": self._generate_debug_suggestions(
                        job_info, str(response.get("logs", ""))
                    ),
                }

            return response

        except Exception as e:
            LoggingUtility.log_error(
                "inspect job", Exception(f"Failed to inspect job: {e}")
            )
            return self.response_formatter.format_error_response("inspect job", e)

    async def retrieve_logs_paginated(
        self,
        identifier: str,
        log_type: str = "job",
        page: int = 1,
        page_size: int = 100,
        max_size_mb: int = 10,
        include_errors: bool = False,
    ) -> Dict[str, Any]:
        """
        Retrieve logs from Ray cluster with pagination support for large log files.

        Args:
            identifier: Job ID, actor ID/name, or node ID
            log_type: Type of logs to retrieve - 'job', 'actor', or 'node'
            page: Page number (1-based)
            page_size: Number of lines per page
            max_size_mb: Maximum size of logs in MB (1-100, default 10)
            include_errors: Whether to include error analysis for jobs

        Returns:
            Dictionary containing logs, pagination info, and metadata
        """
        try:
            self._ensure_initialized()

            # Validate parameters
            validation_error = self._validate_log_retrieval_params(
                identifier, log_type, page_size, max_size_mb, page, page_size
            )
            if validation_error:
                return validation_error

            if log_type == "job":
                return await self._retrieve_job_logs_unified(
                    identifier, page_size, include_errors, max_size_mb, page, page_size
                )
            elif log_type == "actor":
                return await self._retrieve_actor_logs_unified(
                    identifier, page_size, max_size_mb, page, page_size
                )
            elif log_type == "node":
                return await self._retrieve_node_logs_unified(
                    identifier, page_size, max_size_mb, page, page_size
                )
            else:
                # This should not happen due to validation, but kept for safety
                return self.response_formatter.format_error_response(
                    "retrieve logs with pagination",
                    Exception(f"Unsupported log type: {log_type}"),
                )

        except Exception as e:
            LoggingUtility.log_error(
                "retrieve logs with pagination",
                Exception(f"Failed to retrieve logs with pagination: {e}"),
            )
            return self.response_formatter.format_error_response(
                "retrieve logs with pagination", e
            )

    async def _communicate_with_timeout(
        self, process, timeout: int = 30, max_output_size: int = 1024 * 1024
    ) -> tuple[str, str]:
        """Communicate with a process with timeout and output size limits.

        Uses asynchronous stream reading to avoid deadlocks when subprocess
        has large output that could fill the pipe buffer.

        Args:
            process: The subprocess to communicate with
            timeout: Timeout in seconds for the communication
            max_output_size: Maximum size of output to read in bytes

        Returns:
            Tuple of (stdout, stderr) strings

        Raises:
            RuntimeError: If process communication times out
        """
        stdout_chunks = []
        stderr_chunks = []
        stdout_size = 0
        stderr_size = 0

        async def read_stream(stream, chunks, size_tracker):
            """Read from a stream asynchronously with size limits."""
            nonlocal stdout_size, stderr_size

            if not stream or not hasattr(stream, "read"):
                return

            try:
                while True:
                    # Read in small chunks to avoid blocking
                    chunk = await asyncio.get_event_loop().run_in_executor(
                        None, stream.read, 8192
                    )
                    if not chunk:
                        break

                    # Calculate chunk size in bytes for limit checking
                    if isinstance(chunk, str):
                        chunk_size = len(chunk.encode("utf-8"))
                    else:
                        chunk_size = len(chunk)

                    if stream == process.stdout:
                        if stdout_size + chunk_size > max_output_size:
                            # Truncate to stay within limit
                            remaining = max_output_size - stdout_size
                            if remaining > 0:
                                if isinstance(chunk, str):
                                    # For strings, approximate truncation by character count
                                    char_remaining = (
                                        remaining // 2
                                    )  # Conservative estimate
                                    chunk = chunk[:char_remaining]
                                else:
                                    chunk = chunk[:remaining]
                                chunks.append(chunk)
                                stdout_size += (
                                    len(chunk.encode("utf-8"))
                                    if isinstance(chunk, str)
                                    else len(chunk)
                                )
                            break
                        stdout_size += chunk_size
                    else:  # stderr
                        if stderr_size + chunk_size > max_output_size:
                            # Truncate to stay within limit
                            remaining = max_output_size - stderr_size
                            if remaining > 0:
                                if isinstance(chunk, str):
                                    # For strings, approximate truncation by character count
                                    char_remaining = (
                                        remaining // 2
                                    )  # Conservative estimate
                                    chunk = chunk[:char_remaining]
                                else:
                                    chunk = chunk[:remaining]
                                chunks.append(chunk)
                                stderr_size += (
                                    len(chunk.encode("utf-8"))
                                    if isinstance(chunk, str)
                                    else len(chunk)
                                )
                            break
                        stderr_size += chunk_size

                    chunks.append(chunk)

            except Exception:
                # Stream might be closed or unavailable
                pass

        async def wait_for_process():
            """Wait for the process to complete."""
            while process.poll() is None:
                await asyncio.sleep(0.1)

        try:
            # Start reading both streams and wait for process completion
            tasks = [
                asyncio.create_task(
                    read_stream(process.stdout, stdout_chunks, stdout_size)
                ),
                asyncio.create_task(
                    read_stream(process.stderr, stderr_chunks, stderr_size)
                ),
                asyncio.create_task(wait_for_process()),
            ]

            # Wait for all tasks to complete or timeout
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), timeout=timeout
            )

            # Join the chunks - handle both bytes and string output
            if stdout_chunks:
                if isinstance(stdout_chunks[0], bytes):
                    stdout = b"".join(stdout_chunks).decode("utf-8", errors="replace")
                else:
                    stdout = "".join(stdout_chunks)
            else:
                stdout = ""

            if stderr_chunks:
                if isinstance(stderr_chunks[0], bytes):
                    stderr = b"".join(stderr_chunks).decode("utf-8", errors="replace")
                else:
                    stderr = "".join(stderr_chunks)
            else:
                stderr = ""

            return stdout, stderr

        except asyncio.TimeoutError:
            # Cancel all tasks and kill the process
            for task in tasks:
                if not task.done():
                    task.cancel()

            try:
                process.kill()
            except:
                pass

            raise RuntimeError(
                f"Process communication timed out after {timeout} seconds"
            )
        except Exception as e:
            # Cancel all tasks on any error
            for task in tasks:
                if not task.done():
                    task.cancel()
            raise RuntimeError(f"Process communication failed: {str(e)}")

    async def _initialize_job_client_with_retry(
        self, dashboard_url: str, max_retries: int = 3, retry_delay: float = 1.0
    ) -> Optional[Any]:
        """Initialize job client with retry logic."""
        if JobSubmissionClient is None:
            LoggingUtility.log_warning(
                "job_client", "JobSubmissionClient not available"
            )
            return None

        for attempt in range(max_retries):
            try:
                LoggingUtility.log_info(
                    "job_client",
                    f"Attempting to initialize job client (attempt {attempt + 1}/{max_retries})",
                )
                job_client = JobSubmissionClient(dashboard_url)
                LoggingUtility.log_info(
                    "job_client", "Job client initialized successfully"
                )
                return job_client
            except Exception as e:
                LoggingUtility.log_warning(
                    "job_client",
                    f"Job client initialization attempt {attempt + 1} failed: {e}",
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    LoggingUtility.log_error(
                        "job_client",
                        Exception(
                            f"Job client initialization failed after {max_retries} attempts"
                        ),
                    )
                    return None

    async def _initialize_job_client_if_available(self) -> str:
        """Initialize job client with retry logic if conditions are met.

        Returns:
            str: Status of job client initialization ("ready", "unavailable")
        """
        if JobSubmissionClient is not None and self.cluster_address:
            # Use the stored dashboard URL for job client
            if self.dashboard_url:
                LoggingUtility.log_info(
                    "job_client",
                    f"Initializing job client with dashboard URL: {self.dashboard_url}",
                )
                job_client = await self._initialize_job_client_with_retry(
                    self.dashboard_url
                )
                self._update_state(job_client=job_client)
                if self.job_client is None:
                    LoggingUtility.log_warning(
                        "job_client",
                        "Job client initialization failed after retries",
                    )
                    return "unavailable"
                else:
                    LoggingUtility.log_info(
                        "job_client", "Job client initialized successfully"
                    )
                    return "ready"
            else:
                LoggingUtility.log_warning(
                    "job_client",
                    "Dashboard URL not available for job client initialization",
                )
                return "unavailable"
        else:
            if JobSubmissionClient is None:
                LoggingUtility.log_warning(
                    "job_client", "JobSubmissionClient not available"
                )
            elif not self.cluster_address:
                LoggingUtility.log_warning(
                    "job_client",
                    "Cluster address not available for job client initialization",
                )
            return "unavailable"

    async def _stream_process_output(
        self,
        process,
        timeout: int = 30,
        max_lines: int = 1000,
        max_output_size: int = 1024 * 1024,
    ) -> tuple[str, str]:
        """Stream process output with proper memory limits to avoid memory leaks.

        Args:
            process: The subprocess to stream output from
            timeout: Timeout in seconds for the streaming
            max_lines: Maximum number of lines to collect per stream
            max_output_size: Maximum size of output in bytes per stream

        Returns:
            Tuple of (stdout, stderr) strings

        Raises:
            RuntimeError: If process startup times out
        """
        stdout_chunks = []
        stderr_chunks = []
        stdout_size = 0
        stderr_size = 0
        stdout_lines = 0
        stderr_lines = 0

        async def read_stream_line(stream):
            """Read a single line from stream with error handling."""
            try:
                if not stream or not hasattr(stream, "readline"):
                    return None
                line = await asyncio.get_event_loop().run_in_executor(
                    None, stream.readline
                )
                return line if line else None
            except Exception:
                return None

        async def _stream_output():
            nonlocal stdout_size, stderr_size, stdout_lines, stderr_lines

            while process.poll() is None:
                # Check if we've reached limits for both streams
                stdout_limit_reached = (
                    stdout_lines >= max_lines or stdout_size >= max_output_size
                )
                stderr_limit_reached = (
                    stderr_lines >= max_lines or stderr_size >= max_output_size
                )

                if stdout_limit_reached and stderr_limit_reached:
                    break

                # Read from stdout if not at limit
                if not stdout_limit_reached and process.stdout:
                    line = await read_stream_line(process.stdout)
                    if line:
                        line_str = (
                            line.decode().strip()
                            if isinstance(line, bytes)
                            else line.strip()
                        )
                        line_size = len(line_str.encode("utf-8"))

                        # Check if adding this line would exceed limits
                        if (
                            stdout_size + line_size <= max_output_size
                            and stdout_lines < max_lines
                        ):
                            stdout_chunks.append(line_str)
                            stdout_size += line_size
                            stdout_lines += 1

                # Read from stderr if not at limit
                if not stderr_limit_reached and process.stderr:
                    line = await read_stream_line(process.stderr)
                    if line:
                        line_str = (
                            line.decode().strip()
                            if isinstance(line, bytes)
                            else line.strip()
                        )
                        line_size = len(line_str.encode("utf-8"))

                        # Check if adding this line would exceed limits
                        if (
                            stderr_size + line_size <= max_output_size
                            and stderr_lines < max_lines
                        ):
                            stderr_chunks.append(line_str)
                            stderr_size += line_size
                            stderr_lines += 1

                await asyncio.sleep(0.1)

        try:
            await asyncio.wait_for(_stream_output(), timeout=timeout)
        except asyncio.TimeoutError:
            if hasattr(process, "kill"):
                process.kill()
            raise RuntimeError(f"Process startup timed out after {timeout} seconds")

        return "\n".join(stdout_chunks), "\n".join(stderr_chunks)

    def _filter_cluster_starting_parameters(
        self, kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Filter out parameters that are only valid for starting clusters, not connecting."""
        # Parameters that should be filtered out when connecting to existing cluster
        cluster_start_only_params = {
            "num_cpus",
            "num_gpus",
            "object_store_memory",
            "head_node_port",
            "dashboard_port",
            "head_node_host",
            "worker_nodes",
        }

        return {k: v for k, v in kwargs.items() if k not in cluster_start_only_params}

    # ===== LOG RETRIEVAL HELPERS =====
    # REFACTORING COMPLETED: These methods consolidate redundant log retrieval logic
    # that was previously duplicated across 8+ methods (retrieve_logs, retrieve_logs_paginated,
    # and their 6 variants for job/actor/node types).
    #
    # Key improvements:
    # 1. Unified job client creation with standardized error handling
    # 2. Consolidated parameter validation for all log retrieval operations
    # 3. Single unified job log retrieval method handling both regular and paginated modes
    # 4. Standardized placeholder responses for actor/node logs
    # 5. Eliminated ~500 lines of redundant code
    # 6. Consistent error handling and response formatting

    async def _get_or_create_job_client(self, operation_name: str) -> Optional[Any]:
        """Get existing job client or create a new one with standardized error handling."""
        if self.job_client:
            return self.job_client

        if not self.dashboard_url:
            LoggingUtility.log_warning(
                operation_name, "Job client not available: No dashboard URL available"
            )
            return None

        if JobSubmissionClient is None:
            LoggingUtility.log_warning(
                operation_name, "JobSubmissionClient not available"
            )
            return None

        try:
            LoggingUtility.log_info(
                operation_name,
                f"Creating job submission client with dashboard URL: {self.dashboard_url}",
            )
            return JobSubmissionClient(self.dashboard_url)
        except Exception as e:
            LoggingUtility.log_error(
                operation_name, Exception(f"Failed to create job client: {e}")
            )
            return None

    def _validate_log_retrieval_params(
        self,
        identifier: str,
        log_type: str,
        num_lines: int = 0,
        max_size_mb: int = 10,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Validate parameters for log retrieval operations."""
        if not identifier or not identifier.strip():
            return self.response_formatter.format_validation_error(
                "Identifier cannot be empty"
            )

        if log_type not in ["job", "actor", "node"]:
            return self.response_formatter.format_validation_error(
                f"Unsupported log type: {log_type}",
                suggestion="Supported types: 'job', 'actor', 'node'",
            )

        # Validate basic log parameters
        validation_error = self.log_processor.validate_log_parameters(
            num_lines or 100, max_size_mb
        )
        if validation_error:
            return validation_error

        # Validate pagination parameters if provided
        if page is not None:
            if page < 1:
                return self.response_formatter.format_validation_error(
                    "page must be positive"
                )
        if page_size is not None:
            if page_size <= 0 or page_size > 1000:
                return self.response_formatter.format_validation_error(
                    "page_size must be between 1 and 1000"
                )

        return None

    async def _retrieve_job_logs_unified(
        self,
        job_id: str,
        num_lines: int = 100,
        include_errors: bool = False,
        max_size_mb: int = 10,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Unified job log retrieval handling both regular and paginated modes."""
        try:
            # Get job client
            job_client = await self._get_or_create_job_client("job_logs")
            if not job_client:
                return self.response_formatter.format_error_response(
                    "retrieve job logs", Exception("Job client not available")
                )

            # Get raw logs
            try:
                logs = job_client.get_job_logs(job_id)
            except Exception as e:
                return self.response_formatter.format_error_response(
                    "retrieve job logs", Exception(f"Failed to get job logs: {e}")
                )

            # Process logs based on mode
            if page is not None and page_size is not None:
                # Paginated mode
                result = await self.log_processor.stream_logs_with_pagination(
                    logs, page, page_size, max_size_mb
                )

                if result["status"] != "success":
                    return result

                response = {
                    "status": "success",
                    "log_type": "job",
                    "identifier": job_id,
                    "logs": result["logs"],
                    "pagination": result["pagination"],
                    "size_info": result["size_info"],
                }
            else:
                # Regular mode
                # Check size before processing
                if logs and len(logs.encode("utf-8")) > max_size_mb * 1024 * 1024:
                    truncated_logs = self.log_processor.truncate_logs_to_size(
                        logs, max_size_mb
                    )
                    response = {
                        "status": "success",
                        "log_type": "job",
                        "identifier": job_id,
                        "logs": truncated_logs,
                        "warning": f"Logs truncated to {max_size_mb}MB limit",
                        "original_size_mb": len(logs.encode("utf-8")) / (1024 * 1024),
                    }
                else:
                    # Apply line limit if specified
                    if num_lines > 0:
                        logs = await self.log_processor.stream_logs_async(
                            logs, num_lines, max_size_mb
                        )

                    response = {
                        "status": "success",
                        "log_type": "job",
                        "identifier": job_id,
                        "logs": logs,
                    }

            # Add error analysis if requested
            if include_errors:
                response["error_analysis"] = self._analyze_job_logs(
                    response.get("logs", "")
                )

            return response

        except Exception as e:
            LoggingUtility.log_error(
                "job logs", Exception(f"Failed to retrieve job logs: {e}")
            )
            return self.response_formatter.format_error_response("retrieve job logs", e)

    def _create_placeholder_log_response(
        self,
        log_type: str,
        identifier: str,
        num_lines: int,
        max_size_mb: int,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        additional_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create standardized placeholder response for actor/node logs."""
        response = {
            "status": "partial",
            "log_type": log_type,
            "identifier": identifier,
            "message": f"{log_type.title()} logs are not directly accessible through Ray Python API",
            "suggestions": [
                f"Check Ray dashboard for {log_type} logs",
                f"Use Ray CLI: ray logs --{log_type}-id <{log_type}_id>",
                "Monitor through dashboard at http://localhost:8265",
            ],
        }

        if additional_info:
            response.update(additional_info)

        # Add pagination info if in paginated mode
        if page is not None and page_size is not None:
            response["pagination"] = {
                "current_page": page,
                "total_pages": 0,
                "page_size": page_size,
                "total_lines": 0,
                "lines_in_page": 0,
                "has_next": False,
                "has_previous": False,
            }
            note_params = (
                f"page={page}, page_size={page_size}, max_size_mb={max_size_mb}"
            )
        else:
            note_params = f"num_lines={num_lines}, max_size_mb={max_size_mb}"

        response["note"] = (
            f"Log retrieval parameters ({note_params}) will be applied when direct access is implemented"
        )

        return response

    async def _retrieve_actor_logs_unified(
        self,
        actor_identifier: str,
        num_lines: int = 100,
        max_size_mb: int = 10,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Unified actor log retrieval handling both regular and paginated modes."""
        try:
            if not RAY_AVAILABLE or ray is None:
                return ResponseFormatter.format_error_response(
                    "retrieve actor logs", Exception("Ray is not available")
                )

            # Try to get actor information for additional context
            additional_info = {}
            try:
                if len(actor_identifier) == 32 and all(
                    c in "0123456789abcdefABCDEF" for c in actor_identifier
                ):
                    actor_handle = ray.get_actor(actor_identifier)
                else:
                    # Treat as an actor name, search across namespaces
                    actor_handle = ray.get_actor(actor_identifier, namespace="*")

                additional_info["actor_info"] = {
                    "actor_id": actor_handle._actor_id.hex(),
                    "state": "ALIVE",
                }
            except ValueError:
                return ResponseFormatter.format_validation_error(
                    f"Actor {actor_identifier} not found",
                    suggestion="Check Ray dashboard for available actors",
                )

            return self._create_placeholder_log_response(
                "actor",
                actor_identifier,
                num_lines,
                max_size_mb,
                page,
                page_size,
                additional_info,
            )

        except Exception as e:
            LoggingUtility.log_error(
                "actor logs", Exception(f"Failed to retrieve actor logs: {e}")
            )
            return self.response_formatter.format_error_response(
                "retrieve actor logs", e
            )

    async def _retrieve_node_logs_unified(
        self,
        node_id: str,
        num_lines: int = 100,
        max_size_mb: int = 10,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Unified node log retrieval handling both regular and paginated modes."""
        try:
            if not RAY_AVAILABLE or ray is None:
                return ResponseFormatter.format_error_response(
                    "retrieve node logs", Exception("Ray is not available")
                )

            # Get node information for additional context
            nodes = ray.nodes()
            target_node = None

            for node in nodes:
                if node["NodeID"] == node_id:
                    target_node = node
                    break

            if not target_node:
                return ResponseFormatter.format_validation_error(
                    f"Node {node_id} not found",
                    suggestion="Use inspect_ray tool to see available nodes",
                )

            additional_info = {
                "node_info": {
                    "node_id": target_node["NodeID"],
                    "alive": target_node["Alive"],
                    "node_name": target_node.get("NodeName", ""),
                    "node_manager_address": target_node.get("NodeManagerAddress", ""),
                }
            }

            return self._create_placeholder_log_response(
                "node",
                node_id,
                num_lines,
                max_size_mb,
                page,
                page_size,
                additional_info,
            )

        except Exception as e:
            LoggingUtility.log_error(
                "node logs", Exception(f"Failed to retrieve node logs: {e}")
            )
            return self.response_formatter.format_error_response(
                "retrieve node logs", e
            )

    # ===== JOB OPERATION HELPERS =====
    # Additional refactoring for job submission, listing, cancellation, and inspection methods

    def _format_job_info(self, job) -> Dict[str, Any]:
        """Standardize job information formatting across all job operations."""
        return {
            "job_id": job.job_id,
            "status": job.status,
            "entrypoint": job.entrypoint,
            "start_time": job.start_time,
            "end_time": job.end_time,
            "metadata": job.metadata or {},
            "runtime_env": job.runtime_env or {},
        }

    def _validate_job_id(
        self, job_id: str, operation_name: str
    ) -> Optional[Dict[str, Any]]:
        """Validate job ID parameter for job operations."""
        if not job_id or not job_id.strip():
            return self.response_formatter.format_validation_error(
                f"Job ID cannot be empty for {operation_name}"
            )
        return None

    def _validate_entrypoint(self, entrypoint: str) -> Optional[Dict[str, Any]]:
        """Validate entrypoint parameter for job submission."""
        if not entrypoint or not entrypoint.strip():
            return self.response_formatter.format_validation_error(
                "Entrypoint cannot be empty"
            )
        return None

    async def _execute_job_operation(
        self, operation_name: str, job_operation_func, *args, **kwargs
    ) -> Dict[str, Any]:
        """
        Execute a job operation with unified error handling and job client management.

        Args:
            operation_name: Name of the operation for logging (e.g., "job_submission")
            job_operation_func: Function to execute that takes (job_client, *args, **kwargs)
            *args, **kwargs: Arguments to pass to the operation function

        Returns:
            Standardized response dictionary
        """
        try:
            self._ensure_initialized()

            # Get or create job client
            job_client = await self._get_or_create_job_client(operation_name)
            if not job_client:
                return self.response_formatter.format_error_response(
                    operation_name, Exception("Job client not available")
                )

            # Execute the specific operation
            return await job_operation_func(job_client, *args, **kwargs)

        except (KeyboardInterrupt, SystemExit):
            # Re-raise shutdown signals
            raise
        except JobSubmissionError as e:
            LoggingUtility.log_error(
                operation_name, Exception(f"{operation_name} error: {e}")
            )
            return {"status": "error", "message": str(e)}
        except (ConnectionError, TimeoutError) as e:
            LoggingUtility.log_error(
                operation_name,
                Exception(f"Connection error during {operation_name}: {e}"),
            )
            return {"status": "error", "message": f"Connection error: {str(e)}"}
        except (ValueError, TypeError) as e:
            LoggingUtility.log_error(
                operation_name,
                Exception(f"Invalid parameters for {operation_name}: {e}"),
            )
            return {"status": "error", "message": f"Invalid parameters: {str(e)}"}
        except RuntimeError as e:
            LoggingUtility.log_error(
                operation_name, Exception(f"Runtime error during {operation_name}: {e}")
            )
            return {"status": "error", "message": f"Runtime error: {str(e)}"}
        except Exception as e:
            LoggingUtility.log_error(
                operation_name,
                Exception(f"Unexpected error during {operation_name}: {e}"),
                exc_info=True,
            )
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    async def _submit_job_operation(
        self,
        job_client,
        entrypoint: str,
        runtime_env: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute the actual job submission operation."""
        # Entrypoint validation is now done upfront in submit_job method

        # Prepare submit arguments
        submit_kwargs: Dict[str, Any] = {"entrypoint": entrypoint}

        if runtime_env is not None:
            submit_kwargs["runtime_env"] = runtime_env
        if job_id is not None:
            submit_kwargs["job_id"] = job_id
        if metadata is not None:
            submit_kwargs["metadata"] = metadata

        # Add any additional kwargs
        for key, value in kwargs.items():
            if key not in submit_kwargs and value is not None:
                submit_kwargs[key] = value

        # Submit the job
        submitted_job_id = job_client.submit_job(**submit_kwargs)
        return ResponseFormatter.format_success_response(
            result_type="submitted",
            job_id=submitted_job_id,
            message=f"Job {submitted_job_id} submitted successfully",
        )

    async def _list_jobs_operation(self, job_client) -> Dict[str, Any]:
        """Execute the actual job listing operation."""
        jobs = job_client.list_jobs()
        return ResponseFormatter.format_success_response(
            result_type="success",
            jobs=[self._format_job_info(job) for job in jobs],
        )

    async def _cancel_job_operation(self, job_client, job_id: str) -> Dict[str, Any]:
        """Execute the actual job cancellation operation."""
        # Validate job ID
        validation_error = self._validate_job_id(job_id, "job cancellation")
        if validation_error:
            return validation_error

        success = job_client.stop_job(job_id)
        if success:
            return ResponseFormatter.format_success_response(
                result_type="cancelled",
                job_id=job_id,
                message=f"Job {job_id} cancelled successfully",
            )
        else:
            return {
                "status": "error",
                "job_id": job_id,
                "message": f"Failed to cancel job {job_id}",
            }

    async def _inspect_job_operation(
        self, job_client, job_id: str, mode: str = "status"
    ) -> Dict[str, Any]:
        """Execute the actual job inspection operation."""
        # Validate job ID
        validation_error = self._validate_job_id(job_id, "job inspection")
        if validation_error:
            return validation_error

        job_info = job_client.get_job_info(job_id)

        # Base response with job status
        response = {
            "status": "success",
            "job_id": job_id,
            "job_status": job_info.status,
            "entrypoint": job_info.entrypoint,
            "start_time": job_info.start_time,
            "end_time": job_info.end_time,
            "metadata": job_info.metadata or {},
            "runtime_env": job_info.runtime_env or {},
            "message": job_info.message or "",
            "inspection_mode": mode,
            "logs": None,
            "debug_info": None,
        }

        # Add logs if requested
        if mode in ["logs", "debug"]:
            try:
                job_logs = job_client.get_job_logs(job_id)
                response["logs"] = job_logs
            except Exception as e:
                response["logs"] = f"Failed to retrieve logs: {str(e)}"

        # Add debugging information if requested
        if mode == "debug":
            response["debug_info"] = {
                "error_logs": [
                    line
                    for line in str(response.get("logs", "")).split("\n")
                    if "error" in line.lower() or "exception" in line.lower()
                ],
                "recent_logs": (
                    str(response.get("logs", "")).split("\n")[-20:]
                    if response.get("logs")
                    else []
                ),
                "debugging_suggestions": self._generate_debug_suggestions(
                    job_info, str(response.get("logs", ""))
                ),
            }

        return response
