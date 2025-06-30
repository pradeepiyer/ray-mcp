"""Pytest configuration and fixtures for Ray MCP tests."""

import asyncio
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, patch

from mcp.types import TextContent
import pytest

from ray_mcp.tool_registry import ToolRegistry


def pytest_configure(config):
    """Configure pytest with custom markers."""
    # Disable Ray usage reporting to avoid network calls during tests
    os.environ.setdefault("RAY_USAGE_STATS_ENABLED", "0")
    config.addinivalue_line("markers", "e2e: mark test as end-to-end integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "fast: mark test as fast running")
    config.addinivalue_line("markers", "smoke: mark test as smoke test")


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
    from ray_mcp.main import ray_manager

    registry = ToolRegistry(ray_manager)

    # Execute the tool
    result = await registry.execute_tool(tool_name, arguments or {})

    # Convert the result to the expected MCP format
    result_text = json.dumps(result, indent=2)
    return [TextContent(type="text", text=result_text)]


def parse_tool_result(result: List[TextContent]) -> Dict[str, Any]:
    """Parse tool result and return as dictionary."""
    content = get_text_content(result)
    return json.loads(content)


async def wait_for_job_completion(
    job_id: str, 
    max_wait: Optional[int] = None,
    expected_status: str = "SUCCEEDED"
) -> Dict[str, Any]:
    """
    Wait for a job to reach completion status.
    
    Args:
        job_id: The job ID to monitor
        max_wait: Maximum time to wait (uses E2EConfig default if None)
        expected_status: Expected final status (SUCCEEDED, FAILED, etc.)
    
    Returns:
        Final job status data
        
    Raises:
        AssertionError: If job doesn't complete in time or reaches unexpected status
    """
    if max_wait is None:
        max_wait = E2EConfig.get_wait_time()
    
    for i in range(max_wait):
        status_result = await call_tool("inspect_job", {"job_id": job_id})
        status_data = parse_tool_result(status_result)
        job_status = status_data.get("job_status", "UNKNOWN")
        print(f"Job {job_id} status at {i+1}s: {job_status}")
        
        if job_status == expected_status:
            return status_data
        if job_status == "FAILED" and expected_status != "FAILED":
            raise AssertionError(f"Job failed unexpectedly: {status_data}")
        if job_status == "SUCCEEDED" and expected_status == "FAILED":
            raise AssertionError(f"Job succeeded when failure was expected: {status_data}")
            
        await asyncio.sleep(1)
    else:
        raise AssertionError(
            f"Job {job_id} did not reach {expected_status} within {max_wait} seconds. "
            f"Last status: {job_status}"
        )


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


async def start_ray_cluster(
    cpu_limit: Optional[int] = None,
    worker_nodes: Optional[List] = None
) -> Dict[str, Any]:
    """
    Start Ray cluster with appropriate configuration.
    
    Args:
        cpu_limit: Number of CPUs (uses E2EConfig default if None)
        worker_nodes: Worker nodes config (uses E2EConfig default if None)
    
    Returns:
        Start result data
    """
    if cpu_limit is None:
        cpu_limit = E2EConfig.get_cpu_limit()
    if worker_nodes is None:
        worker_nodes = E2EConfig.get_worker_nodes()
    
    print(f"Starting Ray cluster with {cpu_limit} CPU(s)...")
    start_result = await call_tool(
        "init_ray", {"num_cpus": cpu_limit, "worker_nodes": worker_nodes}
    )
    
    start_data = parse_tool_result(start_result)
    print(f"Start result: {start_data}")
    
    if start_data["status"] == "error":
        print("Error message:", start_data["message"])
    
    assert start_data["status"] == "success"
    assert start_data.get("result_type") == "started"
    print(f"Ray cluster started: {start_data}")
    
    return start_data


async def stop_ray_cluster() -> Dict[str, Any]:
    """
    Stop Ray cluster and verify shutdown.
    
    Returns:
        Stop result data
    """
    print("Stopping Ray cluster...")
    stop_result = await call_tool("stop_ray")
    stop_data = parse_tool_result(stop_result)
    
    assert stop_data["status"] == "success"
    assert stop_data.get("result_type") == "stopped"
    print("Ray cluster stopped successfully!")
    
    # Verify cluster is stopped
    print("Verifying cluster is stopped...")
    final_status_result = await call_tool("inspect_ray")
    final_status_data = parse_tool_result(final_status_result)
    assert final_status_data["status"] == "not_running"
    print("Cluster shutdown verification passed!")
    
    return stop_data


async def verify_cluster_status() -> Dict[str, Any]:
    """
    Verify Ray cluster is running and return status.
    
    Returns:
        Cluster status data
    """
    print("Checking cluster status...")
    status_result = await call_tool("inspect_ray")
    status_data = parse_tool_result(status_result)
    
    assert status_data["status"] == "success"
    assert status_data["cluster_overview"]["status"] == "running"
    print(f"Cluster status: {status_data}")
    
    return status_data


async def submit_and_wait_for_job(
    script_content: str,
    expected_status: str = "SUCCEEDED",
    max_wait: Optional[int] = None,
    runtime_env: Optional[Dict] = None
) -> tuple[str, Dict[str, Any]]:
    """
    Submit a job and wait for completion.
    
    Args:
        script_content: Python script content to execute
        expected_status: Expected final job status
        max_wait: Maximum time to wait for completion
        runtime_env: Optional runtime environment
    
    Returns:
        Tuple of (job_id, final_status_data)
    """
    with TempScriptManager(script_content) as script_path:
        print(f"Submitting job with script at {script_path}...")
        
        job_args = {"entrypoint": f"python {script_path}"}
        if runtime_env is not None:
            job_args["runtime_env"] = runtime_env
        
        job_result = await call_tool("submit_job", job_args)
        job_data = parse_tool_result(job_result)
        
        assert job_data["status"] == "success"
        assert job_data["result_type"] == "submitted"
        
        job_id = job_data["job_id"]
        print(f"Job submitted with ID: {job_id}")
        
        # Wait for completion
        final_status = await wait_for_job_completion(job_id, max_wait, expected_status)
        print(f"Job {job_id} completed with status: {expected_status}")
        
        return job_id, final_status


def run_ray_cleanup(verbose: bool = True) -> bool:
    """
    Run the ray_cleanup.sh script.

    Args:
        verbose: Whether to print cleanup messages

    Returns:
        True if cleanup was successful, False otherwise
    """
    cleanup_script = Path(__file__).parent.parent / "scripts" / "ray_cleanup.sh"

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


def ensure_clean_ray_state():
    """
    Ensure Ray is in a clean state by running cleanup and waiting for shutdown.
    """
    run_ray_cleanup()
    wait_for_ray_shutdown()


@pytest.fixture(scope="function", autouse=True)
def cleanup_ray_between_e2e_tests(request):
    """Automatically run ray_cleanup.sh between e2e tests."""
    # Only run cleanup for e2e tests
    if "e2e" in request.keywords:
        print(f"\n🧹 Running cleanup before e2e test: {request.node.name}")

        # Run cleanup before the test
        cleanup_success = run_ray_cleanup(verbose=True)
        if not cleanup_success:
            print("⚠️  Warning: Ray cleanup failed before test")

        # Wait for Ray to fully shutdown
        if wait_for_ray_shutdown(timeout=10):
            print("✅ Ray shutdown confirmed")
        else:
            print("⚠️  Warning: Ray may not have fully shutdown")

        yield

        print(f"\n🧹 Running cleanup after e2e test: {request.node.name}")

        # Run cleanup after the test
        cleanup_success = run_ray_cleanup(verbose=True)
        if not cleanup_success:
            print("⚠️  Warning: Ray cleanup failed after test")

        # Wait for Ray to fully shutdown
        if wait_for_ray_shutdown(timeout=10):
            print("✅ Ray shutdown confirmed")
        else:
            print("⚠️  Warning: Ray may not have fully shutdown")
    else:
        yield


@pytest.fixture
def e2e_ray_manager():
    """Fixture to manage Ray cluster lifecycle for e2e testing."""
    # Use the same RayManager instance that the MCP tools use
    from ray_mcp.main import ray_manager
    
    # Ensure Ray is not already running
    try:
        import ray
        if ray.is_initialized():
            ray.shutdown()
    except ImportError:
        pass  # Ray not available
    
    yield ray_manager
    
    # Cleanup: Stop Ray if it's running
    try:
        import ray
        if ray.is_initialized():
            ray.shutdown()
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture
def mock_cluster_startup():
    """Mock cluster startup operations to speed up tests."""
    with patch("asyncio.sleep") as mock_sleep:
        with patch("subprocess.Popen.communicate") as mock_communicate:
            mock_communicate.return_value = (
                "Ray runtime started\n--address='127.0.0.1:10001'\nView the Ray dashboard at http://127.0.0.1:8265",
                "",
            )
            yield


@pytest.fixture
def mock_ray_available():
    """Mock Ray as available for tests."""
    with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
        yield


@pytest.fixture
def mock_ray_module():
    """Mock the ray module with common behaviors."""
    with patch("ray_mcp.ray_manager.ray") as mock_ray:
        mock_ray.is_initialized.return_value = False
        mock_ray.init.return_value = Mock(
            address_info={"address": "127.0.0.1:10001"},
            dashboard_url="http://127.0.0.1:8265",
        )
        mock_ray.get_runtime_context.return_value.get_node_id.return_value = "node_123"
        yield mock_ray
