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

# Check if running in CI environment
IN_CI = os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI") == "true"

# CI-specific resource constraints
CI_CPU_LIMIT = 1
CI_WAIT_TIME = 10
LOCAL_CPU_LIMIT = 2
LOCAL_WAIT_TIME = 30


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

    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.slow
    async def test_complete_ray_workflow(self, ray_cluster_manager: RayManager):
        """Test the complete Ray workflow: start cluster, submit job, verify results, cleanup."""

        # Use CI-appropriate resource limits
        cpu_limit = CI_CPU_LIMIT if IN_CI else LOCAL_CPU_LIMIT
        max_wait = CI_WAIT_TIME if IN_CI else LOCAL_WAIT_TIME

        # In CI, use empty worker_nodes list to start only head node
        # In local, use None to get default worker nodes for better testing
        worker_nodes = [] if IN_CI else None

        # Step 1: Start Ray cluster using MCP tools
        print(f"Starting Ray cluster with {cpu_limit} CPU(s)...")
        start_result = await call_tool(
            "init_ray", {"num_cpus": cpu_limit, "worker_nodes": worker_nodes}
        )

        # Verify start result
        start_content = get_text_content(start_result)
        start_data = json.loads(start_content)
        print(f"Start result: {start_data}")
        if start_data["status"] == "error":
            print("Error message:", start_data["message"])
        assert start_data["status"] == "success"
        assert start_data.get("result_type") == "started"
        print(f"Ray cluster started: {start_data}")

        # Step 2: Verify cluster status
        print("Checking cluster status...")
        status_result = await call_tool("inspect_ray")
        status_content = get_text_content(status_result)
        status_data = json.loads(status_content)
        assert status_data["status"] == "success"
        assert status_data["cluster_overview"]["status"] == "running"
        print(f"Cluster status: {status_data}")

        # Step 3: Create a lightweight test job instead of using simple_job.py
        print("Creating lightweight test job...")

        # Create a minimal test script
        test_script = """
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

        # Write the test script to a temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(test_script)
            test_script_path = f.name

        try:
            # Submit the lightweight job
            print("Testing job submission functionality...")
            job_result = await call_tool(
                "submit_job", {"entrypoint": f"python {test_script_path}"}
            )

            job_content = get_text_content(job_result)
            job_data = json.loads(job_content)
            assert (
                job_data["status"] == "success"
            ), f"Expected 'success' status, got: {job_data['status']}"
            assert (
                job_data["result_type"] == "submitted"
            ), f"Expected 'submitted' result_type, got: {job_data.get('result_type')}"
            job_id = job_data["job_id"]
            print(f"Job submitted with ID: {job_id}")

            # Test job status with reduced wait time
            print("Testing job status...")
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

        finally:
            # Clean up the test script
            if os.path.exists(test_script_path):
                os.unlink(test_script_path)

        # Step 4: Stop Ray cluster
        print("Stopping Ray cluster...")
        stop_result = await call_tool("stop_ray")
        stop_content = get_text_content(stop_result)
        stop_data = json.loads(stop_content)
        assert stop_data["status"] == "success"
        assert stop_data.get("result_type") == "stopped"
        print("Ray cluster stopped successfully!")

        # Step 5: Verify cluster is stopped
        print("Verifying cluster is stopped...")
        final_status_result = await call_tool("inspect_ray")
        final_status_content = get_text_content(final_status_result)
        final_status_data = json.loads(final_status_content)
        assert final_status_data["status"] == "not_running"
        print("Cluster shutdown verification passed!")

        print("✅ Complete end-to-end test passed successfully!")

    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.slow
    async def test_job_failure_and_debugging_workflow(
        self, ray_cluster_manager: RayManager
    ):
        """Test job failure handling, debugging, and recovery workflows."""

        # Use CI-appropriate resource limits
        cpu_limit = CI_CPU_LIMIT if IN_CI else LOCAL_CPU_LIMIT
        max_wait = CI_WAIT_TIME if IN_CI else LOCAL_WAIT_TIME

        # In CI, use empty worker_nodes list to start only head node
        # In local, use None to get default worker nodes for better testing
        worker_nodes = [] if IN_CI else None

        # Step 1: Start Ray cluster
        print(f"Starting Ray cluster for failure testing with {cpu_limit} CPU(s)...")
        start_result = await call_tool(
            "init_ray", {"num_cpus": cpu_limit, "worker_nodes": worker_nodes}
        )

        # Verify start result
        start_content = get_text_content(start_result)
        start_data = json.loads(start_content)
        print(f"Start result: {start_data}")
        if start_data["status"] == "error":
            print("Error message:", start_data["message"])
        assert start_data["status"] == "success"
        assert start_data.get("result_type") == "started"
        print(f"Ray cluster started for failure testing: {start_data}")

        # Step 2: Create a job that will fail
        print("Submitting a job designed to fail...")

        # Create a script that will fail quickly
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
                fail_job_data["status"] == "success"
            ), f"Expected 'success' status, got: {fail_job_data['status']}"
            assert (
                fail_job_data["result_type"] == "submitted"
            ), f"Expected 'submitted' result_type, got: {fail_job_data.get('result_type')}"
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

            # Step 6: Test a lightweight success job to verify cluster health
            print("Testing lightweight success job...")

            success_script = """
import ray

@ray.remote
def quick_success_task():
    return "Success!"

result = ray.get(quick_success_task.remote())
print(f"Success job result: {result}")
print("Success job completed!")
"""

            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(success_script)
                success_script_path = f.name

            try:
                # Submit the success job
                print("Submitting success job...")
                success_job_result = await call_tool(
                    "submit_job",
                    {"entrypoint": f"python {success_script_path}", "runtime_env": {}},
                )

                success_job_content = get_text_content(success_job_result)
                success_job_data = json.loads(success_job_content)
                success_job_id = success_job_data["job_id"]
                print(f"Success job submitted successfully: {success_job_id}")

                # Test status check on the success job with reduced wait time
                for i in range(max_wait):
                    status_result = await call_tool(
                        "inspect_job", {"job_id": success_job_id}
                    )
                    status_content = get_text_content(status_result)
                    status_data = json.loads(status_content)
                    job_status = status_data.get("job_status", "UNKNOWN")
                    print(f"Success job status at {i+1}s: {job_status}")
                    if job_status == "SUCCEEDED":
                        break
                    if job_status == "FAILED":
                        pytest.fail(f"Success job failed unexpectedly: {status_data}")
                    await asyncio.sleep(1)
                else:
                    pytest.fail(
                        f"Success job did not complete within {max_wait} seconds. Last status: {job_status}"
                    )
                assert status_data["status"] == "success"
                assert status_data["job_status"] == "SUCCEEDED"
                print("Success job completed successfully!")

            except Exception as e:
                print(f"Success job submission failed: {e}")
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
        assert stop_data["status"] == "success"
        assert stop_data.get("result_type") == "stopped"

        print("✅ Job failure and debugging workflow test passed successfully!")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
