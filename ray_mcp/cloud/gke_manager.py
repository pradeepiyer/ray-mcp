"""Google Kubernetes Engine (GKE) cluster management for Ray MCP."""

import asyncio
import base64
from contextlib import contextmanager
import json
import os
import tempfile
from typing import TYPE_CHECKING, Any, Optional

from ..config import config
from ..foundation.enums import CloudProvider
from ..foundation.import_utils import (
    GOOGLE_AUTH_AVAILABLE,
    GOOGLE_CLOUD_AVAILABLE,
    GOOGLE_SERVICE_ACCOUNT_AVAILABLE,
    KUBERNETES_AVAILABLE,
    DefaultCredentialsError,
    client,
    config as k8s_config,
    container_v1,
    default,
    google_auth_transport,
    service_account,
)
from ..foundation.logging_utils import error_response, success_response
from ..foundation.resource_manager import ResourceManager
from ..llm_parser import get_parser


class GKEManager(ResourceManager):
    """Pure prompt-driven Google Kubernetes Engine management - no traditional APIs."""

    # GKE-specific constants
    DEFAULT_NODE_POOL_NAME = "default-pool"
    DEFAULT_CLUSTER_VERSION = "latest"
    DEFAULT_MACHINE_TYPE = "e2-medium"
    DEFAULT_DISK_SIZE_GB = 100
    DEFAULT_NUM_NODES = 3

    def __init__(self):
        super().__init__(
            enable_ray=False,
            enable_kubernetes=True,
            enable_cloud=True,
        )

        self._gke_client = None
        self._k8s_client = None  # Add Kubernetes client
        # Initialize missing instance variables
        self._is_authenticated = False
        self._project_id = None
        self._credentials = None
        self._ca_cert_file = None  # Track the CA certificate file for cleanup

    async def execute_request(self, prompt: str) -> dict[str, Any]:
        """Execute GKE operations using natural language prompts.

        Examples:
            - "authenticate with GCP project ml-experiments"
            - "list all GKE clusters in us-central1"
            - "connect to GKE cluster training-cluster in zone us-central1-a"
            - "create GKE cluster ml-cluster with 3 nodes"
            - "get info for cluster production-cluster"
        """
        try:
            action = await get_parser().parse_cloud_action(prompt)
            operation = action["operation"]

            if operation == "authenticate":
                project_id = action.get("project_id")
                return await self._authenticate_from_prompt(project_id)
            elif operation == "list_clusters":
                project_id = action.get("project_id")
                return await self._discover_clusters(project_id)
            elif operation == "connect_cluster":
                cluster_name = action.get("cluster_name")
                location = action.get("zone")  # parse_cloud_action uses "zone"
                project_id = action.get("project_id")
                if not cluster_name or not location:
                    return error_response("cluster name and location required")
                return await self._connect_cluster(cluster_name, location, project_id)
            elif operation == "create_cluster":
                cluster_name = action.get("cluster_name")
                location = action.get("zone")  # parse_cloud_action uses "zone"
                project_id = action.get("project_id")
                cluster_spec = {"name": cluster_name, "location": location}
                return await self._create_cluster(cluster_spec, project_id)
            elif operation == "get_cluster_info":
                cluster_name = action.get("cluster_name")
                location = action.get("zone")  # parse_cloud_action uses "zone"
                project_id = action.get("project_id")
                if not cluster_name or not location:
                    return error_response("cluster name and location required")
                return await self._get_cluster_info(cluster_name, location, project_id)
            elif operation == "check_environment":
                return await self._check_environment()
            else:
                return error_response(f"Unknown operation: {operation}")

        except ValueError as e:
            return error_response(f"Could not parse request: {str(e)}")
        except Exception as e:
            return self._handle_error("execute_request", e)

    # =================================================================
    # INTERNAL IMPLEMENTATION: All methods are now private
    # =================================================================

    @contextmanager
    def _temporary_ca_cert_file(self, ca_cert_data: bytes):
        """Context manager for temporary CA certificate file with guaranteed cleanup."""
        ca_cert_file = None
        try:
            # Create a temporary file for the CA certificate
            ca_cert_file = tempfile.NamedTemporaryFile(
                mode="w+b", delete=False, suffix=".crt"
            )
            ca_cert_file.write(ca_cert_data)
            ca_cert_file.close()

            # Store the file path for cleanup
            self._ca_cert_file = ca_cert_file.name
            yield ca_cert_file.name
        finally:
            # Always clean up the temporary file
            if ca_cert_file and ca_cert_file.name and os.path.exists(ca_cert_file.name):
                try:
                    os.unlink(ca_cert_file.name)
                except OSError:
                    pass  # File might already be cleaned up
            # Reset the instance variable
            self._ca_cert_file = None

    def _cleanup_ca_cert_file(self):
        """Clean up the CA certificate file."""
        if self._ca_cert_file and os.path.exists(self._ca_cert_file):
            try:
                os.unlink(self._ca_cert_file)
                self._ca_cert_file = None
            except OSError:
                pass  # File might already be cleaned up

    async def _authenticate_from_prompt(
        self, project_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Authenticate with GKE from prompt action."""
        service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        return await self._authenticate_gke(service_account_path, project_id)

    async def _authenticate_gke(
        self,
        service_account_path: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Authenticate with GKE using service account."""
        try:
            return await self._authenticate_gke_operation(
                service_account_path, project_id
            )
        except Exception as e:
            return self._handle_error("gke authentication", e)

    async def _authenticate_gke_operation(
        self,
        service_account_path: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> dict[str, Any]:
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
        if not GOOGLE_SERVICE_ACCOUNT_AVAILABLE:
            raise RuntimeError("Google Auth service account module not available")
        self._credentials = service_account.Credentials.from_service_account_info(
            credentials_data,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )

        # Store project ID
        self._project_id = project_id or credentials_data.get("project_id")
        if not self._project_id:
            raise ValueError(
                "Project ID not found in service account credentials and not provided as parameter"
            )

        # Test authentication by initializing clients
        self._ensure_clients()
        self._is_authenticated = True

        # Update state
        # Simple state tracking
        self._is_authenticated = True

        return {
            "provider": "gke",
            "authenticated": True,
            "project_id": self._project_id,
            "service_account_path": service_account_path,
            "service_account_email": credentials_data.get("client_email"),
        }

    # Legacy aliases for protocol compatibility (all now private)
    async def _discover_gke_clusters(
        self, project_id: Optional[str] = None, location: Optional[str] = None
    ) -> dict[str, Any]:
        """Discover GKE clusters in a project."""
        return await self._discover_clusters(project_id)

    async def _connect_gke_cluster(
        self, cluster_name: str, location: str, project_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Connect to a specific GKE cluster."""
        return await self._connect_cluster(cluster_name, location, project_id)

    async def _create_gke_cluster(
        self, cluster_spec: dict[str, Any], project_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Create a GKE cluster."""
        return await self._create_cluster(cluster_spec, project_id)

    async def _get_gke_cluster_info(
        self, cluster_name: str, location: str, project_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Get information about a GKE cluster."""
        return await self._get_cluster_info(cluster_name, location, project_id)

    def _authenticate(self, credentials: dict[str, Any]) -> dict[str, Any]:
        """Authenticate with Google Cloud Platform."""
        try:
            if not GOOGLE_CLOUD_AVAILABLE:
                return error_response(
                    "Google Cloud SDK is not available. Please install google-cloud-sdk: pip install google-cloud-sdk"
                )

            credentials_json = credentials.get("service_account_json")
            if not credentials_json:
                return error_response(
                    "service_account_json is required for GKE authentication"
                )

            # Parse JSON credentials
            if isinstance(credentials_json, str):
                try:
                    credentials_data = json.loads(credentials_json)
                except json.JSONDecodeError:
                    return error_response(
                        "Invalid JSON format for service account credentials"
                    )
            else:
                credentials_data = credentials_json

            # Create credentials object
            if not GOOGLE_SERVICE_ACCOUNT_AVAILABLE:
                raise RuntimeError("Google Auth service account module not available")
            self._credentials = service_account.Credentials.from_service_account_info(
                credentials_data,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )

            # Store project ID
            self._project_id = credentials_data.get("project_id")
            if not self._project_id:
                return error_response(
                    "project_id not found in service account credentials"
                )

            # Test authentication
            self._ensure_clients()
            self._is_authenticated = True

            return success_response(
                authenticated=True,
                project_id=self._project_id,
                service_account_email=credentials_data.get("client_email"),
            )

        except Exception as e:
            self.logger.log_error("gke authentication", e)
            return self._handle_error("gke authentication", e)

    async def _discover_clusters(
        self, project_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Discover GKE clusters."""
        try:
            return await self._discover_clusters_operation(project_id)
        except Exception as e:
            return self._handle_error("gke cluster discovery", e)

    async def _discover_clusters_operation(
        self, project_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Execute GKE cluster discovery operation."""
        self._ensure_gcp_available()

        # Use ManagedComponent validation method instead of manual check
        await self._ensure_gke_authenticated()

        project_id = self._resolve_project_id(project_id)
        if not project_id:
            raise ValueError(
                "Project ID is required for cluster discovery. Please authenticate with GCP first or specify a project ID."
            )

        parent = f"projects/{project_id}/locations/-"
        clusters_response = await asyncio.to_thread(
            self._gke_client.list_clusters, parent=parent
        )

        discovered_clusters = []
        # Handle the case where clusters_response.clusters is None
        clusters = clusters_response.clusters or []
        for cluster in clusters:
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
            if container_v1 is None:
                raise RuntimeError(
                    "Google Cloud SDK is not available. Please install google-cloud-container"
                )
            self._gke_client = container_v1.ClusterManagerClient(
                credentials=self._credentials
            )

    async def _verify_gke_credentials(self) -> None:
        """Verify that GKE credentials are valid by making a simple API call."""
        if not self._gke_client or not self._project_id:
            raise RuntimeError("GKE client not initialized")

        # Make a simple API call to verify credentials
        parent = f"projects/{self._project_id}/locations/-"
        await asyncio.to_thread(self._gke_client.list_clusters, parent=parent)

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

    async def _connect_cluster(
        self, cluster_name: str, location: str, project_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Connect to a GKE cluster and establish Kubernetes connection."""
        if not GOOGLE_CLOUD_AVAILABLE:
            return error_response(
                "Google Cloud SDK is not available. Please install google-cloud-container: pip install google-cloud-container"
            )

        if not KUBERNETES_AVAILABLE:
            return error_response(
                "Kubernetes client library is not available. Please install kubernetes package: pip install kubernetes"
            )

        # Use ManagedComponent validation method instead of manual check
        try:
            await self._ensure_gke_authenticated()
        except RuntimeError as e:
            return self._handle_error("gke cluster connection", e)

        try:
            project_id = self._resolve_project_id(project_id)
            if not project_id:
                return error_response(
                    "Project ID is required for cluster connection. Please authenticate with GCP first or specify a project ID."
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
            # Simple state tracking
            self._last_operation = "connect_cluster"

            return success_response(
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
            return self._handle_error("gke cluster connection", e)

    async def _establish_kubernetes_connection(
        self, cluster, project_id: str, location: str
    ) -> dict[str, Any]:
        """Establish Kubernetes connection using GKE cluster details and Google Cloud credentials."""
        try:
            if not GOOGLE_AUTH_AVAILABLE:
                return error_response("Google auth transport not available")

            # Create Kubernetes client configuration
            configuration = client.Configuration()
            configuration.host = f"https://{cluster.endpoint}"

            # Get fresh access token from Google Cloud credentials
            request = google_auth_transport.Request()
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

                # Use context manager to ensure cleanup of temporary CA certificate file
                with self._temporary_ca_cert_file(ca_cert_data) as ca_cert_file_path:
                    # Set SSL CA certificate path to use the CA certificate file
                    if hasattr(configuration, "ssl_ca_cert"):
                        setattr(configuration, "ssl_ca_cert", ca_cert_file_path)
                    configuration.verify_ssl = True

                    # Test the connection by creating a client and making an API call
                    with client.ApiClient(configuration) as api_client:
                        v1 = client.CoreV1Api(api_client)
                        version_api = client.VersionApi(api_client)

                        # Test connection by getting server version
                        version_info = await asyncio.to_thread(version_api.get_code)

                        # Also test basic functionality by listing namespaces
                        namespaces = await asyncio.to_thread(v1.list_namespace)

                    # Store the configuration for future use
                    self._k8s_client = configuration

                    # Safe access to git_version attribute
                    git_version = getattr(version_info, "git_version", "unknown")
                    return success_response(
                        connected=True,
                        server_version=git_version,
                        namespaces_count=len(namespaces.items) if namespaces else 0,
                    )
            else:
                # For Autopilot clusters or clusters without explicit CA certs
                configuration.verify_ssl = True

                # Test the connection by creating a client and making an API call
                with client.ApiClient(configuration) as api_client:
                    v1 = client.CoreV1Api(api_client)
                    version_api = client.VersionApi(api_client)

                    # Test connection by getting server version
                    version_info = await asyncio.to_thread(version_api.get_code)

                    # Also test basic functionality by listing namespaces
                    namespaces = await asyncio.to_thread(v1.list_namespace)

                # Store the configuration for future use
                self._k8s_client = configuration

                # Safe access to git_version attribute
                git_version = getattr(version_info, "git_version", "unknown")
                return success_response(
                    connected=True,
                    server_version=git_version,
                    namespaces_count=len(namespaces.items) if namespaces else 0,
                )

        except Exception as e:
            return self._handle_error("establish kubernetes connection", e)

    def _get_kubernetes_client(self) -> Optional[Any]:
        """Get the current Kubernetes client configuration."""
        return self._k8s_client

    def _get_connection_status(self) -> dict[str, Any]:
        """Get GKE connection status."""
        return success_response(
            authenticated=self._is_authenticated,
            project_id=self._project_id,
            provider="gke",
        )

    def _disconnect(self) -> dict[str, Any]:
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
            # Simple state tracking
            self._last_operation = "disconnect_cluster"

            return success_response(disconnected=True, provider="gke")

        except Exception as e:
            return self._handle_error("gke disconnect", e)

    async def _create_cluster(
        self, cluster_spec: dict[str, Any], project_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Create a GKE cluster."""
        if not GOOGLE_CLOUD_AVAILABLE:
            return error_response(
                "Google Cloud SDK is not available. Please install google-cloud-sdk: pip install google-cloud-sdk"
            )

        if not self._is_authenticated:
            return error_response(
                "Not authenticated with GKE. Please authenticate first."
            )

        try:
            project_id = self._resolve_project_id(project_id)
            if not project_id:
                return error_response(
                    "Project ID is required for cluster creation. Please authenticate with GCP first or specify a project ID."
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

            return success_response(
                created=True,
                operation_name=operation.name,
                cluster_name=cluster_spec.get("name", "ray-cluster"),
                location=location,
                project_id=project_id,
            )

        except Exception as e:
            return self._handle_error("gke cluster creation", e)

    async def _get_cluster_info(
        self, cluster_name: str, location: str, project_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Get information about a GKE cluster."""
        if not GOOGLE_CLOUD_AVAILABLE:
            return error_response(
                "Google Cloud SDK is not available. Please install google-cloud-sdk: pip install google-cloud-sdk"
            )

        if not self._is_authenticated:
            return error_response(
                "Not authenticated with GKE. Please authenticate first."
            )

        try:
            project_id = self._resolve_project_id(project_id)
            if not project_id:
                return error_response(
                    "Project ID is required for cluster info. Please authenticate with GCP first or specify a project ID."
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

            return success_response(cluster=cluster_info)

        except Exception as e:
            return self._handle_error("gke cluster info", e)

    def _build_cluster_config(
        self, cluster_spec: dict[str, Any], project_id: str
    ) -> dict[str, Any]:
        """Build GKE cluster configuration from specification."""
        # Get default config from simplified config
        default_config = {
            "machine_type": "n1-standard-2",
            "disk_size": 100,
        }

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

    async def _ensure_gke_authenticated(self) -> dict[str, Any]:
        """Ensure GKE authentication is configured and credentials are valid."""
        try:
            if self._is_authenticated and self._credentials and self._gke_client:
                # Verify existing credentials are still valid
                try:
                    # Test credentials with a simple API call
                    await self._verify_gke_credentials()
                    return success_response(
                        message="Already authenticated with GKE",
                        project_id=self._project_id,
                    )
                except Exception:
                    # Credentials are invalid, need to re-authenticate
                    self._is_authenticated = False
                    self._credentials = None
                    self._gke_client = None

            # Try to authenticate
            self._ensure_gcp_available()

            # Get service account path and project ID
            service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            project_id = config.gcp_project_id

            if not service_account_path:
                return error_response(
                    "GOOGLE_APPLICATION_CREDENTIALS not set. Please set this environment variable."
                )

            if not project_id:
                return error_response(
                    "GCP project_id not configured. Set GOOGLE_APPLICATION_CREDENTIALS or configure authentication."
                )

            # Perform actual authentication with credential verification
            auth_result = await self._authenticate_gke_operation(
                service_account_path, project_id
            )

            # Check if authentication was successful
            if auth_result.get("authenticated"):
                return success_response(
                    message="GKE authentication configured and verified",
                    project_id=project_id,
                )
            else:
                return error_response(
                    f"GKE authentication failed: {auth_result.get('error', 'Unknown error')}"
                )

        except Exception as e:
            return self._handle_error("ensure gke authenticated", e)

    def _resolve_project_id(self, project_id: Optional[str] = None) -> Optional[str]:
        """Resolve project ID from multiple sources with fallback."""
        # Try provided project_id first
        if project_id:
            return project_id

        # Try instance project_id
        if self._project_id:
            return self._project_id

        # Try to get from simplified config as fallback
        try:
            return config.gcp_project_id
        except Exception:
            return None

    async def _check_environment(self) -> dict[str, Any]:
        """Check GKE environment and authentication status."""
        try:
            environment_status = {
                "provider": "gke",
                "google_cloud_available": GOOGLE_CLOUD_AVAILABLE,
                "kubernetes_available": KUBERNETES_AVAILABLE,
                "authenticated": self._is_authenticated,
                "project_id": self._project_id,
                "credentials_configured": bool(
                    os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                ),
            }

            # Additional checks
            if GOOGLE_CLOUD_AVAILABLE:
                environment_status["google_cloud_status"] = "available"
            else:
                environment_status["google_cloud_status"] = (
                    "missing - install google-cloud-container"
                )

            if KUBERNETES_AVAILABLE:
                environment_status["kubernetes_status"] = "available"
            else:
                environment_status["kubernetes_status"] = (
                    "missing - install kubernetes package"
                )

            # Check authentication
            if self._is_authenticated:
                environment_status["authentication_status"] = "authenticated"
                if self._project_id:
                    environment_status["active_project"] = self._project_id
            else:
                environment_status["authentication_status"] = "not authenticated"
                environment_status["suggestion"] = (
                    "Run 'authenticate with GCP project YOUR_PROJECT_ID'"
                )

            return success_response(**environment_status)

        except Exception as e:
            return self._handle_error("check environment", e)

    def __del__(self):
        """Cleanup resources when object is destroyed."""
        try:
            self._cleanup_ca_cert_file()
        except Exception:
            pass  # Ignore errors during cleanup
