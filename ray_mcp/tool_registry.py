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
            name="init_ray",
            description="Initialize Ray cluster - start a new cluster or connect to existing one. If address is provided, connects to existing cluster; otherwise starts a new cluster with optional worker specifications.",
            schema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Ray cluster address to connect to (e.g., 'ray://127.0.0.1:10001'). If provided, connects to existing cluster; if not provided, starts a new cluster.",
                    },
                    "num_cpus": {
                        "type": "integer",
                        "minimum": 1,
                        "default": 1,
                        "description": "Number of CPUs for head node (only used when starting new cluster)",
                    },
                    "num_gpus": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Number of GPUs for head node (only used when starting new cluster)",
                    },
                    "object_store_memory": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Object store memory in bytes for head node (only used when starting new cluster)",
                    },
                    "worker_nodes": {
                        "type": "array",
                        "description": "Configuration for worker nodes to start (only used when starting new cluster)",
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
                        "description": "Port for head node (only used when starting new cluster, if None, a free port will be found)",
                    },
                    "dashboard_port": {
                        "type": ["integer", "null"],
                        "minimum": 1000,
                        "maximum": 65535,
                        "description": "Port for Ray dashboard (only used when starting new cluster, if None, a free port will be found)",
                    },
                    "head_node_host": {
                        "type": "string",
                        "default": "127.0.0.1",
                        "description": "Host address for head node (only used when starting new cluster)",
                    },
                },
            },
            handler=self._init_ray_handler,
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
            name="inspect_job",
            description="Inspect a job with different modes: 'status' (basic info), 'logs' (with logs), or 'debug' (comprehensive debugging info)",
            schema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "Job ID to inspect"},
                    "mode": {
                        "type": "string",
                        "enum": ["status", "logs", "debug"],
                        "default": "status",
                        "description": "Inspection mode: 'status' for basic job info, 'logs' to include job logs, 'debug' for comprehensive debugging information",
                    },
                },
                "required": ["job_id"],
            },
            handler=self._inspect_job_handler,
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
            name="retrieve_logs",
            description="Retrieve logs from Ray cluster for jobs, actors, or nodes with comprehensive error analysis",
            schema={
                "type": "object",
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "Job ID, actor ID/name, or node ID to get logs for (required)",
                    },
                    "log_type": {
                        "type": "string",
                        "enum": ["job", "actor", "node"],
                        "default": "job",
                        "description": "Type of logs to retrieve: 'job' for job logs, 'actor' for actor logs, 'node' for node logs",
                    },
                    "num_lines": {
                        "type": "integer",
                        "default": 100,
                        "description": "Number of log lines to retrieve (0 for all lines)",
                    },
                    "include_errors": {
                        "type": "boolean",
                        "default": False,
                        "description": "Whether to include error analysis for job logs",
                    },
                },
                "required": ["identifier"],
            },
            handler=self._retrieve_logs_handler,
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

    async def _init_ray_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for init_ray tool."""
        return await self.ray_manager.init_cluster(**kwargs)

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

    async def _inspect_job_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for inspect_job tool."""
        return await self.ray_manager.inspect_job(
            kwargs["job_id"], kwargs.get("mode", "status")
        )

    async def _cancel_job_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for cancel_job tool."""
        return await self.ray_manager.cancel_job(kwargs["job_id"])

    async def _retrieve_logs_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for retrieve_logs tool."""
        return await self.ray_manager.retrieve_logs(**kwargs)

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
