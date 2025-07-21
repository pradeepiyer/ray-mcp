"""Core utilities for Ray MCP - enums, logging, responses, and naming."""

from enum import Enum
import logging
import re
import time
from typing import Any, Optional

from kubernetes import config

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================


class CloudProvider(Enum):
    """Supported cloud providers."""

    GKE = "gke"
    AWS = "aws"
    LOCAL = "local"


# =============================================================================
# LOGGING UTILITIES
# =============================================================================


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


def is_kubernetes_ready() -> bool:
    """Check if Kubernetes is ready."""
    try:
        if config:
            config.load_kube_config()
            return True
        return False
    except Exception:
        return False


def handle_error(
    logger: LoggingUtility, operation: str, error: Exception
) -> dict[str, Any]:
    """Handle errors with consistent logging and response formatting."""
    logger.log_error(operation, error)
    return error_response(f"Failed to {operation}: {str(error)}")


def get_logs(log_source: str, max_lines: int = 100) -> str:
    """Get logs with simple truncation."""
    if not log_source:
        return ""

    lines = log_source.split("\n")
    if len(lines) <= max_lines:
        return log_source

    return "\n".join(lines[:max_lines]) + f"\n... (truncated to {max_lines} lines)"


# =============================================================================
# RESPONSE UTILITIES
# =============================================================================


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


# =============================================================================
# NAME GENERATION UTILITIES
# =============================================================================


def generate_ray_resource_name(
    resource_type: str, base_name: Optional[str] = None, max_length: int = 63
) -> str:
    """Generate a simple unique name for a Ray resource.

    Args:
        resource_type: Type of resource ("job" or "service")
        base_name: Optional base name from user input
        max_length: Maximum name length (Kubernetes limit is 63 characters)

    Returns:
        A unique name following Kubernetes naming conventions
    """
    # Generate timestamp-based unique suffix (guaranteed unique per second)
    timestamp = int(time.time())
    unique_suffix = f"{timestamp % 100000:05d}"  # Last 5 digits of timestamp

    # Use base name or default
    if base_name:
        # Simple sanitization: lowercase, replace invalid chars with hyphens
        prefix = re.sub(r"[^a-z0-9-]", "-", base_name.lower().strip())
        prefix = re.sub(r"-+", "-", prefix).strip(
            "-"
        )  # Remove consecutive/trailing hyphens
    else:
        prefix = f"ray-{resource_type}"

    # Ensure prefix starts with letter and is not empty
    if not prefix or not prefix[0].isalpha():
        prefix = f"ray-{resource_type}"

    # Combine with unique suffix
    name = f"{prefix}-{unique_suffix}"

    # Truncate if needed, keeping the unique suffix
    if len(name) > max_length:
        max_prefix = max_length - len(unique_suffix) - 1  # -1 for hyphen
        name = f"{prefix[:max_prefix]}-{unique_suffix}"

    return name
