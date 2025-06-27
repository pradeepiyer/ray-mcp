"""Tool registry for Ray MCP server.

This module centralizes all tool definitions, schemas, and implementations to eliminate
duplication and provide a single source of truth for tool metadata.
"""

import inspect
import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional, Union
from unittest.mock import AsyncMock, Mock

from mcp.types import Tool

from .ray_manager import RayManager

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for all Ray MCP tools with centralized metadata and implementations."""

    def __init__(self, ray_manager: RayManager):
        self.ray_manager = ray_manager
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._register_all_tools()

    def _register_all_tools(self) -> None:
        """Register all available tools with their schemas and implementations."""

        # Basic cluster management
        self._register_tool(
            name="start_ray",
            description="Start a new Ray cluster with head node and worker nodes (defaults to multi-node with 2 workers)",
            schema={
                "type": "object",
                "properties": {
                    "num_cpus": {
                        "type": "integer",
                        "minimum": 1,
                        "default": 1,
                        "description": "Number of CPUs for head node",
                    },
                    "num_gpus": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Number of GPUs for head node",
                    },
                    "object_store_memory": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Object store memory in bytes for head node",
                    },
                    "worker_nodes": {
                        "type": "array",
                        "description": "Configuration for worker nodes to start",
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
                            },
                            "required": ["num_cpus"],
                        },
                    },
                    "head_node_port": {
                        "type": ["integer", "null"],
                        "minimum": 10000,
                        "maximum": 65535,
                        "description": "Port for head node (if None, a free port will be found)",
                    },
                    "dashboard_port": {
                        "type": ["integer", "null"],
                        "minimum": 1000,
                        "maximum": 65535,
                        "description": "Port for Ray dashboard (if None, a free port will be found)",
                    },
                    "head_node_host": {
                        "type": "string",
                        "default": "127.0.0.1",
                        "description": "Host address for head node",
                    },
                },
            },
            handler=self._start_ray_handler,
        )

        self._register_tool(
            name="connect_ray",
            description="Connect to an existing Ray cluster",
            schema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Ray cluster address (e.g., 'ray://127.0.0.1:10001' or '127.0.0.1:10001')",
                    }
                },
                "required": ["address"],
            },
            handler=self._connect_ray_handler,
        )

        self._register_tool(
            name="stop_ray",
            description="Stop the Ray cluster",
            schema={"type": "object", "properties": {}},
            handler=self._stop_ray_handler,
        )

        self._register_tool(
            name="cluster_info",
            description="Get comprehensive cluster information including status, resources, nodes, worker status, performance metrics, health check, and optimization recommendations",
            schema={"type": "object", "properties": {}},
            handler=self._cluster_info_handler,
        )

        # Job management
        self._register_tool(
            name="submit_job",
            description="Submit a job to the Ray cluster",
            schema={
                "type": "object",
                "properties": {
                    "entrypoint": {"type": "string"},
                    "runtime_env": {"type": "object"},
                    "job_id": {"type": "string"},
                    "metadata": {"type": "object"},
                },
                "required": ["entrypoint"],
            },
            handler=self._submit_job_handler,
        )

        self._register_tool(
            name="list_jobs",
            description="List all jobs in the Ray cluster",
            schema={"type": "object", "properties": {}},
            handler=self._list_jobs_handler,
        )

        self._register_tool(
            name="job_status",
            description="Get the status of a specific job",
            schema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "Job ID to check"}
                },
                "required": ["job_id"],
            },
            handler=self._job_status_handler,
        )

        self._register_tool(
            name="cancel_job",
            description="Cancel a running job",
            schema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "Job ID to cancel"}
                },
                "required": ["job_id"],
            },
            handler=self._cancel_job_handler,
        )

        self._register_tool(
            name="monitor_job",
            description="Monitor the progress of a specific job",
            schema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "Job ID to monitor"}
                },
                "required": ["job_id"],
            },
            handler=self._monitor_job_handler,
        )

        self._register_tool(
            name="debug_job",
            description="Debug a job by analyzing its logs and status",
            schema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "Job ID to debug"}
                },
                "required": ["job_id"],
            },
            handler=self._debug_job_handler,
        )

        # Actor management
        self._register_tool(
            name="list_actors",
            description="List all actors in the Ray cluster",
            schema={
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Optional filters to apply to actor list",
                    }
                },
            },
            handler=self._list_actors_handler,
        )

        self._register_tool(
            name="kill_actor",
            description="Kill a specific actor",
            schema={
                "type": "object",
                "properties": {
                    "actor_id": {"type": "string", "description": "Actor ID to kill"},
                    "no_restart": {
                        "type": "boolean",
                        "default": False,
                        "description": "Whether to prevent actor restart",
                    },
                },
                "required": ["actor_id"],
            },
            handler=self._kill_actor_handler,
        )

        # Enhanced monitoring
        self._register_tool(
            name="cluster_info",
            description="Get comprehensive cluster information including status, resources, nodes, worker status, performance metrics, health check, and optimization recommendations",
            schema={"type": "object", "properties": {}},
            handler=self._cluster_info_handler,
        )

        # Logs & debugging
        self._register_tool(
            name="get_logs",
            description="Get logs from a specific job",
            schema={
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "Job ID to get logs for (required)",
                    },
                    "num_lines": {
                        "type": "integer",
                        "default": 100,
                        "description": "Number of log lines to retrieve",
                    },
                },
                "required": ["job_id"],
            },
            handler=self._get_logs_handler,
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

    async def _start_ray_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for start_ray tool."""
        sig = inspect.signature(RayManager.start_cluster)
        filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
        return await self.ray_manager.start_cluster(**filtered)

    async def _connect_ray_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for connect_ray tool."""
        return await self.ray_manager.connect_cluster(**kwargs)

    async def _stop_ray_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for stop_ray tool."""
        return await self.ray_manager.stop_cluster()

    async def _cluster_info_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for cluster_info tool."""
        return await self.ray_manager.get_cluster_info()

    async def _submit_job_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for submit_job tool."""
        sig = inspect.signature(RayManager.submit_job)
        filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
        return await self.ray_manager.submit_job(**filtered)

    async def _list_jobs_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for list_jobs tool."""
        return await self.ray_manager.list_jobs()

    async def _job_status_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for job_status tool."""
        return await self.ray_manager.get_job_status(kwargs["job_id"])

    async def _cancel_job_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for cancel_job tool."""
        return await self.ray_manager.cancel_job(kwargs["job_id"])

    async def _monitor_job_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for monitor_job tool."""
        return await self.ray_manager.monitor_job_progress(kwargs["job_id"])

    async def _debug_job_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for debug_job tool."""
        return await self.ray_manager.debug_job(kwargs["job_id"])

    async def _list_actors_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for list_actors tool."""
        return await self.ray_manager.list_actors(kwargs.get("filters"))

    async def _kill_actor_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for kill_actor tool."""
        sig = inspect.signature(RayManager.kill_actor)
        # Apply default values from the method signature
        bound_args = sig.bind_partial(**kwargs)
        bound_args.apply_defaults()
        return await self.ray_manager.kill_actor(**bound_args.arguments)

    async def _get_logs_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for get_logs tool."""
        sig = inspect.signature(RayManager.get_logs)
        # Apply default values from the method signature
        bound_args = sig.bind_partial(**kwargs)
        bound_args.apply_defaults()
        return await self.ray_manager.get_logs(**bound_args.arguments)

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

    async def execute_tool(
        self, name: str, arguments: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a tool by name with the given arguments."""
        handler = self.get_tool_handler(name)
        if not handler:
            return {"status": "error", "message": f"Unknown tool: {name}"}

        try:
            args = arguments or {}
            result = await handler(**args)

            # Check if enhanced output is enabled
            use_enhanced_output = (
                os.getenv("RAY_MCP_ENHANCED_OUTPUT", "false").lower() == "true"
            )

            if use_enhanced_output:
                enhanced_response = self._wrap_with_system_prompt(name, result)
                return {
                    "status": "success",
                    "enhanced_output": enhanced_response,
                    "raw_result": result,
                }
            else:
                return result

        except Exception as e:
            logger.error(f"Error executing {name}: {e}")
            error_result = {
                "status": "error",
                "message": f"Error executing {name}: {str(e)}",
            }

            # Check if enhanced output is enabled
            use_enhanced_output = (
                os.getenv("RAY_MCP_ENHANCED_OUTPUT", "false").lower() == "true"
            )

            if use_enhanced_output:
                enhanced_error_response = self._wrap_with_system_prompt(
                    name, error_result
                )
                return {
                    "status": "error",
                    "enhanced_output": enhanced_error_response,
                    "raw_result": error_result,
                }
            else:
                return error_result
