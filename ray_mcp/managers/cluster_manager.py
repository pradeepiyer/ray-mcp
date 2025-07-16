"""Pure prompt-driven cluster management for Ray."""

import asyncio
import json
import os
import re
import subprocess
from typing import Any, Optional

from ..config import config
from ..foundation.base_execute_mixin import BaseExecuteRequestMixin
from ..foundation.import_utils import ray
from ..foundation.logging_utils import error_response, success_response
from ..foundation.resource_manager import ResourceManager
from ..llm_parser import get_parser


class ClusterManager(ResourceManager, BaseExecuteRequestMixin):
    """Pure prompt-driven Ray cluster management - no traditional APIs."""

    def __init__(self):
        super().__init__(enable_ray=True)
        # Simple state tracking without complex state manager
        self._cluster_address = None
        self._dashboard_url = None
        self._job_client = None
        # Synchronization for cluster operations
        self._cluster_lock = asyncio.Lock()

    def get_action_parser(self):
        """Get the action parser for cluster operations."""
        return get_parser().parse_cluster_action

    def get_operation_handlers(self) -> dict[str, Any]:
        """Get mapping of operation names to handler methods."""
        return {
            "create": self._create_cluster_from_prompt,
            "connect": self._handle_connect,
            "inspect": self._inspect_cluster,
            "stop": self._stop_cluster,
            "list": self._list_clusters,
            "scale": self._handle_scale,
        }

    async def _handle_connect(self, action: dict[str, Any]) -> dict[str, Any]:
        """Handle connect operation with validation."""
        address = action.get("address")
        if not address:
            return error_response("cluster address required")
        return await self._connect_to_cluster(address)

    async def _handle_scale(self, action: dict[str, Any]) -> dict[str, Any]:
        """Handle scale operation with validation."""
        workers = action.get("workers")
        if workers is None:
            return error_response("number of workers required for scaling")
        return await self._scale_cluster(workers)

    # =================================================================
    # INTERNAL IMPLEMENTATION: All methods are now private
    # =================================================================

    async def _create_cluster_from_prompt(
        self, action: dict[str, Any]
    ) -> dict[str, Any]:
        """Create cluster from parsed prompt action."""
        try:
            # Extract parameters with simple defaults
            cluster_spec = {
                "num_cpus": action.get("cpus", 4),
                "num_gpus": action.get("gpus", 0),
                "dashboard_port": action.get("dashboard_port", 8265),
                "object_store_memory": action.get("object_store_memory"),
                "temp_dir": action.get("temp_dir"),
                "include_dashboard": action.get("include_dashboard", True),
            }

            return await self._create_cluster(cluster_spec)

        except Exception as e:
            return self._handle_error("create cluster from prompt", e)

    async def _create_cluster(self, cluster_spec: dict[str, Any]) -> dict[str, Any]:
        """Create a new Ray cluster."""
        async with self._cluster_lock:
            try:
                self._ensure_ray_available()

                # Check if Ray is already running
                if self._is_ray_ready():
                    return error_response(
                        "Ray cluster is already running. Stop it first or connect to it."
                    )

                # Simple port allocation - use default or provided port
                dashboard_port = cluster_spec.get("dashboard_port", 8265)

                # Start Ray with simple configuration
                config = {
                    "num_cpus": cluster_spec.get("num_cpus", 4),
                    "num_gpus": cluster_spec.get("num_gpus", 0),
                    "dashboard_port": dashboard_port,
                    "include_dashboard": cluster_spec.get("include_dashboard", True),
                }

                # Add optional parameters if provided
                if cluster_spec.get("object_store_memory"):
                    config["object_store_memory"] = cluster_spec["object_store_memory"]
                if cluster_spec.get("temp_dir"):
                    config["temp_dir"] = cluster_spec["temp_dir"]

                # Initialize Ray
                ray_info = ray.init(**config)

                # Update simple state tracking
                self._cluster_address = ray_info.address_info.get(
                    "redis_address"
                ) or ray_info.address_info.get("gcs_address")
                # Get dashboard URL from Ray context, add http:// prefix if needed
                dashboard_url = (
                    ray_info.dashboard_url
                    if hasattr(ray_info, "dashboard_url")
                    else f"127.0.0.1:{dashboard_port}"
                )
                self._dashboard_url = (
                    f"http://{dashboard_url}"
                    if not dashboard_url.startswith("http")
                    else dashboard_url
                )

                return success_response(
                    cluster_address=self._cluster_address,
                    dashboard_url=self._dashboard_url,
                    dashboard_port=dashboard_port,
                    num_cpus=config["num_cpus"],
                    num_gpus=config["num_gpus"],
                    message="Ray cluster created successfully",
                )

            except Exception as e:
                return self._handle_error("create cluster", e)

    async def _connect_to_cluster(self, address: str) -> dict[str, Any]:
        """Connect to an existing Ray cluster."""
        async with self._cluster_lock:
            try:
                self._ensure_ray_available()

                # Check if already connected to a different cluster
                if self._is_ray_ready():
                    current_address = self._cluster_address
                    if current_address == address:
                        return success_response(
                            cluster_address=address,
                            message="Already connected to this cluster",
                        )
                    else:
                        return error_response(
                            f"Already connected to {current_address}. Disconnect first."
                        )

                # Connect to the cluster with timeout
                try:
                    ray_info = await asyncio.wait_for(
                        asyncio.to_thread(ray.init, address=address),
                        timeout=30,  # 30 second timeout for connection attempts
                    )
                except asyncio.TimeoutError:
                    raise Exception(
                        f"Connection to cluster at {address} timed out after 30 seconds"
                    )

                # Update simple state tracking
                self._cluster_address = address

                # Get dashboard URL from Ray context
                if hasattr(ray_info, "dashboard_url") and ray_info.dashboard_url:
                    dashboard_url = ray_info.dashboard_url
                    self._dashboard_url = (
                        f"http://{dashboard_url}"
                        if not dashboard_url.startswith("http")
                        else dashboard_url
                    )
                else:
                    self._dashboard_url = None

                return success_response(
                    cluster_address=address,
                    dashboard_url=self._dashboard_url,
                    message=f"Connected to Ray cluster at {address}",
                )

            except Exception as e:
                return self._handle_error("connect to cluster", e)

    async def _inspect_cluster(self, action: dict[str, Any]) -> dict[str, Any]:
        """Inspect current cluster status."""
        try:
            if not self._is_ray_ready():
                return success_response(
                    cluster_status="not_running",
                    message="No Ray cluster is currently running",
                )

            # Get cluster information
            cluster_info = {
                "cluster_status": "running",
                "cluster_address": self._cluster_address,
                "dashboard_url": self._dashboard_url,
                "nodes": self._get_cluster_nodes(),
                "resources": self._get_cluster_resources(),
                "message": "Cluster inspection completed successfully",
            }

            return success_response(**cluster_info)

        except Exception as e:
            return self._handle_error("inspect cluster", e)

    async def _stop_cluster(self, action: dict[str, Any]) -> dict[str, Any]:
        """Stop the current Ray cluster."""
        async with self._cluster_lock:
            try:
                if not self._is_ray_ready():
                    return success_response(
                        message="No Ray cluster is currently running"
                    )

                # Shutdown Ray
                ray.shutdown()

                # Clear simple state tracking
                self._cluster_address = None
                self._dashboard_url = None
                self._job_client = None

                return success_response(message="Ray cluster stopped successfully")

            except Exception as e:
                return self._handle_error("stop cluster", e)

    def _get_dashboard_url(self) -> Optional[str]:
        """Get dashboard URL from Ray cluster."""
        try:
            if not self._is_ray_ready():
                return None

            # Return stored dashboard URL if available
            if self._dashboard_url:
                return self._dashboard_url

            # Fallback to default port
            return "http://127.0.0.1:8265"

        except Exception:
            return None

    def _get_cluster_nodes(self) -> list[dict[str, Any]]:
        """Get information about cluster nodes."""
        try:
            if not self._is_ray_ready():
                return []

            nodes = ray.nodes()
            return [
                {
                    "node_id": node.get("NodeID", "unknown"),
                    "alive": node.get("Alive", False),
                    "resources": node.get("Resources", {}),
                }
                for node in nodes
            ]

        except Exception:
            return []

    def _get_cluster_resources(self) -> dict[str, Any]:
        """Get cluster resource information."""
        try:
            if not self._is_ray_ready():
                return {}

            cluster_resources = ray.cluster_resources()
            available_resources = ray.available_resources()

            return {
                "total": cluster_resources,
                "available": available_resources,
            }

        except Exception:
            return {}

    async def _list_clusters(self, action: dict[str, Any]) -> dict[str, Any]:
        """List available Ray clusters."""
        try:
            clusters = []

            # Check if current cluster is running
            if self._is_ray_ready():
                cluster_info = {
                    "name": "current",
                    "address": self._cluster_address or "local",
                    "status": "running",
                    "dashboard_url": self._dashboard_url,
                    "nodes": len(self._get_cluster_nodes()),
                    "resources": self._get_cluster_resources(),
                }
                clusters.append(cluster_info)

            return success_response(
                clusters=clusters,
                total_count=len(clusters),
                message=f"Found {len(clusters)} Ray cluster(s)",
            )

        except Exception as e:
            return self._handle_error("list clusters", e)

    async def _scale_cluster(self, workers: int) -> dict[str, Any]:
        """Scale the Ray cluster to the specified number of workers."""
        try:
            if not self._is_ray_ready():
                return error_response("No Ray cluster is currently running")

            # For local clusters, scaling is limited since Ray doesn't provide
            # direct scaling APIs for local clusters
            current_nodes = self._get_cluster_nodes()
            current_worker_count = len(
                [n for n in current_nodes if not n.get("is_head", False)]
            )

            if workers == current_worker_count:
                return success_response(
                    message=f"Cluster already has {workers} workers",
                    current_workers=current_worker_count,
                    requested_workers=workers,
                )

            # Note: For local Ray clusters, manual scaling is not directly supported
            # This is more relevant for cloud/kubernetes clusters
            return error_response(
                f"Manual scaling not supported for local Ray clusters. Current workers: {current_worker_count}, requested: {workers}. Consider using KubeRay for dynamic scaling."
            )

        except Exception as e:
            return self._handle_error("scale cluster", e)
