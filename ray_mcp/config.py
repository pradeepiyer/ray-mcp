"""Ray MCP configuration for cloud providers and Kubernetes."""

from dataclasses import dataclass
import json
import os
from typing import Optional


def _extract_project_id_from_service_account() -> Optional[str]:
    """Extract project ID from service account JSON file."""
    service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not service_account_path:
        return None

    try:
        with open(service_account_path, "r") as f:
            credentials_data = json.load(f)
            return credentials_data.get("project_id")
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None


@dataclass
class Config:
    """Configuration for Ray MCP cloud providers and Kubernetes."""

    # Kubernetes settings
    kubernetes_namespace: str = "default"

    # GCP settings
    gcp_project_id: Optional[str] = None
    gke_region: str = "us-central1"
    gke_zone: str = "us-central1-a"

    # AWS settings
    aws_region: str = "us-west-2"

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            kubernetes_namespace=os.getenv("KUBERNETES_NAMESPACE", "default"),
            gcp_project_id=os.getenv("GOOGLE_CLOUD_PROJECT")
            or _extract_project_id_from_service_account(),
            gke_region=os.getenv("GKE_REGION", "us-central1"),
            gke_zone=os.getenv("GKE_ZONE", "us-central1-a"),
            aws_region=os.getenv("AWS_DEFAULT_REGION", "us-west-2"),
        )


# Global configuration instance
config = Config.from_env()
