"""Centralized job management for Ray."""

import asyncio
import inspect
from typing import Any, Dict, List, Optional

from ..foundation.base_managers import ResourceManager
from ..foundation.interfaces import JobManager, ManagedComponent


class RayJobManager(ResourceManager, JobManager, ManagedComponent):
    """Manages Ray job operations with clean separation of concerns."""

    def __init__(self, state_manager):
        # Initialize both parent classes
        ResourceManager.__init__(
            self,
            state_manager,
            enable_ray=True,
            enable_kubernetes=False,
            enable_cloud=False,
        )
        ManagedComponent.__init__(self, state_manager)

        self._job_client: Optional[Any] = None
        self._job_client_lock = asyncio.Lock()  # Synchronize job client initialization

    @property
    def _handle_exceptions(self):
        """Get the exception handler decorator."""
        return self._ResponseFormatter.handle_exceptions

    async def submit_job(
        self,
        entrypoint: str,
        runtime_env: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Submit a job to the Ray cluster."""
        return await self._execute_operation(
            "submit job",
            self._submit_job_operation,
            entrypoint,
            runtime_env,
            job_id,
            metadata,
            **kwargs,
        )

    async def list_jobs(self) -> Dict[str, Any]:
        """List all jobs in the Ray cluster."""
        return await self._execute_operation("list jobs", self._list_jobs_operation)

    async def cancel_job(self, job_id: str) -> Dict[str, Any]:
        """Cancel a running job."""
        return await self._execute_operation(
            "cancel job", self._cancel_job_operation, job_id
        )

    async def inspect_job(self, job_id: str, mode: str = "status") -> Dict[str, Any]:
        """Inspect job details with different modes."""
        return await self._execute_operation(
            "inspect job", self._inspect_job_operation, job_id, mode
        )

    async def _submit_job_operation(
        self,
        entrypoint: str,
        runtime_env: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute job submission operation."""
        # Use ManagedComponent validation method instead of ResourceManager's
        self._ensure_ray_initialized()

        # Validate entrypoint
        validation_error = self._validate_entrypoint(entrypoint)
        if validation_error:
            return validation_error

        # Get or create job client
        job_client = await self._get_or_create_job_client("submit job")
        if not job_client:
            raise RuntimeError("Failed to initialize job client")

        # Filter kwargs to only include valid parameters for submit_job
        sig = inspect.signature(job_client.submit_job)
        valid_params = set(sig.parameters.keys())
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_params}

        submitted_job_id = job_client.submit_job(
            entrypoint=entrypoint,
            runtime_env=runtime_env,
            job_id=job_id,
            metadata=metadata,
            **filtered_kwargs,
        )

        return {
            "message": f"Job submitted successfully with ID: {submitted_job_id}",
            "job_id": submitted_job_id,
            "entrypoint": entrypoint,
            "runtime_env": runtime_env,
            "metadata": metadata,
        }

    async def _list_jobs_operation(self) -> Dict[str, Any]:
        """Execute list jobs operation."""
        # Use ManagedComponent validation method instead of ResourceManager's
        self._ensure_ray_initialized()

        job_client = await self._get_or_create_job_client("list jobs")
        if not job_client:
            raise RuntimeError("Failed to initialize job client")

        jobs = job_client.list_jobs()

        formatted_jobs = []
        for job in jobs:
            formatted_job = self._format_job_info(job)
            formatted_jobs.append(formatted_job)

        return {
            "message": f"Found {len(formatted_jobs)} jobs",
            "jobs": formatted_jobs,
            "job_count": len(formatted_jobs),
        }

    async def _cancel_job_operation(self, job_id: str) -> Dict[str, Any]:
        """Execute cancel job operation."""
        # Use ManagedComponent validation method instead of ResourceManager's
        self._ensure_ray_initialized()

        # Validate job ID
        validation_error = self._validate_job_id(job_id, "cancel job")
        if validation_error:
            return validation_error

        job_client = await self._get_or_create_job_client("cancel job")
        if not job_client:
            raise RuntimeError("Failed to initialize job client")

        success = job_client.stop_job(job_id)

        if success:
            return {
                "message": f"Job {job_id} cancelled successfully",
                "job_id": job_id,
                "cancelled": True,
            }
        else:
            raise RuntimeError(f"Failed to cancel job {job_id}")

    async def _inspect_job_operation(
        self, job_id: str, mode: str = "status"
    ) -> Dict[str, Any]:
        """Execute inspect job operation."""
        # Use ManagedComponent validation method instead of ResourceManager's
        self._ensure_ray_initialized()

        # Validate job ID
        validation_error = self._validate_job_id(job_id, "inspect job")
        if validation_error:
            return validation_error

        job_client = await self._get_or_create_job_client("inspect job")
        if not job_client:
            raise RuntimeError("Failed to initialize job client")

        # Get job details
        job_details = job_client.get_job_info(job_id)
        formatted_job = self._format_job_info(job_details)

        result = {
            "message": f"Job {job_id} inspection completed",
            "job_id": job_id,
            "job_info": formatted_job,
            "inspection_mode": mode,
        }

        # Add mode-specific information
        if mode in ["logs", "debug"]:
            try:
                logs = job_client.get_job_logs(job_id)
                result["logs"] = logs
            except Exception as e:
                result["logs_error"] = str(e)

        if mode == "debug":
            # Add debug-specific information
            result["debug_info"] = {
                "runtime_env": formatted_job.get("runtime_env"),
                "entrypoint": formatted_job.get("entrypoint"),
                "metadata": formatted_job.get("metadata", {}),
            }

        return result

    async def _get_or_create_job_client(self, operation_name: str) -> Optional[Any]:
        """Get or create job submission client."""
        self._ensure_ray_available()

        if not self._JobSubmissionClient:
            self._log_error(
                operation_name,
                RuntimeError("Ray job submission client is not available"),
            )
            return None

        # Return existing client if available
        if self._get_state_value("job_client"):
            return self._get_state_value("job_client")

        # Use lock to synchronize client initialization
        async with self._job_client_lock:
            # Double-check pattern - another task might have initialized while waiting
            if self._get_state_value("job_client"):
                return self._get_state_value("job_client")

            # Create new client
            dashboard_url = self._get_state_value("dashboard_url")
            if not dashboard_url:
                self._log_warning(
                    operation_name,
                    "Dashboard URL not available, attempting to initialize",
                )
                dashboard_url = await self._initialize_job_client_if_available()

                if not dashboard_url:
                    return None

            # Initialize client with retry logic
            job_client = await self._initialize_job_client_with_retry(dashboard_url)
            if job_client:
                self._update_state(job_client=job_client)

            return job_client

    async def _initialize_job_client_with_retry(
        self, dashboard_url: str, max_retries: int = 3, retry_delay: float = 1.0
    ) -> Optional[Any]:
        """Initialize job client with retry logic."""

        async def _init_client():
            if not self._JobSubmissionClient:
                raise RuntimeError("JobSubmissionClient is not available")
            job_client = self._JobSubmissionClient(dashboard_url)
            # Test the connection by listing jobs
            _ = job_client.list_jobs()
            return job_client

        try:
            return await self._retry_operation(
                _init_client, max_retries, retry_delay, "job_client_init"
            )
        except Exception as e:
            self._log_error(
                "job_client_init",
                RuntimeError(
                    f"Failed to initialize job client after {max_retries} attempts"
                ),
            )
            return None

    async def _initialize_job_client_if_available(self) -> Optional[str]:
        """Try to initialize job client if Ray cluster is available."""
        try:
            if not self._is_ray_initialized():
                return None

            # Get dashboard URL from Ray cluster information
            runtime_context = self._ray.get_runtime_context()
            if not runtime_context:
                return None

            # Try to get dashboard URL from existing state first
            existing_dashboard_url = self._get_state_value("dashboard_url")
            if existing_dashboard_url:
                return existing_dashboard_url

            # Extract dashboard URL from cluster context
            # Check if we can get GCS address to determine the host
            gcs_address = getattr(runtime_context, "gcs_address", None)
            if gcs_address:
                # Parse GCS address to get host (format: host:port)
                try:
                    host = (
                        gcs_address.split(":")[0] if ":" in gcs_address else "127.0.0.1"
                    )
                    # Use standard Ray dashboard port (8265)
                    dashboard_url = f"http://{host}:8265"
                except Exception:
                    # Fallback to localhost if parsing fails
                    dashboard_url = "http://127.0.0.1:8265"
            else:
                # Fallback to localhost if no GCS address available
                dashboard_url = "http://127.0.0.1:8265"

            # Store the dashboard URL in state for future use
            self._update_state(dashboard_url=dashboard_url)
            return dashboard_url

        except Exception as e:
            self._log_error("initialize job client", e)
            return None

    def _format_job_info(self, job) -> Dict[str, Any]:
        """Format job information for consistent output."""
        if hasattr(job, "__dict__"):
            job_dict = job.__dict__
        else:
            job_dict = job

        return {
            "job_id": job_dict.get("job_id") or job_dict.get("submission_id"),
            "status": str(job_dict.get("status", "unknown")),
            "entrypoint": job_dict.get("entrypoint"),
            "submission_time": job_dict.get("submission_time"),
            "start_time": job_dict.get("start_time"),
            "end_time": job_dict.get("end_time"),
            "metadata": job_dict.get("metadata", {}),
            "runtime_env": job_dict.get("runtime_env"),
            "message": job_dict.get("message", ""),
        }
