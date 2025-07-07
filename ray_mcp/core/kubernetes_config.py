"""Kubernetes configuration management."""

import os
from typing import Any, Dict, List, Optional

try:
    from ..logging_utils import LoggingUtility, ResponseFormatter
except ImportError:
    # Fallback for direct execution
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from logging_utils import LoggingUtility, ResponseFormatter

from .interfaces import KubernetesConfig

# Import kubernetes modules with error handling
try:
    from kubernetes import client, config
    from kubernetes.config import ConfigException
    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False
    client = None
    config = None
    ConfigException = Exception


class KubernetesConfigManager(KubernetesConfig):
    """Manages Kubernetes configuration with support for multiple contexts and environments."""

    def __init__(self):
        self._response_formatter = ResponseFormatter()
        self._current_config = None
        self._current_context = None

    @ResponseFormatter.handle_exceptions("load kubernetes config")
    def load_config(self, config_file: Optional[str] = None, context: Optional[str] = None) -> Dict[str, Any]:
        """Load Kubernetes configuration from file or environment."""
        if not KUBERNETES_AVAILABLE:
            return self._response_formatter.format_error_response(
                "load kubernetes config",
                Exception("Kubernetes client library is not available. Please install kubernetes package.")
            )

        try:
            # Try to load config from various sources
            if self._try_load_incluster_config():
                self._current_context = "in-cluster"
                return self._response_formatter.format_success_response(
                    config_type="in-cluster", 
                    context="in-cluster"
                )
            
            # Try kubeconfig file
            config_file = config_file or os.path.expanduser("~/.kube/config")
            if os.path.exists(config_file):
                config.load_kube_config(config_file=config_file, context=context)
                self._current_context = context or self._get_current_context_from_config(config_file)
                return self._response_formatter.format_success_response(
                    config_type="kubeconfig",
                    config_file=config_file,
                    context=self._current_context
                )
            
            # Try environment variables
            if self._try_load_env_config():
                self._current_context = "environment"
                return self._response_formatter.format_success_response(
                    config_type="environment", 
                    context="environment"
                )

            return self._response_formatter.format_error_response(
                "load kubernetes config",
                Exception("No valid Kubernetes configuration found")
            )

        except ConfigException as e:
            return self._response_formatter.format_error_response(
                "load kubernetes config",
                e
            )
        except Exception as e:
            return self._response_formatter.format_error_response(
                "load kubernetes config",
                e
            )

    @ResponseFormatter.handle_exceptions("validate kubernetes config")
    def validate_config(self) -> Dict[str, Any]:
        """Validate the loaded Kubernetes configuration."""
        if not KUBERNETES_AVAILABLE:
            return self._response_formatter.format_error_response(
                "validate kubernetes config",
                Exception("Kubernetes client library is not available")
            )

        try:
            # Try to create a client and make a simple API call
            v1 = client.CoreV1Api()
            v1.get_api_versions()
            
            return self._response_formatter.format_success_response(
                valid=True, 
                context=self._current_context
            )
        except Exception as e:
            return self._response_formatter.format_error_response(
                "validate kubernetes config",
                e
            )

    @ResponseFormatter.handle_exceptions("list kubernetes contexts")
    def list_contexts(self) -> Dict[str, Any]:
        """List available Kubernetes contexts."""
        if not KUBERNETES_AVAILABLE:
            return self._response_formatter.format_error_response(
                "list kubernetes contexts",
                Exception("Kubernetes client library is not available")
            )

        try:
            contexts, active_context = config.list_kube_config_contexts()
            context_list = []
            
            for ctx in contexts:
                context_info = {
                    "name": ctx["name"],
                    "cluster": ctx["context"]["cluster"],
                    "user": ctx["context"]["user"],
                    "namespace": ctx["context"].get("namespace", "default"),
                    "is_active": ctx["name"] == active_context["name"] if active_context else False
                }
                context_list.append(context_info)
            
            return self._response_formatter.format_success_response(
                contexts=context_list,
                active_context=active_context["name"] if active_context else None
            )
        except Exception as e:
            return self._response_formatter.format_error_response(
                "list kubernetes contexts",
                e
            )

    def get_current_context(self) -> Optional[str]:
        """Get the current Kubernetes context."""
        return self._current_context

    def _try_load_incluster_config(self) -> bool:
        """Try to load in-cluster configuration."""
        try:
            config.load_incluster_config()
            return True
        except ConfigException:
            return False

    def _try_load_env_config(self) -> bool:
        """Try to load configuration from environment variables."""
        # Check for common cloud provider environment variables
        if os.getenv("KUBECONFIG"):
            try:
                config.load_kube_config(config_file=os.getenv("KUBECONFIG"))
                return True
            except ConfigException:
                pass
        
        # Check for service account token (alternative in-cluster method)
        if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token"):
            try:
                config.load_incluster_config()
                return True
            except ConfigException:
                pass
        
        return False

    def _get_current_context_from_config(self, config_file: str) -> Optional[str]:
        """Get current context from kubeconfig file."""
        try:
            contexts, active_context = config.list_kube_config_contexts(config_file=config_file)
            return active_context["name"] if active_context else None
        except Exception:
            return None 