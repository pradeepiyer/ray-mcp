"""Ray cluster lifecycle management."""

import asyncio
import re
import subprocess
from typing import Any, Dict, List, Optional

try:
    from ..logging_utils import LoggingUtility, ResponseFormatter
    from ..worker_manager import WorkerManager
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from logging_utils import LoggingUtility, ResponseFormatter
    from worker_manager import WorkerManager
from .interfaces import ClusterManager, PortManager, StateManager, RayComponent

# Import Ray modules with error handling
try:
    import ray
    RAY_AVAILABLE = True
except ImportError:
    RAY_AVAILABLE = False
    ray = None


class RayClusterManager(RayComponent, ClusterManager):
    """Manages Ray cluster lifecycle operations with clean separation of concerns."""
    
    def __init__(
        self, 
        state_manager: StateManager, 
        port_manager: PortManager,
        worker_manager: Optional[WorkerManager] = None
    ):
        super().__init__(state_manager)
        self._port_manager = port_manager
        self._worker_manager = worker_manager or WorkerManager()
        self._head_node_process: Optional[subprocess.Popen] = None
        self._response_formatter = ResponseFormatter()
    
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
        """Initialize Ray cluster - connect to existing or start new cluster."""
        if not RAY_AVAILABLE:
            return self._response_formatter.format_error_response(
                "init cluster", 
                Exception("Ray is not available. Please install Ray to use this feature.")
            )
        
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
            **kwargs
        )
    
    @ResponseFormatter.handle_exceptions("stop cluster")
    async def stop_cluster(self) -> Dict[str, Any]:
        """Stop the Ray cluster and clean up resources."""
        try:
            cleanup_results = []
            
            # Stop worker nodes first
            if self._worker_manager.worker_processes:
                LoggingUtility.log_info("cluster_cleanup", "Stopping worker nodes...")
                worker_results = await self._worker_manager.stop_all_workers()
                cleanup_results.extend(worker_results)
            
            # Stop head node process if we started it
            if self._head_node_process:
                await self._cleanup_head_node_process()
            
            # Shutdown Ray if initialized
            if ray and ray.is_initialized():
                ray.shutdown()
                LoggingUtility.log_info("cluster_cleanup", "Ray shutdown completed")
            
            # Reset state
            self.state_manager.reset_state()
            
            return self._response_formatter.format_success_response(
                message="Ray cluster stopped successfully",
                cleanup_results=cleanup_results
            )
            
        except Exception as e:
            LoggingUtility.log_error("stop cluster", e)
            # Force reset state even if cleanup failed
            self.state_manager.reset_state()
            return self._response_formatter.format_error_response("stop cluster", e)
    
    @ResponseFormatter.handle_exceptions("inspect cluster")
    async def inspect_cluster(self) -> Dict[str, Any]:
        """Get comprehensive cluster information."""
        self._ensure_initialized()
        
        try:
            cluster_info = {}
            
            # Basic cluster status
            cluster_info["status"] = "active" if ray.is_initialized() else "inactive"
            cluster_info["ray_version"] = ray.__version__ if ray else "unavailable"
            
            # Cluster resources and nodes
            if ray.is_initialized():
                cluster_info.update(await self._get_cluster_resources())
                cluster_info.update(await self._get_node_information())
                cluster_info.update(await self._get_cluster_health())
            
            return self._response_formatter.format_success_response(**cluster_info)
            
        except Exception as e:
            return self._response_formatter.format_error_response("inspect cluster", e)
    
    async def _connect_to_existing_cluster(self, address: str) -> Dict[str, Any]:
        """Connect to an existing Ray cluster."""
        try:
            # Validate address format
            if not self._validate_cluster_address(address):
                return self._response_formatter.format_validation_error(
                    f"Invalid cluster address format: {address}"
                )
            
            # Initialize Ray client connection
            ray.init(address=address, ignore_reinit_error=True)
            
            # Update state
            self.state_manager.update_state(
                initialized=True,
                cluster_address=address,
                gcs_address=address
            )
            
            return self._response_formatter.format_success_response(
                message=f"Successfully connected to Ray cluster at {address}",
                cluster_address=address,
                connection_type="existing"
            )
            
        except Exception as e:
            LoggingUtility.log_error("connect to cluster", e)
            return self._response_formatter.format_error_response("connect to cluster", e)
    
    async def _start_new_cluster(self, **kwargs) -> Dict[str, Any]:
        """Start a new Ray cluster."""
        try:
            # Use Ray's default approach - let Ray handle port allocation
            # This avoids port conflicts and is more reliable
            dashboard_port = kwargs.get('dashboard_port') or await self._port_manager.find_free_port(8265)
            
            # Build head node command (without manual port specification)
            build_kwargs = {k: v for k, v in kwargs.items() 
                          if k not in ['head_node_port', 'dashboard_port']}
            head_cmd = await self._build_head_node_command(
                dashboard_port=dashboard_port,
                **build_kwargs
            )
            
            # Start head node process
            self._head_node_process = await self._start_head_node_process(head_cmd)
            if not self._head_node_process:
                return self._response_formatter.format_error_response(
                    "start cluster", Exception("Failed to start head node process")
                )
            
            # Wait for cluster to be ready and initialize Ray to get actual address
            host = kwargs.get('head_node_host', '127.0.0.1')
            dashboard_url = f"http://{host}:{dashboard_port}"
            
            # Initialize Ray and let it detect the cluster
            ray.init(ignore_reinit_error=True)
            
            # Get the actual cluster address from Ray
            runtime_context = ray.get_runtime_context()
            gcs_address = runtime_context.gcs_address if runtime_context else None
            cluster_address = gcs_address or f"{host}:10001"  # fallback
            
            # Update state
            self.state_manager.update_state(
                initialized=True,
                cluster_address=cluster_address,
                gcs_address=gcs_address,
                dashboard_url=dashboard_url
            )
            
            # Start worker nodes if requested
            worker_results = []
            worker_nodes = kwargs.get('worker_nodes')
            if worker_nodes is not None and len(worker_nodes) > 0:
                worker_results = await self._worker_manager.start_worker_nodes(
                    worker_nodes, cluster_address
                )
            elif worker_nodes is None:
                # Default: start 2 worker nodes
                default_workers = self._get_default_worker_config()
                worker_results = await self._worker_manager.start_worker_nodes(
                    default_workers, cluster_address
                )
            
            return self._response_formatter.format_success_response(
                message="Ray cluster started successfully",
                result_type="started",
                cluster_address=cluster_address,
                dashboard_url=dashboard_url,
                gcs_address=gcs_address,
                dashboard_port=dashboard_port,
                worker_results=worker_results,
                connection_type="new"
            )
            
        except Exception as e:
            # Cleanup on failure
            if self._head_node_process:
                await self._cleanup_head_node_process()
            self.state_manager.reset_state()
            return self._response_formatter.format_error_response("start cluster", e)
    
    async def _build_head_node_command(self, dashboard_port: int, **kwargs) -> List[str]:
        """Build the command to start Ray head node."""
        cmd = [
            "ray", "start", "--head",
            "--dashboard-port", str(dashboard_port),
            "--dashboard-host", "0.0.0.0",
        ]
        
        # Add resource specifications
        if kwargs.get('num_cpus'):
            cmd.extend(["--num-cpus", str(kwargs['num_cpus'])])
        if kwargs.get('num_gpus'):
            cmd.extend(["--num-gpus", str(kwargs['num_gpus'])])
        if kwargs.get('object_store_memory'):
            cmd.extend(["--object-store-memory", str(kwargs['object_store_memory'])])
        
        # Add Ray options
        cmd.extend([
            "--disable-usage-stats",
            "--verbose"
        ])
        
        return cmd
    
    async def _start_head_node_process(self, cmd: List[str]) -> Optional[subprocess.Popen]:
        """Start the head node process."""
        try:
            LoggingUtility.log_info("cluster_start", f"Starting head node: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait briefly and check if process is still running
            await asyncio.sleep(2.0)
            
            if process.poll() is None:
                LoggingUtility.log_info("cluster_start", f"Head node started (PID: {process.pid})")
                return process
            else:
                stdout, stderr = process.communicate()
                LoggingUtility.log_error(
                    "cluster_start", 
                    Exception(f"Head node failed to start. STDOUT: {stdout}, STDERR: {stderr}")
                )
                return None
                
        except Exception as e:
            LoggingUtility.log_error("start head node process", e)
            return None
    
    async def _cleanup_head_node_process(self, timeout: int = 10) -> None:
        """Clean up the head node process."""
        if not self._head_node_process:
            return
        
        try:
            # Terminate gracefully
            self._head_node_process.terminate()
            try:
                self._head_node_process.wait(timeout=timeout)
                LoggingUtility.log_info("cluster_cleanup", "Head node process terminated gracefully")
            except subprocess.TimeoutExpired:
                # Force kill if necessary
                self._head_node_process.kill()
                self._head_node_process.wait()
                LoggingUtility.log_warning("cluster_cleanup", "Head node process force killed")
                
        except Exception as e:
            LoggingUtility.log_error("cleanup head node", e)
        finally:
            self._head_node_process = None
    
    def _validate_cluster_address(self, address: str) -> bool:
        """Validate cluster address format."""
        # Basic validation for host:port format
        pattern = r'^[a-zA-Z0-9.-]+:\d+$'
        return bool(re.match(pattern, address))
    
    def _get_default_worker_config(self) -> List[Dict[str, Any]]:
        """Get default worker node configuration."""
        return [
            {"num_cpus": 1, "node_name": "worker-1"},
            {"num_cpus": 1, "node_name": "worker-2"}
        ]
    
    async def _get_cluster_resources(self) -> Dict[str, Any]:
        """Get cluster resource information."""
        try:
            cluster_resources = ray.cluster_resources()
            available_resources = ray.available_resources()
            
            return {
                "cluster_resources": dict(cluster_resources),
                "available_resources": dict(available_resources),
                "resource_utilization": self._calculate_resource_utilization(
                    cluster_resources, available_resources
                )
            }
        except Exception as e:
            LoggingUtility.log_warning("get cluster resources", str(e))
            return {"cluster_resources": {}, "available_resources": {}}
    
    async def _get_node_information(self) -> Dict[str, Any]:
        """Get information about cluster nodes."""
        try:
            nodes = ray.nodes()
            return {
                "num_nodes": len(nodes),
                "node_info": [
                    {
                        "node_id": node.get("NodeID"),
                        "alive": node.get("Alive", False),
                        "resources": node.get("Resources", {}),
                        "node_name": node.get("NodeName", "unknown")
                    }
                    for node in nodes
                ]
            }
        except Exception as e:
            LoggingUtility.log_warning("get node information", str(e))
            return {"num_nodes": 0, "node_info": []}
    
    async def _get_cluster_health(self) -> Dict[str, Any]:
        """Get cluster health information."""
        try:
            # Basic health checks
            runtime_context = ray.get_runtime_context()
            
            return {
                "health_status": "healthy" if runtime_context else "unhealthy",
                "current_node_id": runtime_context.get_node_id() if runtime_context else None,
                "cluster_metadata": {
                    "ray_initialized": ray.is_initialized(),
                    "ray_version": ray.__version__
                }
            }
        except Exception as e:
            LoggingUtility.log_warning("get cluster health", str(e))
            return {"health_status": "unknown"}
    
    def _calculate_resource_utilization(
        self, cluster_resources: Dict, available_resources: Dict
    ) -> Dict[str, float]:
        """Calculate resource utilization percentages."""
        utilization = {}
        
        for resource, total in cluster_resources.items():
            if isinstance(total, (int, float)) and total > 0:
                available = available_resources.get(resource, 0)
                if isinstance(available, (int, float)):
                    used = total - available
                    utilization[resource] = round((used / total) * 100, 2)
        
        return utilization 