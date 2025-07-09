"""KubeRay job management implementation."""

from typing import Any, Dict, Optional

from ...foundation.base_managers import ResourceManager
from ...foundation.interfaces import KubeRayJobManager
from ..crds.crd_operations import CRDOperationsClient
from ..crds.ray_job_crd import RayJobCRDManager


class KubeRayJobManagerImpl(ResourceManager, KubeRayJobManager):
    """Manages Ray job lifecycle using KubeRay Custom Resources."""

    def __init__(
        self,
        state_manager,
        crd_operations: Optional[CRDOperationsClient] = None,
        job_crd: Optional[RayJobCRDManager] = None,
    ):
        super().__init__(
            state_manager, enable_ray=True, enable_kubernetes=True, enable_cloud=False
        )
        self._crd_operations = crd_operations or CRDOperationsClient()
        self._job_crd = job_crd or RayJobCRDManager()

    def set_kubernetes_config(self, kubernetes_config) -> None:
        """Set the Kubernetes configuration for API operations."""
        try:
            from ...foundation.logging_utils import LoggingUtility

            LoggingUtility.log_info(
                "kuberay_job_set_k8s_config",
                f"Setting Kubernetes config - config provided: {kubernetes_config is not None}, host: {getattr(kubernetes_config, 'host', 'N/A') if kubernetes_config else 'N/A'}",
            )
            self._crd_operations.set_kubernetes_config(kubernetes_config)
            LoggingUtility.log_info(
                "kuberay_job_set_k8s_config",
                "Successfully set Kubernetes configuration on CRD operations client",
            )
        except Exception as e:
            # Log the error instead of silently ignoring it
            from ...foundation.logging_utils import LoggingUtility

            LoggingUtility.log_error(
                "kuberay_job_set_k8s_config",
                Exception(f"Failed to set Kubernetes configuration: {str(e)}"),
            )

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
        shutdown_after_job_finishes = job_spec.get(
            "shutdown_after_job_finishes"
        )  # Let intelligent defaults work

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
            shutdown_after_job_finishes=shutdown_after_job_finishes,
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
                    "shutdown_after_job_finishes",
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

        # Get logs from the job's pods
        try:
            # Create a Kubernetes client to get pod logs
            from ..config.kubernetes_client import KubernetesApiClient

            k8s_client = KubernetesApiClient()

            # Set the same Kubernetes configuration as CRD operations if available
            if (
                hasattr(self._crd_operations, "_kubernetes_config")
                and self._crd_operations._kubernetes_config
            ):
                k8s_client.set_kubernetes_config(
                    self._crd_operations._kubernetes_config
                )

            # Approach 1: Try to get logs from job runner pods
            # RayJob creates pods with labels indicating they belong to this job
            job_label_selector = (
                f"ray.io/cluster={ray_cluster_name},ray.io/job-name={name}"
            )

            job_logs_result = await k8s_client.get_pod_logs(
                namespace=namespace,
                label_selector=job_label_selector,
                lines=1000,  # Get more lines for job logs
                timestamps=True,
            )

            # If we got logs from job-specific pods, return them
            if (
                job_logs_result.get("status") == "success"
                and job_logs_result.get("pod_count", 0) > 0
            ):
                logs = job_logs_result.get("logs", "")

                # Process the logs to extract key information
                processed_logs = self._process_ray_job_logs(logs)

                return self._response_formatter.format_success_response(
                    job_name=name,
                    namespace=namespace,
                    ray_cluster_name=ray_cluster_name,
                    job_status=job.get("job_status"),
                    logs=processed_logs,
                    log_source="job_runner_pods",
                    pod_count=job_logs_result.get("pod_count", 0),
                    raw_logs=logs,
                )

            # Approach 2: If no job-specific pods, try to get logs from head node
            # This may contain job submission logs and general job information
            head_pod_selector = (
                f"ray.io/cluster={ray_cluster_name},ray.io/node-type=head"
            )

            head_logs_result = await k8s_client.get_pod_logs(
                namespace=namespace,
                label_selector=head_pod_selector,
                lines=500,  # Get fewer lines from head node
                timestamps=True,
            )

            if (
                head_logs_result.get("status") == "success"
                and head_logs_result.get("pod_count", 0) > 0
            ):
                head_logs = head_logs_result.get("logs", "")

                # Filter head logs to show job-related entries
                job_related_logs = self._filter_head_logs_for_job(head_logs, name)

                return self._response_formatter.format_success_response(
                    job_name=name,
                    namespace=namespace,
                    ray_cluster_name=ray_cluster_name,
                    job_status=job.get("job_status"),
                    logs=job_related_logs,
                    log_source="head_node_filtered",
                    pod_count=head_logs_result.get("pod_count", 0),
                    message=f"Job-specific logs not found, showing job-related entries from head node",
                )

            # Approach 3: Last resort - get general cluster logs
            cluster_selector = f"ray.io/cluster={ray_cluster_name}"

            cluster_logs_result = await k8s_client.get_pod_logs(
                namespace=namespace,
                label_selector=cluster_selector,
                lines=200,  # Get fewer lines for general cluster logs
                timestamps=True,
            )

            if cluster_logs_result.get("status") == "success":
                cluster_logs = cluster_logs_result.get("logs", "")

                return self._response_formatter.format_success_response(
                    job_name=name,
                    namespace=namespace,
                    ray_cluster_name=ray_cluster_name,
                    job_status=job.get("job_status"),
                    logs=cluster_logs,
                    log_source="cluster_general",
                    pod_count=cluster_logs_result.get("pod_count", 0),
                    message=f"Job-specific logs not available, showing general cluster logs",
                )

            # If all approaches fail, return an informative error
            return self._response_formatter.format_error_response(
                "get ray job logs",
                Exception(
                    f"Could not retrieve logs for job '{name}' from cluster '{ray_cluster_name}'"
                ),
            )

        except Exception as e:
            return self._response_formatter.format_error_response(
                "get ray job logs",
                Exception(f"Error retrieving logs: {str(e)}"),
            )

    def _process_ray_job_logs(self, logs: str) -> str:
        """Process and format Ray job logs for better readability."""
        if not logs:
            return "No logs available"

        # Split logs into lines for processing
        lines = logs.split("\n")
        processed_lines = []

        for line in lines:
            # Remove excessive whitespace
            line = line.strip()
            if not line:
                continue

            # Highlight important log entries
            if any(
                keyword in line.lower()
                for keyword in ["error", "exception", "failed", "traceback"]
            ):
                processed_lines.append(f"🔴 {line}")
            elif any(keyword in line.lower() for keyword in ["warning", "warn"]):
                processed_lines.append(f"🟡 {line}")
            elif any(
                keyword in line.lower()
                for keyword in ["success", "completed", "finished"]
            ):
                processed_lines.append(f"🟢 {line}")
            else:
                processed_lines.append(line)

        return "\n".join(processed_lines)

    def _filter_head_logs_for_job(self, logs: str, job_name: str) -> str:
        """Filter head node logs to show only job-related entries."""
        if not logs:
            return "No logs available"

        lines = logs.split("\n")
        job_related_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Look for lines that mention the job name or job-related keywords
            if job_name in line or any(
                keyword in line.lower()
                for keyword in [
                    "job",
                    "submit",
                    "raysubmit",
                    "entrypoint",
                    "runtime_env",
                ]
            ):
                job_related_lines.append(line)

        if not job_related_lines:
            return f"No job-related logs found for job '{job_name}' in head node logs"

        return "\n".join(job_related_lines)

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
