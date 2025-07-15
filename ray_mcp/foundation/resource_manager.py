"""Simplified base class for Ray MCP managers."""

from typing import Any

from .import_utils import (
    GOOGLE_AUTH_AVAILABLE,
    GOOGLE_CLOUD_AVAILABLE,
    GOOGLE_SERVICE_ACCOUNT_AVAILABLE,
    KUBERNETES_AVAILABLE,
    RAY_AVAILABLE,
    ApiException,
    ConfigException,
    DefaultCredentialsError,
    client,
    config,
    container_v1,
    default,
    google_auth_transport,
    ray,
    service_account,
)
from .logging_utils import LoggingUtility, error_response


class ResourceManager:
    """Simple base class for Ray MCP managers."""

    def __init__(
        self,
        enable_ray: bool = False,
        enable_kubernetes: bool = False,
        enable_cloud: bool = False,
    ):
        self.logger = LoggingUtility()

        # Store flags for availability checks
        self.enable_ray = enable_ray
        self.enable_kubernetes = enable_kubernetes
        self.enable_cloud = enable_cloud

    def _is_ray_ready(self) -> bool:
        """Check if Ray is ready."""
        return RAY_AVAILABLE and ray and ray.is_initialized()

    def _is_kubernetes_ready(self) -> bool:
        """Check if Kubernetes is ready."""
        if not KUBERNETES_AVAILABLE:
            return False
        try:
            if config:
                config.load_kube_config()
                return True
            return False
        except Exception:
            return False

    def _ensure_ray_available(self) -> None:
        """Ensure Ray is available."""
        if not RAY_AVAILABLE:
            raise RuntimeError(
                "Ray is not available. Please install Ray: pip install ray[default]"
            )

    def _ensure_kubernetes_available(self) -> None:
        """Ensure Kubernetes client is available."""
        if not KUBERNETES_AVAILABLE:
            raise RuntimeError(
                "Kubernetes client is not available. Please install: pip install kubernetes"
            )

    def _ensure_gcp_available(self) -> None:
        """Ensure GCP libraries are available."""
        if not GOOGLE_CLOUD_AVAILABLE:
            raise RuntimeError(
                "GCP libraries are not available. Please install: pip install google-cloud-container google-auth"
            )

    def _handle_error(self, operation: str, error: Exception) -> dict[str, Any]:
        """Handle errors with simple logging and response."""
        self.logger.log_error(operation, error)
        return error_response(f"Failed to {operation}: {str(error)}")
