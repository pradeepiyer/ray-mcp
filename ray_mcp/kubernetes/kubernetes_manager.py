"""Pure prompt-driven Kubernetes cluster management for Ray MCP."""

import asyncio
import os
from typing import Any, Optional

from ..config import config
from ..foundation.logging_utils import error_response, success_response
from ..foundation.resource_manager import ResourceManager
from ..llm_parser import get_parser


class KubernetesManager(ResourceManager):
    """Pure prompt-driven Kubernetes cluster management - no traditional APIs."""

    def __init__(self):
        super().__init__(
            enable_ray=False,
            enable_kubernetes=True,
            enable_cloud=False,
        )

    async def execute_request(self, prompt: str) -> dict[str, Any]:
        """Execute kubernetes operations using natural language prompts.

        Examples:
            - "connect to kubernetes cluster with context my-cluster"
            - "list all namespaces in cluster"
            - "get cluster health status"
            - "inspect current kubernetes cluster"
        """
        try:
            action = await get_parser().parse_kubernetes_action(prompt)
            operation = action["operation"]

            if operation == "connect":
                context = action.get("context")
                config_file = action.get("config_file")
                return await self._connect_cluster(config_file, context)
            elif operation == "disconnect":
                return await self._disconnect_cluster()
            elif operation == "inspect":
                return await self._inspect_cluster()
            elif operation == "health_check":
                return await self._check_cluster_health()
            elif operation == "list_namespaces":
                return await self._list_namespaces()
            elif operation == "list_contexts":
                return await self._list_contexts()
            else:
                return error_response(f"Unknown operation: {operation}")

        except ValueError as e:
            return error_response(f"Could not parse request: {str(e)}")
        except Exception as e:
            return self._handle_error("execute_request", e)

    # =================================================================
    # INTERNAL IMPLEMENTATION: All methods are now private
    # =================================================================

    async def _connect_cluster(
        self, config_file: Optional[str] = None, context: Optional[str] = None
    ) -> dict[str, Any]:
        """Connect to Kubernetes cluster using unified configuration."""
        try:
            from kubernetes import config as k8s_config

            # Load configuration
            config_file_path = config_file or os.getenv("KUBECONFIG")
            if config_file_path:
                await asyncio.to_thread(
                    k8s_config.load_kube_config,
                    config_file=config_file_path,
                    context=context,
                )
            else:
                await asyncio.to_thread(k8s_config.load_kube_config, context=context)

            # Get current context
            contexts, active_context = await asyncio.to_thread(
                k8s_config.list_kube_config_contexts
            )
            current_context = active_context["name"] if active_context else context

            # Simple state tracking
            self._last_connected_context = current_context

            return success_response(
                message="Connected to Kubernetes cluster successfully",
                context=current_context,
            )
        except Exception as e:
            return self._handle_error("connect to kubernetes", e)

    async def _disconnect_cluster(self) -> dict[str, Any]:
        """Disconnect from Kubernetes cluster."""
        try:
            # Simple state tracking
            self._last_connected_context = None

            return success_response(
                message="Disconnected from Kubernetes cluster successfully"
            )
        except Exception as e:
            return self._handle_error("disconnect from kubernetes", e)

    async def _inspect_cluster(self) -> dict[str, Any]:
        """Get basic cluster information."""
        try:
            self._ensure_kubernetes_connected()

            from kubernetes import client, config as k8s_config

            # Get cluster info
            contexts, active_context = await asyncio.to_thread(
                k8s_config.list_kube_config_contexts
            )
            current_context = active_context["name"] if active_context else "unknown"

            v1 = client.CoreV1Api()

            # Get basic cluster info
            cluster_info = {
                "context": current_context,
                "connected": True,
            }

            # Set server version to unknown for now to avoid type issues
            # Can be enhanced later with proper type annotations
            cluster_info["server_version"] = "unknown"

            return success_response(**cluster_info)
        except Exception as e:
            return self._handle_error("inspect kubernetes cluster", e)

    async def _check_cluster_health(self) -> dict[str, Any]:
        """Check cluster health status."""
        try:
            self._ensure_kubernetes_connected()

            from kubernetes import client

            v1 = client.CoreV1Api()

            # Basic health check - try to list nodes
            nodes = await asyncio.to_thread(v1.list_node)
            node_count = len(nodes.items)

            # Get ready nodes
            ready_nodes = [
                node
                for node in nodes.items
                if any(
                    condition.type == "Ready" and condition.status == "True"
                    for condition in node.status.conditions
                )
            ]

            health_status = {
                "healthy": len(ready_nodes) == node_count,
                "total_nodes": node_count,
                "ready_nodes": len(ready_nodes),
            }

            return success_response(**health_status)
        except Exception as e:
            return self._handle_error("check cluster health", e)

    async def _list_namespaces(self) -> dict[str, Any]:
        """List all namespaces in the cluster."""
        try:
            self._ensure_kubernetes_connected()

            from kubernetes import client

            v1 = client.CoreV1Api()
            namespaces = await asyncio.to_thread(v1.list_namespace)

            namespace_list = [ns.metadata.name for ns in namespaces.items]

            return success_response(
                namespaces=namespace_list, count=len(namespace_list)
            )
        except Exception as e:
            return self._handle_error("list namespaces", e)

    async def _list_contexts(self) -> dict[str, Any]:
        """List available Kubernetes contexts."""
        try:
            from kubernetes import config as k8s_config

            contexts, active_context = await asyncio.to_thread(
                k8s_config.list_kube_config_contexts
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
            return self._handle_error("list contexts", e)

    def _ensure_kubernetes_connected(self) -> None:
        """Ensure Kubernetes is connected and ready."""
        self._ensure_kubernetes_available()

        # Try to connect to kubernetes
        if not self._is_kubernetes_ready():
            raise RuntimeError(
                "Kubernetes is not available or configured. Please check kubeconfig."
            )
