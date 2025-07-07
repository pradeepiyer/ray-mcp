"""Kubernetes API client for direct server communication."""

import asyncio
from typing import Any, Dict, List, Optional

try:
    from ..logging_utils import LoggingUtility, ResponseFormatter
except ImportError:
    # Fallback for direct execution
    import os
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from logging_utils import LoggingUtility, ResponseFormatter

from .interfaces import KubernetesClient
from .kubernetes_config import KubernetesConfigManager

# Import kubernetes modules with error handling
try:
    from kubernetes import client
    from kubernetes.client.rest import ApiException

    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False
    client = None
    ApiException = Exception


class KubernetesApiClient(KubernetesClient):
    """Kubernetes API client with comprehensive cluster interaction capabilities."""

    def __init__(self, config_manager: Optional[KubernetesConfigManager] = None):
        self._config_manager = config_manager or KubernetesConfigManager()
        self._response_formatter = ResponseFormatter()
        self._core_v1_api = None
        self._apps_v1_api = None
        self._version_api = None

    def _ensure_clients(self) -> None:
        """Ensure API clients are initialized."""
        if not KUBERNETES_AVAILABLE:
            raise RuntimeError("Kubernetes client library is not available")

        if self._core_v1_api is None:
            self._core_v1_api = client.CoreV1Api()
        if self._apps_v1_api is None:
            self._apps_v1_api = client.AppsV1Api()
        if self._version_api is None:
            self._version_api = client.VersionApi()

    @ResponseFormatter.handle_exceptions("test kubernetes connection")
    async def test_connection(self) -> Dict[str, Any]:
        """Test connection to Kubernetes cluster."""
        if not KUBERNETES_AVAILABLE:
            return self._response_formatter.format_error_response(
                "test kubernetes connection",
                Exception(
                    "Kubernetes client library is not available. Please install kubernetes package: pip install kubernetes"
                ),
            )

        try:
            # Use asyncio.to_thread to run the synchronous API call in a thread
            self._ensure_clients()
            version_info = await asyncio.to_thread(self._version_api.get_code)

            return self._response_formatter.format_success_response(
                connected=True,
                server_version=version_info.git_version,
                context=self._config_manager.get_current_context(),
            )
        except ApiException as e:
            return self._response_formatter.format_error_response(
                "test kubernetes connection",
                Exception(f"API Error: {e.status} - {e.reason}"),
            )
        except Exception as e:
            return self._response_formatter.format_error_response(
                "test kubernetes connection", e
            )

    @ResponseFormatter.handle_exceptions("get kubernetes cluster info")
    async def get_cluster_info(self) -> Dict[str, Any]:
        """Get comprehensive cluster information."""
        if not KUBERNETES_AVAILABLE:
            return self._response_formatter.format_error_response(
                "get kubernetes cluster info",
                Exception("Kubernetes client library is not available"),
            )

        try:
            self._ensure_clients()

            # Get version information
            version_info = await asyncio.to_thread(self._version_api.get_code)

            # Get cluster nodes
            nodes = await asyncio.to_thread(self._core_v1_api.list_node)

            # Get namespaces
            namespaces = await asyncio.to_thread(self._core_v1_api.list_namespace)

            # Calculate cluster resources
            total_cpu = 0
            total_memory = 0
            ready_nodes = 0

            for node in nodes.items:
                if node.status.allocatable:
                    cpu = node.status.allocatable.get("cpu", "0")
                    memory = node.status.allocatable.get("memory", "0")

                    # Parse CPU (can be in millicores or cores)
                    if cpu.endswith("m"):
                        total_cpu += int(cpu[:-1]) / 1000
                    else:
                        total_cpu += int(cpu)

                    # Parse memory (convert from Ki to GB)
                    if memory.endswith("Ki"):
                        total_memory += int(memory[:-2]) / 1024 / 1024

                # Check if node is ready
                for condition in node.status.conditions:
                    if condition.type == "Ready" and condition.status == "True":
                        ready_nodes += 1
                        break

            return self._response_formatter.format_success_response(
                server_version=version_info.git_version,
                context=self._config_manager.get_current_context(),
                total_nodes=len(nodes.items),
                ready_nodes=ready_nodes,
                total_namespaces=len(namespaces.items),
                total_cpu_cores=round(total_cpu, 2),
                total_memory_gb=round(total_memory, 2),
            )
        except ApiException as e:
            return self._response_formatter.format_error_response(
                "get kubernetes cluster info",
                Exception(f"API Error: {e.status} - {e.reason}"),
            )
        except Exception as e:
            return self._response_formatter.format_error_response(
                "get kubernetes cluster info", e
            )

    @ResponseFormatter.handle_exceptions("list kubernetes namespaces")
    async def list_namespaces(self) -> Dict[str, Any]:
        """List available namespaces."""
        if not KUBERNETES_AVAILABLE:
            return self._response_formatter.format_error_response(
                "list kubernetes namespaces",
                Exception(
                    "Kubernetes client library is not available. Please install kubernetes package: pip install kubernetes"
                ),
            )

        try:
            self._ensure_clients()
            namespaces = await asyncio.to_thread(self._core_v1_api.list_namespace)

            namespace_list = []
            for ns in namespaces.items:
                namespace_info = {
                    "name": ns.metadata.name,
                    "status": ns.status.phase,
                    "age": (
                        ns.metadata.creation_timestamp.isoformat()
                        if ns.metadata.creation_timestamp
                        else None
                    ),
                    "labels": ns.metadata.labels or {},
                }
                namespace_list.append(namespace_info)

            return self._response_formatter.format_success_response(
                namespaces=namespace_list, total_count=len(namespace_list)
            )
        except ApiException as e:
            return self._response_formatter.format_error_response(
                "list kubernetes namespaces",
                Exception(f"API Error: {e.status} - {e.reason}"),
            )
        except Exception as e:
            return self._response_formatter.format_error_response(
                "list kubernetes namespaces", e
            )

    @ResponseFormatter.handle_exceptions("get kubernetes nodes")
    async def get_nodes(self) -> Dict[str, Any]:
        """Get information about cluster nodes."""
        if not KUBERNETES_AVAILABLE:
            return self._response_formatter.format_error_response(
                "get kubernetes nodes",
                Exception(
                    "Kubernetes client library is not available. Please install kubernetes package: pip install kubernetes"
                ),
            )

        try:
            self._ensure_clients()
            nodes = await asyncio.to_thread(self._core_v1_api.list_node)

            node_list = []
            for node in nodes.items:
                node_info = {
                    "name": node.metadata.name,
                    "status": (
                        "Ready"
                        if any(
                            condition.type == "Ready" and condition.status == "True"
                            for condition in node.status.conditions
                        )
                        else "NotReady"
                    ),
                    "age": (
                        node.metadata.creation_timestamp.isoformat()
                        if node.metadata.creation_timestamp
                        else None
                    ),
                    "version": node.status.node_info.kubelet_version,
                    "internal_ip": next(
                        (
                            address.address
                            for address in node.status.addresses
                            if address.type == "InternalIP"
                        ),
                        None,
                    ),
                    "external_ip": next(
                        (
                            address.address
                            for address in node.status.addresses
                            if address.type == "ExternalIP"
                        ),
                        None,
                    ),
                    "labels": node.metadata.labels or {},
                }
                node_list.append(node_info)

            return self._response_formatter.format_success_response(
                nodes=node_list, total_count=len(node_list)
            )
        except ApiException as e:
            return self._response_formatter.format_error_response(
                "get kubernetes nodes", Exception(f"API Error: {e.status} - {e.reason}")
            )
        except Exception as e:
            return self._response_formatter.format_error_response(
                "get kubernetes nodes", e
            )

    @ResponseFormatter.handle_exceptions("list kubernetes pods")
    async def list_pods(
        self, namespace: str = "default", label_selector: Optional[str] = None
    ) -> Dict[str, Any]:
        """List pods in a namespace."""
        if not KUBERNETES_AVAILABLE:
            return self._response_formatter.format_error_response(
                "list kubernetes pods",
                Exception(
                    "Kubernetes client library is not available. Please install kubernetes package: pip install kubernetes"
                ),
            )

        try:
            self._ensure_clients()
            pods = await asyncio.to_thread(
                self._core_v1_api.list_namespaced_pod,
                namespace=namespace,
                label_selector=label_selector,
            )

            pod_list = []
            for pod in pods.items:
                pod_info = {
                    "name": pod.metadata.name,
                    "namespace": pod.metadata.namespace,
                    "status": pod.status.phase,
                    "ready": (
                        f"{sum(1 for c in pod.status.container_statuses if c.ready)}/{len(pod.status.container_statuses)}"
                        if pod.status.container_statuses
                        else "0/0"
                    ),
                    "restarts": (
                        sum(c.restart_count for c in pod.status.container_statuses)
                        if pod.status.container_statuses
                        else 0
                    ),
                    "age": (
                        pod.metadata.creation_timestamp.isoformat()
                        if pod.metadata.creation_timestamp
                        else None
                    ),
                    "node": pod.spec.node_name,
                    "labels": pod.metadata.labels or {},
                }
                pod_list.append(pod_info)

            return self._response_formatter.format_success_response(
                pods=pod_list, total_count=len(pod_list), namespace=namespace
            )
        except ApiException as e:
            return self._response_formatter.format_error_response(
                "list kubernetes pods", Exception(f"API Error: {e.status} - {e.reason}")
            )
        except Exception as e:
            return self._response_formatter.format_error_response(
                "list kubernetes pods", e
            )

    def _ensure_clients(self) -> None:
        """Ensure API clients are initialized."""
        if not KUBERNETES_AVAILABLE:
            raise RuntimeError("Kubernetes client library is not available")

        if self._core_v1_api is None:
            self._core_v1_api = client.CoreV1Api()
        if self._apps_v1_api is None:
            self._apps_v1_api = client.AppsV1Api()
        if self._version_api is None:
            self._version_api = client.VersionApi()

    def _extract_node_roles_from_labels(self, labels: dict) -> str:
        """Extract node roles from labels."""
        roles = []
        for key in labels:
            if key.startswith("node-role.kubernetes.io/"):
                role = key.replace("node-role.kubernetes.io/", "")
                if role:
                    roles.append(role)
        return ",".join(roles) if roles else "<none>"

    def _extract_internal_ip(self, addresses: list) -> str:
        """Extract internal IP from node addresses."""
        for addr in addresses:
            if addr.get("type") == "InternalIP":
                return addr.get("address", "unknown")
        return "unknown"

    def _get_node_roles(self, node) -> str:
        """Extract node roles from Kubernetes node object."""
        roles = []
        if node.metadata.labels:
            for key in node.metadata.labels:
                if key.startswith("node-role.kubernetes.io/"):
                    role = key.replace("node-role.kubernetes.io/", "")
                    if role:
                        roles.append(role)
        return ",".join(roles) if roles else "<none>"

    def _get_node_internal_ip(self, node) -> str:
        """Extract internal IP from Kubernetes node object."""
        if node.status.addresses:
            for addr in node.status.addresses:
                if addr.type == "InternalIP":
                    return addr.address
        return "unknown"

    def _extract_container_state(self, state: dict) -> str:
        """Extract container state from state dict."""
        if "running" in state:
            return "running"
        elif "waiting" in state:
            return f"waiting ({state['waiting'].get('reason', 'unknown')})"
        elif "terminated" in state:
            return f"terminated ({state['terminated'].get('reason', 'unknown')})"
        else:
            return "unknown"

    def _get_container_state(self, state) -> str:
        """Get container state from Kubernetes container state object."""
        if state.running:
            return "running"
        elif state.waiting:
            return f"waiting ({state.waiting.reason})"
        elif state.terminated:
            return f"terminated ({state.terminated.reason})"
        else:
            return "unknown"

    def _count_ready_containers(self, pod) -> int:
        """Count ready containers in a pod."""
        if not pod.status.container_statuses:
            return 0
        return sum(1 for c in pod.status.container_statuses if c.ready)

    def _count_total_restarts(self, pod) -> int:
        """Count total restarts across all containers in a pod."""
        if not pod.status.container_statuses:
            return 0
        return sum(c.restart_count for c in pod.status.container_statuses)

    def get_current_context(self) -> Optional[str]:
        """Get current kubeconfig context."""
        return self._config_manager.get_current_context()

    def _get_pod_ready_status(self, pod) -> str:
        """Get pod ready status as string."""
        if not pod.status.container_statuses:
            return "0/0"
        ready_count = sum(1 for c in pod.status.container_statuses if c.ready)
        total_count = len(pod.status.container_statuses)
        return f"{ready_count}/{total_count}"
