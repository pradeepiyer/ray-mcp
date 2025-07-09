"""Unit tests for KubernetesClusterManager component.

Tests focus on Kubernetes cluster management behavior with 100% mocking.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ray_mcp.core.kubernetes.managers.kubernetes_manager import KubernetesClusterManager
from ray_mcp.core.managers.state_manager import RayStateManager


class TestKubernetesManager:
    """Test cases for KubernetesClusterManager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.state_manager = RayStateManager()
        self.kubernetes_manager = KubernetesClusterManager(self.state_manager)

    def test_manager_initialization(self):
        """Test that Kubernetes manager initializes correctly."""
        assert self.kubernetes_manager is not None
        assert self.kubernetes_manager.state_manager is self.state_manager
        assert self.kubernetes_manager.get_config_manager() is not None
        assert self.kubernetes_manager.get_client() is not None

    @pytest.mark.asyncio
    async def test_connect_cluster_without_kubernetes_lib(self):
        """Test connecting to cluster without kubernetes library."""
        manager = KubernetesClusterManager(self.state_manager)

        # Mock the import system to simulate kubernetes not being available
        manager._config_manager._KUBERNETES_AVAILABLE = False

        result = await manager.connect()

        assert result is not None
        assert result.get("status") == "error"
        assert "kubernetes" in result.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_disconnect_cluster(self):
        """Test disconnecting from cluster."""
        # First set some state
        self.state_manager.update_state(
            kubernetes_connected=True, kubernetes_context="test-context"
        )

        result = await self.kubernetes_manager.disconnect_cluster()

        assert result is not None
        assert result.get("status") == "success"
        assert not self.state_manager.get_state().get("kubernetes_connected", True)
        assert self.state_manager.get_state().get("kubernetes_context") is None

    @pytest.mark.asyncio
    async def test_health_check_not_connected(self):
        """Test health check when not connected."""
        result = await self.kubernetes_manager.health_check()

        assert result is not None
        assert result.get("status") == "error"
        assert "not connected" in result.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_inspect_cluster_not_connected(self):
        """Test inspect cluster when not connected."""
        result = await self.kubernetes_manager.inspect_cluster()

        assert result is not None
        assert result.get("status") == "error"
        assert "not connected" in result.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_get_namespaces_not_connected(self):
        """Test get namespaces when not connected."""
        with pytest.raises(RuntimeError, match="not connected"):
            await self.kubernetes_manager.get_namespaces()

    @pytest.mark.asyncio
    async def test_get_nodes_not_connected(self):
        """Test get nodes when not connected."""
        with pytest.raises(RuntimeError, match="not connected"):
            await self.kubernetes_manager.get_nodes()

    @pytest.mark.asyncio
    async def test_get_pods_not_connected(self):
        """Test get pods when not connected."""
        with pytest.raises(RuntimeError, match="not connected"):
            await self.kubernetes_manager.get_pods()

    @pytest.mark.asyncio
    async def test_validate_config(self):
        """Test config validation."""
        result = await self.kubernetes_manager.validate_config()

        assert result is not None
        # Should not raise an exception and should return a result


class TestKubernetesManagerIntegration:
    """Integration tests for Kubernetes manager with unified manager."""

    def setup_method(self):
        """Set up test fixtures."""
        from ray_mcp.core.managers.unified_manager import RayUnifiedManager

        self.unified_manager = RayUnifiedManager()

    def test_kubernetes_manager_available(self):
        """Test that Kubernetes manager is available in unified manager."""
        k8s_manager = self.unified_manager.get_kubernetes_manager()
        assert k8s_manager is not None
        assert hasattr(k8s_manager, "connect")
        assert hasattr(k8s_manager, "disconnect_cluster")
        assert hasattr(k8s_manager, "inspect_cluster")

    def test_kubernetes_properties(self):
        """Test Kubernetes properties in unified manager."""
        assert hasattr(self.unified_manager, "is_kubernetes_connected")
        assert hasattr(self.unified_manager, "kubernetes_context")
        assert hasattr(self.unified_manager, "kubernetes_server_version")

        # Test initial state
        assert self.unified_manager.is_kubernetes_connected is False
        assert self.unified_manager.kubernetes_context is None
        assert self.unified_manager.kubernetes_server_version is None

    @pytest.mark.asyncio
    async def test_kubernetes_methods_available(self):
        """Test that Kubernetes methods are available in unified manager."""
        methods = [
            "connect_kubernetes_cluster",
            "disconnect_kubernetes_cluster",
            "inspect_kubernetes_cluster",
            "kubernetes_health_check",
            "list_kubernetes_contexts",
            "get_kubernetes_namespaces",
            "get_kubernetes_nodes",
            "get_kubernetes_pods",
            "validate_kubernetes_config",
        ]

        for method_name in methods:
            assert hasattr(self.unified_manager, method_name)
            method = getattr(self.unified_manager, method_name)
            assert callable(method)

    @pytest.mark.asyncio
    async def test_disconnect_kubernetes_cluster(self):
        """Test disconnecting from Kubernetes cluster through unified manager."""
        result = await self.unified_manager.disconnect_kubernetes_cluster()

        assert result is not None
        assert result.get("status") == "success"
        assert not self.unified_manager.is_kubernetes_connected
