"""Clean operation handlers for Ray MCP server."""

from typing import Any, Dict

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
