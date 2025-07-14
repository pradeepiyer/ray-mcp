#!/usr/bin/env python3
"""Critical end-to-end tests for Ray MCP server.

This module contains the most important integration tests that validate
core functionality without mocking, ensuring the system works end-to-end.

Test Focus:
- Complete Ray cluster + job workflows
- MCP server tool integration
- Real prompt processing and response generation
- Critical error scenarios and recovery
"""

import asyncio
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Dict, List

from mcp.types import TextContent
import pytest

# Import the actual server components (no mocking)
from ray_mcp.handlers import RayHandlers
from ray_mcp.managers.unified_manager import RayUnifiedManager
from ray_mcp.tools import get_ray_tools


class E2ETestConfig:
    """Configuration for end-to-end tests."""

    # Detect CI environment
    IN_CI = os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI") == "true"

    # Resource limits for different environments
    CPU_LIMIT = 1 if IN_CI else 2
    MEMORY_LIMIT_GB = 1 if IN_CI else 2
    DASHBOARD_PORT = 8267  # Use non-default port to avoid conflicts

    # Timeouts
    CLUSTER_START_TIMEOUT = 30 if IN_CI else 60
    JOB_COMPLETION_TIMEOUT = 60 if IN_CI else 120
    CONNECTION_TIMEOUT = 10  # Fast timeout for invalid connections


async def cleanup_ray():
    """Clean up any existing Ray instances."""
    try:
        import ray

        if ray.is_initialized():
            ray.shutdown()
            # Reduced wait time for faster cleanup
            await asyncio.sleep(1)
    except:
        pass

    # Also try command line cleanup with reduced timeout
    try:
        import subprocess

        subprocess.run(["ray", "stop"], capture_output=True, check=False, timeout=5)
        # Reduced wait time for faster cleanup
        await asyncio.sleep(0.5)
    except:
        pass

    # Force cleanup any stubborn Ray processes
    try:
        import subprocess
        
        # Kill any remaining Ray processes
        subprocess.run(["pkill", "-f", "ray::"], capture_output=True, check=False)
        subprocess.run(["pkill", "-f", "ray_"], capture_output=True, check=False)
        # Brief wait for process cleanup
        await asyncio.sleep(0.2)
    except:
        pass


def create_test_script(script_content: str) -> str:
    """Create a temporary test script and return its path."""
    import os
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(script_content)
        script_path = f.name
    
    # Make the script executable
    os.chmod(script_path, 0o755)
    return script_path


def parse_tool_response(result: Any) -> Dict[str, Any]:
    """Parse tool response from MCP TextContent format."""
    # Type checker satisfaction - cast to expected type
    from typing import cast

    result_list = cast(List[TextContent], result)
    assert len(result_list) == 1
    text_content = cast(TextContent, result_list[0])
    assert isinstance(text_content, TextContent)
    return json.loads(text_content.text)


@pytest.mark.e2e
class TestCriticalWorkflows:
    """Test the most critical end-to-end workflows."""

    def setup_method(self):
        """Set up for each test."""
        self.unified_manager = RayUnifiedManager()
        self.handlers = RayHandlers(self.unified_manager)
        
        # Store original Ray timeout for restoration
        self.original_gcs_timeout = os.environ.get('RAY_gcs_server_request_timeout_seconds')
        
        # Set faster timeout for tests to avoid long waits on invalid connections
        os.environ['RAY_gcs_server_request_timeout_seconds'] = '5'
        
        # Suppress Ray's verbose logging during tests
        self.original_ray_log_level = os.environ.get('RAY_LOG_LEVEL')
        os.environ['RAY_LOG_LEVEL'] = 'CRITICAL'  # Suppress all but critical logs

    async def teardown_method(self):
        """Clean up after each test."""
        # Restore original Ray timeout
        if self.original_gcs_timeout is not None:
            os.environ['RAY_gcs_server_request_timeout_seconds'] = self.original_gcs_timeout
        else:
            os.environ.pop('RAY_gcs_server_request_timeout_seconds', None)
            
        # Restore original Ray log level
        if self.original_ray_log_level is not None:
            os.environ['RAY_LOG_LEVEL'] = self.original_ray_log_level
        else:
            os.environ.pop('RAY_LOG_LEVEL', None)
            
        await cleanup_ray()

    @pytest.mark.asyncio
    async def test_complete_ray_workflow(self):
        """Test complete Ray workflow: create cluster, submit job, get logs, cleanup."""
        print("🚀 Testing complete Ray workflow...")

        await cleanup_ray()

        try:
            # Step 1: Create local Ray cluster
            print("📡 Creating Ray cluster...")
            result = await self.handlers.handle_tool_call(
                "ray_cluster",
                {
                    "prompt": f"create a local cluster with {E2ETestConfig.CPU_LIMIT} CPUs and dashboard on port {E2ETestConfig.DASHBOARD_PORT}"
                },
            )

            response = parse_tool_response(result)
            print(f"Cluster creation response: {response}")

            # Verify cluster creation
            assert (
                response["status"] == "success"
            ), f"Cluster creation failed: {response}"
            assert "cluster_address" in response
            assert str(E2ETestConfig.DASHBOARD_PORT) in response.get(
                "dashboard_url", ""
            )

            # Wait for cluster to be fully ready
            await asyncio.sleep(5)

            # Step 2: Verify cluster is running by inspecting it
            print("🔍 Inspecting cluster status...")
            result = await self.handlers.handle_tool_call(
                "ray_cluster", {"prompt": "inspect cluster status"}
            )

            response = parse_tool_response(result)
            print(f"Cluster inspection response: {response}")

            assert response["status"] == "success"
            assert response["cluster_status"] == "running"
            assert "resources" in response

            # Step 3: Create and submit a simple test job
            print("💼 Creating and submitting test job...")

            test_job_script = """#!/usr/bin/env python3
import time

# Simple test job that doesn't use Ray remote functions
# This simulates a job that would typically be submitted to Ray
def simple_task(x):
    time.sleep(1)  # Simulate some work
    return x * 2

# Submit some tasks
print("Starting Ray job...")
results = []
for i in range(3):
    result = simple_task(i)
    results.append(result)
    
print(f"Job completed! Results: {results}")
print("Job finished successfully")
"""

            script_path = create_test_script(test_job_script)

            try:
                result = await self.handlers.handle_tool_call(
                    "ray_job", {"prompt": f"submit job with script {script_path}"}
                )

                response = parse_tool_response(result)
                print(f"Job submission response: {response}")

                assert (
                    response["status"] == "success"
                ), f"Job submission failed: {response}"
                assert "job_id" in response
                job_id = response["job_id"]

                # Step 4: Wait for job completion and check status
                print(f"⏳ Waiting for job {job_id} to complete...")

                max_wait_time = E2ETestConfig.JOB_COMPLETION_TIMEOUT
                wait_interval = 5
                elapsed_time = 0

                job_status = None
                while elapsed_time < max_wait_time:
                    result = await self.handlers.handle_tool_call(
                        "ray_job", {"prompt": f"get status for job {job_id}"}
                    )

                    response = parse_tool_response(result)

                    if response["status"] == "success":
                        job_status = response.get("job_status", "UNKNOWN")
                        print(f"Job status: {job_status}")

                        if job_status in ["SUCCEEDED", "FAILED"]:
                            break

                    await asyncio.sleep(wait_interval)
                    elapsed_time += wait_interval

                # If job failed, get logs for debugging
                if job_status == "FAILED":
                    print("🔍 Job failed - getting logs for debugging...")
                    result = await self.handlers.handle_tool_call(
                        "ray_job", {"prompt": f"get logs for job {job_id}"}
                    )
                    response = parse_tool_response(result)
                    if response["status"] == "success" and "logs" in response:
                        print(f"Job logs: {response['logs']}")
                    else:
                        print(f"Could not get job logs: {response}")

                # Verify job completed successfully
                assert (
                    job_status == "SUCCEEDED"
                ), f"Job did not complete successfully. Final status: {job_status}"

                # Step 5: Get job logs
                print("📋 Retrieving job logs...")
                result = await self.handlers.handle_tool_call(
                    "ray_job", {"prompt": f"get logs for job {job_id}"}
                )

                response = parse_tool_response(result)
                print(f"Job logs response keys: {response.keys()}")

                assert response["status"] == "success"
                assert "logs" in response

                # Verify logs contain expected content
                logs = response["logs"]
                assert "Job completed!" in logs or "Job finished successfully" in logs

                # Step 6: List all jobs to verify our job is in the list
                print("📜 Listing all jobs...")
                result = await self.handlers.handle_tool_call(
                    "ray_job", {"prompt": "list all jobs"}
                )

                response = parse_tool_response(result)
                print(f"Job listing response: {response}")
                assert response["status"] == "success"
                assert "jobs" in response

                # Our job should be in the list
                job_ids = [job["job_id"] for job in response["jobs"]]
                assert job_id in job_ids

            finally:
                # Clean up script file
                try:
                    os.unlink(script_path)
                except:
                    pass

        finally:
            # Step 7: Clean up cluster
            print("🧹 Cleaning up cluster...")
            try:
                result = await self.handlers.handle_tool_call(
                    "ray_cluster", {"prompt": "stop the current cluster"}
                )
                response = parse_tool_response(result)
                print(f"Cluster cleanup response: {response}")

                # Cleanup should succeed or cluster might already be stopped
                assert response[
                    "status"
                ] == "success" or "No Ray cluster" in response.get("message", "")

            except Exception as e:
                print(f"Cluster cleanup failed: {e}")

            await cleanup_ray()

    @pytest.mark.asyncio
    async def test_error_handling_workflow(self):
        """Test error handling in critical scenarios."""
        print("🚨 Testing error handling workflow...")

        await cleanup_ray()

        # Test 1: Try to submit job without cluster
        print("Test 1: Submit job without cluster...")
        result = await self.handlers.handle_tool_call(
            "ray_job", {"prompt": "submit job with script nonexistent.py"}
        )

        response = parse_tool_response(result)
        assert response["status"] == "error"
        assert (
            "not running" in response["message"].lower()
            or "not available" in response["message"].lower()
        )

        # Test 2: Try to connect to invalid cluster
        print("Test 2: Connect to invalid cluster...")
        result = await self.handlers.handle_tool_call(
            "ray_cluster", {"prompt": "connect to cluster at 192.0.2.1:9999"}
        )

        response = parse_tool_response(result)
        assert response["status"] == "error"
        
        # Explicitly clean up any Ray processes that might have started
        # This is especially important after invalid connection attempts
        await cleanup_ray()
        
        # Extra cleanup for stubborn background processes
        try:
            import subprocess
            # Force kill any remaining ray processes
            subprocess.run(["pkill", "-f", "ray"], capture_output=True, check=False)
            await asyncio.sleep(1)
        except:
            pass

        # Test 3: Try to inspect non-existent cluster
        print("Test 3: Inspect non-existent cluster...")
        result = await self.handlers.handle_tool_call(
            "ray_cluster", {"prompt": "inspect cluster status"}
        )

        response = parse_tool_response(result)
        # Should return success but indicate no cluster is running
        assert response["status"] == "success"
        assert (
            response.get("cluster_status") == "not_running"
            or response["message"] == "No Ray cluster is currently running"
        )

    @pytest.mark.asyncio
    async def test_prompt_parsing_robustness(self):
        """Test robustness of prompt parsing with various inputs."""
        print("🔤 Testing prompt parsing robustness...")

        # Test various valid prompt formats
        valid_prompts = [
            ("ray_cluster", "CREATE A CLUSTER WITH 2 CPUS"),  # All caps
            ("ray_cluster", "  create   cluster   with   2   cpus  "),  # Extra spaces
            ("ray_job", "Submit job using script train.py"),  # Mixed case
            ("ray_job", "list jobs"),  # Minimal
            ("cloud", "authenticate with gcp"),  # Abbreviated
        ]

        for tool_name, prompt in valid_prompts:
            print(f"Testing: {tool_name} - '{prompt}'")
            result = await self.handlers.handle_tool_call(tool_name, {"prompt": prompt})
            response = parse_tool_response(result)

            # Should not fail due to parsing (may fail due to missing resources)
            assert "Could not parse" not in response.get("message", "")

    @pytest.mark.asyncio
    async def test_tool_integration_consistency(self):
        """Test that all tools follow consistent patterns."""
        print("🔧 Testing tool integration consistency...")

        tools = get_ray_tools()

        for tool in tools:
            # Test each tool with minimal valid prompt
            minimal_prompts = {
                "ray_cluster": "inspect cluster",
                "ray_job": "list jobs",
                "cloud": "check environment",
            }

            prompt = minimal_prompts.get(tool.name)
            if prompt:
                print(f"Testing tool: {tool.name}")
                result = await self.handlers.handle_tool_call(
                    tool.name, {"prompt": prompt}
                )
                response = parse_tool_response(result)

                # All tools should return valid responses (success or error)
                assert "status" in response
                assert response["status"] in ["success", "error"]

                # All responses should include a message
                assert "message" in response
                assert isinstance(response["message"], str)
                assert len(response["message"]) > 0

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test concurrent operations don't interfere with each other."""
        print("🔄 Testing concurrent operations...")

        await cleanup_ray()

        # Test concurrent cluster inspections (should be safe)
        tasks = [
            self.handlers.handle_tool_call(
                "ray_cluster", {"prompt": "inspect cluster status"}
            )
            for _ in range(3)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should complete without exceptions
        for result in results:
            assert not isinstance(result, Exception)
            response = parse_tool_response(result)
            assert "status" in response

    @pytest.mark.asyncio
    async def test_resource_cleanup(self):
        """Test that resources are properly cleaned up."""
        print("🧹 Testing resource cleanup...")

        await cleanup_ray()

        # Create cluster
        result = await self.handlers.handle_tool_call(
            "ray_cluster",
            {"prompt": f"create cluster with {E2ETestConfig.CPU_LIMIT} CPUs"},
        )
        response = parse_tool_response(result)

        if response["status"] == "success":
            # Verify it's running
            result = await self.handlers.handle_tool_call(
                "ray_cluster", {"prompt": "inspect cluster"}
            )
            response = parse_tool_response(result)
            assert response["status"] == "success"
            assert response["cluster_status"] == "running"

            # Stop it
            result = await self.handlers.handle_tool_call(
                "ray_cluster", {"prompt": "stop cluster"}
            )
            response = parse_tool_response(result)
            assert response["status"] == "success"

            # Verify it's stopped
            await asyncio.sleep(2)
            result = await self.handlers.handle_tool_call(
                "ray_cluster", {"prompt": "inspect cluster"}
            )
            response = parse_tool_response(result)
            assert response["status"] == "success"
            assert response["cluster_status"] == "not_running"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
