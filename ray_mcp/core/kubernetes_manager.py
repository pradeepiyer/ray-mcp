"""Kubernetes cluster management following Ray MCP patterns."""

from typing import Any, Dict, Optional

try:
    from ..logging_utils import LoggingUtility, ResponseFormatter
except ImportError:
    # Fallback for direct execution
    import os
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from logging_utils import LoggingUtility, ResponseFormatter

from .interfaces import KubernetesComponent, KubernetesManager, StateManager
from .kubernetes_client import KubernetesApiClient
from .kubernetes_config import KubernetesConfigManager

# Export KUBERNETES_AVAILABLE for testing
try:
    from kubernetes import client, config
    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False


class KubernetesClusterManager(KubernetesComponent, KubernetesManager):
    """Manages Kubernetes cluster operations with clean separation of concerns."""

    def __init__(
        self,
        state_manager: StateManager,
        config_manager: Optional[KubernetesConfigManager] = None,
        client: Optional[KubernetesApiClient] = None,
    ):
        super().__init__(state_manager)
        self._config_manager = config_manager or KubernetesConfigManager()
        self._client = client or KubernetesApiClient(self._config_manager)
        self._response_formatter = ResponseFormatter()

    @ResponseFormatter.handle_exceptions("connect to kubernetes cluster")
    async def connect_cluster(self, config_file: Optional[str] = None, context: Optional[str] = None) -> Dict[str, Any]:
        """Connect to Kubernetes cluster."""
        # First load the configuration
        load_result = self._config_manager.load_config(config_file, context)
        if not load_result.get("success", False):
            return load_result

        # Test the connection
        connection_result = await self._client.test_connection()
        if not connection_result.get("success", False):
            return connection_result

        # Update state to reflect successful connection
        self.state_manager.update_state(
            kubernetes_connected=True,
            kubernetes_context=self._config_manager.get_current_context(),
            kubernetes_config_type=load_result.get("data", {}).get("config_type"),
            kubernetes_server_version=connection_result.get("data", {}).get("server_version")
        )

        return self._response_formatter.format_success_response(
            connected=True,
            context=self._config_manager.get_current_context(),
            config_type=load_result.get("data", {}).get("config_type"),
            server_version=connection_result.get("data", {}).get("server_version")
        )

    @ResponseFormatter.handle_exceptions("disconnect from kubernetes cluster")
    async def disconnect_cluster(self) -> Dict[str, Any]:
        """Disconnect from Kubernetes cluster."""
        # Reset Kubernetes-related state
        self.state_manager.update_state(
            kubernetes_connected=False,
            kubernetes_context=None,
            kubernetes_config_type=None,
            kubernetes_server_version=None
        )

        return self._response_formatter.format_success_response(
            disconnected=True
        )

    @ResponseFormatter.handle_exceptions("inspect kubernetes cluster")
    async def inspect_cluster(self) -> Dict[str, Any]:
        """Inspect Kubernetes cluster."""
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
                "config_type": self.state_manager.get_state().get("kubernetes_config_type"),
                "connected": True
            }
        }

        # Add namespace information if available
        if namespaces_result.get("success", False):
            inspection_data["namespaces"] = namespaces_result.get("data", {})

        # Add node information if available
        if nodes_result.get("success", False):
            inspection_data["nodes"] = nodes_result.get("data", {})

        return self._response_formatter.format_success_response(
            **inspection_data
        )

    @ResponseFormatter.handle_exceptions("kubernetes health check")
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on Kubernetes cluster."""
        state = self.state_manager.get_state()
        
        if not state.get("kubernetes_connected", False):
            return self._response_formatter.format_error_response(
                "kubernetes health check",
                Exception("Not connected to any Kubernetes cluster")
            )

        # Test connection
        connection_result = await self._client.test_connection()
        if not connection_result.get("success", False):
            # Update state to reflect disconnection
            self.state_manager.update_state(kubernetes_connected=False)
            return self._response_formatter.format_error_response(
                "kubernetes health check",
                Exception("Connection test failed - cluster may be unreachable")
            )

        # Get basic cluster health indicators
        try:
            # Get nodes and check their readiness
            nodes_result = await self._client.get_nodes()
            namespaces_result = await self._client.list_namespaces()
            
            health_data = {
                "connection": "healthy",
                "context": self._config_manager.get_current_context(),
                "server_version": connection_result.get("data", {}).get("server_version")
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
                    "healthy": ready_nodes == total_nodes and total_nodes > 0
                }

            # Add namespace health if available
            if namespaces_result.get("success", False):
                namespaces_data = namespaces_result.get("data", {})
                active_namespaces = sum(1 for ns in namespaces_data.get("namespaces", []) if ns.get("status") == "Active")
                
                health_data["namespaces"] = {
                    "total": namespaces_data.get("total_count", 0),
                    "active": active_namespaces
                }

            return self._response_formatter.format_success_response(
                **health_data
            )

        except Exception as e:
            return self._response_formatter.format_error_response(
                "kubernetes health check",
                e
            )

    # Additional utility methods
    async def list_contexts(self) -> Dict[str, Any]:
        """List available Kubernetes contexts."""
        try:
            return self._config_manager.list_contexts()
        except Exception as e:
            return self._response_formatter.format_error_response(
                "list kubernetes contexts",
                e
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
        try:
            return self._config_manager.validate_config()
        except Exception as e:
            return self._response_formatter.format_error_response(
                "validate kubernetes config",
                e
            )

    # Component access for advanced usage
    def get_config_manager(self) -> KubernetesConfigManager:
        """Get the configuration manager component."""
        return self._config_manager

    def get_client(self) -> KubernetesApiClient:
        """Get the API client component."""
        return self._client 