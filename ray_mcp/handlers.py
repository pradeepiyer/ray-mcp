"""Clean operation handlers for Ray MCP server."""

import json
from typing import Any, Dict, List, Optional

from mcp.types import TextContent
from .managers.unified_manager import RayUnifiedManager


class RayHandlers:
    """Clean handlers for Ray operations."""

    def __init__(self, unified_manager: RayUnifiedManager):
        self.unified_manager = unified_manager

    async def handle_cluster(self, prompt: str) -> Dict[str, Any]:
        """Handle cluster operations using pure prompt-driven interface."""
        return await self.unified_manager.handle_cluster_request(prompt)

    async def handle_job(self, prompt: str) -> Dict[str, Any]:
        """Handle job operations using pure prompt-driven interface."""
        return await self.unified_manager.handle_job_request(prompt)

    async def handle_cloud(self, prompt: str) -> Dict[str, Any]:
        """Handle cloud operations using pure prompt-driven interface."""
        return await self.unified_manager.handle_cloud_request(prompt)

    async def handle_tool_call(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> List[TextContent]:
        """Handle MCP tool calls and return formatted responses."""
        try:
            # Validate arguments
            if arguments is None:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "status": "error",
                        "message": "Arguments required"
                    })
                )]
            
            # Extract prompt
            if "prompt" not in arguments:
                return [TextContent(
                    type="text", 
                    text=json.dumps({
                        "status": "error",
                        "message": "Prompt required"
                    })
                )]
            
            prompt = arguments["prompt"]
            
            # Route to appropriate handler
            if name == "ray_cluster":
                result = await self.handle_cluster(prompt)
            elif name == "ray_job":
                result = await self.handle_job(prompt)
            elif name == "cloud":
                result = await self.handle_cloud(prompt)
            else:
                result = {
                    "status": "error",
                    "message": f"Unknown tool: {name}"
                }
            
            # Return formatted response
            return [TextContent(
                type="text",
                text=json.dumps(result)
            )]
            
        except Exception as e:
            # Handle any unexpected errors
            return [TextContent(
                type="text",
                text=json.dumps({
                    "status": "error", 
                    "message": f"Handler error: {str(e)}"
                })
            )]
