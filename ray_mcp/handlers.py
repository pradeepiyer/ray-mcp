"""Clean operation handlers for Ray MCP server."""

from typing import Any, Dict

from .managers.unified_manager import RayUnifiedManager
from .parsers import ActionParser


class RayHandlers:
    """Clean handlers for Ray operations."""

    def __init__(self, ray_manager: RayUnifiedManager):
        self.ray_manager = ray_manager

    async def handle_cluster(self, prompt: str) -> Dict[str, Any]:
        """Handle cluster operations."""
        try:
            action = ActionParser.parse_cluster_action(prompt)
            operation = action["operation"]

            if operation == "create":
                return await self._create_cluster(action)
            elif operation == "connect":
                return await self._connect_cluster(action)
            elif operation == "stop":
                return await self._stop_cluster(action)
            elif operation == "scale":
                return await self._scale_cluster(action)
            elif operation == "inspect":
                return await self._inspect_cluster(action)
            elif operation == "list":
                return await self._list_clusters()
            else:
                return {"status": "error", "message": f"Unknown operation: {operation}"}

        except ValueError as e:
            return {"status": "error", "message": str(e)}

    async def handle_job(self, prompt: str) -> Dict[str, Any]:
        """Handle job operations."""
        try:
            action = ActionParser.parse_job_action(prompt)
            operation = action["operation"]

            if operation == "submit":
                return await self._submit_job(action)
            elif operation == "list":
                return await self._list_jobs()
            elif operation == "inspect":
                return await self._inspect_job(action)
            elif operation == "logs":
                return await self._get_job_logs(action)
            elif operation == "cancel":
                return await self._cancel_job(action)
            else:
                return {"status": "error", "message": f"Unknown operation: {operation}"}

        except ValueError as e:
            return {"status": "error", "message": str(e)}

    async def handle_cloud(self, prompt: str) -> Dict[str, Any]:
        """Handle cloud operations."""
        try:
            action = ActionParser.parse_cloud_action(prompt)
            operation = action["operation"]

            if operation == "authenticate":
                return await self._authenticate_cloud(action)
            elif operation == "list_clusters":
                return await self._list_k8s_clusters()
            elif operation == "connect_cluster":
                return await self._connect_k8s_cluster(action)
            elif operation == "create_cluster":
                return await self._create_k8s_cluster(action)
            elif operation == "check_environment":
                return await self._check_environment()
            else:
                return {"status": "error", "message": f"Unknown operation: {operation}"}

        except ValueError as e:
            return {"status": "error", "message": str(e)}

    # Cluster operation implementations
    async def _create_cluster(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Create Ray cluster."""
        if action["environment"] == "kubernetes":
            cluster_spec = {
                "cluster_name": action.get("name"),
                "worker_node_specs": [] if action.get("head_only") else None,
                **action.get("resources", {}),
            }
            return await self.ray_manager.create_kuberay_cluster(
                cluster_spec=cluster_spec
            )
        else:
            return await self.ray_manager.init_cluster(
                num_cpus=action.get("resources", {}).get("cpu", 1),
                worker_nodes=[] if action.get("head_only") else None,
            )

    async def _connect_cluster(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Connect to existing cluster."""
        return await self.ray_manager.init_cluster(address=action.get("address"))

    async def _stop_cluster(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Stop Ray cluster."""
        cluster_name = action.get("name")
        if cluster_name:
            return await self.ray_manager.delete_kuberay_cluster(cluster_name)
        else:
            return await self.ray_manager.stop_cluster()

    async def _scale_cluster(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Scale cluster workers."""
        cluster_name = action.get("name")
        worker_replicas = action.get("workers", 1)
        if cluster_name:
            return await self.ray_manager.scale_ray_cluster(
                name=cluster_name, worker_replicas=worker_replicas
            )
        else:
            return {"status": "error", "message": "cluster name required for scaling"}

    async def _inspect_cluster(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Inspect cluster status."""
        cluster_name = action.get("name")
        if cluster_name:
            return await self.ray_manager.get_kuberay_cluster(cluster_name)
        else:
            return await self.ray_manager.inspect_ray_cluster()

    async def _list_clusters(self) -> Dict[str, Any]:
        """List all clusters."""
        return await self.ray_manager.list_ray_clusters()

    # Job operation implementations
    async def _submit_job(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Submit Ray job."""
        job_spec = {
            "entrypoint": f"python {action.get('script', 'main.py')}",
            "runtime_env": (
                {"working_dir": action.get("source")} if action.get("source") else None
            ),
        }
        return await self.ray_manager.create_kuberay_job(job_spec=job_spec)

    async def _list_jobs(self) -> Dict[str, Any]:
        """List all jobs."""
        return await self.ray_manager.list_ray_jobs()

    async def _inspect_job(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Inspect job status."""
        job_id = action.get("job_id")
        if job_id:
            return await self.ray_manager.inspect_ray_job(job_id)
        else:
            return {"status": "error", "message": "job_id required for inspection"}

    async def _get_job_logs(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Get job logs."""
        job_id = action.get("job_id")
        if job_id:
            return await self.ray_manager.retrieve_logs(
                identifier=job_id,
                include_errors=action.get("filter_errors", False),
            )
        else:
            return {"status": "error", "message": "job_id required for logs"}

    async def _cancel_job(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Cancel job."""
        job_id = action.get("job_id")
        if job_id:
            return await self.ray_manager.cancel_ray_job(job_id)
        else:
            return {"status": "error", "message": "job_id required for cancellation"}

    # Cloud operation implementations
    async def _authenticate_cloud(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate with cloud provider."""
        return await self.ray_manager.authenticate_cloud_provider(
            provider="gke", auth_config={"project_id": action.get("project")}
        )

    async def _list_k8s_clusters(self) -> Dict[str, Any]:
        """List Kubernetes clusters."""
        return await self.ray_manager.list_kubernetes_clusters(provider="gke")

    async def _connect_k8s_cluster(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Connect to K8s cluster."""
        return await self.ray_manager.connect_kubernetes_cluster(
            provider="gke", cluster_name=action.get("cluster_name")
        )

    async def _create_k8s_cluster(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Create K8s cluster."""
        cluster_spec = {
            "name": action.get("cluster_name"),
            "zone": action.get("zone", "us-central1-a"),
        }
        return await self.ray_manager.create_kubernetes_cluster(
            provider="gke", cluster_spec=cluster_spec
        )

    async def _check_environment(self) -> Dict[str, Any]:
        """Check environment status."""
        return await self.ray_manager.check_environment()
