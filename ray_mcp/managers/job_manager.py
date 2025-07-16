"""Pure prompt-driven job management for Ray clusters using Dashboard API."""

from typing import Any

from ..config import config
from ..foundation.base_execute_mixin import BaseExecuteRequestMixin
from ..foundation.dashboard_client import DashboardAPIError, DashboardClient
from ..foundation.import_utils import ray
from ..foundation.logging_utils import error_response, success_response
from ..foundation.resource_manager import ResourceManager
from ..llm_parser import get_parser


class JobManager(ResourceManager, BaseExecuteRequestMixin):
    """Pure prompt-driven Ray job management using Dashboard API."""

    def __init__(self, unified_manager=None):
        super().__init__(enable_ray=True)
        self._unified_manager = unified_manager

    def get_action_parser(self):
        """Get the action parser for job operations."""
        return get_parser().parse_job_action

    def get_operation_handlers(self) -> dict[str, Any]:
        """Get mapping of operation names to handler methods."""
        return {
            "submit": self._submit_job_from_prompt,
            "list": self._list_jobs,
            "get": self._handle_get_job,
            "inspect": self._handle_get_job,
            "cancel": self._handle_cancel_job,
            "logs": self._handle_get_logs,
        }

    async def _handle_get_job(self, action: dict[str, Any]) -> dict[str, Any]:
        """Handle get/inspect job operation with validation."""
        job_id = action.get("job_id")
        if not job_id:
            return error_response("job_id required")
        return await self._get_job_status(job_id)

    async def _handle_cancel_job(self, action: dict[str, Any]) -> dict[str, Any]:
        """Handle cancel job operation with validation."""
        job_id = action.get("job_id")
        if not job_id:
            return error_response("job_id required")
        return await self._cancel_job(job_id)

    async def _handle_get_logs(self, action: dict[str, Any]) -> dict[str, Any]:
        """Handle get logs operation with validation."""
        job_id = action.get("job_id")
        if not job_id:
            return error_response("job_id required")
        return await self._get_job_logs(job_id)

    async def _submit_job_from_prompt(self, action: dict[str, Any]) -> dict[str, Any]:
        """Submit job from parsed prompt action."""
        try:
            job_spec = {
                "entrypoint": action.get("script") or action.get("entrypoint"),
                "runtime_env": action.get("runtime_env", {}),
                "metadata": action.get("metadata", {}),
                "job_id": action.get("job_id"),
            }

            if not job_spec["entrypoint"]:
                return error_response("script/entrypoint required")

            return await self._submit_job(job_spec)

        except Exception as e:
            return self._handle_error("submit job from prompt", e)

    async def _submit_job(self, job_spec: dict[str, Any]) -> dict[str, Any]:
        """Submit a job to the Ray cluster using Dashboard API."""
        try:
            if not self._is_ray_ready():
                return error_response(
                    "Ray cluster is not running. Start a cluster first."
                )

            dashboard_url = self._get_dashboard_url()
            if not dashboard_url:
                return error_response("Could not determine Ray dashboard URL")

            async with DashboardClient(dashboard_url) as client:
                result = await client.submit_job(
                    entrypoint=job_spec["entrypoint"],
                    runtime_env=job_spec.get("runtime_env"),
                    job_id=job_spec.get("job_id"),
                    metadata=job_spec.get("metadata"),
                )

                # Dashboard API uses submission_id as the primary identifier
                submitted_job_id = result.get("submission_id", result.get("job_id"))

                return success_response(
                    job_id=submitted_job_id,
                    entrypoint=job_spec["entrypoint"],
                    job_status="submitted",
                    message=f"Job submitted successfully",
                )

        except DashboardAPIError as e:
            return error_response(f"Dashboard API error: {e.message}")
        except Exception as e:
            return self._handle_error("submit job", e)

    async def _list_jobs(self, action: dict[str, Any]) -> dict[str, Any]:
        """List all jobs in the cluster using Dashboard API."""
        try:
            if not self._is_ray_ready():
                return error_response("Ray cluster is not running")

            dashboard_url = self._get_dashboard_url()
            if not dashboard_url:
                return error_response("Could not determine Ray dashboard URL")

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

                return success_response(
                    jobs=job_list,
                    total_count=len(job_list),
                    message=f"Found {len(job_list)} jobs",
                )

        except DashboardAPIError as e:
            return error_response(f"Dashboard API error: {e.message}")
        except Exception as e:
            return self._handle_error("list jobs", e)

    async def _get_job_status(self, job_id: str) -> dict[str, Any]:
        """Get status of a specific job using Dashboard API."""
        try:
            if not self._is_ray_ready():
                return error_response("Ray cluster is not running")

            dashboard_url = self._get_dashboard_url()
            if not dashboard_url:
                return error_response("Could not determine Ray dashboard URL")

            async with DashboardClient(dashboard_url) as client:
                job_info = await client.get_job_info(job_id)

                return success_response(
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
                return error_response(f"Job {job_id} not found")
            return error_response(f"Dashboard API error: {e.message}")
        except Exception as e:
            return self._handle_error("get job status", e)

    async def _cancel_job(self, job_id: str) -> dict[str, Any]:
        """Cancel a running job using Dashboard API."""
        try:
            if not self._is_ray_ready():
                return error_response("Ray cluster is not running")

            dashboard_url = self._get_dashboard_url()
            if not dashboard_url:
                return error_response("Could not determine Ray dashboard URL")

            async with DashboardClient(dashboard_url) as client:
                result = await client.stop_job(job_id)

                return success_response(
                    job_id=job_id, message=f"Job {job_id} cancellation requested"
                )

        except DashboardAPIError as e:
            if e.status_code == 404:
                return error_response(f"Job {job_id} not found")
            return error_response(f"Dashboard API error: {e.message}")
        except Exception as e:
            return self._handle_error("cancel job", e)

    async def _get_job_logs(self, job_id: str) -> dict[str, Any]:
        """Get logs for a specific job using Dashboard API."""
        try:
            if not self._is_ray_ready():
                return error_response("Ray cluster is not running")

            dashboard_url = self._get_dashboard_url()
            if not dashboard_url:
                return error_response("Could not determine Ray dashboard URL")

            async with DashboardClient(dashboard_url) as client:
                logs_result = await client.get_job_logs(job_id)

                # Handle different response formats from Dashboard API
                logs = logs_result.get("logs", str(logs_result))

                return success_response(
                    job_id=job_id, logs=logs, message=f"Retrieved logs for job {job_id}"
                )

        except DashboardAPIError as e:
            if e.status_code == 404:
                return error_response(f"Job {job_id} not found")
            return error_response(f"Dashboard API error: {e.message}")
        except Exception as e:
            return self._handle_error("get job logs", e)

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

            # Fallback to default port - JobManager doesn't manage Ray clusters directly,
            # so it can't access the dashboard URL from ray.init() return value.
            # The proper way is to get it from the unified manager (above).
            return "http://127.0.0.1:8265"

        except Exception:
            return "http://127.0.0.1:8265"
