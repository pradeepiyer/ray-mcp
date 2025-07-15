"""Pure prompt-driven KubeRay job management for Ray MCP."""

from typing import Any, Dict, Optional

from ..config import get_config_manager_sync
from ..foundation.base_managers import ResourceManager
from ..foundation.logging_utils import LoggingUtility
from ..parsers import ActionParser
from .manifest_generator import ManifestGenerator


class KubeRayJobManager(ResourceManager):
    """Pure prompt-driven Ray job management using KubeRay - no traditional APIs."""

    def __init__(self):
        super().__init__(
            enable_ray=True,
            enable_kubernetes=True,
            enable_cloud=False,
        )

        self._config_manager = get_config_manager_sync()
        self._manifest_generator = ManifestGenerator()

    async def execute_request(self, prompt: str) -> Dict[str, Any]:
        """Execute KubeRay job operations using natural language prompts.

        Examples:
            - "create Ray job with training script train.py on kubernetes"
            - "list all Ray jobs in production namespace"
            - "get status of job training-run-123"
            - "delete job experiment-456"
            - "get logs for job data-processing"
        """
        try:
            action = ActionParser.parse_kuberay_job_action(prompt)
            operation = action["operation"]

            if operation == "create":
                return await self._create_ray_job_from_prompt(action)
            elif operation == "list":
                namespace = action.get("namespace", "default")
                return await self._list_ray_jobs(namespace)
            elif operation == "get":
                name = action.get("name")
                namespace = action.get("namespace", "default")
                if not name:
                    return {"status": "error", "message": "job name required"}
                return await self._get_ray_job(name, namespace)
            elif operation == "delete":
                name = action.get("name")
                namespace = action.get("namespace", "default")
                if not name:
                    return {"status": "error", "message": "job name required"}
                return await self._delete_ray_job(name, namespace)
            elif operation == "logs":
                name = action.get("name")
                namespace = action.get("namespace", "default")
                if not name:
                    return {"status": "error", "message": "job name required"}
                return await self._get_ray_job_logs(name, namespace)
            else:
                return {"status": "error", "message": f"Unknown operation: {operation}"}

        except ValueError as e:
            return {"status": "error", "message": f"Could not parse request: {str(e)}"}
        except Exception as e:
            return self._ResponseFormatter.format_error_response("execute_request", e)

    # =================================================================
    # INTERNAL IMPLEMENTATION: All methods are now private
    # =================================================================

    def _set_kubernetes_config(self, kubernetes_config) -> None:
        """Set the Kubernetes configuration for API operations.

        Note: With manifest generation approach, kubectl uses the current kubeconfig context,
        so explicit configuration setting is not needed.
        """
        try:

            LoggingUtility.log_info(
                "kuberay_job_set_k8s_config",
                f"Kubernetes config provided: {kubernetes_config is not None} - using kubectl with current context",
            )
            LoggingUtility.log_info(
                "kuberay_job_set_k8s_config",
                "Using kubectl with current kubeconfig context",
            )
        except Exception as e:

            LoggingUtility.log_error(
                "kuberay_job_set_k8s_config",
                Exception(f"Failed to configure kubectl context: {str(e)}"),
            )

    async def _create_ray_job_from_prompt(
        self, action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create Ray job from parsed prompt action using manifest generation."""
        try:
            namespace = action.get("namespace", "default")

            # Generate manifest from action
            manifest = self._manifest_generator.generate_ray_job_manifest(
                f"create job {action.get('name', 'ray-job')}", action
            )

            # Apply manifest
            result = await self._manifest_generator.apply_manifest(manifest, namespace)

            if result.get("status") == "success":
                job_name = action.get("name", "ray-job")

                return self._ResponseFormatter.format_success_response(
                    job_name=job_name,
                    namespace=namespace,
                    job_status="creating",
                    entrypoint=action.get("script", "python main.py"),
                    runtime_env=action.get("runtime_env"),
                    message=f"RayJob '{job_name}' creation initiated",
                    manifest_applied=True,
                )
            else:
                return self._ResponseFormatter.format_error_response(
                    "create ray job", Exception(result.get("message", "Unknown error"))
                )

        except Exception as e:
            return self._ResponseFormatter.format_error_response(
                "create ray job from prompt", e
            )

    async def _create_ray_job(
        self, job_spec: Dict[str, Any], namespace: str = "default"
    ) -> Dict[str, Any]:
        """Create a Ray job using KubeRay CRD."""
        return await self._execute_operation(
            "create ray job", self._create_ray_job_operation, job_spec, namespace
        )

    async def _create_ray_job_operation(
        self, job_spec: Dict[str, Any], namespace: str = "default"
    ) -> Dict[str, Any]:
        """Execute Ray job creation operation using manifest generation."""
        # Use ManagedComponent validation method instead of ResourceManager's
        self._ensure_kuberay_ready()

        # Validate job specification
        if not job_spec:
            raise ValueError("Job specification is required")

        entrypoint = job_spec.get("entrypoint")
        if not entrypoint:
            raise ValueError("entrypoint is required in job specification")

        job_name = job_spec.get("job_name", "ray-job")

        # Convert job_spec to action format for manifest generation
        action = {
            "name": job_name,
            "namespace": namespace,
            "script": entrypoint,
            "runtime_env": job_spec.get("runtime_env"),
        }

        # Generate and apply manifest
        manifest = self._manifest_generator.generate_ray_job_manifest(
            f"create job {job_name}", action
        )

        apply_result = await self._manifest_generator.apply_manifest(
            manifest, namespace
        )

        if apply_result.get("status") != "success":
            raise RuntimeError(
                f"Failed to create Ray job: {apply_result.get('message')}"
            )

        return {
            "job_name": job_name,
            "namespace": namespace,
            "entrypoint": entrypoint,
            "runtime_env": job_spec.get("runtime_env"),
            "job_status": "creating",
            "manifest_applied": True,
            **apply_result,
        }

    async def _get_ray_job(
        self, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Get Ray job status."""
        # Use ManagedComponent validation method instead of ResourceManager's
        self._ensure_kuberay_ready()

        result = await self._manifest_generator.get_resource_status(
            "rayjob", name, namespace
        )

        if result.get("status") == "success":
            resource = result.get("resource", {})
            status = resource.get("status", {})

            # Extract detailed job status
            job_status_value = status.get("jobStatus", "Unknown")
            job_status = {
                "name": name,
                "namespace": namespace,
                "job_status": job_status_value,
                "ray_cluster_name": status.get("rayClusterName"),
                "job_deployment_status": status.get("jobDeploymentStatus", "Unknown"),
                "dashboard_url": status.get("dashboardURL"),
                "start_time": status.get("startTime"),
                "end_time": status.get("endTime"),
                "submission_id": status.get("submissionId"),
                "message": status.get("message"),
                "creation_timestamp": resource.get("metadata", {}).get(
                    "creationTimestamp"
                ),
            }

            # Add status flags for compatibility with tests
            running = job_status_value in ["RUNNING", "PENDING"]
            complete = job_status_value in ["SUCCEEDED", "FAILED", "STOPPED"]

            return self._ResponseFormatter.format_success_response(
                job=job_status,
                raw_resource=resource,
                running=running,
                complete=complete,
            )
        else:
            return result

    async def _list_ray_jobs(self, namespace: str = "default") -> Dict[str, Any]:
        """List Ray jobs."""
        # Use ManagedComponent validation method instead of ResourceManager's
        self._ensure_kuberay_ready()

        result = await self._manifest_generator.list_resources("rayjob", namespace)

        if result.get("status") == "success":
            jobs = []
            for resource_summary in result.get("resources", []):
                job_info = {
                    "name": resource_summary.get("name"),
                    "namespace": resource_summary.get("namespace"),
                    "job_status": resource_summary.get("status", {}).get(
                        "jobStatus", "Unknown"
                    ),
                    "creation_timestamp": resource_summary.get("creation_timestamp"),
                    "labels": resource_summary.get("labels", {}),
                }
                jobs.append(job_info)

            return self._ResponseFormatter.format_success_response(
                jobs=jobs, total_count=len(jobs), namespace=namespace
            )
        else:
            return result

    async def _delete_ray_job(
        self, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Delete Ray job."""
        # Use ManagedComponent validation method instead of ResourceManager's
        self._ensure_kuberay_ready()

        result = await self._manifest_generator.delete_resource(
            "rayjob", name, namespace
        )

        if result.get("status") == "success":
            return self._ResponseFormatter.format_success_response(
                job_name=name,
                namespace=namespace,
                deleted=True,
                deletion_timestamp=result.get("deletion_timestamp"),
                message=f"RayJob '{name}' deletion initiated",
            )
        else:
            return result

    async def _get_ray_job_logs(
        self, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Get Ray job logs."""
        # Use ManagedComponent validation method instead of ResourceManager's
        self._ensure_kuberay_ready()

        # First get the job to understand its current state
        job_result = await self._get_ray_job(name, namespace)
        if job_result.get("status") != "success":
            return job_result

        job_data = job_result.get("job", {})

        # Try to get cluster name from job status for log retrieval
        # This maintains compatibility with existing tests
        ray_cluster_name = None
        if job_result.get("raw_resource"):
            status = job_result["raw_resource"].get("status", {})
            ray_cluster_name = status.get("rayClusterName")

        if not ray_cluster_name:
            return self._ResponseFormatter.format_error_response(
                "get ray job logs",
                Exception(f"No Ray cluster associated with job '{name}'"),
            )

        # Try to get logs using Kubernetes client for compatibility with tests
        try:
            from kubernetes import client

            v1 = client.CoreV1Api()

            # Try to get job-specific pod logs
            pods = v1.list_namespaced_pod(
                namespace=namespace,
                label_selector=f"ray.io/cluster={ray_cluster_name},ray.io/job-name={name}",
            )

            logs = []
            for pod in pods.items:
                try:
                    pod_logs = v1.read_namespaced_pod_log(
                        name=pod.metadata.name,
                        namespace=namespace,
                        tail_lines=1000,
                        timestamps=True,
                    )
                    logs.append(f"=== Pod {pod.metadata.name} ===\n{pod_logs}")
                except Exception:
                    continue

            pod_logs_result = {"logs": "\n".join(logs), "status": "success"}

            # Check if we got job-specific pods or need to fall back
            if len(logs) > 0:
                # Found job-specific pods
                return self._ResponseFormatter.format_success_response(
                    job_name=name,
                    namespace=namespace,
                    ray_cluster_name=ray_cluster_name,
                    job_status=job_data.get("job_status"),
                    logs=pod_logs_result.get("logs", "No logs available"),
                    log_source="job_runner_pods",
                    pod_count=len(logs),
                    message=f"Retrieved logs for job '{name}' from cluster '{ray_cluster_name}'",
                )
            else:
                # Fallback to head node logs
                head_pods = v1.list_namespaced_pod(
                    namespace=namespace,
                    label_selector=f"ray.io/cluster={ray_cluster_name},ray.io/node-type=head",
                )

                head_logs = []
                for pod in head_pods.items:
                    try:
                        pod_logs = v1.read_namespaced_pod_log(
                            name=pod.metadata.name,
                            namespace=namespace,
                            tail_lines=1000,
                            timestamps=True,
                        )
                        head_logs.append(
                            f"=== Head Pod {pod.metadata.name} ===\n{pod_logs}"
                        )
                    except Exception:
                        continue

                return self._ResponseFormatter.format_success_response(
                    job_name=name,
                    namespace=namespace,
                    ray_cluster_name=ray_cluster_name,
                    job_status=job_data.get("job_status"),
                    logs="\n".join(head_logs) if head_logs else "No logs available",
                    log_source="head_node_filtered",
                    pod_count=len(head_logs),
                    message=f"Retrieved logs for job '{name}' from cluster '{ray_cluster_name}' head node",
                )

        except Exception as e:
            return self._ResponseFormatter.format_error_response(
                f"kubernetes logs for job {name}",
                e,
            )

    def _ensure_kuberay_ready(self) -> None:
        """Ensure KubeRay operator is available and ready."""
        self._ensure_kubernetes_available()

        # Try to connect to kubernetes
        if not self._is_kubernetes_ready():
            raise RuntimeError(
                "Kubernetes is not available or configured. Please check kubeconfig."
            )

        # For now, just check if we can connect to K8s
        # Future enhancement: check if KubeRay operator is actually running
