"""Ray MCP Server - Clean 3-tool natural language interface."""

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
from .foundation.import_utils import RAY_AVAILABLE
from .foundation.logging_utils import LoggingUtility
from .handlers import RayHandlers
from .managers.unified_manager import RayUnifiedManager
from .tools import get_ray_tools

# Check Ray availability
# RAY_AVAILABLE is imported from import_utils

# Initialize server and components
server = Server("ray-mcp")
ray_manager = RayUnifiedManager()
handlers = RayHandlers(ray_manager)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return the 3 Ray tools with natural language interfaces."""
    return get_ray_tools()


@server.call_tool()
async def call_tool(name: str, arguments: Optional[dict] = None) -> list[TextContent]:
    """Handle tool calls with natural language prompts."""
    if not arguments or "prompt" not in arguments:
        return [
            TextContent(
                type="text", text='{"status": "error", "message": "prompt required"}'
            )
        ]

    prompt = arguments["prompt"]

    try:
        if name == "ray_cluster":
            result = await handlers.handle_cluster(prompt)
        elif name == "ray_job":
            result = await handlers.handle_job(prompt)
        elif name == "cloud":
            result = await handlers.handle_cloud(prompt)
        else:
            result = {"status": "error", "message": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        error_result = {"status": "error", "message": str(e)}
        return [TextContent(type="text", text=json.dumps(error_result, indent=2))]


async def main():
    """Run the Ray MCP server."""
    if not RAY_AVAILABLE:
        LoggingUtility.log_warning(
            "server",
            "Ray is not available. The MCP server will start but Ray operations will fail.",
        )

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
