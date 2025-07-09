"""Cluster management tool schemas for Ray MCP server."""

from typing import Any, Dict


def get_init_ray_cluster_schema() -> Dict[str, Any]:
    """Schema for init_ray_cluster tool."""
    return {
        "type": "object",
        "properties": {
            "address": {
                "type": "string",
                "description": "Ray cluster address to connect to (e.g., '127.0.0.1:10001'). If provided, connects to existing cluster via dashboard API; if not provided, creates new cluster based on cluster_type. IMPORTANT: When connecting to a Ray cluster running on GKE/Kubernetes, you MUST specify cluster_type='kubernetes' to ensure proper coordination with the GKE connection. Connection uses dashboard API (port 8265) for all cluster operations.",
            },
            "cluster_type": {
                "type": "string",
                "enum": ["local", "kubernetes", "k8s"],
                "default": "local",
                "description": "Type of cluster to create or connect to. 'local' for local Ray clusters, 'kubernetes'/'k8s' for KubeRay clusters on Kubernetes. REQUIRED when connecting to existing Ray clusters on GKE/Kubernetes via address parameter.",
            },
            "kubernetes_config": {
                "type": "object",
                "description": "Kubernetes-specific configuration for KubeRay clusters. Only used when cluster_type is 'kubernetes' or 'k8s'.",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "default": "default",
                        "description": "Kubernetes namespace to deploy the Ray cluster in",
                    },
                    "cluster_name": {
                        "type": "string",
                        "description": "Name for the Ray cluster (auto-generated if not provided)",
                    },
                    "image": {
                        "type": "string",
                        "description": "Container image for Ray pods (defaults to ray:2.47.0)",
                    },
                    "service_account": {
                        "type": "string",
                        "description": "Kubernetes service account for Ray pods",
                    },
                    "node_selector": {
                        "type": "object",
                        "description": "Node selector for pod scheduling",
                    },
                    "tolerations": {
                        "type": "array",
                        "description": "Tolerations for pod scheduling",
                        "items": {
                            "type": "object",
                            "properties": {
                                "key": {"type": "string"},
                                "operator": {"type": "string"},
                                "value": {"type": "string"},
                                "effect": {"type": "string"},
                                "tolerationSeconds": {"type": "integer"},
                            },
                        },
                    },
                    "service_type": {
                        "type": "string",
                        "enum": ["ClusterIP", "NodePort", "LoadBalancer"],
                        "default": "LoadBalancer",
                        "description": "Kubernetes service type for Ray head service. 'LoadBalancer' exposes dashboard externally (recommended for cloud), 'NodePort' exposes on node ports, 'ClusterIP' is cluster-internal only",
                    },
                    "service_annotations": {
                        "type": "object",
                        "description": "Custom service annotations for cloud provider configuration (e.g., load balancer settings)",
                        "additionalProperties": {"type": "string"},
                    },
                    "enable_ingress": {
                        "type": "boolean",
                        "default": False,
                        "description": "Whether to enable ingress for Ray dashboard",
                    },
                    "auto_scale": {
                        "type": "boolean",
                        "default": False,
                        "description": "Whether to enable autoscaling for worker nodes",
                    },
                    "min_replicas": {
                        "type": "integer",
                        "minimum": 0,
                        "default": 1,
                        "description": "Minimum number of worker replicas when autoscaling is enabled",
                    },
                    "max_replicas": {
                        "type": "integer",
                        "minimum": 1,
                        "default": 10,
                        "description": "Maximum number of worker replicas when autoscaling is enabled",
                    },
                },
            },
            "num_cpus": {
                "type": "integer",
                "minimum": 1,
                "default": 1,
                "description": "Number of CPUs for head node (local clusters) or head node pod (Kubernetes clusters)",
            },
            "num_gpus": {
                "type": "integer",
                "minimum": 0,
                "description": "Number of GPUs for head node (local clusters) or head node pod (Kubernetes clusters)",
            },
            "object_store_memory": {
                "type": "integer",
                "minimum": 0,
                "description": "Object store memory in bytes for head node (local clusters) or head node pod (Kubernetes clusters)",
            },
            "resources": {
                "type": "object",
                "description": "Resource requests and limits for Kubernetes pods. Only used when cluster_type is 'kubernetes' or 'k8s'.",
                "properties": {
                    "head_node": {
                        "type": "object",
                        "description": "Resources for head node pod",
                        "properties": {
                            "requests": {
                                "type": "object",
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
                            },
                            "limits": {
                                "type": "object",
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
                            },
                        },
                    },
                    "worker_nodes": {
                        "type": "object",
                        "description": "Resources for worker node pods",
                        "properties": {
                            "requests": {
                                "type": "object",
                                "properties": {
                                    "cpu": {
                                        "type": "string",
                                        "description": "CPU request (e.g., '500m', '1')",
                                    },
                                    "memory": {
                                        "type": "string",
                                        "description": "Memory request (e.g., '1Gi', '512Mi')",
                                    },
                                    "nvidia.com/gpu": {
                                        "type": "string",
                                        "description": "GPU request (e.g., '1', '2')",
                                    },
                                },
                            },
                            "limits": {
                                "type": "object",
                                "properties": {
                                    "cpu": {
                                        "type": "string",
                                        "description": "CPU limit (e.g., '1000m', '2')",
                                    },
                                    "memory": {
                                        "type": "string",
                                        "description": "Memory limit (e.g., '2Gi', '1024Mi')",
                                    },
                                    "nvidia.com/gpu": {
                                        "type": "string",
                                        "description": "GPU limit (e.g., '1', '2')",
                                    },
                                },
                            },
                        },
                    },
                },
            },
            "worker_nodes": {
                "type": "array",
                "description": "Worker node configuration. CRITICAL: Pass empty array [] for head-node-only clusters (when user says 'only head node' or 'no worker nodes'). Omit this parameter for default behavior (2 workers). Pass array with worker configs for custom workers.",
                "items": {
                    "type": "object",
                    "properties": {
                        "num_cpus": {
                            "type": "integer",
                            "minimum": 1,
                            "description": "Number of CPUs for this worker node",
                        },
                        "num_gpus": {
                            "type": "integer",
                            "minimum": 0,
                            "description": "Number of GPUs for this worker node",
                        },
                        "object_store_memory": {
                            "type": "integer",
                            "minimum": 0,
                            "description": "Object store memory in bytes for this worker node",
                        },
                        "resources": {
                            "type": "object",
                            "description": "Additional custom resources for this worker node",
                        },
                        "node_name": {
                            "type": "string",
                            "description": "Optional name for this worker node",
                        },
                        "image": {
                            "type": "string",
                            "description": "Container image for this worker node (Kubernetes only)",
                        },
                        "node_selector": {
                            "type": "object",
                            "description": "Node selector for this worker node (Kubernetes only)",
                        },
                        "tolerations": {
                            "type": "array",
                            "description": "Tolerations for this worker node (Kubernetes only)",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "key": {"type": "string"},
                                    "operator": {"type": "string"},
                                    "value": {"type": "string"},
                                    "effect": {"type": "string"},
                                    "tolerationSeconds": {"type": "integer"},
                                },
                            },
                        },
                    },
                    "required": ["num_cpus"],
                },
            },
            "head_node_port": {
                "type": ["integer", "null"],
                "minimum": 10000,
                "maximum": 65535,
                "description": "Port for head node (only used for local clusters, if None, a free port will be found)",
            },
            "dashboard_port": {
                "type": ["integer", "null"],
                "minimum": 1000,
                "maximum": 65535,
                "description": "Port for Ray dashboard (only used for local clusters, if None, a free port will be found)",
            },
            "head_node_host": {
                "type": "string",
                "default": "127.0.0.1",
                "description": "Host address for head node (only used for local clusters)",
            },
        },
    }


def get_stop_ray_cluster_schema() -> Dict[str, Any]:
    """Schema for stop_ray_cluster tool."""
    return {
        "type": "object",
        "properties": {
            "cluster_name": {
                "type": "string",
                "description": "Name of the Ray cluster to stop/delete (required for KubeRay clusters, ignored for local clusters)",
            },
            "cluster_type": {
                "type": "string",
                "enum": ["local", "kubernetes", "k8s", "auto"],
                "default": "auto",
                "description": "Type of cluster: 'local' for local Ray clusters, 'kubernetes'/'k8s' for KubeRay clusters, 'auto' for automatic detection",
            },
            "namespace": {
                "type": "string",
                "default": "default",
                "description": "Kubernetes namespace (only used for KubeRay clusters)",
            },
        },
    }


def get_inspect_ray_cluster_schema() -> Dict[str, Any]:
    """Schema for inspect_ray_cluster tool."""
    return {
        "type": "object",
        "properties": {
            "cluster_name": {
                "type": "string",
                "description": "Name of the Ray cluster to inspect (required for KubeRay clusters, ignored for local clusters)",
            },
            "cluster_type": {
                "type": "string",
                "enum": ["local", "kubernetes", "k8s", "auto"],
                "default": "auto",
                "description": "Type of cluster: 'local' for local Ray clusters, 'kubernetes'/'k8s' for KubeRay clusters, 'auto' for automatic detection",
            },
            "namespace": {
                "type": "string",
                "default": "default",
                "description": "Kubernetes namespace (only used for KubeRay clusters)",
            },
        },
    }


def get_scale_ray_cluster_schema() -> Dict[str, Any]:
    """Schema for scale_ray_cluster tool."""
    return {
        "type": "object",
        "properties": {
            "worker_replicas": {
                "type": "integer",
                "minimum": 0,
                "description": "Number of worker replicas to scale to",
            },
            "cluster_name": {
                "type": "string",
                "description": "Name of the Ray cluster to scale (required for KubeRay clusters, ignored for local clusters)",
            },
            "cluster_type": {
                "type": "string",
                "enum": ["local", "kubernetes", "k8s", "auto"],
                "default": "auto",
                "description": "Type of cluster: 'local' for local Ray clusters, 'kubernetes'/'k8s' for KubeRay clusters, 'auto' for automatic detection",
            },
            "namespace": {
                "type": "string",
                "default": "default",
                "description": "Kubernetes namespace (only used for KubeRay clusters)",
            },
        },
        "required": ["worker_replicas"],
    }


def get_list_ray_clusters_schema() -> Dict[str, Any]:
    """Schema for list_ray_clusters tool."""
    return {
        "type": "object",
        "properties": {
            "cluster_type": {
                "type": "string",
                "enum": ["local", "kubernetes", "k8s", "all"],
                "default": "all",
                "description": "Type of clusters to list: 'local' for local Ray clusters, 'kubernetes'/'k8s' for KubeRay clusters, 'all' for both types",
            },
            "namespace": {
                "type": "string",
                "default": "default",
                "description": "Kubernetes namespace (only used for KubeRay clusters)",
            },
        },
    }
