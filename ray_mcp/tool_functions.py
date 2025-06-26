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
    async def start_ray(
        num_cpus: Optional[int] = 1,
        num_gpus: Optional[int] = None,
        object_store_memory: Optional[int] = None,
        worker_nodes: Optional[List[Dict[str, Any]]] = None,
        head_node_port: int = 10001,
        dashboard_port: int = 8265,
        head_node_host: str = "127.0.0.1",
        address: Optional[str] = None,
    ) -> List[TextContent]:
        """Start a new Ray cluster with head node and worker nodes."""
        result = await tool_registry.execute_tool(
            "start_ray",
            {
                "num_cpus": num_cpus,
                "num_gpus": num_gpus,
                "object_store_memory": object_store_memory,
                "worker_nodes": worker_nodes,
                "head_node_port": head_node_port,
                "dashboard_port": dashboard_port,
                "head_node_host": head_node_host,
                "address": address,
            },
        )
        return _format_response(result)

    @server.call_tool()
    async def connect_ray(address: str) -> List[TextContent]:
        """Connect to an existing Ray cluster."""
        result = await tool_registry.execute_tool("connect_ray", {"address": address})
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
    async def job_status(job_id: str) -> List[TextContent]:
        """Get the status of a specific job."""
        result = await tool_registry.execute_tool("job_status", {"job_id": job_id})
        return _format_response(result)

    @server.call_tool()
    async def cancel_job(job_id: str) -> List[TextContent]:
        """Cancel a running job."""
        result = await tool_registry.execute_tool("cancel_job", {"job_id": job_id})
        return _format_response(result)

    @server.call_tool()
    async def monitor_job(job_id: str) -> List[TextContent]:
        """Monitor the progress of a specific job."""
        result = await tool_registry.execute_tool("monitor_job", {"job_id": job_id})
        return _format_response(result)

    @server.call_tool()
    async def debug_job(job_id: str) -> List[TextContent]:
        """Debug a job by analyzing its logs and status."""
        result = await tool_registry.execute_tool("debug_job", {"job_id": job_id})
        return _format_response(result)

    # Actor management tools
    @server.call_tool()
    async def list_actors(
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[TextContent]:
        """List all actors in the Ray cluster."""
        result = await tool_registry.execute_tool("list_actors", {"filters": filters})
        return _format_response(result)

    @server.call_tool()
    async def kill_actor(actor_id: str, no_restart: bool = False) -> List[TextContent]:
        """Kill a specific actor."""
        result = await tool_registry.execute_tool(
            "kill_actor", {"actor_id": actor_id, "no_restart": no_restart}
        )
        return _format_response(result)

    # Enhanced monitoring tools
    @server.call_tool()
    async def performance_metrics() -> List[TextContent]:
        """Get performance metrics for the Ray cluster."""
        result = await tool_registry.execute_tool("performance_metrics", {})
        return _format_response(result)

    @server.call_tool()
    async def health_check() -> List[TextContent]:
        """Perform a comprehensive health check of the Ray cluster."""
        result = await tool_registry.execute_tool("health_check", {})
        return _format_response(result)

    @server.call_tool()
    async def optimize_config() -> List[TextContent]:
        """Analyze and suggest optimizations for the Ray cluster configuration."""
        result = await tool_registry.execute_tool("optimize_config", {})
        return _format_response(result)

    # Logs & debugging tools
    @server.call_tool()
    async def get_logs(
        job_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        node_id: Optional[str] = None,
        num_lines: int = 100,
    ) -> List[TextContent]:
        """Get logs from jobs, actors, or nodes."""
        result = await tool_registry.execute_tool(
            "get_logs",
            {
                "job_id": job_id,
                "actor_id": actor_id,
                "node_id": node_id,
                "num_lines": num_lines,
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
