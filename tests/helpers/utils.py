"""Test utilities for Ray MCP tests."""

import asyncio
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any, Dict, List, Optional

from mcp.types import TextContent


# E2E Test Environment Configuration
class E2EConfig:
    """Configuration for e2e tests with CI/local environment handling."""

    # Check if running in CI environment
    IN_CI = os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI") == "true"

    # CI-specific resource constraints
    CI_CPU_LIMIT = 1
    CI_WAIT_TIME = 10
    LOCAL_CPU_LIMIT = 2
    LOCAL_WAIT_TIME = 30

    @classmethod
    def get_cpu_limit(cls) -> int:
        """Get appropriate CPU limit for current environment."""
        return cls.CI_CPU_LIMIT if cls.IN_CI else cls.LOCAL_CPU_LIMIT

    @classmethod
    def get_wait_time(cls) -> int:
        """Get appropriate wait time for current environment."""
        return cls.CI_WAIT_TIME if cls.IN_CI else cls.LOCAL_WAIT_TIME

    @classmethod
    def get_worker_nodes(cls) -> Optional[List]:
        """Get appropriate worker nodes config for current environment."""
        # In CI, use empty worker_nodes list to start only head node
        # In local, use None to get default worker nodes for better testing
        return [] if cls.IN_CI else None


def get_text_content(result: List[TextContent]) -> str:
    """Helper function to extract text content from MCP result."""
    content = list(result)[0]
    assert isinstance(content, TextContent)
    return content.text


async def call_tool(
    tool_name: str, arguments: Optional[Dict[str, Any]] = None
) -> List[TextContent]:
    """Helper function to call tools using the ToolRegistry architecture."""
    # Use the same RayManager instance that the MCP tools use
    from ray_mcp.main import handlers

    # Convert tool name and arguments to prompt format
    if tool_name == "ray_job":
        prompt = arguments.get("prompt", "list jobs")
        result = await handlers.handle_job(prompt)
    elif tool_name == "ray_service":
        prompt = arguments.get("prompt", "list services")
        result = await handlers.handle_service(prompt)
    elif tool_name == "ray_cloud":
        prompt = arguments.get("prompt", "check environment")
        result = await handlers.handle_cloud(prompt)
    else:
        result = {"status": "error", "message": f"Unknown tool: {tool_name}"}

    # Convert the result to the expected MCP format
    result_text = json.dumps(result, indent=2)
    return [TextContent(type="text", text=result_text)]


def parse_tool_result(result: List[TextContent]) -> Dict[str, Any]:
    """Parse tool result and return as dictionary."""
    content = get_text_content(result)
    return json.loads(content)


class TempScriptManager:
    """Context manager for creating and cleaning up temporary Python scripts."""

    def __init__(self, script_content: str, suffix: str = ".py"):
        self.script_content = script_content
        self.suffix = suffix
        self.script_path = None

    def __enter__(self) -> str:
        """Create temporary script and return path."""
        # Add shebang line if it's not already present
        if not self.script_content.startswith("#!"):
            script_with_shebang = "#!/usr/bin/env python3\n" + self.script_content
        else:
            script_with_shebang = self.script_content

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=self.suffix, delete=False
        ) as f:
            f.write(script_with_shebang)
            self.script_path = f.name

        # Make the script executable
        os.chmod(self.script_path, 0o755)

        return self.script_path

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up temporary script."""
        if self.script_path and os.path.exists(self.script_path):
            os.unlink(self.script_path)


