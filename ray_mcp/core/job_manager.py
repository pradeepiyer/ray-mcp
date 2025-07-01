"""Ray job management with focused responsibilities."""

import inspect
from typing import Any, Dict, Optional

try:
    from ..logging_utils import LoggingUtility, ResponseFormatter
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from logging_utils import LoggingUtility, ResponseFormatter
from .interfaces import JobManager, StateManager, RayComponent

# Import Ray modules with error handling
try:
    import ray
    from ray.job_submission import JobSubmissionClient
    RAY_AVAILABLE = True
except ImportError:
    RAY_AVAILABLE = False
    ray = None
    JobSubmissionClient = None


class RayJobManager(RayComponent, JobManager):
    """Manages Ray job operations with clean separation of concerns."""
    
    def __init__(self, state_manager: StateManager):
        super().__init__(state_manager)
        self._response_formatter = ResponseFormatter()
        self._job_client: Optional[JobSubmissionClient] = None
    
    @ResponseFormatter.handle_exceptions("submit job")
    async def submit_job(
        self,
        entrypoint: str,
        runtime_env: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Submit a job to the Ray cluster."""
        self._ensure_initialized()
        
        # Validate entrypoint
        validation_error = self._validate_entrypoint(entrypoint)
        if validation_error:
            return validation_error
        
        # Get or create job client
        job_client = await self._get_or_create_job_client("submit job")
        if not job_client:
            return self._response_formatter.format_error_response(
                "submit job", Exception("Failed to initialize job client")
            )
        
        return await self._execute_job_operation(
            "submit job",
            self._submit_job_operation,
            job_client,
            entrypoint,
            runtime_env=runtime_env,
            job_id=job_id,
            metadata=metadata,
            **kwargs
        )
    
    @ResponseFormatter.handle_exceptions("list jobs")
    async def list_jobs(self) -> Dict[str, Any]:
        """List all jobs in the Ray cluster."""
        self._ensure_initialized()
        
        job_client = await self._get_or_create_job_client("list jobs")
        if not job_client:
            return self._response_formatter.format_error_response(
                "list jobs", Exception("Failed to initialize job client")
            )
        
        return await self._execute_job_operation(
            "list jobs", self._list_jobs_operation, job_client
        )
    
    @ResponseFormatter.handle_exceptions("cancel job")
    async def cancel_job(self, job_id: str) -> Dict[str, Any]:
        """Cancel a running job."""
        self._ensure_initialized()
        
        # Validate job ID
        validation_error = self._validate_job_id(job_id, "cancel job")
        if validation_error:
            return validation_error
        
        job_client = await self._get_or_create_job_client("cancel job")
        if not job_client:
            return self._response_formatter.format_error_response(
                "cancel job", Exception("Failed to initialize job client")
            )
        
        return await self._execute_job_operation(
            "cancel job", self._cancel_job_operation, job_client, job_id
        )
    
    @ResponseFormatter.handle_exceptions("inspect job")
    async def inspect_job(self, job_id: str, mode: str = "status") -> Dict[str, Any]:
        """Inspect job details with different modes."""
        self._ensure_initialized()
        
        # Validate job ID
        validation_error = self._validate_job_id(job_id, "inspect job")
        if validation_error:
            return validation_error
        
        job_client = await self._get_or_create_job_client("inspect job")
        if not job_client:
            return self._response_formatter.format_error_response(
                "inspect job", Exception("Failed to initialize job client")
            )
        
        return await self._execute_job_operation(
            "inspect job", self._inspect_job_operation, job_client, job_id, mode
        )
    
    async def _get_or_create_job_client(self, operation_name: str) -> Optional[JobSubmissionClient]:
        """Get or create job submission client."""
        if not RAY_AVAILABLE or not JobSubmissionClient:
            LoggingUtility.log_error(
                operation_name, 
                Exception("Ray job submission client is not available")
            )
            return None
        
        # Return existing client if available
        state = self.state_manager.get_state()
        if state.get("job_client"):
            return state["job_client"]
        
        # Create new client
        dashboard_url = state.get("dashboard_url")
        if not dashboard_url:
            LoggingUtility.log_warning(
                operation_name, "Dashboard URL not available, attempting to initialize"
            )
            dashboard_url = await self._initialize_job_client_if_available()
            if not dashboard_url:
                return None
        
        # Initialize client with retry logic
        job_client = await self._initialize_job_client_with_retry(dashboard_url)
        if job_client:
            self.state_manager.update_state(job_client=job_client)
        
        return job_client
    
    async def _initialize_job_client_with_retry(
        self, dashboard_url: str, max_retries: int = 3, retry_delay: float = 1.0
    ) -> Optional[JobSubmissionClient]:
        """Initialize job client with retry logic."""
        import asyncio
        
        for attempt in range(max_retries):
            try:
                LoggingUtility.log_info(
                    "job_client_init", 
                    f"Initializing job client (attempt {attempt + 1}/{max_retries})"
                )
                
                # Create client
                job_client = JobSubmissionClient(dashboard_url)
                
                # Test the connection by listing jobs
                _ = job_client.list_jobs()
                
                LoggingUtility.log_info("job_client_init", "Job client initialized successfully")
                return job_client
                
            except Exception as e:
                LoggingUtility.log_warning(
                    "job_client_init",
                    f"Attempt {attempt + 1} failed: {e}"
                )
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
        
        LoggingUtility.log_error(
            "job_client_init", 
            Exception(f"Failed to initialize job client after {max_retries} attempts")
        )
        return None
    
    async def _initialize_job_client_if_available(self) -> Optional[str]:
        """Try to initialize job client if Ray cluster is available."""
        try:
            if not ray or not ray.is_initialized():
                return None
            
            # Try to get dashboard URL from Ray
            runtime_context = ray.get_runtime_context()
            if not runtime_context:
                return None
            
            # For now, assume standard dashboard port
            # In a real implementation, this would need to be extracted from cluster info
            dashboard_url = "http://127.0.0.1:8265"
            
            self.state_manager.update_state(dashboard_url=dashboard_url)
            return dashboard_url
            
        except Exception as e:
            LoggingUtility.log_error("initialize job client", e)
            return None
    
    async def _execute_job_operation(
        self, operation_name: str, job_operation_func, *args, **kwargs
    ) -> Dict[str, Any]:
        """Execute a job operation with standardized error handling."""
        try:
            result = await job_operation_func(*args, **kwargs)
            return self._response_formatter.format_success_response(**result)
        except Exception as e:
            LoggingUtility.log_error(operation_name, e)
            return self._response_formatter.format_error_response(operation_name, e)
    
    async def _submit_job_operation(
        self,
        job_client: JobSubmissionClient,
        entrypoint: str,
        runtime_env: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute job submission operation."""
        # Filter kwargs to only include valid parameters for submit_job
        sig = inspect.signature(job_client.submit_job)
        valid_params = set(sig.parameters.keys())
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_params}
        
        submitted_job_id = job_client.submit_job(
            entrypoint=entrypoint,
            runtime_env=runtime_env,
            job_id=job_id,
            metadata=metadata,
            **filtered_kwargs
        )
        
        return {
            "message": f"Job submitted successfully with ID: {submitted_job_id}",
            "job_id": submitted_job_id,
            "entrypoint": entrypoint,
            "runtime_env": runtime_env,
            "metadata": metadata,
        }
    
    async def _list_jobs_operation(self, job_client: JobSubmissionClient) -> Dict[str, Any]:
        """Execute list jobs operation."""
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
    
    async def _cancel_job_operation(
        self, job_client: JobSubmissionClient, job_id: str
    ) -> Dict[str, Any]:
        """Execute cancel job operation."""
        success = job_client.stop_job(job_id)
        
        if success:
            return {
                "message": f"Job {job_id} cancelled successfully",
                "job_id": job_id,
                "cancelled": True,
            }
        else:
            raise Exception(f"Failed to cancel job {job_id}")
    
    async def _inspect_job_operation(
        self, job_client: JobSubmissionClient, job_id: str, mode: str = "status"
    ) -> Dict[str, Any]:
        """Execute inspect job operation."""
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
    
    def _format_job_info(self, job) -> Dict[str, Any]:
        """Format job information for consistent output."""
        if hasattr(job, '__dict__'):
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
    
    def _validate_job_id(self, job_id: str, operation_name: str) -> Optional[Dict[str, Any]]:
        """Validate job ID format."""
        if not job_id or not isinstance(job_id, str) or not job_id.strip():
            return self._response_formatter.format_validation_error(
                f"Invalid job_id for {operation_name}: must be a non-empty string"
            )
        return None
    
    def _validate_entrypoint(self, entrypoint: str) -> Optional[Dict[str, Any]]:
        """Validate job entrypoint."""
        if not entrypoint or not isinstance(entrypoint, str) or not entrypoint.strip():
            return self._response_formatter.format_validation_error(
                "Entrypoint must be a non-empty string"
            )
        return None 