"""Centralized log management for Ray clusters."""

from typing import Any, Dict, Optional

from ..foundation.base_managers import ResourceManager
from ..foundation.logging_utils import LogProcessor


class LogManager(ResourceManager):
    """Manages Ray log retrieval and processing operations."""

    def __init__(self):
        super().__init__(
            enable_ray=True,
            enable_kubernetes=False,
            enable_cloud=False,
        )

        self._log_processor = LogProcessor()

    async def execute_request(self, prompt: str) -> Dict[str, Any]:
        """Execute log operations using natural language prompts.

        This is a simple log manager that delegates to retrieve_logs.
        For now it just returns an error since log operations are handled
        by job and cluster managers directly.
        """
        return self._ResponseFormatter.format_error_response(
            "log manager execute_request",
            Exception(
                "Log operations should be handled by job or cluster managers directly"
            ),
        )

    async def retrieve_logs(
        self,
        identifier: str,
        log_type: str = "job",
        num_lines: int = 100,
        include_errors: bool = False,
        max_size_mb: int = 10,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Retrieve logs from Ray cluster with optional pagination and comprehensive error analysis."""
        return await self._execute_operation(
            "retrieve logs",
            self._retrieve_logs_operation,
            identifier,
            log_type,
            num_lines,
            include_errors,
            max_size_mb,
            page,
            page_size,
            **kwargs,
        )

    async def _retrieve_logs_operation(
        self,
        identifier: str,
        log_type: str = "job",
        num_lines: int = 100,
        include_errors: bool = False,
        max_size_mb: int = 10,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute log retrieval operation."""
        # Validate parameters
        validation_error = self._validate_log_retrieval_params(
            identifier, log_type, num_lines, max_size_mb, page, page_size
        )
        if validation_error:
            return validation_error

        # Only job logs are supported
        if log_type == "job":
            # Use pagination if page parameters are provided
            if page is not None:
                # Set default page_size if not provided
                if page_size is None:
                    page_size = 100
                return await self._retrieve_job_logs_paginated(
                    identifier, page, page_size, max_size_mb, include_errors
                )
            else:
                return await self._retrieve_job_logs_unified(
                    identifier, num_lines, include_errors, max_size_mb
                )
        else:
            raise ValueError(f"Invalid log_type: {log_type}. Only 'job' is supported")

    async def _retrieve_job_logs_unified(
        self,
        job_id: str,
        num_lines: int = 100,
        include_errors: bool = False,
        max_size_mb: int = 10,
    ) -> Dict[str, Any]:
        """Unified job log retrieval with error analysis."""
        # Use ManagedComponent validation method instead of ResourceManager's
        self._ensure_ray_available()

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
                "num_lines_retrieved": (
                    0 if not processed_logs else len(processed_logs.splitlines())
                ),
                "max_size_mb": max_size_mb,
            }

            # Add error analysis if requested
            if include_errors and processed_logs:
                from ..foundation.logging_utils import LogAnalyzer

                result["error_analysis"] = LogAnalyzer.analyze_logs_for_errors(
                    processed_logs
                )

            return result

        except Exception as e:
            self._LoggingUtility.log_error("retrieve job logs", e)
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
        # Use ManagedComponent validation method instead of ResourceManager's
        self._ensure_ray_available()

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
                from ..foundation.logging_utils import LogAnalyzer

                paginated_result["error_analysis"] = (
                    LogAnalyzer.analyze_logs_for_errors(paginated_result["logs"])
                )

            return paginated_result

        except Exception as e:
            self._LoggingUtility.log_error("retrieve job logs paginated", e)
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
        self._ensure_ray_available()

        if not self._JobSubmissionClient:
            return None

        job_client = getattr(self, "_job_client", None)

        if not job_client:
            # Try to create a basic client if we have dashboard URL
            dashboard_url = getattr(self, "_dashboard_url", None)
            if dashboard_url:
                try:
                    job_client = self._JobSubmissionClient(dashboard_url)
                    # Test the connection
                    _ = job_client.list_jobs()
                    self._job_client = job_client
                    return job_client
                except Exception as e:
                    self._LoggingUtility.log_warning("create job client", str(e))

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
            return self._ResponseFormatter.format_validation_error(
                "Identifier must be a non-empty string"
            )

        # Validate log type - only job logs are supported
        if log_type != "job":
            return self._ResponseFormatter.format_validation_error(
                f"Invalid log_type: {log_type}. Only 'job' is supported"
            )

        # Validate size parameters
        if max_size_mb <= 0 or max_size_mb > 100:
            return self._ResponseFormatter.format_validation_error(
                "max_size_mb must be between 1 and 100"
            )

        # Validate line parameters (if specified and not default)
        if num_lines < 1 or num_lines > 10000:
            return self._ResponseFormatter.format_validation_error(
                "num_lines must be between 1 and 10000"
            )

        # Validate pagination parameters (if specified)
        if page is not None and page < 1:
            return self._ResponseFormatter.format_validation_error(
                "page must be positive"
            )

        if page_size is not None and (page_size < 1 or page_size > 1000):
            return self._ResponseFormatter.format_validation_error(
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
        # Use ResponseFormatter as base and add log-specific fields
        error_msg = (
            additional_info.get("error", "Log retrieval failed")
            if additional_info
            else "Log retrieval failed"
        )
        response = self._ResponseFormatter.format_error_response(
            "retrieve logs", Exception(error_msg)
        )

        # Add log-specific fields
        response.update(
            {
                "log_type": log_type,
                "identifier": identifier,
                "logs": "",
                "max_size_mb": max_size_mb,
            }
        )

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

        # Add any remaining additional error information
        if additional_info:
            # Remove the 'error' key since we already used it for the message
            remaining_info = {k: v for k, v in additional_info.items() if k != "error"}
            response.update(remaining_info)

        return response
