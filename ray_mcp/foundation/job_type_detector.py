"""Job type detection utility for Ray MCP server."""

import re
from typing import Any, Dict, Optional


class JobTypeDetector:
    """Utility class for detecting job types based on identifiers and system state."""

    @staticmethod
    def detect_from_id(
        job_id: str, system_state: Dict[str, Any], explicit_job_type: str = "auto"
    ) -> str:
        """Detect job type based on job ID patterns and system state.

        Args:
            job_id: The job identifier to analyze
            system_state: Current system state from StateManager
            explicit_job_type: Explicitly specified job type ("auto", "local", "kubernetes", "k8s")

        Returns:
            str: Detected job type ("local" or "kubernetes")
        """
        if explicit_job_type and explicit_job_type.lower() != "auto":
            normalized_type = explicit_job_type.lower()
            return (
                "kubernetes"
                if normalized_type in ["kubernetes", "k8s"]
                else normalized_type
            )

        # If no job_id provided, fall back to general system detection
        if not job_id:
            return JobTypeDetector.detect_from_system_state(system_state)

        # UUID-like format suggests local Ray job
        if re.match(
            r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$", job_id
        ):
            return "local"

        # Ray job submission format
        if job_id.startswith("raysubmit_"):
            return "local"

        # Kubernetes resource name format suggests KubeRay job
        if re.match(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", job_id) and len(job_id) <= 63:
            return "kubernetes"

        # Fall back to system state detection
        return JobTypeDetector.detect_from_system_state(system_state)

    @staticmethod
    def detect_cluster_type_from_name(
        cluster_name: Optional[str], explicit_cluster_type: str = "auto"
    ) -> str:
        """Detect cluster type based on cluster name patterns.

        Args:
            cluster_name: The cluster name to analyze (can be None)
            explicit_cluster_type: Explicitly specified type ("auto", "local", "kubernetes", "k8s")

        Returns:
            str: Detected cluster type ("local" or "kubernetes")
        """
        if explicit_cluster_type and explicit_cluster_type.lower() != "auto":
            normalized_type = explicit_cluster_type.lower()
            return (
                "kubernetes"
                if normalized_type in ["kubernetes", "k8s"]
                else normalized_type
            )

        if not cluster_name:
            return "local"

        # Kubernetes resource name format suggests KubeRay cluster
        if (
            re.match(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", cluster_name)
            and len(cluster_name) <= 63
        ):
            return "kubernetes"

        # Default to local cluster type if no patterns match
        return "local"

    @staticmethod
    def detect_from_system_state(system_state: Dict[str, Any]) -> str:
        """Detect job type based on current system state.

        Args:
            system_state: Current system state from StateManager

        Returns:
            str: Detected job type ("local" or "kubernetes")
        """
        try:
            gke_connection = system_state.get("cloud_provider_connections", {}).get(
                "gke", {}
            )

            # Priority 1: Check for active cloud provider connections (GKE, etc.)
            if gke_connection.get("connected", False):
                return "kubernetes"

            # Priority 2: Check for general Kubernetes connection
            if system_state.get("kubernetes_connected", False):
                return "kubernetes"

            # Priority 3: Check for existing KubeRay clusters
            kuberay_clusters = system_state.get("kuberay_clusters", {})
            if kuberay_clusters:
                return "kubernetes"

            # Priority 4: If we have any indication of Kubernetes/GKE availability,
            # prefer kubernetes (for ephemeral cluster creation) over local
            if gke_connection or system_state.get("cloud_provider_connections", {}).get(
                "gke"
            ):
                return "kubernetes"

            # Priority 5: Check if local Ray is initialized
            if system_state.get("initialized", False):
                return "local"

            return "local"
        except Exception:
            return "local"

    @staticmethod
    def detect_from_identifier(identifier: str, system_state: Dict[str, Any]) -> str:
        """Detect job type based on identifier patterns and system state.

        This is an alias for detect_from_id for backward compatibility.

        Args:
            identifier: The job/cluster identifier to analyze
            system_state: Current system state from StateManager

        Returns:
            str: Detected job type ("local" or "kubernetes")
        """
        return JobTypeDetector.detect_from_id(identifier, system_state)
