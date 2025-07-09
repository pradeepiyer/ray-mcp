"""Job management tool schemas for Ray MCP server."""

from typing import Any, Dict


def get_submit_ray_job_schema() -> Dict[str, Any]:
    """Schema for submit_ray_job tool."""
    return {
        "type": "object",
        "properties": {
            "entrypoint": {
                "type": "string",
                "description": "Entry point command for the job (required)",
            },
            "job_type": {
                "type": "string",
                "enum": ["local", "kubernetes", "k8s", "auto"],
                "default": "auto",
                "description": "Type of job to submit. 'local' for local Ray clusters, 'kubernetes'/'k8s' for KubeRay jobs, 'auto' for automatic detection based on cluster state (will use kubernetes if GKE is connected)",
            },
            "runtime_env": {
                "type": "object",
                "description": "Runtime environment configuration for the job",
            },
            "job_id": {
                "type": "string",
                "description": "Optional job ID (auto-generated if not provided)",
            },
            "metadata": {
                "type": "object",
                "description": "Optional metadata for the job",
            },
            "kubernetes_config": {
                "type": "object",
                "description": "Kubernetes-specific configuration for KubeRay jobs. Only used when job_type is 'kubernetes', 'k8s', or auto-detected as Kubernetes",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "default": "default",
                        "description": "Kubernetes namespace to deploy the job in",
                    },
                    "job_name": {
                        "type": "string",
                        "description": "Name for the RayJob resource (auto-generated if not provided)",
                    },
                    "cluster_selector": {
                        "type": "object",
                        "description": "Selector to choose existing Ray cluster for the job",
                    },
                    "suspend": {
                        "type": "boolean",
                        "default": False,
                        "description": "Whether to suspend the job initially",
                    },
                    "ttl_seconds_after_finished": {
                        "type": "integer",
                        "minimum": 0,
                        "default": 86400,
                        "description": "Time to live for the job after completion (in seconds)",
                    },
                    "active_deadline_seconds": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Maximum time the job can run before being terminated (in seconds)",
                    },
                    "backoff_limit": {
                        "type": "integer",
                        "minimum": 0,
                        "default": 0,
                        "description": "Number of retry attempts for failed jobs",
                    },
                    "shutdown_after_job_finishes": {
                        "type": "boolean",
                        "description": "Whether to shutdown the Ray cluster after the job finishes. If not specified, automatically determined: true for new clusters (ephemeral), false for existing clusters (persistent).",
                    },
                },
            },
            "image": {
                "type": "string",
                "description": "Container image for the job (Kubernetes only, defaults to rayproject/ray:2.47.0)",
            },
            "resources": {
                "type": "object",
                "description": "Resource requests and limits for Kubernetes job pods. Only used for Kubernetes jobs",
                "properties": {
                    "requests": {
                        "type": "object",
                        "properties": {
                            "cpu": {
                                "type": "string",
                                "description": "CPU request (e.g., '1000m', '2')",
                            },
                            "memory": {
                                "type": "string",
                                "description": "Memory request (e.g., '2Gi', '1024Mi')",
                            },
                            "nvidia.com/gpu": {
                                "type": "string",
                                "description": "GPU request (e.g., '1', '2')",
                            },
                        },
                    },
                    "limits": {
                        "type": "object",
                        "properties": {
                            "cpu": {
                                "type": "string",
                                "description": "CPU limit (e.g., '2000m', '4')",
                            },
                            "memory": {
                                "type": "string",
                                "description": "Memory limit (e.g., '4Gi', '2048Mi')",
                            },
                            "nvidia.com/gpu": {
                                "type": "string",
                                "description": "GPU limit (e.g., '1', '2')",
                            },
                        },
                    },
                },
            },
            "tolerations": {
                "type": "array",
                "description": "Tolerations for job pod scheduling (Kubernetes only)",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "operator": {"type": "string"},
                        "value": {"type": "string"},
                        "effect": {"type": "string"},
                        "tolerationSeconds": {"type": "integer"},
                    },
                },
            },
            "node_selector": {
                "type": "object",
                "description": "Node selector for job pod scheduling (Kubernetes only)",
            },
            "service_account": {
                "type": "string",
                "description": "Kubernetes service account for job pods (Kubernetes only)",
            },
            "environment": {
                "type": "object",
                "description": "Environment variables for the job",
                "additionalProperties": {"type": "string"},
            },
            "working_dir": {
                "type": "string",
                "description": "Working directory for the job",
            },
        },
        "required": ["entrypoint"],
    }


def get_list_ray_jobs_schema() -> Dict[str, Any]:
    """Schema for list_ray_jobs tool."""
    return {
        "type": "object",
        "properties": {
            "job_type": {
                "type": "string",
                "enum": ["local", "kubernetes", "k8s", "auto", "all"],
                "default": "auto",
                "description": "Type of jobs to list. 'local' for local Ray clusters, 'kubernetes'/'k8s' for KubeRay jobs, 'auto' for automatic detection based on cluster state, 'all' for all job types",
            },
            "namespace": {
                "type": "string",
                "default": "default",
                "description": "Kubernetes namespace (only used for KubeRay jobs)",
            },
        },
    }


def get_inspect_ray_job_schema() -> Dict[str, Any]:
    """Schema for inspect_ray_job tool."""
    return {
        "type": "object",
        "properties": {
            "job_id": {
                "type": "string",
                "description": "ID or name of the job to inspect",
            },
            "job_type": {
                "type": "string",
                "enum": ["local", "kubernetes", "k8s", "auto"],
                "default": "auto",
                "description": "Type of job: 'local' for local Ray clusters, 'kubernetes'/'k8s' for KubeRay jobs, 'auto' for automatic detection",
            },
            "namespace": {
                "type": "string",
                "default": "default",
                "description": "Kubernetes namespace (only used for KubeRay jobs)",
            },
            "mode": {
                "type": "string",
                "enum": ["status", "full"],
                "default": "status",
                "description": "Inspection mode: 'status' for basic status, 'full' for detailed information",
            },
        },
        "required": ["job_id"],
    }


def get_cancel_ray_job_schema() -> Dict[str, Any]:
    """Schema for cancel_ray_job tool."""
    return {
        "type": "object",
        "properties": {
            "job_id": {
                "type": "string",
                "description": "ID or name of the job to cancel",
            },
            "job_type": {
                "type": "string",
                "enum": ["local", "kubernetes", "k8s", "auto"],
                "default": "auto",
                "description": "Type of job: 'local' for local Ray clusters, 'kubernetes'/'k8s' for KubeRay jobs, 'auto' for automatic detection",
            },
            "namespace": {
                "type": "string",
                "default": "default",
                "description": "Kubernetes namespace (only used for KubeRay jobs)",
            },
        },
        "required": ["job_id"],
    }
