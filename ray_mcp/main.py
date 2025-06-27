#!/usr/bin/env python3
"""Main entry point for the Ray MCP server."""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

# Import MCP types
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import ServerCapabilities, TextContent, Tool

# Import Ray modules with proper error handling
try:
    import ray
    from ray import job_submission

    RAY_AVAILABLE = True
except ImportError:
    RAY_AVAILABLE = False
    ray = None
    job_submission = None

from .ray_manager import RayManager
from .tool_registry import ToolRegistry

# Initialize server and ray manager
server = Server("ray-mcp")
ray_manager = RayManager()
tool_registry = ToolRegistry(ray_manager)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available Ray tools with their schemas and descriptions.

    Returns a comprehensive list of all available Ray cluster management tools
    that can be called by LLM agents. Each tool includes detailed input schemas
    with parameter descriptions, types, and validation rules.

    Returns:
        List[Tool]: List of Tool objects containing:
            - name: Tool identifier (e.g., "start_ray", "submit_job")
            - description: Human-readable description of tool functionality
            - inputSchema: JSON schema defining required and optional parameters
                with types, constraints, and descriptions for each parameter

    The tools are organized into categories:
    - Basic cluster management: start_ray, connect_ray, stop_ray, cluster_info
    - Job management: submit_job, list_jobs, job_status, cancel_job, monitor_job, debug_job
    - Actor management: list_actors, kill_actor
    - Enhanced monitoring: performance_metrics, health_check, optimize_config
    - Logs & debugging: get_logs

    Failure modes:
        - No tools available: Returns empty list (should not occur in normal operation)
        - Schema generation errors: Returns tools with basic schemas
    """
    return tool_registry.get_tool_list()


# Dispatcher for all tool calls
@server.call_tool()
async def dispatch_tool_call(
    name: str, arguments: Optional[dict] = None
) -> List[TextContent]:
    """Dispatch tool call to the correct tool handler by name."""
    result = await tool_registry.execute_tool(name, arguments)
    if "enhanced_output" in result:
        return [TextContent(type="text", text=result["enhanced_output"])]
    else:
        return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def main():
    """Main entry point for the Ray MCP server."""
    if not RAY_AVAILABLE:
        logger.warning(
            "Ray is not available. The MCP server will start but Ray operations will fail."
        )

    # Start the server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="ray-mcp",
                server_version="1.0.0",
                capabilities=ServerCapabilities(),
            ),
        )


def run_server():
    """Run the Ray MCP server."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_server()
