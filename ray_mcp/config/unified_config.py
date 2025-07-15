"""Unified configuration management for Ray MCP - replaces all fragmented config systems."""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml


class ConfigProvider(Enum):
    """Supported configuration providers."""

    RAY = "ray"
    KUBERNETES = "kubernetes"
    GKE = "gke"
    LOCAL = "local"


@dataclass
class UnifiedConfig:
    """Unified configuration container for all Ray MCP components."""

    # Ray configuration
    ray_address: Optional[str] = None
    ray_dashboard_host: str = "127.0.0.1"
    ray_dashboard_port: int = 8265
    ray_num_cpus: Optional[int] = None
    ray_num_gpus: Optional[int] = None
    ray_object_store_memory: Optional[int] = None

    # Kubernetes configuration
    kubeconfig_path: Optional[str] = None
    kubernetes_context: Optional[str] = None
    kubernetes_namespace: str = "default"

    # GKE configuration
    gcp_project_id: Optional[str] = None
    gcp_credentials_path: Optional[str] = None
    gke_region: str = "us-central1"
    gke_zone: str = "us-central1-a"

    # General settings
    enhanced_output: bool = False
    log_level: str = "INFO"
    timeout_seconds: int = 300

    # Resource templates
    templates: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize templates with defaults."""
        if not self.templates:
            self.templates = self._get_default_templates()

    def _get_default_templates(self) -> Dict[str, Dict[str, Any]]:
        """Get default resource templates."""
        return {
            "ray_cluster": {
                "basic": {
                    "head_resources": {"cpu": "1", "memory": "2Gi"},
                    "worker_resources": {"cpu": "1", "memory": "2Gi"},
                    "workers": 1,
                    "ray_version": "2.47.0",
                },
                "medium": {
                    "head_resources": {"cpu": "2", "memory": "4Gi"},
                    "worker_resources": {"cpu": "2", "memory": "4Gi"},
                    "workers": 3,
                    "ray_version": "2.47.0",
                },
                "gpu": {
                    "head_resources": {"cpu": "2", "memory": "4Gi"},
                    "worker_resources": {
                        "cpu": "2",
                        "memory": "4Gi",
                        "nvidia.com/gpu": "1",
                    },
                    "workers": 2,
                    "ray_version": "2.47.0",
                },
            },
            "gke_cluster": {
                "basic": {
                    "machine_type": "e2-medium",
                    "disk_size_gb": 100,
                    "num_nodes": 3,
                    "preemptible": False,
                },
                "production": {
                    "machine_type": "n1-standard-4",
                    "disk_size_gb": 200,
                    "num_nodes": 5,
                    "preemptible": False,
                },
                "gpu": {
                    "machine_type": "n1-standard-4",
                    "disk_size_gb": 200,
                    "num_nodes": 3,
                    "accelerator_type": "nvidia-tesla-t4",
                    "accelerator_count": 1,
                    "preemptible": True,
                },
            },
        }


class UnifiedConfigManager:
    """Unified configuration manager that replaces all fragmented config systems."""

    def __init__(self):
        self._config = UnifiedConfig()
        self._loaded = False

    async def initialize(self) -> None:
        """Initialize configuration from all sources in priority order."""
        if self._loaded:
            return

        # Load configuration in priority order
        await self._load_defaults()
        await self._load_system_config()
        await self._load_user_config()
        await self._load_project_config()
        await self._load_environment_variables()

        self._loaded = True

    async def _load_defaults(self) -> None:
        """Load system defaults."""
        # Defaults are already set in UnifiedConfig dataclass
        pass

    async def _load_system_config(self) -> None:
        """Load system-wide configuration."""
        system_config_path = Path("/etc/ray-mcp/config.yaml")
        if system_config_path.exists():
            await self._load_config_file(system_config_path)

    async def _load_user_config(self) -> None:
        """Load user-specific configuration."""
        user_config_dir = Path.home() / ".ray-mcp"
        user_config_path = user_config_dir / "config.yaml"

        if user_config_path.exists():
            await self._load_config_file(user_config_path)

    async def _load_project_config(self) -> None:
        """Load project-specific configuration."""
        project_config_path = Path.cwd() / ".ray-mcp.yaml"
        if project_config_path.exists():
            await self._load_config_file(project_config_path)

    async def _load_environment_variables(self) -> None:
        """Load configuration from environment variables."""
        logger = logging.getLogger(__name__)

        env_mappings = {
            # Ray settings
            "RAY_ADDRESS": "ray_address",
            "RAY_DASHBOARD_HOST": "ray_dashboard_host",
            "RAY_DASHBOARD_PORT": "ray_dashboard_port",
            "RAY_NUM_CPUS": "ray_num_cpus",
            "RAY_NUM_GPUS": "ray_num_gpus",
            "RAY_OBJECT_STORE_MEMORY": "ray_object_store_memory",
            # Kubernetes settings
            "KUBECONFIG": "kubeconfig_path",
            "KUBERNETES_CONTEXT": "kubernetes_context",
            "KUBERNETES_NAMESPACE": "kubernetes_namespace",
            # GKE settings
            "GOOGLE_CLOUD_PROJECT": "gcp_project_id",
            "GCLOUD_PROJECT": "gcp_project_id",  # Alternative name
            "GOOGLE_APPLICATION_CREDENTIALS": "gcp_credentials_path",
            "GKE_REGION": "gke_region",
            "GKE_ZONE": "gke_zone",
            # General settings
            "RAY_MCP_ENHANCED_OUTPUT": "enhanced_output",
            "RAY_MCP_LOG_LEVEL": "log_level",
            "RAY_MCP_TIMEOUT": "timeout_seconds",
        }

        for env_var, config_key in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                # Type conversion
                if (
                    config_key.endswith("_port")
                    or config_key.endswith("_cpus")
                    or config_key.endswith("_gpus")
                    or config_key.endswith("_memory")
                    or config_key.endswith("_seconds")
                ):
                    try:
                        value = int(value)
                    except ValueError:
                        logger.warning(
                            f"Invalid integer value for environment variable {env_var}='{os.getenv(env_var)}'. "
                            f"Expected integer for {config_key}. Keeping default value."
                        )
                        continue
                elif config_key == "enhanced_output":
                    value = value.lower() in ("true", "1", "yes", "on")

                setattr(self._config, config_key, value)

    async def _load_config_file(self, config_path: Path) -> None:
        """Load configuration from a YAML file."""
        try:
            file_config = await asyncio.to_thread(self._load_yaml_file, config_path)

            # Update configuration with file values
            for key, value in file_config.items():
                if hasattr(self._config, key):
                    setattr(self._config, key, value)

        except Exception as e:
            # Log warning but don't fail - config files are optional
            print(f"Warning: Could not load config file {config_path}: {e}")

    def _load_yaml_file(self, config_path: Path) -> Dict[str, Any]:
        """Helper method to load YAML file synchronously for asyncio.to_thread."""
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}

    def get_ray_config(self) -> Dict[str, Any]:
        """Get Ray-specific configuration."""
        return {
            "address": self._config.ray_address,
            "dashboard_host": self._config.ray_dashboard_host,
            "dashboard_port": self._config.ray_dashboard_port,
            "num_cpus": self._config.ray_num_cpus,
            "num_gpus": self._config.ray_num_gpus,
            "object_store_memory": self._config.ray_object_store_memory,
        }

    def get_kubernetes_config(self) -> Dict[str, Any]:
        """Get Kubernetes-specific configuration."""
        return {
            "kubeconfig_path": self._config.kubeconfig_path,
            "context": self._config.kubernetes_context,
            "namespace": self._config.kubernetes_namespace,
        }

    def get_gke_config(self) -> Dict[str, Any]:
        """Get GKE-specific configuration."""
        return {
            "project_id": self._config.gcp_project_id,
            "credentials_path": self._config.gcp_credentials_path,
            "region": self._config.gke_region,
            "zone": self._config.gke_zone,
        }

    def get_gcp_config(self) -> Dict[str, Any]:
        """Get GCP-specific configuration."""
        return {
            "project_id": self._config.gcp_project_id,
            "credentials_path": self._config.gcp_credentials_path,
        }

    def get_provider_config(
        self, provider: Union[str, ConfigProvider]
    ) -> Dict[str, Any]:
        """Get configuration for a specific provider."""
        if isinstance(provider, str):
            provider = ConfigProvider(provider)

        if provider == ConfigProvider.RAY:
            return self.get_ray_config()
        elif provider == ConfigProvider.KUBERNETES:
            return self.get_kubernetes_config()
        elif provider == ConfigProvider.GKE:
            return self.get_gke_config()
        elif provider == ConfigProvider.LOCAL:
            return self.get_ray_config()
        else:
            return {}

    def get_template(
        self, resource_type: str, template_name: str = "basic"
    ) -> Dict[str, Any]:
        """Get a resource template."""
        return self._config.templates.get(resource_type, {}).get(template_name, {})

    def get_cluster_template(
        self, provider: Union[str, ConfigProvider], template_name: str = "basic"
    ) -> Dict[str, Any]:
        """Get cluster template for a specific provider."""
        if isinstance(provider, str):
            provider = ConfigProvider(provider)

        if provider == ConfigProvider.GKE:
            return self.get_template("gke_cluster", template_name)
        else:
            return self.get_template("ray_cluster", template_name)

    def detect_environment(self) -> Dict[str, Any]:
        """Detect current environment and available providers."""
        detected = {
            "ray_available": self._is_ray_available(),
            "kubernetes_available": self._is_kubernetes_available(),
            "gke_available": self._is_gke_available(),
            "in_cluster": self._is_in_kubernetes_cluster(),
            "providers": [],
        }

        # Determine available providers
        if detected["gke_available"]:
            detected["providers"].append("gke")
        if detected["kubernetes_available"]:
            detected["providers"].append("kubernetes")
        if detected["ray_available"]:
            detected["providers"].append("ray")

        # Suggest default provider
        if detected["gke_available"]:
            detected["default_provider"] = "gke"
        elif detected["kubernetes_available"]:
            detected["default_provider"] = "kubernetes"
        else:
            detected["default_provider"] = "ray"

        return detected

    def _is_ray_available(self) -> bool:
        """Check if Ray is available."""
        try:
            import ray

            return True
        except ImportError:
            return False

    def _is_kubernetes_available(self) -> bool:
        """Check if Kubernetes client is available and configured."""
        try:
            import kubernetes

            # Check if kubeconfig exists or we're in cluster
            return (
                self._config.kubeconfig_path
                and os.path.exists(self._config.kubeconfig_path)
                or os.path.exists(os.path.expanduser("~/.kube/config"))
                or self._is_in_kubernetes_cluster()
            )
        except ImportError:
            return False

    def _is_gke_available(self) -> bool:
        """Check if GKE is available and configured."""
        from ..foundation.import_utils import is_google_cloud_available

        # Check if Google Cloud SDK is available
        if not is_google_cloud_available():
            return False

        # Check if GCP credentials are available
        credentials_available = (
            (
                self._config.gcp_credentials_path
                and os.path.exists(self._config.gcp_credentials_path)
            )
            or bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
            or self._is_in_gke_cluster()
        )
        return credentials_available

    def _is_in_kubernetes_cluster(self) -> bool:
        """Check if running inside a Kubernetes cluster."""
        return os.path.exists(
            "/var/run/secrets/kubernetes.io/serviceaccount"
        ) and os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token")

    def _is_in_gke_cluster(self) -> bool:
        """Check if running inside a GKE cluster."""
        # Check GKE metadata server
        try:
            import requests

            response = requests.get(
                "http://metadata.google.internal/computeMetadata/v1/instance/attributes/cluster-name",
                headers={"Metadata-Flavor": "Google"},
                timeout=2,
            )
            return response.status_code == 200
        except:
            return False

    def validate_config(self) -> Dict[str, Any]:
        """Validate current configuration."""
        issues = []
        warnings = []

        # Validate Ray configuration
        if self._config.ray_address:
            if not (
                self._config.ray_address.startswith("ray://")
                or ":" in self._config.ray_address
            ):
                issues.append(
                    "ray_address must be in format 'ray://host:port' or 'host:port'"
                )

        # Validate Kubernetes configuration
        if self._config.kubeconfig_path and not os.path.exists(
            self._config.kubeconfig_path
        ):
            issues.append(
                f"kubeconfig_path does not exist: {self._config.kubeconfig_path}"
            )

        # Validate GKE configuration
        if self._config.gcp_credentials_path and not os.path.exists(
            self._config.gcp_credentials_path
        ):
            issues.append(
                f"gcp_credentials_path does not exist: {self._config.gcp_credentials_path}"
            )

        # Check for missing required settings based on detected environment
        env_detection = self.detect_environment()
        if "gke" in env_detection["providers"] and not self._config.gcp_project_id:
            warnings.append("GKE detected but no gcp_project_id configured")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "environment": env_detection,
        }

    def export_config(self, include_defaults: bool = False) -> Dict[str, Any]:
        """Export current configuration as a dictionary."""
        config_dict = {}

        # Export non-default values only (unless include_defaults=True)
        default_config = UnifiedConfig()

        for field_name in self._config.__dataclass_fields__:
            current_value = getattr(self._config, field_name)
            default_value = getattr(default_config, field_name)

            if include_defaults or current_value != default_value:
                config_dict[field_name] = current_value

        return config_dict

    @property
    def config(self) -> UnifiedConfig:
        """Get the current configuration object."""
        return self._config


# Global configuration manager instance
_config_manager: Optional[UnifiedConfigManager] = None


async def get_config_manager() -> UnifiedConfigManager:
    """Get the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = UnifiedConfigManager()
        await _config_manager.initialize()
    return _config_manager


def get_config_manager_sync() -> UnifiedConfigManager:
    """Get the global configuration manager instance (synchronous)."""
    global _config_manager
    if _config_manager is None:
        _config_manager = UnifiedConfigManager()
        # Note: Initialization will happen on first async call
    return _config_manager
