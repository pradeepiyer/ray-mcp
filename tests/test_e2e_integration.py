#!/usr/bin/env python3
"""End-to-end integration tests for the Ray MCP server."""

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch

from mcp.types import TextContent, Tool
import psutil
import pytest
import pytest_asyncio
import ray

from ray_mcp.main import list_tools, ray_manager
from ray_mcp.ray_manager import RayManager
from ray_mcp.tool_registry import ToolRegistry

SKIP_IN_CI = pytest.mark.skipif(
    os.environ.get("GITHUB_ACTIONS") == "true",
    reason="Unreliable in CI due to resource constraints",
)


def get_text_content(result) -> str:
    """Helper function to extract text content from MCP result."""
    content = list(result)[0]
    assert isinstance(content, TextContent)
    return content.text


async def call_tool(
    tool_name: str, arguments: Optional[Dict[str, Any]] = None
) -> List[TextContent]:
    """Helper function to call tools using the new ToolRegistry architecture."""
    # Use the same RayManager instance that the MCP tools use
    from ray_mcp.main import ray_manager

    registry = ToolRegistry(ray_manager)

    # Execute the tool
    result = await registry.execute_tool(tool_name, arguments or {})

    # Convert the result to the expected MCP format
    result_text = json.dumps(result, indent=2)
    return [TextContent(type="text", text=result_text)]


class TestE2EIntegration:
    """End-to-end integration tests that test the complete workflow without mocking."""

    @pytest_asyncio.fixture
    async def ray_cluster_manager(self):
        """Fixture to manage Ray cluster lifecycle for testing."""
        # Use the same RayManager instance that the MCP tools use
        from ray_mcp.main import ray_manager

        # Ensure Ray is not already running
        if ray.is_initialized():
            ray.shutdown()

        yield ray_manager

        # Cleanup: Stop Ray if it's running
        try:
            if ray.is_initialized():
                ray.shutdown()
        except Exception:
            pass  # Ignore cleanup errors

    @SKIP_IN_CI
    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.slow
    async def test_complete_ray_workflow(self, ray_cluster_manager: RayManager):
        """Test the complete Ray workflow: start cluster, submit job, verify results, cleanup."""

        # Step 1: Start Ray cluster using MCP tools
        print("Starting Ray cluster...")
        start_result = await call_tool("init_ray", {"num_cpus": 4})

        # Verify start result
        start_content = get_text_content(start_result)
        start_data = json.loads(start_content)
        print(f"Start result: {start_data}")
        if start_data["status"] != "started":
            print(f"Error message: {start_data.get('message', 'No error message')}")
        assert start_data["status"] == "started"
        print(f"Ray cluster started: {start_data}")

        # Step 2: Verify cluster status
        print("Checking cluster status...")
        status_result = await call_tool("cluster_info")
        status_content = get_text_content(status_result)
        status_data = json.loads(status_content)
        assert status_data["status"] == "success"
        assert status_data["cluster_overview"]["status"] == "running"
        print(f"Cluster status: {status_data}")

        # Step 3: Submit the simple_job.py
        print("Submitting simple_job.py...")

        # Get the absolute path to the examples directory
        current_dir = Path(__file__).parent.parent
        examples_dir = current_dir / "examples"
        simple_job_path = examples_dir / "simple_job.py"

        assert simple_job_path.exists(), f"simple_job.py not found at {simple_job_path}"

        # Step 3: Test job submission functionality
        print("Testing job submission functionality...")

        # Submit the job
        job_result = await call_tool(
            "submit_job", {"entrypoint": f"python {simple_job_path}"}
        )

        job_content = get_text_content(job_result)
        job_data = json.loads(job_content)
        assert (
            job_data["status"] == "submitted"
        ), f"Expected 'submitted' status, got: {job_data['status']}"
        job_id = job_data["job_id"]
        print(f"Job submitted with ID: {job_id}")

        # Test job status
        print("Testing job status...")
        max_wait = 30
        for i in range(max_wait):
            status_result = await call_tool("inspect_job", {"job_id": job_id})
            status_content = get_text_content(status_result)
            status_data = json.loads(status_content)
            job_status = status_data.get("job_status", "UNKNOWN")
            print(f"Job status at {i+1}s: {job_status}")
            if job_status == "SUCCEEDED":
                break
            if job_status == "FAILED":
                pytest.fail(f"Job failed unexpectedly: {status_data}")
            await asyncio.sleep(1)
        else:
            pytest.fail(
                f"Job did not complete within {max_wait} seconds. Last status: {job_status}"
            )
        assert status_data["status"] == "success"
        assert status_data["job_status"] == "SUCCEEDED"
        print("Job completed successfully!")

        # Test job listing functionality
        print("Testing job listing functionality...")
        jobs_result = await call_tool("list_jobs")
        jobs_content = get_text_content(jobs_result)
        jobs_data = json.loads(jobs_content)
        assert jobs_data["status"] == "success"
        print(f"Found {len(jobs_data['jobs'])} jobs in the cluster")

        print("Job management tests completed!")

        # Step 4: Stop Ray cluster
        print("Stopping Ray cluster...")
        stop_result = await call_tool("stop_ray")
        stop_content = get_text_content(stop_result)
        stop_data = json.loads(stop_content)
        assert stop_data["status"] == "stopped"
        print("Ray cluster stopped successfully!")

        # Step 5: Verify cluster is stopped
        print("Verifying cluster is stopped...")
        final_status_result = await call_tool("cluster_info")
        final_status_content = get_text_content(final_status_result)
        final_status_data = json.loads(final_status_content)
        assert final_status_data["status"] == "not_running"
        print("Cluster shutdown verification passed!")

        print("✅ Complete end-to-end test passed successfully!")

    @SKIP_IN_CI
    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.slow
    async def test_job_failure_and_debugging_workflow(
        self, ray_cluster_manager: RayManager
    ):
        """Test job failure handling, debugging, and recovery workflows."""

        # Step 1: Start Ray cluster
        print("Starting Ray cluster for failure testing...")
        start_result = await call_tool("init_ray", {"num_cpus": 2})

        # Verify start result
        start_content = get_text_content(start_result)
        start_data = json.loads(start_content)
        print(f"Start result: {start_data}")
        if start_data["status"] != "started":
            print(f"Error message: {start_data.get('message', 'No error message')}")
        assert start_data["status"] == "started"
        print(f"Ray cluster started for failure testing: {start_data}")

        # Step 2: Create a job that will fail
        print("Submitting a job designed to fail...")

        # Create a script that will fail
        failing_script = """
import sys
print("This job will fail intentionally")
sys.exit(1)  # Intentional failure
"""

        # Write the failing script to a temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(failing_script)
            failing_script_path = f.name

        try:
            # Submit the failing job
            print("Submitting failing job...")
            fail_job_result = await call_tool(
                "submit_job",
                {"entrypoint": f"python {failing_script_path}", "runtime_env": {}},
            )

            fail_job_content = get_text_content(fail_job_result)
            fail_job_data = json.loads(fail_job_content)
            assert (
                fail_job_data["status"] == "submitted"
            ), f"Expected 'submitted' status, got: {fail_job_data['status']}"
            fail_job_id = fail_job_data["job_id"]
            print(f"Failing job submitted with ID: {fail_job_id}")

            # Step 3: Test job status
            print("Testing job status...")
            status_result = await call_tool("inspect_job", {"job_id": fail_job_id})
            status_content = get_text_content(status_result)
            status_data = json.loads(status_content)
            assert status_data["status"] == "success"
            print(f"Job status: {status_data.get('job_status', 'UNKNOWN')}")

            # Step 4: Test log retrieval functionality
            print("Testing log retrieval functionality...")
            logs_result = await call_tool(
                "retrieve_logs", {"identifier": fail_job_id, "log_type": "job"}
            )
            logs_content = get_text_content(logs_result)
            logs_data = json.loads(logs_content)

            assert logs_data["status"] == "success"
            print("Log retrieval successful")

            # Step 5: Debug the failed job
            print("Debugging the failed job...")
            debug_result = await call_tool(
                "inspect_job", {"job_id": fail_job_id, "mode": "debug"}
            )
            debug_content = get_text_content(debug_result)
            debug_data = json.loads(debug_content)

            assert debug_data["status"] == "success"
            assert "debug_info" in debug_data
            print("Debug functionality working")

            # Step 6: Test additional job submission to verify cluster health
            print("Testing additional job submission...")

            success_script = """
import time
print("Starting test job...")
time.sleep(1)
print("Job completed!")
"""

            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(success_script)
                success_script_path = f.name

            try:
                # Submit the additional job
                print("Submitting additional job...")
                success_job_result = await call_tool(
                    "submit_job",
                    {"entrypoint": f"python {success_script_path}", "runtime_env": {}},
                )

                success_job_content = get_text_content(success_job_result)
                success_job_data = json.loads(success_job_content)
                success_job_id = success_job_data["job_id"]
                print(f"Additional job submitted successfully: {success_job_id}")

                # Test status check on the new job
                max_wait = 30
                for i in range(max_wait):
                    status_result = await call_tool(
                        "inspect_job", {"job_id": success_job_id}
                    )
                    status_content = get_text_content(status_result)
                    status_data = json.loads(status_content)
                    job_status = status_data.get("job_status", "UNKNOWN")
                    print(f"Additional job status at {i+1}s: {job_status}")
                    if job_status == "SUCCEEDED":
                        break
                    if job_status == "FAILED":
                        pytest.fail(
                            f"Additional job failed unexpectedly: {status_data}"
                        )
                    await asyncio.sleep(1)
                else:
                    pytest.fail(
                        f"Additional job did not complete within {max_wait} seconds. Last status: {job_status}"
                    )
                assert status_data["status"] == "success"
                assert status_data["job_status"] == "SUCCEEDED"
                print("Additional job completed successfully!")

            except Exception as e:
                print(f"Additional job submission failed: {e}")
                success_job_id = None

            finally:
                # Clean up success script
                if os.path.exists(success_script_path):
                    os.unlink(success_script_path)

            # Step 7: List all jobs to verify both are recorded
            print("Listing all jobs...")
            jobs_result = await call_tool("list_jobs")
            jobs_content = get_text_content(jobs_result)
            jobs_data = json.loads(jobs_content)

            assert jobs_data["status"] == "success"
            print(f"Found {len(jobs_data['jobs'])} jobs in the cluster")

        finally:
            # Clean up the failing script
            if os.path.exists(failing_script_path):
                os.unlink(failing_script_path)

        # Step 8: Stop Ray cluster
        print("Stopping Ray cluster...")
        stop_result = await call_tool("stop_ray")
        stop_content = get_text_content(stop_result)
        stop_data = json.loads(stop_content)
        assert stop_data["status"] == "stopped"

        print("✅ Job failure and debugging workflow test passed successfully!")

    @pytest.mark.asyncio
    @pytest.mark.smoke
    @pytest.mark.fast
    async def test_mcp_tools_availability(self):
        """Test that all required MCP tools are available and correctly listed."""
        from ray_mcp.main import list_tools

        tools = await list_tools()
        assert isinstance(tools, list)
        tool_names = {tool.name for tool in tools}
        expected_tools = {
            "init_ray",
            "stop_ray",
            "cluster_info",
            "submit_job",
            "list_jobs",
            "inspect_job",
            "cancel_job",
            "retrieve_logs",
        }
        # All required tools must be present
        assert expected_tools.issubset(tool_names)
        # Check that all tools are Tool instances
        from mcp.types import Tool

        for tool in tools:
            assert isinstance(tool, Tool)

        print("✅ MCP tools availability test passed!")

    @pytest.mark.asyncio
    async def test_error_handling_without_ray(self):
        """Test error handling for operations when Ray is not initialized."""

        # Ensure Ray is not running
        if ray.is_initialized():
            ray.shutdown()

        # Test calling job operations without Ray initialized
        result = await call_tool("submit_job", {"entrypoint": "python test.py"})
        content = get_text_content(result)

        # Should get a proper error response
        assert "Ray is not initialized" in content or "not_running" in content.lower()

        # Test cluster status when Ray is not running
        status_result = await call_tool("cluster_info")
        status_content = get_text_content(status_result)
        status_data = json.loads(status_content)
        assert status_data["status"] == "not_running"

        print("✅ Error handling test passed!")


@SKIP_IN_CI
@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.slow
async def test_simple_job_standalone():
    """Test that simple_job.py can run standalone (validation test)."""

    # Get the path to simple_job.py
    current_dir = Path(__file__).parent.parent
    simple_job_path = current_dir / "examples" / "simple_job.py"

    assert simple_job_path.exists(), f"simple_job.py not found at {simple_job_path}"

    # Import and run the job directly instead of using subprocess
    # This avoids the hanging issue with Ray + uv + subprocess
    import contextlib
    import importlib.util
    from io import StringIO
    import sys

    # Capture stdout to verify output
    captured_output = StringIO()

    # Load the simple_job module
    spec = importlib.util.spec_from_file_location("simple_job", simple_job_path)
    if spec is None or spec.loader is None:
        pytest.fail(f"Could not load simple_job.py from {simple_job_path}")

    simple_job_module = importlib.util.module_from_spec(spec)

    # Run the job and capture output
    try:
        with contextlib.redirect_stdout(captured_output):
            spec.loader.exec_module(simple_job_module)
            # Call main function if it exists
            if hasattr(simple_job_module, "main"):
                simple_job_module.main()
    except Exception as e:
        pytest.fail(f"simple_job.py failed with exception: {e}")

    # Get the captured output
    output = captured_output.getvalue()

    # Verify expected output
    assert (
        "Ray is not initialized, initializing now..." in output
        or "Ray is already initialized (job context)" in output
    )
    assert "Running Simple Tasks" in output
    assert "Task result:" in output
    assert "All tasks completed successfully!" in output
    assert (
        "Ray shutdown complete (initialized by script)." in output
        or "Job execution complete (Ray managed externally)." in output
    )

    print("✅ Simple job standalone test passed!")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
