"""Pure prompt-driven cluster management for Ray."""

import asyncio
import json
import os
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from ..config import get_config_manager_sync
from ..foundation.base_managers import ResourceManager
from ..parsers import ActionParser


class ClusterManager(ResourceManager):
    """Pure prompt-driven Ray cluster management - no traditional APIs."""

    def __init__(self):
        super().__init__(enable_ray=True)
        self._config_manager = get_config_manager_sync()
        # Simple state tracking without complex state manager
        self._cluster_address = None
        self._dashboard_url = None
        self._job_client = None

    async def execute_request(self, prompt: str) -> Dict[str, Any]:
        """Execute cluster operations using natural language prompts.

        Examples:
            - "create a local cluster with 4 CPUs"
            - "connect to cluster at 10.0.0.1:10001"
            - "stop the current cluster"
            - "inspect cluster status"
        """
        try:
            action = ActionParser.parse_cluster_action(prompt)
            operation = action["operation"]

            if operation == "create":
                return await self._create_cluster_from_prompt(action)
            elif operation == "connect":
                address = action.get("address")
                if not address:
                    return {"status": "error", "message": "cluster address required"}
                return await self._connect_to_cluster(address)
            elif operation == "inspect":
                return await self._inspect_cluster()
            elif operation == "stop":
                return await self._stop_cluster()
            else:
                return {"status": "error", "message": f"Unknown operation: {operation}"}

        except ValueError as e:
            return {"status": "error", "message": f"Could not parse request: {str(e)}"}
        except Exception as e:
            return self._ResponseFormatter.format_error_response("execute_request", e)

    # =================================================================
    # INTERNAL IMPLEMENTATION: All methods are now private
    # =================================================================

    async def _create_cluster_from_prompt(
        self, action: Dict[str, Any]
    ) -> Dict[str, Any]:
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
            return self._ResponseFormatter.format_error_response(
                "create cluster from prompt", e
            )

    async def _create_cluster(self, cluster_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new Ray cluster."""
        try:
            self._ensure_ray_available()

            # Check if Ray is already running
            if self._is_ray_ready():
                return self._ResponseFormatter.format_error_response(
                    "create cluster",
                    Exception(
                        "Ray cluster is already running. Stop it first or connect to it."
                    ),
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
            ray_info = self._ray.init(**config)

            # Update simple state tracking
            self._cluster_address = ray_info.get("redis_address") or ray_info.get(
                "gcs_address"
            )
            self._dashboard_url = f"http://127.0.0.1:{dashboard_port}"

            return self._ResponseFormatter.format_success_response(
                cluster_address=self._cluster_address,
                dashboard_url=self._dashboard_url,
                dashboard_port=dashboard_port,
                num_cpus=config["num_cpus"],
                num_gpus=config["num_gpus"],
                message="Ray cluster created successfully",
            )

        except Exception as e:
            return self._ResponseFormatter.format_error_response("create cluster", e)

    async def _connect_to_cluster(self, address: str) -> Dict[str, Any]:
        """Connect to an existing Ray cluster."""
        try:
            self._ensure_ray_available()

            # Check if already connected to a different cluster
            if self._is_ray_ready():
                current_address = self._cluster_address
                if current_address == address:
                    return self._ResponseFormatter.format_success_response(
                        cluster_address=address,
                        message="Already connected to this cluster",
                    )
                else:
                    return self._ResponseFormatter.format_error_response(
                        "connect to cluster",
                        Exception(
                            f"Already connected to {current_address}. Disconnect first."
                        ),
                    )

            # Connect to the cluster
            ray_info = self._ray.init(address=address)

            # Update simple state tracking
            self._cluster_address = address

            # Try to determine dashboard URL
            try:
                dashboard_url = self._get_dashboard_url()
                self._dashboard_url = dashboard_url
            except Exception:
                self._dashboard_url = None

            return self._ResponseFormatter.format_success_response(
                cluster_address=address,
                dashboard_url=self._dashboard_url,
                message=f"Connected to Ray cluster at {address}",
            )

        except Exception as e:
            return self._ResponseFormatter.format_error_response(
                "connect to cluster", e
            )

    async def _inspect_cluster(self) -> Dict[str, Any]:
        """Inspect current cluster status."""
        try:
            if not self._is_ray_ready():
                return self._ResponseFormatter.format_success_response(
                    status="not_running", message="No Ray cluster is currently running"
                )

            # Get cluster information
            cluster_info = {
                "status": "running",
                "cluster_address": self._cluster_address,
                "dashboard_url": self._dashboard_url,
                "nodes": self._get_cluster_nodes(),
                "resources": self._get_cluster_resources(),
            }

            return self._ResponseFormatter.format_success_response(**cluster_info)

        except Exception as e:
            return self._ResponseFormatter.format_error_response("inspect cluster", e)

    async def _stop_cluster(self) -> Dict[str, Any]:
        """Stop the current Ray cluster."""
        try:
            if not self._is_ray_ready():
                return self._ResponseFormatter.format_success_response(
                    message="No Ray cluster is currently running"
                )

            # Shutdown Ray
            self._ray.shutdown()

            # Clear simple state tracking
            self._cluster_address = None
            self._dashboard_url = None
            self._job_client = None

            return self._ResponseFormatter.format_success_response(
                message="Ray cluster stopped successfully"
            )

        except Exception as e:
            return self._ResponseFormatter.format_error_response("stop cluster", e)

    def _get_dashboard_url(self) -> Optional[str]:
        """Get dashboard URL from Ray cluster."""
        try:
            if not self._is_ray_ready():
                return None

            # Try to get dashboard URL from Ray
            runtime_context = self._ray.get_runtime_context()
            if hasattr(runtime_context, "dashboard_url"):
                return runtime_context.dashboard_url

            # Fallback to default port
            return "http://127.0.0.1:8265"

        except Exception:
            return None

    def _get_cluster_nodes(self) -> List[Dict[str, Any]]:
        """Get information about cluster nodes."""
        try:
            if not self._is_ray_ready():
                return []

            nodes = self._ray.nodes()
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

    def _get_cluster_resources(self) -> Dict[str, Any]:
        """Get cluster resource information."""
        try:
            if not self._is_ray_ready():
                return {}

            cluster_resources = self._ray.cluster_resources()
            available_resources = self._ray.available_resources()

            return {
                "total": cluster_resources,
                "available": available_resources,
            }

        except Exception:
            return {}
