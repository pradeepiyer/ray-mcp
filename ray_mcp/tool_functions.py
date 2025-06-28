"""Individual tool functions for Ray MCP server.

This module provides individual tool functions decorated with @server.call_tool()
to follow MCP best practices. Each function is properly typed and can be discovered
automatically by MCP clients.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from mcp.types import TextContent

from .tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


def create_tool_functions(server, tool_registry: ToolRegistry):
    """Create and register individual tool functions with the MCP server.

    This function dynamically creates individual @server.call_tool() decorated
    functions for each tool in the registry, following MCP best practices.
    """

    # Basic cluster management tools
    @server.call_tool()
    async def init_ray(
        address: Optional[str] = None,
        num_cpus: Optional[int] = 1,
        num_gpus: Optional[int] = None,
        object_store_memory: Optional[int] = None,
        worker_nodes: Optional[List[Dict[str, Any]]] = None,
        head_node_port: Optional[int] = None,
        dashboard_port: Optional[int] = None,
        head_node_host: str = "127.0.0.1",
    ) -> List[TextContent]:
        """Initialize Ray cluster - start a new cluster or connect to existing one. If address is provided, connects to existing cluster; otherwise starts a new cluster with optional worker specifications."""
        result = await tool_registry.execute_tool(
            "init_ray",
            {
                "address": address,
                "num_cpus": num_cpus,
                "num_gpus": num_gpus,
                "object_store_memory": object_store_memory,
                "worker_nodes": worker_nodes,
                "head_node_port": head_node_port,
                "dashboard_port": dashboard_port,
                "head_node_host": head_node_host,
            },
        )
        return _format_response(result)

    @server.call_tool()
    async def stop_ray() -> List[TextContent]:
        """Stop the Ray cluster."""
        result = await tool_registry.execute_tool("stop_ray", {})
        return _format_response(result)

    @server.call_tool()
    async def cluster_info() -> List[TextContent]:
        """Get comprehensive cluster information including status, resources, nodes, and worker status."""
        result = await tool_registry.execute_tool("cluster_info", {})
        return _format_response(result)

    # Job management tools
    @server.call_tool()
    async def submit_job(
        entrypoint: str,
        runtime_env: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> List[TextContent]:
        """Submit a job to the Ray cluster."""
        result = await tool_registry.execute_tool(
            "submit_job",
            {
                "entrypoint": entrypoint,
                "runtime_env": runtime_env,
                "job_id": job_id,
                "metadata": metadata,
            },
        )
        return _format_response(result)

    @server.call_tool()
    async def list_jobs() -> List[TextContent]:
        """List all jobs in the Ray cluster."""
        result = await tool_registry.execute_tool("list_jobs", {})
        return _format_response(result)

    @server.call_tool()
    async def inspect_job(job_id: str, mode: str = "status") -> List[TextContent]:
        """Inspect a job with different modes: 'status' (basic info), 'logs' (with logs), or 'debug' (comprehensive debugging info)."""
        result = await tool_registry.execute_tool(
            "inspect_job", {"job_id": job_id, "mode": mode}
        )
        return _format_response(result)

    @server.call_tool()
    async def cancel_job(job_id: str) -> List[TextContent]:
        """Cancel a running job."""
        result = await tool_registry.execute_tool("cancel_job", {"job_id": job_id})
        return _format_response(result)

    # Enhanced monitoring tools
    @server.call_tool()
    async def retrieve_logs(
        identifier: str,
        log_type: str = "job",
        num_lines: int = 100,
        include_errors: bool = False,
    ) -> List[TextContent]:
        """Retrieve logs from Ray cluster for jobs, actors, or nodes with comprehensive error analysis."""
        result = await tool_registry.execute_tool(
            "retrieve_logs",
            {
                "identifier": identifier,
                "log_type": log_type,
                "num_lines": num_lines,
                "include_errors": include_errors,
            },
        )
        return _format_response(result)


def _format_response(result: Dict[str, Any]) -> List[TextContent]:
    """Format the tool execution result as TextContent for MCP response."""
    if "enhanced_output" in result:
        # Enhanced output mode
        return [TextContent(type="text", text=result["enhanced_output"])]
    else:
        # Standard output mode
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
