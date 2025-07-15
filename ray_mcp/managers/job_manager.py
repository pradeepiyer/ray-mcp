"""Pure prompt-driven job management for Ray clusters using Dashboard API."""

from typing import Any, Dict

from ..config import get_config_manager_sync
from ..foundation.dashboard_client import DashboardAPIError, DashboardClient
from ..foundation.resource_manager import ResourceManager
from ..parsers import ActionParser


class JobManager(ResourceManager):
    """Pure prompt-driven Ray job management using Dashboard API."""

    def __init__(self, unified_manager=None):
        super().__init__(enable_ray=True)
        self._config_manager = get_config_manager_sync()
        self._unified_manager = unified_manager

    async def execute_request(self, prompt: str) -> Dict[str, Any]:
        """Execute job operations using natural language prompts.

        Examples:
            - "submit job with script train.py"
            - "list all running jobs"
            - "get logs for job raysubmit_123"
            - "cancel job raysubmit_456"
        """
        try:
            action = ActionParser.parse_job_action(prompt)
            operation = action["operation"]

            if operation == "submit":
                return await self._submit_job_from_prompt(action)
            elif operation == "list":
                return await self._list_jobs()
            elif operation == "get":
                job_id = action.get("job_id")
                if not job_id:
                    return {"status": "error", "message": "job_id required"}
                return await self._get_job_status(job_id)
            elif operation == "inspect":
                job_id = action.get("job_id")
                if not job_id:
                    return {"status": "error", "message": "job_id required"}
                return await self._get_job_status(job_id)
            elif operation == "cancel":
                job_id = action.get("job_id")
                if not job_id:
                    return {"status": "error", "message": "job_id required"}
                return await self._cancel_job(job_id)
            elif operation == "logs":
                job_id = action.get("job_id")
                if not job_id:
                    return {"status": "error", "message": "job_id required"}
                return await self._get_job_logs(job_id)
            else:
                return {"status": "error", "message": f"Unknown operation: {operation}"}

        except ValueError as e:
            return {"status": "error", "message": f"Could not parse request: {str(e)}"}
        except Exception as e:
            return self._ResponseFormatter.format_error_response("execute_request", e)

    async def _submit_job_from_prompt(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Submit job from parsed prompt action."""
        try:
            job_spec = {
                "entrypoint": action.get("script") or action.get("entrypoint"),
                "runtime_env": action.get("runtime_env", {}),
                "metadata": action.get("metadata", {}),
                "job_id": action.get("job_id"),
            }

            if not job_spec["entrypoint"]:
                return {"status": "error", "message": "script/entrypoint required"}

            return await self._submit_job(job_spec)

        except Exception as e:
            return self._ResponseFormatter.format_error_response(
                "submit job from prompt", e
            )

    async def _submit_job(self, job_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a job to the Ray cluster using Dashboard API."""
        try:
            if not self._is_ray_ready():
                return self._ResponseFormatter.format_error_response(
                    "submit job",
                    Exception("Ray cluster is not running. Start a cluster first."),
                )

            dashboard_url = self._get_dashboard_url()
            if not dashboard_url:
                return self._ResponseFormatter.format_error_response(
                    "submit job", Exception("Could not determine Ray dashboard URL")
                )

            async with DashboardClient(dashboard_url) as client:
                result = await client.submit_job(
                    entrypoint=job_spec["entrypoint"],
                    runtime_env=job_spec.get("runtime_env"),
                    job_id=job_spec.get("job_id"),
                    metadata=job_spec.get("metadata"),
                )

                # Dashboard API uses submission_id as the primary identifier
                submitted_job_id = result.get("submission_id", result.get("job_id"))

                return self._ResponseFormatter.format_success_response(
                    job_id=submitted_job_id,
                    entrypoint=job_spec["entrypoint"],
                    job_status="submitted",
                    message=f"Job submitted successfully",
                )

        except DashboardAPIError as e:
            return self._ResponseFormatter.format_error_response(
                "submit job", Exception(f"Dashboard API error: {e.message}")
            )
        except Exception as e:
            return self._ResponseFormatter.format_error_response("submit job", e)

    async def _list_jobs(self) -> Dict[str, Any]:
        """List all jobs in the cluster using Dashboard API."""
        try:
            if not self._is_ray_ready():
                return self._ResponseFormatter.format_error_response(
                    "list jobs", Exception("Ray cluster is not running")
                )

            dashboard_url = self._get_dashboard_url()
            if not dashboard_url:
                return self._ResponseFormatter.format_error_response(
                    "list jobs", Exception("Could not determine Ray dashboard URL")
                )

            async with DashboardClient(dashboard_url) as client:
                result = await client.list_jobs()

                # Transform Dashboard API response to match expected format
                job_list = []
                jobs_data = (
                    result if isinstance(result, list) else result.get("jobs", [])
                )

                for job in jobs_data:
                    if isinstance(job, dict):
                        # Dashboard API uses submission_id as the primary identifier
                        job_id = job.get("submission_id") or job.get("job_id")

                        job_list.append(
                            {
                                "job_id": job_id,
                                "status": job.get("status"),
                                "entrypoint": job.get("entrypoint", "unknown"),
                                "start_time": job.get("start_time"),
                                "end_time": job.get("end_time"),
                                "metadata": job.get("metadata", {}),
                            }
                        )

                return self._ResponseFormatter.format_success_response(
                    jobs=job_list,
                    total_count=len(job_list),
                    message=f"Found {len(job_list)} jobs",
                )

        except DashboardAPIError as e:
            return self._ResponseFormatter.format_error_response(
                "list jobs", Exception(f"Dashboard API error: {e.message}")
            )
        except Exception as e:
            return self._ResponseFormatter.format_error_response("list jobs", e)

    async def _get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get status of a specific job using Dashboard API."""
        try:
            if not self._is_ray_ready():
                return self._ResponseFormatter.format_error_response(
                    "get job status", Exception("Ray cluster is not running")
                )

            dashboard_url = self._get_dashboard_url()
            if not dashboard_url:
                return self._ResponseFormatter.format_error_response(
                    "get job status", Exception("Could not determine Ray dashboard URL")
                )

            async with DashboardClient(dashboard_url) as client:
                job_info = await client.get_job_info(job_id)

                return self._ResponseFormatter.format_success_response(
                    job_id=job_id,
                    job_status=job_info.get("status"),
                    entrypoint=job_info.get("entrypoint", "unknown"),
                    start_time=job_info.get("start_time"),
                    end_time=job_info.get("end_time"),
                    metadata=job_info.get("metadata", {}),
                    message=job_info.get("message"),
                )

        except DashboardAPIError as e:
            if e.status_code == 404:
                return self._ResponseFormatter.format_error_response(
                    "get job status", Exception(f"Job {job_id} not found")
                )
            return self._ResponseFormatter.format_error_response(
                "get job status", Exception(f"Dashboard API error: {e.message}")
            )
        except Exception as e:
            return self._ResponseFormatter.format_error_response("get job status", e)

    async def _cancel_job(self, job_id: str) -> Dict[str, Any]:
        """Cancel a running job using Dashboard API."""
        try:
            if not self._is_ray_ready():
                return self._ResponseFormatter.format_error_response(
                    "cancel job", Exception("Ray cluster is not running")
                )

            dashboard_url = self._get_dashboard_url()
            if not dashboard_url:
                return self._ResponseFormatter.format_error_response(
                    "cancel job", Exception("Could not determine Ray dashboard URL")
                )

            async with DashboardClient(dashboard_url) as client:
                result = await client.stop_job(job_id)

                return self._ResponseFormatter.format_success_response(
                    job_id=job_id, message=f"Job {job_id} cancellation requested"
                )

        except DashboardAPIError as e:
            if e.status_code == 404:
                return self._ResponseFormatter.format_error_response(
                    "cancel job", Exception(f"Job {job_id} not found")
                )
            return self._ResponseFormatter.format_error_response(
                "cancel job", Exception(f"Dashboard API error: {e.message}")
            )
        except Exception as e:
            return self._ResponseFormatter.format_error_response("cancel job", e)

    async def _get_job_logs(self, job_id: str) -> Dict[str, Any]:
        """Get logs for a specific job using Dashboard API."""
        try:
            if not self._is_ray_ready():
                return self._ResponseFormatter.format_error_response(
                    "get job logs", Exception("Ray cluster is not running")
                )

            dashboard_url = self._get_dashboard_url()
            if not dashboard_url:
                return self._ResponseFormatter.format_error_response(
                    "get job logs", Exception("Could not determine Ray dashboard URL")
                )

            async with DashboardClient(dashboard_url) as client:
                logs_result = await client.get_job_logs(job_id)

                # Handle different response formats from Dashboard API
                logs = logs_result.get("logs", str(logs_result))

                return self._ResponseFormatter.format_success_response(
                    job_id=job_id, logs=logs, message=f"Retrieved logs for job {job_id}"
                )

        except DashboardAPIError as e:
            if e.status_code == 404:
                return self._ResponseFormatter.format_error_response(
                    "get job logs", Exception(f"Job {job_id} not found")
                )
            return self._ResponseFormatter.format_error_response(
                "get job logs", Exception(f"Dashboard API error: {e.message}")
            )
        except Exception as e:
            return self._ResponseFormatter.format_error_response("get job logs", e)

    def _get_dashboard_url(self) -> str:
        """Get dashboard URL for job client."""
        try:
            if not self._is_ray_ready():
                return "http://127.0.0.1:8265"

            # First try to get from unified manager if available
            if self._unified_manager and hasattr(
                self._unified_manager, "get_dashboard_url"
            ):
                dashboard_url = self._unified_manager.get_dashboard_url()
                if dashboard_url != "http://127.0.0.1:8265":  # Not the default fallback
                    return dashboard_url

            # Try to get dashboard URL from Ray
            runtime_context = self._ray.get_runtime_context()
            if hasattr(runtime_context, "dashboard_url"):
                return runtime_context.dashboard_url

            # Fallback to default
            return "http://127.0.0.1:8265"

        except Exception:
            return "http://127.0.0.1:8265"
