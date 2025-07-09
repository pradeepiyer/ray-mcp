"""Tool registry for Ray MCP server.

This module centralizes all tool definitions, schemas, and implementations to eliminate
duplication and provide a single source of truth for tool metadata.
"""

import asyncio
import inspect
import json
import logging
import os
import shutil
from typing import Any, Callable, Dict, List, Optional, Tuple

from mcp.types import Tool

from .core.managers.unified_manager import RayUnifiedManager

logger = logging.getLogger(__name__)
from .core.foundation.logging_utils import ResponseFormatter


class ToolRegistry:
    """Registry for all Ray MCP tools with centralized metadata and implementations."""

    def __init__(self, ray_manager: RayUnifiedManager):
        self.ray_manager = ray_manager
        self._tools: Dict[str, Dict[str, Any]] = {}
        self.response_formatter = ResponseFormatter()
        self._register_all_tools()

    def _register_all_tools(self) -> None:
        """Register all available tools with their schemas and implementations."""

        # Basic cluster management
        self._register_tool(
            name="init_ray_cluster",
            description="Initialize Ray cluster - start a new local cluster, connect to existing cluster, or create a Kubernetes cluster via KubeRay. Supports both local Ray clusters and Kubernetes-based clusters using KubeRay operator. If address is provided, connects to existing cluster; otherwise creates new cluster based on cluster_type. IMPORTANT: For head-node-only clusters (no worker nodes), explicitly pass worker_nodes=[] (empty array). For default behavior (2 workers), omit worker_nodes parameter.",
            schema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Ray cluster address to connect to (e.g., '127.0.0.1:10001'). If provided, connects to existing cluster via dashboard API; if not provided, creates new cluster based on cluster_type. IMPORTANT: When connecting to a Ray cluster running on GKE/Kubernetes, you MUST specify cluster_type='kubernetes' to ensure proper coordination with the GKE connection. Connection uses dashboard API (port 8265) for all cluster operations.",
                    },
                    "cluster_type": {
                        "type": "string",
                        "enum": ["local", "kubernetes", "k8s"],
                        "default": "local",
                        "description": "Type of cluster to create or connect to. 'local' for local Ray clusters, 'kubernetes'/'k8s' for KubeRay clusters on Kubernetes. REQUIRED when connecting to existing Ray clusters on GKE/Kubernetes via address parameter.",
                    },
                    "kubernetes_config": {
                        "type": "object",
                        "description": "Kubernetes-specific configuration for KubeRay clusters. Only used when cluster_type is 'kubernetes' or 'k8s'.",
                        "properties": {
                            "namespace": {
                                "type": "string",
                                "default": "default",
                                "description": "Kubernetes namespace to deploy the Ray cluster in",
                            },
                            "cluster_name": {
                                "type": "string",
                                "description": "Name for the Ray cluster (auto-generated if not provided)",
                            },
                            "image": {
                                "type": "string",
                                "description": "Container image for Ray pods (defaults to ray:2.47.0)",
                            },
                            "service_account": {
                                "type": "string",
                                "description": "Kubernetes service account for Ray pods",
                            },
                            "node_selector": {
                                "type": "object",
                                "description": "Node selector for pod scheduling",
                            },
                            "tolerations": {
                                "type": "array",
                                "description": "Tolerations for pod scheduling",
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
                            "service_type": {
                                "type": "string",
                                "enum": ["ClusterIP", "NodePort", "LoadBalancer"],
                                "default": "LoadBalancer",
                                "description": "Kubernetes service type for Ray head service. 'LoadBalancer' exposes dashboard externally (recommended for cloud), 'NodePort' exposes on node ports, 'ClusterIP' is cluster-internal only",
                            },
                            "service_annotations": {
                                "type": "object",
                                "description": "Custom service annotations for cloud provider configuration (e.g., load balancer settings)",
                                "additionalProperties": {"type": "string"},
                            },
                            "enable_ingress": {
                                "type": "boolean",
                                "default": False,
                                "description": "Whether to enable ingress for Ray dashboard",
                            },
                            "auto_scale": {
                                "type": "boolean",
                                "default": False,
                                "description": "Whether to enable autoscaling for worker nodes",
                            },
                            "min_replicas": {
                                "type": "integer",
                                "minimum": 0,
                                "default": 1,
                                "description": "Minimum number of worker replicas when autoscaling is enabled",
                            },
                            "max_replicas": {
                                "type": "integer",
                                "minimum": 1,
                                "default": 10,
                                "description": "Maximum number of worker replicas when autoscaling is enabled",
                            },
                        },
                    },
                    "num_cpus": {
                        "type": "integer",
                        "minimum": 1,
                        "default": 1,
                        "description": "Number of CPUs for head node (local clusters) or head node pod (Kubernetes clusters)",
                    },
                    "num_gpus": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Number of GPUs for head node (local clusters) or head node pod (Kubernetes clusters)",
                    },
                    "object_store_memory": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Object store memory in bytes for head node (local clusters) or head node pod (Kubernetes clusters)",
                    },
                    "resources": {
                        "type": "object",
                        "description": "Resource requests and limits for Kubernetes pods. Only used when cluster_type is 'kubernetes' or 'k8s'.",
                        "properties": {
                            "head_node": {
                                "type": "object",
                                "description": "Resources for head node pod",
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
                            "worker_nodes": {
                                "type": "object",
                                "description": "Resources for worker node pods",
                                "properties": {
                                    "requests": {
                                        "type": "object",
                                        "properties": {
                                            "cpu": {
                                                "type": "string",
                                                "description": "CPU request (e.g., '500m', '1')",
                                            },
                                            "memory": {
                                                "type": "string",
                                                "description": "Memory request (e.g., '1Gi', '512Mi')",
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
                                                "description": "CPU limit (e.g., '1000m', '2')",
                                            },
                                            "memory": {
                                                "type": "string",
                                                "description": "Memory limit (e.g., '2Gi', '1024Mi')",
                                            },
                                            "nvidia.com/gpu": {
                                                "type": "string",
                                                "description": "GPU limit (e.g., '1', '2')",
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                    "worker_nodes": {
                        "type": "array",
                        "description": "Worker node configuration. CRITICAL: Pass empty array [] for head-node-only clusters (when user says 'only head node' or 'no worker nodes'). Omit this parameter for default behavior (2 workers). Pass array with worker configs for custom workers.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "num_cpus": {
                                    "type": "integer",
                                    "minimum": 1,
                                    "description": "Number of CPUs for this worker node",
                                },
                                "num_gpus": {
                                    "type": "integer",
                                    "minimum": 0,
                                    "description": "Number of GPUs for this worker node",
                                },
                                "object_store_memory": {
                                    "type": "integer",
                                    "minimum": 0,
                                    "description": "Object store memory in bytes for this worker node",
                                },
                                "resources": {
                                    "type": "object",
                                    "description": "Additional custom resources for this worker node",
                                },
                                "node_name": {
                                    "type": "string",
                                    "description": "Optional name for this worker node",
                                },
                                "image": {
                                    "type": "string",
                                    "description": "Container image for this worker node (Kubernetes only)",
                                },
                                "node_selector": {
                                    "type": "object",
                                    "description": "Node selector for this worker node (Kubernetes only)",
                                },
                                "tolerations": {
                                    "type": "array",
                                    "description": "Tolerations for this worker node (Kubernetes only)",
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
                            },
                            "required": ["num_cpus"],
                        },
                    },
                    "head_node_port": {
                        "type": ["integer", "null"],
                        "minimum": 10000,
                        "maximum": 65535,
                        "description": "Port for head node (only used for local clusters, if None, a free port will be found)",
                    },
                    "dashboard_port": {
                        "type": ["integer", "null"],
                        "minimum": 1000,
                        "maximum": 65535,
                        "description": "Port for Ray dashboard (only used for local clusters, if None, a free port will be found)",
                    },
                    "head_node_host": {
                        "type": "string",
                        "default": "127.0.0.1",
                        "description": "Host address for head node (only used for local clusters)",
                    },
                },
            },
            handler=self._init_ray_cluster_handler,
        )

        self._register_tool(
            name="stop_ray_cluster",
            description="Stop or delete a Ray cluster. Supports both local Ray clusters (stop) and KubeRay clusters (delete). For KubeRay clusters, provide cluster_name and namespace.",
            schema={
                "type": "object",
                "properties": {
                    "cluster_name": {
                        "type": "string",
                        "description": "Name of the Ray cluster to stop/delete (required for KubeRay clusters, ignored for local clusters)",
                    },
                    "cluster_type": {
                        "type": "string",
                        "enum": ["local", "kubernetes", "k8s", "auto"],
                        "default": "auto",
                        "description": "Type of cluster: 'local' for local Ray clusters, 'kubernetes'/'k8s' for KubeRay clusters, 'auto' for automatic detection",
                    },
                    "namespace": {
                        "type": "string",
                        "default": "default",
                        "description": "Kubernetes namespace (only used for KubeRay clusters)",
                    },
                },
            },
            handler=self._stop_ray_cluster_handler,
        )

        self._register_tool(
            name="inspect_ray_cluster",
            description="Get comprehensive cluster information including status, resources, and nodes. Supports both local Ray clusters and KubeRay clusters. For KubeRay clusters, provide cluster_name and namespace.",
            schema={
                "type": "object",
                "properties": {
                    "cluster_name": {
                        "type": "string",
                        "description": "Name of the Ray cluster to inspect (required for KubeRay clusters, ignored for local clusters)",
                    },
                    "cluster_type": {
                        "type": "string",
                        "enum": ["local", "kubernetes", "k8s", "auto"],
                        "default": "auto",
                        "description": "Type of cluster: 'local' for local Ray clusters, 'kubernetes'/'k8s' for KubeRay clusters, 'auto' for automatic detection",
                    },
                    "namespace": {
                        "type": "string",
                        "default": "default",
                        "description": "Kubernetes namespace (only used for KubeRay clusters)",
                    },
                },
            },
            handler=self._inspect_ray_cluster_handler,
        )

        # Job management
        self._register_tool(
            name="submit_ray_job",
            description="Submit a job to the Ray cluster. Supports both local Ray clusters and Kubernetes-based clusters using KubeRay operator. Automatically detects job type based on cluster state or explicit job_type parameter. For local clusters, uses Ray job submission API. For Kubernetes clusters, creates RayJob CRD resources.",
            schema={
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
                        "description": "Container image for the job (Kubernetes only, defaults to ray:2.47.0)",
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
            },
            handler=self._submit_ray_job_handler,
        )

        self._register_tool(
            name="list_ray_jobs",
            description="List all jobs in the Ray cluster. Supports both local Ray clusters and Kubernetes-based clusters using KubeRay operator. Automatically detects job type based on cluster state or explicit job_type parameter.",
            schema={
                "type": "object",
                "properties": {
                    "job_type": {
                        "type": "string",
                        "enum": ["local", "kubernetes", "k8s", "auto", "all"],
                        "default": "auto",
                        "description": "Type of jobs to list. 'local' for local Ray jobs, 'kubernetes'/'k8s' for KubeRay jobs, 'auto' for automatic detection (will use kubernetes if GKE is connected), 'all' for both types",
                    },
                    "namespace": {
                        "type": "string",
                        "default": "default",
                        "description": "Kubernetes namespace to list jobs from (only used for Kubernetes jobs)",
                    },
                },
            },
            handler=self._list_ray_jobs_handler,
        )

        self._register_tool(
            name="inspect_ray_job",
            description="Inspect a job with different modes. Supports both local Ray jobs (using job_id) and KubeRay jobs (using job_name + namespace). Automatically detects job type based on ID format or uses explicit job_type parameter.",
            schema={
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "Job ID (for local Ray) or job name (for KubeRay) to inspect",
                    },
                    "job_type": {
                        "type": "string",
                        "enum": ["local", "kubernetes", "k8s", "auto"],
                        "default": "auto",
                        "description": "Type of job: 'local' for local Ray jobs, 'kubernetes'/'k8s' for KubeRay jobs, 'auto' for automatic detection based on job_id format",
                    },
                    "namespace": {
                        "type": "string",
                        "default": "default",
                        "description": "Kubernetes namespace (only used for KubeRay jobs)",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["status", "logs", "debug"],
                        "default": "status",
                        "description": "Inspection mode: 'status' for basic job info, 'logs' to include job logs, 'debug' for comprehensive debugging information",
                    },
                },
                "required": ["job_id"],
            },
            handler=self._inspect_ray_job_handler,
        )

        self._register_tool(
            name="cancel_ray_job",
            description="Cancel or delete a running job. Supports both local Ray jobs (cancel) and KubeRay jobs (delete). Automatically detects job type based on ID format or uses explicit job_type parameter.",
            schema={
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "Job ID (for local Ray) or job name (for KubeRay) to cancel/delete",
                    },
                    "job_type": {
                        "type": "string",
                        "enum": ["local", "kubernetes", "k8s", "auto"],
                        "default": "auto",
                        "description": "Type of job: 'local' for local Ray jobs, 'kubernetes'/'k8s' for KubeRay jobs, 'auto' for automatic detection based on job_id format",
                    },
                    "namespace": {
                        "type": "string",
                        "default": "default",
                        "description": "Kubernetes namespace (only used for KubeRay jobs)",
                    },
                },
                "required": ["job_id"],
            },
            handler=self._cancel_ray_job_handler,
        )

        self._register_tool(
            name="retrieve_logs",
            description="Retrieve job logs from Ray cluster. Supports both local Ray jobs and KubeRay jobs. Automatically detects job type based on ID format or uses explicit job_type parameter. For local jobs, supports pagination and error analysis.",
            schema={
                "type": "object",
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "Job ID (for local Ray) or job name (for KubeRay) to get logs for",
                    },
                    "job_type": {
                        "type": "string",
                        "enum": ["local", "kubernetes", "k8s", "auto"],
                        "default": "auto",
                        "description": "Type of job: 'local' for local Ray jobs, 'kubernetes'/'k8s' for KubeRay jobs, 'auto' for automatic detection based on identifier format",
                    },
                    "namespace": {
                        "type": "string",
                        "default": "default",
                        "description": "Kubernetes namespace (only used for KubeRay jobs)",
                    },
                    "log_type": {
                        "type": "string",
                        "enum": ["job"],
                        "default": "job",
                        "description": "Type of logs to retrieve - only 'job' logs are supported",
                    },
                    "num_lines": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10000,
                        "default": 100,
                        "description": "Number of log lines to retrieve (0 for all lines, max 10000). Ignored if page is specified. Only supported for local Ray jobs.",
                    },
                    "include_errors": {
                        "type": "boolean",
                        "default": False,
                        "description": "Whether to include error analysis for job logs (only supported for local Ray jobs)",
                    },
                    "max_size_mb": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 10,
                        "description": "Maximum size of logs in MB (1-100, default 10) to prevent memory exhaustion (only supported for local Ray jobs)",
                    },
                    "page": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Page number (1-based) for paginated log retrieval. If specified, enables pagination mode (only supported for local Ray jobs)",
                    },
                    "page_size": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 1000,
                        "default": 100,
                        "description": "Number of lines per page (1-1000). Only used when page is specified (only supported for local Ray jobs)",
                    },
                },
                "required": ["identifier"],
            },
            handler=self._retrieve_logs_handler,
        )

        # Ray cluster listing (unified for local and KubeRay)
        self._register_tool(
            name="list_ray_clusters",
            description="List Ray clusters. Supports both local Ray clusters and KubeRay clusters. For local clusters, returns information about the current Ray cluster if running. For KubeRay clusters, lists all clusters in the specified namespace.",
            schema={
                "type": "object",
                "properties": {
                    "cluster_type": {
                        "type": "string",
                        "enum": ["local", "kubernetes", "k8s", "auto"],
                        "default": "auto",
                        "description": "Type of clusters to list: 'local' for local Ray clusters, 'kubernetes'/'k8s' for KubeRay clusters, 'auto' for automatic detection based on cluster state",
                    },
                    "namespace": {
                        "type": "string",
                        "default": "default",
                        "description": "Kubernetes namespace to list clusters from (only used for KubeRay clusters)",
                    },
                },
            },
            handler=self._list_ray_clusters_handler,
        )

        self._register_tool(
            name="scale_ray_cluster",
            description="Scale a Ray cluster by adjusting worker replicas. For KubeRay clusters, adjusts worker replicas. For local Ray clusters, returns information about scaling limitations.",
            schema={
                "type": "object",
                "properties": {
                    "cluster_name": {
                        "type": "string",
                        "description": "Name of the Ray cluster to scale (required for KubeRay clusters, ignored for local clusters)",
                    },
                    "worker_replicas": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Number of worker replicas to scale to (only supported for KubeRay clusters)",
                    },
                    "cluster_type": {
                        "type": "string",
                        "enum": ["local", "kubernetes", "k8s", "auto"],
                        "default": "auto",
                        "description": "Type of Ray cluster: 'local' for local Ray clusters, 'kubernetes'/'k8s' for KubeRay clusters, 'auto' for auto-detection",
                    },
                    "namespace": {
                        "type": "string",
                        "default": "default",
                        "description": "Kubernetes namespace of the cluster (only applies to KubeRay clusters)",
                    },
                },
                "required": ["worker_replicas"],
            },
            handler=self._scale_ray_cluster_handler,
        )

        # Cloud Provider Management Tools
        self._register_tool(
            name="detect_cloud_provider",
            description="Detect available cloud providers and authentication methods. Identifies if you're running in GKE or local environment and shows available authentication options.",
            schema={"type": "object", "properties": {}},
            handler=self._detect_cloud_provider_handler,
        )

        self._register_tool(
            name="check_environment",
            description="Check environment setup, dependencies, and authentication status for cloud providers",
            schema={
                "type": "object",
                "properties": {
                    "provider": {
                        "type": "string",
                        "enum": ["gke", "all"],
                        "description": "Cloud provider to check (optional, defaults to all)",
                    }
                },
                "required": [],
            },
            handler=self._check_environment_handler,
        )

        self._register_tool(
            name="authenticate_cloud_provider",
            description="Authenticate with a cloud provider (GKE). For GKE, provide service account path and project ID.",
            schema={
                "type": "object",
                "properties": {
                    "provider": {
                        "type": "string",
                        "enum": ["gke", "local"],
                        "description": "Cloud provider to authenticate with",
                    },
                    "service_account_path": {
                        "type": "string",
                        "description": "Path to GKE service account JSON file (GKE only)",
                    },
                    "project_id": {
                        "type": "string",
                        "description": "Google Cloud project ID (GKE only)",
                    },
                    "zone": {
                        "type": "string",
                        "description": "GCP zone (GKE only)",
                    },
                    "config_file": {
                        "type": "string",
                        "description": "Kubeconfig file path (local only)",
                    },
                    "context": {
                        "type": "string",
                        "description": "Kubernetes context name (local only)",
                    },
                },
                "required": ["provider"],
            },
            handler=self._authenticate_cloud_provider_handler,
        )

        self._register_tool(
            name="list_cloud_clusters",
            description="List clusters for a specific cloud provider. Discovers available clusters in GKE projects or local Kubernetes contexts.",
            schema={
                "type": "object",
                "properties": {
                    "provider": {
                        "type": "string",
                        "enum": ["gke", "local"],
                        "description": "Cloud provider to list clusters for",
                    },
                    "project_id": {
                        "type": "string",
                        "description": "Google Cloud project ID (GKE only)",
                    },
                    "zone": {
                        "type": "string",
                        "description": "GKE zone to list clusters in (optional, lists all if not specified)",
                    },
                },
                "required": ["provider"],
            },
            handler=self._list_cloud_clusters_handler,
        )

        self._register_tool(
            name="connect_cloud_cluster",
            description="Connect to a cloud cluster. Configures kubeconfig and tests connection to the specified cluster.",
            schema={
                "type": "object",
                "properties": {
                    "provider": {
                        "type": "string",
                        "enum": ["gke", "local"],
                        "description": "Cloud provider of the cluster",
                    },
                    "cluster_name": {
                        "type": "string",
                        "description": "Name of the cluster to connect to",
                    },
                    "project_id": {
                        "type": "string",
                        "description": "Google Cloud project ID (GKE only)",
                    },
                    "zone": {"type": "string", "description": "GKE zone (GKE only)"},
                    "config_file": {
                        "type": "string",
                        "description": "Kubeconfig file path (local only)",
                    },
                },
                "required": ["provider", "cluster_name"],
            },
            handler=self._connect_cloud_cluster_handler,
        )

        self._register_tool(
            name="create_cloud_cluster",
            description="Create a new cloud cluster. Supports creating GKE clusters with customizable specifications including node types, scaling, and networking.",
            schema={
                "type": "object",
                "properties": {
                    "provider": {
                        "type": "string",
                        "enum": ["gke"],
                        "description": "Cloud provider to create cluster in",
                    },
                    "cluster_spec": {
                        "type": "object",
                        "description": "Cluster specification including name, node configuration, networking, etc.",
                        "properties": {
                            "name": {"type": "string", "description": "Cluster name"},
                            "zone": {
                                "type": "string",
                                "description": "GKE zone (GKE only)",
                            },
                            "machine_type": {
                                "type": "string",
                                "description": "Node machine type (GKE: n1-standard-2)",
                            },
                            "disk_size": {
                                "type": "integer",
                                "description": "Node disk size in GB",
                            },
                            "initial_node_count": {
                                "type": "integer",
                                "description": "Initial number of nodes",
                            },
                            "version": {
                                "type": "string",
                                "description": "Kubernetes version",
                            },
                        },
                        "required": ["name"],
                    },
                    "project_id": {
                        "type": "string",
                        "description": "Google Cloud project ID (GKE only)",
                    },
                },
                "required": ["provider", "cluster_spec"],
            },
            handler=self._create_cloud_cluster_handler,
        )

        self._register_tool(
            name="get_cloud_cluster_info",
            description="Get detailed information about a cloud cluster including status, node pools, networking, and configuration.",
            schema={
                "type": "object",
                "properties": {
                    "provider": {
                        "type": "string",
                        "enum": ["gke", "local"],
                        "description": "Cloud provider of the cluster",
                    },
                    "cluster_name": {
                        "type": "string",
                        "description": "Name of the cluster",
                    },
                    "project_id": {
                        "type": "string",
                        "description": "Google Cloud project ID (GKE only)",
                    },
                    "zone": {"type": "string", "description": "GKE zone (GKE only)"},
                },
                "required": ["provider", "cluster_name"],
            },
            handler=self._get_cloud_cluster_info_handler,
        )

        self._register_tool(
            name="get_cloud_provider_status",
            description="Get authentication and connection status for a cloud provider.",
            schema={
                "type": "object",
                "properties": {
                    "provider": {
                        "type": "string",
                        "enum": ["gke", "local"],
                        "description": "Cloud provider to check status for",
                    }
                },
                "required": ["provider"],
            },
            handler=self._get_cloud_provider_status_handler,
        )

        self._register_tool(
            name="disconnect_cloud_provider",
            description="Disconnect from a cloud provider and reset connection state.",
            schema={
                "type": "object",
                "properties": {
                    "provider": {
                        "type": "string",
                        "enum": ["gke", "local"],
                        "description": "Cloud provider to disconnect from",
                    }
                },
                "required": ["provider"],
            },
            handler=self._disconnect_cloud_provider_handler,
        )

        self._register_tool(
            name="get_cloud_config_template",
            description="Get cluster configuration template for a cloud provider. Returns YAML/JSON templates for creating clusters with different configurations (basic, production, GPU).",
            schema={
                "type": "object",
                "properties": {
                    "provider": {
                        "type": "string",
                        "enum": ["gke"],
                        "description": "Cloud provider to get template for",
                    },
                    "template_type": {
                        "type": "string",
                        "enum": ["basic", "production", "gpu"],
                        "default": "basic",
                        "description": "Type of cluster template",
                    },
                },
                "required": ["provider"],
            },
            handler=self._get_cloud_config_template_handler,
        )

    def _register_tool(
        self, name: str, description: str, schema: Dict[str, Any], handler: Callable
    ) -> None:
        """Register a tool with its metadata and handler."""
        self._tools[name] = {
            "description": description,
            "schema": schema,
            "handler": handler,
        }

    def get_tool_list(self) -> List[Tool]:
        """Get the list of all registered tools for MCP server."""
        tools = []
        for name, tool_info in self._tools.items():
            tools.append(
                Tool(
                    name=name,
                    description=tool_info["description"],
                    inputSchema=tool_info["schema"],
                )
            )
        return tools

    def get_tool_handler(self, name: str) -> Optional[Callable]:
        """Get the handler function for a specific tool."""
        tool_info = self._tools.get(name)
        return tool_info["handler"] if tool_info else None

    def list_tool_names(self) -> List[str]:
        """Get a list of all registered tool names."""
        return list(self._tools.keys())

    # Tool handlers - these replace the duplicated logic in main.py and tools.py

    async def _init_ray_cluster_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for init_ray_cluster tool with support for both local and Kubernetes clusters."""
        # Determine cluster type first
        cluster_type = kwargs.get("cluster_type", "local").lower()

        # If address is provided, handle based on cluster type
        if kwargs.get("address"):
            if cluster_type in ["kubernetes", "k8s"]:
                # For Kubernetes address-based connections, ensure proper coordination
                try:
                    # Ensure GKE coordination is in place if we have a GKE connection
                    await self.ray_manager._ensure_kuberay_gke_coordination()
                except Exception as coord_error:
                    # Log coordination error but don't fail the connection
                    from ray_mcp.core.foundation.logging_utils import LoggingUtility

                    LoggingUtility.log_warning(
                        "init_ray_gke_coordination",
                        f"Failed to coordinate GKE for Ray connection: {coord_error}",
                    )

                try:
                    # Connect to existing Ray cluster running on Kubernetes
                    return await self.ray_manager.init_cluster(**kwargs)
                except Exception as e:
                    return ResponseFormatter.format_error_response(
                        "connect to kubernetes ray cluster", e
                    )
            else:
                # Local address-based connection
                local_kwargs = {
                    k: v
                    for k, v in kwargs.items()
                    if k not in ["cluster_type", "kubernetes_config"]
                }
                return await self.ray_manager.init_cluster(**local_kwargs)

        # For local clusters, use existing init_cluster method
        if cluster_type == "local":
            # Remove cluster_type and kubernetes_config from kwargs for local clusters
            local_kwargs = {
                k: v
                for k, v in kwargs.items()
                if k not in ["cluster_type", "kubernetes_config"]
            }
            return await self.ray_manager.init_cluster(**local_kwargs)

        # For Kubernetes clusters, create KubeRay cluster
        elif cluster_type in ["kubernetes", "k8s"]:
            return await self._create_kuberay_cluster(**kwargs)

        else:
            return ResponseFormatter.format_validation_error(
                f"Invalid cluster_type: {cluster_type}. Must be 'local', 'kubernetes', or 'k8s'"
            )

    async def _create_kuberay_cluster(self, **kwargs) -> Dict[str, Any]:
        """Create a KubeRay cluster from init_ray parameters."""
        try:
            # Ensure GKE coordination is in place if we have a GKE connection
            await self._ensure_gke_coordination()

            # Extract Kubernetes configuration
            kubernetes_config = kwargs.get("kubernetes_config", {})
            namespace = kubernetes_config.get("namespace", "default")
            cluster_name = kubernetes_config.get("cluster_name")

            # Build cluster specification from parameters
            cluster_spec = await self._build_kuberay_cluster_spec(**kwargs)

            # Create the cluster
            result = await self.ray_manager.create_kuberay_cluster(
                cluster_spec=cluster_spec, namespace=namespace
            )

            return result
        except Exception as e:
            return ResponseFormatter.format_error_response("create kuberay cluster", e)

    async def _build_kuberay_cluster_spec(self, **kwargs) -> Dict[str, Any]:
        """Build KubeRay cluster specification from init_ray parameters."""
        kubernetes_config = kwargs.get("kubernetes_config", {})
        resources = kwargs.get("resources", {})
        worker_nodes = kwargs.get("worker_nodes")

        # Basic cluster configuration
        cluster_spec = {
            "cluster_name": kubernetes_config.get("cluster_name"),
            "namespace": kubernetes_config.get("namespace", "default"),
            "ray_version": kubernetes_config.get("ray_version", "2.47.0"),
            "enable_ingress": kubernetes_config.get("enable_ingress", False),
        }

        # Head node configuration
        default_image = kubernetes_config.get("image", "rayproject/ray:2.47.0")
        head_node_config = {
            "image": default_image,
            "num_cpus": 2,  # Default CPU count for head node
            "service_type": kubernetes_config.get(
                "service_type", "LoadBalancer"
            ),  # Default to LoadBalancer for external access
        }

        # Add service annotations if provided
        if kubernetes_config.get("service_annotations"):
            head_node_config["service_annotations"] = kubernetes_config[
                "service_annotations"
            ]

        # Add CPU/GPU/memory from direct parameters
        if kwargs.get("num_cpus"):
            head_node_config["num_cpus"] = kwargs["num_cpus"]
        if kwargs.get("num_gpus"):
            head_node_config["num_gpus"] = kwargs["num_gpus"]
        if kwargs.get("object_store_memory"):
            head_node_config["object_store_memory"] = kwargs["object_store_memory"]

        # Add Kubernetes resources for head node
        if resources.get("head_node"):
            head_node_config["resources"] = resources["head_node"]

        # Add scheduling constraints
        if kubernetes_config.get("node_selector"):
            head_node_config["node_selector"] = kubernetes_config["node_selector"]
        if kubernetes_config.get("tolerations"):
            head_node_config["tolerations"] = kubernetes_config["tolerations"]

        # Add service account
        if kubernetes_config.get("service_account"):
            head_node_config["service_account"] = kubernetes_config["service_account"]

        cluster_spec["head_node_spec"] = head_node_config

        # Worker nodes configuration
        worker_node_specs = []

        # Handle worker_nodes parameter
        if worker_nodes is not None:
            if len(worker_nodes) == 0:
                # Head-only cluster
                pass
            else:
                # Custom worker configuration
                for i, worker_config in enumerate(worker_nodes):
                    worker_spec = {
                        "group_name": worker_config.get(
                            "node_name", f"worker-group-{i}"
                        ),
                        "replicas": 1,
                        "image": worker_config.get("image", default_image),
                        "num_cpus": worker_config.get("num_cpus", 2),
                    }

                    # Add Ray parameters
                    if worker_config.get("num_gpus"):
                        worker_spec["num_gpus"] = worker_config["num_gpus"]
                    if worker_config.get("object_store_memory"):
                        worker_spec["object_store_memory"] = worker_config[
                            "object_store_memory"
                        ]

                    # Add Kubernetes-specific parameters
                    if worker_config.get("node_selector"):
                        worker_spec["node_selector"] = worker_config["node_selector"]
                    if worker_config.get("tolerations"):
                        worker_spec["tolerations"] = worker_config["tolerations"]

                    worker_node_specs.append(worker_spec)
        else:
            # Default: create 2 worker groups
            default_worker_spec = {
                "group_name": "worker-group",
                "replicas": 2,
                "image": default_image,
                "num_cpus": 2,
            }

            # Add default worker resources
            if resources.get("worker_nodes"):
                default_worker_spec["resources"] = resources["worker_nodes"]

            worker_node_specs.append(default_worker_spec)

        cluster_spec["worker_node_specs"] = worker_node_specs

        return cluster_spec

    async def _stop_ray_cluster_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for unified stop_ray_cluster tool supporting both local and KubeRay clusters."""
        cluster_name = kwargs.get("cluster_name")
        cluster_type = await self._detect_cluster_type_from_name(
            cluster_name, kwargs.get("cluster_type", "auto")
        )
        namespace = kwargs.get("namespace", "default")

        if cluster_type == "local":
            return await self.ray_manager.stop_cluster()
        elif cluster_type in ["kubernetes", "k8s"]:
            if not cluster_name:
                return ResponseFormatter.format_validation_error(
                    "cluster_name is required for KubeRay cluster deletion"
                )
            await self._ensure_gke_coordination()
            return await self.ray_manager.delete_kuberay_cluster(
                cluster_name, namespace
            )
        else:
            return ResponseFormatter.format_validation_error(
                f"Invalid cluster_type: {cluster_type}. Must be 'local', 'kubernetes', 'k8s', or 'auto'"
            )

    async def _inspect_ray_cluster_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for unified inspect_ray_cluster tool supporting both local and KubeRay clusters."""
        cluster_name = kwargs.get("cluster_name")
        cluster_type = await self._detect_cluster_type_from_name(
            cluster_name, kwargs.get("cluster_type", "auto")
        )
        namespace = kwargs.get("namespace", "default")

        if cluster_type == "local":
            return await self.ray_manager.inspect_ray_cluster()
        elif cluster_type in ["kubernetes", "k8s"]:
            if not cluster_name:
                return ResponseFormatter.format_validation_error(
                    "cluster_name is required for KubeRay cluster inspection"
                )
            await self._ensure_gke_coordination()
            return await self.ray_manager.get_kuberay_cluster(cluster_name, namespace)
        else:
            return ResponseFormatter.format_validation_error(
                f"Invalid cluster_type: {cluster_type}. Must be 'local', 'kubernetes', 'k8s', or 'auto'"
            )

    async def _submit_ray_job_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for submit_ray_job tool with support for both local and Kubernetes jobs."""
        # Determine job type
        job_type = kwargs.get("job_type", "auto").lower()

        if job_type == "auto":
            # Auto-detect based on cluster state
            job_type = await self._detect_job_type()

            # For local jobs, use existing submit_ray_job method
        if job_type == "local":
            # Remove job_type and kubernetes_config from kwargs for local jobs
            local_kwargs = {
                k: v
                for k, v in kwargs.items()
                if k
                not in [
                    "job_type",
                    "kubernetes_config",
                    "image",
                    "tolerations",
                    "node_selector",
                    "service_account",
                    "environment",
                    "working_dir",
                ]
            }
            # Filter to only include valid parameters for local job submission
            sig = inspect.signature(self.ray_manager.submit_ray_job)
            valid_params = {k for k in sig.parameters.keys() if k != "self"}
            filtered = {k: v for k, v in local_kwargs.items() if k in valid_params}
            return await self.ray_manager.submit_ray_job(**filtered)

        # For Kubernetes jobs, create KubeRay job
        elif job_type in ["kubernetes", "k8s"]:
            # Ensure GKE coordination is in place if we have a GKE connection
            await self._ensure_gke_coordination()
            return await self._create_kuberay_job(**kwargs)

        else:
            return ResponseFormatter.format_validation_error(
                f"Invalid job_type: {job_type}. Must be 'local', 'kubernetes', 'k8s', or 'auto'"
            )

    async def _detect_job_type(self) -> str:
        """Detect job type based on cluster state."""
        try:
            # Check if we have an active GKE connection
            state = self.ray_manager.state_manager.get_state()
            gke_connection = state.get("cloud_provider_connections", {}).get("gke", {})
            if gke_connection.get("connected", False):
                return "kubernetes"

            # Check if we have general Kubernetes connection
            if state.get("kubernetes_connected", False):
                return "kubernetes"

            # Check if we have KubeRay clusters
            if (
                hasattr(self.ray_manager, "kuberay_clusters")
                and self.ray_manager.kuberay_clusters
            ):
                return "kubernetes"

            # Check legacy property for backwards compatibility
            if (
                hasattr(self.ray_manager, "is_kubernetes_connected")
                and self.ray_manager.is_kubernetes_connected
            ):
                return "kubernetes"

            # Check if we have local Ray cluster
            if (
                hasattr(self.ray_manager, "is_initialized")
                and self.ray_manager.is_initialized
            ):
                return "local"

            # Default to local if no cluster is detected
            return "local"
        except Exception:
            # Fall back to local on any error
            return "local"

    async def _detect_job_type_from_id(
        self, job_id: str, explicit_job_type: str = "auto"
    ) -> str:
        """Detect job type based on job ID patterns and explicit type."""
        import re

        # If explicit type is provided and not auto, use it
        if explicit_job_type and explicit_job_type.lower() != "auto":
            return explicit_job_type.lower()

        # UUID-like format suggests local Ray job (e.g., raysubmit_abcd1234...)
        if re.match(
            r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$", job_id
        ):
            return "local"

        # Ray job submission format (raysubmit_...)
        if job_id.startswith("raysubmit_"):
            return "local"

        # Kubernetes resource name format suggests KubeRay job (lowercase alphanumeric with dashes)
        if re.match(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", job_id) and len(job_id) <= 63:
            return "kubernetes"

        # Fallback to cluster state detection
        return await self._detect_job_type()

    async def _detect_cluster_type_from_name(
        self, cluster_name: Optional[str] = None, explicit_cluster_type: str = "auto"
    ) -> str:
        """Detect cluster type based on cluster name and explicit type."""
        import re

        # If explicit type is provided and not auto, use it
        if explicit_cluster_type and explicit_cluster_type.lower() != "auto":
            return explicit_cluster_type.lower()

        # If no cluster name provided, this is likely local Ray
        if not cluster_name:
            return "local"

        # Kubernetes resource name format suggests KubeRay cluster
        if (
            re.match(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", cluster_name)
            and len(cluster_name) <= 63
        ):
            return "kubernetes"

        # Fallback to cluster state detection
        return await self._detect_job_type()

    async def _create_kuberay_job(self, **kwargs) -> Dict[str, Any]:
        """Create a KubeRay job from submit_job parameters."""
        try:
            # Ensure GKE coordination is in place if we have a GKE connection
            await self._ensure_gke_coordination()

            # Extract Kubernetes configuration
            kubernetes_config = kwargs.get("kubernetes_config", {})
            namespace = kubernetes_config.get("namespace", "default")

            # Build job specification from parameters
            job_spec = await self._build_kuberay_job_spec(**kwargs)

            # Create the job
            result = await self.ray_manager.create_kuberay_job(
                job_spec=job_spec, namespace=namespace
            )

            return result
        except Exception as e:
            return ResponseFormatter.format_error_response("create kuberay job", e)

    async def _build_kuberay_job_spec(self, **kwargs) -> Dict[str, Any]:
        """Build KubeRay job specification from submit_job parameters."""
        kubernetes_config = kwargs.get("kubernetes_config", {})

        # Basic job configuration
        job_spec = {
            "entrypoint": kwargs["entrypoint"],
            "runtime_env": kwargs.get("runtime_env"),
            "job_name": kubernetes_config.get("job_name"),
            "namespace": kubernetes_config.get("namespace", "default"),
            "cluster_selector": kubernetes_config.get("cluster_selector"),
            "suspend": kubernetes_config.get("suspend", False),
            "ttl_seconds_after_finished": kubernetes_config.get(
                "ttl_seconds_after_finished", 86400
            ),
            "active_deadline_seconds": kubernetes_config.get("active_deadline_seconds"),
            "backoff_limit": kubernetes_config.get("backoff_limit", 0),
            "shutdown_after_job_finishes": kubernetes_config.get(
                "shutdown_after_job_finishes"
            ),  # No default - let intelligent behavior work
        }

        # AUTO-DETECT EXISTING CLUSTERS: If no cluster_selector is provided,
        # discover existing KubeRay clusters and use them
        if not job_spec.get("cluster_selector"):
            try:
                from ray_mcp.core.foundation.logging_utils import LoggingUtility

                LoggingUtility.log_info(
                    "auto_cluster_discovery",
                    "No cluster_selector provided - discovering existing KubeRay clusters",
                )

                # CRITICAL FIX: Actively discover existing clusters from Kubernetes
                namespace = job_spec["namespace"]
                try:
                    cluster_list_result = await self.ray_manager.list_ray_clusters(
                        namespace=namespace
                    )

                    if cluster_list_result.get("status") == "success":
                        existing_clusters = cluster_list_result.get("clusters", [])
                        LoggingUtility.log_info(
                            "auto_cluster_discovery",
                            f"Found {len(existing_clusters)} existing clusters in namespace '{namespace}'",
                        )

                        if existing_clusters:
                            # Use the first ready cluster
                            target_cluster = None
                            for cluster in existing_clusters:
                                cluster_name = cluster.get("name")
                                cluster_phase = cluster.get("phase", "Unknown")

                                LoggingUtility.log_info(
                                    "auto_cluster_discovery",
                                    f"Evaluating cluster '{cluster_name}' - phase: {cluster_phase}",
                                )

                                # Prefer ready clusters, but accept any running cluster
                                if cluster_phase in [
                                    "ready",
                                    "running",
                                    "Running",
                                    "Ready",
                                ]:
                                    target_cluster = cluster_name
                                    break
                                elif not target_cluster and cluster_phase not in [
                                    "failed",
                                    "error",
                                    "Failed",
                                    "Error",
                                ]:
                                    # Fallback to any non-failed cluster
                                    target_cluster = cluster_name

                            if target_cluster:
                                job_spec["cluster_selector"] = target_cluster
                                LoggingUtility.log_info(
                                    "auto_cluster_discovery",
                                    f"Auto-detected existing KubeRay cluster '{target_cluster}' in namespace '{namespace}'",
                                )
                            else:
                                LoggingUtility.log_warning(
                                    "auto_cluster_discovery",
                                    f"Found {len(existing_clusters)} clusters but none are in a usable state",
                                )
                        else:
                            LoggingUtility.log_info(
                                "auto_cluster_discovery",
                                f"No existing clusters found in namespace '{namespace}' - will create new cluster",
                            )
                    else:
                        LoggingUtility.log_warning(
                            "auto_cluster_discovery",
                            f"Failed to list clusters: {cluster_list_result.get('message', 'Unknown error')}",
                        )

                except Exception as discovery_error:
                    LoggingUtility.log_warning(
                        "auto_cluster_discovery",
                        f"Cluster discovery failed: {discovery_error} - will create new cluster",
                    )

                # If no cluster found in target namespace, try 'default' namespace
                if not job_spec.get("cluster_selector") and namespace != "default":
                    try:
                        LoggingUtility.log_info(
                            "auto_cluster_discovery",
                            "No clusters in target namespace - checking 'default' namespace",
                        )

                        default_cluster_result = (
                            await self.ray_manager.list_ray_clusters(
                                namespace="default"
                            )
                        )

                        if default_cluster_result.get("status") == "success":
                            default_clusters = default_cluster_result.get(
                                "clusters", []
                            )

                            if default_clusters:
                                # Use the first cluster from default namespace
                                target_cluster = default_clusters[0].get("name")
                                if target_cluster:
                                    job_spec["cluster_selector"] = target_cluster
                                    job_spec["namespace"] = (
                                        "default"  # Update namespace to match cluster
                                    )
                                    LoggingUtility.log_info(
                                        "auto_cluster_discovery",
                                        f"Auto-detected existing cluster '{target_cluster}' in 'default' namespace - updated job namespace",
                                    )

                    except Exception as default_discovery_error:
                        LoggingUtility.log_warning(
                            "auto_cluster_discovery",
                            f"Default namespace discovery failed: {default_discovery_error}",
                        )

            except Exception as e:
                # If auto-detection fails completely, continue without cluster_selector (will create new cluster)
                from ray_mcp.core.foundation.logging_utils import LoggingUtility

                LoggingUtility.log_warning(
                    "auto_cluster_discovery",
                    f"Auto-detection failed: {e} - will create new cluster",
                )

        # Add container image
        if kwargs.get("image"):
            job_spec["image"] = kwargs["image"]

        # Add resources
        if kwargs.get("resources"):
            job_spec["resources"] = kwargs["resources"]

        # Add scheduling constraints
        if kwargs.get("tolerations"):
            job_spec["tolerations"] = kwargs["tolerations"]
        if kwargs.get("node_selector"):
            job_spec["node_selector"] = kwargs["node_selector"]

        # Add service account
        if kwargs.get("service_account"):
            job_spec["service_account"] = kwargs["service_account"]

        # Add environment variables
        if kwargs.get("environment"):
            job_spec["environment"] = kwargs["environment"]

        # Add working directory
        if kwargs.get("working_dir"):
            job_spec["working_dir"] = kwargs["working_dir"]

        # Add metadata
        if kwargs.get("metadata"):
            job_spec["metadata"] = kwargs["metadata"]

        return job_spec

    async def _ensure_gke_coordination(self) -> None:
        """Ensure GKE coordination is in place if we have a GKE connection."""
        try:
            # Check if we have an active GKE connection
            state = self.ray_manager.state_manager.get_state()
            gke_connection = state.get("cloud_provider_connections", {}).get("gke", {})

            if gke_connection.get("connected", False):
                # If we're connected to GKE but not coordinated, ensure coordination
                if not state.get("kuberay_gke_coordinated", False):
                    await self.ray_manager._ensure_kuberay_gke_coordination()
        except AttributeError as attr_e:
            # Handle case where state manager access fails
            from ray_mcp.core.foundation.logging_utils import LoggingUtility

            LoggingUtility.log_error(
                "ensure_gke_coordination",
                Exception(f"Failed to access state manager: {attr_e}"),
            )
        except Exception as e:
            # Don't fail operations if coordination fails, just log it
            from ray_mcp.core.foundation.logging_utils import LoggingUtility

            LoggingUtility.log_warning(
                "ensure_gke_coordination", f"Failed to ensure GKE coordination: {e}"
            )

    async def _list_ray_jobs_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for list_ray_jobs tool."""
        job_type = kwargs.get("job_type", "auto").lower()

        if job_type == "auto":
            # Auto-detect based on cluster state
            job_type = await self._detect_job_type()

        namespace = kwargs.get("namespace", "default")

        if job_type == "local":
            return await self.ray_manager.list_ray_jobs()
        elif job_type in ["kubernetes", "k8s"]:
            # Ensure GKE coordination is in place if we have a GKE connection
            await self._ensure_gke_coordination()
            return await self.ray_manager.list_kuberay_jobs(namespace=namespace)
        else:
            return ResponseFormatter.format_validation_error(
                f"Invalid job_type: {job_type}. Must be 'local', 'kubernetes', 'k8s', or 'auto'"
            )

    async def _inspect_ray_job_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for unified inspect_ray_job tool supporting both local and KubeRay jobs."""
        job_id = kwargs["job_id"]
        job_type = await self._detect_job_type_from_id(
            job_id, kwargs.get("job_type", "auto")
        )
        namespace = kwargs.get("namespace", "default")
        mode = kwargs.get("mode", "status")

        if job_type == "local":
            return await self.ray_manager.inspect_ray_job(job_id, mode)
        elif job_type in ["kubernetes", "k8s"]:
            await self._ensure_gke_coordination()
            return await self.ray_manager.get_kuberay_job(job_id, namespace)
        else:
            return ResponseFormatter.format_validation_error(
                f"Invalid job_type: {job_type}. Must be 'local', 'kubernetes', 'k8s', or 'auto'"
            )

    async def _cancel_ray_job_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for unified cancel_ray_job tool supporting both local and KubeRay jobs."""
        job_id = kwargs["job_id"]
        job_type = await self._detect_job_type_from_id(
            job_id, kwargs.get("job_type", "auto")
        )
        namespace = kwargs.get("namespace", "default")

        if job_type == "local":
            return await self.ray_manager.cancel_ray_job(job_id)
        elif job_type in ["kubernetes", "k8s"]:
            await self._ensure_gke_coordination()
            return await self.ray_manager.delete_kuberay_job(job_id, namespace)
        else:
            return ResponseFormatter.format_validation_error(
                f"Invalid job_type: {job_type}. Must be 'local', 'kubernetes', 'k8s', or 'auto'"
            )

    async def _retrieve_logs_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for unified retrieve_logs tool supporting both local and KubeRay jobs."""
        identifier = kwargs["identifier"]
        log_type = kwargs.get("log_type", "job")

        # Validate log_type first before attempting job type detection
        if log_type not in ["job"]:
            return ResponseFormatter.format_validation_error(
                f"Invalid log_type: {log_type}. Must be 'job'"
            )

        job_type = await self._detect_job_type_from_id(
            identifier, kwargs.get("job_type", "auto")
        )
        namespace = kwargs.get("namespace", "default")

        if job_type == "local":
            return await self.ray_manager.retrieve_logs(**kwargs)
        elif job_type in ["kubernetes", "k8s"]:
            await self._ensure_gke_coordination()
            return await self.ray_manager.get_kuberay_job_logs(identifier, namespace)
        else:
            return ResponseFormatter.format_validation_error(
                f"Invalid job_type: {job_type}. Must be 'local', 'kubernetes', 'k8s', or 'auto'"
            )

    # Ray cluster management handlers

    async def _list_ray_clusters_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for unified list_ray_clusters tool supporting both local and KubeRay clusters."""
        cluster_type = await self._detect_cluster_type_from_name(
            None, kwargs.get("cluster_type", "auto")
        )
        namespace = kwargs.get("namespace", "default")

        if cluster_type == "local":
            return await self._list_local_ray_clusters()
        elif cluster_type in ["kubernetes", "k8s"]:
            await self._ensure_gke_coordination()
            return await self.ray_manager.list_ray_clusters(namespace=namespace)
        else:
            return ResponseFormatter.format_validation_error(
                f"Invalid cluster_type: {cluster_type}. Must be 'local', 'kubernetes', 'k8s', or 'auto'"
            )

    async def _list_local_ray_clusters(self) -> Dict[str, Any]:
        """List local Ray clusters (returns current cluster info if Ray is running)."""
        try:
            # Check if Ray is initialized
            if (
                hasattr(self.ray_manager, "is_initialized")
                and self.ray_manager.is_initialized
            ):
                # Get basic cluster information
                cluster_info = await self.ray_manager.inspect_ray_cluster()
                if cluster_info.get("status") == "success":
                    # Format as a cluster list
                    cluster_data = {
                        "name": "local-ray-cluster",
                        "type": "local",
                        "status": cluster_info.get("cluster_status", "unknown"),
                        "address": self.ray_manager.cluster_address,
                        "dashboard_url": self.ray_manager.dashboard_url,
                        "ray_version": cluster_info.get("ray_version"),
                        "nodes": cluster_info.get("nodes", []),
                        "resources": cluster_info.get("cluster_resources", {}),
                    }

                    return ResponseFormatter.format_success_response(
                        clusters=[cluster_data], total_clusters=1, cluster_type="local"
                    )
                else:
                    # Ray inspection failed, return empty list
                    return ResponseFormatter.format_success_response(
                        clusters=[],
                        total_clusters=0,
                        cluster_type="local",
                        message="No local Ray cluster is currently running",
                    )
            else:
                # Ray not initialized, return empty list
                return ResponseFormatter.format_success_response(
                    clusters=[],
                    total_clusters=0,
                    cluster_type="local",
                    message="No local Ray cluster is currently running",
                )
        except Exception as e:
            return ResponseFormatter.format_error_response("list local ray clusters", e)

    async def _scale_ray_cluster_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for unified scale_ray_cluster tool supporting both local and KubeRay clusters."""
        cluster_name = kwargs.get("cluster_name")
        worker_replicas = kwargs["worker_replicas"]
        cluster_type = await self._detect_cluster_type_from_name(
            cluster_name, kwargs.get("cluster_type", "auto")
        )
        namespace = kwargs.get("namespace", "default")

        if cluster_type == "local":
            # Local Ray clusters don't support dynamic scaling
            from ray_mcp.core.foundation.logging_utils import LoggingUtility

            LoggingUtility.log_info(
                "scale_ray_cluster",
                f"Local Ray cluster scaling requested but not supported - would scale to {worker_replicas} workers",
            )

            return ResponseFormatter.format_success_response(
                status="info",
                message="Local Ray clusters do not support dynamic scaling",
                details={
                    "requested_worker_replicas": worker_replicas,
                    "cluster_type": "local",
                    "scaling_supported": False,
                    "explanation": "Local Ray clusters have a fixed number of worker nodes determined at cluster startup. To change the number of workers, you need to stop and restart the cluster with different configuration.",
                    "alternatives": [
                        "Stop the current cluster with 'stop_ray'",
                        "Restart with desired worker count using 'init_ray' with appropriate parameters",
                    ],
                },
            )
        elif cluster_type in ["kubernetes", "k8s"]:
            if not cluster_name:
                return ResponseFormatter.format_validation_error(
                    "cluster_name is required for KubeRay cluster scaling"
                )

            await self._ensure_gke_coordination()
            return await self.ray_manager.scale_ray_cluster(
                cluster_name, worker_replicas, namespace
            )
        else:
            return ResponseFormatter.format_validation_error(
                f"Invalid cluster_type: {cluster_type}. Must be 'local', 'kubernetes', 'k8s', or 'auto'"
            )

    # Cloud Provider Tool Handlers

    async def _detect_cloud_provider_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for detect_cloud_provider tool."""
        cloud_manager = self.ray_manager.get_cloud_provider_manager()
        return await cloud_manager.detect_cloud_provider()

    async def _check_environment_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for check_environment tool."""
        cloud_manager = self.ray_manager.get_cloud_provider_manager()
        provider_str = kwargs.get("provider", "all")
        if provider_str == "all":
            return await cloud_manager.check_environment()
        else:
            return await cloud_manager.check_environment(provider_str)

    async def _authenticate_cloud_provider_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for authenticate_cloud_provider tool."""
        from ray_mcp.core.foundation.interfaces import CloudProvider

        provider_str = kwargs["provider"]
        provider = CloudProvider(provider_str)

        # Build auth config from kwargs
        auth_config = {}
        for key in [
            "service_account_path",
            "project_id",
            "aws_access_key_id",
            "aws_secret_access_key",
            "region",
            "config_file",
            "context",
        ]:
            if key in kwargs:
                auth_config[key] = kwargs[key]

        cloud_manager = self.ray_manager.get_cloud_provider_manager()
        return await cloud_manager.authenticate_cloud_provider(provider, auth_config)

    async def _list_cloud_clusters_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for list_cloud_clusters tool."""
        from ray_mcp.core.foundation.interfaces import CloudProvider

        provider_str = kwargs["provider"]
        provider = CloudProvider(provider_str)

        # Extract provider-specific parameters
        provider_kwargs = {}
        if "project_id" in kwargs:
            provider_kwargs["project_id"] = kwargs["project_id"]
        if "zone" in kwargs:
            provider_kwargs["zone"] = kwargs["zone"]
        if "region" in kwargs:
            provider_kwargs["region"] = kwargs["region"]

        cloud_manager = self.ray_manager.get_cloud_provider_manager()
        return await cloud_manager.list_cloud_clusters(provider, **provider_kwargs)

    async def _connect_cloud_cluster_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for connect_cloud_cluster tool."""
        from ray_mcp.core.foundation.interfaces import CloudProvider

        provider_str = kwargs["provider"]
        provider = CloudProvider(provider_str)
        cluster_name = kwargs["cluster_name"]

        # Extract provider-specific parameters
        provider_kwargs = {}
        for key in ["project_id", "zone", "region", "config_file"]:
            if key in kwargs:
                provider_kwargs[key] = kwargs[key]

        cloud_manager = self.ray_manager.get_cloud_provider_manager()
        return await cloud_manager.connect_cloud_cluster(
            provider, cluster_name, **provider_kwargs
        )

    async def _create_cloud_cluster_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for create_cloud_cluster tool."""
        from ray_mcp.core.foundation.interfaces import CloudProvider

        provider_str = kwargs["provider"]
        provider = CloudProvider(provider_str)
        cluster_spec = kwargs["cluster_spec"]

        # Extract provider-specific parameters
        provider_kwargs = {}
        if "project_id" in kwargs:
            provider_kwargs["project_id"] = kwargs["project_id"]
        if "region" in kwargs:
            provider_kwargs["region"] = kwargs["region"]

        cloud_manager = self.ray_manager.get_cloud_provider_manager()
        return await cloud_manager.create_cloud_cluster(
            provider, cluster_spec, **provider_kwargs
        )

    async def _get_cloud_cluster_info_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for get_cloud_cluster_info tool."""
        from ray_mcp.core.foundation.interfaces import CloudProvider

        provider_str = kwargs["provider"]
        provider = CloudProvider(provider_str)
        cluster_name = kwargs["cluster_name"]

        # Extract provider-specific parameters
        provider_kwargs = {}
        for key in ["project_id", "zone", "region"]:
            if key in kwargs:
                provider_kwargs[key] = kwargs[key]

        cloud_manager = self.ray_manager.get_cloud_provider_manager()
        return await cloud_manager.get_cloud_cluster_info(
            provider, cluster_name, **provider_kwargs
        )

    async def _get_cloud_provider_status_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for get_cloud_provider_status tool."""
        from ray_mcp.core.foundation.interfaces import CloudProvider

        provider_str = kwargs["provider"]
        provider = CloudProvider(provider_str)

        cloud_manager = self.ray_manager.get_cloud_provider_manager()
        return await cloud_manager.get_provider_status(provider)

    async def _disconnect_cloud_provider_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for disconnect_cloud_provider tool."""
        from ray_mcp.core.foundation.interfaces import CloudProvider

        provider_str = kwargs["provider"]
        provider = CloudProvider(provider_str)

        cloud_manager = self.ray_manager.get_cloud_provider_manager()
        return await cloud_manager.disconnect_cloud_provider(provider)

    async def _get_cloud_config_template_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for get_cloud_config_template tool."""
        from ray_mcp.core.foundation.interfaces import CloudProvider

        provider_str = kwargs["provider"]
        provider = CloudProvider(provider_str)
        template_type = kwargs.get("template_type", "basic")

        cloud_manager = self.ray_manager.get_cloud_provider_manager()
        config_manager = cloud_manager.get_config_manager()
        return config_manager.get_cluster_template(provider, template_type)

    def _wrap_with_system_prompt(self, tool_name: str, result: Dict[str, Any]) -> str:
        """Wrap tool output with a system prompt for LLM enhancement."""
        result_json = json.dumps(result, indent=2)

        system_prompt = f"""You are an AI assistant helping with Ray cluster management. A user just called the '{tool_name}' tool and received the following response:

{result_json}

Please provide a human-readable summary of what happened, add relevant context, and suggest logical next steps. Format your response as follows:

**Tool Result Summary:**
Brief summary of what the tool call accomplished or revealed

**Context:**
Additional context about what this means for the Ray cluster

**Suggested Next Steps:**
2-3 relevant next actions the user might want to take, with specific tool names

**Available Commands:**
Quick reference of commonly used Ray MCP tools: {', '.join(self.list_tool_names())}

**Original Response:**
{result_json}"""

        return system_prompt

    @ResponseFormatter.handle_exceptions("execute tool")
    async def execute_tool(
        self, name: str, arguments: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a tool by name with the given arguments."""
        handler = self.get_tool_handler(name)
        if not handler:
            return ResponseFormatter.format_validation_error(f"Unknown tool: {name}")

        args = arguments or {}

        # Validate required parameters
        tool_info = self._tools.get(name)
        if tool_info and "schema" in tool_info:
            schema = tool_info["schema"]
            required_params = schema.get("required", [])
            missing_params = [param for param in required_params if param not in args]
            if missing_params:
                return ResponseFormatter.format_validation_error(
                    f"Missing required parameters for tool '{name}': {', '.join(missing_params)}"
                )

        result = await handler(**args)

        # Check if enhanced output is enabled
        use_enhanced_output = (
            os.getenv("RAY_MCP_ENHANCED_OUTPUT", "false").lower() == "true"
        )

        if use_enhanced_output:
            enhanced_response = self._wrap_with_system_prompt(name, result)
            return ResponseFormatter.format_success_response(
                enhanced_output=enhanced_response, raw_result=result
            )
        else:
            return result
