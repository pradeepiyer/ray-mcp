"""Cluster management tool schemas for Ray MCP server."""

from typing import Any, Dict

from .schema_utils import (
    build_basic_cluster_schema,
    get_boolean_property,
    get_cluster_type_property,
    get_integer_with_min,
    get_kubernetes_resources_schema,
    get_node_selector_schema,
    get_port_property,
    get_resource_requests_limits_schema,
    get_service_type_schema,
    get_string_property,
    get_tolerations_schema,
)


def get_init_ray_cluster_schema() -> Dict[str, Any]:
    """Schema for init_ray_cluster tool."""
    return {
        "type": "object",
        "properties": {
            "address": get_string_property(
                "Ray cluster address to connect to (e.g., '127.0.0.1:10001'). If provided, connects to existing cluster via dashboard API; if not provided, creates new cluster based on cluster_type. IMPORTANT: When connecting to a Ray cluster running on GKE/Kubernetes, you MUST specify cluster_type='kubernetes' to ensure proper coordination with the GKE connection. Connection uses dashboard API (port 8265) for all cluster operations."
            ),
            "cluster_type": {
                **get_cluster_type_property(include_auto=False),
                "default": "local",
                "description": "Type of cluster to create or connect to. 'local' for local Ray clusters, 'kubernetes'/'k8s' for KubeRay clusters on Kubernetes. REQUIRED when connecting to existing Ray clusters on GKE/Kubernetes via address parameter.",
            },
            "kubernetes_config": {
                "type": "object",
                "description": "Kubernetes-specific configuration for KubeRay clusters. Only used when cluster_type is 'kubernetes' or 'k8s'.",
                "properties": {
                    "namespace": get_string_property(
                        "Kubernetes namespace to deploy the Ray cluster in", "default"
                    ),
                    "cluster_name": get_string_property(
                        "Name for the Ray cluster (auto-generated if not provided)"
                    ),
                    "image": get_string_property(
                        "Container image for Ray pods (defaults to ray:2.47.0)"
                    ),
                    "service_account": get_string_property(
                        "Kubernetes service account for Ray pods"
                    ),
                    "node_selector": get_node_selector_schema(),
                    "tolerations": get_tolerations_schema(),
                    "service_type": get_service_type_schema(),
                    "service_annotations": {
                        "type": "object",
                        "description": "Custom service annotations for cloud provider configuration (e.g., load balancer settings)",
                        "additionalProperties": {"type": "string"},
                    },
                    "enable_ingress": get_boolean_property(
                        "Whether to enable ingress for Ray dashboard", False
                    ),
                    "auto_scale": get_boolean_property(
                        "Whether to enable autoscaling for worker nodes", False
                    ),
                    "min_replicas": get_integer_with_min(
                        0,
                        "Minimum number of worker replicas when autoscaling is enabled",
                        1,
                    ),
                    "max_replicas": get_integer_with_min(
                        1,
                        "Maximum number of worker replicas when autoscaling is enabled",
                        10,
                    ),
                },
            },
            "num_cpus": get_integer_with_min(
                1,
                "Number of CPUs for head node (local clusters) or head node pod (Kubernetes clusters)",
                1,
            ),
            "num_gpus": get_integer_with_min(
                0,
                "Number of GPUs for head node (local clusters) or head node pod (Kubernetes clusters)",
            ),
            "object_store_memory": get_integer_with_min(
                0,
                "Object store memory in bytes for head node (local clusters) or head node pod (Kubernetes clusters)",
            ),
            "resources": {
                "type": "object",
                "description": "Resource requests and limits for Kubernetes pods. Only used when cluster_type is 'kubernetes' or 'k8s'.",
                "properties": {
                    "head_node": {
                        **get_kubernetes_resources_schema(),
                        "description": "Resources for head node pod",
                    },
                    "worker_nodes": {
                        **get_kubernetes_resources_schema(),
                        "description": "Resources for worker node pods",
                    },
                },
            },
            "worker_nodes": {
                "type": "array",
                "description": "Worker node configuration. CRITICAL: Pass empty array [] for head-node-only clusters (when user says 'only head node' or 'no worker nodes'). Omit this parameter for default behavior (2 workers). Pass array with worker configs for custom workers.",
                "items": {
                    "type": "object",
                    "properties": {
                        "num_cpus": get_integer_with_min(
                            1, "Number of CPUs for this worker node"
                        ),
                        "num_gpus": get_integer_with_min(
                            0, "Number of GPUs for this worker node"
                        ),
                        "object_store_memory": get_integer_with_min(
                            0, "Object store memory in bytes for this worker node"
                        ),
                        "resources": {
                            "type": "object",
                            "description": "Additional custom resources for this worker node",
                        },
                        "node_name": get_string_property(
                            "Optional name for this worker node"
                        ),
                        "image": get_string_property(
                            "Container image for this worker node (Kubernetes only)"
                        ),
                        "node_selector": get_node_selector_schema(),
                        "tolerations": get_tolerations_schema(),
                    },
                    "required": ["num_cpus"],
                },
            },
            "head_node_port": {
                **get_port_property(min_port=10000, allow_null=True),
                "description": "Port for head node (only used for local clusters, if None, a free port will be found)",
            },
            "dashboard_port": {
                **get_port_property(allow_null=True),
                "description": "Port for Ray dashboard (only used for local clusters, if None, a free port will be found)",
            },
            "head_node_host": get_string_property(
                "Host address for head node (only used for local clusters)", "127.0.0.1"
            ),
        },
    }


def get_stop_ray_cluster_schema() -> Dict[str, Any]:
    """Schema for stop_ray_cluster tool."""
    return build_basic_cluster_schema()


def get_inspect_ray_cluster_schema() -> Dict[str, Any]:
    """Schema for inspect_ray_cluster tool."""
    return build_basic_cluster_schema()


def get_scale_ray_cluster_schema() -> Dict[str, Any]:
    """Schema for scale_ray_cluster tool."""
    additional_properties = {
        "worker_replicas": {
            **get_integer_with_min(0, "Number of worker replicas to scale to"),
            "required": True,
        },
    }
    schema = build_basic_cluster_schema(additional_properties)
    schema["required"] = ["worker_replicas"]
    return schema


def get_list_ray_clusters_schema() -> Dict[str, Any]:
    """Schema for list_ray_clusters tool."""
    additional_properties = {
        "cluster_type": {
            **get_cluster_type_property(),
            "enum": ["local", "kubernetes", "k8s", "all"],
            "default": "all",
            "description": "Type of clusters to list: 'local' for local Ray clusters, 'kubernetes'/'k8s' for KubeRay clusters, 'all' for both types",
        },
    }
    return build_basic_cluster_schema(additional_properties)
