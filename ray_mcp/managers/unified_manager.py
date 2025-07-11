"""Unified Ray MCP manager that composes focused components."""

from typing import Any, Dict, Optional

from ray_mcp.cloud.providers.cloud_provider_manager import CloudProviderManager
from ray_mcp.kubernetes.managers.kubernetes_manager import KubernetesManager

from ..foundation.interfaces import CloudProvider
from ..foundation.job_type_detector import JobTypeDetector
from ..foundation.log_processor_strategy import LogProcessorStrategy
from ..kubernetes.managers.kuberay_cluster_manager import KubeRayClusterManager
from ..kubernetes.managers.kuberay_job_manager import KubeRayJobManager
from .cluster_manager import ClusterManager
from .job_manager import JobManager
from .log_manager import LogManager
from .port_manager import PortManager
from .state_manager import StateManager


class RayUnifiedManager:
    """Unified manager that composes focused Ray MCP components.

    This class provides a clean facade over the individual focused components,
    maintaining the same interface as the original monolithic RayManager while
    internally delegating to specialized components.
    """

    def __init__(self):
        # Initialize core components
        self._state_manager = StateManager()
        self._port_manager = PortManager()

        # Initialize specialized managers with dependencies
        self._cluster_manager = ClusterManager(self._state_manager, self._port_manager)
        self._job_manager = JobManager(self._state_manager)
        self._log_manager = LogManager(self._state_manager)
        self._kubernetes_manager = KubernetesManager(self._state_manager)
        self._kuberay_cluster_manager = KubeRayClusterManager(self._state_manager)
        self._kuberay_job_manager = KubeRayJobManager(self._state_manager)
        self._cloud_provider_manager = CloudProviderManager(self._state_manager)

    # Delegate properties to state manager
    @property
    def state_manager(self) -> StateManager:
        """Get the state manager."""
        return self._state_manager

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

    async def inspect_ray_cluster(self) -> Dict[str, Any]:
        """Inspect Ray cluster."""
        return await self._cluster_manager.inspect_cluster()

    # Job management methods
    async def submit_ray_job(
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

    async def list_ray_jobs(self) -> Dict[str, Any]:
        """List all jobs in the Ray cluster."""
        return await self._job_manager.list_jobs()

    async def cancel_ray_job(self, job_id: str) -> Dict[str, Any]:
        """Cancel a running job."""
        return await self._job_manager.cancel_job(job_id)

    async def inspect_ray_job(
        self, job_id: str, mode: str = "status"
    ) -> Dict[str, Any]:
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

    async def retrieve_logs_unified(
        self,
        identifier: str,
        log_type: str = "job",
        num_lines: int = 100,
        include_errors: bool = False,
        max_size_mb: int = 10,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        namespace: str = "default",
        **kwargs,
    ) -> Dict[str, Any]:
        """Unified log retrieval that supports both local and KubeRay jobs."""
        system_state = self._state_manager.get_state()

        return await LogProcessorStrategy.process_unified_logs(
            identifier=identifier,
            system_state=system_state,
            log_type=log_type,
            num_lines=num_lines,
            include_errors=include_errors,
            max_size_mb=max_size_mb,
            page=page,
            page_size=page_size,
            namespace=namespace,
            local_log_manager=self._log_manager,
            kuberay_job_manager=self._kuberay_job_manager,
            **kwargs,
        )

    async def _detect_job_type_from_identifier(self, identifier: str) -> str:
        """Detect job type based on identifier patterns and system state."""
        system_state = self._state_manager.get_state()
        job_type = JobTypeDetector.detect_from_identifier(identifier, system_state)

        # Convert "kubernetes" to "kuberay" for backward compatibility
        return "kuberay" if job_type == "kubernetes" else job_type

    # Port management methods (for internal use)
    async def find_free_port(self, start_port: int = 10001, max_tries: int = 50) -> int:
        """Find a free port."""
        return await self._port_manager.find_free_port(start_port, max_tries)

    def cleanup_port_lock(self, port: int) -> None:
        """Clean up port lock file."""
        self._port_manager.cleanup_port_lock(port)

    # Component access for advanced usage
    def get_state_manager(self) -> StateManager:
        """Get the state manager component."""
        return self._state_manager

    def get_cluster_manager(self) -> ClusterManager:
        """Get the cluster manager component."""
        return self._cluster_manager

    def get_job_manager(self) -> JobManager:
        """Get the job manager component."""
        return self._job_manager

    def get_log_manager(self) -> LogManager:
        """Get the log manager component."""
        return self._log_manager

    def get_port_manager(self) -> PortManager:
        """Get the port manager component."""
        return self._port_manager

    def get_kubernetes_manager(self) -> KubernetesManager:
        """Get the Kubernetes manager component."""
        return self._kubernetes_manager

    def get_kuberay_cluster_manager(self) -> KubeRayClusterManager:
        """Get the KubeRay cluster manager component."""
        return self._kuberay_cluster_manager

    def get_kuberay_job_manager(self) -> KubeRayJobManager:
        """Get the KubeRay job manager component."""
        return self._kuberay_job_manager

    def get_cloud_provider_manager(self) -> CloudProviderManager:
        """Get the cloud provider manager component."""
        return self._cloud_provider_manager

    # Kubernetes management methods
    async def connect_kubernetes_cluster(
        self,
        config_file: Optional[str] = None,
        context: Optional[str] = None,
        cluster_name: Optional[str] = None,
        provider: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Connect to Kubernetes cluster - supports both local kubeconfig and cloud provider connections.

        For local connections: Use config_file and/or context parameters
        For cloud provider connections: Use cluster_name, provider, and cloud-specific kwargs (zone, project_id, etc.)
        """
        # If provider is specified, this is a cloud provider connection
        if provider or cluster_name:
            if not cluster_name:
                return {
                    "status": "error",
                    "message": "cluster_name is required for cloud provider connections",
                }

            if provider:
                provider_enum = CloudProvider(provider)
                result = await self._cloud_provider_manager.connect_cloud_cluster(
                    provider_enum, cluster_name, **kwargs
                )

                # If GKE connection was successful, coordinate with KubeRay managers
                if (
                    result.get("status") == "success"
                    and provider_enum == CloudProvider.GKE
                ):
                    await self._coordinate_gke_kubernetes_config()

                return result
            else:
                # If no provider specified, detect and use the current environment
                detection_result = await self.detect_cloud_provider()
                detected_provider = detection_result.get("detected_provider")
                if detected_provider:
                    provider_enum = CloudProvider(detected_provider)
                    result = await self._cloud_provider_manager.connect_cloud_cluster(
                        provider_enum, cluster_name, **kwargs
                    )

                    # If GKE connection was successful, coordinate with KubeRay managers
                    if (
                        result.get("status") == "success"
                        and provider_enum == CloudProvider.GKE
                    ):
                        await self._coordinate_gke_kubernetes_config()

                    return result
                else:
                    return {
                        "status": "error",
                        "message": "No cloud provider detected and none specified",
                    }
        else:
            # This is a local kubeconfig connection
            return await self._kubernetes_manager.connect_cluster(
                config_file=config_file, context=context
            )

    async def disconnect_kubernetes_cluster(self) -> Dict[str, Any]:
        """Disconnect from Kubernetes cluster."""
        return await self._kubernetes_manager.disconnect_cluster()

    async def inspect_kubernetes_cluster(self) -> Dict[str, Any]:
        """Inspect Kubernetes cluster."""
        return await self._kubernetes_manager.inspect_cluster()

    async def kubernetes_health_check(self) -> Dict[str, Any]:
        """Perform health check on Kubernetes cluster."""
        return await self._kubernetes_manager.health_check()

    async def list_kubernetes_clusters(
        self, provider: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        """List Kubernetes clusters - supports both local kubeconfig contexts and cloud provider clusters.

        For cloud provider clusters: Use provider parameter (e.g., 'gke')
        For local contexts: Omit provider or use provider='local'
        """
        if provider and provider != "local":
            provider_enum = CloudProvider(provider)
            return await self._cloud_provider_manager.list_cloud_clusters(
                provider_enum, **kwargs
            )
        elif provider == "local":
            # List local Kubernetes contexts
            return await self._kubernetes_manager.list_contexts()
        else:
            # If no provider specified, detect and use the current environment
            detection_result = await self.detect_cloud_provider()
            detected_provider = detection_result.get("detected_provider")
            if detected_provider:
                provider_enum = CloudProvider(detected_provider)
                return await self._cloud_provider_manager.list_cloud_clusters(
                    provider_enum, **kwargs
                )
            else:
                return {
                    "status": "error",
                    "message": "No cloud provider detected and none specified",
                }

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
    async def create_kuberay_cluster(
        self, cluster_spec: Dict[str, Any], namespace: str = "default"
    ) -> Dict[str, Any]:
        """Create a Ray cluster using KubeRay."""
        # Ensure GKE coordination is in place if we have a GKE connection
        await self._ensure_kuberay_gke_coordination()
        return await self._kuberay_cluster_manager.create_ray_cluster(
            cluster_spec, namespace
        )

    async def get_kuberay_cluster(
        self, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Get Ray cluster status."""
        # Ensure GKE coordination is in place if we have a GKE connection
        await self._ensure_kuberay_gke_coordination()
        return await self._kuberay_cluster_manager.get_ray_cluster(name, namespace)

    async def list_ray_clusters(self, namespace: str = "default") -> Dict[str, Any]:
        """List Ray clusters (both local and KubeRay)."""
        # This method is used by the unified list_ray_clusters tool
        # The tool handler _list_ray_clusters_handler handles local vs KubeRay detection
        await self._ensure_kuberay_gke_coordination()
        return await self._kuberay_cluster_manager.list_ray_clusters(namespace)

    async def update_kuberay_cluster(
        self, name: str, cluster_spec: Dict[str, Any], namespace: str = "default"
    ) -> Dict[str, Any]:
        """Update Ray cluster configuration."""
        return await self._kuberay_cluster_manager.update_ray_cluster(
            name, cluster_spec, namespace
        )

    async def delete_kuberay_cluster(
        self, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Delete Ray cluster."""
        return await self._kuberay_cluster_manager.delete_ray_cluster(name, namespace)

    async def scale_ray_cluster(
        self, name: str, worker_replicas: int, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Scale Ray cluster workers (unified method)."""
        # This method is used by the unified scale_ray_cluster tool
        # The tool handler _scale_ray_cluster_handler handles local vs KubeRay detection
        return await self._kuberay_cluster_manager.scale_ray_cluster(
            name, worker_replicas, namespace
        )

    # KubeRay job management methods
    async def create_kuberay_job(
        self, job_spec: Dict[str, Any], namespace: str = "default"
    ) -> Dict[str, Any]:
        """Create a Ray job using KubeRay."""
        return await self._kuberay_job_manager.create_ray_job(job_spec, namespace)

    async def get_kuberay_job(
        self, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Get Ray job status."""
        return await self._kuberay_job_manager.get_ray_job(name, namespace)

    async def list_kuberay_jobs(self, namespace: str = "default") -> Dict[str, Any]:
        """List Ray jobs."""
        return await self._kuberay_job_manager.list_ray_jobs(namespace)

    async def delete_kuberay_job(
        self, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Delete Ray job."""
        return await self._kuberay_job_manager.delete_ray_job(name, namespace)

    async def get_kuberay_job_logs(
        self, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
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

    # Cloud provider management methods
    async def detect_cloud_provider(self) -> Dict[str, Any]:
        """Detect available cloud providers."""
        return await self._cloud_provider_manager.detect_cloud_provider()

    async def authenticate_cloud_provider(
        self, provider: str, auth_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Authenticate with a cloud provider."""
        provider_enum = CloudProvider(provider)
        return await self._cloud_provider_manager.authenticate_cloud_provider(
            provider_enum, auth_config
        )

    async def _coordinate_gke_kubernetes_config(self) -> None:
        """Coordinate GKE Kubernetes configuration with KubeRay managers."""
        try:
            from ..foundation.logging_utils import LoggingUtility

            LoggingUtility.log_info(
                "coordinate_gke_config",
                "Starting GKE Kubernetes configuration coordination",
            )

            # Get the GKE manager and its Kubernetes configuration
            gke_manager = self._cloud_provider_manager.get_gke_manager()
            k8s_config = gke_manager.get_kubernetes_client()

            LoggingUtility.log_info(
                "coordinate_gke_config",
                f"GKE manager k8s config: {k8s_config is not None}, host: {getattr(k8s_config, 'host', 'N/A') if k8s_config else 'N/A'}",
            )

            if k8s_config:
                # Update KubeRay managers with the GKE Kubernetes configuration
                LoggingUtility.log_info(
                    "coordinate_gke_config",
                    "Setting Kubernetes configuration on KubeRay managers",
                )
                self._kuberay_cluster_manager.set_kubernetes_config(k8s_config)
                self._kuberay_job_manager.set_kubernetes_config(k8s_config)

                # Update state to reflect the coordination
                self._state_manager.update_state(
                    kuberay_gke_coordinated=True, kuberay_kubernetes_config_type="gke"
                )

                LoggingUtility.log_info(
                    "coordinate_gke_config",
                    "Successfully coordinated GKE Kubernetes configuration with KubeRay managers",
                )
            else:
                # Log warning if no configuration is available
                LoggingUtility.log_warning(
                    "coordinate_gke_config",
                    "No Kubernetes configuration available from GKE manager",
                )
        except Exception as e:
            # Log the specific error for debugging
            from ..foundation.logging_utils import LoggingUtility

            LoggingUtility.log_error(
                "coordinate_gke_config",
                Exception(f"Failed to coordinate GKE configuration: {str(e)}"),
            )
            # The KubeRay operations will still work, just without the optimized configuration

    async def _ensure_kuberay_gke_coordination(self) -> None:
        """Ensure KubeRay managers are coordinated with GKE if connection exists."""
        try:
            from ..foundation.logging_utils import LoggingUtility

            state = self._state_manager.get_state()

            # Check if we're already coordinated
            already_coordinated = state.get("kuberay_gke_coordinated", False)
            LoggingUtility.log_info(
                "ensure_kuberay_gke_coordination",
                f"Checking coordination status - already coordinated: {already_coordinated}",
            )

            if already_coordinated:
                return

            # Check if there's an active GKE connection
            gke_connection = state.get("cloud_provider_connections", {}).get("gke", {})
            gke_connected = gke_connection.get("connected", False)
            LoggingUtility.log_info(
                "ensure_kuberay_gke_coordination",
                f"GKE connection status: {gke_connected}, connection details: {gke_connection}",
            )

            if gke_connected:
                # Coordinate with the existing GKE connection
                LoggingUtility.log_info(
                    "ensure_kuberay_gke_coordination",
                    "Found active GKE connection, initiating coordination",
                )
                await self._coordinate_gke_kubernetes_config()
            else:
                LoggingUtility.log_info(
                    "ensure_kuberay_gke_coordination",
                    "No active GKE connection found, skipping coordination",
                )
        except Exception as e:
            # Don't fail KubeRay operations if coordination fails
            from ..foundation.logging_utils import LoggingUtility

            LoggingUtility.log_warning(
                "ensure_kuberay_gke_coordination",
                f"Failed to ensure KubeRay-GKE coordination: {str(e)}",
            )

    async def create_kubernetes_cluster(
        self, cluster_spec: Dict[str, Any], provider: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        """Create a Kubernetes cluster - supports cloud providers only (local cluster creation not supported).

        For cloud providers: Use provider parameter (e.g., 'gke') and cluster_spec
        """
        if not provider:
            # If no provider specified, detect and use the current environment
            detection_result = await self.detect_cloud_provider()
            detected_provider = detection_result.get("detected_provider")
            if detected_provider and detected_provider != "local":
                provider = detected_provider
            else:
                return {
                    "status": "error",
                    "message": "Cloud provider is required for cluster creation. Local cluster creation not supported.",
                }

        if provider == "local":
            return {
                "status": "error",
                "message": "Local cluster creation not supported. Use existing clusters or Docker/minikube.",
            }

        provider_enum = CloudProvider(provider)
        return await self._cloud_provider_manager.create_cloud_cluster(
            provider_enum, cluster_spec, **kwargs
        )

    async def get_kubernetes_cluster_info(
        self, cluster_name: str, provider: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        """Get Kubernetes cluster information - supports both local and cloud provider clusters.

        For cloud provider clusters: Use provider parameter and cluster_name
        For local clusters: Use cluster_name (as context name) and provider='local' or omit provider
        """
        if provider and provider != "local":
            provider_enum = CloudProvider(provider)
            return await self._cloud_provider_manager.get_cloud_cluster_info(
                provider_enum, cluster_name, **kwargs
            )
        elif provider == "local":
            # For local clusters, get info about the current cluster
            return await self._kubernetes_manager.inspect_cluster()
        else:
            # If no provider specified, detect and use the current environment
            detection_result = await self.detect_cloud_provider()
            detected_provider = detection_result.get("detected_provider")
            if detected_provider and detected_provider != "local":
                provider_enum = CloudProvider(detected_provider)
                return await self._cloud_provider_manager.get_cloud_cluster_info(
                    provider_enum, cluster_name, **kwargs
                )
            else:
                # Default to local cluster info
                return await self._kubernetes_manager.inspect_cluster()

    async def get_cloud_provider_status(self, provider: str) -> Dict[str, Any]:
        """Get cloud provider status."""
        provider_enum = CloudProvider(provider)
        return await self._cloud_provider_manager.get_provider_status(provider_enum)

    async def disconnect_cloud_provider(self, provider: str) -> Dict[str, Any]:
        """Disconnect from a cloud provider."""
        provider_enum = CloudProvider(provider)
        return await self._cloud_provider_manager.disconnect_cloud_provider(
            provider_enum
        )

    async def get_cloud_config_template(
        self, provider: str, template_type: str = "basic"
    ) -> Dict[str, Any]:
        """Get cloud configuration template."""
        provider_enum = CloudProvider(provider)
        return self._cloud_provider_manager.get_config_manager().get_cluster_template(
            provider_enum, template_type
        )

    async def check_environment(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """Check environment setup, dependencies, and authentication status."""
        return await self._cloud_provider_manager.check_environment(provider)

    # Cloud provider properties
    @property
    def is_cloud_authenticated(self) -> bool:
        """Check if authenticated with any cloud provider."""
        auth_state = self._state_manager.get_state().get("cloud_provider_auth", {})
        return any(
            provider.get("authenticated", False) for provider in auth_state.values()
        )

    @property
    def cloud_provider_connections(self) -> Dict[str, Any]:
        """Get current cloud provider connections."""
        return self._state_manager.get_state().get("cloud_provider_connections", {})
