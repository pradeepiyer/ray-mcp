"""Unified cloud provider management for Ray MCP."""

import asyncio
from typing import Any, Dict, Optional

from ...foundation.base_managers import ResourceManager
from ...foundation.interfaces import CloudProvider, CloudProviderManager
from ..config.cloud_provider_config import CloudProviderConfigManager
from ..config.cloud_provider_detector import CloudProviderDetector
from .gke_manager import GKEClusterManager


class UnifiedCloudProviderManager(ResourceManager, CloudProviderManager):
    """Unified manager for all cloud provider operations."""

    def __init__(
        self,
        state_manager,
        detector: Optional[CloudProviderDetector] = None,
        config_manager: Optional[CloudProviderConfigManager] = None,
        gke_manager: Optional[GKEClusterManager] = None,
    ):
        super().__init__(
            state_manager, enable_ray=False, enable_kubernetes=True, enable_cloud=True
        )
        self._detector = detector or CloudProviderDetector(state_manager)
        self._config_manager = config_manager or CloudProviderConfigManager(
            state_manager
        )
        self._gke_manager = gke_manager or GKEClusterManager(
            state_manager, self._detector, self._config_manager
        )

    async def detect_cloud_provider(self) -> Dict[str, Any]:
        """Detect available cloud providers and authentication methods."""
        try:
            # Detect current environment
            detected_provider = self._detector.detect_provider()
            available_auth = self._detector.get_auth_type()

            # Check which providers are available
            providers_status = {}

            # Check GKE availability
            gke_status = await self._check_gke_availability()
            providers_status["gke"] = gke_status

            # Local Kubernetes
            providers_status["local"] = {
                "available": True,
                "auth_type": "kubeconfig",
                "description": "Local Kubernetes cluster via kubeconfig",
            }

            return self._response_formatter.format_success_response(
                detected_provider=(
                    detected_provider.value if detected_provider else None
                ),
                detected_auth_type=available_auth.value if available_auth else None,
                providers=providers_status,
                supported_providers=[p.value for p in CloudProvider],
            )

        except Exception as e:
            return self._response_formatter.format_error_response(
                "detect cloud provider", e
            )

    async def authenticate_cloud_provider(
        self, provider: CloudProvider, auth_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Authenticate with a cloud provider."""
        try:
            # Validate provider
            if provider not in CloudProvider:
                return self._response_formatter.format_error_response(
                    "authenticate cloud provider",
                    Exception(f"Unsupported provider: {provider}"),
                )

            # Route to appropriate manager
            if provider == CloudProvider.GKE:
                return await self._authenticate_gke(auth_config or {})
            elif provider == CloudProvider.LOCAL:
                return await self._authenticate_local(auth_config or {})
            else:
                return self._response_formatter.format_error_response(
                    "authenticate cloud provider",
                    Exception(f"Authentication not implemented for {provider.value}"),
                )

        except Exception as e:
            return self._response_formatter.format_error_response(
                "authenticate cloud provider", e
            )

    async def list_cloud_clusters(
        self, provider: CloudProvider, **kwargs
    ) -> Dict[str, Any]:
        """List clusters for a cloud provider."""
        try:
            # Route to appropriate manager (they handle their own authentication)
            if provider == CloudProvider.GKE:
                return await self._gke_manager.discover_gke_clusters(
                    kwargs.get("project_id"), kwargs.get("zone")
                )
            elif provider == CloudProvider.LOCAL:
                return await self._list_local_contexts()
            else:
                return self._response_formatter.format_error_response(
                    "list cloud clusters",
                    Exception(f"Cluster listing not implemented for {provider.value}"),
                )

        except Exception as e:
            return self._response_formatter.format_error_response(
                "list cloud clusters", e
            )

    async def connect_cloud_cluster(
        self, provider: CloudProvider, cluster_name: str, **kwargs
    ) -> Dict[str, Any]:
        """Connect to a cloud cluster."""
        try:
            # Route to appropriate manager (they handle their own authentication)
            if provider == CloudProvider.GKE:
                zone = kwargs.get("zone")
                if not zone:
                    return self._response_formatter.format_error_response(
                        "connect cloud cluster",
                        Exception("zone is required for GKE cluster connection"),
                    )
                return await self._gke_manager.connect_gke_cluster(
                    cluster_name, zone, kwargs.get("project_id")
                )
            elif provider == CloudProvider.LOCAL:
                return await self._connect_local_cluster(cluster_name, kwargs)
            else:
                return self._response_formatter.format_error_response(
                    "connect cloud cluster",
                    Exception(
                        f"Cluster connection not implemented for {provider.value}"
                    ),
                )

        except Exception as e:
            return self._response_formatter.format_error_response(
                "connect cloud cluster", e
            )

    async def create_cloud_cluster(
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
                return await self._gke_manager.create_gke_cluster(
                    cluster_spec, kwargs.get("project_id")
                )
            elif provider == CloudProvider.LOCAL:
                return self._response_formatter.format_error_response(
                    "create cloud cluster",
                    Exception(
                        "Local cluster creation not supported. Use existing clusters or Docker/minikube."
                    ),
                )
            else:
                return self._response_formatter.format_error_response(
                    "create cloud cluster",
                    Exception(f"Cluster creation not implemented for {provider.value}"),
                )

        except Exception as e:
            return self._response_formatter.format_error_response(
                "create cloud cluster", e
            )

    async def get_cloud_cluster_info(
        self, provider: CloudProvider, cluster_name: str, **kwargs
    ) -> Dict[str, Any]:
        """Get cloud cluster information."""
        try:
            # Route to appropriate manager (they handle their own authentication)
            if provider == CloudProvider.GKE:
                zone = kwargs.get("zone")
                if not zone:
                    return self._response_formatter.format_error_response(
                        "get cloud cluster info",
                        Exception("zone is required for GKE cluster info"),
                    )
                return await self._gke_manager.get_gke_cluster_info(
                    cluster_name, zone, kwargs.get("project_id")
                )
            elif provider == CloudProvider.LOCAL:
                return await self._get_local_cluster_info(cluster_name)
            else:
                return self._response_formatter.format_error_response(
                    "get cloud cluster info",
                    Exception(f"Cluster info not implemented for {provider.value}"),
                )

        except Exception as e:
            return self._response_formatter.format_error_response(
                "get cloud cluster info", e
            )

    # Provider-specific authentication methods
    async def _authenticate_gke(self, auth_config: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate with GKE."""
        return await self._gke_manager.authenticate_gke(
            auth_config.get("service_account_path"), auth_config.get("project_id")
        )

    async def _authenticate_local(self, auth_config: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate with local Kubernetes."""
        try:
            # Use existing Kubernetes configuration
            from ...kubernetes.config.kubernetes_config import KubernetesConfigManager

            k8s_config = KubernetesConfigManager()

            config_result = k8s_config.load_config(
                auth_config.get("config_file"), auth_config.get("context")
            )

            if config_result.get("success", False):
                # Update state
                self.state_manager.update_state(
                    cloud_provider_auth={
                        "local": {
                            "authenticated": True,
                            "auth_type": "kubeconfig",
                            "context": k8s_config.get_current_context(),
                            "auth_time": self._get_current_time(),
                        }
                    }
                )

                return self._response_formatter.format_success_response(
                    provider="local",
                    authenticated=True,
                    auth_type="kubeconfig",
                    context=k8s_config.get_current_context(),
                )
            else:
                return config_result

        except Exception as e:
            return self._response_formatter.format_error_response(
                "local authentication", e
            )

    # Provider availability checks
    async def _check_gke_availability(self) -> Dict[str, Any]:
        """Check GKE availability."""
        try:
            # Check if Google Cloud is available using the detector
            from ...foundation.import_utils import get_google_cloud_imports

            gcp_imports = get_google_cloud_imports()
            if not gcp_imports["GOOGLE_CLOUD_AVAILABLE"]:
                return {
                    "available": False,
                    "reason": "Google Cloud SDK not installed",
                    "install_command": "pip install google-cloud-container",
                }

            # Check for authentication
            auth_type = None
            if self._detector.detect_provider() == CloudProvider.GKE:
                auth_type = self._detector.get_auth_type()

            return {
                "available": True,
                "auth_type": auth_type.value if auth_type else None,
                "description": "Google Kubernetes Engine",
            }

        except Exception as e:
            return {"available": False, "error": str(e)}

    # Local Kubernetes operations
    async def _list_local_contexts(self) -> Dict[str, Any]:
        """List local Kubernetes contexts."""
        try:
            from ...kubernetes.config.kubernetes_config import KubernetesConfigManager

            k8s_config = KubernetesConfigManager()
            return await k8s_config.list_contexts()

        except Exception as e:
            return self._response_formatter.format_error_response(
                "list local contexts", e
            )

    async def _connect_local_cluster(
        self, cluster_name: str, kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Connect to local Kubernetes cluster."""
        try:
            from ...kubernetes.managers.kubernetes_manager import (
                KubernetesClusterManager,
            )

            k8s_manager = KubernetesClusterManager(self.state_manager)

            return await k8s_manager.connect_cluster(
                kwargs.get("config_file"), cluster_name  # Use cluster_name as context
            )

        except Exception as e:
            return self._response_formatter.format_error_response(
                "connect local cluster", e
            )

    async def _get_local_cluster_info(self, cluster_name: str) -> Dict[str, Any]:
        """Get local cluster information."""
        try:
            from ...kubernetes.managers.kubernetes_manager import (
                KubernetesClusterManager,
            )

            k8s_manager = KubernetesClusterManager(self.state_manager)

            return await k8s_manager.inspect_cluster()

        except Exception as e:
            return self._response_formatter.format_error_response(
                "get local cluster info", e
            )

    # Validation methods
    async def _validate_cluster_spec(
        self, provider: CloudProvider, cluster_spec: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate cluster specification for a provider."""
        try:
            # Common validation
            if not cluster_spec.get("name"):
                return self._response_formatter.format_error_response(
                    "validate cluster spec", Exception("Cluster name is required")
                )

            # Provider-specific validation
            if provider == CloudProvider.GKE:
                return await self._validate_gke_cluster_spec(cluster_spec)
            else:
                return self._response_formatter.format_success_response(
                    valid=True, cluster_spec=cluster_spec
                )

        except Exception as e:
            return self._response_formatter.format_error_response(
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
            return self._response_formatter.format_error_response(
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

        return self._response_formatter.format_success_response(
            valid=True, cluster_spec=cluster_spec, warnings=warnings
        )

    # Utility methods
    def get_detector(self) -> CloudProviderDetector:
        """Get the cloud provider detector."""
        return self._detector

    def get_config_manager(self) -> CloudProviderConfigManager:
        """Get the cloud provider configuration manager."""
        return self._config_manager

    def get_gke_manager(self) -> GKEClusterManager:
        """Get the GKE cluster manager."""
        return self._gke_manager

    def _get_current_time(self) -> str:
        """Get current time as ISO string."""
        from datetime import datetime

        return datetime.utcnow().isoformat() + "Z"

    async def check_environment(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """Check environment setup, dependencies, and authentication status."""
        try:
            import os
            import subprocess
            import sys

            results = {
                "python_version": sys.version,
                "python_executable": sys.executable,
                "environment": {},
                "dependencies": {},
                "authentication": {},
                "recommendations": [],
            }

            # Check which providers to examine
            providers_to_check = []
            if provider and provider != "all":
                if provider in ["gke", "local"]:
                    providers_to_check = [provider]
                else:
                    return self._response_formatter.format_error_response(
                        "check environment", Exception(f"Unknown provider: {provider}")
                    )
            else:
                providers_to_check = ["gke", "local"]

            # Check GKE environment
            if "gke" in providers_to_check:
                gke_env = await self._check_gke_environment()
                results["dependencies"]["gke"] = gke_env["dependencies"]
                results["authentication"]["gke"] = gke_env["authentication"]
                results["environment"]["gke"] = gke_env["environment"]
                results["recommendations"].extend(gke_env.get("recommendations", []))

            # Check local Kubernetes
            if "local" in providers_to_check:
                local_env = await self._check_local_environment()
                results["dependencies"]["local"] = local_env["dependencies"]
                results["authentication"]["local"] = local_env["authentication"]
                results["environment"]["local"] = local_env["environment"]
                results["recommendations"].extend(local_env.get("recommendations", []))

            # Add general recommendations
            if not any(
                results["dependencies"][p]["python_sdk"]
                for p in results["dependencies"]
            ):
                results["recommendations"].append(
                    "Consider installing cloud provider SDKs for better performance: "
                    "pip install 'ray-mcp[cloud]' or uv sync --extra cloud"
                )

            return self._response_formatter.format_success_response(**results)

        except Exception as e:
            return self._response_formatter.format_error_response(
                "check environment", e
            )

    async def _check_gke_environment(self) -> Dict[str, Any]:
        """Check GKE-specific environment setup."""
        import subprocess
        import sys

        result = {
            "dependencies": {"python_sdk": False, "cli": False},
            "authentication": {"ambient": False, "cli": False, "explicit": False},
            "environment": {},
            "recommendations": [],
        }

        # Check Python SDK
        try:
            from ...foundation.import_utils import get_google_cloud_imports

            gcp_imports = get_google_cloud_imports()
            if gcp_imports["GOOGLE_CLOUD_AVAILABLE"]:
                result["dependencies"]["python_sdk"] = True
                result["environment"]["google_cloud_sdk"] = "installed"
            else:
                raise ImportError("Google Cloud SDK not available")
        except ImportError:
            result["environment"]["google_cloud_sdk"] = "not_installed"
            result["recommendations"].append(
                f"Install Google Cloud SDK: {sys.executable} -m pip install 'ray-mcp[gke]'"
            )

        # Note: gcloud CLI is no longer used as fallback - Python SDK is required
        result["dependencies"]["cli"] = result["dependencies"]["python_sdk"]

        # Check authentication
        if result["dependencies"]["python_sdk"]:
            try:
                from ...foundation.import_utils import get_google_cloud_imports

                gcp_imports = get_google_cloud_imports()
                if gcp_imports["GOOGLE_AUTH_AVAILABLE"] and gcp_imports["default"]:
                    default_func = gcp_imports["default"]
                    credentials, project_id = await asyncio.to_thread(default_func)
                    if credentials and project_id:
                        result["authentication"]["ambient"] = True
                        result["environment"]["default_project"] = project_id
            except Exception:
                pass

        # CLI authentication is no longer used - only Python SDK
        result["authentication"]["cli"] = result["authentication"]["ambient"]

        # Check explicit authentication
        auth_state = (
            self.state_manager.get_state().get("cloud_provider_auth", {}).get("gke", {})
        )
        if auth_state.get("authenticated", False):
            result["authentication"]["explicit"] = True
            result["environment"]["auth_type"] = auth_state.get("auth_type")

        return result

    async def _check_local_environment(self) -> Dict[str, Any]:
        """Check local Kubernetes environment setup."""
        import os

        result = {
            "dependencies": {"kubernetes_python": False},
            "authentication": {"kubeconfig": False, "current_context": None},
            "environment": {},
            "recommendations": [],
        }

        # Check Kubernetes Python client
        try:
            import kubernetes

            result["dependencies"]["kubernetes_python"] = True
            result["environment"]["kubernetes_python"] = "installed"
        except ImportError:
            result["environment"]["kubernetes_python"] = "not_installed"
            result["recommendations"].append(
                "Kubernetes Python client should be available (included in ray-mcp)"
            )

        # Check kubeconfig
        kubeconfig_path = os.path.expanduser("~/.kube/config")
        if os.path.exists(kubeconfig_path):
            result["environment"]["kubeconfig_path"] = kubeconfig_path

            # Try to get current context using Kubernetes Python client
            if result["dependencies"]["kubernetes_python"]:
                try:
                    from kubernetes import config

                    contexts, active_context = config.list_kube_config_contexts()
                    if active_context:
                        result["authentication"]["kubeconfig"] = True
                        result["authentication"]["current_context"] = active_context[
                            "name"
                        ]
                        result["environment"]["current_context"] = active_context[
                            "name"
                        ]
                except Exception:
                    # If we can't load the config, kubeconfig might be invalid
                    pass
        else:
            result["environment"]["kubeconfig_path"] = "not_found"
            result["recommendations"].append(
                "Set up kubeconfig file or connect to a Kubernetes cluster"
            )

        return result

    async def get_provider_status(self, provider: CloudProvider) -> Dict[str, Any]:
        """Get status of a specific cloud provider."""
        try:
            state = self.state_manager.get_state()
            auth_state = state.get("cloud_provider_auth", {}).get(provider.value, {})
            connection_state = state.get("cloud_provider_connections", {}).get(
                provider.value, {}
            )

            return self._response_formatter.format_success_response(
                provider=provider.value,
                authenticated=auth_state.get("authenticated", False),
                connected=connection_state.get("connected", False),
                auth_details=auth_state,
                connection_details=connection_state,
            )

        except Exception as e:
            return self._response_formatter.format_error_response(
                f"get {provider.value} status", e
            )

    async def disconnect_cloud_provider(
        self, provider: CloudProvider
    ) -> Dict[str, Any]:
        """Disconnect from a cloud provider."""
        try:
            # Update state to remove connection
            state = self.state_manager.get_state()
            cloud_connections = state.get("cloud_provider_connections", {})

            if provider.value in cloud_connections:
                del cloud_connections[provider.value]
                self.state_manager.update_state(
                    cloud_provider_connections=cloud_connections
                )

            # If this was the active Kubernetes connection, reset that too
            if state.get("kubernetes_config_type") == provider.value:
                self.state_manager.update_state(
                    kubernetes_connected=False,
                    kubernetes_context=None,
                    kubernetes_config_type=None,
                    kubernetes_server_version=None,
                )

            return self._response_formatter.format_success_response(
                provider=provider.value, disconnected=True
            )

        except Exception as e:
            return self._response_formatter.format_error_response(
                f"disconnect {provider.value}", e
            )
