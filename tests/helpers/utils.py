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

from ray_mcp.handlers import RayHandlers
from ray_mcp.managers.unified_manager import RayUnifiedManager


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
    if tool_name == "ray_cluster":
        prompt = arguments.get("prompt", "list clusters")
        result = await handlers.handle_cluster(prompt)
    elif tool_name == "ray_job":
        prompt = arguments.get("prompt", "list jobs")
        result = await handlers.handle_job(prompt)
    elif tool_name == "cloud":
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
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=self.suffix, delete=False
        ) as f:
            f.write(self.script_content)
            self.script_path = f.name
        return self.script_path

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up temporary script."""
        if self.script_path and os.path.exists(self.script_path):
            os.unlink(self.script_path)


# Common test scripts
class TestScripts:
    """Collection of common test scripts for e2e tests."""

    QUICK_SUCCESS = """
import ray
import time

@ray.remote
def quick_task(n):
    return n * n

# Run a simple task
result = ray.get(quick_task.remote(5))
print(f"Task result: {result}")
print("Job completed successfully!")
"""

    INTENTIONAL_FAILURE = """
import sys
print("This job will fail intentionally")
sys.exit(1)  # Intentional failure
"""

    LIGHTWEIGHT_SUCCESS = """
import ray

@ray.remote
def quick_success_task():
    return "Success!"

result = ray.get(quick_success_task.remote())
print(f"Success job result: {result}")
print("Success job completed!")
"""


def run_ray_cleanup(verbose: bool = True) -> bool:
    """
    Run the ray_cleanup.sh script.

    Args:
        verbose: Whether to print cleanup messages

    Returns:
        True if cleanup was successful, False otherwise
    """
    cleanup_script = Path(__file__).parent.parent.parent / "scripts" / "ray_cleanup.sh"

    if not cleanup_script.exists():
        if verbose:
            print("⚠️  Ray cleanup script not found")
        return False

    try:
        if verbose:
            print("🧹 Running ray_cleanup.sh...")

        result = subprocess.run(
            [str(cleanup_script)], check=True, capture_output=True, text=True
        )

        if verbose:
            print("✅ Ray cleanup completed successfully")
            if result.stdout:
                print(f"Cleanup output: {result.stdout}")

        return True

    except subprocess.CalledProcessError as e:
        if verbose:
            print(f"⚠️  Ray cleanup failed: {e}")
            if e.stdout:
                print(f"stdout: {e.stdout}")
            if e.stderr:
                print(f"stderr: {e.stderr}")
        return False


def wait_for_ray_shutdown(timeout: int = 30) -> bool:
    """
    Wait for Ray to fully shutdown.

    Args:
        timeout: Maximum time to wait in seconds

    Returns:
        True if Ray shutdown successfully, False if timeout
    """
    try:
        import ray
    except ImportError:
        # Ray not available, consider it shutdown
        return True

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            if not ray.is_initialized():
                return True
            time.sleep(1)
        except Exception:
            # Ray might be in an inconsistent state, continue waiting
            time.sleep(1)

    return False
