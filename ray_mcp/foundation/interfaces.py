"""Core interfaces and components for Ray MCP."""

from abc import ABC
from enum import Enum
from typing import Any, Dict


class CloudProvider(Enum):
    """Supported cloud providers."""

    GKE = "gke"
    LOCAL = "local"


class AuthenticationType(Enum):
    """Authentication types for cloud providers."""

    SERVICE_ACCOUNT = "service_account"
    KUBECONFIG = "kubeconfig"
    IN_CLUSTER = "in_cluster"


class ManagedComponent(ABC):
    """Unified base class for all MCP components with configurable validation.

    This replaces the former RayComponent, KubernetesComponent, KubeRayComponent,
    and CloudProviderComponent classes with a single, more maintainable base class.
    """

    def __init__(self, state_manager):
        self._state_manager = state_manager

    @property
    def state_manager(self):
        """Get the state manager."""
        return self._state_manager

    def _ensure_ray_initialized(self) -> None:
        """Ensure Ray is initialized."""
        if not self._state_manager.is_initialized():
            raise RuntimeError("Ray is not initialized. Please start Ray first.")

    def _ensure_kubernetes_connected(self) -> None:
        """Ensure Kubernetes is connected."""
        state = self._state_manager.get_state()
        if not state.get("kubernetes_connected", False):
            raise RuntimeError(
                "Kubernetes is not connected. Please connect to a cluster first."
            )

    def _ensure_kuberay_ready(self) -> None:
        """Ensure Kubernetes is connected and KubeRay is available."""
        self._ensure_kubernetes_connected()
        # Additional KubeRay-specific checks could be added here

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
