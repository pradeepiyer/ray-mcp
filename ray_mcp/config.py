"""Simplified Ray MCP configuration - replaces 476-line system."""

from dataclasses import dataclass
import os
from typing import Optional


@dataclass
class Config:
    """Simple configuration for Ray MCP."""

    # Ray settings
    ray_address: Optional[str] = None
    ray_dashboard_port: int = 8265
    ray_num_cpus: Optional[int] = None
    ray_num_gpus: Optional[int] = None

    # Kubernetes settings
    kubernetes_namespace: str = "default"
    kubernetes_context: Optional[str] = None

    # GCP settings
    gcp_project_id: Optional[str] = None
    gke_region: str = "us-central1"
    gke_zone: str = "us-central1-a"

    # General settings
    log_level: str = "INFO"
    timeout_seconds: int = 300
    enhanced_output: bool = False

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""

        def safe_int(value: str, default: str) -> int:
            """Safely convert string to int with default fallback."""
            if not value or value.strip() == "":
                return int(default)
            return int(value)

        def safe_optional_int(value: str) -> Optional[int]:
            """Safely convert string to optional int."""
            if not value or value.strip() == "":
                return None
            return int(value)

        return cls(
            ray_address=os.getenv("RAY_ADDRESS") or None,
            ray_dashboard_port=safe_int(os.getenv("RAY_DASHBOARD_PORT", ""), "8265"),
            ray_num_cpus=safe_optional_int(os.getenv("RAY_NUM_CPUS", "")),
            ray_num_gpus=safe_optional_int(os.getenv("RAY_NUM_GPUS", "")),
            kubernetes_namespace=os.getenv("KUBERNETES_NAMESPACE", "default"),
            kubernetes_context=os.getenv("KUBERNETES_CONTEXT") or None,
            gcp_project_id=os.getenv("GOOGLE_CLOUD_PROJECT") or None,
            gke_region=os.getenv("GKE_REGION", "us-central1"),
            gke_zone=os.getenv("GKE_ZONE", "us-central1-a"),
            log_level=os.getenv("RAY_MCP_LOG_LEVEL", "INFO"),
            timeout_seconds=safe_int(os.getenv("RAY_MCP_TIMEOUT", ""), "300"),
            enhanced_output=os.getenv("RAY_MCP_ENHANCED_OUTPUT", "false").lower()
            == "true",
        )


# Global configuration instance
config = Config.from_env()
