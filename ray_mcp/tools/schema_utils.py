"""Utility functions for building common schema patterns.

This module provides reusable schema components to eliminate duplication
across tool schemas and ensure consistency.
"""

from typing import Any, Dict, List, Optional


def get_cluster_type_property(include_auto: bool = True) -> Dict[str, Any]:
    """Get cluster type property schema with consistent options."""
    enum_values = ["local", "kubernetes", "k8s"]
    description = "Type of cluster: 'local' for local Ray clusters, 'kubernetes'/'k8s' for KubeRay clusters"

    if include_auto:
        enum_values.append("auto")
        description += ", 'auto' for automatic detection"

    return {
        "type": "string",
        "enum": enum_values,
        "default": "auto" if include_auto else "local",
        "description": description,
    }


def get_cloud_provider_property(include_all: bool = False) -> Dict[str, Any]:
    """Get cloud provider property schema with consistent options."""
    enum_values = ["gke", "local"]
    description = (
        "Cloud provider: 'gke' for Google Kubernetes Engine, 'local' for local clusters"
    )

    if include_all:
        enum_values.insert(0, "all")
        description = "Cloud provider: 'all' for all providers, " + description

    schema = {
        "type": "string",
        "enum": enum_values,
        "description": description,
    }

    if include_all:
        schema["default"] = "all"

    return schema


def get_kubernetes_namespace_property() -> Dict[str, Any]:
    """Get kubernetes namespace property schema."""
    return {
        "type": "string",
        "default": "default",
        "description": "Kubernetes namespace (only used for KubeRay clusters)",
    }


def get_cluster_name_property(required_for_kuberay: bool = True) -> Dict[str, Any]:
    """Get cluster name property schema."""
    description = "Name of the Ray cluster"
    if required_for_kuberay:
        description += " (required for KubeRay clusters, ignored for local clusters)"

    return {
        "type": "string",
        "description": description,
    }


def get_gke_project_id_property() -> Dict[str, Any]:
    """Get GKE project ID property schema."""
    return {
        "type": "string",
        "description": "Google Cloud project ID (GKE only)",
    }


def get_gke_zone_property() -> Dict[str, Any]:
    """Get GKE zone property schema."""
    return {
        "type": "string",
        "description": "Zone of the cluster (GKE only)",
    }


def get_port_property(
    min_port: int = 1000, max_port: int = 65535, allow_null: bool = True
) -> Dict[str, Any]:
    """Get port property schema with validation."""
    schema = {
        "type": "integer" if not allow_null else ["integer", "null"],
        "minimum": min_port,
        "maximum": max_port,
    }
    return schema


def get_resource_requests_limits_schema() -> Dict[str, Any]:
    """Get standard Kubernetes resource requests/limits schema."""
    return {
        "type": "object",
        "properties": {
            "cpu": {
                "type": "string",
                "description": "CPU request/limit (e.g., '500m', '1', '2')",
            },
            "memory": {
                "type": "string",
                "description": "Memory request/limit (e.g., '1Gi', '512Mi')",
            },
            "nvidia.com/gpu": {
                "type": "string",
                "description": "GPU request/limit (e.g., '1', '2')",
            },
        },
    }


def get_kubernetes_resources_schema() -> Dict[str, Any]:
    """Get complete Kubernetes resources schema with requests and limits."""
    return {
        "type": "object",
        "properties": {
            "requests": get_resource_requests_limits_schema(),
            "limits": get_resource_requests_limits_schema(),
        },
    }


def get_tolerations_schema() -> Dict[str, Any]:
    """Get Kubernetes tolerations schema."""
    return {
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
    }


def get_node_selector_schema() -> Dict[str, Any]:
    """Get Kubernetes node selector schema."""
    return {
        "type": "object",
        "description": "Node selector for pod scheduling",
    }


def get_service_type_schema() -> Dict[str, Any]:
    """Get Kubernetes service type schema."""
    return {
        "type": "string",
        "enum": ["ClusterIP", "NodePort", "LoadBalancer"],
        "default": "LoadBalancer",
        "description": "Kubernetes service type for Ray head service. 'LoadBalancer' exposes dashboard externally (recommended for cloud), 'NodePort' exposes on node ports, 'ClusterIP' is cluster-internal only",
    }


def get_integer_with_min(
    minimum: int, description: str, default: Optional[int] = None
) -> Dict[str, Any]:
    """Get integer property with minimum value validation."""
    schema = {
        "type": "integer",
        "minimum": minimum,
        "description": description,
    }
    if default is not None:
        schema["default"] = default
    return schema


def get_boolean_property(
    description: str, default: Optional[bool] = None
) -> Dict[str, Any]:
    """Get boolean property schema."""
    schema: Dict[str, Any] = {
        "type": "boolean",
        "description": description,
    }
    if default is not None:
        schema["default"] = default
    return schema


def get_string_property(
    description: str, default: Optional[str] = None
) -> Dict[str, Any]:
    """Get string property schema."""
    schema = {
        "type": "string",
        "description": description,
    }
    if default is not None:
        schema["default"] = default
    return schema


def build_basic_cluster_schema(
    additional_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build basic cluster schema with common properties."""
    properties = {
        "cluster_name": get_cluster_name_property(),
        "cluster_type": get_cluster_type_property(),
        "namespace": get_kubernetes_namespace_property(),
    }

    if additional_properties:
        properties.update(additional_properties)

    return {
        "type": "object",
        "properties": properties,
    }


def build_cloud_provider_schema(
    additional_properties: Optional[Dict[str, Any]] = None,
    include_all: bool = False,
    required_provider: bool = True,
) -> Dict[str, Any]:
    """Build basic cloud provider schema with common properties."""
    properties = {
        "provider": get_cloud_provider_property(include_all=include_all),
    }

    if additional_properties:
        properties.update(additional_properties)

    schema = {
        "type": "object",
        "properties": properties,
    }

    if required_provider:
        schema["required"] = ["provider"]

    return schema


def build_gke_cluster_schema(
    additional_properties: Optional[Dict[str, Any]] = None,
    required_cluster_name: bool = False,
) -> Dict[str, Any]:
    """Build GKE cluster schema with common GKE properties."""
    properties = {
        "provider": get_cloud_provider_property(),
        "cluster_name": get_string_property("Name of the cluster"),
        "project_id": get_gke_project_id_property(),
        "zone": get_gke_zone_property(),
    }

    if additional_properties:
        properties.update(additional_properties)

    required = ["provider"]
    if required_cluster_name:
        required.append("cluster_name")

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


def build_job_type_schema(include_all: bool = False) -> Dict[str, Any]:
    """Build job type schema for job-related tools."""
    enum_values = ["local", "kubernetes", "k8s", "auto"]
    description = "Type of job: 'local' for local Ray clusters, 'kubernetes'/'k8s' for KubeRay jobs, 'auto' for automatic detection"

    if include_all:
        enum_values.append("all")
        description += ", 'all' for all job types"

    return {
        "type": "string",
        "enum": enum_values,
        "default": "auto",
        "description": description,
    }
