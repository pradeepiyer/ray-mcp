"""Core enums for Ray MCP."""

from enum import Enum


class CloudProvider(Enum):
    """Supported cloud providers."""

    GKE = "gke"
    LOCAL = "local"


class AuthenticationType(Enum):
    """Authentication types for cloud providers."""

    SERVICE_ACCOUNT = "service_account"
    KUBECONFIG = "kubeconfig"
    IN_CLUSTER = "in_cluster"
