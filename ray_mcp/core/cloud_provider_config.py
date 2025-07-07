"""Cloud provider configuration templates and management for Ray MCP."""

import json
import os
from typing import Any, Dict, Optional

import yaml

try:
    from ..logging_utils import LoggingUtility, ResponseFormatter
except ImportError:
    # Fallback for direct execution
    import os
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from logging_utils import LoggingUtility, ResponseFormatter

from .interfaces import CloudProvider, CloudProviderConfig, StateManager


class CloudProviderConfigManager(CloudProviderConfig):
    """Manages cloud provider configurations and templates."""

    def __init__(self, state_manager: Optional[StateManager] = None):
        self._state_manager = state_manager
        self._response_formatter = ResponseFormatter()
        self._config_cache = {}
        self._templates = self._load_templates()

    def get_provider_config(self, provider: CloudProvider) -> Dict[str, Any]:
        """Get configuration for a specific cloud provider."""
        return self._config_cache.get(provider.value, {})

    def load_provider_config(
        self, provider: CloudProvider, config_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """Load configuration for a specific cloud provider."""
        try:
            if config_file:
                with open(config_file, "r") as f:
                    if config_file.endswith(".yaml") or config_file.endswith(".yml"):
                        config = yaml.safe_load(f)
                    else:
                        config = json.load(f)
            else:
                config = self._load_default_config(provider)

            # Cache the configuration
            self._config_cache[provider.value] = config

            return self._response_formatter.format_success_response(
                provider=provider.value, config=config, loaded=True
            )

        except Exception as e:
            return self._response_formatter.format_error_response(
                f"load {provider.value} config", e
            )

    def validate_provider_config(
        self, provider: CloudProvider, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate configuration for a specific cloud provider."""
        try:
            if provider == CloudProvider.GKE:
                return self._validate_gke_config(config)
            else:
                return self._response_formatter.format_error_response(
                    f"validate {provider.value} config",
                    Exception(f"Validation not supported for {provider.value}"),
                )

        except Exception as e:
            return self._response_formatter.format_error_response(
                f"validate {provider.value} config", e
            )

    def get_cluster_template(
        self, provider: CloudProvider, cluster_type: str = "basic"
    ) -> Dict[str, Any]:
        """Get cluster template for a specific cloud provider."""
        try:
            template = self._templates.get(provider.value, {}).get(cluster_type)
            if not template:
                return self._response_formatter.format_error_response(
                    f"get {provider.value} template",
                    Exception(
                        f"Template '{cluster_type}' not found for {provider.value}"
                    ),
                )

            return self._response_formatter.format_success_response(
                provider=provider.value, cluster_type=cluster_type, template=template
            )

        except Exception as e:
            return self._response_formatter.format_error_response(
                f"get {provider.value} template", e
            )

    def _load_templates(self) -> Dict[str, Any]:
        """Load cloud provider templates."""
        return {
            "gke": {
                "basic": self._get_gke_basic_template(),
                "production": self._get_gke_production_template(),
                "gpu": self._get_gke_gpu_template(),
            },
        }

    def _load_default_config(self, provider: CloudProvider) -> Dict[str, Any]:
        """Load default configuration for a provider."""
        if provider == CloudProvider.GKE:
            return {
                "project_id": os.getenv("GOOGLE_CLOUD_PROJECT")
                or os.getenv("GCLOUD_PROJECT"),
                "region": os.getenv("GOOGLE_CLOUD_REGION") or "us-central1",
                "zone": os.getenv("GOOGLE_CLOUD_ZONE") or "us-central1-a",
                "service_account_path": os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
                "cluster_name_prefix": "ray-cluster",
                "node_pool_name": "ray-nodes",
                "machine_type": "n1-standard-2",
                "disk_size": 100,
                "num_nodes": 3,
                "enable_workload_identity": True,
                "enable_network_policy": True,
                "enable_ip_alias": True,
            }

        return {}

    def _get_gke_basic_template(self) -> Dict[str, Any]:
        """Get basic GKE cluster template."""
        return {
            "apiVersion": "ray.io/v1",
            "kind": "RayCluster",
            "metadata": {
                "name": "ray-cluster-gke",
                "namespace": "default",
                "labels": {"cloud-provider": "gke", "cluster-type": "basic"},
            },
            "spec": {
                "rayVersion": "2.8.0",
                "headGroupSpec": {
                    "replicas": 1,
                    "rayStartParams": {"dashboard-host": "0.0.0.0"},
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "name": "ray-head",
                                    "image": "rayproject/ray:2.8.0",
                                    "ports": [
                                        {"containerPort": 6379, "name": "gcs-server"},
                                        {"containerPort": 8265, "name": "dashboard"},
                                        {"containerPort": 10001, "name": "client"},
                                    ],
                                    "resources": {
                                        "requests": {"cpu": "1", "memory": "2Gi"},
                                        "limits": {"cpu": "2", "memory": "4Gi"},
                                    },
                                    "env": [
                                        {
                                            "name": "GOOGLE_CLOUD_PROJECT",
                                            "value": "${GOOGLE_CLOUD_PROJECT}",
                                        }
                                    ],
                                }
                            ],
                            "nodeSelector": {
                                "cloud.google.com/gke-nodepool": "ray-nodes"
                            },
                            "tolerations": [
                                {
                                    "key": "ray-node",
                                    "operator": "Equal",
                                    "value": "true",
                                    "effect": "NoSchedule",
                                }
                            ],
                        }
                    },
                },
                "workerGroupSpecs": [
                    {
                        "groupName": "worker-group",
                        "replicas": 2,
                        "rayStartParams": {},
                        "template": {
                            "spec": {
                                "containers": [
                                    {
                                        "name": "ray-worker",
                                        "image": "rayproject/ray:2.8.0",
                                        "resources": {
                                            "requests": {"cpu": "1", "memory": "2Gi"},
                                            "limits": {"cpu": "2", "memory": "4Gi"},
                                        },
                                        "env": [
                                            {
                                                "name": "GOOGLE_CLOUD_PROJECT",
                                                "value": "${GOOGLE_CLOUD_PROJECT}",
                                            }
                                        ],
                                    }
                                ],
                                "nodeSelector": {
                                    "cloud.google.com/gke-nodepool": "ray-nodes"
                                },
                                "tolerations": [
                                    {
                                        "key": "ray-node",
                                        "operator": "Equal",
                                        "value": "true",
                                        "effect": "NoSchedule",
                                    }
                                ],
                            }
                        },
                    }
                ],
            },
        }

    def _get_gke_production_template(self) -> Dict[str, Any]:
        """Get production GKE cluster template."""
        template = self._get_gke_basic_template()

        # Enhance for production
        template["spec"]["headGroupSpec"]["template"]["spec"]["containers"][0][
            "resources"
        ] = {
            "requests": {"cpu": "2", "memory": "8Gi"},
            "limits": {"cpu": "4", "memory": "16Gi"},
        }

        template["spec"]["workerGroupSpecs"][0]["replicas"] = 5
        template["spec"]["workerGroupSpecs"][0]["template"]["spec"]["containers"][0][
            "resources"
        ] = {
            "requests": {"cpu": "2", "memory": "8Gi"},
            "limits": {"cpu": "4", "memory": "16Gi"},
        }

        # Add monitoring and logging
        template["spec"]["headGroupSpec"]["template"]["spec"]["containers"][0][
            "env"
        ].extend(
            [
                {"name": "RAY_ENABLE_RECORD_ACTOR_TASK_LOGGING", "value": "1"},
                {"name": "RAY_BACKEND_LOG_LEVEL", "value": "info"},
            ]
        )

        return template

    def _get_gke_gpu_template(self) -> Dict[str, Any]:
        """Get GPU-enabled GKE cluster template."""
        template = self._get_gke_basic_template()

        # Add GPU resources
        template["spec"]["headGroupSpec"]["template"]["spec"]["containers"][0][
            "resources"
        ]["limits"]["nvidia.com/gpu"] = "1"
        template["spec"]["workerGroupSpecs"][0]["template"]["spec"]["containers"][0][
            "resources"
        ]["limits"]["nvidia.com/gpu"] = "1"

        # Add GPU node selector
        template["spec"]["headGroupSpec"]["template"]["spec"]["nodeSelector"][
            "accelerator"
        ] = "nvidia-tesla-k80"
        template["spec"]["workerGroupSpecs"][0]["template"]["spec"]["nodeSelector"][
            "accelerator"
        ] = "nvidia-tesla-k80"

        return template

    def _validate_gke_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate GKE configuration."""
        required_fields = ["project_id"]
        missing_fields = []

        for field in required_fields:
            if field not in config or not config[field]:
                missing_fields.append(field)

        if missing_fields:
            return self._response_formatter.format_error_response(
                "validate gke config",
                Exception(f"Missing required fields: {', '.join(missing_fields)}"),
            )

        # Validate project_id format
        project_id = config["project_id"]
        if not isinstance(project_id, str) or len(project_id) < 6:
            return self._response_formatter.format_error_response(
                "validate gke config", Exception("Invalid project_id format")
            )

        return self._response_formatter.format_success_response(
            provider="gke", valid=True, config=config
        )

    def save_config(
        self,
        provider: CloudProvider,
        config: Dict[str, Any],
        file_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Save configuration to file."""
        try:
            if not file_path:
                file_path = f"{provider.value}_config.yaml"

            with open(file_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False)

            return self._response_formatter.format_success_response(
                provider=provider.value, config_file=file_path, saved=True
            )

        except Exception as e:
            return self._response_formatter.format_error_response(
                f"save {provider.value} config", e
            )

    def get_available_templates(self, provider: CloudProvider) -> Dict[str, Any]:
        """Get list of available templates for a provider."""
        try:
            templates = list(self._templates.get(provider.value, {}).keys())
            return self._response_formatter.format_success_response(
                provider=provider.value, templates=templates
            )

        except Exception as e:
            return self._response_formatter.format_error_response(
                f"get {provider.value} templates", e
            )
