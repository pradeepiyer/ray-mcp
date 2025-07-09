"""Cloud provider tool schemas for Ray MCP server."""

from typing import Any, Dict


def get_detect_cloud_provider_schema() -> Dict[str, Any]:
    """Schema for detect_cloud_provider tool."""
    return {
        "type": "object",
        "properties": {},
    }


def get_check_environment_schema() -> Dict[str, Any]:
    """Schema for check_environment tool."""
    return {
        "type": "object",
        "properties": {
            "provider": {
                "type": "string",
                "enum": ["all", "gke", "local"],
                "default": "all",
                "description": "Cloud provider to check: 'all' for all providers, 'gke' for Google Kubernetes Engine, 'local' for local environment",
            },
        },
    }


def get_authenticate_cloud_provider_schema() -> Dict[str, Any]:
    """Schema for authenticate_cloud_provider tool."""
    return {
        "type": "object",
        "properties": {
            "provider": {
                "type": "string",
                "enum": ["gke", "local"],
                "description": "Cloud provider to authenticate with: 'gke' for Google Kubernetes Engine, 'local' for local environment",
            },
            "service_account_path": {
                "type": "string",
                "description": "Path to service account JSON file (GKE only)",
            },
            "project_id": {
                "type": "string",
                "description": "Google Cloud project ID (GKE only)",
            },
            "aws_access_key_id": {
                "type": "string",
                "description": "AWS access key ID (AWS only)",
            },
            "aws_secret_access_key": {
                "type": "string",
                "description": "AWS secret access key (AWS only)",
            },
            "region": {
                "type": "string",
                "description": "Cloud provider region",
            },
            "config_file": {
                "type": "string",
                "description": "Path to configuration file",
            },
            "context": {
                "type": "string",
                "description": "Context name for configuration",
            },
        },
        "required": ["provider"],
    }


def get_list_cloud_clusters_schema() -> Dict[str, Any]:
    """Schema for list_cloud_clusters tool."""
    return {
        "type": "object",
        "properties": {
            "provider": {
                "type": "string",
                "enum": ["gke", "local"],
                "description": "Cloud provider: 'gke' for Google Kubernetes Engine, 'local' for local clusters",
            },
            "project_id": {
                "type": "string",
                "description": "Google Cloud project ID (GKE only)",
            },
            "zone": {
                "type": "string",
                "description": "Zone to list clusters from (GKE only)",
            },
        },
        "required": ["provider"],
    }


def get_connect_cloud_cluster_schema() -> Dict[str, Any]:
    """Schema for connect_cloud_cluster tool."""
    return {
        "type": "object",
        "properties": {
            "provider": {
                "type": "string",
                "enum": ["gke", "local"],
                "description": "Cloud provider: 'gke' for Google Kubernetes Engine, 'local' for local clusters",
            },
            "cluster_name": {
                "type": "string",
                "description": "Name of the cluster to connect to",
            },
            "zone": {
                "type": "string",
                "description": "Zone of the cluster (GKE only)",
            },
            "project_id": {
                "type": "string",
                "description": "Google Cloud project ID (GKE only)",
            },
            "context": {
                "type": "string",
                "description": "Kubernetes context name (local only)",
            },
        },
        "required": ["provider", "cluster_name"],
    }


def get_create_cloud_cluster_schema() -> Dict[str, Any]:
    """Schema for create_cloud_cluster tool."""
    return {
        "type": "object",
        "properties": {
            "provider": {
                "type": "string",
                "enum": ["gke"],
                "description": "Cloud provider: 'gke' for Google Kubernetes Engine",
            },
            "cluster_spec": {
                "type": "object",
                "description": "Cluster specification for the cloud provider",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the cluster to create",
                    },
                    "zone": {
                        "type": "string",
                        "description": "Zone to create the cluster in",
                    },
                    "node_count": {
                        "type": "integer",
                        "minimum": 1,
                        "default": 3,
                        "description": "Number of nodes in the cluster",
                    },
                    "machine_type": {
                        "type": "string",
                        "default": "e2-medium",
                        "description": "Machine type for cluster nodes",
                    },
                },
                "required": ["name", "zone"],
            },
            "project_id": {
                "type": "string",
                "description": "Google Cloud project ID (GKE only)",
            },
        },
        "required": ["provider", "cluster_spec"],
    }


def get_get_cloud_cluster_info_schema() -> Dict[str, Any]:
    """Schema for get_cloud_cluster_info tool."""
    return {
        "type": "object",
        "properties": {
            "provider": {
                "type": "string",
                "enum": ["gke", "local"],
                "description": "Cloud provider: 'gke' for Google Kubernetes Engine, 'local' for local clusters",
            },
            "cluster_name": {
                "type": "string",
                "description": "Name of the cluster to get information about",
            },
            "zone": {
                "type": "string",
                "description": "Zone of the cluster (GKE only)",
            },
            "project_id": {
                "type": "string",
                "description": "Google Cloud project ID (GKE only)",
            },
        },
        "required": ["provider", "cluster_name"],
    }


def get_get_cloud_provider_status_schema() -> Dict[str, Any]:
    """Schema for get_cloud_provider_status tool."""
    return {
        "type": "object",
        "properties": {
            "provider": {
                "type": "string",
                "enum": ["all", "gke", "local"],
                "default": "all",
                "description": "Cloud provider to get status for: 'all' for all providers, 'gke' for Google Kubernetes Engine, 'local' for local environment",
            },
        },
    }


def get_disconnect_cloud_provider_schema() -> Dict[str, Any]:
    """Schema for disconnect_cloud_provider tool."""
    return {
        "type": "object",
        "properties": {
            "provider": {
                "type": "string",
                "enum": ["gke", "local"],
                "description": "Cloud provider to disconnect from: 'gke' for Google Kubernetes Engine, 'local' for local environment",
            },
        },
        "required": ["provider"],
    }


def get_get_cloud_config_template_schema() -> Dict[str, Any]:
    """Schema for get_cloud_config_template tool."""
    return {
        "type": "object",
        "properties": {
            "provider": {
                "type": "string",
                "enum": ["gke", "local"],
                "description": "Cloud provider to get config template for: 'gke' for Google Kubernetes Engine, 'local' for local environment",
            },
            "config_type": {
                "type": "string",
                "enum": ["authentication", "cluster", "full"],
                "default": "full",
                "description": "Type of configuration template: 'authentication' for auth config, 'cluster' for cluster config, 'full' for complete config",
            },
        },
        "required": ["provider"],
    }
