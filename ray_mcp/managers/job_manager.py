"""Pure prompt-driven job management for Ray clusters."""

import asyncio
from typing import Any, Dict

from ..config import get_config_manager_sync
from ..foundation.resource_manager import ResourceManager
from ..parsers import ActionParser


class JobManager(ResourceManager):
    """Pure prompt-driven Ray job management - no traditional APIs."""

    def __init__(self, unified_manager=None):
        super().__init__(enable_ray=True)
        self._config_manager = get_config_manager_sync()
        # Simple state tracking
        self._job_client = None
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

    # =================================================================
    # INTERNAL IMPLEMENTATION: All methods are now private
    # =================================================================

    async def _submit_job_from_prompt(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Submit job from parsed prompt action."""
        try:
            # Extract job specification
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
        """Submit a job to the Ray cluster."""
        try:
            if not self._is_ray_ready():
                return self._ResponseFormatter.format_error_response(
                    "submit job",
                    Exception("Ray cluster is not running. Start a cluster first."),
                )

            # Get or create job client
            job_client = await self._get_job_client()
            if not job_client:
                return self._ResponseFormatter.format_error_response(
                    "submit job", Exception("Could not create job client")
                )

            # Submit the job
            job_id = await asyncio.to_thread(
                job_client.submit_job,
                entrypoint=job_spec["entrypoint"],
                runtime_env=job_spec.get("runtime_env"),
                metadata=job_spec.get("metadata"),
                job_id=job_spec.get("job_id"),
            )

            return self._ResponseFormatter.format_success_response(
                job_id=job_id,
                entrypoint=job_spec["entrypoint"],
                job_status="submitted",
                message=f"Job {job_id} submitted successfully",
            )

        except Exception as e:
            return self._ResponseFormatter.format_error_response("submit job", e)

    async def _list_jobs(self) -> Dict[str, Any]:
        """List all jobs in the cluster."""
        try:
            if not self._is_ray_ready():
                return self._ResponseFormatter.format_error_response(
                    "list jobs", Exception("Ray cluster is not running")
                )

            job_client = await self._get_job_client()
            if not job_client:
                return self._ResponseFormatter.format_error_response(
                    "list jobs", Exception("Could not create job client")
                )

            jobs = await asyncio.to_thread(job_client.list_jobs)
            job_list = []

            # Handle both dict and list responses from Ray
            if isinstance(jobs, dict):
                for job_id, job_info in jobs.items():
                    job_list.append(
                        {
                            "job_id": job_id,
                            "status": (
                                job_info.status.value
                                if hasattr(job_info.status, "value")
                                else str(job_info.status)
                            ),
                            "entrypoint": getattr(job_info, "entrypoint", "unknown"),
                            "start_time": getattr(job_info, "start_time", None),
                            "end_time": getattr(job_info, "end_time", None),
                            "metadata": getattr(job_info, "metadata", {}),
                        }
                    )
            else:
                # Handle list response
                for job_info in jobs:
                    # Try different attributes to get job_id
                    job_id = (
                        getattr(job_info, "job_id", None)
                        or getattr(job_info, "submission_id", None)
                        or getattr(job_info, "id", None)
                        or "unknown"
                    )
                    job_list.append(
                        {
                            "job_id": job_id,
                            "status": (
                                job_info.status.value
                                if hasattr(job_info.status, "value")
                                else str(job_info.status)
                            ),
                            "entrypoint": getattr(job_info, "entrypoint", "unknown"),
                            "start_time": getattr(job_info, "start_time", None),
                            "end_time": getattr(job_info, "end_time", None),
                            "metadata": getattr(job_info, "metadata", {}),
                        }
                    )

            return self._ResponseFormatter.format_success_response(
                jobs=job_list,
                total_count=len(job_list),
                message=f"Found {len(job_list)} jobs",
            )

        except Exception as e:
            return self._ResponseFormatter.format_error_response("list jobs", e)

    async def _get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get status of a specific job."""
        try:
            if not self._is_ray_ready():
                return self._ResponseFormatter.format_error_response(
                    "get job status", Exception("Ray cluster is not running")
                )

            job_client = await self._get_job_client()
            if not job_client:
                return self._ResponseFormatter.format_error_response(
                    "get job status", Exception("Could not create job client")
                )

            job_info = await asyncio.to_thread(job_client.get_job_info, job_id)

            return self._ResponseFormatter.format_success_response(
                job_id=job_id,
                job_status=(
                    job_info.status.value
                    if hasattr(job_info.status, "value")
                    else str(job_info.status)
                ),
                entrypoint=getattr(job_info, "entrypoint", "unknown"),
                start_time=getattr(job_info, "start_time", None),
                end_time=getattr(job_info, "end_time", None),
                metadata=getattr(job_info, "metadata", {}),
                message=getattr(job_info, "message", None),
            )

        except Exception as e:
            return self._ResponseFormatter.format_error_response("get job status", e)

    async def _cancel_job(self, job_id: str) -> Dict[str, Any]:
        """Cancel a running job."""
        try:
            if not self._is_ray_ready():
                return self._ResponseFormatter.format_error_response(
                    "cancel job", Exception("Ray cluster is not running")
                )

            job_client = await self._get_job_client()
            if not job_client:
                return self._ResponseFormatter.format_error_response(
                    "cancel job", Exception("Could not create job client")
                )

            success = await asyncio.to_thread(job_client.stop_job, job_id)

            if success:
                return self._ResponseFormatter.format_success_response(
                    job_id=job_id, message=f"Job {job_id} cancelled successfully"
                )
            else:
                return self._ResponseFormatter.format_error_response(
                    "cancel job", Exception(f"Failed to cancel job {job_id}")
                )

        except Exception as e:
            return self._ResponseFormatter.format_error_response("cancel job", e)

    async def _get_job_logs(self, job_id: str) -> Dict[str, Any]:
        """Get logs for a specific job."""
        try:
            if not self._is_ray_ready():
                return self._ResponseFormatter.format_error_response(
                    "get job logs", Exception("Ray cluster is not running")
                )

            job_client = await self._get_job_client()
            if not job_client:
                return self._ResponseFormatter.format_error_response(
                    "get job logs", Exception("Could not create job client")
                )

            logs = await asyncio.to_thread(job_client.get_job_logs, job_id)

            return self._ResponseFormatter.format_success_response(
                job_id=job_id, logs=logs, message=f"Retrieved logs for job {job_id}"
            )

        except Exception as e:
            return self._ResponseFormatter.format_error_response("get job logs", e)

    async def _get_job_client(self):
        """Get or create job submission client."""
        try:
            if self._job_client:
                return self._job_client

            if not self._is_ray_ready():
                return None

            # Try to get dashboard URL for job client
            if not self._JobSubmissionClient:
                return None

            dashboard_url = self._get_dashboard_url()
            if dashboard_url:
                self._job_client = self._JobSubmissionClient(dashboard_url)
            else:
                # Try default dashboard URL
                self._job_client = self._JobSubmissionClient("http://127.0.0.1:8265")

            return self._job_client

        except Exception:
            return None

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
