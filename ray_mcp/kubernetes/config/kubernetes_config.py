"""Kubernetes configuration management for Ray MCP."""

import asyncio
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...foundation.import_utils import get_kubernetes_imports, get_logging_utils


class KubernetesConfig:
    """Manages Kubernetes configuration loading and validation."""

    def __init__(self):
        # Import logging utilities
        logging_utils = get_logging_utils()
        self._LoggingUtility = logging_utils["LoggingUtility"]
        self._ResponseFormatter = logging_utils["ResponseFormatter"]

        # Import Kubernetes modules
        k8s_imports = get_kubernetes_imports()
        self._client = k8s_imports["client"]
        self._config = k8s_imports["config"]
        self._KUBERNETES_AVAILABLE = k8s_imports["KUBERNETES_AVAILABLE"]
        self._ApiException = k8s_imports["ApiException"]
        self._ConfigException = k8s_imports["ConfigException"]

        self._current_config = None
        self._current_context = None

    def load_config(
        self, config_file: Optional[str] = None, context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Load Kubernetes configuration from file or environment."""
        try:
            if not self._KUBERNETES_AVAILABLE:
                return self._ResponseFormatter.format_error_response(
                    "load kubernetes config",
                    Exception(
                        "Kubernetes client library is not available. Please install kubernetes package: pip install kubernetes"
                    ),
                )

            # Try to load config from various sources
            if self._try_load_incluster_config():
                self._current_context = "in-cluster"
                return self._ResponseFormatter.format_success_response(
                    config_type="in-cluster", context="in-cluster"
                )

            # Try kubeconfig file
            config_file = config_file or os.path.expanduser("~/.kube/config")
            if os.path.exists(config_file):
                self._config.load_kube_config(config_file=config_file, context=context)
                self._current_context = (
                    context or self._get_current_context_from_config(config_file)
                )
                return self._ResponseFormatter.format_success_response(
                    config_type="kubeconfig",
                    config_file=config_file,
                    context=self._current_context,
                )

            # Try environment variables
            if self._try_load_env_config():
                self._current_context = "environment"
                return self._ResponseFormatter.format_success_response(
                    config_type="environment", context="environment"
                )

            return self._ResponseFormatter.format_error_response(
                "load kubernetes config",
                Exception("No valid Kubernetes configuration found"),
            )

        except Exception as e:
            self._LoggingUtility.log_error("load kubernetes config", e)
            return self._ResponseFormatter.format_error_response(
                "load kubernetes config", e
            )

    async def validate_config(self) -> Dict[str, Any]:
        """Validate the loaded Kubernetes configuration."""
        try:
            if not self._KUBERNETES_AVAILABLE:
                return self._ResponseFormatter.format_error_response(
                    "validate kubernetes config",
                    Exception("Kubernetes client library is not available"),
                )

            # Try to create a client and make a simple API call
            v1 = self._client.CoreV1Api()
            version_api = self._client.VersionApi()

            # Test connection by getting server version
            version_info = await asyncio.to_thread(version_api.get_code)

            # Safe access to git_version attribute
            git_version = getattr(version_info, "git_version", "unknown")
            return self._ResponseFormatter.format_success_response(
                valid=True,
                context=self._current_context,
                server_version=git_version,
            )
        except Exception as e:
            self._LoggingUtility.log_error("validate kubernetes config", e)
            return self._ResponseFormatter.format_error_response(
                "validate kubernetes config", e
            )

    async def list_contexts(self) -> Dict[str, Any]:
        """List available Kubernetes contexts."""
        try:
            if not self._KUBERNETES_AVAILABLE:
                return self._ResponseFormatter.format_error_response(
                    "list kubernetes contexts",
                    Exception(
                        "Kubernetes client library is not available. Please install kubernetes package: pip install kubernetes"
                    ),
                )

            contexts, active_context = await asyncio.to_thread(
                self._config.list_kube_config_contexts
            )
            context_list = []

            for ctx in contexts:
                # Safe dictionary access with type checking
                if not isinstance(ctx, dict):
                    continue

                context_dict = ctx.get("context", {})
                if not isinstance(context_dict, dict):
                    continue

                context_info = {
                    "name": ctx.get("name", "unknown"),
                    "cluster": context_dict.get("cluster", "unknown"),
                    "user": context_dict.get("user", "unknown"),
                    "namespace": context_dict.get("namespace", "default"),
                    "is_active": (
                        ctx.get("name") == active_context.get("name")
                        if active_context and isinstance(active_context, dict)
                        else False
                    ),
                }
                context_list.append(context_info)

            active_context_name = (
                active_context.get("name")
                if active_context and isinstance(active_context, dict)
                else None
            )

            return self._ResponseFormatter.format_success_response(
                contexts=context_list,
                active_context=active_context_name,
            )
        except Exception as e:
            self._LoggingUtility.log_error("list kubernetes contexts", e)
            return self._ResponseFormatter.format_error_response(
                "list kubernetes contexts", e
            )

    def get_current_context(self) -> Optional[str]:
        """Get the current Kubernetes context."""
        return self._current_context

    def _try_load_incluster_config(self) -> bool:
        """Try to load in-cluster configuration."""
        try:
            self._config.load_incluster_config()
            return True
        except self._ConfigException:
            return False

    def _try_load_env_config(self) -> bool:
        """Try to load configuration from environment variables."""
        # Check for common cloud provider environment variables
        if os.getenv("KUBECONFIG"):
            try:
                self._config.load_kube_config(config_file=os.getenv("KUBECONFIG"))
                return True
            except self._ConfigException:
                pass

        # Check for service account token (alternative in-cluster method)
        if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token"):
            try:
                self._config.load_incluster_config()
                return True
            except self._ConfigException:
                pass

        return False

    def _get_current_context_from_config(self, config_file: str) -> Optional[str]:
        """Get current context from kubeconfig file."""
        try:
            contexts, active_context = self._config.list_kube_config_contexts(
                config_file=config_file
            )
            return active_context["name"] if active_context else None
        except Exception:
            return None
