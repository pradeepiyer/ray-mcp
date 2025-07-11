"""Centralized cluster management for Ray."""

import asyncio
import json
import os
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from ..foundation.base_managers import ResourceManager
from ..foundation.interfaces import ClusterManager, ManagedComponent, StateManager
from .port_manager import PortManager


class RayClusterManager(ResourceManager, ClusterManager, ManagedComponent):
    """Manages Ray cluster lifecycle operations with clean separation of concerns."""

    def __init__(
        self,
        state_manager,
        port_manager: PortManager,
    ):
        # Initialize both parent classes
        ResourceManager.__init__(
            self,
            state_manager,
            enable_ray=True,
            enable_kubernetes=False,
            enable_cloud=False,
        )
        ManagedComponent.__init__(self, state_manager)

        self._port_manager = port_manager
        self._head_node_process: Optional[subprocess.Popen] = None
        # Simple worker tracking (replacing WorkerManager)
        self._worker_processes: List[subprocess.Popen] = []
        self._worker_configs: List[Dict[str, Any]] = []

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
        """Initialize Ray cluster - connect to existing or start new cluster."""
        return await self._execute_operation(
            "init cluster",
            self._init_cluster_operation,
            address,
            num_cpus,
            num_gpus,
            object_store_memory,
            worker_nodes,
            head_node_port,
            dashboard_port,
            head_node_host,
            **kwargs,
        )

    async def _init_cluster_operation(
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
        """Execute cluster initialization operation."""
        self._ensure_ray_available()

        # If address provided, connect to existing cluster
        if address:
            return await self._connect_to_existing_cluster(address)

        # Otherwise, start new cluster
        return await self._start_new_cluster(
            num_cpus=num_cpus,
            num_gpus=num_gpus,
            object_store_memory=object_store_memory,
            worker_nodes=worker_nodes,
            head_node_port=head_node_port,
            dashboard_port=dashboard_port,
            head_node_host=head_node_host,
            **kwargs,
        )

    async def stop_cluster(self) -> Dict[str, Any]:
        """Stop the Ray cluster and clean up resources."""
        try:
            return await self._execute_operation(
                "stop cluster", self._stop_cluster_operation
            )
        finally:
            # Always reset state, even if cleanup fails
            self._reset_state()

    async def _stop_cluster_operation(self) -> Dict[str, Any]:
        """Execute cluster stop operation."""
        # Get connection type from state to determine appropriate cleanup
        connection_type = self._get_state_value("connection_type")

        if connection_type == "existing":
            return await self._disconnect_from_existing_cluster()
        else:
            return await self._stop_local_cluster()

    async def inspect_cluster(self) -> Dict[str, Any]:
        """Get basic cluster information."""
        return await self._execute_operation(
            "inspect cluster", self._inspect_cluster_operation
        )

    async def _inspect_cluster_operation(self) -> Dict[str, Any]:
        """Execute cluster inspection operation."""
        # Use ManagedComponent validation method instead of ResourceManager's
        self._ensure_ray_initialized()

        cluster_info = {}

        # Use cluster_status to avoid collision with response status
        cluster_info["cluster_status"] = (
            "running" if self._ray and self._ray.is_initialized() else "not_running"
        )
        cluster_info["ray_version"] = (
            self._ray.__version__ if self._ray else "unavailable"
        )

        return cluster_info

    async def _disconnect_from_existing_cluster(self) -> Dict[str, Any]:
        """Disconnect from existing Ray cluster without stopping remote cluster."""
        self._LoggingUtility.log_info(
            "cluster_disconnect", "Disconnecting from existing Ray cluster..."
        )

        # Only shutdown local Ray instance - this doesn't affect the remote cluster
        if self._ray and self._ray.is_initialized():
            self._ray.shutdown()
            self._LoggingUtility.log_info(
                "cluster_disconnect", "Local Ray instance shutdown completed"
            )

        return {
            "message": "Successfully disconnected from existing Ray cluster",
            "connection_type": "existing",
            "action": "disconnected",
        }

    async def _stop_local_cluster(self) -> Dict[str, Any]:
        """Stop locally-started Ray cluster and clean up all resources."""
        cleanup_results = []

        # Stop worker nodes first using simplified method
        if self._worker_processes:
            self._LoggingUtility.log_info("cluster_cleanup", "Stopping worker nodes...")
            worker_results = await self._stop_all_workers()
            cleanup_results.extend(worker_results)

        # Clean up head node process reference
        # Note: The 'ray start' command has already exited after starting Ray daemon processes.
        # The actual Ray cluster cleanup is handled by ray.shutdown() below.
        if self._head_node_process:
            self._LoggingUtility.log_info(
                "cluster_cleanup", "Head node command already completed"
            )
            self._head_node_process = None

        # Shutdown Ray if initialized
        if self._ray and self._ray.is_initialized():
            self._ray.shutdown()
            self._LoggingUtility.log_info("cluster_cleanup", "Ray shutdown completed")

        return {
            "message": "Ray cluster stopped successfully",
            "connection_type": "new",
            "action": "stopped",
            "cleanup_results": cleanup_results,
        }

    def _validate_cluster_address(self, address: str) -> bool:
        """Validate cluster address format supporting IPv4 and hostnames."""
        if not address or ":" not in address:
            return False

        # Handle IPv4 addresses and hostnames with port: host:port
        if address.count(":") == 1:
            parts = address.split(":")
            if len(parts) == 2:
                host_part, port_part = parts
                return self._validate_ipv4_or_hostname(
                    host_part
                ) and self._validate_port(port_part)

        return False

    def _validate_ipv4_or_hostname(self, host: str) -> bool:
        """Validate IPv4 address or hostname."""
        if not host:
            return False

        # Check if this looks like an IPv4 address (contains only digits, dots)
        if "." in host:
            parts = host.split(".")

            # If it looks like an IPv4 pattern (all parts are digits), validate strictly
            looks_like_ipv4 = all(part.isdigit() for part in parts if part)

            if looks_like_ipv4:
                # This looks like an IPv4 address, validate it strictly
                if len(parts) != 4:
                    return False  # Invalid IPv4, don't fall through to hostname

                try:
                    for part in parts:
                        if not part:  # Empty part
                            return False
                        num = int(part)
                        if num < 0 or num > 255:
                            return False
                    return True  # Valid IPv4
                except ValueError:
                    return False  # Invalid IPv4

        # Check for hostname/domain format
        hostname_pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
        return bool(re.match(hostname_pattern, host))

    def _validate_port(self, port: str) -> bool:
        """Validate port number."""
        try:
            port_num = int(port)
            return 1 <= port_num <= 65535
        except (ValueError, TypeError):
            return False

    def _parse_cluster_address(self, address: str) -> Tuple[str, int]:
        """Parse cluster address and return host and port.

        Args:
            address: Address in format "host:port"

        Returns:
            Tuple of (host, port)

        Raises:
            ValueError: If address format is invalid
        """
        if not self._validate_cluster_address(address):
            raise ValueError(f"Invalid cluster address format: {address}")

        # Handle IPv4 addresses or hostnames host:port
        if address.count(":") == 1:
            host, port_str = address.split(":")
            port = int(port_str)
            return host, port

        raise ValueError(f"Unable to parse cluster address: {address}")

    async def _connect_to_existing_cluster(self, address: str) -> Dict[str, Any]:
        """Connect to an existing Ray cluster via dashboard API with atomic state updates."""
        try:
            # Validate address format
            if not self._validate_cluster_address(address):
                return self._ResponseFormatter.format_validation_error(
                    f"Invalid cluster address format: {address}"
                )

            # Parse address to construct dashboard URL
            try:
                host, port = self._parse_cluster_address(address)
            except ValueError as e:
                return self._ResponseFormatter.format_validation_error(str(e))

            dashboard_port = 8265  # Standard Ray dashboard port
            dashboard_url = f"http://{host}:{dashboard_port}"

            # Test connection via dashboard API
            if not self._JobSubmissionClient:
                return self._ResponseFormatter.format_error_response(
                    "connect to cluster",
                    Exception(
                        "JobSubmissionClient not available - Ray not properly installed"
                    ),
                )

            # Verify cluster connectivity via dashboard API
            job_client = await self._test_dashboard_connection(dashboard_url)
            if not job_client:
                return self._ResponseFormatter.format_error_response(
                    "connect to cluster",
                    Exception(f"Failed to connect to Ray dashboard at {dashboard_url}"),
                )

            # Initialize local Ray without connecting to remote cluster
            # This gives us access to Ray APIs for cluster inspection
            if self._ray and not self._ray.is_initialized():
                self._ray.init(ignore_reinit_error=True)

            # Query the actual GCS address from the Ray cluster after connection
            actual_gcs_address = await self._get_actual_gcs_address()

            # Apply all state updates atomically in a single batch
            self.state_manager.update_state(
                initialized=True,
                cluster_address=address,
                gcs_address=actual_gcs_address,
                dashboard_url=dashboard_url,
                job_client=job_client,
                connection_type="existing",
            )

            return self._ResponseFormatter.format_success_response(
                message=f"Successfully connected to Ray cluster via dashboard API at {dashboard_url}",
                cluster_address=address,
                dashboard_url=dashboard_url,
                connection_type="existing",
            )

        except Exception as e:
            # No state changes have been made if we reach this point
            self._LoggingUtility.log_error("connect to cluster", e)
            return self._ResponseFormatter.format_error_response(
                "connect to cluster", e
            )

    async def _start_new_cluster(self, **kwargs) -> Dict[str, Any]:
        """Start a new Ray cluster with atomic state updates."""
        try:
            # Use Ray's default approach - let Ray handle port allocation
            # This avoids port conflicts and is more reliable
            dashboard_port = kwargs.get(
                "dashboard_port"
            ) or await self._port_manager.find_free_port(8265)

            # Build head node command (without manual port specification)
            build_kwargs = {
                k: v
                for k, v in kwargs.items()
                if k not in ["head_node_port", "dashboard_port"]
            }
            head_cmd = await self._build_head_node_command(
                dashboard_port=dashboard_port, **build_kwargs
            )

            # Start head node process
            self._head_node_process = await self._start_head_node_process(head_cmd)
            if not self._head_node_process:
                return self._ResponseFormatter.format_error_response(
                    "start cluster", Exception("Failed to start head node process")
                )

            # Wait for cluster to be ready and initialize Ray to get actual address
            host = kwargs.get("head_node_host", "127.0.0.1")
            dashboard_url = f"http://{host}:{dashboard_port}"

            # Wait for the head node to be fully ready before connecting
            await self._wait_for_head_node_ready(dashboard_port, host)

            # Initialize Ray and let it detect the cluster
            if self._ray:
                self._ray.init(ignore_reinit_error=True)

            # Get the actual cluster address from Ray
            runtime_context = self._ray.get_runtime_context() if self._ray else None
            gcs_address = runtime_context.gcs_address if runtime_context else None
            cluster_address = gcs_address or f"{host}:10001"  # fallback

            # Start worker nodes if requested
            worker_results = []
            worker_nodes = kwargs.get("worker_nodes")
            if worker_nodes is not None and len(worker_nodes) > 0:
                worker_results = await self._start_worker_nodes(
                    worker_nodes, cluster_address
                )
            elif worker_nodes is None:
                # Default: start 2 worker nodes
                default_workers = self._get_default_worker_config()
                worker_results = await self._start_worker_nodes(
                    default_workers, cluster_address
                )

            # Apply all state updates atomically in a single batch
            self.state_manager.update_state(
                initialized=True,
                cluster_address=cluster_address,
                gcs_address=gcs_address,
                dashboard_url=dashboard_url,
                connection_type="new",
            )

            return self._ResponseFormatter.format_success_response(
                message="Ray cluster started successfully",
                result_type="started",
                cluster_address=cluster_address,
                dashboard_url=dashboard_url,
                gcs_address=gcs_address,
                dashboard_port=dashboard_port,
                worker_results=worker_results,
                connection_type="new",
            )

        except Exception as e:
            # Cleanup on failure - no state changes have been made
            # Note: The 'ray start' command has already exited, so we just need to clear the reference.
            # Ray daemon processes (if started) will be cleaned up by the OS or manual intervention.
            if self._head_node_process:
                self._LoggingUtility.log_info(
                    "cluster_cleanup",
                    "Clearing head node process reference after failure",
                )
                self._head_node_process = None
            return self._ResponseFormatter.format_error_response("start cluster", e)

    async def _build_head_node_command(
        self, dashboard_port: int, **kwargs
    ) -> List[str]:
        """Build the command to start Ray head node."""
        cmd = [
            "ray",
            "start",
            "--head",
            "--dashboard-port",
            str(dashboard_port),
            "--dashboard-host",
            "0.0.0.0",
        ]

        # Add resource specifications
        if kwargs.get("num_cpus"):
            cmd.extend(["--num-cpus", str(kwargs["num_cpus"])])
        if kwargs.get("num_gpus"):
            cmd.extend(["--num-gpus", str(kwargs["num_gpus"])])
        if kwargs.get("object_store_memory"):
            cmd.extend(["--object-store-memory", str(kwargs["object_store_memory"])])

        # Add Ray options
        cmd.extend(["--disable-usage-stats", "--verbose"])

        return cmd

    async def _start_head_node_process(
        self, cmd: List[str]
    ) -> Optional[subprocess.Popen]:
        """Start the head node process."""
        try:
            self._LoggingUtility.log_info(
                "cluster_start", f"Starting head node: {' '.join(cmd)}"
            )

            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )

            # Wait for the command to complete (ray start exits after starting the cluster)
            stdout, stderr = process.communicate()

            # Check if the command completed successfully
            if process.returncode == 0:
                self._LoggingUtility.log_info(
                    "cluster_start", "Head node command completed successfully"
                )
                self._LoggingUtility.log_debug("cluster_start", f"STDOUT: {stdout}")
                # Ray start command succeeded - Ray cluster is now running as daemon processes
                return process
            else:
                self._LoggingUtility.log_error(
                    "cluster_start",
                    Exception(
                        f"Head node command failed with return code {process.returncode}. STDOUT: {stdout}, STDERR: {stderr}"
                    ),
                )
                return None

        except Exception as e:
            self._LoggingUtility.log_error("start head node process", e)
            return None

    async def _test_dashboard_connection(
        self, dashboard_url: str, max_retries: int = 3, retry_delay: float = 1.0
    ) -> Optional[Any]:
        """Test connection to Ray dashboard API."""
        if not self._JobSubmissionClient:
            return None

        for attempt in range(max_retries):
            try:
                self._LoggingUtility.log_info(
                    "dashboard_connect",
                    f"Testing dashboard connection (attempt {attempt + 1}/{max_retries}): {dashboard_url}",
                )

                # Create client and test connection
                job_client = self._JobSubmissionClient(dashboard_url)

                # Test the connection by listing jobs
                _ = job_client.list_jobs()

                self._LoggingUtility.log_info(
                    "dashboard_connect", "Dashboard connection successful"
                )
                return job_client

            except Exception as e:
                self._LoggingUtility.log_warning(
                    "dashboard_connect", f"Attempt {attempt + 1} failed: {e}"
                )

                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff

        self._LoggingUtility.log_error(
            "dashboard_connect",
            Exception(f"Failed to connect to dashboard after {max_retries} attempts"),
        )
        return None

    def _get_default_worker_config(self) -> List[Dict[str, Any]]:
        """Get default worker node configuration."""
        return [
            {"num_cpus": 1, "node_name": "worker-1"},
            {"num_cpus": 1, "node_name": "worker-2"},
        ]

    async def _wait_for_head_node_ready(
        self, dashboard_port: int, host: str, max_wait: int = 10
    ) -> None:
        """Wait for the head node to be fully ready before connecting."""
        dashboard_url = f"http://{host}:{dashboard_port}"

        for attempt in range(max_wait):
            try:
                # Try to connect to the dashboard to see if Ray is ready
                if self._JobSubmissionClient:
                    job_client = self._JobSubmissionClient(dashboard_url)
                    _ = job_client.list_jobs()  # This will fail if Ray isn't ready
                    self._LoggingUtility.log_info(
                        "head_node_ready",
                        f"Head node ready after {attempt + 1} seconds",
                    )
                    return
            except Exception as e:
                self._LoggingUtility.log_debug(
                    "head_node_ready", f"Attempt {attempt + 1}: {e}"
                )

            await asyncio.sleep(1.0)

        self._LoggingUtility.log_warning(
            "head_node_ready",
            f"Head node may not be fully ready after {max_wait} seconds, proceeding anyway",
        )

    async def _get_actual_gcs_address(self) -> Optional[str]:
        """Get the actual GCS address from Ray runtime context."""
        try:
            if not self._ray or not self._ray.is_initialized():
                self._LoggingUtility.log_warning(
                    "get_gcs_address", "Ray is not initialized, cannot get GCS address"
                )
                return None

            runtime_context = self._ray.get_runtime_context()
            if not runtime_context:
                self._LoggingUtility.log_warning(
                    "get_gcs_address", "Ray runtime context is not available"
                )
                return None

            gcs_address = getattr(runtime_context, "gcs_address", None)
            if gcs_address:
                self._LoggingUtility.log_info(
                    "get_gcs_address", f"Retrieved GCS address: {gcs_address}"
                )
                return gcs_address
            else:
                self._LoggingUtility.log_warning(
                    "get_gcs_address", "GCS address not available in runtime context"
                )
                return None

        except Exception as e:
            self._LoggingUtility.log_error("get_gcs_address", e)
            return None

    # Simplified worker management methods (replacing WorkerManager)
    async def _start_worker_nodes(
        self, worker_configs: List[Dict[str, Any]], head_node_address: str
    ) -> List[Dict[str, Any]]:
        """Start multiple worker nodes with simplified management."""
        worker_results = []

        for i, config in enumerate(worker_configs):
            try:
                node_name = config.get("node_name", f"worker-{i+1}")
                worker_result = await self._start_single_worker(
                    config, head_node_address, node_name
                )
                worker_results.append(worker_result)

                # Small delay between worker starts
                if i < len(worker_configs) - 1:
                    await asyncio.sleep(0.5)

            except Exception as e:
                self._LoggingUtility.log_error(f"start worker node {i+1}", e)
                worker_results.append(
                    {
                        "status": "error",
                        "node_name": config.get("node_name", f"worker-{i+1}"),
                        "message": f"Failed to start worker node: {str(e)}",
                    }
                )

        return worker_results

    async def _start_single_worker(
        self, config: Dict[str, Any], head_node_address: str, node_name: str
    ) -> Dict[str, Any]:
        """Start a single worker node with simplified process management."""
        try:
            # Build worker command
            cmd = self._build_worker_command(config, head_node_address)

            # Start worker process
            process = await self._spawn_worker_process(cmd, node_name)

            if process:
                self._worker_processes.append(process)
                self._worker_configs.append(config)

                return {
                    "status": "started",
                    "node_name": node_name,
                    "message": f"Worker node '{node_name}' started successfully",
                    "process_id": process.pid,
                    "config": config,
                }
            else:
                return {
                    "status": "error",
                    "node_name": node_name,
                    "message": "Failed to spawn worker process",
                }

        except Exception as e:
            self._LoggingUtility.log_error(f"start worker process for {node_name}", e)
            return {
                "status": "error",
                "node_name": node_name,
                "message": f"Failed to start worker process: {str(e)}",
            }

    def _build_worker_command(
        self, config: Dict[str, Any], head_node_address: str
    ) -> List[str]:
        """Build command to start a Ray worker node."""
        cmd = ["ray", "start", "--address", head_node_address]

        # Add resource specifications
        if "num_cpus" in config:
            cmd.extend(["--num-cpus", str(config["num_cpus"])])
        if "num_gpus" in config:
            cmd.extend(["--num-gpus", str(config["num_gpus"])])
        if "object_store_memory" in config:
            # Ensure minimum 75MB
            min_memory_bytes = 75 * 1024 * 1024
            memory_bytes = max(min_memory_bytes, config["object_store_memory"])
            cmd.extend(["--object-store-memory", str(memory_bytes)])
        if "resources" in config and isinstance(config["resources"], dict):
            resources_json = json.dumps(config["resources"])
            cmd.extend(["--resources", resources_json])
        if "node_name" in config:
            cmd.extend(["--node-name", config["node_name"]])

        cmd.extend(["--block", "--disable-usage-stats"])
        return cmd

    async def _spawn_worker_process(
        self, cmd: List[str], node_name: str
    ) -> Optional[subprocess.Popen]:
        """Spawn a worker node process with simplified error handling."""
        try:
            self._LoggingUtility.log_info(
                "worker_start", f"Starting worker '{node_name}': {' '.join(cmd)}"
            )

            # Set up environment
            env = os.environ.copy()
            env["RAY_DISABLE_USAGE_STATS"] = "1"
            env["RAY_ENABLE_WINDOWS_OR_OSX_CLUSTER"] = "1"

            # Start process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
                text=True,
            )

            # Brief startup check
            await asyncio.sleep(0.2)

            if process.poll() is None:
                self._LoggingUtility.log_info(
                    "worker_start", f"Worker '{node_name}' started (PID: {process.pid})"
                )
                return process
            else:
                self._LoggingUtility.log_error(
                    "worker_start",
                    Exception(f"Worker '{node_name}' failed to start"),
                )
                return None

        except Exception as e:
            self._LoggingUtility.log_error("spawn worker process", e)
            return None

    async def _stop_all_workers(self) -> List[Dict[str, Any]]:
        """Stop all worker nodes with simplified cleanup."""
        results = []

        for i, process in enumerate(self._worker_processes):
            try:
                node_name = self._worker_configs[i].get("node_name", f"worker-{i+1}")

                # Terminate process
                process.terminate()

                # Wait for graceful shutdown
                try:
                    loop = asyncio.get_running_loop()
                    await asyncio.wait_for(
                        loop.run_in_executor(None, process.wait), timeout=5
                    )
                    status = "stopped"
                    message = f"Worker '{node_name}' stopped gracefully"
                except asyncio.TimeoutError:
                    # Force kill
                    process.kill()
                    try:
                        await asyncio.wait_for(
                            loop.run_in_executor(None, process.wait), timeout=3
                        )
                        status = "force_stopped"
                        message = f"Worker '{node_name}' force stopped"
                    except asyncio.TimeoutError:
                        status = "force_stopped"
                        message = (
                            f"Worker '{node_name}' force stopped (may still be running)"
                        )

                results.append(
                    {
                        "status": status,
                        "node_name": node_name,
                        "message": message,
                        "process_id": process.pid,
                    }
                )

            except Exception as e:
                results.append(
                    {
                        "status": "error",
                        "node_name": f"worker-{i+1}",
                        "message": f"Error stopping worker: {str(e)}",
                    }
                )

        # Clear worker tracking
        self._worker_processes.clear()
        self._worker_configs.clear()

        return results
