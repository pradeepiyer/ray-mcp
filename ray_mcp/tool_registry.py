"""Streamlined tool registry for Ray MCP server using modular schemas.

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

from .foundation.logging_utils import ResponseFormatter
from .managers.unified_manager import RayUnifiedManager
from .tools import cloud_tools, cluster_tools, job_tools, log_tools

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Streamlined registry for Ray MCP tools with modular schemas."""

    def __init__(self, ray_manager: RayUnifiedManager):
        self.ray_manager = ray_manager
        self._tools: Dict[str, Dict[str, Any]] = {}
        self.response_formatter = ResponseFormatter()
        self._register_all_tools()

    def _register_all_tools(self) -> None:
        """Register all available tools with their schemas and implementations."""

        # Cluster management tools
        self._register_tool(
            name="init_ray_cluster",
            description="Initialize Ray cluster - start a new local cluster, connect to existing cluster, or create a Kubernetes cluster via KubeRay. Supports both local Ray clusters and Kubernetes-based clusters using KubeRay operator. If address is provided, connects to existing cluster; otherwise creates new cluster based on cluster_type. IMPORTANT: For head-node-only clusters (no worker nodes), explicitly pass worker_nodes=[] (empty array). For default behavior (2 workers), omit worker_nodes parameter.",
            schema=cluster_tools.get_init_ray_cluster_schema(),
            handler=self._init_ray_cluster_handler,
        )

        self._register_tool(
            name="stop_ray_cluster",
            description="Stop or delete a Ray cluster. Supports both local Ray clusters (stop) and KubeRay clusters (delete). For KubeRay clusters, provide cluster_name and namespace.",
            schema=cluster_tools.get_stop_ray_cluster_schema(),
            handler=self._stop_ray_cluster_handler,
        )

        self._register_tool(
            name="inspect_ray_cluster",
            description="Get comprehensive cluster information including status, resources, and nodes. Supports both local Ray clusters and KubeRay clusters. For KubeRay clusters, provide cluster_name and namespace.",
            schema=cluster_tools.get_inspect_ray_cluster_schema(),
            handler=self._inspect_ray_cluster_handler,
        )

        self._register_tool(
            name="scale_ray_cluster",
            description="Scale Ray cluster worker nodes. Supports both local Ray clusters and KubeRay clusters.",
            schema=cluster_tools.get_scale_ray_cluster_schema(),
            handler=self._scale_ray_cluster_handler,
        )

        self._register_tool(
            name="list_ray_clusters",
            description="List available Ray clusters. Supports both local Ray clusters and KubeRay clusters.",
            schema=cluster_tools.get_list_ray_clusters_schema(),
            handler=self._list_ray_clusters_handler,
        )

        # Job management tools
        self._register_tool(
            name="submit_ray_job",
            description="Submit a job to the Ray cluster. Supports both local Ray clusters and Kubernetes-based clusters using KubeRay operator. Automatically detects job type based on cluster state or explicit job_type parameter. For local clusters, uses Ray job submission API. For Kubernetes clusters, creates RayJob CRD resources.",
            schema=job_tools.get_submit_ray_job_schema(),
            handler=self._submit_ray_job_handler,
        )

        self._register_tool(
            name="list_ray_jobs",
            description="List all jobs in the Ray cluster. Supports both local Ray clusters and KubeRay jobs.",
            schema=job_tools.get_list_ray_jobs_schema(),
            handler=self._list_ray_jobs_handler,
        )

        self._register_tool(
            name="inspect_ray_job",
            description="Get detailed information about a specific Ray job. Supports both local Ray clusters and KubeRay jobs.",
            schema=job_tools.get_inspect_ray_job_schema(),
            handler=self._inspect_ray_job_handler,
        )

        self._register_tool(
            name="cancel_ray_job",
            description="Cancel a running Ray job. Supports both local Ray clusters and KubeRay jobs.",
            schema=job_tools.get_cancel_ray_job_schema(),
            handler=self._cancel_ray_job_handler,
        )

        # Log management tools
        self._register_tool(
            name="retrieve_logs",
            description="Retrieve logs from Ray cluster components, jobs, or tasks with optional filtering and pagination.",
            schema=log_tools.get_retrieve_logs_schema(),
            handler=self._retrieve_logs_handler,
        )

        # Cloud provider tools
        self._register_tool(
            name="detect_cloud_provider",
            description="Detect the current cloud provider environment and available authentication methods.",
            schema=cloud_tools.get_detect_cloud_provider_schema(),
            handler=self._detect_cloud_provider_handler,
        )

        self._register_tool(
            name="check_environment",
            description="Check environment setup, dependencies, and authentication status for cloud providers.",
            schema=cloud_tools.get_check_environment_schema(),
            handler=self._check_environment_handler,
        )

        self._register_tool(
            name="authenticate_cloud_provider",
            description="Authenticate with a cloud provider using provided credentials.",
            schema=cloud_tools.get_authenticate_cloud_provider_schema(),
            handler=self._authenticate_cloud_provider_handler,
        )

        self._register_tool(
            name="list_cloud_clusters",
            description="List available clusters in the specified cloud provider.",
            schema=cloud_tools.get_list_cloud_clusters_schema(),
            handler=self._list_cloud_clusters_handler,
        )

        self._register_tool(
            name="connect_cloud_cluster",
            description="Connect to an existing cluster in the specified cloud provider.",
            schema=cloud_tools.get_connect_cloud_cluster_schema(),
            handler=self._connect_cloud_cluster_handler,
        )

        self._register_tool(
            name="create_cloud_cluster",
            description="Create a new cluster in the specified cloud provider.",
            schema=cloud_tools.get_create_cloud_cluster_schema(),
            handler=self._create_cloud_cluster_handler,
        )

        self._register_tool(
            name="get_cloud_cluster_info",
            description="Get detailed information about a specific cloud cluster.",
            schema=cloud_tools.get_get_cloud_cluster_info_schema(),
            handler=self._get_cloud_cluster_info_handler,
        )

        self._register_tool(
            name="get_cloud_provider_status",
            description="Get current status and connection information for cloud providers.",
            schema=cloud_tools.get_get_cloud_provider_status_schema(),
            handler=self._get_cloud_provider_status_handler,
        )

        self._register_tool(
            name="disconnect_cloud_provider",
            description="Disconnect from the specified cloud provider.",
            schema=cloud_tools.get_disconnect_cloud_provider_schema(),
            handler=self._disconnect_cloud_provider_handler,
        )

        self._register_tool(
            name="get_cloud_config_template",
            description="Get configuration templates for cloud provider setup.",
            schema=cloud_tools.get_get_cloud_config_template_schema(),
            handler=self._get_cloud_config_template_handler,
        )

    def _register_tool(
        self, name: str, description: str, schema: Dict[str, Any], handler: Callable
    ) -> None:
        """Register a tool with its schema and handler."""
        self._tools[name] = {
            "description": description,
            "schema": schema,
            "handler": handler,
        }

    def get_tool_list(self) -> List[Tool]:
        """Get list of all registered tools."""
        return [
            Tool(
                name=name,
                description=tool_info["description"],
                inputSchema=tool_info["schema"],
            )
            for name, tool_info in self._tools.items()
        ]

    def get_tool_handler(self, name: str) -> Optional[Callable]:
        """Get handler for a specific tool."""
        tool_info = self._tools.get(name)
        return tool_info["handler"] if tool_info else None

    def list_tool_names(self) -> List[str]:
        """Get a list of all registered tool names."""
        return list(self._tools.keys())

    # =================================================================
    # TOOL HANDLERS - Streamlined versions with core logic intact
    # =================================================================

    async def _init_ray_cluster_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for init_ray_cluster tool with support for both local and Kubernetes clusters."""
        cluster_type = kwargs.get("cluster_type", "local").lower()

        # If address is provided, handle based on cluster type
        if kwargs.get("address"):
            if cluster_type in ["kubernetes", "k8s"]:
                await self._ensure_gke_coordination()
                return await self.ray_manager.init_cluster(**kwargs)
            else:
                local_kwargs = {
                    k: v
                    for k, v in kwargs.items()
                    if k not in ["cluster_type", "kubernetes_config"]
                }
                return await self.ray_manager.init_cluster(**local_kwargs)

        # For local clusters, use existing init_cluster method
        if cluster_type == "local":
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

    async def _scale_ray_cluster_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for scale_ray_cluster tool."""
        cluster_name = kwargs.get("cluster_name")
        cluster_type = await self._detect_cluster_type_from_name(
            cluster_name, kwargs.get("cluster_type", "auto")
        )
        namespace = kwargs.get("namespace", "default")
        worker_replicas = kwargs.get("worker_replicas")

        if cluster_type == "local":
            return ResponseFormatter.format_validation_error(
                "Scaling not supported for local clusters"
            )
        elif cluster_type in ["kubernetes", "k8s"]:
            if not cluster_name:
                return ResponseFormatter.format_validation_error(
                    "cluster_name is required for KubeRay cluster scaling"
                )
            if worker_replicas is None:
                return ResponseFormatter.format_validation_error(
                    "worker_replicas is required for cluster scaling"
                )
            await self._ensure_gke_coordination()
            return await self.ray_manager.scale_ray_cluster(
                cluster_name, worker_replicas, namespace
            )
        else:
            return ResponseFormatter.format_validation_error(
                f"Invalid cluster_type: {cluster_type}. Must be 'local', 'kubernetes', 'k8s', or 'auto'"
            )

    async def _list_ray_clusters_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for list_ray_clusters tool."""
        cluster_type = kwargs.get("cluster_type", "all").lower()
        namespace = kwargs.get("namespace", "default")

        if cluster_type == "local":
            return await self._list_local_ray_clusters()
        elif cluster_type in ["kubernetes", "k8s"]:
            await self._ensure_gke_coordination()
            return await self.ray_manager.list_ray_clusters(namespace=namespace)
        elif cluster_type == "all":
            # Combine local and Kubernetes clusters
            local_result = await self._list_local_ray_clusters()
            k8s_result = await self.ray_manager.list_ray_clusters(namespace=namespace)

            clusters = []
            if local_result.get("status") == "success":
                clusters.extend(local_result.get("clusters", []))
            if k8s_result.get("status") == "success":
                clusters.extend(k8s_result.get("clusters", []))

            return ResponseFormatter.format_success_response(
                clusters=clusters, total_count=len(clusters)
            )
        else:
            return ResponseFormatter.format_validation_error(
                f"Invalid cluster_type: {cluster_type}. Must be 'local', 'kubernetes', 'k8s', or 'all'"
            )

    async def _submit_ray_job_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for submit_ray_job tool with support for both local and Kubernetes jobs."""
        job_type = kwargs.get("job_type", "auto").lower()

        if job_type == "auto":
            job_type = await self._detect_job_type()

        if job_type == "local":
            # Filter kwargs for local job submission
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
                ]
            }

            # Filter to only include valid parameters for local job submission
            sig = inspect.signature(self.ray_manager.submit_ray_job)
            valid_params = {k for k in sig.parameters.keys() if k != "self"}
            filtered = {k: v for k, v in local_kwargs.items() if k in valid_params}
            return await self.ray_manager.submit_ray_job(**filtered)

        elif job_type in ["kubernetes", "k8s"]:
            await self._ensure_gke_coordination()
            return await self._create_kuberay_job(**kwargs)

        else:
            return ResponseFormatter.format_validation_error(
                f"Invalid job_type: {job_type}. Must be 'local', 'kubernetes', 'k8s', or 'auto'"
            )

    async def _list_ray_jobs_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for list_ray_jobs tool."""
        job_type = kwargs.get("job_type", "auto").lower()
        namespace = kwargs.get("namespace", "default")

        if job_type == "auto":
            job_type = await self._detect_job_type()

        if job_type == "local":
            return await self.ray_manager.list_ray_jobs()
        elif job_type in ["kubernetes", "k8s"]:
            await self._ensure_gke_coordination()
            return await self.ray_manager.list_kuberay_jobs(namespace=namespace)
        elif job_type == "all":
            # Combine local and Kubernetes jobs
            local_result = await self.ray_manager.list_ray_jobs()
            k8s_result = await self.ray_manager.list_kuberay_jobs(namespace=namespace)

            jobs = []
            if local_result.get("status") == "success":
                jobs.extend(local_result.get("jobs", []))
            if k8s_result.get("status") == "success":
                jobs.extend(k8s_result.get("jobs", []))

            return ResponseFormatter.format_success_response(
                jobs=jobs, total_count=len(jobs)
            )
        else:
            return ResponseFormatter.format_validation_error(
                f"Invalid job_type: {job_type}. Must be 'local', 'kubernetes', 'k8s', 'auto', or 'all'"
            )

    async def _inspect_ray_job_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for inspect_ray_job tool."""
        job_id = kwargs.get("job_id")
        if not job_id:
            return ResponseFormatter.format_validation_error(
                "job_id is required for job inspection"
            )

        job_type = await self._detect_job_type_from_id(
            job_id, kwargs.get("job_type", "auto")
        )
        namespace = kwargs.get("namespace", "default")

        if job_type == "local":
            return await self.ray_manager.inspect_ray_job(job_id)
        elif job_type in ["kubernetes", "k8s"]:
            await self._ensure_gke_coordination()
            return await self.ray_manager.get_kuberay_job(job_id, namespace)
        else:
            return ResponseFormatter.format_validation_error(
                f"Invalid job_type: {job_type}. Must be 'local', 'kubernetes', 'k8s', or 'auto'"
            )

    async def _cancel_ray_job_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for cancel_ray_job tool."""
        job_id = kwargs.get("job_id")
        if not job_id:
            return ResponseFormatter.format_validation_error(
                "job_id is required for job cancellation"
            )

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
        """Handler for retrieve_logs tool."""
        return await self.ray_manager.retrieve_logs(**kwargs)

    # Cloud provider handlers
    async def _detect_cloud_provider_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for detect_cloud_provider tool."""
        return await self.ray_manager.detect_cloud_provider()

    async def _check_environment_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for check_environment tool."""
        return await self.ray_manager.check_environment(**kwargs)

    async def _authenticate_cloud_provider_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for authenticate_cloud_provider tool."""
        provider = kwargs.get("provider")
        if not provider:
            return ResponseFormatter.format_validation_error("provider is required")

        # Bundle auth parameters into auth_config
        auth_config = {}
        auth_params = [
            "service_account_path",
            "project_id",
            "aws_access_key_id",
            "aws_secret_access_key",
            "region",
            "config_file",
            "context",
        ]

        for param in auth_params:
            if param in kwargs:
                auth_config[param] = kwargs[param]

        # Pass only provider and auth_config to the underlying method
        return await self.ray_manager.authenticate_cloud_provider(
            provider=provider, auth_config=auth_config if auth_config else None
        )

    async def _list_cloud_clusters_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for list_cloud_clusters tool."""
        return await self.ray_manager.list_cloud_clusters(**kwargs)

    async def _connect_cloud_cluster_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for connect_cloud_cluster tool."""
        return await self.ray_manager.connect_cloud_cluster(**kwargs)

    async def _create_cloud_cluster_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for create_cloud_cluster tool."""
        return await self.ray_manager.create_cloud_cluster(**kwargs)

    async def _get_cloud_cluster_info_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for get_cloud_cluster_info tool."""
        return await self.ray_manager.get_cloud_cluster_info(**kwargs)

    async def _get_cloud_provider_status_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for get_cloud_provider_status tool."""
        return await self.ray_manager.get_cloud_provider_status(**kwargs)

    async def _disconnect_cloud_provider_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for disconnect_cloud_provider tool."""
        return await self.ray_manager.disconnect_cloud_provider(**kwargs)

    async def _get_cloud_config_template_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for get_cloud_config_template tool."""
        return await self.ray_manager.get_cloud_config_template(**kwargs)

    # =================================================================
    # HELPER METHODS
    # =================================================================

    async def _ensure_gke_coordination(self) -> None:
        """Ensure GKE coordination is in place if we have a GKE connection."""
        try:
            return await self.ray_manager._ensure_kuberay_gke_coordination()
        except Exception as coord_error:
            logger.warning(
                f"Failed to coordinate GKE for Ray connection: {coord_error}"
            )

    async def _detect_job_type(self) -> str:
        """Detect job type based on cluster state."""
        try:
            state = self.ray_manager.state_manager.get_state()
            gke_connection = state.get("cloud_provider_connections", {}).get("gke", {})

            if gke_connection.get("connected", False):
                return "kubernetes"
            if state.get("kubernetes_connected", False):
                return "kubernetes"
            if (
                hasattr(self.ray_manager, "kuberay_clusters")
                and self.ray_manager.kuberay_clusters
            ):
                return "kubernetes"
            if (
                hasattr(self.ray_manager, "is_initialized")
                and self.ray_manager.is_initialized
            ):
                return "local"

            return "local"
        except Exception:
            return "local"

    async def _detect_job_type_from_id(
        self, job_id: str, explicit_job_type: str = "auto"
    ) -> str:
        """Detect job type based on job ID patterns and explicit type."""
        import re

        if explicit_job_type and explicit_job_type.lower() != "auto":
            return explicit_job_type.lower()

        # If no job_id provided, fall back to general detection
        if not job_id:
            return await self._detect_job_type()

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

        return await self._detect_job_type()

    async def _detect_cluster_type_from_name(
        self, cluster_name: Optional[str] = None, explicit_cluster_type: str = "auto"
    ) -> str:
        """Detect cluster type based on cluster name and explicit type."""
        import re

        if explicit_cluster_type and explicit_cluster_type.lower() != "auto":
            return explicit_cluster_type.lower()

        if not cluster_name:
            return "local"

        # Kubernetes resource name format suggests KubeRay cluster
        if (
            re.match(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", cluster_name)
            and len(cluster_name) <= 63
        ):
            return "kubernetes"

        return await self._detect_job_type()

    async def _create_kuberay_cluster(self, **kwargs) -> Dict[str, Any]:
        """Create a KubeRay cluster from init_ray parameters."""
        try:
            await self._ensure_gke_coordination()
            kubernetes_config = kwargs.get("kubernetes_config", {})
            namespace = kubernetes_config.get("namespace", "default")
            cluster_spec = await self._build_kuberay_cluster_spec(**kwargs)
            return await self.ray_manager.create_kuberay_cluster(
                cluster_spec=cluster_spec, namespace=namespace
            )
        except Exception as e:
            return ResponseFormatter.format_error_response("create kuberay cluster", e)

    async def _create_kuberay_job(self, **kwargs) -> Dict[str, Any]:
        """Create a KubeRay job from submit_job parameters."""
        try:
            await self._ensure_gke_coordination()
            kubernetes_config = kwargs.get("kubernetes_config", {})
            namespace = kubernetes_config.get("namespace", "default")
            job_spec = await self._build_kuberay_job_spec(**kwargs)
            return await self.ray_manager.create_kuberay_job(
                job_spec=job_spec, namespace=namespace
            )
        except Exception as e:
            return ResponseFormatter.format_error_response("create kuberay job", e)

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
            "num_cpus": kwargs.get("num_cpus", 2),
            "service_type": kubernetes_config.get("service_type", "LoadBalancer"),
        }

        if kubernetes_config.get("service_annotations"):
            head_node_config["service_annotations"] = kubernetes_config[
                "service_annotations"
            ]
        if kwargs.get("num_gpus"):
            head_node_config["num_gpus"] = kwargs["num_gpus"]
        if kwargs.get("object_store_memory"):
            head_node_config["object_store_memory"] = kwargs["object_store_memory"]
        if resources.get("head_node"):
            head_node_config["resources"] = resources["head_node"]

        cluster_spec["head_node_spec"] = head_node_config

        # Worker nodes configuration
        worker_node_specs = []
        if worker_nodes is not None:
            if len(worker_nodes) == 0:
                pass  # Head-only cluster
            else:
                for i, worker_config in enumerate(worker_nodes):
                    worker_spec = {
                        "group_name": worker_config.get(
                            "node_name", f"worker-group-{i}"
                        ),
                        "replicas": 1,
                        "image": worker_config.get("image", default_image),
                        "num_cpus": worker_config.get("num_cpus", 2),
                    }
                    if worker_config.get("num_gpus"):
                        worker_spec["num_gpus"] = worker_config["num_gpus"]
                    worker_node_specs.append(worker_spec)
        else:
            # Default: create 2 worker groups
            default_worker_spec = {
                "group_name": "worker-group",
                "replicas": 2,
                "image": default_image,
                "num_cpus": 2,
            }
            if resources.get("worker_nodes"):
                default_worker_spec["resources"] = resources["worker_nodes"]
            worker_node_specs.append(default_worker_spec)

        cluster_spec["worker_node_specs"] = worker_node_specs
        return cluster_spec

    async def _build_kuberay_job_spec(self, **kwargs) -> Dict[str, Any]:
        """Build KubeRay job specification from submit_job parameters."""
        kubernetes_config = kwargs.get("kubernetes_config", {})

        return {
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
            ),
        }

    async def _list_local_ray_clusters(self) -> Dict[str, Any]:
        """List local Ray clusters."""
        try:
            state = self.ray_manager.state_manager.get_state()
            clusters = []

            if state.get("initialized", False):
                clusters.append(
                    {
                        "name": "local-ray-cluster",
                        "type": "local",
                        "status": "running",
                        "address": state.get("cluster_address", "local"),
                        "dashboard_url": state.get("dashboard_url", "N/A"),
                    }
                )

            return ResponseFormatter.format_success_response(
                clusters=clusters, total_count=len(clusters)
            )
        except Exception as e:
            return ResponseFormatter.format_error_response("list local ray clusters", e)

    def _wrap_with_system_prompt(self, tool_name: str, result: Dict[str, Any]) -> str:
        """Wrap tool output with a system prompt for LLM enhancement."""
        result_json = json.dumps(result, indent=2)

        system_prompt = f"""You are an AI assistant helping with Ray cluster management. A user just called 
the '{tool_name}' tool and received the following response:

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

        # Execute the handler
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
