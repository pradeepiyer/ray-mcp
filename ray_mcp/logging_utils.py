"""Centralized logging utilities for Ray MCP server.

This module provides utilities for standardized logging, log processing,
and response formatting to eliminate redundancy across the codebase.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class LogProcessor:
    """Centralized log processing utilities."""

    @staticmethod
    def validate_log_parameters(
        num_lines: int, max_size_mb: int
    ) -> Optional[Dict[str, Any]]:
        """Validate log retrieval parameters and return error if invalid."""
        if num_lines <= 0:
            return {"status": "error", "message": "num_lines must be positive"}
        if num_lines > 10000:  # Reasonable upper limit
            return {"status": "error", "message": "num_lines cannot exceed 10000"}
        if max_size_mb <= 0 or max_size_mb > 100:  # 100MB max
            return {
                "status": "error",
                "message": "max_size_mb must be between 1 and 100",
            }
        return None

    @staticmethod
    def truncate_logs_to_size(logs: str, max_size_mb: int) -> str:
        """Truncate logs to specified size limit while preserving line boundaries."""
        max_bytes = max_size_mb * 1024 * 1024
        logs_bytes = logs.encode("utf-8")

        if len(logs_bytes) <= max_bytes:
            return logs

        # Truncate to size limit, trying to break at line boundaries
        truncated_bytes = logs_bytes[:max_bytes]
        truncated_text = truncated_bytes.decode("utf-8", errors="ignore")

        # Try to break at a line boundary
        last_newline = truncated_text.rfind("\n")
        if last_newline > 0:
            truncated_text = truncated_text[:last_newline]

        return truncated_text + f"\n... (truncated at {max_size_mb}MB limit)"

    @staticmethod
    def stream_logs_with_limits(
        log_source: Union[str, List[str]],
        max_lines: int = 100,
        max_size_mb: int = 10,
        max_line_size_kb: int = 1024,  # Add per-line size limit (1MB default)
    ) -> str:
        """Stream logs with line and size limits to prevent memory exhaustion.

        Args:
            log_source: String or list of log lines to process
            max_lines: Maximum number of lines to return
            max_size_mb: Maximum total size in MB
            max_line_size_kb: Maximum size per line in KB to prevent memory exhaustion

        Returns:
            Processed log string with appropriate truncation messages
        """
        lines = []
        current_size = 0
        max_size_bytes = max_size_mb * 1024 * 1024
        max_line_bytes = max_line_size_kb * 1024

        try:
            # Handle both string and list inputs with streaming approach
            if isinstance(log_source, str):
                log_lines = log_source.split("\n")
            else:
                log_lines = log_source

            for line_idx, line in enumerate(log_lines):
                # Early exit if we've reached the line limit
                if len(lines) >= max_lines:
                    lines.append(f"... (truncated at {max_lines} lines)")
                    break

                # Check per-line size limit first to prevent memory exhaustion
                line_bytes = line.encode("utf-8")
                if len(line_bytes) > max_line_bytes:
                    # Truncate the individual line if it's too large
                    truncated_line = (
                        line[:max_line_size_kb]
                        .encode("utf-8", errors="ignore")
                        .decode("utf-8", errors="ignore")
                    )
                    truncated_line += f"... (line truncated at {max_line_size_kb}KB)"
                    line_bytes = truncated_line.encode("utf-8")
                    line = truncated_line

                # Check total size limit
                if current_size + len(line_bytes) > max_size_bytes:
                    lines.append(f"... (truncated at {max_size_mb}MB limit)")
                    break

                lines.append(line.rstrip())
                current_size += len(line_bytes)

        except Exception as e:
            LoggingUtility.log_error("streaming logs", e)
            lines.append(f"Error reading logs: {str(e)}")

        return "\n".join(lines)

    @staticmethod
    async def stream_logs_async(
        log_source: Union[str, List[str]],
        max_lines: int = 100,
        max_size_mb: int = 10,
        max_line_size_kb: int = 1024,
    ) -> str:
        """Async version of log streaming for better performance with large logs."""
        return await asyncio.get_event_loop().run_in_executor(
            None,
            LogProcessor.stream_logs_with_limits,
            log_source,
            max_lines,
            max_size_mb,
            max_line_size_kb,
        )

    @staticmethod
    async def stream_logs_with_pagination(
        log_source: Union[str, List[str]],
        page: int = 1,
        page_size: int = 100,
        max_size_mb: int = 10,
        max_line_size_kb: int = 1024,
    ) -> Dict[str, Any]:
        """Stream logs with pagination support for large log files."""
        try:
            # Handle both string and list inputs
            if isinstance(log_source, str):
                log_lines = log_source.split("\n")
            else:
                log_lines = log_source

            total_lines = len(log_lines)
            total_pages = (total_lines + page_size - 1) // page_size

            # Validate page number
            if page < 1 or page > total_pages:
                return {
                    "status": "error",
                    "message": f"Invalid page number. Available pages: 1-{total_pages}",
                    "total_pages": total_pages,
                    "total_lines": total_lines,
                }

            # Calculate start and end indices
            start_idx = (page - 1) * page_size
            end_idx = min(start_idx + page_size, total_lines)

            # Extract page lines
            page_lines = log_lines[start_idx:end_idx]

            # Apply size limits to the page with per-line size checking
            current_size = 0
            max_size_bytes = max_size_mb * 1024 * 1024
            max_line_bytes = max_line_size_kb * 1024
            limited_lines = []

            for line in page_lines:
                # Check per-line size limit first to prevent memory exhaustion
                line_bytes = line.encode("utf-8")
                if len(line_bytes) > max_line_bytes:
                    # Truncate the individual line if it's too large
                    truncated_line = (
                        line[:max_line_size_kb]
                        .encode("utf-8", errors="ignore")
                        .decode("utf-8", errors="ignore")
                    )
                    truncated_line += f"... (line truncated at {max_line_size_kb}KB)"
                    line_bytes = truncated_line.encode("utf-8")
                    line = truncated_line

                # Check total size limit
                if current_size + len(line_bytes) > max_size_bytes:
                    limited_lines.append(f"... (truncated at {max_size_mb}MB limit)")
                    break

                limited_lines.append(line.rstrip())
                current_size += len(line_bytes)

            return ResponseFormatter.format_success_response(
                logs="\n".join(limited_lines),
                pagination={
                    "current_page": page,
                    "total_pages": total_pages,
                    "page_size": page_size,
                    "total_lines": total_lines,
                    "lines_in_page": len(limited_lines),
                    "has_next": page < total_pages,
                    "has_previous": page > 1,
                },
                size_info={
                    "current_size_mb": current_size / (1024 * 1024),
                    "max_size_mb": max_size_mb,
                    "max_line_size_kb": max_line_size_kb,
                },
            )

        except Exception as e:
            LoggingUtility.log_error("paginated log streaming", e)
            return {
                "status": "error",
                "message": f"Error streaming logs with pagination: {str(e)}",
            }


class LoggingUtility:
    """Centralized logging utility for standardized error and success logging."""

    @staticmethod
    def log_error(operation: str, error: Exception, exc_info: bool = False) -> None:
        """Log an error with standardized formatting."""
        logger.error(f"Failed to {operation}: {error}", exc_info=exc_info)

    @staticmethod
    def log_warning(operation: str, message: str) -> None:
        """Log a warning with standardized formatting."""
        logger.warning(f"{operation}: {message}")

    @staticmethod
    def log_info(operation: str, message: str) -> None:
        """Log an info message with standardized formatting."""
        logger.info(f"{operation}: {message}")

    @staticmethod
    def log_debug(operation: str, message: str) -> None:
        """Log a debug message with standardized formatting."""
        logger.debug(f"{operation}: {message}")


class ResponseFormatter:
    """Centralized response formatting utilities."""

    @staticmethod
    def handle_exceptions(operation: str):
        """Decorator to standardize exception handling and error response formatting."""

        def decorator(func):
            import functools

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    LoggingUtility.log_error(operation, e)
                    return ResponseFormatter.format_error_response(operation, e)

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    LoggingUtility.log_error(operation, e)
                    return ResponseFormatter.format_error_response(operation, e)

            import inspect

            if inspect.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper

        return decorator

    @staticmethod
    def format_error_response(
        operation: str, error: Exception, **kwargs
    ) -> Dict[str, Any]:
        """Format a standardized error response."""
        response = {
            "status": "error",
            "message": f"Failed to {operation}: {str(error)}",
        }
        response.update(kwargs)
        return response

    @staticmethod
    def format_success_response(**kwargs) -> Dict[str, Any]:
        """Format a standardized success response."""
        response = {"status": "success"}
        response.update(kwargs)
        return response

    @staticmethod
    def format_validation_error(message: str, **kwargs) -> Dict[str, Any]:
        """Format a validation error response."""
        response = {"status": "error", "message": message}
        response.update(kwargs)
        return response

    @staticmethod
    def format_partial_response(message: str, **kwargs) -> Dict[str, Any]:
        """Format a partial success response (for operations that succeeded but with limitations)."""
        response = {"status": "partial", "message": message}
        response.update(kwargs)
        return response


class LogRetrievalManager:
    """Centralized log retrieval manager for job logs only."""

    def __init__(self):
        self.log_processor = LogProcessor()
        self.response_formatter = ResponseFormatter()

    async def retrieve_logs(
        self,
        identifier: str,
        log_type: str,
        num_lines: int = 100,
        include_errors: bool = False,
        max_size_mb: int = 10,
        paginated: bool = False,
        page: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Unified log retrieval method that handles job logs only."""
        # Validate parameters
        validation_error = self.log_processor.validate_log_parameters(
            num_lines, max_size_mb
        )
        if validation_error:
            return validation_error

        if paginated and page <= 0:
            return self.response_formatter.format_validation_error(
                "page must be positive"
            )

        # Only job logs are supported
        if log_type == "job":
            return await self._retrieve_job_logs_unified(
                identifier,
                num_lines,
                include_errors,
                max_size_mb,
                paginated,
                page,
                page_size,
            )
        else:
            return self.response_formatter.format_validation_error(
                f"Invalid log_type: {log_type}. Only 'job' is supported"
            )

    async def _retrieve_job_logs_unified(
        self,
        job_id: str,
        num_lines: int,
        include_errors: bool,
        max_size_mb: int,
        paginated: bool,
        page: int,
        page_size: int,
    ) -> Dict[str, Any]:
        """Unified job log retrieval that handles both regular and paginated modes."""
        try:
            # This would need access to the job client from RayManager
            # For now, return a placeholder that indicates this needs integration
            return self.response_formatter.format_partial_response(
                "Job log retrieval needs integration with RayManager job client",
                log_type="job",
                identifier=job_id,
                paginated=paginated,
            )
        except Exception as e:
            LoggingUtility.log_error("retrieve job logs", e)
            return self.response_formatter.format_error_response("retrieve job logs", e)
