"""Ray cluster management functionality."""

import asyncio
import inspect
import json
import logging
import os
import socket
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union, cast

# Import Ray modules with error handling
try:
    import ray
    from ray.job_submission import JobSubmissionClient

    RAY_AVAILABLE = True
except ImportError:
    RAY_AVAILABLE = False
    ray = None  # type: ignore
    JobSubmissionClient = None  # type: ignore

from .worker_manager import WorkerManager

logger = logging.getLogger(__name__)


class RayManager:
    """Manages Ray cluster operations."""

    def __init__(self) -> None:
        self.__is_initialized = False
        self._cluster_address: Optional[str] = None
        self._gcs_address: Optional[str] = None  # Store GCS address for worker nodes
        self._job_client: Optional[Any] = (
            None  # Use Any to avoid type issues with conditional imports
        )
        self._worker_manager = WorkerManager()
        self._head_node_process: Optional[Any] = None  # Track head node process

    @property
    def is_initialized(self) -> bool:
        """Check if Ray is initialized."""
        return (
            self.__is_initialized
            and RAY_AVAILABLE
            and ray is not None
            and ray.is_initialized()
        )

    @property
    def _is_initialized(self) -> bool:
        """Get the _is_initialized flag."""
        return self.__is_initialized

    @_is_initialized.setter
    def _is_initialized(self, value: bool) -> None:
        """Set the _is_initialized flag."""
        self.__is_initialized = value

    def _ensure_initialized(self) -> None:
        """Ensure Ray is initialized."""
        if not self.is_initialized:
            raise RuntimeError("Ray is not initialized. Please start Ray first.")

    async def _initialize_job_client_with_retry(
        self, address: str, max_retries: int = 8, delay: float = 3.0
    ):
        """Initialize job client with retry logic to wait for dashboard agent to be ready."""

        if JobSubmissionClient is None:
            logger.error("JobSubmissionClient is not available")
            return None

        for attempt in range(max_retries):
            try:
                job_client = JobSubmissionClient(address)
                # Test the connection by doing a simple operation that requires the agent
                job_client.list_jobs()
                logger.info(
                    f"Job client initialized successfully on attempt {attempt + 1}"
                )
                return job_client
            except Exception as e:
                error_msg = str(e)
                if attempt < max_retries - 1:
                    # Check if it's a timeout or connection error that we should retry
                    if any(
                        keyword in error_msg.lower()
                        for keyword in ["timeout", "connection", "agent", "not found"]
                    ):
                        logger.warning(
                            f"Job client initialization attempt {attempt + 1} failed (retryable): {e}. Retrying in {delay} seconds..."
                        )
                        await asyncio.sleep(delay)
                        # Exponential backoff for later attempts
                        if attempt >= 3:
                            delay *= 1.5
                    else:
                        logger.error(
                            f"Job client initialization failed with non-retryable error: {e}"
                        )
                        return None
                else:
                    logger.error(
                        f"Failed to initialize job client after {max_retries} attempts: {e}"
                    )
                    return None
        return None

    def _filter_cluster_starting_parameters(
        self, kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Filter out parameters that are only valid for starting new clusters.

        When connecting to an existing cluster (address is provided), these parameters
        are ignored as they only apply to cluster creation, not connection.

        Args:
            kwargs: The keyword arguments to filter

        Returns:
            Filtered kwargs with cluster-starting parameters removed
        """
        # Parameters that are only valid for starting new clusters
        cluster_starting_params = {
            "num_cpus",
            "num_gpus",
            "object_store_memory",
            "head_node_port",
            "dashboard_port",
            "head_node_host",
            "worker_nodes",
        }

        filtered_kwargs = {}
        ignored_params = []

        for key, value in kwargs.items():
            if key in cluster_starting_params:
                ignored_params.append(key)
                logger.info(
                    f"Ignoring cluster-starting parameter '{key}' when connecting to existing cluster"
                )
            else:
                filtered_kwargs[key] = value

        if ignored_params:
            logger.info(
                f"Filtered out cluster-starting parameters when connecting to existing cluster: {ignored_params}"
            )

        return filtered_kwargs

    def _sanitize_init_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Remove ``None`` values and any keys not accepted by ``ray.init``."""

        cleaned = {k: v for k, v in kwargs.items() if v is not None}

        try:
            if ray is not None:
                valid_params = set(inspect.signature(ray.init).parameters.keys())
            else:
                raise ValueError
        except Exception:
            # If ray or its signature isn't available, return without extra filtering
            return cleaned

        return {k: v for k, v in cleaned.items() if k in valid_params}

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
        """
        try:
            if not RAY_AVAILABLE or ray is None:
                return {
                    "status": "error",
                    "message": "Ray is not available. Please install Ray.",
                }

            def find_free_port(start_port=10001, max_tries=50):
                port = start_port
                for _ in range(max_tries):
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        try:
                            s.bind(("", port))
                            return port
                        except OSError:
                            port += 1
                raise RuntimeError("No free port found.")

            def parse_dashboard_url(stdout: str) -> Optional[str]:
                import re

                # Updated pattern to handle URLs with or without quotes
                # Match: View the Ray dashboard at http://... or View the Ray dashboard at 'http://...' or View the Ray dashboard at "http://..."
                pattern = r"View the Ray dashboard at ['\"]?(http://[^\s\"']+)['\"]?"
                match = re.search(pattern, stdout)
                return match.group(1) if match else None

            def parse_gcs_address(stdout: str) -> Optional[str]:
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
                self._is_initialized = True
                self._cluster_address = ray_context.address_info["address"]
                dashboard_url = ray_context.dashboard_url

                # Extract GCS address from the provided address for worker nodes
                if address.startswith("ray://"):
                    # Extract IP:PORT from ray://IP:PORT format
                    self._gcs_address = address[6:]  # Remove "ray://" prefix
                else:
                    # Assume it's already in IP:PORT format
                    self._gcs_address = address

                # Initialize job client with retry logic - this must complete before returning success
                job_client_status = "ready"
                if JobSubmissionClient is not None and self._cluster_address:
                    # Use the dashboard URL (HTTP address) for job client
                    job_client_address = ray_context.dashboard_url
                    if job_client_address:
                        self._job_client = await self._initialize_job_client_with_retry(
                            job_client_address
                        )
                        if self._job_client is None:
                            job_client_status = "unavailable"
                    else:
                        logger.warning(
                            "Dashboard URL not available for job client initialization"
                        )
                        job_client_status = "unavailable"

                return {
                    "status": "connected",
                    "message": f"Successfully connected to Ray cluster at {address}",
                    "address": self._cluster_address,
                    "dashboard_url": ray_context.dashboard_url,
                    "node_id": (
                        ray.get_runtime_context().get_node_id()
                        if ray is not None
                        else None
                    ),
                    "session_name": getattr(ray_context, "session_name", "unknown"),
                    "job_client_status": job_client_status,
                }
            else:
                import os
                import subprocess

                # Use specified ports or find free ports
                if head_node_port is None:
                    head_node_port = find_free_port(
                        20000
                    )  # Start from 20000 to avoid conflicts with worker ports
                if dashboard_port is None:
                    dashboard_port = find_free_port(8265)

                # Find a free port for the Ray Client server (start from a different range to avoid conflicts)
                ray_client_port = find_free_port(
                    30000
                )  # Start from 30000 to ensure it's different from head_node_port

                # Use head_node_port as the GCS server port
                gcs_port = head_node_port

                # Build ray start command for head node
                head_cmd = [
                    "ray",
                    "start",
                    "--head",
                    "--port",
                    str(gcs_port),
                    "--ray-client-server-port",
                    str(ray_client_port),
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
                print(f"Starting head node with command: {' '.join(head_cmd)}")
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
                stdout, stderr = await asyncio.get_event_loop().run_in_executor(
                    None, head_process.communicate
                )
                exit_code = head_process.poll()
                if exit_code != 0 or "Ray runtime started" not in stdout:
                    return {
                        "status": "error",
                        "message": f"Failed to start head node (exit code: {exit_code}). stdout: {stdout}, stderr: {stderr}",
                    }
                dashboard_url = parse_dashboard_url(stdout)
                gcs_address = parse_gcs_address(stdout)
                if not gcs_address:
                    return {
                        "status": "error",
                        "message": f"Could not parse GCS address from head node output. stdout: {stdout}, stderr: {stderr}",
                    }
                # Store GCS address for worker nodes
                self._gcs_address = gcs_address
                # Use the Ray Client server port and the head node IP for ray://
                head_ip = gcs_address.split(":")[0]
                ray_address = f"ray://{head_ip}:{ray_client_port}"
                init_kwargs: Dict[str, Any] = {
                    "address": ray_address,
                    "ignore_reinit_error": True,
                }
                init_kwargs.update(self._sanitize_init_kwargs(kwargs))
                try:
                    ray_context = ray.init(**init_kwargs)
                    self._is_initialized = True
                    self._cluster_address = ray_address
                except Exception as e:
                    logger.error(f"Failed to connect to head node: {e}")
                    logger.error(f"Head node stdout: {stdout}")
                    logger.error(f"Head node stderr: {stderr}")
                    return {
                        "status": "error",
                        "message": f"Failed to connect to head node: {str(e)}",
                    }

            # Initialize job client with retry logic - this must complete before returning success
            job_client_status = "ready"
            if JobSubmissionClient is not None and self._cluster_address:
                # Use the dashboard URL (HTTP address) for job client
                job_client_address = ray_context.dashboard_url
                if job_client_address:
                    self._job_client = await self._initialize_job_client_with_retry(
                        job_client_address
                    )
                    if self._job_client is None:
                        job_client_status = "unavailable"
                else:
                    logger.warning(
                        "Dashboard URL not available for job client initialization"
                    )
                    job_client_status = "unavailable"

            # Set default worker nodes if none specified and not connecting to existing cluster
            if worker_nodes is None and address is None:
                worker_nodes = self._get_default_worker_config()
            # If worker_nodes is an empty list, keep it empty (no workers)
            # If worker_nodes is a non-empty list, use the provided workers

            # Start worker nodes if specified
            worker_results = []
            if worker_nodes and address is None:  # Only start workers for new clusters
                worker_results = await self._worker_manager.start_worker_nodes(
                    worker_nodes, self._gcs_address
                )

            # Determine status based on whether we connected or started
            if address:
                status = "connected"
                message = f"Successfully connected to Ray cluster at {address}"
            else:
                status = "started"
                message = "Ray cluster started successfully"

            return {
                "status": status,
                "message": message,
                "cluster_address": self._cluster_address,
                "dashboard_url": dashboard_url,
                "node_id": (
                    ray.get_runtime_context().get_node_id() if ray is not None else None
                ),
                "session_name": getattr(ray_context, "session_name", "unknown"),
                "job_client_status": job_client_status,
                "worker_nodes": worker_results if worker_results else None,
            }

        except Exception as e:
            logger.error(f"Failed to initialize Ray cluster: {e}")
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
                return {"status": "error", "message": "Ray is not available"}

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
                    import subprocess

                    # Use ray stop to properly stop the head node
                    stop_cmd = ["ray", "stop"]
                    stop_process = subprocess.run(
                        stop_cmd, capture_output=True, text=True, timeout=10
                    )
                    if stop_process.returncode == 0:
                        head_stop_result = "stopped"
                    else:
                        head_stop_result = f"error: {stop_process.stderr}"
                except Exception as e:
                    head_stop_result = f"error: {str(e)}"
                finally:
                    self._head_node_process = None

            self.__is_initialized = False
            self._cluster_address = None
            self._gcs_address = None
            self._job_client = None

            return {
                "status": "stopped",
                "message": "Ray cluster stopped successfully",
                "worker_nodes": worker_stop_results,
                "head_node": head_stop_result,
            }

        except Exception as e:
            logger.error(f"Failed to stop Ray cluster: {e}")
            return {
                "status": "error",
                "message": f"Failed to stop Ray cluster: {str(e)}",
            }

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

            return {
                "status": "success",
                "timestamp": time.time(),
                "cluster_overview": {
                    "status": "running",
                    "address": self._cluster_address,
                    "total_nodes": len(nodes),
                    "alive_nodes": len([n for n in nodes if n["Alive"]]),
                    "total_workers": total_workers,
                    "running_workers": running_workers,
                },
                "resources": {
                    "cluster_resources": cluster_resources,
                    "available_resources": available_resources,
                    "resource_usage": resource_usage,
                },
                "nodes": node_info,
                "worker_nodes": worker_status,
                "performance_metrics": {
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
                "health_check": {
                    "overall_status": overall_status,
                    "health_score": round(health_score, 2),
                    "checks": health_checks,
                    "recommendations": health_recommendations,
                    "node_count": len(nodes),
                    "active_jobs": 0,  # Would need job client to get this
                    "active_actors": 0,  # Would need to count actors
                },
                "optimization_analysis": {
                    "cpu_utilization": round(cpu_utilization, 2),
                    "memory_utilization": round(memory_utilization, 2),
                    "node_count": len(nodes),
                    "alive_nodes": alive_nodes,
                },
                "optimization_suggestions": optimization_suggestions,
            }

        except Exception as e:
            logger.error(f"Failed to get cluster info: {e}")
            return {
                "status": "error",
                "message": f"Failed to get cluster info: {str(e)}",
            }

    async def submit_job(
        self,
        entrypoint: str,
        runtime_env: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Submit a job to the Ray cluster."""
        try:
            self._ensure_initialized()

            if not self._job_client:
                # Use Ray's built-in job submission for Ray Client mode
                try:
                    import ray.job_submission

                    # Create a job submission client using the current Ray context
                    job_client = ray.job_submission.JobSubmissionClient()

                    # Prepare submit arguments
                    submit_kwargs: Dict[str, Any] = {
                        "entrypoint": entrypoint,
                    }

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

                    return {
                        "status": "submitted",
                        "job_id": submitted_job_id,
                        "message": f"Job {submitted_job_id} submitted successfully",
                    }
                except Exception as e:
                    logger.error(f"Failed to submit job using Ray built-in client: {e}")
                    return {
                        "status": "error",
                        "message": f"Job submission not available in Ray Client mode: {str(e)}",
                    }

            # Type the submit_kwargs properly to avoid pyright errors
            submit_kwargs: Dict[str, Any] = {
                "entrypoint": entrypoint,
            }

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
            submitted_job_id = self._job_client.submit_job(**submit_kwargs)

            return {
                "status": "submitted",
                "job_id": submitted_job_id,
                "message": f"Job {submitted_job_id} submitted successfully",
            }

        except Exception as e:
            logger.error(f"Failed to submit job: {e}")
            return {"status": "error", "message": f"Failed to submit job: {str(e)}"}

    async def list_jobs(self) -> Dict[str, Any]:
        """List all jobs."""
        try:
            self._ensure_initialized()

            if not self._job_client:
                # Use Ray's built-in job listing for Ray Client mode
                try:
                    import ray.job_submission

                    # Create a job submission client using the current Ray context
                    job_client = ray.job_submission.JobSubmissionClient()
                    jobs = job_client.list_jobs()

                    return {
                        "status": "success",
                        "jobs": [
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
                    }
                except Exception as e:
                    logger.error(f"Failed to list jobs using Ray built-in client: {e}")
                    return {
                        "status": "error",
                        "message": f"Job listing not available in Ray Client mode: {str(e)}",
                    }

            jobs = self._job_client.list_jobs()

            return {
                "status": "success",
                "jobs": [
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
            }

        except Exception as e:
            logger.error(f"Failed to list jobs: {e}")
            return {"status": "error", "message": f"Failed to list jobs: {str(e)}"}

    # Note: get_job_status functionality is now part of inspect_job method

    async def cancel_job(self, job_id: str) -> Dict[str, Any]:
        """Cancel a job."""
        try:
            self._ensure_initialized()

            if not self._job_client:
                # Use Ray's built-in job cancellation for Ray Client mode
                try:
                    import ray.job_submission

                    # Create a job submission client using the current Ray context
                    job_client = ray.job_submission.JobSubmissionClient()
                    success = job_client.stop_job(job_id)

                    if success:
                        return {
                            "status": "cancelled",
                            "job_id": job_id,
                            "message": f"Job {job_id} cancelled successfully",
                        }
                    else:
                        return {
                            "status": "error",
                            "job_id": job_id,
                            "message": f"Failed to cancel job {job_id}",
                        }
                except Exception as e:
                    logger.error(f"Failed to cancel job using Ray built-in client: {e}")
                    return {
                        "status": "error",
                        "message": f"Job cancellation not available in Ray Client mode: {str(e)}",
                    }

            success = self._job_client.stop_job(job_id)

            if success:
                return {
                    "status": "cancelled",
                    "job_id": job_id,
                    "message": f"Job {job_id} cancelled successfully",
                }
            else:
                return {
                    "status": "error",
                    "job_id": job_id,
                    "message": f"Failed to cancel job {job_id}",
                }

        except Exception as e:
            logger.error(f"Failed to cancel job: {e}")
            return {"status": "error", "message": f"Failed to cancel job: {str(e)}"}

    async def retrieve_logs(
        self,
        identifier: str,
        log_type: str = "job",
        num_lines: int = 100,
        include_errors: bool = False,
    ) -> Dict[str, Any]:
        """
        Retrieve logs from Ray cluster for jobs, actors, or nodes.

        Args:
            identifier: Job ID, actor ID/name, or node ID
            log_type: Type of logs to retrieve - 'job', 'actor', or 'node'
            num_lines: Number of log lines to retrieve (0 for all)
            include_errors: Whether to include error analysis for jobs

        Returns:
            Dictionary containing logs and metadata
        """
        try:
            self._ensure_initialized()

            if log_type == "job":
                return await self._retrieve_job_logs(
                    identifier, num_lines, include_errors
                )
            elif log_type == "actor":
                return await self._retrieve_actor_logs(identifier, num_lines)
            elif log_type == "node":
                return await self._retrieve_node_logs(identifier, num_lines)
            else:
                return {
                    "status": "error",
                    "message": f"Unsupported log type: {log_type}",
                    "suggestion": "Supported types: 'job', 'actor', 'node'",
                }

        except Exception as e:
            logger.error(f"Failed to retrieve logs: {e}")
            return {"status": "error", "message": f"Failed to retrieve logs: {str(e)}"}

    async def _retrieve_job_logs(
        self, job_id: str, num_lines: int = 100, include_errors: bool = False
    ) -> Dict[str, Any]:
        """Retrieve logs for a specific job."""
        try:
            if self._job_client:
                # Get job logs using job client
                logs = self._job_client.get_job_logs(job_id)
                if num_lines > 0:
                    logs = "\n".join(logs.split("\n")[-num_lines:])

                response: Dict[str, Any] = {
                    "status": "success",
                    "log_type": "job",
                    "identifier": job_id,
                    "logs": logs,
                }

                if include_errors:
                    response["error_analysis"] = self._analyze_job_logs(logs)

                return response
            else:
                # Use Ray's built-in job log functionality for Ray Client mode
                try:
                    import ray.job_submission

                    # Create a job submission client using the current Ray context
                    job_client = ray.job_submission.JobSubmissionClient()
                    logs = job_client.get_job_logs(job_id)
                    if num_lines > 0:
                        logs = "\n".join(logs.split("\n")[-num_lines:])

                    response: Dict[str, Any] = {
                        "status": "success",
                        "log_type": "job",
                        "identifier": job_id,
                        "logs": logs,
                    }

                    if include_errors:
                        response["error_analysis"] = self._analyze_job_logs(logs)

                    return response
                except Exception as e:
                    logger.error(
                        f"Failed to get job logs using Ray built-in client: {e}"
                    )
                    return {
                        "status": "partial",
                        "message": f"Job log retrieval not available in Ray Client mode: {str(e)}",
                        "suggestion": "Check Ray dashboard for comprehensive log viewing",
                    }

        except Exception as e:
            logger.error(f"Failed to retrieve job logs: {e}")
            return {
                "status": "error",
                "message": f"Failed to retrieve job logs: {str(e)}",
            }

    async def _retrieve_actor_logs(
        self, actor_identifier: str, num_lines: int = 100
    ) -> Dict[str, Any]:
        """Retrieve logs for a specific actor."""
        try:
            # Note: Ray doesn't provide direct actor log access through Python API
            # This is a placeholder for future implementation
            # For now, we can try to get actor information and suggest alternatives

            if not RAY_AVAILABLE or ray is None:
                return {"status": "error", "message": "Ray is not available"}

            # Try to get actor information
            try:
                if len(actor_identifier) == 32 and all(
                    c in "0123456789abcdefABCDEF" for c in actor_identifier
                ):
                    actor_handle = ray.get_actor(actor_identifier)
                else:
                    # Treat as an actor name, search across namespaces
                    actor_handle = ray.get_actor(actor_identifier, namespace="*")

                # Get actor info
                actor_info = {
                    "actor_id": actor_handle._actor_id.hex(),
                    "state": "ALIVE",
                }

                return {
                    "status": "partial",
                    "log_type": "actor",
                    "identifier": actor_identifier,
                    "message": "Actor logs are not directly accessible through Ray Python API",
                    "actor_info": actor_info,
                    "suggestions": [
                        "Check Ray dashboard for actor logs",
                        "Use Ray CLI: ray logs --actor-id <actor_id>",
                        "Monitor actor through dashboard at http://localhost:8265",
                    ],
                }

            except ValueError:
                return {
                    "status": "error",
                    "message": f"Actor {actor_identifier} not found",
                    "suggestion": "Check Ray dashboard for available actors",
                }

        except Exception as e:
            logger.error(f"Failed to retrieve actor logs: {e}")
            return {
                "status": "error",
                "message": f"Failed to retrieve actor logs: {str(e)}",
            }

    async def _retrieve_node_logs(
        self, node_id: str, num_lines: int = 100
    ) -> Dict[str, Any]:
        """Retrieve logs for a specific node."""
        try:
            if not RAY_AVAILABLE or ray is None:
                return {"status": "error", "message": "Ray is not available"}

            # Get node information
            nodes = ray.nodes()
            target_node = None

            for node in nodes:
                if node["NodeID"] == node_id:
                    target_node = node
                    break

            if not target_node:
                return {
                    "status": "error",
                    "message": f"Node {node_id} not found",
                    "suggestion": "Use inspect_ray tool to see available nodes",
                }

            # Note: Ray doesn't provide direct node log access through Python API
            # This is a placeholder for future implementation
            return {
                "status": "partial",
                "log_type": "node",
                "identifier": node_id,
                "message": "Node logs are not directly accessible through Ray Python API",
                "node_info": {
                    "node_id": target_node["NodeID"],
                    "alive": target_node["Alive"],
                    "node_name": target_node.get("NodeName", ""),
                    "node_manager_address": target_node.get("NodeManagerAddress", ""),
                },
                "suggestions": [
                    "Check Ray dashboard for node logs",
                    "Use Ray CLI: ray logs --node-id <node_id>",
                    "Check log files at /tmp/ray/session_*/logs/",
                    "Monitor node through dashboard at http://localhost:8265",
                ],
            }

        except Exception as e:
            logger.error(f"Failed to retrieve node logs: {e}")
            return {
                "status": "error",
                "message": f"Failed to retrieve node logs: {str(e)}",
            }

    def _analyze_job_logs(self, logs: str) -> Dict[str, Any]:
        """Analyze job logs for errors and provide debugging suggestions."""
        if not logs:
            return {"error_count": 0, "errors": [], "suggestions": []}

        logs = str(logs)
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
        """Generate debugging suggestions based on job info and logs."""
        suggestions = []

        job_logs = str(job_logs) if job_logs is not None else ""

        if job_info.status == "FAILED":
            suggestions.append(
                "Job failed. Check error logs for specific error messages."
            )

        if job_logs and "import" in job_logs.lower() and "error" in job_logs.lower():
            suggestions.append(
                "Import error detected. Check if all required packages are installed in the runtime environment."
            )

        if job_logs and "memory" in job_logs.lower() and "error" in job_logs.lower():
            suggestions.append(
                "Memory error detected. Consider increasing object store memory or optimizing data usage."
            )

        if job_logs and "timeout" in job_logs.lower():
            suggestions.append(
                "Timeout detected. Check if the job is taking longer than expected or increase timeout limits."
            )

        if not suggestions:
            suggestions.append(
                "No obvious issues detected. Check the complete logs for more details."
            )

        return suggestions

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

            if not self._job_client:
                # Use Ray's built-in job inspection for Ray Client mode
                try:
                    import ray.job_submission

                    # Create a job submission client using the current Ray context
                    job_client = ray.job_submission.JobSubmissionClient()
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
                    logger.error(
                        f"Failed to inspect job using Ray built-in client: {e}"
                    )
                    return {
                        "status": "error",
                        "message": f"Job inspection not available in Ray Client mode: {str(e)}",
                    }

            # Use job client if available
            job_info = self._job_client.get_job_info(job_id)

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
            }

            # Add logs if requested
            if mode in ["logs", "debug"]:
                try:
                    job_logs = self._job_client.get_job_logs(job_id)
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
            logger.error(f"Failed to inspect job: {e}")
            return {"status": "error", "message": f"Failed to inspect job: {str(e)}"}
