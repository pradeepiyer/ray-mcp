"""Natural language parsing for Ray operations."""

import re
from typing import Any, Dict, Optional


class ActionParser:
    """Parse natural language into structured actions."""

    # Cluster operations
    CLUSTER_CREATE = r"(?:create|start|init|setup|deploy).+cluster"
    CLUSTER_CONNECT = r"connect.+cluster|attach.+cluster"
    CLUSTER_STOP = r"(?:stop|shutdown|delete|destroy|terminate).+cluster"
    CLUSTER_SCALE = r"scale.+cluster|scale.+worker"
    CLUSTER_INSPECT = r"(?:inspect|status|info|describe|check|get).+cluster|show.+cluster.+(?:information|details|status|info)"
    CLUSTER_LIST = r"list.+cluster|show.+clusters"

    # Job operations
    JOB_LIST = r"(?:list|show|get).+job"
    JOB_SUBMIT = r"(?:submit|execute|start).+job|run\s+job"
    JOB_INSPECT = r"(?:inspect|status|check).+job"
    JOB_LOGS = r"(?:logs?|log).+job|get.+logs?"
    JOB_CANCEL = r"(?:cancel|stop|kill).+job"

    # Cloud operations
    CLOUD_AUTH = r"(?:auth|login|authenticate).+(?:gcp|google|gke|cloud)"
    CLOUD_LIST = r"(?:list|show|get).+(?:cluster|k8s|kubernetes|gke|gcp)"
    CLOUD_CONNECT = r"connect.+(?:gke|gcp|k8s|kubernetes)"
    CLOUD_CREATE = r"create.+(?:cluster|gke|gcp|k8s)"
    CLOUD_CHECK = r"(?:check|verify|test).+(?:env|auth|setup)"
    CLOUD_INFO = (
        r"(?:get|show|describe|info).+(?:cluster|gke|gcp).+(?:info|details|status)"
    )

    # Kubernetes operations
    K8S_CONNECT = r"connect.+(?:kubernetes|k8s|cluster).+(?:context|config)"
    K8S_DISCONNECT = r"disconnect.+(?:kubernetes|k8s|cluster)"
    K8S_INSPECT = r"(?:inspect|status|info|describe).+(?:kubernetes|k8s|cluster)"
    K8S_HEALTH = r"(?:health|check).+(?:kubernetes|k8s|cluster)"
    K8S_LIST_NAMESPACES = r"(?:list|show).+namespace"
    K8S_LIST_CONTEXTS = r"(?:list|show).+context"

    # KubeRay job operations
    KUBERAY_JOB_CREATE = (
        r"(?:create|deploy|submit).+(?:ray.+job|job.+ray).+(?:kubernetes|k8s|kuberay)"
    )
    KUBERAY_JOB_LIST = r"(?:list|show).+(?:ray.+job|job).+(?:kubernetes|k8s|kuberay)"
    KUBERAY_JOB_GET = r"(?:get|status|check).+(?:job|ray.+job)"
    KUBERAY_JOB_DELETE = r"(?:delete|remove|stop).+(?:job|ray.+job)"
    KUBERAY_JOB_LOGS = r"(?:logs?|log).+(?:job|ray.+job)"

    # KubeRay cluster operations
    KUBERAY_CLUSTER_CREATE = (
        r"(?:create|deploy).+(?:ray.+cluster|cluster.+ray).+(?:kubernetes|k8s|kuberay)"
    )
    KUBERAY_CLUSTER_LIST = (
        r"(?:list|show).+(?:ray.+cluster|cluster).+(?:kubernetes|k8s|kuberay)"
    )
    KUBERAY_CLUSTER_GET = r"(?:get|status|check).+(?:cluster|ray.+cluster)"
    KUBERAY_CLUSTER_SCALE = r"scale.+(?:cluster|ray.+cluster)"
    KUBERAY_CLUSTER_DELETE = r"(?:delete|remove|destroy).+(?:cluster|ray.+cluster)"

    @classmethod
    def parse_cluster_action(cls, prompt: str) -> Dict[str, Any]:
        """Parse cluster action from prompt."""
        prompt_lower = prompt.lower()

        if re.search(cls.CLUSTER_CREATE, prompt_lower):
            resources = cls._extract_resources(prompt)
            result = {
                "operation": "create",
                "environment": cls._detect_environment(prompt),
                "name": cls._extract_name(prompt),
                "head_only": "head only" in prompt_lower or "no worker" in prompt_lower,
            }
            # Flatten resource info
            if "cpu" in resources:
                result["cpus"] = resources["cpu"]
            if "gpu" in resources:
                result["gpus"] = resources["gpu"]
            if "workers" in resources:
                result["workers"] = resources["workers"]
            if "dashboard_port" in resources:
                result["dashboard_port"] = resources["dashboard_port"]
            return result
        elif re.search(cls.CLUSTER_CONNECT, prompt_lower):
            return {
                "operation": "connect",
                "address": cls._extract_address(prompt),
                "name": cls._extract_name(prompt),
            }
        elif re.search(cls.CLUSTER_STOP, prompt_lower):
            return {"operation": "stop", "name": cls._extract_name(prompt)}
        elif re.search(cls.CLUSTER_SCALE, prompt_lower):
            return {
                "operation": "scale",
                "name": cls._extract_name(prompt),
                "workers": cls._extract_number(prompt, "worker"),
            }
        elif re.search(cls.CLUSTER_INSPECT, prompt_lower):
            return {"operation": "inspect", "name": cls._extract_name(prompt)}
        elif re.search(cls.CLUSTER_LIST, prompt_lower):
            return {"operation": "list"}

        raise ValueError(f"Cannot understand cluster action: {prompt}")

    @classmethod
    def parse_job_action(cls, prompt: str) -> Dict[str, Any]:
        """Parse job action from prompt."""
        prompt_lower = prompt.lower()

        if re.search(cls.JOB_LOGS, prompt_lower):
            return {
                "operation": "logs",
                "job_id": cls._extract_job_id(prompt),
                "filter_errors": "error" in prompt_lower,
            }
        elif re.search(cls.JOB_SUBMIT, prompt_lower):
            return {
                "operation": "submit",
                "source": cls._extract_source_url(prompt),
                "script": cls._extract_script_path(prompt),
                "resources": cls._extract_resources(prompt),
            }
        elif re.search(cls.JOB_INSPECT, prompt_lower):
            return {"operation": "inspect", "job_id": cls._extract_job_id(prompt)}
        elif re.search(cls.JOB_CANCEL, prompt_lower):
            return {"operation": "cancel", "job_id": cls._extract_job_id(prompt)}
        elif re.search(cls.JOB_LIST, prompt_lower):
            return {"operation": "list"}

        raise ValueError(f"Cannot understand job action: {prompt}")

    @classmethod
    def parse_cloud_action(cls, prompt: str) -> Dict[str, Any]:
        """Parse cloud action from prompt."""
        prompt_lower = prompt.lower()

        if re.search(cls.CLOUD_AUTH, prompt_lower):
            return {
                "operation": "authenticate",
                "provider": "gcp",
                "project_id": cls._extract_project(prompt),
            }
        elif re.search(cls.CLOUD_LIST, prompt_lower):
            return {"operation": "list_clusters", "provider": "gcp"}
        elif re.search(cls.CLOUD_CONNECT, prompt_lower):
            return {
                "operation": "connect_cluster",
                "cluster_name": cls._extract_name(prompt),
                "provider": "gcp",
                "zone": cls._extract_zone(prompt),
            }
        elif re.search(cls.CLOUD_CREATE, prompt_lower):
            return {
                "operation": "create_cluster",
                "cluster_name": cls._extract_name(prompt),
                "provider": "gcp",
                "zone": cls._extract_zone(prompt),
            }
        elif re.search(cls.CLOUD_CHECK, prompt_lower):
            return {"operation": "check_environment"}
        elif re.search(cls.CLOUD_INFO, prompt_lower):
            return {
                "operation": "get_cluster_info",
                "cluster_name": cls._extract_name(prompt),
                "provider": "gcp",
                "zone": cls._extract_zone(prompt),
            }

        raise ValueError(f"Cannot understand cloud action: {prompt}")

    @classmethod
    def parse_kubernetes_action(cls, prompt: str) -> Dict[str, Any]:
        """Parse kubernetes action from prompt."""
        prompt_lower = prompt.lower()

        if re.search(cls.K8S_CONNECT, prompt_lower):
            return {
                "operation": "connect",
                "context": cls._extract_context(prompt),
                "config_file": cls._extract_config_file(prompt),
            }
        elif re.search(cls.K8S_DISCONNECT, prompt_lower):
            return {"operation": "disconnect"}
        elif re.search(cls.K8S_INSPECT, prompt_lower):
            return {"operation": "inspect"}
        elif re.search(cls.K8S_HEALTH, prompt_lower):
            return {"operation": "health_check"}
        elif re.search(cls.K8S_LIST_NAMESPACES, prompt_lower):
            return {"operation": "list_namespaces"}
        elif re.search(cls.K8S_LIST_CONTEXTS, prompt_lower):
            return {"operation": "list_contexts"}

        raise ValueError(f"Cannot understand kubernetes action: {prompt}")

    @classmethod
    def parse_kuberay_job_action(cls, prompt: str) -> Dict[str, Any]:
        """Parse KubeRay job action from prompt."""
        prompt_lower = prompt.lower()

        if re.search(cls.KUBERAY_JOB_CREATE, prompt_lower):
            return {
                "operation": "create",
                "script": cls._extract_script_path(prompt),
                "name": cls._extract_name(prompt),
                "namespace": cls._extract_namespace(prompt),
                "runtime_env": cls._extract_runtime_env(prompt),
            }
        elif re.search(cls.KUBERAY_JOB_LIST, prompt_lower):
            return {
                "operation": "list",
                "namespace": cls._extract_namespace(prompt),
            }
        elif re.search(cls.KUBERAY_JOB_GET, prompt_lower):
            return {
                "operation": "get",
                "name": cls._extract_job_name(prompt),
                "namespace": cls._extract_namespace(prompt),
            }
        elif re.search(cls.KUBERAY_JOB_DELETE, prompt_lower):
            return {
                "operation": "delete",
                "name": cls._extract_job_name(prompt),
                "namespace": cls._extract_namespace(prompt),
            }
        elif re.search(cls.KUBERAY_JOB_LOGS, prompt_lower):
            return {
                "operation": "logs",
                "name": cls._extract_job_name(prompt),
                "namespace": cls._extract_namespace(prompt),
            }

        raise ValueError(f"Cannot understand KubeRay job action: {prompt}")

    @classmethod
    def parse_kuberay_cluster_action(cls, prompt: str) -> Dict[str, Any]:
        """Parse KubeRay cluster action from prompt."""
        prompt_lower = prompt.lower()

        if re.search(cls.KUBERAY_CLUSTER_CREATE, prompt_lower):
            return {
                "operation": "create",
                "name": cls._extract_name(prompt),
                "namespace": cls._extract_namespace(prompt),
                "workers": cls._extract_number(prompt, "worker"),
                "head_resources": cls._extract_head_resources(prompt),
                "worker_resources": cls._extract_worker_resources(prompt),
            }
        elif re.search(cls.KUBERAY_CLUSTER_LIST, prompt_lower):
            return {
                "operation": "list",
                "namespace": cls._extract_namespace(prompt),
            }
        elif re.search(cls.KUBERAY_CLUSTER_GET, prompt_lower):
            return {
                "operation": "get",
                "name": cls._extract_cluster_name(prompt),
                "namespace": cls._extract_namespace(prompt),
            }
        elif re.search(cls.KUBERAY_CLUSTER_SCALE, prompt_lower):
            return {
                "operation": "scale",
                "name": cls._extract_cluster_name(prompt),
                "workers": cls._extract_number(prompt, "worker"),
                "namespace": cls._extract_namespace(prompt),
            }
        elif re.search(cls.KUBERAY_CLUSTER_DELETE, prompt_lower):
            return {
                "operation": "delete",
                "name": cls._extract_cluster_name(prompt),
                "namespace": cls._extract_namespace(prompt),
            }

        raise ValueError(f"Cannot understand KubeRay cluster action: {prompt}")

    # Helper extraction methods
    @staticmethod
    def _detect_environment(prompt: str) -> str:
        if re.search(r"\b(?:k8s|kubernetes|gke)\b", prompt, re.IGNORECASE):
            return "kubernetes"
        return "local"

    @staticmethod
    def _extract_resources(prompt: str) -> Dict[str, Any]:
        resources = {}
        if match := re.search(r"(\d+)\s*(?:cpu|core)", prompt, re.IGNORECASE):
            resources["cpu"] = int(match.group(1))
        if match := re.search(r"(\d+)\s*(?:gpu|nvidia)", prompt, re.IGNORECASE):
            resources["gpu"] = int(match.group(1))
        if match := re.search(r"(\d+)\s*worker", prompt, re.IGNORECASE):
            resources["workers"] = int(match.group(1))
        if match := re.search(r"dashboard\s+on\s+port\s+(\d+)", prompt, re.IGNORECASE):
            resources["dashboard_port"] = int(match.group(1))
        return resources

    @staticmethod
    def _extract_name(prompt: str) -> Optional[str]:
        if match := re.search(
            r"(?:named|cluster|called)\s+([^\s]+)", prompt, re.IGNORECASE
        ):
            return match.group(1)
        return None

    @staticmethod
    def _extract_address(prompt: str) -> Optional[str]:
        # Look for IP:port or hostname:port patterns
        if match := re.search(r"(?:at\s+)?([^\s]+:\d+)", prompt):
            return match.group(1)
        return None

    @staticmethod
    def _extract_source_url(prompt: str) -> Optional[str]:
        if match := re.search(r"https://github\.com/[^\s]+", prompt):
            return match.group(0)
        if match := re.search(r"s3://[^\s]+", prompt):
            return match.group(0)
        return None

    @staticmethod
    def _extract_script_path(prompt: str) -> Optional[str]:
        if match := re.search(r"([^\s]+\.py)", prompt):
            return match.group(1)
        return None

    @staticmethod
    def _extract_job_id(prompt: str) -> Optional[str]:
        if match := re.search(r"job[\s-]+([^\s]+)", prompt, re.IGNORECASE):
            return match.group(1)
        return None

    @staticmethod
    def _extract_number(prompt: str, context: str) -> Optional[int]:
        pattern = rf"(\d+)\s*{context}"
        if match := re.search(pattern, prompt, re.IGNORECASE):
            return int(match.group(1))
        return None

    @staticmethod
    def _extract_project(prompt: str) -> Optional[str]:
        if match := re.search(r"project\s+([^\s]+)", prompt, re.IGNORECASE):
            return match.group(1)
        return None

    @staticmethod
    def _extract_zone(prompt: str) -> Optional[str]:
        if match := re.search(r"(?:zone|region)\s+([^\s]+)", prompt, re.IGNORECASE):
            return match.group(1)
        return None

    @staticmethod
    def _extract_context(prompt: str) -> Optional[str]:
        if match := re.search(r"context\s+([^\s]+)", prompt, re.IGNORECASE):
            return match.group(1)
        return None

    @staticmethod
    def _extract_config_file(prompt: str) -> Optional[str]:
        if match := re.search(r"config\s+([^\s]+)", prompt, re.IGNORECASE):
            return match.group(1)
        return None

    @staticmethod
    def _extract_namespace(prompt: str) -> Optional[str]:
        if match := re.search(r"namespace\s+([^\s]+)", prompt, re.IGNORECASE):
            return match.group(1)
        return None

    @staticmethod
    def _extract_job_name(prompt: str) -> Optional[str]:
        if match := re.search(r"(?:job|ray.+job)\s+([^\s]+)", prompt, re.IGNORECASE):
            return match.group(1)
        return None

    @staticmethod
    def _extract_runtime_env(prompt: str) -> Optional[Dict[str, Any]]:
        # Extract runtime environment specifications from prompt
        runtime_env = {}
        if re.search(r"pip\s+install", prompt, re.IGNORECASE):
            runtime_env["pip"] = ["requirements.txt"]  # Default
        if match := re.search(r"working.+dir\s+([^\s]+)", prompt, re.IGNORECASE):
            runtime_env["working_dir"] = match.group(1)
        return runtime_env if runtime_env else None

    @staticmethod
    def _extract_cluster_name(prompt: str) -> Optional[str]:
        if match := re.search(
            r"(?:cluster|ray.+cluster)\s+([^\s]+)", prompt, re.IGNORECASE
        ):
            return match.group(1)
        return None

    @staticmethod
    def _extract_head_resources(prompt: str) -> Dict[str, str]:
        resources = {"cpu": "1", "memory": "2Gi"}  # defaults
        if match := re.search(r"head.+(\d+)\s*(?:cpu|core)", prompt, re.IGNORECASE):
            resources["cpu"] = match.group(1)
        if match := re.search(r"head.+(\d+)\s*(?:gb|gi)", prompt, re.IGNORECASE):
            resources["memory"] = f"{match.group(1)}Gi"
        return resources

    @staticmethod
    def _extract_worker_resources(prompt: str) -> Dict[str, str]:
        resources = {"cpu": "1", "memory": "2Gi"}  # defaults
        if match := re.search(r"worker.+(\d+)\s*(?:cpu|core)", prompt, re.IGNORECASE):
            resources["cpu"] = match.group(1)
        if match := re.search(r"worker.+(\d+)\s*(?:gb|gi)", prompt, re.IGNORECASE):
            resources["memory"] = f"{match.group(1)}Gi"
        return resources

    @staticmethod
    def _extract_location(prompt: str) -> Optional[str]:
        """Extract zone or location for GKE operations."""
        if match := re.search(
            r"(?:zone|location|region)\s+([^\s]+)", prompt, re.IGNORECASE
        ):
            return match.group(1)
        return None
