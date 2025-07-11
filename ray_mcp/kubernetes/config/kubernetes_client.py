"""Kubernetes API client management for Ray MCP."""

import asyncio
from typing import Any, Dict, List, Optional

from ...foundation.import_utils import get_kubernetes_imports, get_logging_utils


class KubernetesClient:
    """Manages Kubernetes API client operations and connections."""

    def __init__(self, config_manager=None):
        # Import logging utilities
        logging_utils = get_logging_utils()
        self._LoggingUtility = logging_utils["LoggingUtility"]
        self._ResponseFormatter = logging_utils["ResponseFormatter"]

        # Import Kubernetes modules
        k8s_imports = get_kubernetes_imports()
        self._client = k8s_imports["client"]
        self._config = k8s_imports["config"]
        self._KUBERNETES_AVAILABLE = k8s_imports["KUBERNETES_AVAILABLE"]
        self._ApiException = k8s_imports["ApiException"]
        self._ConfigException = k8s_imports["ConfigException"]

        self._config_manager = config_manager
        self._api_client = None
        self._v1_client = None
        self._apps_v1_client = None

    def set_kubernetes_config(self, kubernetes_config: Any) -> None:
        """Set the Kubernetes configuration to use for API calls."""
        self._kubernetes_config = kubernetes_config
        # Reset the clients so they get recreated with the new config
        self._core_v1_api = None
        self._apps_v1_api = None
        self._version_api = None

    def _ensure_clients(self) -> None:
        """Ensure API clients are initialized."""
        if not self._KUBERNETES_AVAILABLE:
            raise RuntimeError("Kubernetes client library is not available")

        if self._core_v1_api is None:
            if self._kubernetes_config:
                # Use the pre-configured Kubernetes client
                api_client = self._client.ApiClient(self._kubernetes_config)
                self._core_v1_api = self._client.CoreV1Api(api_client)
            else:
                self._core_v1_api = self._client.CoreV1Api()

        if self._apps_v1_api is None:
            if self._kubernetes_config:
                # Use the pre-configured Kubernetes client
                api_client = self._client.ApiClient(self._kubernetes_config)
                self._apps_v1_api = self._client.AppsV1Api(api_client)
            else:
                self._apps_v1_api = self._client.AppsV1Api()

        if self._version_api is None:
            if self._kubernetes_config:
                # Use the pre-configured Kubernetes client
                api_client = self._client.ApiClient(self._kubernetes_config)
                self._version_api = self._client.VersionApi(api_client)
            else:
                self._version_api = self._client.VersionApi()

    async def test_connection(self) -> Dict[str, Any]:
        """Test connection to Kubernetes cluster."""
        if not self._KUBERNETES_AVAILABLE:
            return self._ResponseFormatter.format_error_response(
                "test kubernetes connection",
                Exception(
                    "Kubernetes client library is not available. Please install kubernetes package: pip install kubernetes"
                ),
            )

        try:
            # Use asyncio.to_thread to run the synchronous API call in a thread
            self._ensure_clients()
            version_info = await asyncio.to_thread(self._version_api.get_code)

            # Safe access to git_version attribute
            git_version = getattr(version_info, "git_version", "unknown")
            return self._ResponseFormatter.format_success_response(
                connected=True,
                server_version=git_version,
                context=self._config_manager.get_current_context(),
            )
        except self._ApiException as e:
            status = getattr(e, "status", "unknown")
            reason = getattr(e, "reason", "unknown")
            return self._ResponseFormatter.format_error_response(
                "test kubernetes connection",
                Exception(f"API Error: {status} - {reason}"),
            )
        except Exception as e:
            return self._ResponseFormatter.format_error_response(
                "test kubernetes connection", e
            )

    async def get_cluster_info(self) -> Dict[str, Any]:
        """Get comprehensive cluster information."""
        if not self._KUBERNETES_AVAILABLE:
            return self._ResponseFormatter.format_error_response(
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

            # Safe access to git_version attribute
            git_version = getattr(version_info, "git_version", "unknown")
            return self._ResponseFormatter.format_success_response(
                server_version=git_version,
                context=self._config_manager.get_current_context(),
                total_nodes=len(nodes.items),
                ready_nodes=ready_nodes,
                total_namespaces=len(namespaces.items),
                total_cpu_cores=round(total_cpu, 2),
                total_memory_gb=round(total_memory, 2),
            )
        except self._ApiException as e:
            status = getattr(e, "status", "unknown")
            reason = getattr(e, "reason", "unknown")
            return self._ResponseFormatter.format_error_response(
                "get kubernetes cluster info",
                Exception(f"API Error: {status} - {reason}"),
            )
        except Exception as e:
            return self._ResponseFormatter.format_error_response(
                "get kubernetes cluster info", e
            )

    async def list_namespaces(self) -> Dict[str, Any]:
        """List available namespaces."""
        if not self._KUBERNETES_AVAILABLE:
            return self._ResponseFormatter.format_error_response(
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

            return self._ResponseFormatter.format_success_response(
                namespaces=namespace_list, total_count=len(namespace_list)
            )
        except self._ApiException as e:
            status = getattr(e, "status", "unknown")
            reason = getattr(e, "reason", "unknown")
            return self._ResponseFormatter.format_error_response(
                "list kubernetes namespaces",
                Exception(f"API Error: {status} - {reason}"),
            )
        except Exception as e:
            return self._ResponseFormatter.format_error_response(
                "list kubernetes namespaces", e
            )

    async def get_nodes(self) -> Dict[str, Any]:
        """Get information about cluster nodes."""
        if not self._KUBERNETES_AVAILABLE:
            return self._ResponseFormatter.format_error_response(
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

            return self._ResponseFormatter.format_success_response(
                nodes=node_list, total_count=len(node_list)
            )
        except self._ApiException as e:
            status = getattr(e, "status", "unknown")
            reason = getattr(e, "reason", "unknown")
            return self._ResponseFormatter.format_error_response(
                "get kubernetes nodes", Exception(f"API Error: {status} - {reason}")
            )
        except Exception as e:
            return self._ResponseFormatter.format_error_response(
                "get kubernetes nodes", e
            )

    async def list_pods(
        self, namespace: str = "default", label_selector: Optional[str] = None
    ) -> Dict[str, Any]:
        """List pods in a namespace."""
        if not self._KUBERNETES_AVAILABLE:
            return self._ResponseFormatter.format_error_response(
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

            return self._ResponseFormatter.format_success_response(
                pods=pod_list, total_count=len(pod_list), namespace=namespace
            )
        except self._ApiException as e:
            status = getattr(e, "status", "unknown")
            reason = getattr(e, "reason", "unknown")
            return self._ResponseFormatter.format_error_response(
                "list kubernetes pods", Exception(f"API Error: {status} - {reason}")
            )
        except Exception as e:
            return self._ResponseFormatter.format_error_response(
                "list kubernetes pods", e
            )

    async def get_pods(self, namespace: str = "default") -> Dict[str, Any]:
        """Get pods in a namespace (interface method)."""
        # This method is required by the KubernetesClient interface
        # Delegate to the existing list_pods method
        return await self.list_pods(namespace=namespace)

    async def get_pod_logs(
        self,
        pod_name: Optional[str] = None,
        namespace: str = "default",
        container: Optional[str] = None,
        label_selector: Optional[str] = None,
        lines: Optional[int] = None,
        since_seconds: Optional[int] = None,
        follow: bool = False,
        timestamps: bool = False,
    ) -> Dict[str, Any]:
        """Get logs from a pod or pods matching a label selector."""
        if not self._KUBERNETES_AVAILABLE:
            return self._ResponseFormatter.format_error_response(
                "get pod logs",
                Exception("Kubernetes client library is not available"),
            )

        try:
            self._ensure_clients()

            # If pod_name is specified, get logs from that specific pod
            if pod_name:
                log_response = await asyncio.to_thread(
                    self._core_v1_api.read_namespaced_pod_log,
                    name=pod_name,
                    namespace=namespace,
                    container=container,
                    tail_lines=lines,
                    since_seconds=since_seconds,
                    follow=follow,
                    timestamps=timestamps,
                )

                return self._ResponseFormatter.format_success_response(
                    logs=log_response,
                    pod_name=pod_name,
                    namespace=namespace,
                    container=container,
                )

            # If label_selector is specified, get logs from all matching pods
            elif label_selector:
                pods_result = await self.list_pods(
                    namespace=namespace, label_selector=label_selector
                )

                if pods_result.get("status") != "success":
                    return pods_result

                pods = pods_result.get("pods", [])
                if not pods:
                    return self._ResponseFormatter.format_success_response(
                        logs="No pods found matching the label selector",
                        pod_count=0,
                        namespace=namespace,
                        label_selector=label_selector,
                    )

                # Collect logs from all matching pods
                all_logs = []
                for pod in pods:
                    pod_name = pod.get("name")
                    try:
                        log_response = await asyncio.to_thread(
                            self._core_v1_api.read_namespaced_pod_log,
                            name=pod_name,
                            namespace=namespace,
                            container=container,
                            tail_lines=lines,
                            since_seconds=since_seconds,
                            follow=follow,
                            timestamps=timestamps,
                        )

                        # Add pod header to distinguish logs from different pods
                        pod_logs = f"=== Pod: {pod_name} ===\n{log_response}\n"
                        all_logs.append(pod_logs)

                    except self._ApiException as e:
                        # Continue with other pods if one fails
                        error_msg = f"=== Pod: {pod_name} - Error: {getattr(e, 'reason', 'unknown')} ===\n"
                        all_logs.append(error_msg)

                combined_logs = "\n".join(all_logs)

                return self._ResponseFormatter.format_success_response(
                    logs=combined_logs,
                    pod_count=len(pods),
                    namespace=namespace,
                    label_selector=label_selector,
                )

            else:
                return self._ResponseFormatter.format_error_response(
                    "get pod logs",
                    Exception("Either pod_name or label_selector must be specified"),
                )

        except self._ApiException as e:
            status = getattr(e, "status", "unknown")
            reason = getattr(e, "reason", "unknown")
            return self._ResponseFormatter.format_error_response(
                "get pod logs", Exception(f"API Error: {status} - {reason}")
            )
        except Exception as e:
            return self._ResponseFormatter.format_error_response("get pod logs", e)

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
