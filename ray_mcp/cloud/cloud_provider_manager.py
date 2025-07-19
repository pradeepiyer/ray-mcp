"""Pure prompt-driven cloud provider management for Ray MCP."""

import asyncio
import os
from typing import Any, Optional

from ..config import config
from ..foundation.enums import CloudProvider
from ..foundation.logging_utils import error_response, success_response
from ..foundation.resource_manager import ResourceManager
from ..llm_parser import get_parser
from .eks_manager import EKSManager
from .gke_manager import GKEManager


class CloudProviderManager(ResourceManager):
    """Pure prompt-driven cloud provider management - no traditional APIs."""

    def __init__(self):
        super().__init__(
            enable_ray=False,
            enable_kubernetes=True,
            enable_cloud=True,
        )

        self._gke_manager = GKEManager()
        self._eks_manager = EKSManager()

    async def execute_request(self, prompt: str) -> dict[str, Any]:
        """Execute cloud operations using natural language prompts.

        Examples:
            - "authenticate with GCP"
            - "connect to GKE cluster named my-cluster"
            - "list kubernetes clusters"
            - "check environment status"
        """
        try:
            action = await get_parser().parse_cloud_action(prompt)
            operation = action["operation"]

            if operation == "authenticate":
                return await self._authenticate_from_prompt(action)
            elif operation == "connect_cluster":
                return await self._connect_cluster_from_prompt(action)
            elif operation == "list_clusters":
                provider = action.get("provider", "gcp")
                if self._is_gcp_provider(provider):
                    return await self._list_cloud_clusters(CloudProvider.GKE)
                elif self._is_aws_provider(provider):
                    return await self._list_cloud_clusters(CloudProvider.AWS)
                elif self._is_azure_provider(provider):
                    return error_response("Azure cluster listing not yet implemented")
                else:
                    # Default to GCP for backward compatibility
                    return await self._list_cloud_clusters(CloudProvider.GKE)
            elif operation == "create_cluster":
                return await self._create_cluster_from_prompt(action)
            elif operation == "check_environment":
                return await self._detect_cloud_provider()
            else:
                return error_response(f"Unknown operation: {operation}")

        except ValueError as e:
            return error_response(f"Could not parse request: {str(e)}")
        except Exception as e:
            return self._handle_error("execute_request", e)

    # =================================================================
    # INTERNAL IMPLEMENTATION: All methods are now private
    # =================================================================

    def _is_gcp_provider(self, provider: str) -> bool:
        """Check if provider string refers to GCP/GKE (both are synonymous)."""
        return provider.lower() in [
            "gcp",
            "gke",
            "google cloud",
            "google",
            "google cloud platform",
        ]

    def _is_aws_provider(self, provider: str) -> bool:
        """Check if provider string refers to AWS."""
        return provider.lower() in [
            "aws",
            "amazon",
            "amazon cloud",
            "amazon web services",
        ]

    def _is_azure_provider(self, provider: str) -> bool:
        """Check if provider string refers to Azure."""
        return provider.lower() in ["azure", "microsoft azure", "azure cloud"]

    def _normalize_provider(self, provider: str) -> str:
        """Normalize provider string to standard values."""
        if self._is_gcp_provider(provider):
            return "gcp"
        elif self._is_aws_provider(provider):
            return "aws"
        elif self._is_azure_provider(provider):
            return "azure"
        else:
            return provider.lower()

    async def _authenticate_from_prompt(self, action: dict[str, Any]) -> dict[str, Any]:
        """Convert parsed prompt action to cloud authentication."""
        provider = action.get("provider", "gcp")
        project = action.get("project_id")

        # Normalize provider string
        normalized_provider = self._normalize_provider(provider)

        if self._is_gcp_provider(provider):
            auth_config = {}
            if project:
                auth_config["project_id"] = project
            return await self._authenticate_cloud_provider(
                CloudProvider.GKE, auth_config=auth_config
            )
        elif self._is_aws_provider(provider):
            auth_config = {}
            if action.get("zone"):  # AWS regions are passed as "zone" in LLM parser
                auth_config["region"] = action.get("zone")
            return await self._authenticate_cloud_provider(
                CloudProvider.AWS, auth_config=auth_config
            )
        elif self._is_azure_provider(provider):
            return error_response("Azure authentication not yet implemented")
        else:
            return error_response(f"Unsupported provider: {provider}")

    async def _connect_cluster_from_prompt(
        self, action: dict[str, Any]
    ) -> dict[str, Any]:
        """Convert parsed prompt action to cluster connection."""
        cluster_name = action.get("cluster_name")
        provider = action.get("provider", "gcp")

        if not cluster_name:
            return error_response("cluster_name required for connection")

        if self._is_gcp_provider(provider):
            return await self._connect_cloud_cluster(
                CloudProvider.GKE, cluster_name=cluster_name
            )
        elif self._is_aws_provider(provider):
            return await self._connect_cloud_cluster(
                CloudProvider.AWS, cluster_name=cluster_name
            )
        elif self._is_azure_provider(provider):
            return error_response("Azure cluster connection not yet implemented")
        else:
            return error_response(f"Unsupported provider: {provider}")

    async def _create_cluster_from_prompt(
        self, action: dict[str, Any]
    ) -> dict[str, Any]:
        """Convert parsed prompt action to cluster creation."""
        cluster_name = action.get("cluster_name")
        provider = action.get("provider", "gcp")
        zone = action.get("zone", "us-central1-a")

        if not cluster_name:
            return error_response("cluster_name required for creation")

        if self._is_gcp_provider(provider):
            cluster_spec = {"name": cluster_name, "zone": zone}
            return await self._create_cloud_cluster(
                CloudProvider.GKE, cluster_spec=cluster_spec
            )
        elif self._is_aws_provider(provider):
            cluster_spec = {"name": cluster_name, "region": zone}
            return await self._create_cloud_cluster(
                CloudProvider.AWS, cluster_spec=cluster_spec
            )
        elif self._is_azure_provider(provider):
            return error_response("Azure cluster creation not yet implemented")
        else:
            return error_response(f"Unsupported provider: {provider}")

    async def _detect_cloud_provider(self) -> dict[str, Any]:
        """Detect available cloud providers and authentication methods."""
        try:
            # Simple environment detection using direct config access
            providers_status = {}

            # Check GKE availability
            gcp_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if gcp_credentials and config.gcp_project_id:
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

            # Check AWS/EKS availability
            aws_credentials_available = (
                (os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"))
                or os.getenv("AWS_PROFILE")
                or os.path.exists(os.path.expanduser("~/.aws/credentials"))
            )

            if aws_credentials_available:
                providers_status["eks"] = {
                    "available": True,
                    "auth_type": "aws_credentials",
                    "description": "Amazon Elastic Kubernetes Service",
                }
            else:
                providers_status["eks"] = {
                    "available": False,
                    "reason": "AWS credentials not available or not configured",
                }

            # Local Kubernetes
            try:
                from kubernetes import config as k8s_config

                k8s_config.load_kube_config()
                providers_status["local"] = {
                    "available": True,
                    "auth_type": "kubeconfig",
                    "description": "Local Kubernetes cluster via kubeconfig",
                }
            except Exception:
                providers_status["local"] = {
                    "available": False,
                    "reason": "Kubernetes client not available or not configured",
                }

            # Determine default provider
            default_provider = (
                "gke"
                if providers_status["gke"]["available"]
                else (
                    "eks"
                    if providers_status["eks"]["available"]
                    else "local" if providers_status["local"]["available"] else None
                )
            )

            return success_response(
                message="Cloud provider detection completed successfully",
                detected_provider=default_provider,
                providers=providers_status,
                environment={
                    "gcp_project_id": config.gcp_project_id,
                    "aws_region": getattr(config, "aws_region", None),
                    "kubernetes_namespace": config.kubernetes_namespace,
                },
                supported_providers=[p.value for p in CloudProvider],
            )

        except Exception as e:
            return self._handle_error("detect cloud provider", e)

    async def _authenticate_cloud_provider(
        self, provider: CloudProvider, auth_config: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Authenticate with a cloud provider."""
        try:
            # Validate provider
            if provider not in CloudProvider:
                return error_response(f"Unsupported provider: {provider}")

            # Route to appropriate manager
            if provider == CloudProvider.GKE:
                return await self._authenticate_gke(auth_config or {})
            elif provider == CloudProvider.AWS:
                return await self._authenticate_aws(auth_config or {})
            elif provider == CloudProvider.LOCAL:
                return await self._authenticate_local(auth_config or {})
            else:
                return error_response(
                    f"Authentication not implemented for {provider.value}"
                )

        except Exception as e:
            return self._handle_error("authenticate cloud provider", e)

    async def _list_cloud_clusters(
        self, provider: CloudProvider, **kwargs
    ) -> dict[str, Any]:
        """List clusters for a cloud provider."""
        try:
            # Route to appropriate manager (they handle their own authentication)
            if provider == CloudProvider.GKE:
                # Use ManagedComponent validation method instead of ResourceManager's
                await self._ensure_gke_authenticated()
                prompt = "list all GKE clusters"
                if kwargs.get("project_id"):
                    prompt += f" in project {kwargs.get('project_id')}"
                if kwargs.get("zone"):
                    prompt += f" in location {kwargs.get('zone')}"
                return await self._gke_manager.execute_request(prompt)
            elif provider == CloudProvider.AWS:
                await self._ensure_aws_authenticated()
                prompt = "list all EKS clusters"
                if kwargs.get("region"):
                    prompt += f" in region {kwargs.get('region')}"
                return await self._eks_manager.execute_request(prompt)
            elif provider == CloudProvider.LOCAL:
                return await self._list_local_contexts()
            else:
                return error_response(
                    f"Cluster listing not implemented for {provider.value}"
                )

        except Exception as e:
            return self._handle_error("list cloud clusters", e)

    async def _connect_cloud_cluster(
        self, provider: CloudProvider, cluster_name: str, **kwargs
    ) -> dict[str, Any]:
        """Connect to a cloud cluster."""
        try:
            # Route to appropriate manager (they handle their own authentication)
            if provider == CloudProvider.GKE:
                # Use ManagedComponent validation method instead of ResourceManager's
                await self._ensure_gke_authenticated()
                zone = kwargs.get("zone")
                if not zone:
                    # Auto-discover zone by listing clusters and finding matching cluster name
                    try:
                        discovery_result = await self._gke_manager.execute_request(
                            "list all GKE clusters"
                        )
                        if "clusters" in discovery_result:
                            for cluster in discovery_result["clusters"]:
                                if cluster.get("name") == cluster_name:
                                    zone = cluster.get("location")
                                    break

                        if not zone:
                            return error_response(
                                f"Could not find cluster '{cluster_name}' in any zone. Please specify the zone explicitly or ensure the cluster exists."
                            )
                    except Exception as e:
                        return error_response(
                            f"Could not auto-discover zone for cluster '{cluster_name}': {str(e)}"
                        )
                prompt = f"connect to GKE cluster {cluster_name} in zone {zone}"
                if kwargs.get("project_id"):
                    prompt += f" in project {kwargs.get('project_id')}"
                return await self._gke_manager.execute_request(prompt)
            elif provider == CloudProvider.AWS:
                await self._ensure_aws_authenticated()
                region = kwargs.get("region")
                if not region:
                    # Auto-discover region by listing clusters and finding matching cluster name
                    try:
                        discovery_result = await self._eks_manager.execute_request(
                            "list all EKS clusters"
                        )
                        if "clusters" in discovery_result:
                            for cluster in discovery_result["clusters"]:
                                if cluster.get("name") == cluster_name:
                                    region = cluster.get("region")
                                    break

                        if not region:
                            return error_response(
                                f"Could not find cluster '{cluster_name}' in any region. Please specify the region explicitly or ensure the cluster exists."
                            )
                    except Exception as e:
                        return error_response(
                            f"Could not auto-discover region for cluster '{cluster_name}': {str(e)}"
                        )
                prompt = f"connect to EKS cluster {cluster_name} in region {region}"
                return await self._eks_manager.execute_request(prompt)
            elif provider == CloudProvider.LOCAL:
                return await self._connect_local_cluster(cluster_name, kwargs)
            else:
                return error_response(
                    f"Cluster connection not implemented for {provider.value}"
                )

        except Exception as e:
            return self._handle_error("connect cloud cluster", e)

    async def _create_cloud_cluster(
        self, provider: CloudProvider, cluster_spec: dict[str, Any], **kwargs
    ) -> dict[str, Any]:
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
            elif provider == CloudProvider.AWS:
                await self._ensure_aws_authenticated()
                cluster_name = cluster_spec.get("name", "ray-cluster")
                region = cluster_spec.get("region", "us-west-2")
                prompt = f"create EKS cluster {cluster_name} in region {region}"
                return await self._eks_manager.execute_request(prompt)
            elif provider == CloudProvider.LOCAL:
                return error_response(
                    "Local cluster creation not supported. Use existing clusters or Docker/minikube."
                )
            else:
                return error_response(
                    f"Cluster creation not implemented for {provider.value}"
                )

        except Exception as e:
            return self._handle_error("create cloud cluster", e)

    # Provider-specific authentication methods
    async def _authenticate_gke(self, auth_config: dict[str, Any]) -> dict[str, Any]:
        """Authenticate with GKE."""
        prompt = "authenticate with GCP"
        if auth_config.get("project_id"):
            prompt += f" project {auth_config.get('project_id')}"
        return await self._gke_manager.execute_request(prompt)

    async def _authenticate_aws(self, auth_config: dict[str, Any]) -> dict[str, Any]:
        """Authenticate with AWS."""
        prompt = "authenticate with AWS"
        if auth_config.get("region"):
            prompt += f" region {auth_config.get('region')}"
        return await self._eks_manager.execute_request(prompt)

    async def _authenticate_local(self, auth_config: dict[str, Any]) -> dict[str, Any]:
        """Authenticate with local Kubernetes."""
        try:
            from kubernetes import config as kube_config

            # Load kubeconfig
            config_file = auth_config.get("config_file")
            context = auth_config.get("context")

            if config_file:
                await asyncio.to_thread(
                    kube_config.load_kube_config,
                    config_file=config_file,
                    context=context,
                )
            else:
                await asyncio.to_thread(kube_config.load_kube_config, context=context)

            # Get current context
            contexts, active_context = await asyncio.to_thread(
                kube_config.list_kube_config_contexts
            )
            current_context = active_context["name"] if active_context else context

            # Simple state tracking (no complex state manager)
            self._last_connected_cluster = current_context

            return success_response(
                provider="local",
                authenticated=True,
                auth_type="kubeconfig",
                context=current_context,
            )

        except Exception as e:
            return self._handle_error("local authentication", e)

    # Local Kubernetes operations
    async def _list_local_contexts(self) -> dict[str, Any]:
        """List local Kubernetes contexts."""
        try:
            from kubernetes import config as kube_config

            contexts, active_context = await asyncio.to_thread(
                kube_config.list_kube_config_contexts
            )
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

            return success_response(
                contexts=context_names,
                active_context=active_context_name,
                count=len(context_names),
            )

        except Exception as e:
            return self._handle_error("list local contexts", e)

    async def _connect_local_cluster(
        self, cluster_name: str, kwargs: dict[str, Any]
    ) -> dict[str, Any]:
        """Connect to local Kubernetes cluster."""
        try:
            from kubernetes import config as kube_config

            # Load kubeconfig with the specified context
            config_file = kwargs.get("config_file")
            if config_file:
                await asyncio.to_thread(
                    kube_config.load_kube_config,
                    config_file=config_file,
                    context=cluster_name,
                )
            else:
                await asyncio.to_thread(
                    kube_config.load_kube_config, context=cluster_name
                )

            # Update state
            # Simple state tracking (no complex state manager)
            self._last_connected_cluster = cluster_name

            return success_response(
                provider="local",
                connected=True,
                cluster_name=cluster_name,
                context=cluster_name,
            )

        except Exception as e:
            return self._handle_error("connect local cluster", e)

    # Validation methods
    async def _validate_cluster_spec(
        self, provider: CloudProvider, cluster_spec: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate cluster specification for a provider."""
        try:
            # Common validation
            if not cluster_spec.get("name"):
                return error_response("Cluster name is required")

            # Provider-specific validation
            if provider == CloudProvider.GKE:
                return await self._validate_gke_cluster_spec(cluster_spec)
            else:
                return success_response(valid=True, cluster_spec=cluster_spec)

        except Exception as e:
            return self._handle_error("validate cluster spec", e)

    async def _validate_gke_cluster_spec(
        self, cluster_spec: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate GKE cluster specification."""
        required_fields = ["name"]
        recommended_fields = ["zone", "machine_type", "disk_size"]

        # Check required fields
        missing_fields = [
            field for field in required_fields if field not in cluster_spec
        ]
        if missing_fields:
            return error_response(
                f"Missing required fields: {', '.join(missing_fields)}"
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

        return success_response(
            valid=True, cluster_spec=cluster_spec, warnings=warnings
        )

    # Utility methods
    def get_gke_manager(self) -> GKEManager:
        """Get the GKE cluster manager."""
        return self._gke_manager

    def get_eks_manager(self) -> EKSManager:
        """Get the EKS cluster manager."""
        return self._eks_manager

    def _get_current_time(self) -> str:
        """Get current time as ISO string."""
        from datetime import datetime

        return datetime.utcnow().isoformat() + "Z"

    async def check_environment(self, provider: Optional[str] = None) -> dict[str, Any]:
        """Check environment setup, dependencies, and authentication status."""
        try:
            # Simple environment check using direct config access
            env_info = {
                "gcp_project_id": config.gcp_project_id,
                "kubernetes_namespace": config.kubernetes_namespace,
                "gke_region": config.gke_region,
                "gke_zone": config.gke_zone,
                "gcp_credentials_available": bool(
                    os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                ),
            }

            # Simple validation
            validation = {
                "config_valid": True,
                "missing_fields": [],
            }

            return success_response(
                message="Environment check completed successfully",
                environment=env_info,
                validation=validation,
                providers_available=["gke", "local"],
                default_provider=(
                    "gke" if env_info["gcp_credentials_available"] else "local"
                ),
            )

        except Exception as e:
            return self._handle_error("check environment", e)

    async def _ensure_gke_authenticated(self) -> dict[str, Any]:
        """Ensure GKE authentication is configured and credentials are valid."""
        try:
            # Delegate to the actual GKE manager for proper credential verification
            return await self._gke_manager._ensure_gke_authenticated()

        except Exception as e:
            return self._handle_error("ensure gke authenticated", e)

    async def _ensure_aws_authenticated(self) -> dict[str, Any]:
        """Ensure AWS authentication is configured and credentials are valid."""
        try:
            # Delegate to the actual EKS manager for proper credential verification
            return await self._eks_manager._ensure_eks_authenticated()

        except Exception as e:
            return self._handle_error("ensure aws authenticated", e)
