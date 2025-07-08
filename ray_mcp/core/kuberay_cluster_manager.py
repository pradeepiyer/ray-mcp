"""KubeRay cluster management for Ray clusters on Kubernetes."""

from typing import Any, Dict, List, Optional

try:
    from ..logging_utils import LoggingUtility, ResponseFormatter
except ImportError:
    # Fallback for direct execution
    import os
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from logging_utils import LoggingUtility, ResponseFormatter

from .crd_operations import CRDOperationsClient
from .interfaces import KubeRayClusterManager, KubeRayComponent, StateManager
from .ray_cluster_crd import RayClusterCRDManager


class KubeRayClusterManagerImpl(KubeRayComponent, KubeRayClusterManager):
    """Manages Ray cluster lifecycle using KubeRay Custom Resources."""

    def __init__(
        self,
        state_manager: StateManager,
        crd_operations: Optional[CRDOperationsClient] = None,
        cluster_crd: Optional[RayClusterCRDManager] = None,
    ):
        super().__init__(state_manager)
        self._crd_operations = crd_operations or CRDOperationsClient()
        self._cluster_crd = cluster_crd or RayClusterCRDManager()
        self._response_formatter = ResponseFormatter()

    def set_kubernetes_config(self, kubernetes_config) -> None:
        """Set the Kubernetes configuration for API operations."""
        try:
            from ..logging_utils import LoggingUtility
            LoggingUtility.log_info(
                "kuberay_cluster_set_k8s_config",
                f"Setting Kubernetes config - config provided: {kubernetes_config is not None}, host: {getattr(kubernetes_config, 'host', 'N/A') if kubernetes_config else 'N/A'}"
            )
            self._crd_operations.set_kubernetes_config(kubernetes_config)
            LoggingUtility.log_info(
                "kuberay_cluster_set_k8s_config",
                "Successfully set Kubernetes configuration on CRD operations client"
            )
        except Exception as e:
            # Log the error instead of silently ignoring it
            from ..logging_utils import LoggingUtility
            LoggingUtility.log_error(
                "kuberay_cluster_set_k8s_config",
                f"Failed to set Kubernetes configuration: {str(e)}"
            )



    @ResponseFormatter.handle_exceptions("create ray cluster")
    async def create_ray_cluster(
        self, cluster_spec: Dict[str, Any], namespace: str = "default"
    ) -> Dict[str, Any]:
        """Create a Ray cluster using KubeRay."""
        self._ensure_kuberay_ready()

        # Extract configuration from cluster_spec
        cluster_name = cluster_spec.get("cluster_name")
        head_node_spec = cluster_spec.get("head_node_spec", {})
        worker_node_specs = cluster_spec.get("worker_node_specs", [])
        ray_version = cluster_spec.get("ray_version", "2.47.0")
        enable_ingress = cluster_spec.get("enable_ingress", False)
        suspend = cluster_spec.get("suspend", False)

        # Validate required fields
        if not head_node_spec:
            return self._response_formatter.format_error_response(
                "create ray cluster", Exception("head_node_spec is required")
            )

        # Create the RayCluster CRD specification
        crd_result = self._cluster_crd.create_spec(
            head_node_spec=head_node_spec,
            worker_node_specs=worker_node_specs,
            cluster_name=cluster_name,
            namespace=namespace,
            ray_version=ray_version,
            enable_ingress=enable_ingress,
            suspend=suspend,
            **{
                k: v
                for k, v in cluster_spec.items()
                if k
                not in [
                    "cluster_name",
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
        actual_cluster_name = crd_result["cluster_name"]

        # Create the RayCluster resource in Kubernetes
        create_result = await self._crd_operations.create_resource(
            resource_type="raycluster",
            resource_spec=ray_cluster_spec,
            namespace=namespace,
        )

        if create_result.get("status") == "success":
            # Update state to track the cluster
            self._update_cluster_state(actual_cluster_name, namespace, "creating")

            return self._response_formatter.format_success_response(
                cluster_name=actual_cluster_name,
                namespace=namespace,
                cluster_status="creating",
                resource=create_result.get("resource", {}),
                dashboard_url=self._get_dashboard_url(actual_cluster_name, namespace),
                message=f"RayCluster '{actual_cluster_name}' creation initiated",
            )
        else:
            return create_result

    @ResponseFormatter.handle_exceptions("get ray cluster")
    async def get_ray_cluster(
        self, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Get Ray cluster status."""
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

            return self._response_formatter.format_success_response(
                cluster=cluster_status, ready=is_ready, raw_resource=resource
            )
        else:
            return result

    @ResponseFormatter.handle_exceptions("list ray clusters")
    async def list_ray_clusters(self, namespace: str = "default") -> Dict[str, Any]:
        """List Ray clusters."""
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

            return self._response_formatter.format_success_response(
                clusters=clusters, total_count=len(clusters), namespace=namespace
            )
        else:
            return result

    @ResponseFormatter.handle_exceptions("update ray cluster")
    async def update_ray_cluster(
        self, name: str, cluster_spec: Dict[str, Any], namespace: str = "default"
    ) -> Dict[str, Any]:
        """Update Ray cluster configuration."""
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

            return self._response_formatter.format_success_response(
                cluster_name=name,
                namespace=namespace,
                cluster_status="updating",
                message=f"RayCluster '{name}' update initiated",
            )
        else:
            return update_result

    @ResponseFormatter.handle_exceptions("delete ray cluster")
    async def delete_ray_cluster(
        self, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Delete Ray cluster."""
        self._ensure_kuberay_ready()

        result = await self._crd_operations.delete_resource(
            resource_type="raycluster", name=name, namespace=namespace
        )

        if result.get("status") == "success":
            # Update state to remove the cluster
            self._remove_cluster_state(name, namespace)

            return self._response_formatter.format_success_response(
                cluster_name=name,
                namespace=namespace,
                deleted=True,
                deletion_timestamp=result.get("deletion_timestamp"),
                message=f"RayCluster '{name}' deletion initiated",
            )
        else:
            return result

    @ResponseFormatter.handle_exceptions("scale ray cluster")
    async def scale_ray_cluster(
        self, name: str, worker_replicas: int, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Scale Ray cluster workers."""
        self._ensure_kuberay_ready()

        if worker_replicas < 0:
            return self._response_formatter.format_error_response(
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
            return self._response_formatter.format_error_response(
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
            return self._response_formatter.format_success_response(
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
        # This would typically be constructed based on ingress or port-forwarding setup
        # For now, return a template URL
        return f"http://{cluster_name}-head-svc.{namespace}.svc.cluster.local:8265"
