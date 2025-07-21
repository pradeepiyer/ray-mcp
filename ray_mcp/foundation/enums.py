"""Core enums for Ray MCP."""

from enum import Enum


class CloudProvider(Enum):
    """Supported cloud providers."""

    GKE = "gke"
    AWS = "aws"
    LOCAL = "local"
