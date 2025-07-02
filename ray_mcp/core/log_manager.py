"""Centralized log management for Ray clusters."""

from typing import TYPE_CHECKING, Any, Dict, Optional

# Use TYPE_CHECKING to avoid runtime issues with imports
if TYPE_CHECKING:
    from ray.job_submission import JobSubmissionClient
else:
    JobSubmissionClient = None

try:
    from ..logging_utils import LoggingUtility, LogProcessor, ResponseFormatter
except ImportError:
    # Fallback for direct execution
    import os
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from logging_utils import LoggingUtility, LogProcessor, ResponseFormatter

from .interfaces import LogManager, RayComponent, StateManager

# Import Ray modules with error handling
try:
    import ray
    from ray.job_submission import JobSubmissionClient as _JobSubmissionClient

    RAY_AVAILABLE = True
    JobSubmissionClient = _JobSubmissionClient
except ImportError:
    RAY_AVAILABLE = False
    ray = None
    JobSubmissionClient = None


class RayLogManager(RayComponent, LogManager):
    """Manages log retrieval operations with unified patterns and memory protection."""

    def __init__(self, state_manager: StateManager):
        super().__init__(state_manager)
        self._log_processor = LogProcessor()
        self._response_formatter = ResponseFormatter()

    @ResponseFormatter.handle_exceptions("retrieve logs")
    async def retrieve_logs(
        self,
        identifier: str,
        log_type: str = "job",
        num_lines: int = 100,
        include_errors: bool = False,
        max_size_mb: int = 10,
        **kwargs,
    ) -> Dict[str, Any]:
        """Retrieve logs from Ray cluster with comprehensive error analysis."""
        # Validate parameters
        validation_error = self._validate_log_retrieval_params(
            identifier, log_type, num_lines, max_size_mb
        )
        if validation_error:
            return validation_error

        # Only job logs are supported
        if log_type == "job":
            return await self._retrieve_job_logs_unified(
                identifier, num_lines, include_errors, max_size_mb
            )
        else:
            return self._response_formatter.format_validation_error(
                f"Invalid log_type: {log_type}. Only 'job' is supported"
            )

    @ResponseFormatter.handle_exceptions("retrieve logs paginated")
    async def retrieve_logs_paginated(
        self,
        identifier: str,
        log_type: str = "job",
        page: int = 1,
        page_size: int = 100,
        max_size_mb: int = 10,
        include_errors: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Retrieve logs with pagination support for large log files."""
        # Validate parameters
        validation_error = self._validate_log_retrieval_params(
            identifier, log_type, 0, max_size_mb, page, page_size
        )
        if validation_error:
            return validation_error

        # Only job logs are supported
        if log_type == "job":
            return await self._retrieve_job_logs_paginated(
                identifier, page, page_size, max_size_mb, include_errors
            )
        else:
            return self._response_formatter.format_validation_error(
                f"Invalid log_type: {log_type}. Only 'job' is supported"
            )

    async def _retrieve_job_logs_unified(
        self,
        job_id: str,
        num_lines: int = 100,
        include_errors: bool = False,
        max_size_mb: int = 10,
    ) -> Dict[str, Any]:
        """Unified job log retrieval with error analysis."""
        self._ensure_initialized()

        try:
            # Get job client
            job_client = await self._get_job_client()
            if not job_client:
                return self._create_error_log_response(
                    "job",
                    job_id,
                    num_lines,
                    max_size_mb,
                    additional_info={"error": "Job client not available"},
                )

            # Retrieve logs
            raw_logs = job_client.get_job_logs(job_id)

            # Process logs with size and line limits
            processed_logs = self._log_processor.stream_logs_with_limits(
                raw_logs, num_lines, max_size_mb
            )

            result = {
                "status": "success",
                "log_type": "job",
                "identifier": job_id,
                "logs": processed_logs,
                "num_lines_retrieved": len(processed_logs.split("\n")),
                "max_size_mb": max_size_mb,
            }

            # Add error analysis if requested
            if include_errors and processed_logs:
                result["error_analysis"] = self._analyze_job_logs(processed_logs)

            return result

        except Exception as e:
            LoggingUtility.log_error("retrieve job logs", e)
            return self._create_error_log_response(
                "job", job_id, num_lines, max_size_mb, additional_info={"error": str(e)}
            )

    async def _retrieve_job_logs_paginated(
        self,
        job_id: str,
        page: int = 1,
        page_size: int = 100,
        max_size_mb: int = 10,
        include_errors: bool = False,
    ) -> Dict[str, Any]:
        """Retrieve job logs with pagination support."""
        self._ensure_initialized()

        try:
            # Get job client
            job_client = await self._get_job_client()
            if not job_client:
                return self._create_error_log_response(
                    "job",
                    job_id,
                    0,
                    max_size_mb,
                    page,
                    page_size,
                    additional_info={"error": "Job client not available"},
                )

            # Retrieve logs
            raw_logs = job_client.get_job_logs(job_id)

            # Process logs with pagination
            paginated_result = await self._log_processor.stream_logs_with_pagination(
                raw_logs, page, page_size, max_size_mb
            )

            if paginated_result.get("status") == "error":
                return paginated_result

            # Add job-specific information
            paginated_result.update(
                {
                    "log_type": "job",
                    "identifier": job_id,
                }
            )

            # Add error analysis if requested and we have logs
            if include_errors and paginated_result.get("logs"):
                paginated_result["error_analysis"] = self._analyze_job_logs(
                    paginated_result["logs"]
                )

            return paginated_result

        except Exception as e:
            LoggingUtility.log_error("retrieve job logs paginated", e)
            return self._create_error_log_response(
                "job",
                job_id,
                0,
                max_size_mb,
                page,
                page_size,
                additional_info={"error": str(e)},
            )

    async def _get_job_client(self) -> Optional[Any]:
        """Get the job submission client from state."""
        if not RAY_AVAILABLE or not JobSubmissionClient:
            return None

        state = self.state_manager.get_state()
        job_client = state.get("job_client")

        if not job_client:
            # Try to create a basic client if we have dashboard URL
            dashboard_url = state.get("dashboard_url")
            if dashboard_url:
                try:
                    job_client = JobSubmissionClient(dashboard_url)
                    # Test the connection
                    _ = job_client.list_jobs()
                    self.state_manager.update_state(job_client=job_client)
                    return job_client
                except Exception as e:
                    LoggingUtility.log_warning("create job client", str(e))

        return job_client

    def _validate_log_retrieval_params(
        self,
        identifier: str,
        log_type: str,
        num_lines: int = 0,
        max_size_mb: int = 10,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Validate log retrieval parameters."""
        # Validate identifier
        if not identifier or not isinstance(identifier, str) or not identifier.strip():
            return self._response_formatter.format_validation_error(
                "Identifier must be a non-empty string"
            )

        # Validate log type - only job logs are supported
        if log_type != "job":
            return self._response_formatter.format_validation_error(
                f"Invalid log_type: {log_type}. Only 'job' is supported"
            )

        # Validate size parameters
        if max_size_mb <= 0 or max_size_mb > 100:
            return self._response_formatter.format_validation_error(
                "max_size_mb must be between 1 and 100"
            )

        # Validate line parameters (if specified and not default)
        if num_lines < 1 or num_lines > 10000:
            return self._response_formatter.format_validation_error(
                "num_lines must be between 1 and 10000"
            )

        # Validate pagination parameters (if specified)
        if page is not None and page < 1:
            return self._response_formatter.format_validation_error(
                "page must be positive"
            )

        if page_size is not None and (page_size < 1 or page_size > 1000):
            return self._response_formatter.format_validation_error(
                "page_size must be between 1 and 1000"
            )

        return None

    def _create_error_log_response(
        self,
        log_type: str,
        identifier: str,
        num_lines: int,
        max_size_mb: int,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        additional_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a standardized error response when log retrieval fails."""
        response = {
            "status": "error",
            "log_type": log_type,
            "identifier": identifier,
            "logs": "",
            "max_size_mb": max_size_mb,
        }

        # Add pagination info if applicable
        if page is not None and page_size is not None:
            response["pagination"] = {
                "current_page": page,
                "total_pages": 0,
                "page_size": page_size,
                "total_lines": 0,
                "lines_in_page": 0,
                "has_next": False,
                "has_previous": False,
            }
        else:
            response["num_lines_retrieved"] = 0
            response["requested_lines"] = num_lines

        # Add additional error information
        if additional_info:
            response.update(additional_info)

        return response

    def _analyze_job_logs(self, logs: str) -> Dict[str, Any]:
        """Analyze job logs for errors and issues."""
        if not logs:
            return {"errors_found": False, "analysis": "No logs to analyze"}

        error_patterns = [
            r"ERROR",
            r"Exception",
            r"Traceback",
            r"FAILED",
            r"CRITICAL",
            r"Fatal",
        ]

        log_lines = logs.split("\n")
        errors = []

        for i, line in enumerate(log_lines):
            for pattern in error_patterns:
                if pattern.lower() in line.lower():
                    errors.append(
                        {
                            "line_number": i + 1,
                            "error_type": pattern,
                            "line_content": line.strip(),
                        }
                    )
                    break

        return {
            "errors_found": len(errors) > 0,
            "error_count": len(errors),
            "errors": errors[:10],  # Limit to first 10 errors
            "total_lines_analyzed": len(log_lines),
            "analysis": f"Found {len(errors)} potential error lines out of {len(log_lines)} total lines",
        }
