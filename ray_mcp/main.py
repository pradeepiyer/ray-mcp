"""Ray MCP Server - Clean 4-tool natural language interface."""

import asyncio
import json
import logging
import sys
from typing import Optional

from mcp import stdio_server
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import ServerCapabilities, TextContent, Tool

from . import __version__
from .cloud.cloud_provider_manager import CloudProviderManager
from .core_utils import LoggingUtility, error_response
from .kuberay.job_manager import JobManager
from .kuberay.service_manager import ServiceManager
from .llm_parser import get_parser
from .tools import get_ray_tools

# Kubernetes-only Ray MCP server

# Initialize server and components
server = Server("ray-mcp")
job_manager = JobManager()
service_manager = ServiceManager()
cloud_provider_manager = CloudProviderManager()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return the unified Ray tool with natural language interface."""
    return get_ray_tools()


@server.call_tool()
async def call_tool(name: str, arguments: Optional[dict] = None) -> list[TextContent]:
    """Handle tool calls with LLM-based routing from natural language prompts."""
    if not arguments or "prompt" not in arguments:
        return [
            TextContent(
                type="text", text='{"status": "error", "message": "prompt required"}'
            )
        ]

    prompt = arguments["prompt"]

    try:
        if name != "ray":
            result = error_response(f"Unknown tool: {name}")
        else:
            # Use LLM to parse the prompt and determine routing
            action = await get_parser().parse_action(prompt)
            action_type = action.get("type")

            if action_type == "job":
                result = await job_manager.execute_request(action)
            elif action_type == "service":
                result = await service_manager.execute_request(action)
            elif action_type == "cloud":
                result = await cloud_provider_manager.execute_request(action)
            else:
                result = error_response(
                    f"Unable to determine operation type from prompt: {prompt}"
                )

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        error_result = error_response(str(e))
        return [TextContent(type="text", text=json.dumps(error_result, indent=2))]


async def main():
    """Run the Ray MCP server."""
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="ray-mcp",
                    server_version=__version__,
                    capabilities=ServerCapabilities(),
                ),
            )
    finally:
        # Clean up global OpenAI client to prevent TaskGroup errors
        from .llm_parser import reset_global_parser

        await reset_global_parser()


def run_server():
    """Entry point for the Ray MCP server."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        LoggingUtility.log_info("server", "Server stopped by user")
    except Exception as e:
        LoggingUtility.log_error("server", e)
        sys.exit(1)


if __name__ == "__main__":
    run_server()
