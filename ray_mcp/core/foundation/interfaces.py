"""Interfaces and protocols for Ray MCP components."""

from abc import ABC
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


class CloudProvider(Enum):
    """Supported cloud providers."""

    GKE = "gke"
    LOCAL = "local"


class AuthenticationType(Enum):
    """Authentication types for cloud providers."""

    SERVICE_ACCOUNT = "service_account"
    KUBECONFIG = "kubeconfig"
    IN_CLUSTER = "in_cluster"


@runtime_checkable
class StateManager(Protocol):
    """Protocol for managing Ray cluster state."""

    def get_state(self) -> Dict[str, Any]:
        """Get current cluster state."""
        ...

    def update_state(self, **kwargs) -> None:
        """Update cluster state."""
        ...

    def reset_state(self) -> None:
        """Reset state to initial values."""
        ...

    def is_initialized(self) -> bool:
        """Check if Ray is initialized."""
        ...


@runtime_checkable
class ClusterManager(Protocol):
    """Protocol for Ray cluster lifecycle management."""

    async def init_cluster(self, **kwargs) -> Dict[str, Any]:
        """Initialize Ray cluster."""
        ...

    async def stop_cluster(self) -> Dict[str, Any]:
        """Stop Ray cluster."""
        ...

    async def inspect_cluster(self) -> Dict[str, Any]:
        """Get cluster information."""
        ...


@runtime_checkable
class JobManager(Protocol):
    """Protocol for Ray job management."""

    async def submit_job(self, entrypoint: str, **kwargs) -> Dict[str, Any]:
        """Submit a job to the cluster."""
        ...

    async def list_jobs(self) -> Dict[str, Any]:
        """List all jobs."""
        ...

    async def cancel_job(self, job_id: str) -> Dict[str, Any]:
        """Cancel a job."""
        ...

    async def inspect_job(self, job_id: str, mode: str = "status") -> Dict[str, Any]:
        """Inspect job details."""
        ...


@runtime_checkable
class LogManager(Protocol):
    """Protocol for log retrieval and processing."""

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
        ...


@runtime_checkable
class PortManager(Protocol):
    """Protocol for port management."""

    async def find_free_port(self, start_port: int = 10001, max_tries: int = 50) -> int:
        """Find a free port."""
        ...

    def cleanup_port_lock(self, port: int) -> None:
        """Clean up port lock file."""
        ...


@runtime_checkable
class ProcessManager(Protocol):
    """Protocol for process management."""

    async def spawn_process(self, cmd: List[str], **kwargs) -> Optional[Any]:
        """Spawn a new process."""
        ...

    async def terminate_process(self, process: Any, timeout: int = 5) -> Dict[str, Any]:
        """Terminate a process gracefully."""
        ...


@runtime_checkable
class KubernetesClient(Protocol):
    """Protocol for Kubernetes API client interactions."""

    async def test_connection(self) -> Dict[str, Any]:
        """Test connection to Kubernetes cluster."""
        ...

    async def get_cluster_info(self) -> Dict[str, Any]:
        """Get cluster information."""
        ...

    async def list_namespaces(self) -> Dict[str, Any]:
        """List available namespaces."""
        ...

    async def get_nodes(self) -> Dict[str, Any]:
        """Get cluster nodes information."""
        ...

    async def get_pods(self, namespace: str = "default") -> Dict[str, Any]:
        """Get pods in a namespace."""
        ...

    def get_current_context(self) -> Optional[str]:
        """Get current kubeconfig context."""
        ...


@runtime_checkable
class KubernetesConfig(Protocol):
    """Protocol for Kubernetes configuration management."""

    def load_config(
        self, config_file: Optional[str] = None, context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Load Kubernetes configuration."""
        ...

    def validate_config(self) -> Dict[str, Any]:
        """Validate Kubernetes configuration."""
        ...

    def list_contexts(self) -> Dict[str, Any]:
        """List available contexts."""
        ...

    def get_current_context(self) -> Optional[str]:
        """Get current context."""
        ...


@runtime_checkable
class KubernetesManager(Protocol):
    """Protocol for Kubernetes cluster management."""

    async def connect_cluster(
        self, config_file: Optional[str] = None, context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Connect to Kubernetes cluster."""
        ...

    async def disconnect_cluster(self) -> Dict[str, Any]:
        """Disconnect from Kubernetes cluster."""
        ...

    async def inspect_cluster(self) -> Dict[str, Any]:
        """Inspect Kubernetes cluster."""
        ...

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on Kubernetes cluster."""
        ...


@runtime_checkable
class CRDOperations(Protocol):
    """Protocol for Custom Resource Definition operations."""

    async def create_resource(
        self,
        resource_type: str,
        resource_spec: Dict[str, Any],
        namespace: str = "default",
    ) -> Dict[str, Any]:
        """Create a custom resource."""
        ...

    async def get_resource(
        self, resource_type: str, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Get a custom resource by name."""
        ...

    async def list_resources(
        self, resource_type: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """List custom resources."""
        ...

    async def update_resource(
        self,
        resource_type: str,
        name: str,
        resource_spec: Dict[str, Any],
        namespace: str = "default",
    ) -> Dict[str, Any]:
        """Update a custom resource."""
        ...

    async def delete_resource(
        self, resource_type: str, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Delete a custom resource."""
        ...

    async def watch_resource(
        self, resource_type: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Watch custom resource changes."""
        ...


@runtime_checkable
class RayClusterCRD(Protocol):
    """Protocol for RayCluster Custom Resource Definition."""

    def create_spec(
        self,
        head_node_spec: Dict[str, Any],
        worker_node_specs: List[Dict[str, Any]],
        **kwargs,
    ) -> Dict[str, Any]:
        """Create RayCluster specification."""
        ...

    def validate_spec(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Validate RayCluster specification."""
        ...

    def to_yaml(self, spec: Dict[str, Any]) -> str:
        """Convert specification to YAML."""
        ...

    def to_json(self, spec: Dict[str, Any]) -> str:
        """Convert specification to JSON."""
        ...


@runtime_checkable
class RayJobCRD(Protocol):
    """Protocol for RayJob Custom Resource Definition."""

    def create_spec(
        self, entrypoint: str, runtime_env: Optional[Dict[str, Any]] = None, **kwargs
    ) -> Dict[str, Any]:
        """Create RayJob specification."""
        ...

    def validate_spec(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Validate RayJob specification."""
        ...

    def to_yaml(self, spec: Dict[str, Any]) -> str:
        """Convert specification to YAML."""
        ...

    def to_json(self, spec: Dict[str, Any]) -> str:
        """Convert specification to JSON."""
        ...


@runtime_checkable
class KubeRayClusterManager(Protocol):
    """Protocol for KubeRay cluster management."""

    async def create_ray_cluster(
        self, cluster_spec: Dict[str, Any], namespace: str = "default"
    ) -> Dict[str, Any]:
        """Create a Ray cluster using KubeRay."""
        ...

    async def get_ray_cluster(
        self, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Get Ray cluster status."""
        ...

    async def list_ray_clusters(self, namespace: str = "default") -> Dict[str, Any]:
        """List Ray clusters."""
        ...

    async def update_ray_cluster(
        self, name: str, cluster_spec: Dict[str, Any], namespace: str = "default"
    ) -> Dict[str, Any]:
        """Update Ray cluster configuration."""
        ...

    async def delete_ray_cluster(
        self, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Delete Ray cluster."""
        ...

    async def scale_ray_cluster(
        self, name: str, worker_replicas: int, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Scale Ray cluster workers."""
        ...


@runtime_checkable
class KubeRayJobManager(Protocol):
    """Protocol for KubeRay job management."""

    async def create_ray_job(
        self, job_spec: Dict[str, Any], namespace: str = "default"
    ) -> Dict[str, Any]:
        """Create a Ray job using KubeRay."""
        ...

    async def get_ray_job(
        self, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Get Ray job status."""
        ...

    async def list_ray_jobs(self, namespace: str = "default") -> Dict[str, Any]:
        """List Ray jobs."""
        ...

    async def delete_ray_job(
        self, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Delete Ray job."""
        ...

    async def get_ray_job_logs(
        self, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Get Ray job logs."""
        ...


@runtime_checkable
class CloudProviderAuth(Protocol):
    """Protocol for cloud provider authentication."""

    def detect_provider(self) -> Optional[CloudProvider]:
        """Detect the current cloud provider."""
        ...

    def get_auth_type(self) -> Optional[AuthenticationType]:
        """Get the authentication type available."""
        ...

    async def authenticate(
        self, provider: CloudProvider, auth_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Authenticate with cloud provider."""
        ...

    async def validate_authentication(self, provider: CloudProvider) -> Dict[str, Any]:
        """Validate authentication with cloud provider."""
        ...


@runtime_checkable
class CloudProviderConfig(Protocol):
    """Protocol for cloud provider configuration management."""

    def get_provider_config(self, provider: CloudProvider) -> Dict[str, Any]:
        """Get configuration for a specific cloud provider."""
        ...

    def load_provider_config(
        self, provider: CloudProvider, config_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """Load configuration for a specific cloud provider."""
        ...

    def validate_provider_config(
        self, provider: CloudProvider, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate configuration for a specific cloud provider."""
        ...

    def get_cluster_template(
        self, provider: CloudProvider, cluster_type: str = "basic"
    ) -> Dict[str, Any]:
        """Get cluster template for a specific cloud provider."""
        ...


@runtime_checkable
class GKEManager(Protocol):
    """Protocol for Google Kubernetes Engine management."""

    async def authenticate_gke(
        self,
        service_account_path: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Authenticate with GKE using service account."""
        ...

    async def discover_gke_clusters(
        self, project_id: Optional[str] = None, zone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Discover GKE clusters in a project."""
        ...

    async def connect_gke_cluster(
        self, cluster_name: str, zone: str, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Connect to a specific GKE cluster."""
        ...

    async def create_gke_cluster(
        self, cluster_spec: Dict[str, Any], project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a GKE cluster."""
        ...

    async def get_gke_cluster_info(
        self, cluster_name: str, zone: str, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get information about a GKE cluster."""
        ...


@runtime_checkable
class CloudProviderManager(Protocol):
    """Protocol for unified cloud provider management."""

    async def detect_cloud_provider(self) -> Dict[str, Any]:
        """Detect available cloud providers."""
        ...

    async def authenticate_cloud_provider(
        self, provider: CloudProvider, auth_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Authenticate with a cloud provider."""
        ...

    async def list_cloud_clusters(
        self, provider: CloudProvider, **kwargs
    ) -> Dict[str, Any]:
        """List clusters for a cloud provider."""
        ...

    async def connect_cloud_cluster(
        self, provider: CloudProvider, cluster_name: str, **kwargs
    ) -> Dict[str, Any]:
        """Connect to a cloud cluster."""
        ...

    async def create_cloud_cluster(
        self, provider: CloudProvider, cluster_spec: Dict[str, Any], **kwargs
    ) -> Dict[str, Any]:
        """Create a cloud cluster."""
        ...

    async def get_cloud_cluster_info(
        self, provider: CloudProvider, cluster_name: str, **kwargs
    ) -> Dict[str, Any]:
        """Get cloud cluster information."""
        ...


class RayComponent(ABC):
    """Base class for Ray MCP components."""

    def __init__(self, state_manager: StateManager):
        self._state_manager = state_manager

    @property
    def state_manager(self) -> StateManager:
        """Get the state manager."""
        return self._state_manager

    def _ensure_initialized(self) -> None:
        """Ensure Ray is initialized."""
        if not self._state_manager.is_initialized():
            raise RuntimeError("Ray is not initialized. Please start Ray first.")


class KubernetesComponent(ABC):
    """Base class for Kubernetes MCP components."""

    def __init__(self, state_manager: StateManager):
        self._state_manager = state_manager

    @property
    def state_manager(self) -> StateManager:
        """Get the state manager."""
        return self._state_manager

    def _ensure_connected(self) -> None:
        """Ensure Kubernetes is connected."""
        state = self._state_manager.get_state()
        if not state.get("kubernetes_connected", False):
            raise RuntimeError(
                "Kubernetes is not connected. Please connect to a cluster first."
            )


class KubeRayComponent(ABC):
    """Base class for KubeRay MCP components."""

    def __init__(self, state_manager: StateManager):
        self._state_manager = state_manager

    @property
    def state_manager(self) -> StateManager:
        """Get the state manager."""
        return self._state_manager

    def _ensure_kuberay_ready(self) -> None:
        """Ensure Kubernetes is connected and KubeRay is available."""
        state = self._state_manager.get_state()
        if not state.get("kubernetes_connected", False):
            raise RuntimeError(
                "Kubernetes is not connected. Please connect to a cluster first."
            )

        # Could add additional checks for KubeRay CRDs being installed
        # This would be expanded in a real implementation


class CloudProviderComponent(ABC):
    """Base class for cloud provider MCP components."""

    def __init__(self, state_manager: StateManager):
        self._state_manager = state_manager

    @property
    def state_manager(self) -> StateManager:
        """Get the state manager."""
        return self._state_manager

    def _ensure_cloud_authenticated(self, provider: CloudProvider) -> None:
        """Ensure cloud provider is authenticated."""
        state = self._state_manager.get_state()
        cloud_auth = state.get("cloud_provider_auth", {})
        if not cloud_auth.get(provider.value, {}).get("authenticated", False):
            raise RuntimeError(
                f"Not authenticated with {provider.value}. Please authenticate first."
            )

    def _ensure_cloud_connected(self, provider: CloudProvider) -> None:
        """Ensure cloud provider cluster is connected."""
        state = self._state_manager.get_state()
        cloud_connections = state.get("cloud_provider_connections", {})
        if not cloud_connections.get(provider.value, {}).get("connected", False):
            raise RuntimeError(
                f"Not connected to {provider.value} cluster. Please connect first."
            )
