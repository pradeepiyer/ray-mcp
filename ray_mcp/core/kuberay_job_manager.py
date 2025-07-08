"""KubeRay job management for Ray jobs on Kubernetes."""

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
from .interfaces import KubeRayComponent, KubeRayJobManager, StateManager
from .ray_job_crd import RayJobCRDManager


class KubeRayJobManagerImpl(KubeRayComponent, KubeRayJobManager):
    """Manages Ray job lifecycle using KubeRay Custom Resources."""

    def __init__(
        self,
        state_manager: StateManager,
        crd_operations: Optional[CRDOperationsClient] = None,
        job_crd: Optional[RayJobCRDManager] = None,
    ):
        super().__init__(state_manager)
        self._crd_operations = crd_operations or CRDOperationsClient()
        self._job_crd = job_crd or RayJobCRDManager()
        self._response_formatter = ResponseFormatter()

    def set_kubernetes_config(self, kubernetes_config) -> None:
        """Set the Kubernetes configuration for API operations."""
        try:
            from ..logging_utils import LoggingUtility
            LoggingUtility.log_info(
                "kuberay_job_set_k8s_config",
                f"Setting Kubernetes config - config provided: {kubernetes_config is not None}, host: {getattr(kubernetes_config, 'host', 'N/A') if kubernetes_config else 'N/A'}"
            )
            self._crd_operations.set_kubernetes_config(kubernetes_config)
            LoggingUtility.log_info(
                "kuberay_job_set_k8s_config",
                "Successfully set Kubernetes configuration on CRD operations client"
            )
        except Exception as e:
            # Log the error instead of silently ignoring it
            from ..logging_utils import LoggingUtility
            LoggingUtility.log_error(
                "kuberay_job_set_k8s_config",
                f"Failed to set Kubernetes configuration: {str(e)}"
            )

    @ResponseFormatter.handle_exceptions("create ray job")
    async def create_ray_job(
        self, job_spec: Dict[str, Any], namespace: str = "default"
    ) -> Dict[str, Any]:
        """Create a Ray job using KubeRay."""
        self._ensure_kuberay_ready()

        # Extract configuration from job_spec
        entrypoint = job_spec.get("entrypoint")
        runtime_env = job_spec.get("runtime_env")
        job_name = job_spec.get("job_name")
        cluster_selector = job_spec.get("cluster_selector")
        suspend = job_spec.get("suspend", False)
        ttl_seconds_after_finished = job_spec.get("ttl_seconds_after_finished", 86400)
        active_deadline_seconds = job_spec.get("active_deadline_seconds")
        backoff_limit = job_spec.get("backoff_limit", 0)

        # Validate required fields
        if not entrypoint:
            return self._response_formatter.format_error_response(
                "create ray job", Exception("entrypoint is required")
            )

        # Create the RayJob CRD specification
        crd_result = self._job_crd.create_spec(
            entrypoint=entrypoint,
            runtime_env=runtime_env,
            job_name=job_name,
            namespace=namespace,
            cluster_selector=cluster_selector,
            suspend=suspend,
            ttl_seconds_after_finished=ttl_seconds_after_finished,
            active_deadline_seconds=active_deadline_seconds,
            backoff_limit=backoff_limit,
            **{
                k: v
                for k, v in job_spec.items()
                if k
                not in [
                    "entrypoint",
                    "runtime_env",
                    "job_name",
                    "namespace",
                    "cluster_selector",
                    "suspend",
                    "ttl_seconds_after_finished",
                    "active_deadline_seconds",
                    "backoff_limit",
                ]
            },
        )

        if crd_result.get("status") != "success":
            return crd_result

        ray_job_spec = crd_result["job_spec"]
        actual_job_name = crd_result["job_name"]

        # Create the RayJob resource in Kubernetes
        create_result = await self._crd_operations.create_resource(
            resource_type="rayjob", resource_spec=ray_job_spec, namespace=namespace
        )

        if create_result.get("status") == "success":
            # Update state to track the job
            self._update_job_state(actual_job_name, namespace, "creating")

            return self._response_formatter.format_success_response(
                job_name=actual_job_name,
                namespace=namespace,
                job_status="creating",
                entrypoint=entrypoint,
                resource=create_result.get("resource", {}),
                message=f"RayJob '{actual_job_name}' creation initiated",
            )
        else:
            return create_result

    @ResponseFormatter.handle_exceptions("get ray job")
    async def get_ray_job(
        self, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Get Ray job status."""
        self._ensure_kuberay_ready()

        result = await self._crd_operations.get_resource(
            resource_type="rayjob", name=name, namespace=namespace
        )

        if result.get("status") == "success":
            resource = result.get("resource", {})
            status = resource.get("status", {})
            spec = resource.get("spec", {})

            # Extract detailed status information
            job_status = {
                "name": name,
                "namespace": namespace,
                "phase": status.get("phase", "Unknown"),
                "job_status": status.get("jobStatus", "Unknown"),
                "job_deployment_status": status.get("jobDeploymentStatus", "Unknown"),
                "ray_cluster_name": status.get("rayClusterName"),
                "ray_cluster_namespace": status.get("rayClusterNamespace"),
                "start_time": status.get("startTime"),
                "end_time": status.get("endTime"),
                "creation_timestamp": resource.get("metadata", {}).get(
                    "creationTimestamp"
                ),
                "entrypoint": spec.get("entrypoint"),
                "runtime_env": spec.get("runtimeEnvYAML"),
                "ttl_seconds_after_finished": spec.get("ttlSecondsAfterFinished"),
                "suspend": spec.get("suspend", False),
            }

            # Check if job is complete
            is_complete = status.get("jobStatus") in ["SUCCEEDED", "FAILED", "STOPPED"]
            is_running = status.get("jobStatus") == "RUNNING"

            return self._response_formatter.format_success_response(
                job=job_status,
                complete=is_complete,
                running=is_running,
                raw_resource=resource,
            )
        else:
            return result

    @ResponseFormatter.handle_exceptions("list ray jobs")
    async def list_ray_jobs(self, namespace: str = "default") -> Dict[str, Any]:
        """List Ray jobs."""
        self._ensure_kuberay_ready()

        result = await self._crd_operations.list_resources(
            resource_type="rayjob", namespace=namespace
        )

        if result.get("status") == "success":
            jobs = []
            for resource_summary in result.get("resources", []):
                # Get additional status from the full resource if available
                status = resource_summary.get("status", {})

                job_info = {
                    "name": resource_summary.get("name"),
                    "namespace": resource_summary.get("namespace"),
                    "phase": resource_summary.get("phase", "Unknown"),
                    "job_status": status.get("jobStatus", "Unknown"),
                    "creation_timestamp": resource_summary.get("creation_timestamp"),
                    "labels": resource_summary.get("labels", {}),
                    "ray_cluster_name": status.get("rayClusterName"),
                    "start_time": status.get("startTime"),
                    "end_time": status.get("endTime"),
                }
                jobs.append(job_info)

            return self._response_formatter.format_success_response(
                jobs=jobs, total_count=len(jobs), namespace=namespace
            )
        else:
            return result

    @ResponseFormatter.handle_exceptions("delete ray job")
    async def delete_ray_job(
        self, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Delete Ray job."""
        self._ensure_kuberay_ready()

        result = await self._crd_operations.delete_resource(
            resource_type="rayjob", name=name, namespace=namespace
        )

        if result.get("status") == "success":
            # Update state to remove the job
            self._remove_job_state(name, namespace)

            return self._response_formatter.format_success_response(
                job_name=name,
                namespace=namespace,
                deleted=True,
                deletion_timestamp=result.get("deletion_timestamp"),
                message=f"RayJob '{name}' deletion initiated",
            )
        else:
            return result

    @ResponseFormatter.handle_exceptions("get ray job logs")
    async def get_ray_job_logs(
        self, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Get Ray job logs."""
        self._ensure_kuberay_ready()

        # First get the job to understand its current state and associated cluster
        job_result = await self.get_ray_job(name, namespace)
        if job_result.get("status") != "success":
            return job_result

        job = job_result.get("job", {})
        ray_cluster_name = job.get("ray_cluster_name")

        if not ray_cluster_name:
            return self._response_formatter.format_error_response(
                "get ray job logs",
                Exception(f"No Ray cluster associated with job '{name}'"),
            )

        # In a full implementation, this would:
        # 1. Connect to the Ray cluster dashboard API
        # 2. Retrieve job logs using the Ray Job API
        # 3. Or query Kubernetes pod logs for the job

        # For now, return a placeholder with available information
        return self._response_formatter.format_success_response(
            job_name=name,
            namespace=namespace,
            ray_cluster_name=ray_cluster_name,
            job_status=job.get("job_status"),
            logs_available=True,
            message="Log retrieval would be implemented to fetch from Ray cluster dashboard or Kubernetes pods",
            log_sources=[
                f"Ray cluster: {ray_cluster_name}",
                f"Kubernetes namespace: {namespace}",
                "Job runner pod logs",
                "Ray dashboard job logs API",
            ],
        )

    def _update_job_state(self, job_name: str, namespace: str, status: str) -> None:
        """Update job state in state manager."""
        state = self.state_manager.get_state()
        kuberay_jobs = state.get("kuberay_jobs", {})

        kuberay_jobs[f"{namespace}/{job_name}"] = {
            "name": job_name,
            "namespace": namespace,
            "job_status": status,
        }

        self.state_manager.update_state(kuberay_jobs=kuberay_jobs)

    def _remove_job_state(self, job_name: str, namespace: str) -> None:
        """Remove job state from state manager."""
        state = self.state_manager.get_state()
        kuberay_jobs = state.get("kuberay_jobs", {})

        job_key = f"{namespace}/{job_name}"
        if job_key in kuberay_jobs:
            del kuberay_jobs[job_key]
            self.state_manager.update_state(kuberay_jobs=kuberay_jobs)
