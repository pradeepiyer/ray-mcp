"""Pure prompt-driven unified Ray MCP manager that composes focused components."""

from typing import Any, Dict

from ..cloud.cloud_provider_manager import CloudProviderManager
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
        self._job_manager = JobManager()
        self._log_manager = LogManager()
        self._kubernetes_manager = KubernetesManager()
        self._kuberay_cluster_manager = KubeRayClusterManager()
        self._kuberay_job_manager = KubeRayJobManager()
        self._cloud_provider_manager = CloudProviderManager()

    # =================================================================
    # PUBLIC PROMPT-DRIVEN INTERFACE: Only 3 methods
    # =================================================================

    async def handle_cluster_request(self, prompt: str) -> Dict[str, Any]:
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
            # Detect environment and route to appropriate manager
            if self._is_kubernetes_environment(prompt):
                # Check if it's KubeRay or general Kubernetes
                if "ray" in prompt.lower():
                    return await self._kuberay_cluster_manager.execute_request(prompt)
                else:
                    return await self._kubernetes_manager.execute_request(prompt)
            else:
                return await self._cluster_manager.execute_request(prompt)
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def handle_job_request(self, prompt: str) -> Dict[str, Any]:
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
            # Detect environment and route to appropriate manager
            if self._is_kubernetes_environment(prompt):
                return await self._kuberay_job_manager.execute_request(prompt)
            else:
                return await self._job_manager.execute_request(prompt)
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def handle_cloud_request(self, prompt: str) -> Dict[str, Any]:
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
            return {"status": "error", "message": str(e)}

    # =================================================================
    # PRIVATE IMPLEMENTATION: Utilities only
    # =================================================================

    def _is_kubernetes_environment(self, prompt: str) -> bool:
        """Detect if prompt is for Kubernetes/KubeRay operations."""
        k8s_keywords = [
            "kubernetes",
            "k8s",
            "kuberay",
            "namespace",
            "kubectl",
            "kubeconfig",
        ]
        prompt_lower = prompt.lower()
        return any(keyword in prompt_lower for keyword in k8s_keywords)
