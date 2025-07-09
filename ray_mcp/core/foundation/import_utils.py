"""Centralized import management for Ray MCP.

This module provides a unified interface for importing third-party dependencies
with proper error handling and availability checks.
"""

import sys
from typing import Any, Dict


def get_logging_utils() -> Dict[str, Any]:
    """Get logging utilities with proper error handling."""
    try:
        from .logging_utils import LoggingUtility, ResponseFormatter

        return {
            "LoggingUtility": LoggingUtility,
            "ResponseFormatter": ResponseFormatter,
        }
    except ImportError:
        # Fallback for direct execution
        try:
            from logging_utils import LoggingUtility, ResponseFormatter

            return {
                "LoggingUtility": LoggingUtility,
                "ResponseFormatter": ResponseFormatter,
            }
        except ImportError:
            # Create mock classes for testing
            class MockLoggingUtility:
                @staticmethod
                def log_info(operation: str, message: str):
                    pass

                @staticmethod
                def log_warning(operation: str, message: str):
                    pass

                @staticmethod
                def log_error(operation: str, error: Exception):
                    pass

            class MockResponseFormatter:
                def format_success_response(self, **kwargs):
                    return {"status": "success", **kwargs}

                def format_error_response(self, operation: str, error: Exception):
                    return {
                        "status": "error",
                        "operation": operation,
                        "message": str(error),
                    }

            return {
                "LoggingUtility": MockLoggingUtility,
                "ResponseFormatter": MockResponseFormatter,
            }


def get_ray_imports() -> Dict[str, Any]:
    """Get Ray imports with availability checking."""
    try:
        import ray
        from ray.job_submission import JobSubmissionClient

        return {
            "ray": ray,
            "JobSubmissionClient": JobSubmissionClient,
            "RAY_AVAILABLE": True,
        }
    except ImportError:
        return {"ray": None, "JobSubmissionClient": None, "RAY_AVAILABLE": False}


def get_kubernetes_imports() -> Dict[str, Any]:
    """Get Kubernetes imports with availability checking."""
    try:
        from kubernetes import client, config
        from kubernetes.client.rest import ApiException
        from kubernetes.config import ConfigException

        return {
            "client": client,
            "config": config,
            "ApiException": ApiException,
            "ConfigException": ConfigException,
            "KUBERNETES_AVAILABLE": True,
        }
    except ImportError:
        return {
            "client": None,
            "config": None,
            "ApiException": Exception,
            "ConfigException": Exception,
            "KUBERNETES_AVAILABLE": False,
        }


def get_google_cloud_imports() -> Dict[str, Any]:
    """Get Google Cloud imports with availability checking."""
    try:
        from google.auth import default
        from google.auth.exceptions import DefaultCredentialsError
        import google.auth.transport.requests
        from google.cloud import container_v1
        from google.oauth2 import service_account

        return {
            "default": default,
            "DefaultCredentialsError": DefaultCredentialsError,
            "container_v1": container_v1,
            "service_account": service_account,
            "google_auth_transport": google.auth.transport.requests,
            "GOOGLE_CLOUD_AVAILABLE": True,
            "GOOGLE_AUTH_AVAILABLE": True,
        }
    except ImportError:
        return {
            "default": None,
            "DefaultCredentialsError": Exception,
            "container_v1": None,
            "service_account": None,
            "google_auth_transport": None,
            "GOOGLE_CLOUD_AVAILABLE": False,
            "GOOGLE_AUTH_AVAILABLE": False,
        }


def is_ray_available() -> bool:
    """Check if Ray is available."""
    return get_ray_imports()["RAY_AVAILABLE"]


def is_kubernetes_available() -> bool:
    """Check if Kubernetes is available."""
    return get_kubernetes_imports()["KUBERNETES_AVAILABLE"]


def is_google_cloud_available() -> bool:
    """Check if Google Cloud SDK is available."""
    return get_google_cloud_imports()["GOOGLE_CLOUD_AVAILABLE"]
