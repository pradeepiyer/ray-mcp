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
    def _stream_log_lines(
        log_source: Union[str, List[str]], max_line_size_bytes: int = 1024 * 1024
    ):
        """Generator that yields log lines one by one to prevent memory exhaustion.

        Args:
            log_source: String or list of log lines to process
            max_line_size_bytes: Maximum size per line in bytes to prevent memory exhaustion

        Yields:
            Individual lines from the log source
        """
        if isinstance(log_source, str):
            # For strings, use a character-by-character approach to avoid loading all lines in memory
            current_line = ""
            current_line_bytes = 0
            line_truncated = False

            for char in log_source:
                if char == "\n":
                    # End of line - yield what we have and reset
                    if line_truncated:
                        yield current_line + "... (line truncated due to size limit)"
                    else:
                        yield current_line
                    current_line = ""
                    current_line_bytes = 0
                    line_truncated = False
                else:
                    # Only add character if we haven't already truncated this line
                    if not line_truncated:
                        char_bytes = len(char.encode("utf-8"))
                        if current_line_bytes + char_bytes > max_line_size_bytes:
                            # Line is too long, mark as truncated but don't add more characters
                            line_truncated = True
                        else:
                            current_line += char
                            current_line_bytes += char_bytes

            # Don't forget the last line if it doesn't end with newline
            if current_line or line_truncated:
                if line_truncated:
                    yield current_line + "... (line truncated due to size limit)"
                else:
                    yield current_line
        else:
            # For lists, check each line's size and truncate if necessary
            for line in log_source:
                line_bytes = len(line.encode("utf-8"))
                if line_bytes > max_line_size_bytes:
                    # Truncate the line to fit within the size limit
                    truncated_line = line
                    while (
                        len(truncated_line.encode("utf-8")) > max_line_size_bytes - 50
                    ):  # Leave space for truncation marker
                        truncated_line = truncated_line[:-1]
                    yield truncated_line + "... (line truncated due to size limit)"
                else:
                    yield line

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
            # Use streaming approach to process logs line by line
            for line_idx, line in enumerate(
                LogProcessor._stream_log_lines(log_source, max_line_size_kb * 1024)
            ):
                # Early exit if we've reached the line limit
                if len(lines) >= max_lines:
                    lines.append(f"... (truncated at {max_lines} lines)")
                    break

                # Check total size limit
                line_bytes = line.encode("utf-8")
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
            # First, we need to count total lines efficiently
            # For very large logs, we'll estimate rather than count all lines
            total_lines = 0
            if isinstance(log_source, str):
                # For strings, estimate line count without loading all into memory
                # Use a sample-based approach for very large strings
                if len(log_source) > 10 * 1024 * 1024:  # 10MB threshold
                    # Sample first 1MB to estimate line density
                    sample_size = min(
                        1024 * 1024, len(log_source)
                    )  # 1MB or full string
                    sample = log_source[:sample_size]
                    sample_lines = sample.count("\n") + 1
                    estimated_total_lines = int(
                        (len(log_source) / sample_size) * sample_lines
                    )
                    total_lines = estimated_total_lines
                else:
                    # For smaller strings, count accurately
                    total_lines = log_source.count("\n") + 1
            else:
                total_lines = len(log_source)

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
            end_idx = start_idx + page_size

            # Stream through logs to get the requested page
            current_line_idx = 0
            page_lines = []

            for line in LogProcessor._stream_log_lines(
                log_source, max_line_size_kb * 1024
            ):
                if current_line_idx >= end_idx:
                    break

                if current_line_idx >= start_idx:
                    page_lines.append(line)

                current_line_idx += 1

            # Apply size limits to the page with per-line size checking
            current_size = 0
            max_size_bytes = max_size_mb * 1024 * 1024
            limited_lines = []

            for line in page_lines:
                # Check total size limit
                line_bytes = line.encode("utf-8")
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
            )

        except Exception as e:
            LoggingUtility.log_error("stream logs with pagination", e)
            return ResponseFormatter.format_error_response(
                "stream logs with pagination", e
            )


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


class LogAnalyzer:
    """Shared utility for analyzing logs for errors and issues."""

    @staticmethod
    def analyze_logs_for_errors(logs: str) -> Dict[str, Any]:
        """Analyze logs for errors and issues - consolidated from duplicated methods."""
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
