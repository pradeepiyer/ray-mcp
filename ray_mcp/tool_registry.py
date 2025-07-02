"""Tool registry for Ray MCP server.

This module centralizes all tool definitions, schemas, and implementations to eliminate
duplication and provide a single source of truth for tool metadata.
"""

import inspect
import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional, Union

from mcp.types import Tool

from .core.unified_manager import RayUnifiedManager

logger = logging.getLogger(__name__)
from .logging_utils import LoggingUtility, ResponseFormatter


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
            name="init_ray",
            description="Initialize Ray cluster - start a new cluster or connect to existing one. If address is provided, connects to existing cluster; otherwise starts a new cluster. IMPORTANT: For head-node-only clusters (no worker nodes), explicitly pass worker_nodes=[] (empty array). For default behavior (2 workers), omit worker_nodes parameter. For custom workers, specify worker configurations. All cluster management is done through the dashboard API.",
            schema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Ray cluster address to connect to (e.g., '127.0.0.1:10001'). If provided, connects to existing cluster via dashboard API; if not provided, starts a new cluster. Connection uses dashboard API (port 8265) for all cluster operations.",
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
            name="inspect_ray",
            description="Get comprehensive cluster information including status, resources, and nodes",
            schema={"type": "object", "properties": {}},
            handler=self._inspect_ray_handler,
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
            description="Retrieve job logs from Ray cluster with optional pagination, comprehensive error analysis and memory protection",
            schema={
                "type": "object",
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "Job ID to get logs for (required)",
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
                        "description": "Number of log lines to retrieve (0 for all lines, max 10000). Ignored if page is specified",
                    },
                    "include_errors": {
                        "type": "boolean",
                        "default": False,
                        "description": "Whether to include error analysis for job logs",
                    },
                    "max_size_mb": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 10,
                        "description": "Maximum size of logs in MB (1-100, default 10) to prevent memory exhaustion",
                    },
                    "page": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Page number (1-based) for paginated log retrieval. If specified, enables pagination mode",
                    },
                    "page_size": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 1000,
                        "default": 100,
                        "description": "Number of lines per page (1-1000). Only used when page is specified",
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

    async def _inspect_ray_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for inspect_ray tool."""
        return await self.ray_manager.inspect_ray()

    async def _submit_job_handler(self, **kwargs) -> Dict[str, Any]:
        """Handler for submit_job tool."""
        sig = inspect.signature(self.ray_manager.submit_job)
        # Exclude 'self' parameter from filtering since it's not in kwargs
        valid_params = {k for k in sig.parameters.keys() if k != "self"}
        filtered = {k: v for k, v in kwargs.items() if k in valid_params}
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
