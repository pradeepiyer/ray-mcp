"""Simplified logging utilities for Ray MCP."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class LoggingUtility:
    """Simple logging utility."""

    @staticmethod
    def log_info(operation: str, message: str) -> None:
        """Log an info message."""
        logger.info(f"{operation}: {message}")

    @staticmethod
    def log_error(operation: str, error: Exception) -> None:
        """Log an error message."""
        logger.error(f"{operation}: {str(error)}")

    @staticmethod
    def log_warning(operation: str, message: str) -> None:
        """Log a warning message."""
        logger.warning(f"{operation}: {message}")

    @staticmethod
    def log_debug(operation: str, message: str) -> None:
        """Log a debug message."""
        logger.debug(f"{operation}: {message}")


# Simple response helpers
def success_response(**kwargs) -> dict[str, Any]:
    """Create a success response."""
    response = {"status": "success"}
    response.update(kwargs)
    return response


def error_response(message: str, **kwargs) -> dict[str, Any]:
    """Create an error response."""
    response = {"status": "error", "message": message}
    response.update(kwargs)
    return response


def get_logs(log_source: str, max_lines: int = 100) -> str:
    """Get logs with simple truncation."""
    if not log_source:
        return ""

    lines = log_source.split("\n")
    if len(lines) <= max_lines:
        return log_source

    return "\n".join(lines[:max_lines]) + f"\n... (truncated to {max_lines} lines)"
