"""Google Kubernetes Engine (GKE) management for Ray MCP."""

import asyncio
import json
import os
from typing import Any, Dict, List, Optional

try:
    from ..logging_utils import LoggingUtility, ResponseFormatter
except ImportError:
    # Fallback for direct execution
    import os
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from logging_utils import LoggingUtility, ResponseFormatter

from .cloud_provider_config import CloudProviderConfigManager
from .cloud_provider_detector import CloudProviderDetector
from .interfaces import CloudProvider, CloudProviderComponent, GKEManager, StateManager
from .kubernetes_config import KubernetesConfigManager

# Import Google Cloud SDK modules with error handling
try:
    from google.auth import default
    from google.auth.exceptions import DefaultCredentialsError
    from google.cloud import container_v1

    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GOOGLE_CLOUD_AVAILABLE = False
    container_v1 = None
    default = None
    DefaultCredentialsError = Exception

# Import kubernetes modules
try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException

    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False
    client = None
    config = None
    ApiException = Exception


class GKEClusterManager(CloudProviderComponent, GKEManager):
    """Manages GKE clusters with authentication and discovery capabilities."""

    def __init__(
        self,
        state_manager: StateManager,
        detector: Optional[CloudProviderDetector] = None,
        config_manager: Optional[CloudProviderConfigManager] = None,
        kubernetes_config: Optional[KubernetesConfigManager] = None,
    ):
        super().__init__(state_manager)
        self._detector = detector or CloudProviderDetector(state_manager)
        self._config_manager = config_manager or CloudProviderConfigManager(
            state_manager
        )
        self._kubernetes_config = kubernetes_config or KubernetesConfigManager()
        self._response_formatter = ResponseFormatter()
        self._gke_client = None
        # Initialize missing instance variables
        self._is_authenticated = False
        self._project_id = None
        self._credentials = None

    async def authenticate_gke(
        self,
        service_account_path: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Authenticate with GKE using service account."""
        try:
            if not GOOGLE_CLOUD_AVAILABLE:
                return self._response_formatter.format_error_response(
                    "gke authentication",
                    Exception(
                        "Google Cloud SDK is not available. Please install google-cloud-container: pip install google-cloud-container"
                    ),
                )

            # Use service account path from parameter or environment
            service_account_path = service_account_path or os.getenv(
                "GOOGLE_APPLICATION_CREDENTIALS"
            )
            if not service_account_path:
                return self._response_formatter.format_error_response(
                    "gke authentication",
                    Exception(
                        "Service account path not provided and GOOGLE_APPLICATION_CREDENTIALS not set"
                    ),
                )

            if not os.path.exists(service_account_path):
                return self._response_formatter.format_error_response(
                    "gke authentication",
                    Exception(
                        f"Service account file not found: {service_account_path}"
                    ),
                )

            # Load credentials from service account file
            with open(service_account_path, "r") as f:
                credentials_data = json.load(f)

            # Create credentials object
            from google.oauth2 import service_account

            self._credentials = service_account.Credentials.from_service_account_info(
                credentials_data,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )

            # Store project ID
            self._project_id = project_id or credentials_data.get("project_id")
            if not self._project_id:
                return self._response_formatter.format_error_response(
                    "gke authentication",
                    ValueError(
                        "Project ID not found in service account credentials and not provided as parameter"
                    ),
                )

            # Set environment variable for other Google Cloud libraries
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account_path

            # Test authentication by initializing clients
            self._ensure_clients()
            self._is_authenticated = True

            # Update state
            self.state_manager.update_state(
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

            return self._response_formatter.format_success_response(
                provider="gke",
                authenticated=True,
                project_id=self._project_id,
                service_account_path=service_account_path,
                service_account_email=credentials_data.get("client_email"),
            )

        except Exception as e:
            return self._response_formatter.format_error_response(
                "gke authentication", e
            )

    # Add aliases for protocol compatibility
    async def discover_gke_clusters(
        self, project_id: Optional[str] = None, zone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Discover GKE clusters in a project."""
        return self.discover_clusters(project_id)

    async def connect_gke_cluster(
        self, cluster_name: str, zone: str, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Connect to a specific GKE cluster."""
        return self.connect_cluster(cluster_name, zone, project_id)

    async def create_gke_cluster(
        self, cluster_spec: Dict[str, Any], project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a GKE cluster."""
        return self.create_cluster(cluster_spec, project_id)

    async def get_gke_cluster_info(
        self, cluster_name: str, zone: str, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get information about a GKE cluster."""
        return self.get_cluster_info(cluster_name, zone, project_id)

    @ResponseFormatter.handle_exceptions("gke authentication")
    def authenticate(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate with Google Cloud Platform."""
        if not GOOGLE_CLOUD_AVAILABLE:
            return self._response_formatter.format_error_response(
                "gke authentication",
                Exception(
                    "Google Cloud SDK is not available. Please install google-cloud-sdk: pip install google-cloud-sdk"
                ),
            )

        try:
            credentials_json = credentials.get("service_account_json")
            if not credentials_json:
                return self._response_formatter.format_error_response(
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
                    return self._response_formatter.format_error_response(
                        "gke authentication",
                        ValueError(
                            "Invalid JSON format for service account credentials"
                        ),
                    )
            else:
                credentials_data = credentials_json

            # Create credentials object
            from google.oauth2 import service_account

            self._credentials = service_account.Credentials.from_service_account_info(
                credentials_data,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )

            # Store project ID
            self._project_id = credentials_data.get("project_id")
            if not self._project_id:
                return self._response_formatter.format_error_response(
                    "gke authentication",
                    ValueError("project_id not found in service account credentials"),
                )

            # Test authentication
            self._ensure_clients()
            self._is_authenticated = True

            return self._response_formatter.format_success_response(
                authenticated=True,
                project_id=self._project_id,
                service_account_email=credentials_data.get("client_email"),
            )

        except Exception as e:
            return self._response_formatter.format_error_response(
                "gke authentication", e
            )

    @ResponseFormatter.handle_exceptions("gke cluster discovery")
    def discover_clusters(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Discover GKE clusters."""
        if not GOOGLE_CLOUD_AVAILABLE:
            return self._response_formatter.format_error_response(
                "gke cluster discovery",
                Exception(
                    "Google Cloud SDK is not available. Please install google-cloud-sdk: pip install google-cloud-sdk"
                ),
            )

        if not self._is_authenticated:
            return self._response_formatter.format_error_response(
                "gke cluster discovery",
                Exception("Not authenticated with GKE. Please authenticate first."),
            )

        try:
            project_id = project_id or self._project_id
            if not project_id:
                return self._response_formatter.format_error_response(
                    "gke cluster discovery",
                    ValueError("Project ID is required for cluster discovery"),
                )

            parent = f"projects/{project_id}/locations/-"
            clusters_response = self._gke_client.list_clusters(parent=parent)

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

            return self._response_formatter.format_success_response(
                clusters=discovered_clusters,
                total_count=len(discovered_clusters),
                project_id=project_id,
            )

        except Exception as e:
            return self._response_formatter.format_error_response(
                "gke cluster discovery", e
            )

    def _ensure_clients(self) -> None:
        """Ensure GKE clients are initialized."""
        if not GOOGLE_CLOUD_AVAILABLE:
            raise RuntimeError("Google Cloud SDK is not available")

        if not self._credentials:
            raise RuntimeError("Not authenticated with GKE")

        if self._gke_client is None:
            self._gke_client = container_v1.ClusterManagerClient(
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

    def connect_cluster(
        self, cluster_name: str, location: str, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Connect to a GKE cluster."""
        if not GOOGLE_CLOUD_AVAILABLE:
            return self._response_formatter.format_error_response(
                "gke cluster connection",
                Exception(
                    "Google Cloud SDK is not available. Please install google-cloud-sdk: pip install google-cloud-sdk"
                ),
            )

        if not self._is_authenticated:
            return self._response_formatter.format_error_response(
                "gke cluster connection",
                Exception("Not authenticated with GKE. Please authenticate first."),
            )

        try:
            project_id = project_id or self._project_id
            if not project_id:
                return self._response_formatter.format_error_response(
                    "gke cluster connection",
                    ValueError("Project ID is required for cluster connection"),
                )

            # Get cluster details
            cluster_path = (
                f"projects/{project_id}/locations/{location}/clusters/{cluster_name}"
            )
            cluster = self._gke_client.get_cluster(name=cluster_path)

            # Generate kubeconfig
            kubeconfig = self._generate_kubeconfig(cluster, project_id)

            return self._response_formatter.format_success_response(
                connected=True,
                cluster_name=cluster_name,
                location=location,
                project_id=project_id,
                endpoint=cluster.endpoint,
                kubeconfig=kubeconfig,
            )

        except Exception as e:
            return self._response_formatter.format_error_response(
                "gke cluster connection", e
            )

    def _generate_kubeconfig(self, cluster, project_id: str) -> Dict[str, Any]:
        """Generate kubeconfig for the cluster."""
        # This is a simplified version - real implementation would need
        # proper certificate handling and token generation
        return {
            "apiVersion": "v1",
            "kind": "Config",
            "clusters": [
                {
                    "name": cluster.name,
                    "cluster": {"server": f"https://{cluster.endpoint}"},
                }
            ],
            "contexts": [
                {
                    "name": cluster.name,
                    "context": {
                        "cluster": cluster.name,
                        "user": f"gke_{project_id}_{cluster.location}_{cluster.name}",
                    },
                }
            ],
            "current-context": cluster.name,
        }

    def get_connection_status(self) -> Dict[str, Any]:
        """Get GKE connection status."""
        return self._response_formatter.format_success_response(
            authenticated=self._is_authenticated,
            project_id=self._project_id,
            provider="gke",
        )

    def create_cluster(
        self, cluster_spec: Dict[str, Any], project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a GKE cluster."""
        if not GOOGLE_CLOUD_AVAILABLE:
            return self._response_formatter.format_error_response(
                "gke cluster creation",
                Exception(
                    "Google Cloud SDK is not available. Please install google-cloud-sdk: pip install google-cloud-sdk"
                ),
            )

        if not self._is_authenticated:
            return self._response_formatter.format_error_response(
                "gke cluster creation",
                Exception("Not authenticated with GKE. Please authenticate first."),
            )

        try:
            project_id = project_id or self._project_id
            if not project_id:
                return self._response_formatter.format_error_response(
                    "gke cluster creation",
                    ValueError("Project ID is required for cluster creation"),
                )

            # Build cluster configuration
            cluster_config = self._build_cluster_config(cluster_spec, project_id)

            # Create the cluster
            location = cluster_spec.get("location", "us-central1-a")
            parent = f"projects/{project_id}/locations/{location}"

            operation = self._gke_client.create_cluster(
                parent=parent, cluster=cluster_config
            )

            return self._response_formatter.format_success_response(
                created=True,
                operation_name=operation.name,
                cluster_name=cluster_spec.get("name", "ray-cluster"),
                location=location,
                project_id=project_id,
            )

        except Exception as e:
            return self._response_formatter.format_error_response(
                "gke cluster creation", e
            )

    def get_cluster_info(
        self, cluster_name: str, location: str, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get information about a GKE cluster."""
        if not GOOGLE_CLOUD_AVAILABLE:
            return self._response_formatter.format_error_response(
                "gke cluster info",
                Exception(
                    "Google Cloud SDK is not available. Please install google-cloud-sdk: pip install google-cloud-sdk"
                ),
            )

        if not self._is_authenticated:
            return self._response_formatter.format_error_response(
                "gke cluster info",
                Exception("Not authenticated with GKE. Please authenticate first."),
            )

        try:
            project_id = project_id or self._project_id
            if not project_id:
                return self._response_formatter.format_error_response(
                    "gke cluster info",
                    ValueError("Project ID is required for cluster info"),
                )

            # Get cluster details
            cluster_path = (
                f"projects/{project_id}/locations/{location}/clusters/{cluster_name}"
            )
            cluster = self._gke_client.get_cluster(name=cluster_path)

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

            return self._response_formatter.format_success_response(
                cluster=cluster_info
            )

        except Exception as e:
            return self._response_formatter.format_error_response("gke cluster info", e)

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
