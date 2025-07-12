"""Google Kubernetes Engine (GKE) cluster management for Ray MCP."""

import asyncio
import base64
import json
import os
import tempfile
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ...foundation.base_managers import ResourceManager
from ...foundation.import_utils import get_kubernetes_imports, get_logging_utils
from ...foundation.interfaces import CloudProvider, ManagedComponent
from ...kubernetes.config.kubernetes_config import KubernetesConfig
from ..config.cloud_provider_config import CloudProviderConfig
from ..config.cloud_provider_detector import CloudProviderDetector

if TYPE_CHECKING:
    from ...managers.state_manager import StateManager


class GKEManager(ResourceManager, ManagedComponent):
    """Manages Google Kubernetes Engine clusters and operations."""

    # GKE-specific constants
    DEFAULT_NODE_POOL_NAME = "default-pool"
    DEFAULT_CLUSTER_VERSION = "latest"
    DEFAULT_MACHINE_TYPE = "e2-medium"
    DEFAULT_DISK_SIZE_GB = 100
    DEFAULT_NUM_NODES = 3

    def __init__(
        self,
        state_manager: "StateManager",
        kubernetes_config: Optional[KubernetesConfig] = None,
    ):
        # Initialize both parent classes
        ResourceManager.__init__(
            self,
            state_manager,
            enable_ray=False,
            enable_kubernetes=True,
            enable_cloud=True,
        )
        ManagedComponent.__init__(self, state_manager)

        self._detector = CloudProviderDetector(state_manager)
        self._config_manager = CloudProviderConfig(state_manager)
        self._kubernetes_config = kubernetes_config or KubernetesConfig()
        self._gke_client = None
        self._k8s_client = None  # Add Kubernetes client
        # Initialize missing instance variables
        self._is_authenticated = False
        self._project_id = None
        self._credentials = None
        self._ca_cert_file = None  # Track the CA certificate file for cleanup

    def _cleanup_ca_cert_file(self):
        """Clean up the CA certificate file."""
        if self._ca_cert_file and os.path.exists(self._ca_cert_file):
            try:
                os.unlink(self._ca_cert_file)
                self._ca_cert_file = None
            except OSError:
                pass  # File might already be cleaned up

    async def authenticate_gke(
        self,
        service_account_path: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Authenticate with GKE using service account."""
        return await self._execute_operation(
            "gke authentication",
            self._authenticate_gke_operation,
            service_account_path,
            project_id,
        )

    async def _authenticate_gke_operation(
        self,
        service_account_path: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute GKE authentication operation."""
        self._ensure_gcp_available()

        # Use service account path from parameter or environment
        service_account_path = service_account_path or os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS"
        )
        if not service_account_path:
            raise ValueError(
                "Service account path not provided and GOOGLE_APPLICATION_CREDENTIALS not set"
            )

        if not os.path.exists(service_account_path):
            raise FileNotFoundError(
                f"Service account file not found: {service_account_path}"
            )

        # Load credentials from service account file
        with open(service_account_path, "r") as f:
            credentials_data = json.load(f)

        # Create credentials object
        self._credentials = self._service_account.Credentials.from_service_account_info(
            credentials_data,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )

        # Store project ID
        self._project_id = project_id or credentials_data.get("project_id")
        if not self._project_id:
            raise ValueError(
                "Project ID not found in service account credentials and not provided as parameter"
            )

        # Set environment variable for other Google Cloud libraries
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account_path

        # Test authentication by initializing clients
        self._ensure_clients()
        self._is_authenticated = True

        # Update state
        self._update_state(
            cloud_provider_auth={
                "gke": {
                    "authenticated": True,
                    "auth_type": "service_account",
                    "service_account_path": service_account_path,
                    "project_id": self._project_id,
                    "auth_time": self._get_current_time(),
                }
            }
        )

        return {
            "provider": "gke",
            "authenticated": True,
            "project_id": self._project_id,
            "service_account_path": service_account_path,
            "service_account_email": credentials_data.get("client_email"),
        }

    # Add aliases for protocol compatibility
    async def discover_gke_clusters(
        self, project_id: Optional[str] = None, zone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Discover GKE clusters in a project."""
        return await self.discover_clusters(project_id)

    async def connect_gke_cluster(
        self, cluster_name: str, zone: str, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Connect to a specific GKE cluster."""
        return await self.connect_cluster(cluster_name, zone, project_id)

    async def create_gke_cluster(
        self, cluster_spec: Dict[str, Any], project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a GKE cluster."""
        return await self.create_cluster(cluster_spec, project_id)

    async def get_gke_cluster_info(
        self, cluster_name: str, zone: str, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get information about a GKE cluster."""
        return await self.get_cluster_info(cluster_name, zone, project_id)

    def authenticate(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate with Google Cloud Platform."""
        try:
            if not self._GOOGLE_CLOUD_AVAILABLE:
                return self._ResponseFormatter.format_error_response(
                    "gke authentication",
                    Exception(
                        "Google Cloud SDK is not available. Please install google-cloud-sdk: pip install google-cloud-sdk"
                    ),
                )

            credentials_json = credentials.get("service_account_json")
            if not credentials_json:
                return self._ResponseFormatter.format_error_response(
                    "gke authentication",
                    ValueError(
                        "service_account_json is required for GKE authentication"
                    ),
                )

            # Parse JSON credentials
            if isinstance(credentials_json, str):
                try:
                    credentials_data = json.loads(credentials_json)
                except json.JSONDecodeError:
                    return self._ResponseFormatter.format_error_response(
                        "gke authentication",
                        ValueError(
                            "Invalid JSON format for service account credentials"
                        ),
                    )
            else:
                credentials_data = credentials_json

            # Create credentials object
            self._credentials = (
                self._service_account.Credentials.from_service_account_info(
                    credentials_data,
                    scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
            )

            # Store project ID
            self._project_id = credentials_data.get("project_id")
            if not self._project_id:
                return self._ResponseFormatter.format_error_response(
                    "gke authentication",
                    ValueError("project_id not found in service account credentials"),
                )

            # Test authentication
            self._ensure_clients()
            self._is_authenticated = True

            return self._ResponseFormatter.format_success_response(
                authenticated=True,
                project_id=self._project_id,
                service_account_email=credentials_data.get("client_email"),
            )

        except Exception as e:
            self._log_error("gke authentication", e)
            return self._ResponseFormatter.format_error_response(
                "gke authentication", e
            )

    async def discover_clusters(
        self, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Discover GKE clusters."""
        return await self._execute_operation(
            "gke cluster discovery", self._discover_clusters_operation, project_id
        )

    async def _discover_clusters_operation(
        self, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute GKE cluster discovery operation."""
        self._ensure_gcp_available()

        # Use ManagedComponent validation method instead of manual check
        self._ensure_cloud_authenticated(CloudProvider.GKE)

        project_id = project_id or self._project_id
        if not project_id:
            raise ValueError("Project ID is required for cluster discovery")

        parent = f"projects/{project_id}/locations/-"
        clusters_response = await asyncio.to_thread(
            self._gke_client.list_clusters, parent=parent
        )

        discovered_clusters = []
        for cluster in clusters_response.clusters:
            # Safely determine location type based on location format
            location_type = (
                "zonal"
                if "-" in cluster.location and cluster.location.count("-") == 2
                else "regional"
            )

            cluster_info = {
                "name": getattr(cluster, "name", "unknown"),
                "location": getattr(cluster, "location", "unknown"),
                "status": (
                    getattr(cluster.status, "name", "unknown")
                    if hasattr(cluster, "status")
                    else "unknown"
                ),
                "node_count": getattr(cluster, "current_node_count", 0),
                "version": getattr(cluster, "current_master_version", "unknown"),
                "created_time": self._format_timestamp(
                    getattr(cluster, "create_time", None)
                ),
                "endpoint": getattr(cluster, "endpoint", ""),
                "location_type": location_type,
                "network": getattr(cluster, "network", ""),
                "subnetwork": getattr(cluster, "subnetwork", ""),
                "project_id": project_id,
            }
            discovered_clusters.append(cluster_info)

        return {
            "clusters": discovered_clusters,
            "total_count": len(discovered_clusters),
            "project_id": project_id,
        }

    def _ensure_clients(self) -> None:
        """Ensure GKE clients are initialized."""
        self._ensure_gcp_available()

        if not self._credentials:
            raise RuntimeError("Not authenticated with GKE")

        if self._gke_client is None:
            self._gke_client = self._container_v1.ClusterManagerClient(
                credentials=self._credentials
            )

    def _format_timestamp(self, timestamp) -> str:
        """Format timestamp safely handling both string and datetime objects."""
        if timestamp is None:
            return ""

        try:
            # If it's already a string, return it
            if isinstance(timestamp, str):
                return timestamp
            # If it's a datetime-like object, format it
            elif hasattr(timestamp, "isoformat"):
                return timestamp.isoformat()
            # If it's a protobuf timestamp, convert it
            elif hasattr(timestamp, "ToDatetime"):
                return timestamp.ToDatetime().isoformat()
            else:
                return str(timestamp)
        except Exception:
            return str(timestamp)

    async def connect_cluster(
        self, cluster_name: str, location: str, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Connect to a GKE cluster and establish Kubernetes connection."""
        if not self._GOOGLE_CLOUD_AVAILABLE:
            return self._ResponseFormatter.format_error_response(
                "gke cluster connection",
                Exception(
                    "Google Cloud SDK is not available. Please install google-cloud-container: pip install google-cloud-container"
                ),
            )

        if not self._KUBERNETES_AVAILABLE:
            return self._ResponseFormatter.format_error_response(
                "gke cluster connection",
                Exception(
                    "Kubernetes client library is not available. Please install kubernetes package: pip install kubernetes"
                ),
            )

        # Use ManagedComponent validation method instead of manual check
        try:
            self._ensure_cloud_authenticated(CloudProvider.GKE)
        except RuntimeError as e:
            return self._ResponseFormatter.format_error_response(
                "gke cluster connection", e
            )

        try:
            # Clean up any existing certificate file
            self._cleanup_ca_cert_file()

            project_id = project_id or self._project_id
            if not project_id:
                return self._ResponseFormatter.format_error_response(
                    "gke cluster connection",
                    ValueError("Project ID is required for cluster connection"),
                )

            # Get cluster details from GKE API
            cluster_path = (
                f"projects/{project_id}/locations/{location}/clusters/{cluster_name}"
            )
            cluster = await asyncio.to_thread(
                self._gke_client.get_cluster, name=cluster_path
            )

            # Establish actual Kubernetes connection using API
            k8s_connection_result = await self._establish_kubernetes_connection(
                cluster, project_id, location
            )

            if k8s_connection_result.get("status") != "success":
                return k8s_connection_result

            # Create context name following GKE convention
            context_name = f"gke_{project_id}_{location}_{cluster_name}"

            # Update state to reflect both GKE and Kubernetes connection
            self.state_manager.update_state(
                kubernetes_connected=True,
                kubernetes_context=context_name,
                kubernetes_config_type="gke",
                kubernetes_server_version=k8s_connection_result.get("server_version"),
                cloud_provider_connections={
                    "gke": {
                        "connected": True,
                        "cluster_name": cluster_name,
                        "location": location,
                        "project_id": project_id,
                        "endpoint": cluster.endpoint,
                        "context": context_name,
                    }
                },
            )

            return self._ResponseFormatter.format_success_response(
                connected=True,
                cluster_name=cluster_name,
                location=location,
                project_id=project_id,
                endpoint=cluster.endpoint,
                kubernetes_connected=True,
                context=context_name,
                server_version=k8s_connection_result.get("server_version"),
            )

        except Exception as e:
            return self._ResponseFormatter.format_error_response(
                "gke cluster connection", e
            )

    async def _establish_kubernetes_connection(
        self, cluster, project_id: str, location: str
    ) -> Dict[str, Any]:
        """Establish Kubernetes connection using GKE cluster details and Google Cloud credentials."""
        try:
            if not self._GOOGLE_AUTH_AVAILABLE:
                return self._ResponseFormatter.format_error_response(
                    "kubernetes connection",
                    Exception("Google auth transport not available"),
                )

            # Create Kubernetes client configuration
            configuration = self._client.Configuration()
            configuration.host = f"https://{cluster.endpoint}"

            # Get fresh access token from Google Cloud credentials
            request = self._google_auth_transport.Request()
            await asyncio.to_thread(self._credentials.refresh, request)

            # Set up bearer token authentication
            configuration.api_key_prefix["authorization"] = "Bearer"
            configuration.api_key["authorization"] = self._credentials.token

            # Handle cluster CA certificate
            if (
                hasattr(cluster, "master_auth")
                and cluster.master_auth
                and cluster.master_auth.cluster_ca_certificate
            ):
                # Decode the base64-encoded CA certificate
                ca_cert_data = base64.b64decode(
                    cluster.master_auth.cluster_ca_certificate
                )

                # Create a temporary file for the CA certificate
                ca_cert_file = tempfile.NamedTemporaryFile(
                    mode="w+b", delete=False, suffix=".crt"
                )
                ca_cert_file.write(ca_cert_data)
                ca_cert_file.close()

                # Store the file path for later cleanup
                self._ca_cert_file = ca_cert_file.name

                # Set SSL CA certificate path to use the CA certificate file
                configuration.ssl_ca_cert = self._ca_cert_file
                configuration.verify_ssl = True
            else:
                # For Autopilot clusters or clusters without explicit CA certs
                configuration.verify_ssl = True

            # Test the connection by creating a client and making an API call
            with self._client.ApiClient(configuration) as api_client:
                v1 = self._client.CoreV1Api(api_client)
                version_api = self._client.VersionApi(api_client)

                # Test connection by getting server version
                version_info = await asyncio.to_thread(version_api.get_code)

                # Also test basic functionality by listing namespaces
                namespaces = await asyncio.to_thread(v1.list_namespace)

            # Store the configuration for future use
            self._k8s_client = configuration

            # Don't delete the certificate file yet - it's needed for future operations

            # Safe access to git_version attribute
            git_version = getattr(version_info, "git_version", "unknown")
            return self._ResponseFormatter.format_success_response(
                connected=True,
                server_version=git_version,
                namespaces_count=len(namespaces.items) if namespaces else 0,
            )

        except Exception as e:
            # Clean up temporary file on error
            if hasattr(self, "_ca_cert_file") and self._ca_cert_file:
                try:
                    os.unlink(self._ca_cert_file)
                    self._ca_cert_file = None
                except OSError:
                    pass

            return self._ResponseFormatter.format_error_response(
                "establish kubernetes connection", e
            )

    def get_kubernetes_client(self) -> Optional[Any]:
        """Get the current Kubernetes client configuration."""
        return self._k8s_client

    def get_connection_status(self) -> Dict[str, Any]:
        """Get GKE connection status."""
        return self._ResponseFormatter.format_success_response(
            authenticated=self._is_authenticated,
            project_id=self._project_id,
            provider="gke",
        )

    def disconnect(self) -> Dict[str, Any]:
        """Disconnect from GKE and clean up resources."""
        try:
            # Clean up certificate file
            self._cleanup_ca_cert_file()

            # Reset connection state
            self._k8s_client = None
            self._is_authenticated = False
            self._project_id = None
            self._credentials = None
            self._gke_client = None

            # Update state
            self.state_manager.update_state(
                kubernetes_connected=False,
                kubernetes_context=None,
                kubernetes_config_type=None,
                kubernetes_server_version=None,
                cloud_provider_connections={},
                cloud_provider_auth={},
            )

            return self._ResponseFormatter.format_success_response(
                disconnected=True, provider="gke"
            )

        except Exception as e:
            return self._ResponseFormatter.format_error_response("gke disconnect", e)

    async def create_cluster(
        self, cluster_spec: Dict[str, Any], project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a GKE cluster."""
        if not self._GOOGLE_CLOUD_AVAILABLE:
            return self._ResponseFormatter.format_error_response(
                "gke cluster creation",
                Exception(
                    "Google Cloud SDK is not available. Please install google-cloud-sdk: pip install google-cloud-sdk"
                ),
            )

        if not self._is_authenticated:
            return self._ResponseFormatter.format_error_response(
                "gke cluster creation",
                Exception("Not authenticated with GKE. Please authenticate first."),
            )

        try:
            project_id = project_id or self._project_id
            if not project_id:
                return self._ResponseFormatter.format_error_response(
                    "gke cluster creation",
                    ValueError("Project ID is required for cluster creation"),
                )

            # Build cluster configuration
            cluster_config_dict = self._build_cluster_config(cluster_spec, project_id)

            # Create the cluster
            location = cluster_spec.get("location", "us-central1-a")
            parent = f"projects/{project_id}/locations/{location}"

            # Type cast to satisfy type checker - GKE API accepts dictionary format
            from typing import Any, cast

            cluster_config_typed = cast(Any, cluster_config_dict)

            operation = await asyncio.to_thread(
                self._gke_client.create_cluster,
                parent=parent,
                cluster=cluster_config_typed,
            )

            return self._ResponseFormatter.format_success_response(
                created=True,
                operation_name=operation.name,
                cluster_name=cluster_spec.get("name", "ray-cluster"),
                location=location,
                project_id=project_id,
            )

        except Exception as e:
            return self._ResponseFormatter.format_error_response(
                "gke cluster creation", e
            )

    async def get_cluster_info(
        self, cluster_name: str, location: str, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get information about a GKE cluster."""
        if not self._GOOGLE_CLOUD_AVAILABLE:
            return self._ResponseFormatter.format_error_response(
                "gke cluster info",
                Exception(
                    "Google Cloud SDK is not available. Please install google-cloud-sdk: pip install google-cloud-sdk"
                ),
            )

        if not self._is_authenticated:
            return self._ResponseFormatter.format_error_response(
                "gke cluster info",
                Exception("Not authenticated with GKE. Please authenticate first."),
            )

        try:
            project_id = project_id or self._project_id
            if not project_id:
                return self._ResponseFormatter.format_error_response(
                    "gke cluster info",
                    ValueError("Project ID is required for cluster info"),
                )

            # Get cluster details
            cluster_path = (
                f"projects/{project_id}/locations/{location}/clusters/{cluster_name}"
            )
            cluster = await asyncio.to_thread(
                self._gke_client.get_cluster, name=cluster_path
            )

            # Format detailed cluster information
            cluster_info = {
                "name": getattr(cluster, "name", "unknown"),
                "location": location,
                "status": (
                    getattr(cluster.status, "name", "unknown")
                    if hasattr(cluster, "status")
                    else "unknown"
                ),
                "endpoint": getattr(cluster, "endpoint", ""),
                "kubernetes_version": getattr(
                    cluster, "current_master_version", "unknown"
                ),
                "node_count": getattr(cluster, "current_node_count", 0),
                "create_time": self._format_timestamp(
                    getattr(cluster, "create_time", None)
                ),
                "network": getattr(cluster, "network", ""),
                "subnetwork": getattr(cluster, "subnetwork", ""),
                "description": getattr(cluster, "description", ""),
                "node_pools": [
                    {
                        "name": getattr(pool, "name", "unknown"),
                        "status": (
                            getattr(pool.status, "name", "unknown")
                            if hasattr(pool, "status")
                            else "unknown"
                        ),
                        "node_count": getattr(pool, "initial_node_count", 0),
                        "machine_type": (
                            getattr(pool.config, "machine_type", "unknown")
                            if hasattr(pool, "config")
                            else "unknown"
                        ),
                        "disk_size": (
                            getattr(pool.config, "disk_size_gb", 0)
                            if hasattr(pool, "config")
                            else 0
                        ),
                        "preemptible": (
                            getattr(pool.config, "preemptible", False)
                            if hasattr(pool, "config")
                            else False
                        ),
                        "image_type": (
                            getattr(pool.config, "image_type", "unknown")
                            if hasattr(pool, "config")
                            else "unknown"
                        ),
                    }
                    for pool in (
                        cluster.node_pools if hasattr(cluster, "node_pools") else []
                    )
                ],
            }

            return self._ResponseFormatter.format_success_response(cluster=cluster_info)

        except Exception as e:
            return self._ResponseFormatter.format_error_response("gke cluster info", e)

    def _build_cluster_config(
        self, cluster_spec: Dict[str, Any], project_id: str
    ) -> Dict[str, Any]:
        """Build GKE cluster configuration from specification."""
        # Get default config
        default_config = self._config_manager.get_provider_config(CloudProvider.GKE)

        # Build basic cluster config
        cluster_config = {
            "name": cluster_spec.get("name", "ray-cluster"),
            "description": cluster_spec.get(
                "description", "Ray cluster created by Ray MCP"
            ),
            "initial_node_count": cluster_spec.get("initial_node_count", 3),
            "node_config": {
                "machine_type": cluster_spec.get(
                    "machine_type", default_config.get("machine_type", "n1-standard-2")
                ),
                "disk_size_gb": cluster_spec.get(
                    "disk_size", default_config.get("disk_size", 100)
                ),
                "oauth_scopes": ["https://www.googleapis.com/auth/cloud-platform"],
                "service_account": cluster_spec.get("service_account", "default"),
                "preemptible": cluster_spec.get("preemptible", False),
            },
            "master_auth": {
                "client_certificate_config": {"issue_client_certificate": False}
            },
            "legacy_abac": {"enabled": False},
            "ip_allocation_policy": {"use_ip_aliases": True},
            "workload_identity_config": {"workload_pool": f"{project_id}.svc.id.goog"},
        }

        return cluster_config

    def _get_current_time(self) -> str:
        """Get current time as ISO string."""
        from datetime import datetime

        return datetime.now().isoformat()

    def __del__(self):
        """Cleanup resources when object is destroyed."""
        try:
            self._cleanup_ca_cert_file()
        except Exception:
            pass  # Ignore errors during cleanup
