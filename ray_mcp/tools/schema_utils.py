"""Utility functions for building common schema patterns.

This module provides reusable schema components to eliminate duplication
across tool schemas and ensure consistency.
"""

from typing import Any, Dict, List, Optional

from .schema_registry import SchemaRegistry


def get_cluster_type_property(include_auto: bool = True) -> Dict[str, Any]:
    """Get cluster type property schema with consistent options."""
    schema = SchemaRegistry.cluster_type_schema(include_all=False)
    if not include_auto and "auto" in schema.get("enum", []):
        # Remove "auto" from enum if not requested
        enum_values = [v for v in schema["enum"] if v != "auto"]
        schema = schema.copy()
        schema["enum"] = enum_values
        # Update default if it was "auto"
        if schema.get("default") == "auto":
            schema["default"] = "local"
    return schema


def get_cloud_provider_property(include_all: bool = False) -> Dict[str, Any]:
    """Get cloud provider property schema with consistent options."""
    return SchemaRegistry.cloud_provider_schema(include_all=include_all)


def get_kubernetes_namespace_property() -> Dict[str, Any]:
    """Get Kubernetes namespace property schema."""
    return SchemaRegistry.kubernetes_namespace_schema()


def get_string_property(
    description: str, default: Optional[str] = None, **kwargs
) -> Dict[str, Any]:
    """Get basic string property schema with description."""
    schema = {"type": "string", "description": description}
    if default is not None:
        schema["default"] = default
    schema.update(kwargs)
    return schema


def get_integer_property(
    description: str,
    minimum: Optional[int] = None,
    maximum: Optional[int] = None,
    default: Optional[int] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Get integer property schema with optional constraints."""
    schema: Dict[str, Any] = {"type": "integer", "description": description}
    if minimum is not None:
        schema["minimum"] = minimum
    if maximum is not None:
        schema["maximum"] = maximum
    if default is not None:
        schema["default"] = default
    schema.update(kwargs)
    return schema


def get_boolean_property(
    description: str, default: Optional[bool] = None, **kwargs
) -> Dict[str, Any]:
    """Get boolean property schema with optional default."""
    schema: Dict[str, Any] = {"type": "boolean", "description": description}
    if default is not None:
        schema["default"] = default
    schema.update(kwargs)
    return schema


def get_array_property(
    description: str, items_schema: Optional[Dict[str, Any]] = None, **kwargs
) -> Dict[str, Any]:
    """Get array property schema with optional item constraints."""
    schema: Dict[str, Any] = {"type": "array", "description": description}
    if items_schema:
        schema["items"] = items_schema
    schema.update(kwargs)
    return schema


def get_object_property(
    description: str, properties: Optional[Dict[str, Any]] = None, **kwargs
) -> Dict[str, Any]:
    """Get object property schema with optional property definitions."""
    schema: Dict[str, Any] = {"type": "object", "description": description}
    if properties:
        schema["properties"] = properties
    schema.update(kwargs)
    return schema


def get_port_property(allow_null: bool = True, min_port: int = 1000) -> Dict[str, Any]:
    """Get port property schema."""
    return SchemaRegistry.port_schema(min_port=min_port, allow_null=allow_null)


def get_kubernetes_resources_property() -> Dict[str, Any]:
    """Get Kubernetes resources property schema."""
    return SchemaRegistry.kubernetes_resources_schema()


def get_tolerations_property() -> Dict[str, Any]:
    """Get Kubernetes tolerations property schema."""
    return SchemaRegistry.tolerations_schema()


def get_node_selector_property() -> Dict[str, Any]:
    """Get Kubernetes node selector property schema."""
    return SchemaRegistry.node_selector_schema()


def get_job_type_property(include_all: bool = False) -> Dict[str, Any]:
    """Get job type property schema."""
    return SchemaRegistry.job_type_schema(include_all=include_all)


def get_runtime_env_property() -> Dict[str, Any]:
    """Get Ray runtime environment property schema."""
    return SchemaRegistry.runtime_env_schema()


def get_kubernetes_config_property() -> Dict[str, Any]:
    """Get Kubernetes configuration property schema."""
    return SchemaRegistry.kubernetes_config_schema()


def get_pagination_properties() -> Dict[str, Any]:
    """Get pagination properties schema."""
    return SchemaRegistry.pagination_schema()


def get_log_retrieval_properties() -> Dict[str, Any]:
    """Get log retrieval properties schema."""
    return SchemaRegistry.log_retrieval_schema()


# Legacy functions for backward compatibility during refactoring
def get_integer_with_min(
    minimum: int, description: str, default: Optional[int] = None, **kwargs
) -> Dict[str, Any]:
    """Get integer property with minimum constraint."""
    return get_integer_property(description, minimum=minimum, default=default, **kwargs)


def build_cloud_provider_schema(
    additional_properties: Optional[Dict[str, Any]] = None,
    required_provider: bool = False,
    include_all: bool = False,
) -> Dict[str, Any]:
    """Build cloud provider schema with additional properties."""
    schema = {
        "type": "object",
        "properties": {
            "provider": get_cloud_provider_property(include_all=include_all)
        },
        "additionalProperties": False,
    }

    if additional_properties:
        schema["properties"].update(additional_properties)

    if required_provider:
        schema["required"] = ["provider"]

    return schema


def build_gke_cluster_schema(
    additional_properties: Optional[Dict[str, Any]] = None,
    required_cluster_name: bool = False,
) -> Dict[str, Any]:
    """Build GKE cluster schema with additional properties."""
    properties = {
        "cluster_name": get_string_property("Name of the GKE cluster"),
        "project_id": get_string_property("Google Cloud project ID"),
        "zone": get_string_property("GKE cluster zone"),
        "region": get_string_property("GKE cluster region"),
    }

    if additional_properties:
        properties.update(additional_properties)

    schema = {"type": "object", "properties": properties, "additionalProperties": False}

    if required_cluster_name:
        schema["required"] = ["cluster_name"]

    return schema


# Additional legacy functions needed by cluster_tools.py
def get_kubernetes_resources_schema() -> Dict[str, Any]:
    """Get Kubernetes resources schema."""
    return SchemaRegistry.kubernetes_resources_schema()


def get_node_selector_schema() -> Dict[str, Any]:
    """Get node selector schema."""
    return SchemaRegistry.node_selector_schema()


def get_resource_requests_limits_schema() -> Dict[str, Any]:
    """Get resource requests and limits schema."""
    return SchemaRegistry.kubernetes_resources_schema()


def get_service_type_schema() -> Dict[str, Any]:
    """Get Kubernetes service type schema."""
    return {
        "type": "string",
        "enum": ["ClusterIP", "NodePort", "LoadBalancer"],
        "default": "LoadBalancer",
        "description": "Kubernetes service type for Ray head node",
    }


def get_tolerations_schema() -> Dict[str, Any]:
    """Get tolerations schema."""
    return SchemaRegistry.tolerations_schema()


def build_basic_cluster_schema(
    additional_properties: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Build basic cluster schema."""
    properties = {
        "cluster_type": get_cluster_type_property(),
        "cluster_name": get_string_property("Name of the cluster"),
        "namespace": get_kubernetes_namespace_property(),
    }

    if additional_properties:
        properties.update(additional_properties)

    return {"type": "object", "properties": properties, "additionalProperties": True}
