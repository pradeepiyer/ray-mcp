"""Pure prompt-driven unified Ray MCP manager that composes focused components."""

from typing import Any

from ..cloud.cloud_provider_manager import CloudProviderManager
from ..foundation.logging_utils import error_response
from ..kubernetes.kuberay_cluster_manager import KubeRayClusterManager
from ..kubernetes.kuberay_job_manager import KubeRayJobManager
from ..kubernetes.kubernetes_manager import KubernetesManager
from .cluster_manager import ClusterManager
from .job_manager import JobManager
from .log_manager import LogManager


class RayUnifiedManager:
    """Pure prompt-driven unified manager that composes focused Ray MCP components.

    This class provides a clean prompt-driven interface over specialized components,
    enabling natural language control of all Ray operations.
    """

    def __init__(self):
        # Initialize specialized managers - no state/port managers needed
        self._cluster_manager = ClusterManager()
        self._job_manager = JobManager(unified_manager=self)
        self._log_manager = LogManager()
        self._kubernetes_manager = KubernetesManager()
        self._kuberay_cluster_manager = KubeRayClusterManager()
        self._kuberay_job_manager = KubeRayJobManager()
        self._cloud_provider_manager = CloudProviderManager()

    # =================================================================
    # PUBLIC PROMPT-DRIVEN INTERFACE: Only 3 methods
    # =================================================================

    async def handle_cluster_request(self, prompt: str) -> dict[str, Any]:
        """Handle cluster operations using natural language prompts.

        Examples:
            - "create a local cluster with 4 CPUs"
            - "connect to cluster at 10.0.0.1:10001"
            - "stop the current cluster"
            - "inspect cluster status"
            - "create Ray cluster named ml-cluster with 3 workers on kubernetes"
            - "connect to kubernetes cluster with context my-cluster"
        """
        try:
            # Parse the action first to get the environment
            from ..llm_parser import get_parser

            action = await get_parser().parse_cluster_action(prompt)
            environment = action.get("environment", "auto")

            # Route based on parsed environment, with fallback to prompt detection
            if environment == "local":
                return await self._cluster_manager.execute_request(prompt)
            elif environment == "kubernetes":
                # Check if it's KubeRay or general Kubernetes
                if "ray" in prompt.lower():
                    return await self._kuberay_cluster_manager.execute_request(prompt)
                else:
                    return await self._kubernetes_manager.execute_request(prompt)
            else:
                # Fallback to prompt-based detection for "auto" or unspecified environment
                if self._is_kubernetes_environment(prompt):
                    # Check if it's KubeRay or general Kubernetes
                    if "ray" in prompt.lower():
                        return await self._kuberay_cluster_manager.execute_request(
                            prompt
                        )
                    else:
                        return await self._kubernetes_manager.execute_request(prompt)
                else:
                    return await self._cluster_manager.execute_request(prompt)
        except Exception as e:
            return error_response(str(e))

    async def handle_job_request(self, prompt: str) -> dict[str, Any]:
        """Handle job operations using natural language prompts.

        Examples:
            - "submit job with script train.py"
            - "list all running jobs"
            - "get logs for job raysubmit_123"
            - "cancel job raysubmit_456"
            - "create Ray job with training script train.py on kubernetes"
            - "get logs for job data-processing in namespace production"
        """
        try:
            # Parse the action first to get the environment
            from ..llm_parser import get_parser

            action = await get_parser().parse_job_action(prompt)
            environment = action.get("environment", "auto")

            # Route based on parsed environment, with fallback to prompt detection
            if environment == "local":
                return await self._job_manager.execute_request(prompt)
            elif environment == "kubernetes":
                return await self._kuberay_job_manager.execute_request(prompt)
            else:
                # Fallback to prompt-based detection for "auto" or unspecified environment
                # If we have a local Ray cluster running, prefer that over Kubernetes
                if self._job_manager._is_ray_ready():
                    return await self._job_manager.execute_request(prompt)
                elif self._is_kubernetes_environment(prompt):
                    return await self._kuberay_job_manager.execute_request(prompt)
                else:
                    return await self._job_manager.execute_request(prompt)
        except Exception as e:
            return error_response(str(e))

    async def handle_cloud_request(self, prompt: str) -> dict[str, Any]:
        """Handle cloud operations using natural language prompts.

        Examples:
            - "authenticate with GCP project ml-experiments"
            - "list all GKE clusters"
            - "connect to GKE cluster production-cluster"
            - "check cloud environment setup"
            - "create GKE cluster ml-cluster with 3 nodes"
        """
        try:
            return await self._cloud_provider_manager.execute_request(prompt)
        except Exception as e:
            return error_response(str(e))

    # =================================================================
    # PRIVATE IMPLEMENTATION: Utilities only
    # =================================================================

    def _is_kubernetes_environment(self, prompt: str) -> bool:
        """Detect if prompt is for Kubernetes/KubeRay operations.

        Priority order:
        1. If prompt explicitly mentions "local" -> route to local (False)
        2. If prompt explicitly mentions Kubernetes keywords -> route to kubernetes (True)
        3. If we're connected to Kubernetes cluster -> route to kubernetes as default (True)
        4. Otherwise -> route to local (False)
        """
        prompt_lower = prompt.lower()

        # First priority: Check if prompt explicitly mentions "local"
        local_keywords = ["local", "localhost", "127.0.0.1"]
        if any(keyword in prompt_lower for keyword in local_keywords):
            return False

        # Second priority: Check if prompt explicitly mentions Kubernetes keywords
        k8s_keywords = [
            "kubernetes",
            "k8s",
            "kuberay",
            "gke",
            "gcp",
            "namespace",
            "kubectl",
            "kubeconfig",
        ]
        if any(keyword in prompt_lower for keyword in k8s_keywords):
            return True

        # Third priority: Check if we're connected to a Kubernetes cluster
        # This is only used as a default when no explicit environment is mentioned
        if self._is_kubernetes_connected():
            return True

        # Fallback: Route to local
        return False

    def _is_kubernetes_connected(self) -> bool:
        """Check if we're actually connected to a Kubernetes cluster."""
        try:
            # Check if Kubernetes client is available and we can load kube config
            return self._kuberay_job_manager._is_kubernetes_ready()
        except Exception:
            return False

    def get_dashboard_url(self) -> str:
        """Get the dashboard URL from the cluster manager."""
        if (
            hasattr(self._cluster_manager, "_dashboard_url")
            and self._cluster_manager._dashboard_url
        ):
            return self._cluster_manager._dashboard_url
        return "http://127.0.0.1:8265"  # Default fallback
