"""Kubernetes cluster management for Ray MCP."""

from typing import Any, Dict, List, Optional

from ...foundation.base_managers import ResourceManager
from ...foundation.interfaces import KubernetesManager
from ..config.kubernetes_client import KubernetesApiClient
from ..config.kubernetes_config import KubernetesConfigManager


class KubernetesClusterManager(ResourceManager, KubernetesManager):
    """Manages Kubernetes cluster operations with clean separation of concerns."""

    def __init__(
        self,
        state_manager,
        config_manager: Optional[KubernetesConfigManager] = None,
        client: Optional[KubernetesApiClient] = None,
    ):
        super().__init__(
            state_manager, enable_ray=False, enable_kubernetes=True, enable_cloud=False
        )
        self._config_manager = config_manager or KubernetesConfigManager()
        self._client = client or KubernetesApiClient(self._config_manager)

    async def connect(self, context: Optional[str] = None) -> Dict[str, Any]:
        """Connect to a Kubernetes cluster."""
        return await self._execute_operation(
            "connect to kubernetes cluster", self._connect_operation, context
        )

    async def _connect_operation(self, context: Optional[str] = None) -> Dict[str, Any]:
        """Execute Kubernetes cluster connection operation."""
        # Load configuration
        config_result = self._config_manager.load_config(context=context)

        if not config_result.get("success", False):
            return config_result

        # Test connection
        connection_result = await self._client.test_connection()

        if not connection_result.get("success", False):
            return connection_result

        # Update state to connected
        self._update_state(
            kubernetes_connected=True,
            kubernetes_context=self._config_manager.get_current_context(),
            kubernetes_config_type=config_result.get("config_type", "unknown"),
            kubernetes_server_version=connection_result.get("server_version"),
        )

        return {
            "connected": True,
            "context": self._config_manager.get_current_context(),
            "config_type": config_result.get("config_type"),
            "server_version": connection_result.get("server_version"),
        }

    async def connect_cluster(
        self, config_file: Optional[str] = None, context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Connect to Kubernetes cluster (interface method)."""
        return await self._execute_operation(
            "connect kubernetes cluster",
            self._connect_cluster_operation,
            config_file,
            context,
        )

    async def _connect_cluster_operation(
        self, config_file: Optional[str] = None, context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute Kubernetes cluster connection operation with config file support."""
        # Load configuration with config_file support
        config_result = self._config_manager.load_config(
            config_file=config_file, context=context
        )

        if not config_result.get("success", False):
            return config_result

        # Test connection
        connection_result = await self._client.test_connection()

        if not connection_result.get("success", False):
            return connection_result

        # Update state to connected
        self._update_state(
            kubernetes_connected=True,
            kubernetes_context=self._config_manager.get_current_context(),
            kubernetes_config_type=config_result.get("config_type", "unknown"),
            kubernetes_server_version=connection_result.get("server_version"),
        )

        return {
            "connected": True,
            "context": self._config_manager.get_current_context(),
            "config_type": config_result.get("config_type"),
            "server_version": connection_result.get("server_version"),
        }

    async def disconnect_cluster(self) -> Dict[str, Any]:
        """Disconnect from Kubernetes cluster."""
        return await self._execute_operation(
            "disconnect from kubernetes cluster", self._disconnect_cluster_operation
        )

    async def _disconnect_cluster_operation(self) -> Dict[str, Any]:
        """Execute Kubernetes cluster disconnection operation."""
        # Reset Kubernetes-related state
        self._update_state(
            kubernetes_connected=False,
            kubernetes_context=None,
            kubernetes_config_type=None,
            kubernetes_server_version=None,
        )

        return {"disconnected": True}

    async def inspect_cluster(self) -> Dict[str, Any]:
        """Inspect Kubernetes cluster."""
        return await self._execute_operation(
            "inspect kubernetes cluster", self._inspect_cluster_operation
        )

    async def _inspect_cluster_operation(self) -> Dict[str, Any]:
        """Execute Kubernetes cluster inspection operation."""
        self._ensure_connected()

        # Get comprehensive cluster information
        cluster_info = await self._client.get_cluster_info()
        if not cluster_info.get("success", False):
            return cluster_info

        # Get additional details
        namespaces_result = await self._client.list_namespaces()
        nodes_result = await self._client.get_nodes()

        # Compile inspection data
        inspection_data = {
            "cluster_info": cluster_info.get("data", {}),
            "connection_details": {
                "context": self._config_manager.get_current_context(),
                "config_type": self._get_state_value("kubernetes_config_type"),
                "connected": True,
            },
        }

        # Add namespace information if available
        if namespaces_result.get("success", False):
            inspection_data["namespaces"] = namespaces_result.get("data", {})

        # Add node information if available
        if nodes_result.get("success", False):
            inspection_data["nodes"] = nodes_result.get("data", {})

        return inspection_data

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on Kubernetes cluster."""
        return await self._execute_operation(
            "kubernetes health check", self._health_check_operation
        )

    async def _health_check_operation(self) -> Dict[str, Any]:
        """Execute Kubernetes cluster health check operation."""
        if not self._get_state_value("kubernetes_connected", False):
            raise RuntimeError("Not connected to any Kubernetes cluster")

        # Test connection
        connection_result = await self._client.test_connection()
        if not connection_result.get("success", False):
            # Update state to reflect disconnection
            self._update_state(kubernetes_connected=False)
            raise RuntimeError("Connection test failed - cluster may be unreachable")

        # Get nodes and check their readiness
        nodes_result = await self._client.get_nodes()
        namespaces_result = await self._client.list_namespaces()

        health_data = {
            "connection": "healthy",
            "context": self._config_manager.get_current_context(),
            "server_version": connection_result.get("data", {}).get("server_version"),
        }

        # Add node health if available
        if nodes_result.get("success", False):
            nodes_data = nodes_result.get("data", {})
            nodes = nodes_data.get("nodes", [])
            ready_nodes = sum(1 for node in nodes if node.get("status") == "True")
            total_nodes = len(nodes)

            health_data["nodes"] = {
                "total": total_nodes,
                "ready": ready_nodes,
                "healthy": ready_nodes == total_nodes and total_nodes > 0,
            }

        # Add namespace health if available
        if namespaces_result.get("success", False):
            namespaces_data = namespaces_result.get("data", {})
            active_namespaces = sum(
                1
                for ns in namespaces_data.get("namespaces", [])
                if ns.get("status") == "Active"
            )

            health_data["namespaces"] = {
                "total": namespaces_data.get("total_count", 0),
                "active": active_namespaces,
            }

        return health_data

    # Additional utility methods
    async def list_contexts(self) -> Dict[str, Any]:
        """List available Kubernetes contexts."""
        return await self._execute_operation(
            "list kubernetes contexts", self._config_manager.list_contexts
        )

    async def get_namespaces(self) -> Dict[str, Any]:
        """Get list of namespaces."""
        self._ensure_connected()
        return await self._client.list_namespaces()

    async def get_nodes(self) -> Dict[str, Any]:
        """Get cluster nodes."""
        self._ensure_connected()
        return await self._client.get_nodes()

    async def get_pods(self, namespace: str = "default") -> Dict[str, Any]:
        """Get pods in a namespace."""
        self._ensure_connected()
        return await self._client.get_pods(namespace)

    async def validate_config(self) -> Dict[str, Any]:
        """Validate Kubernetes configuration."""
        return await self._execute_operation(
            "validate kubernetes config", self._config_manager.validate_config
        )

    # Component access for advanced usage
    def get_config_manager(self) -> KubernetesConfigManager:
        """Get the configuration manager component."""
        return self._config_manager

    def get_client(self) -> KubernetesApiClient:
        """Get the API client component."""
        return self._client
