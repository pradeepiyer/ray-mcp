"""Unified Ray MCP manager that composes focused components."""

from typing import Any, Dict, Optional

from .cluster_manager import RayClusterManager
from .job_manager import RayJobManager
from .log_manager import RayLogManager
from .port_manager import RayPortManager
from .state_manager import RayStateManager
from .kubernetes_manager import KubernetesClusterManager
from .kuberay_cluster_manager import KubeRayClusterManagerImpl
from .kuberay_job_manager import KubeRayJobManagerImpl


class RayUnifiedManager:
    """Unified manager that composes focused Ray MCP components.

    This class provides a clean facade over the individual focused components,
    maintaining the same interface as the original monolithic RayManager while
    internally delegating to specialized components.
    """

    def __init__(self):
        # Initialize core components
        self._state_manager = RayStateManager()
        self._port_manager = RayPortManager()

        # Initialize specialized managers with dependencies
        self._cluster_manager = RayClusterManager(
            self._state_manager, self._port_manager
        )
        self._job_manager = RayJobManager(self._state_manager)
        self._log_manager = RayLogManager(self._state_manager)
        self._kubernetes_manager = KubernetesClusterManager(self._state_manager)
        self._kuberay_cluster_manager = KubeRayClusterManagerImpl(self._state_manager)
        self._kuberay_job_manager = KubeRayJobManagerImpl(self._state_manager)

    # Delegate properties to state manager
    @property
    def is_initialized(self) -> bool:
        """Check if Ray is initialized."""
        return self._state_manager.is_initialized()

    @property
    def cluster_address(self) -> Optional[str]:
        """Get cluster address."""
        return self._state_manager.get_state().get("cluster_address")

    @property
    def dashboard_url(self) -> Optional[str]:
        """Get dashboard URL."""
        return self._state_manager.get_state().get("dashboard_url")

    @property
    def job_client(self) -> Optional[Any]:
        """Get job client."""
        return self._state_manager.get_state().get("job_client")

    # Cluster management methods
    async def init_cluster(self, **kwargs) -> Dict[str, Any]:
        """Initialize Ray cluster."""
        return await self._cluster_manager.init_cluster(**kwargs)

    async def stop_cluster(self) -> Dict[str, Any]:
        """Stop Ray cluster."""
        return await self._cluster_manager.stop_cluster()

    async def inspect_ray(self) -> Dict[str, Any]:
        """Inspect Ray cluster."""
        return await self._cluster_manager.inspect_cluster()

    # Job management methods
    async def submit_job(
        self,
        entrypoint: str,
        runtime_env: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Submit a job to the Ray cluster."""
        return await self._job_manager.submit_job(
            entrypoint, runtime_env, job_id, metadata, **kwargs
        )

    async def list_jobs(self) -> Dict[str, Any]:
        """List all jobs in the Ray cluster."""
        return await self._job_manager.list_jobs()

    async def cancel_job(self, job_id: str) -> Dict[str, Any]:
        """Cancel a running job."""
        return await self._job_manager.cancel_job(job_id)

    async def inspect_job(self, job_id: str, mode: str = "status") -> Dict[str, Any]:
        """Inspect job details."""
        return await self._job_manager.inspect_job(job_id, mode)

    # Log management methods
    async def retrieve_logs(
        self,
        identifier: str,
        log_type: str = "job",
        num_lines: int = 100,
        include_errors: bool = False,
        max_size_mb: int = 10,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Retrieve logs from Ray cluster with optional pagination."""
        return await self._log_manager.retrieve_logs(
            identifier,
            log_type,
            num_lines,
            include_errors,
            max_size_mb,
            page,
            page_size,
            **kwargs,
        )

    # Port management methods (for internal use)
    async def find_free_port(self, start_port: int = 10001, max_tries: int = 50) -> int:
        """Find a free port."""
        return await self._port_manager.find_free_port(start_port, max_tries)

    def cleanup_port_lock(self, port: int) -> None:
        """Clean up port lock file."""
        self._port_manager.cleanup_port_lock(port)

    # Component access for advanced usage
    def get_state_manager(self) -> RayStateManager:
        """Get the state manager component."""
        return self._state_manager

    def get_cluster_manager(self) -> RayClusterManager:
        """Get the cluster manager component."""
        return self._cluster_manager

    def get_job_manager(self) -> RayJobManager:
        """Get the job manager component."""
        return self._job_manager

    def get_log_manager(self) -> RayLogManager:
        """Get the log manager component."""
        return self._log_manager

    def get_port_manager(self) -> RayPortManager:
        """Get the port manager component."""
        return self._port_manager

    def get_kubernetes_manager(self) -> KubernetesClusterManager:
        """Get the Kubernetes manager component."""
        return self._kubernetes_manager

    def get_kuberay_cluster_manager(self) -> KubeRayClusterManagerImpl:
        """Get the KubeRay cluster manager component."""
        return self._kuberay_cluster_manager

    def get_kuberay_job_manager(self) -> KubeRayJobManagerImpl:
        """Get the KubeRay job manager component."""
        return self._kuberay_job_manager

    # Kubernetes management methods
    async def connect_kubernetes_cluster(self, config_file: Optional[str] = None, context: Optional[str] = None) -> Dict[str, Any]:
        """Connect to Kubernetes cluster."""
        return await self._kubernetes_manager.connect_cluster(config_file, context)

    async def disconnect_kubernetes_cluster(self) -> Dict[str, Any]:
        """Disconnect from Kubernetes cluster."""
        return await self._kubernetes_manager.disconnect_cluster()

    async def inspect_kubernetes_cluster(self) -> Dict[str, Any]:
        """Inspect Kubernetes cluster."""
        return await self._kubernetes_manager.inspect_cluster()

    async def kubernetes_health_check(self) -> Dict[str, Any]:
        """Perform health check on Kubernetes cluster."""
        return await self._kubernetes_manager.health_check()

    async def list_kubernetes_contexts(self) -> Dict[str, Any]:
        """List available Kubernetes contexts."""
        return await self._kubernetes_manager.list_contexts()

    async def get_kubernetes_namespaces(self) -> Dict[str, Any]:
        """Get list of Kubernetes namespaces."""
        return await self._kubernetes_manager.get_namespaces()

    async def get_kubernetes_nodes(self) -> Dict[str, Any]:
        """Get Kubernetes cluster nodes."""
        return await self._kubernetes_manager.get_nodes()

    async def get_kubernetes_pods(self, namespace: str = "default") -> Dict[str, Any]:
        """Get pods in a Kubernetes namespace."""
        return await self._kubernetes_manager.get_pods(namespace)

    async def validate_kubernetes_config(self) -> Dict[str, Any]:
        """Validate Kubernetes configuration."""
        return await self._kubernetes_manager.validate_config()

    # Kubernetes properties
    @property
    def is_kubernetes_connected(self) -> bool:
        """Check if connected to Kubernetes cluster."""
        return self._state_manager.get_state().get("kubernetes_connected", False)

    @property
    def kubernetes_context(self) -> Optional[str]:
        """Get current Kubernetes context."""
        return self._state_manager.get_state().get("kubernetes_context")

    @property
    def kubernetes_server_version(self) -> Optional[str]:
        """Get Kubernetes server version."""
        return self._state_manager.get_state().get("kubernetes_server_version")

    # KubeRay cluster management methods
    async def create_kuberay_cluster(self, cluster_spec: Dict[str, Any], namespace: str = "default") -> Dict[str, Any]:
        """Create a Ray cluster using KubeRay."""
        return await self._kuberay_cluster_manager.create_ray_cluster(cluster_spec, namespace)

    async def get_kuberay_cluster(self, name: str, namespace: str = "default") -> Dict[str, Any]:
        """Get Ray cluster status."""
        return await self._kuberay_cluster_manager.get_ray_cluster(name, namespace)

    async def list_kuberay_clusters(self, namespace: str = "default") -> Dict[str, Any]:
        """List Ray clusters."""
        return await self._kuberay_cluster_manager.list_ray_clusters(namespace)

    async def update_kuberay_cluster(self, name: str, cluster_spec: Dict[str, Any], namespace: str = "default") -> Dict[str, Any]:
        """Update Ray cluster configuration."""
        return await self._kuberay_cluster_manager.update_ray_cluster(name, cluster_spec, namespace)

    async def delete_kuberay_cluster(self, name: str, namespace: str = "default") -> Dict[str, Any]:
        """Delete Ray cluster."""
        return await self._kuberay_cluster_manager.delete_ray_cluster(name, namespace)

    async def scale_kuberay_cluster(self, name: str, worker_replicas: int, namespace: str = "default") -> Dict[str, Any]:
        """Scale Ray cluster workers."""
        return await self._kuberay_cluster_manager.scale_ray_cluster(name, worker_replicas, namespace)

    # KubeRay job management methods
    async def create_kuberay_job(self, job_spec: Dict[str, Any], namespace: str = "default") -> Dict[str, Any]:
        """Create a Ray job using KubeRay."""
        return await self._kuberay_job_manager.create_ray_job(job_spec, namespace)

    async def get_kuberay_job(self, name: str, namespace: str = "default") -> Dict[str, Any]:
        """Get Ray job status."""
        return await self._kuberay_job_manager.get_ray_job(name, namespace)

    async def list_kuberay_jobs(self, namespace: str = "default") -> Dict[str, Any]:
        """List Ray jobs."""
        return await self._kuberay_job_manager.list_ray_jobs(namespace)

    async def delete_kuberay_job(self, name: str, namespace: str = "default") -> Dict[str, Any]:
        """Delete Ray job."""
        return await self._kuberay_job_manager.delete_ray_job(name, namespace)

    async def get_kuberay_job_logs(self, name: str, namespace: str = "default") -> Dict[str, Any]:
        """Get Ray job logs."""
        return await self._kuberay_job_manager.get_ray_job_logs(name, namespace)

    # KubeRay properties
    @property
    def kuberay_clusters(self) -> Dict[str, Any]:
        """Get current KubeRay clusters."""
        return self._state_manager.get_state().get("kuberay_clusters", {})

    @property
    def kuberay_jobs(self) -> Dict[str, Any]:
        """Get current KubeRay jobs."""
        return self._state_manager.get_state().get("kuberay_jobs", {})
