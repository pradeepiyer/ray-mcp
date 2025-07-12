"""Centralized schema registry for Ray MCP tools."""

from typing import Any, Dict, List, Optional


class SchemaRegistry:
    """Central registry for commonly used JSON schemas across Ray MCP tools."""

    @staticmethod
    def kubernetes_resources_schema() -> Dict[str, Any]:
        """Schema for Kubernetes resource requests and limits."""
        return {
            "type": "object",
            "description": "Kubernetes resource requests and limits for CPU, memory, and GPU",
            "properties": {
                "requests": {
                    "type": "object",
                    "description": "Minimum resource requirements",
                    "properties": {
                        "cpu": {
                            "type": "string",
                            "description": "CPU request (e.g., '1000m', '2')",
                        },
                        "memory": {
                            "type": "string",
                            "description": "Memory request (e.g., '2Gi', '1024Mi')",
                        },
                        "nvidia.com/gpu": {
                            "type": "string",
                            "description": "GPU request (e.g., '1', '2')",
                        },
                    },
                    "additionalProperties": True,
                },
                "limits": {
                    "type": "object",
                    "description": "Maximum resource limits",
                    "properties": {
                        "cpu": {
                            "type": "string",
                            "description": "CPU limit (e.g., '2000m', '4')",
                        },
                        "memory": {
                            "type": "string",
                            "description": "Memory limit (e.g., '4Gi', '2048Mi')",
                        },
                        "nvidia.com/gpu": {
                            "type": "string",
                            "description": "GPU limit (e.g., '1', '2')",
                        },
                    },
                    "additionalProperties": True,
                },
            },
            "additionalProperties": False,
        }

    @staticmethod
    def tolerations_schema() -> Dict[str, Any]:
        """Schema for Kubernetes pod tolerations."""
        return {
            "type": "array",
            "description": "Tolerations for pod scheduling on tainted nodes",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Taint key to tolerate"},
                    "operator": {
                        "type": "string",
                        "enum": ["Equal", "Exists"],
                        "description": "Operator for matching the taint",
                    },
                    "value": {
                        "type": "string",
                        "description": "Taint value to tolerate (when operator is Equal)",
                    },
                    "effect": {
                        "type": "string",
                        "enum": ["NoSchedule", "PreferNoSchedule", "NoExecute"],
                        "description": "Taint effect to tolerate",
                    },
                    "tolerationSeconds": {
                        "type": "integer",
                        "description": "Seconds to tolerate NoExecute effect",
                    },
                },
                "additionalProperties": False,
            },
        }

    @staticmethod
    def node_selector_schema() -> Dict[str, Any]:
        """Schema for Kubernetes node selector."""
        return {
            "type": "object",
            "description": "Node selector for pod scheduling (key-value pairs)",
            "additionalProperties": {"type": "string"},
        }

    @staticmethod
    def job_type_schema(include_all: bool = False) -> Dict[str, Any]:
        """Schema for job type enumeration.

        Args:
            include_all: Whether to include 'all' option for listing operations
        """
        enum_values = ["local", "kubernetes", "k8s", "auto"]
        if include_all:
            enum_values.append("all")

        return {
            "type": "string",
            "enum": enum_values,
            "default": "auto",
            "description": (
                "Type of job: 'local' for local Ray clusters, "
                "'kubernetes'/'k8s' for KubeRay jobs, "
                "'auto' for automatic detection"
                + (", 'all' for all job types" if include_all else "")
            ),
        }

    @staticmethod
    def cluster_type_schema(include_all: bool = False) -> Dict[str, Any]:
        """Schema for cluster type enumeration.

        Args:
            include_all: Whether to include 'all' option for listing operations
        """
        enum_values = ["local", "kubernetes", "k8s", "auto"]
        if include_all:
            enum_values.append("all")

        return {
            "type": "string",
            "enum": enum_values,
            "default": "auto",
            "description": (
                "Type of cluster: 'local' for local Ray clusters, "
                "'kubernetes'/'k8s' for KubeRay clusters, "
                "'auto' for automatic detection"
                + (", 'all' for all cluster types" if include_all else "")
            ),
        }

    @staticmethod
    def kubernetes_namespace_schema() -> Dict[str, Any]:
        """Schema for Kubernetes namespace."""
        return {
            "type": "string",
            "default": "default",
            "description": "Kubernetes namespace (only used for KubeRay operations)",
            "pattern": "^[a-z0-9]([-a-z0-9]*[a-z0-9])?$",
            "maxLength": 63,
        }

    @staticmethod
    def cloud_provider_schema(include_all: bool = False) -> Dict[str, Any]:
        """Schema for cloud provider enumeration.

        Args:
            include_all: Whether to include comprehensive provider list
        """
        enum_values = ["gke", "local"]
        if include_all:
            # Future cloud providers can be added here
            enum_values.extend(["eks", "aks"])

        return {
            "type": "string",
            "enum": enum_values,
            "description": (
                "Cloud provider: 'gke' for Google Kubernetes Engine, "
                "'local' for local clusters"
                + (", 'eks' for AWS EKS, 'aks' for Azure AKS" if include_all else "")
            ),
        }

    @staticmethod
    def port_schema(
        min_port: int = 1000, max_port: int = 65535, allow_null: bool = True
    ) -> Dict[str, Any]:
        """Schema for port number validation.

        Args:
            min_port: Minimum allowed port number
            max_port: Maximum allowed port number
            allow_null: Whether to allow null values
        """
        schema = {
            "type": ["integer"] + (["null"] if allow_null else []),
            "minimum": min_port,
            "maximum": max_port,
            "description": f"Port number between {min_port} and {max_port}",
        }
        return schema

    @staticmethod
    def identifier_schema(identifier_type: str = "job") -> Dict[str, Any]:
        """Schema for job/cluster identifiers.

        Args:
            identifier_type: Type of identifier ("job", "cluster", etc.)
        """
        return {
            "type": "string",
            "description": f"Unique identifier for the {identifier_type}",
            "minLength": 1,
            "maxLength": 253,  # Maximum Kubernetes resource name length
        }

    @staticmethod
    def entrypoint_schema() -> Dict[str, Any]:
        """Schema for job entrypoint commands."""
        return {
            "type": "string",
            "description": "Command to execute for the job (e.g., 'python train.py')",
            "minLength": 1,
        }

    @staticmethod
    def runtime_env_schema() -> Dict[str, Any]:
        """Schema for Ray runtime environment."""
        return {
            "type": "object",
            "description": "Ray runtime environment configuration",
            "properties": {
                "pip": {
                    "type": "array",
                    "description": "List of pip packages to install",
                    "items": {"type": "string"},
                },
                "conda": {
                    "type": "object",
                    "description": "Conda environment specification",
                },
                "env_vars": {
                    "type": "object",
                    "description": "Environment variables to set",
                    "additionalProperties": {"type": "string"},
                },
                "working_dir": {
                    "type": "string",
                    "description": "Working directory for the job",
                },
            },
            "additionalProperties": True,
        }

    @staticmethod
    def kubernetes_config_schema() -> Dict[str, Any]:
        """Schema for Kubernetes-specific configuration."""
        return {
            "type": "object",
            "description": "Kubernetes-specific configuration for KubeRay operations",
            "properties": {
                "namespace": SchemaRegistry.kubernetes_namespace_schema(),
                "cluster_name": {
                    "type": "string",
                    "description": "Name of the KubeRay cluster",
                    "pattern": "^[a-z0-9]([-a-z0-9]*[a-z0-9])?$",
                    "maxLength": 63,
                },
                "job_name": {
                    "type": "string",
                    "description": "Name of the KubeRay job",
                    "pattern": "^[a-z0-9]([-a-z0-9]*[a-z0-9])?$",
                    "maxLength": 63,
                },
                "image": {
                    "type": "string",
                    "description": "Container image for Ray pods",
                    "default": "rayproject/ray:2.47.0",
                },
                "service_type": {
                    "type": "string",
                    "enum": ["ClusterIP", "NodePort", "LoadBalancer"],
                    "default": "LoadBalancer",
                    "description": "Kubernetes service type for Ray head node",
                },
                "tolerations": SchemaRegistry.tolerations_schema(),
                "node_selector": SchemaRegistry.node_selector_schema(),
                "resources": SchemaRegistry.kubernetes_resources_schema(),
                "ttl_seconds_after_finished": {
                    "type": "integer",
                    "description": "Seconds to keep job after completion",
                    "default": 86400,
                },
                "shutdown_after_job_finishes": {
                    "type": "boolean",
                    "description": "Whether to shut down cluster after job completion",
                },
            },
            "additionalProperties": True,
        }

    @staticmethod
    def pagination_schema() -> Dict[str, Any]:
        """Schema for pagination parameters."""
        return {
            "page": {
                "type": "integer",
                "minimum": 1,
                "description": "Page number for pagination (1-based)",
            },
            "page_size": {
                "type": "integer",
                "minimum": 1,
                "maximum": 1000,
                "default": 100,
                "description": "Number of items per page",
            },
        }

    @staticmethod
    def log_retrieval_schema() -> Dict[str, Any]:
        """Schema for log retrieval parameters."""
        return {
            "num_lines": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10000,
                "default": 100,
                "description": "Maximum number of log lines to retrieve",
            },
            "include_errors": {
                "type": "boolean",
                "default": False,
                "description": "Whether to include error analysis in the response",
            },
            "max_size_mb": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "default": 10,
                "description": "Maximum log size in megabytes",
            },
        }
