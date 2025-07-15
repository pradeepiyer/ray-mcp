"""Centralized mock classes for testing and fallback scenarios.

This module provides mock implementations of core utilities when actual
dependencies are not available, primarily for testing and development scenarios.
"""

from typing import Any, Dict


class MockLoggingUtility:
    """Mock implementation of LoggingUtility for testing scenarios."""

    @staticmethod
    def log_info(operation: str, message: str) -> None:
        """Mock log info - does nothing in test scenarios."""
        pass

    @staticmethod
    def log_warning(operation: str, message: str) -> None:
        """Mock log warning - does nothing in test scenarios."""
        pass

    @staticmethod
    def log_error(operation: str, error: Exception) -> None:
        """Mock log error - does nothing in test scenarios."""
        pass

    @staticmethod
    def log_debug(operation: str, message: str) -> None:
        """Mock log debug - does nothing in test scenarios."""
        pass


class MockResponseFormatter:
    """Mock implementation of ResponseFormatter for testing scenarios."""

    def format_success_response(self, **kwargs) -> Dict[str, Any]:
        """Mock success response formatter."""
        response = {"status": "success"}
        response.update(kwargs)
        return response

    def format_error_response(
        self, operation: str, error: Exception, **kwargs
    ) -> Dict[str, Any]:
        """Mock error response formatter."""
        response = {
            "status": "error",
            "operation": operation,
            "message": str(error),
        }
        response.update(kwargs)
        return response

    def format_validation_error(self, message: str, **kwargs) -> Dict[str, Any]:
        """Mock validation error formatter."""
        response = {"status": "error", "message": message}
        response.update(kwargs)
        return response

    def format_partial_response(self, message: str, **kwargs) -> Dict[str, Any]:
        """Mock partial response formatter."""
        response = {"status": "partial", "message": message}
        response.update(kwargs)
        return response

    @staticmethod
    def handle_exceptions(operation: str):
        """Mock exception handler decorator."""

        def decorator(func):
            return func  # Just return function unchanged in mock

        return decorator


def get_mock_logging_utils() -> Dict[str, Any]:
    """Get mock logging utilities for testing scenarios."""
    return {
        "LoggingUtility": MockLoggingUtility,
        "ResponseFormatter": MockResponseFormatter,
    }
