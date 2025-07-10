"""KubeRay cluster management implementation."""

import asyncio
from typing import Any, Dict, List, Optional

from ...foundation.base_managers import ResourceManager
from ...foundation.interfaces import KubeRayClusterManager, ManagedComponent
from ..crds.crd_operations import CRDOperationsClient
from ..crds.ray_cluster_crd import RayClusterCRDManager


class KubeRayClusterManagerImpl(
    ResourceManager, KubeRayClusterManager, ManagedComponent
):
    """Manages Ray cluster lifecycle using KubeRay Custom Resources."""

    def __init__(
        self,
        state_manager,
        crd_operations: Optional[CRDOperationsClient] = None,
        cluster_crd: Optional[RayClusterCRDManager] = None,
    ):
        # Initialize both parent classes
        ResourceManager.__init__(
            self,
            state_manager,
            enable_ray=True,
            enable_kubernetes=True,
            enable_cloud=False,
        )
        ManagedComponent.__init__(self, state_manager)

        self._crd_operations = crd_operations or CRDOperationsClient()
        self._cluster_crd = cluster_crd or RayClusterCRDManager()
        self._core_v1_api = None

    def _ensure_kubernetes_client(self) -> None:
        """Ensure Kubernetes core API client is initialized."""
        self._ensure_kubernetes_available()

        if self._core_v1_api is None:
            # Use the same configuration as CRD operations for consistency
            if (
                hasattr(self._crd_operations, "_api_client")
                and self._crd_operations._api_client
            ):
                self._core_v1_api = self._client.CoreV1Api(
                    self._crd_operations._api_client
                )
            else:
                self._core_v1_api = self._client.CoreV1Api()

    def set_kubernetes_config(self, kubernetes_config) -> None:
        """Set the Kubernetes configuration for API operations."""
        try:
            from ...foundation.logging_utils import LoggingUtility

            LoggingUtility.log_info(
                "kuberay_cluster_set_k8s_config",
                f"Setting Kubernetes config - config provided: {kubernetes_config is not None}, host: {getattr(kubernetes_config, 'host', 'N/A') if kubernetes_config else 'N/A'}",
            )
            self._crd_operations.set_kubernetes_config(kubernetes_config)
            # Reset core API client to use new configuration
            self._core_v1_api = None
            LoggingUtility.log_info(
                "kuberay_cluster_set_k8s_config",
                "Successfully set Kubernetes configuration on CRD operations client",
            )
        except Exception as e:
            # Log the error instead of silently ignoring it
            from ...foundation.logging_utils import LoggingUtility

            LoggingUtility.log_error(
                "kuberay_cluster_set_k8s_config",
                Exception(f"Failed to set Kubernetes configuration: {str(e)}"),
            )

    async def create_ray_cluster(
        self, cluster_spec: Dict[str, Any], namespace: str = "default"
    ) -> Dict[str, Any]:
        """Create a Ray cluster using KubeRay CRD."""
        return await self._execute_operation(
            "create ray cluster",
            self._create_ray_cluster_operation,
            cluster_spec,
            namespace,
        )

    async def _create_ray_cluster_operation(
        self, cluster_spec: Dict[str, Any], namespace: str = "default"
    ) -> Dict[str, Any]:
        """Execute Ray cluster creation operation."""
        # Validate cluster specification
        if not cluster_spec:
            raise ValueError("Cluster specification is required")

        head_node_spec = cluster_spec.get("head_node_spec")
        if not head_node_spec:
            raise ValueError("head_node_spec is required in cluster specification")

        # Generate cluster spec using CRD manager
        crd_result = self._cluster_crd.create_spec(
            head_node_spec,
            cluster_spec.get("worker_node_specs", []),
            cluster_spec.get("cluster_name"),
        )

        if crd_result.get("status") != "success":
            raise RuntimeError(
                f"Failed to create cluster specification: {crd_result.get('message')}"
            )

        cluster_name = crd_result["cluster_name"]
        ray_cluster_spec = crd_result["cluster_spec"]

        # Create the Ray cluster resource
        create_result = await self._crd_operations.create_resource(
            "raycluster", ray_cluster_spec, namespace
        )

        if create_result.get("status") != "success":
            raise RuntimeError(
                f"Failed to create Ray cluster: {create_result.get('message')}"
            )

        return {
            "cluster_name": cluster_name,
            "namespace": namespace,
            "cluster_spec": ray_cluster_spec,
            **create_result,
        }

    async def get_ray_cluster(
        self, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Get Ray cluster status."""
        # Use ManagedComponent validation method instead of ResourceManager's
        self._ensure_kuberay_ready()

        result = await self._crd_operations.get_resource(
            resource_type="raycluster", name=name, namespace=namespace
        )

        if result.get("status") == "success":
            resource = result.get("resource", {})
            status = resource.get("status", {})

            # Extract detailed status information
            cluster_status = {
                "name": name,
                "namespace": namespace,
                "phase": status.get("phase", "Unknown"),
                "state": status.get("state", "Unknown"),
                "ready_worker_replicas": status.get("readyWorkerReplicas", 0),
                "desired_worker_replicas": status.get("desiredWorkerReplicas", 0),
                "min_worker_replicas": status.get("minWorkerReplicas", 0),
                "max_worker_replicas": status.get("maxWorkerReplicas", 0),
                "head_pod_ip": status.get("head", {}).get("podIP"),
                "dashboard_url": self._get_dashboard_url(name, namespace),
                "service_ips": status.get("head", {}).get("serviceIP"),
                "creation_timestamp": resource.get("metadata", {}).get(
                    "creationTimestamp"
                ),
                "ray_version": resource.get("spec", {}).get("rayVersion"),
            }

            # Check if cluster is ready
            is_ready = status.get("state") == "ready" and status.get(
                "readyWorkerReplicas", 0
            ) >= status.get("minWorkerReplicas", 0)

            return self._ResponseFormatter.format_success_response(
                cluster=cluster_status, ready=is_ready, raw_resource=resource
            )
        else:
            return result

    async def list_ray_clusters(self, namespace: str = "default") -> Dict[str, Any]:
        """List Ray clusters."""
        # Use ManagedComponent validation method instead of ResourceManager's
        self._ensure_kuberay_ready()

        result = await self._crd_operations.list_resources(
            resource_type="raycluster", namespace=namespace
        )

        if result.get("status") == "success":
            clusters = []
            for resource_summary in result.get("resources", []):
                cluster_info = {
                    "name": resource_summary.get("name"),
                    "namespace": resource_summary.get("namespace"),
                    "phase": resource_summary.get("phase", "Unknown"),
                    "creation_timestamp": resource_summary.get("creation_timestamp"),
                    "labels": resource_summary.get("labels", {}),
                    "dashboard_url": self._get_dashboard_url(
                        resource_summary.get("name"), resource_summary.get("namespace")
                    ),
                }
                clusters.append(cluster_info)

            return self._ResponseFormatter.format_success_response(
                clusters=clusters, total_count=len(clusters), namespace=namespace
            )
        else:
            return result

    async def update_ray_cluster(
        self, name: str, cluster_spec: Dict[str, Any], namespace: str = "default"
    ) -> Dict[str, Any]:
        """Update Ray cluster configuration."""
        # Use ManagedComponent validation method instead of ResourceManager's
        self._ensure_kuberay_ready()

        # Get current cluster to understand current state
        current_result = await self.get_ray_cluster(name, namespace)
        if current_result.get("status") != "success":
            return current_result

        # Extract configuration from cluster_spec
        head_node_spec = cluster_spec.get("head_node_spec")
        worker_node_specs = cluster_spec.get("worker_node_specs")
        ray_version = cluster_spec.get("ray_version")
        enable_ingress = cluster_spec.get("enable_ingress")
        suspend = cluster_spec.get("suspend")

        # Create updated CRD specification
        crd_result = self._cluster_crd.create_spec(
            head_node_spec=head_node_spec or {},
            worker_node_specs=worker_node_specs or [],
            cluster_name=name,
            namespace=namespace,
            ray_version=ray_version or "2.47.0",
            enable_ingress=enable_ingress or False,
            suspend=suspend or False,
            **{
                k: v
                for k, v in cluster_spec.items()
                if k
                not in [
                    "head_node_spec",
                    "worker_node_specs",
                    "namespace",
                    "ray_version",
                    "enable_ingress",
                    "suspend",
                ]
            },
        )

        if crd_result.get("status") != "success":
            return crd_result

        ray_cluster_spec = crd_result["cluster_spec"]

        # Update the RayCluster resource
        update_result = await self._crd_operations.update_resource(
            resource_type="raycluster",
            name=name,
            resource_spec=ray_cluster_spec,
            namespace=namespace,
        )

        if update_result.get("status") == "success":
            self._update_cluster_state(name, namespace, "updating")

            return self._ResponseFormatter.format_success_response(
                cluster_name=name,
                namespace=namespace,
                cluster_status="updating",
                message=f"RayCluster '{name}' update initiated",
            )
        else:
            return update_result

    async def delete_ray_cluster(
        self, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Delete Ray cluster."""
        # Use ManagedComponent validation method instead of ResourceManager's
        self._ensure_kuberay_ready()

        result = await self._crd_operations.delete_resource(
            resource_type="raycluster", name=name, namespace=namespace
        )

        if result.get("status") == "success":
            # Update state to remove the cluster
            self._remove_cluster_state(name, namespace)

            return self._ResponseFormatter.format_success_response(
                cluster_name=name,
                namespace=namespace,
                deleted=True,
                deletion_timestamp=result.get("deletion_timestamp"),
                message=f"RayCluster '{name}' deletion initiated",
            )
        else:
            return result

    async def scale_ray_cluster(
        self, name: str, worker_replicas: int, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Scale Ray cluster workers."""
        # Use ManagedComponent validation method instead of ResourceManager's
        self._ensure_kuberay_ready()

        if worker_replicas < 0:
            return self._ResponseFormatter.format_error_response(
                "scale ray cluster", Exception("worker_replicas must be non-negative")
            )

        # Get current cluster configuration
        current_result = await self.get_ray_cluster(name, namespace)
        if current_result.get("status") != "success":
            return current_result

        current_resource = current_result.get("raw_resource", {})
        current_spec = current_resource.get("spec", {})

        # Update worker group replicas
        worker_groups = current_spec.get("workerGroupSpecs", [])
        if not worker_groups:
            return self._ResponseFormatter.format_error_response(
                "scale ray cluster", Exception("No worker groups found in cluster")
            )

        # Scale the first worker group (could be enhanced to scale specific groups)
        worker_groups[0]["replicas"] = worker_replicas
        worker_groups[0]["maxReplicas"] = max(
            worker_replicas * 2, worker_groups[0].get("maxReplicas", worker_replicas)
        )

        # Update the cluster
        update_spec = {"spec": current_spec}

        update_result = await self._crd_operations.update_resource(
            resource_type="raycluster",
            name=name,
            resource_spec=update_spec,
            namespace=namespace,
        )

        if update_result.get("status") == "success":
            return self._ResponseFormatter.format_success_response(
                cluster_name=name,
                namespace=namespace,
                worker_replicas=worker_replicas,
                cluster_status="scaling",
                message=f"RayCluster '{name}' scaling to {worker_replicas} worker replicas",
            )
        else:
            return update_result

    def _update_cluster_state(
        self, cluster_name: str, namespace: str, status: str
    ) -> None:
        """Update cluster state in state manager."""
        state = self.state_manager.get_state()
        kuberay_clusters = state.get("kuberay_clusters", {})

        kuberay_clusters[f"{namespace}/{cluster_name}"] = {
            "name": cluster_name,
            "namespace": namespace,
            "cluster_status": status,
            "dashboard_url": self._get_dashboard_url(cluster_name, namespace),
        }

        self.state_manager.update_state(kuberay_clusters=kuberay_clusters)

    def _remove_cluster_state(self, cluster_name: str, namespace: str) -> None:
        """Remove cluster state from state manager."""
        state = self.state_manager.get_state()
        kuberay_clusters = state.get("kuberay_clusters", {})

        cluster_key = f"{namespace}/{cluster_name}"
        if cluster_key in kuberay_clusters:
            del kuberay_clusters[cluster_key]
            self.state_manager.update_state(kuberay_clusters=kuberay_clusters)

    def _get_dashboard_url(self, cluster_name: str, namespace: str) -> str:
        """Get the dashboard URL for a Ray cluster."""
        # Return cluster-internal URL for now (external URL detection would require async)
        # External URL detection can be added later with proper async handling
        return f"http://{cluster_name}-head-svc.{namespace}.svc.cluster.local:8265"

    async def _get_external_dashboard_url(
        self, cluster_name: str, namespace: str
    ) -> Optional[str]:
        """Get external dashboard URL for LoadBalancer or NodePort services."""
        if not self._KUBERNETES_AVAILABLE:
            return None

        try:
            self._ensure_kubernetes_client()
            service_name = f"{cluster_name}-head-svc"

            # Get the service from Kubernetes API
            try:
                service = await asyncio.to_thread(
                    self._core_v1_api.read_namespaced_service,
                    name=service_name,
                    namespace=namespace,
                )
            except self._ApiException as e:
                status = getattr(e, "status", "unknown")
                if status == 404:
                    from ...foundation.logging_utils import LoggingUtility

                    LoggingUtility.log_debug(
                        "get_external_dashboard_url",
                        f"Service {service_name} not found in namespace {namespace}",
                    )
                    return None
                else:
                    raise

            # Safe access to service.spec.type
            service_type = getattr(getattr(service, "spec", None), "type", "Unknown")
            dashboard_port = 8265

            if service_type == "LoadBalancer":
                return self._get_loadbalancer_url(service, dashboard_port)
            elif service_type == "NodePort":
                return self._get_nodeport_url(service, dashboard_port, namespace)
            else:
                from ...foundation.logging_utils import LoggingUtility

                LoggingUtility.log_debug(
                    "get_external_dashboard_url",
                    f"Service {service_name} is type {service_type}, no external access",
                )
                return None

        except Exception as e:
            from ...foundation.logging_utils import LoggingUtility

            LoggingUtility.log_debug(
                "get_external_dashboard_url", f"Error getting external URL: {e}"
            )
            return None

    def _get_loadbalancer_url(self, service, dashboard_port: int) -> Optional[str]:
        """Get LoadBalancer service external URL."""
        try:
            # Safe access to service.status.load_balancer
            service_status = getattr(service, "status", None)
            if not service_status:
                return None

            load_balancer = getattr(service_status, "load_balancer", None)
            if not load_balancer:
                return None

            ingress_list = getattr(load_balancer, "ingress", None)
            if not ingress_list or len(ingress_list) == 0:
                return None

            ingress = ingress_list[0]

            # Try IP first, then hostname
            external_host = getattr(ingress, "ip", None) or getattr(
                ingress, "hostname", None
            )
            if external_host:
                # Find the external port for dashboard
                external_port = self._find_external_port(service, dashboard_port)
                if external_port:
                    url = f"http://{external_host}:{external_port}"
                    from ...foundation.logging_utils import LoggingUtility

                    LoggingUtility.log_info(
                        "loadbalancer_url", f"LoadBalancer external URL: {url}"
                    )
                    return url

            from ...foundation.logging_utils import LoggingUtility

            LoggingUtility.log_debug(
                "loadbalancer_url",
                "LoadBalancer service has no external IP assigned yet",
            )
            return None

        except Exception as e:
            from ...foundation.logging_utils import LoggingUtility

            LoggingUtility.log_debug(
                "loadbalancer_url", f"Error getting LoadBalancer URL: {e}"
            )
            return None

    def _get_nodeport_url(
        self, service, dashboard_port: int, namespace: str
    ) -> Optional[str]:
        """Get NodePort service external URL."""
        try:
            # Safe access to service.spec.ports
            service_spec = getattr(service, "spec", None)
            if not service_spec:
                return None

            ports = getattr(service_spec, "ports", [])
            if not ports:
                return None

            # Find the NodePort for the dashboard
            node_port = None
            for port in ports:
                port_num = getattr(port, "port", None)
                node_port_num = getattr(port, "node_port", None)
                if port_num == dashboard_port and node_port_num:
                    node_port = node_port_num
                    break

            if not node_port:
                from ...foundation.logging_utils import LoggingUtility

                LoggingUtility.log_debug(
                    "nodeport_url",
                    f"Dashboard port {dashboard_port} not found in service ports",
                )
                return None

            # Get node external IP (using sync version for non-async method)
            node_ip = self._get_node_external_ip_sync()
            if node_ip:
                url = f"http://{node_ip}:{node_port}"
                from ...foundation.logging_utils import LoggingUtility

                LoggingUtility.log_info("nodeport_url", f"NodePort external URL: {url}")
                return url

            from ...foundation.logging_utils import LoggingUtility

            LoggingUtility.log_debug(
                "nodeport_url", "Could not determine node external IP"
            )
            return None

        except Exception as e:
            from ...foundation.logging_utils import LoggingUtility

            LoggingUtility.log_debug("nodeport_url", f"Error getting NodePort URL: {e}")
            return None

    def _find_external_port(self, service, target_port: int) -> Optional[int]:
        """Find the external port for a target port in a service."""
        try:
            service_spec = getattr(service, "spec", None)
            if not service_spec:
                return None

            ports = getattr(service_spec, "ports", [])
            if not ports:
                return None

            for port in ports:
                port_num = getattr(port, "port", None)
                if port_num == target_port:
                    return port_num
            return None
        except Exception:
            return None

    async def _get_node_external_ip(self) -> Optional[str]:
        """Get external IP of any cluster node."""
        try:
            self._ensure_kubernetes_client()

            # List all nodes
            nodes = await asyncio.to_thread(self._core_v1_api.list_node)

            # Look for a node with external IP
            for node in nodes.items:
                if node.status.addresses:
                    for address in node.status.addresses:
                        if address.type == "ExternalIP":
                            return address.address

            # If no external IP, try internal IP as fallback
            for node in nodes.items:
                if node.status.addresses:
                    for address in node.status.addresses:
                        if address.type == "InternalIP":
                            from ...foundation.logging_utils import LoggingUtility

                            LoggingUtility.log_debug(
                                "node_external_ip",
                                f"Using internal IP {address.address} as fallback",
                            )
                            return address.address

            return None

        except Exception as e:
            from ...foundation.logging_utils import LoggingUtility

            LoggingUtility.log_debug(
                "node_external_ip", f"Error getting node external IP: {e}"
            )
            return None

    def _get_node_external_ip_sync(self) -> Optional[str]:
        """Get external IP of any cluster node (sync version for dashboard URL)."""
        try:
            if not self._KUBERNETES_AVAILABLE:
                return None

            self._ensure_kubernetes_client()

            # Simplified sync version - just return None for dashboard URL generation
            # The async version should be used for critical operations
            from ...foundation.logging_utils import LoggingUtility

            LoggingUtility.log_debug(
                "node_external_ip_sync",
                "Sync version used for dashboard URL - returning None to use cluster-internal URL",
            )
            return None

        except Exception as e:
            from ...foundation.logging_utils import LoggingUtility

            LoggingUtility.log_debug(
                "node_external_ip_sync", f"Error in sync version: {e}"
            )
            return None

    async def _get_nodeport_url_async(
        self, service, dashboard_port: int, namespace: str
    ) -> Optional[str]:
        """Get NodePort service external URL (async version)."""
        try:
            # Safe access to service.spec.ports
            service_spec = getattr(service, "spec", None)
            if not service_spec:
                return None

            ports = getattr(service_spec, "ports", [])
            if not ports:
                return None

            # Find the NodePort for the dashboard
            node_port = None
            for port in ports:
                port_num = getattr(port, "port", None)
                node_port_num = getattr(port, "node_port", None)
                if port_num == dashboard_port and node_port_num:
                    node_port = node_port_num
                    break

            if not node_port:
                from ...foundation.logging_utils import LoggingUtility

                LoggingUtility.log_debug(
                    "nodeport_url_async",
                    f"No NodePort found for dashboard port {dashboard_port}",
                )
                return None

            # Get a node IP to construct the URL (using async version)
            node_ip = await self._get_node_external_ip()
            if node_ip:
                url = f"http://{node_ip}:{node_port}"
                from ...foundation.logging_utils import LoggingUtility

                LoggingUtility.log_info(
                    "nodeport_url_async", f"NodePort external URL: {url}"
                )
                return url
            else:
                from ...foundation.logging_utils import LoggingUtility

                LoggingUtility.log_debug(
                    "nodeport_url_async",
                    "No external node IP available for NodePort access",
                )
                return None

        except Exception as e:
            from ...foundation.logging_utils import LoggingUtility

            LoggingUtility.log_debug(
                "nodeport_url_async", f"Error getting NodePort URL: {e}"
            )
            return None

    async def _wait_for_service_ready(
        self, cluster_name: str, namespace: str, timeout: int = 120
    ) -> Optional[str]:
        """Wait for service to be ready and return external URL if available."""
        if not self._KUBERNETES_AVAILABLE:
            return None

        try:
            service_name = f"{cluster_name}-head-svc"

            for attempt in range(timeout // 10):  # Check every 10 seconds
                try:
                    self._ensure_kubernetes_client()

                    # Check if service exists
                    try:
                        service = await asyncio.to_thread(
                            self._core_v1_api.read_namespaced_service,
                            name=service_name,
                            namespace=namespace,
                        )
                    except self._ApiException as e:
                        status = getattr(e, "status", "unknown")
                        if status == 404:
                            from ...foundation.logging_utils import LoggingUtility

                            LoggingUtility.log_debug(
                                "service_ready_check",
                                f"Attempt {attempt + 1}: Service {service_name} not found yet",
                            )
                            await asyncio.sleep(10)
                            continue
                        else:
                            raise

                    # Check service type and readiness with safe access
                    service_spec = getattr(service, "spec", None)
                    service_type = (
                        getattr(service_spec, "type", "Unknown")
                        if service_spec
                        else "Unknown"
                    )

                    if service_type == "LoadBalancer":
                        # For LoadBalancer, check if external IP is assigned
                        service_status = getattr(service, "status", None)
                        if service_status:
                            load_balancer = getattr(
                                service_status, "load_balancer", None
                            )
                            if load_balancer:
                                ingress_list = getattr(load_balancer, "ingress", None)
                                if ingress_list and len(ingress_list) > 0:
                                    ingress = ingress_list[0]
                                    if getattr(ingress, "ip", None) or getattr(
                                        ingress, "hostname", None
                                    ):
                                        external_url = self._get_loadbalancer_url(
                                            service, 8265
                                        )
                                        if external_url:
                                            from ...foundation.logging_utils import (
                                                LoggingUtility,
                                            )

                                            LoggingUtility.log_info(
                                                "service_ready",
                                                f"LoadBalancer service {service_name} ready with external URL: {external_url}",
                                            )
                                            return external_url

                        from ...foundation.logging_utils import LoggingUtility

                        LoggingUtility.log_debug(
                            "service_ready_check",
                            f"Attempt {attempt + 1}: LoadBalancer {service_name} external IP not assigned yet",
                        )

                    elif service_type == "NodePort":
                        # For NodePort, service is ready once it exists
                        external_url = await self._get_nodeport_url_async(
                            service, 8265, namespace
                        )
                        if external_url:
                            from ...foundation.logging_utils import LoggingUtility

                            LoggingUtility.log_info(
                                "service_ready",
                                f"NodePort service {service_name} ready with external URL: {external_url}",
                            )
                            return external_url

                        from ...foundation.logging_utils import LoggingUtility

                        LoggingUtility.log_debug(
                            "service_ready_check",
                            f"Attempt {attempt + 1}: NodePort {service_name} has no accessible external IP",
                        )

                    else:
                        # For ClusterIP, service is ready but no external access
                        from ...foundation.logging_utils import LoggingUtility

                        LoggingUtility.log_debug(
                            "service_ready_check",
                            f"Service {service_name} is type {service_type}, no external access available",
                        )
                        return None

                except Exception as e:
                    from ...foundation.logging_utils import LoggingUtility

                    LoggingUtility.log_debug(
                        "service_ready_check", f"Attempt {attempt + 1}: {e}"
                    )

                await asyncio.sleep(10)

            from ...foundation.logging_utils import LoggingUtility

            LoggingUtility.log_warning(
                "service_ready_timeout",
                f"Service {service_name} external access not ready after {timeout}s, using cluster-internal URL",
            )
            return None

        except Exception as e:
            from ...foundation.logging_utils import LoggingUtility

            LoggingUtility.log_error(
                "wait_for_service_ready", Exception(f"Error waiting for service: {e}")
            )
            return None
