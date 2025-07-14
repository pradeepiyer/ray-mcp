"""Pure prompt-driven cloud provider management for Ray MCP."""

import asyncio
from typing import Any, Dict, Optional

from ..config import get_config_manager_sync
from ..foundation.base_managers import ResourceManager
from ..foundation.interfaces import CloudProvider
from ..parsers import ActionParser
from .gke_manager import GKEManager


class CloudProviderManager(ResourceManager):
    """Pure prompt-driven cloud provider management - no traditional APIs."""

    def __init__(self):
        super().__init__(
            enable_ray=False,
            enable_kubernetes=True,
            enable_cloud=True,
        )

        self._config_manager = get_config_manager_sync()
        self._gke_manager = GKEManager()

    async def execute_request(self, prompt: str) -> Dict[str, Any]:
        """Execute cloud operations using natural language prompts.

        Examples:
            - "authenticate with GCP"
            - "connect to GKE cluster named my-cluster"
            - "list kubernetes clusters"
            - "check environment status"
        """
        try:
            action = ActionParser.parse_cloud_action(prompt)
            operation = action["operation"]

            if operation == "authenticate":
                return await self._authenticate_from_prompt(action)
            elif operation == "connect_cluster":
                return await self._connect_cluster_from_prompt(action)
            elif operation == "list_clusters":
                return await self._list_cloud_clusters(CloudProvider.GKE)
            elif operation == "create_cluster":
                return await self._create_cluster_from_prompt(action)
            elif operation == "check_environment":
                return await self._detect_cloud_provider()
            else:
                return {"status": "error", "message": f"Unknown operation: {operation}"}

        except ValueError as e:
            return {"status": "error", "message": f"Could not parse request: {str(e)}"}
        except Exception as e:
            return self._ResponseFormatter.format_error_response("execute_request", e)

    # =================================================================
    # INTERNAL IMPLEMENTATION: All methods are now private
    # =================================================================

    async def _authenticate_from_prompt(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Convert parsed prompt action to cloud authentication."""
        provider = action.get("provider", "gcp")
        project = action.get("project_id")

        if provider == "gcp":
            auth_config = {}
            if project:
                auth_config["project_id"] = project
            return await self._authenticate_cloud_provider(
                CloudProvider.GKE, auth_config=auth_config
            )
        else:
            return {"status": "error", "message": f"Unsupported provider: {provider}"}

    async def _connect_cluster_from_prompt(
        self, action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert parsed prompt action to cluster connection."""
        cluster_name = action.get("cluster_name")
        provider = action.get("provider", "gke")

        if not cluster_name:
            return {
                "status": "error",
                "message": "cluster_name required for connection",
            }

        return await self._connect_cloud_cluster(
            CloudProvider.GKE, cluster_name=cluster_name
        )

    async def _create_cluster_from_prompt(
        self, action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert parsed prompt action to cluster creation."""
        cluster_name = action.get("cluster_name")
        provider = action.get("provider", "gke")
        zone = action.get("zone", "us-central1-a")

        if not cluster_name:
            return {"status": "error", "message": "cluster_name required for creation"}

        cluster_spec = {"name": cluster_name, "zone": zone}

        return await self._create_cloud_cluster(
            CloudProvider.GKE, cluster_spec=cluster_spec
        )

    async def _detect_cloud_provider(self) -> Dict[str, Any]:
        """Detect available cloud providers and authentication methods."""
        try:
            # Use unified config manager for environment detection
            env_detection = self._config_manager.detect_environment()

            # Check which providers are available
            providers_status = {}

            # Check GKE availability
            if env_detection["gke_available"]:
                providers_status["gke"] = {
                    "available": True,
                    "auth_type": "service_account",
                    "description": "Google Kubernetes Engine",
                }
            else:
                providers_status["gke"] = {
                    "available": False,
                    "reason": "Google Cloud SDK not available or not authenticated",
                }

            # Local Kubernetes
            if env_detection["kubernetes_available"]:
                providers_status["local"] = {
                    "available": True,
                    "auth_type": "kubeconfig",
                    "description": "Local Kubernetes cluster via kubeconfig",
                }
            else:
                providers_status["local"] = {
                    "available": False,
                    "reason": "Kubernetes client not available or not configured",
                }

            return self._ResponseFormatter.format_success_response(
                message="Cloud provider detection completed successfully",
                detected_provider=env_detection.get("default_provider"),
                providers=providers_status,
                environment=env_detection,
                supported_providers=[p.value for p in CloudProvider],
            )

        except Exception as e:
            return self._ResponseFormatter.format_error_response(
                "detect cloud provider", e
            )

    async def _authenticate_cloud_provider(
        self, provider: CloudProvider, auth_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Authenticate with a cloud provider."""
        try:
            # Validate provider
            if provider not in CloudProvider:
                return self._ResponseFormatter.format_error_response(
                    "authenticate cloud provider",
                    Exception(f"Unsupported provider: {provider}"),
                )

            # Route to appropriate manager
            if provider == CloudProvider.GKE:
                return await self._authenticate_gke(auth_config or {})
            elif provider == CloudProvider.LOCAL:
                return await self._authenticate_local(auth_config or {})
            else:
                return self._ResponseFormatter.format_error_response(
                    "authenticate cloud provider",
                    Exception(f"Authentication not implemented for {provider.value}"),
                )

        except Exception as e:
            return self._ResponseFormatter.format_error_response(
                "authenticate cloud provider", e
            )

    async def _list_cloud_clusters(
        self, provider: CloudProvider, **kwargs
    ) -> Dict[str, Any]:
        """List clusters for a cloud provider."""
        try:
            # Route to appropriate manager (they handle their own authentication)
            if provider == CloudProvider.GKE:
                # Use ManagedComponent validation method instead of ResourceManager's
                await self._ensure_gke_authenticated()
                prompt = f"list all GKE clusters"
                if kwargs.get("project_id"):
                    prompt += f" in project {kwargs.get('project_id')}"
                if kwargs.get("zone"):
                    prompt += f" in location {kwargs.get('zone')}"
                return await self._gke_manager.execute_request(prompt)
            elif provider == CloudProvider.LOCAL:
                return await self._list_local_contexts()
            else:
                return self._ResponseFormatter.format_error_response(
                    "list cloud clusters",
                    Exception(f"Cluster listing not implemented for {provider.value}"),
                )

        except Exception as e:
            return self._ResponseFormatter.format_error_response(
                "list cloud clusters", e
            )

    async def _connect_cloud_cluster(
        self, provider: CloudProvider, cluster_name: str, **kwargs
    ) -> Dict[str, Any]:
        """Connect to a cloud cluster."""
        try:
            # Route to appropriate manager (they handle their own authentication)
            if provider == CloudProvider.GKE:
                # Use ManagedComponent validation method instead of ResourceManager's
                await self._ensure_gke_authenticated()
                zone = kwargs.get("zone")
                if not zone:
                    return self._ResponseFormatter.format_error_response(
                        "connect cloud cluster",
                        Exception("zone is required for GKE cluster connection"),
                    )
                prompt = f"connect to GKE cluster {cluster_name} in zone {zone}"
                if kwargs.get("project_id"):
                    prompt += f" in project {kwargs.get('project_id')}"
                return await self._gke_manager.execute_request(prompt)
            elif provider == CloudProvider.LOCAL:
                return await self._connect_local_cluster(cluster_name, kwargs)
            else:
                return self._ResponseFormatter.format_error_response(
                    "connect cloud cluster",
                    Exception(
                        f"Cluster connection not implemented for {provider.value}"
                    ),
                )

        except Exception as e:
            return self._ResponseFormatter.format_error_response(
                "connect cloud cluster", e
            )

    async def _create_cloud_cluster(
        self, provider: CloudProvider, cluster_spec: Dict[str, Any], **kwargs
    ) -> Dict[str, Any]:
        """Create a cloud cluster."""
        try:
            # Validate cluster specification
            validation_result = await self._validate_cluster_spec(
                provider, cluster_spec
            )
            if not validation_result.get("valid", False):
                return validation_result

            # Route to appropriate manager (they handle their own authentication)
            if provider == CloudProvider.GKE:
                # Use ManagedComponent validation method instead of ResourceManager's
                await self._ensure_gke_authenticated()
                cluster_name = cluster_spec.get("name", "ray-cluster")
                location = cluster_spec.get("location", "us-central1-a")
                prompt = f"create GKE cluster {cluster_name} in location {location}"
                if kwargs.get("project_id"):
                    prompt += f" in project {kwargs.get('project_id')}"
                return await self._gke_manager.execute_request(prompt)
            elif provider == CloudProvider.LOCAL:
                return self._ResponseFormatter.format_error_response(
                    "create cloud cluster",
                    Exception(
                        "Local cluster creation not supported. Use existing clusters or Docker/minikube."
                    ),
                )
            else:
                return self._ResponseFormatter.format_error_response(
                    "create cloud cluster",
                    Exception(f"Cluster creation not implemented for {provider.value}"),
                )

        except Exception as e:
            return self._ResponseFormatter.format_error_response(
                "create cloud cluster", e
            )

    # Provider-specific authentication methods
    async def _authenticate_gke(self, auth_config: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate with GKE."""
        prompt = f"authenticate with GCP"
        if auth_config.get("project_id"):
            prompt += f" project {auth_config.get('project_id')}"
        return await self._gke_manager.execute_request(prompt)

    async def _authenticate_local(self, auth_config: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate with local Kubernetes."""
        try:
            from kubernetes import config

            # Load kubeconfig
            config_file = auth_config.get("config_file")
            context = auth_config.get("context")

            if config_file:
                config.load_kube_config(config_file=config_file, context=context)
            else:
                config.load_kube_config(context=context)

            # Get current context
            contexts, active_context = config.list_kube_config_contexts()
            current_context = active_context["name"] if active_context else context

            # Simple state tracking (no complex state manager)
            self._last_connected_cluster = current_context

            return self._ResponseFormatter.format_success_response(
                provider="local",
                authenticated=True,
                auth_type="kubeconfig",
                context=current_context,
            )

        except Exception as e:
            return self._ResponseFormatter.format_error_response(
                "local authentication", e
            )

    # Local Kubernetes operations
    async def _list_local_contexts(self) -> Dict[str, Any]:
        """List local Kubernetes contexts."""
        try:
            from kubernetes import config

            contexts, active_context = config.list_kube_config_contexts()
            context_names = []
            if contexts:
                for ctx in contexts:
                    if isinstance(ctx, dict) and "name" in ctx:
                        context_names.append(ctx["name"])
            active_context_name = None
            if (
                active_context
                and isinstance(active_context, dict)
                and "name" in active_context
            ):
                active_context_name = active_context["name"]

            return self._ResponseFormatter.format_success_response(
                contexts=context_names,
                active_context=active_context_name,
                count=len(context_names),
            )

        except Exception as e:
            return self._ResponseFormatter.format_error_response(
                "list local contexts", e
            )

    async def _connect_local_cluster(
        self, cluster_name: str, kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Connect to local Kubernetes cluster."""
        try:
            from kubernetes import config

            # Load kubeconfig with the specified context
            config_file = kwargs.get("config_file")
            if config_file:
                config.load_kube_config(config_file=config_file, context=cluster_name)
            else:
                config.load_kube_config(context=cluster_name)

            # Update state
            # Simple state tracking (no complex state manager)
            self._last_connected_cluster = cluster_name

            return self._ResponseFormatter.format_success_response(
                provider="local",
                connected=True,
                cluster_name=cluster_name,
                context=cluster_name,
            )

        except Exception as e:
            return self._ResponseFormatter.format_error_response(
                "connect local cluster", e
            )

    # Validation methods
    async def _validate_cluster_spec(
        self, provider: CloudProvider, cluster_spec: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate cluster specification for a provider."""
        try:
            # Common validation
            if not cluster_spec.get("name"):
                return self._ResponseFormatter.format_error_response(
                    "validate cluster spec", Exception("Cluster name is required")
                )

            # Provider-specific validation
            if provider == CloudProvider.GKE:
                return await self._validate_gke_cluster_spec(cluster_spec)
            else:
                return self._ResponseFormatter.format_success_response(
                    valid=True, cluster_spec=cluster_spec
                )

        except Exception as e:
            return self._ResponseFormatter.format_error_response(
                "validate cluster spec", e
            )

    async def _validate_gke_cluster_spec(
        self, cluster_spec: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate GKE cluster specification."""
        required_fields = ["name"]
        recommended_fields = ["zone", "machine_type", "disk_size"]

        # Check required fields
        missing_fields = [
            field for field in required_fields if field not in cluster_spec
        ]
        if missing_fields:
            return self._ResponseFormatter.format_error_response(
                "validate gke cluster spec",
                Exception(f"Missing required fields: {', '.join(missing_fields)}"),
            )

        # Check for recommended fields
        missing_recommended = [
            field for field in recommended_fields if field not in cluster_spec
        ]
        warnings = []
        if missing_recommended:
            warnings.append(
                f"Missing recommended fields: {', '.join(missing_recommended)}"
            )

        return self._ResponseFormatter.format_success_response(
            valid=True, cluster_spec=cluster_spec, warnings=warnings
        )

    # Utility methods
    def get_gke_manager(self) -> GKEManager:
        """Get the GKE cluster manager."""
        return self._gke_manager

    def _get_current_time(self) -> str:
        """Get current time as ISO string."""
        from datetime import datetime

        return datetime.utcnow().isoformat() + "Z"

    async def check_environment(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """Check environment setup, dependencies, and authentication status."""
        try:
            # Use unified config manager for environment checking
            env_detection = self._config_manager.detect_environment()
            validation = self._config_manager.validate_config()

            return self._ResponseFormatter.format_success_response(
                message="Environment check completed successfully",
                environment=env_detection,
                validation=validation,
                providers_available=env_detection["providers"],
                default_provider=env_detection.get("default_provider"),
            )

        except Exception as e:
            return self._ResponseFormatter.format_error_response("check environment", e)

    async def _ensure_gke_authenticated(self) -> Dict[str, Any]:
        """Ensure GKE authentication is configured."""
        try:
            self._ensure_gcp_available()

            # Check if credentials are available
            gcp_config = self._config_manager.get_gcp_config()
            if not gcp_config.get("project_id"):
                return self._ResponseFormatter.format_error_response(
                    "ensure gke authenticated",
                    Exception(
                        "GCP project_id not configured. Set GOOGLE_APPLICATION_CREDENTIALS or configure authentication."
                    ),
                )

            return self._ResponseFormatter.format_success_response(
                message="GKE authentication configured",
                project_id=gcp_config.get("project_id"),
            )

        except Exception as e:
            return self._ResponseFormatter.format_error_response(
                "ensure gke authenticated", e
            )
