"""Cloud provider tool schemas for Ray MCP server."""

from typing import Any, Dict

from .schema_utils import (
    build_cloud_provider_schema,
    build_gke_cluster_schema,
    get_cloud_provider_property,
    get_integer_with_min,
    get_string_property,
)


def get_detect_cloud_provider_schema() -> Dict[str, Any]:
    """Schema for detect_cloud_provider tool."""
    return {
        "type": "object",
        "properties": {},
    }


def get_check_environment_schema() -> Dict[str, Any]:
    """Schema for check_environment tool."""
    return build_cloud_provider_schema(include_all=True, required_provider=False)


def get_authenticate_cloud_provider_schema() -> Dict[str, Any]:
    """Schema for authenticate_cloud_provider tool."""
    additional_properties = {
        "service_account_path": get_string_property(
            "Path to service account JSON file (GKE only)"
        ),
        "project_id": get_string_property("Google Cloud project ID (GKE only)"),
        "aws_access_key_id": get_string_property("AWS access key ID (AWS only)"),
        "aws_secret_access_key": get_string_property(
            "AWS secret access key (AWS only)"
        ),
        "region": get_string_property("Cloud provider region"),
        "config_file": get_string_property("Path to configuration file"),
        "context": get_string_property("Context name for configuration"),
    }
    return build_cloud_provider_schema(additional_properties, required_provider=True)


def get_list_cloud_clusters_schema() -> Dict[str, Any]:
    """Schema for list_cloud_clusters tool."""
    additional_properties = {
        "project_id": get_string_property("Google Cloud project ID (GKE only)"),
        "zone": get_string_property("Zone to list clusters from (GKE only)"),
    }
    return build_cloud_provider_schema(additional_properties, required_provider=True)


def get_connect_cloud_cluster_schema() -> Dict[str, Any]:
    """Schema for connect_cloud_cluster tool."""
    additional_properties = {
        "context": get_string_property("Kubernetes context name (local only)"),
    }
    return build_gke_cluster_schema(additional_properties, required_cluster_name=True)


def get_create_cloud_cluster_schema() -> Dict[str, Any]:
    """Schema for create_cloud_cluster tool."""
    return {
        "type": "object",
        "properties": {
            "provider": {
                **get_cloud_provider_property(),
                "enum": ["gke"],
                "description": "Cloud provider: 'gke' for Google Kubernetes Engine",
            },
            "cluster_spec": {
                "type": "object",
                "description": "Cluster specification for the cloud provider",
                "properties": {
                    "name": get_string_property("Name of the cluster to create"),
                    "zone": get_string_property("Zone to create the cluster in"),
                    "node_count": get_integer_with_min(
                        1, "Number of nodes in the cluster", 3
                    ),
                    "machine_type": get_string_property(
                        "Machine type for cluster nodes", "e2-medium"
                    ),
                },
                "required": ["name", "zone"],
            },
            "project_id": get_string_property("Google Cloud project ID (GKE only)"),
        },
        "required": ["provider", "cluster_spec"],
    }


def get_get_cloud_cluster_info_schema() -> Dict[str, Any]:
    """Schema for get_cloud_cluster_info tool."""
    return build_gke_cluster_schema(required_cluster_name=True)


def get_get_cloud_provider_status_schema() -> Dict[str, Any]:
    """Schema for get_cloud_provider_status tool."""
    return build_cloud_provider_schema(include_all=True, required_provider=False)


def get_disconnect_cloud_provider_schema() -> Dict[str, Any]:
    """Schema for disconnect_cloud_provider tool."""
    return build_cloud_provider_schema(required_provider=True)


def get_get_cloud_config_template_schema() -> Dict[str, Any]:
    """Schema for get_cloud_config_template tool."""
    additional_properties = {
        "config_type": {
            "type": "string",
            "enum": ["authentication", "cluster", "full"],
            "default": "full",
            "description": "Type of configuration template: 'authentication' for auth config, 'cluster' for cluster config, 'full' for complete config",
        },
    }
    return build_cloud_provider_schema(additional_properties, required_provider=True)
