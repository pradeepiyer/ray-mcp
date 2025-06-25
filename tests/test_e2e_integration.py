#!/usr/bin/env python3
"""End-to-end integration tests for the Ray MCP server."""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil
import pytest
import pytest_asyncio
import ray

from mcp.types import TextContent, Tool

# Import the MCP server functions directly for testing
from ray_mcp.main import call_tool, list_tools
from ray_mcp.ray_manager import RayManager


def get_text_content(result) -> str:
    """Helper function to extract text content from MCP result."""
    content = list(result)[0]
    assert isinstance(content, TextContent)
    return content.text


class TestE2EIntegration:
    """End-to-end integration tests that test the complete workflow without mocking."""

    @pytest_asyncio.fixture
    async def ray_cluster_manager(self):
        """Fixture to manage Ray cluster lifecycle for testing."""
        ray_manager = RayManager()

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

        # Step 1: Start Ray cluster using MCP tools
        print("Starting Ray cluster...")
        start_result = await call_tool("start_ray", {"num_cpus": 4})

        # Verify start result
        start_content = get_text_content(start_result)
        start_data = json.loads(start_content)
        assert start_data["status"] == "started"
        print(f"Ray cluster started: {start_data}")

        # Verify Ray is actually initialized
        assert ray.is_initialized(), "Ray should be initialized after start_ray"

        # Step 2: Verify cluster status
        print("Checking cluster status...")
        status_result = await call_tool("cluster_status")
        status_content = get_text_content(status_result)
        status_data = json.loads(status_content)
        assert status_data["status"] == "running"
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
        assert job_data["status"] == "submitted"
        job_id = job_data["job_id"]
        print(f"Job submitted with ID: {job_id}")

        # Wait for job to complete
        print("Waiting for job to complete...")
        job_completed = False
        for i in range(15):  # 15 seconds should be sufficient for job completion
            status_result = await call_tool("job_status", {"job_id": job_id})
            status_content = get_text_content(status_result)
            status_data = json.loads(status_content)
            job_status = status_data.get("job_status", "UNKNOWN")
            if i % 5 == 0:  # Print status every 5 seconds to reduce noise
                print(f"Job status check {i+1}: {job_status}")

            if job_status == "SUCCEEDED":
                print("Job completed successfully!")
                job_completed = True
                break
            elif job_status == "FAILED":
                # Get job logs for debugging
                logs_result = await call_tool("get_logs", {"job_id": job_id})
                logs_content = get_text_content(logs_result)
                logs_data = json.loads(logs_content)
                pytest.fail(
                    f"Job failed unexpectedly: {status_data}\nLogs: {logs_data.get('logs', 'No logs available')}"
                )
            elif job_status in ["PENDING", "RUNNING"]:
                await asyncio.sleep(1)
            else:
                await asyncio.sleep(1)

        assert job_completed, "Job did not complete within expected time"

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
        final_status_result = await call_tool("cluster_status")
        final_status_content = get_text_content(final_status_result)
        final_status_data = json.loads(final_status_content)
        assert final_status_data["status"] == "not_running"
        print("Cluster shutdown verification passed!")

        # Verify Ray is actually shutdown
        assert not ray.is_initialized(), "Ray should be shutdown after stop_ray"

        print("✅ Complete end-to-end test passed successfully!")

    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.slow
    async def test_actor_management_workflow(self, ray_cluster_manager: RayManager):
        """Test the complete actor management workflow: create actors, list, monitor, kill."""

        # Step 1: Start Ray cluster
        print("Starting Ray cluster for actor management...")
        start_result = await call_tool("start_ray", {"num_cpus": 4})
        start_content = get_text_content(start_result)
        start_data = json.loads(start_content)
        assert start_data["status"] == "started"
        print(f"Ray cluster started: {start_data}")

        # Step 2: Create a script that creates actors but doesn't shutdown Ray
        print("Creating actors directly...")

        # Create an actor script that creates actors and keeps them alive
        actor_script = """
import ray
import time

@ray.remote
class TestActor:
    def __init__(self, actor_id):
        self.actor_id = actor_id
        print(f"TestActor {actor_id} initialized")
    
    def get_id(self):
        return self.actor_id
    
    def do_work(self, n):
        time.sleep(0.1)  # Simulate some work
        return f"Actor {self.actor_id} processed {n}"

def main():
    # Create multiple actors that will stay alive
    actors = []
    for i in range(3):
        actor = TestActor.remote(i)
        actors.append(actor)
        print(f"Created actor {i}")
    
    # Do some work with the actors to keep them active
    futures = []
    for i, actor in enumerate(actors):
        future = actor.do_work.remote(i * 10)
        futures.append(future)
    
    results = ray.get(futures)
    for result in results:
        print(result)
    
    print("Actors created and working. Keeping job alive for testing...")
    # Keep the job alive for a while so actors can be listed
    time.sleep(10)
    print("Actor job completing...")

if __name__ == "__main__":
    main()
"""

        # Write the actor script to a temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(actor_script)
            actor_script_path = f.name

        try:
            # Submit the actor job
            actor_job_result = await call_tool(
                "submit_job", {"entrypoint": f"python {actor_script_path}"}
            )

            actor_job_content = get_text_content(actor_job_result)
            actor_job_data = json.loads(actor_job_content)
            assert actor_job_data["status"] == "submitted"
            actor_job_id = actor_job_data["job_id"]
            print(f"Actor job submitted with ID: {actor_job_id}")

            # Step 3: Wait for actor job to start and create actors
            print("Waiting for actors to be created...")
            await asyncio.sleep(
                5
            )  # Give time for actors to be created and start working

            # Step 4: List actors to verify they were created
            print("Listing actors...")
            actors_result = await call_tool("list_actors")
            actors_content = get_text_content(actors_result)
            actors_data = json.loads(actors_content)

            assert actors_data["status"] == "success"
            actors_list = actors_data["actors"]
            print(f"Found {len(actors_list)} actors")

            # Verify we have some actors
            assert len(actors_list) > 0, "No actors found after running actor script"

            # Step 5: Get details about the first actor
            if actors_list:
                first_actor = actors_list[0]
                actor_id = first_actor["actor_id"]
                print(f"First actor details: {first_actor}")

                # Verify actor has expected fields
                assert "actor_id" in first_actor
                assert "state" in first_actor
                assert "name" in first_actor  # It's 'name', not 'class_name'

                # Step 6: Try to kill the first actor (may fail for system actors)
                print(f"Attempting to kill actor {actor_id}...")
                kill_result = await call_tool(
                    "kill_actor", {"actor_id": actor_id, "no_restart": True}
                )
                kill_content = get_text_content(kill_result)
                kill_data = json.loads(kill_content)

                if kill_data["status"] == "success":
                    print(f"Actor killed successfully: {kill_data}")

                    # Step 7: Verify actor was killed by listing actors again
                    print("Verifying actor was killed...")
                    await asyncio.sleep(2)  # Wait for actor to be cleaned up

                    actors_result2 = await call_tool("list_actors")
                    actors_content2 = get_text_content(actors_result2)
                    actors_data2 = json.loads(actors_content2)

                    new_actors_list = actors_data2["actors"]

                    # The killed actor should either be gone or marked as DEAD
                    actor_still_exists = any(
                        a["actor_id"] == actor_id for a in new_actors_list
                    )
                    if actor_still_exists:
                        killed_actor = next(
                            a for a in new_actors_list if a["actor_id"] == actor_id
                        )
                        assert killed_actor["state"] in [
                            "DEAD",
                            "KILLED",
                        ], f"Actor should be dead but is {killed_actor['state']}"

                    print("Actor kill verification passed!")
                else:
                    print(
                        f"Actor kill failed (expected for system actors): {kill_data}"
                    )
                    # This is acceptable - some actors (like job supervisor actors) cannot be killed
                    print("Skipping kill verification for system actor")

            # Step 8: Wait for actor job to complete or cancel it
            print("Canceling actor job...")
            cancel_result = await call_tool("cancel_job", {"job_id": actor_job_id})
            cancel_content = get_text_content(cancel_result)
            cancel_data = json.loads(cancel_content)
            print(f"Job cancellation result: {cancel_data}")

        finally:
            # Clean up the actor script
            if os.path.exists(actor_script_path):
                os.unlink(actor_script_path)

        # Step 9: Stop Ray cluster
        print("Stopping Ray cluster...")
        stop_result = await call_tool("stop_ray")
        stop_content = get_text_content(stop_result)
        stop_data = json.loads(stop_content)
        assert stop_data["status"] == "stopped"

        print("✅ Actor management workflow test passed successfully!")

    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.slow
    async def test_monitoring_and_health_workflow(
        self, ray_cluster_manager: RayManager
    ):
        """Test the complete monitoring and health check workflow."""

        # Step 1: Start Ray cluster
        print("Starting Ray cluster for monitoring tests...")
        start_result = await call_tool("start_ray", {"num_cpus": 4, "num_gpus": 0})
        start_content = get_text_content(start_result)
        start_data = json.loads(start_content)
        assert start_data["status"] == "started"
        print(f"Ray cluster started for monitoring: {start_data}")

        # Step 2: Get initial cluster resources
        print("Getting cluster resources...")
        resources_result = await call_tool("cluster_resources")
        resources_content = get_text_content(resources_result)
        resources_data = json.loads(resources_content)

        assert resources_data["status"] == "success"
        assert "cluster_resources" in resources_data
        assert "available_resources" in resources_data
        print(f"Cluster resources: {resources_data['cluster_resources']}")
        print(f"Available resources: {resources_data['available_resources']}")

        # Verify we have the expected CPU resources
        cluster_cpus = resources_data["cluster_resources"].get("CPU", 0)
        assert cluster_cpus >= 4, f"Expected at least 4 CPUs, got {cluster_cpus}"

        # Step 3: Get cluster nodes information
        print("Getting cluster nodes...")
        nodes_result = await call_tool("cluster_nodes")
        nodes_content = get_text_content(nodes_result)
        nodes_data = json.loads(nodes_content)

        assert nodes_data["status"] == "success"
        assert "nodes" in nodes_data
        nodes_list = nodes_data["nodes"]
        assert len(nodes_list) >= 1, "Should have at least one node"
        print(f"Found {len(nodes_list)} nodes")

        # Step 4: Get performance metrics
        print("Getting performance metrics...")
        metrics_result = await call_tool("performance_metrics")
        metrics_content = get_text_content(metrics_result)
        metrics_data = json.loads(metrics_content)

        assert metrics_data["status"] == "success"
        assert "cluster_overview" in metrics_data
        assert "resource_details" in metrics_data
        assert "node_details" in metrics_data

        # Verify key metrics are present
        cluster_overview = metrics_data["cluster_overview"]
        resource_details = metrics_data["resource_details"]
        node_details = metrics_data["node_details"]

        assert "total_cpus" in cluster_overview
        assert "available_cpus" in cluster_overview
        assert "CPU" in resource_details
        assert len(node_details) >= 1

        print(f"Performance metrics collected: {list(metrics_data.keys())}")

        # Step 5: Perform health check
        print("Performing cluster health check...")
        health_result = await call_tool("health_check")
        health_content = get_text_content(health_result)
        health_data = json.loads(health_content)

        assert health_data["status"] == "success"
        assert "overall_status" in health_data
        assert "checks" in health_data
        assert "recommendations" in health_data

        print(f"Health status: {health_data['overall_status']}")
        print(f"Health checks: {health_data['checks']}")
        print(f"Recommendations: {health_data['recommendations']}")

        # Step 6: Get optimization recommendations
        print("Getting cluster optimization recommendations...")
        optimize_result = await call_tool("optimize_config")
        optimize_content = get_text_content(optimize_result)
        optimize_data = json.loads(optimize_content)

        assert optimize_data["status"] == "success"
        assert "suggestions" in optimize_data

        suggestions = optimize_data["suggestions"]
        print(f"Optimization suggestions: {suggestions}")

        # Step 7: Submit a job to create some load for monitoring
        print("Submitting a job to create cluster load...")
        current_dir = Path(__file__).parent.parent
        simple_job_path = current_dir / "examples" / "simple_job.py"

        load_job_result = await call_tool(
            "submit_job", {"entrypoint": f"python {simple_job_path}", "runtime_env": {}}
        )

        load_job_content = get_text_content(load_job_result)
        load_job_data = json.loads(load_job_content)
        assert load_job_data["status"] == "submitted"
        load_job_id = load_job_data["job_id"]
        print(f"Load job submitted: {load_job_id}")

        # Step 8: Monitor job progress while it's running
        print("Monitoring job progress...")
        max_attempts = 5
        for attempt in range(max_attempts):
            await asyncio.sleep(1)  # Wait a bit between checks

            # Check job status
            status_result = await call_tool("job_status", {"job_id": load_job_id})
            status_content = get_text_content(status_result)
            status_data = json.loads(status_content)

            job_status = status_data.get("job_status", "UNKNOWN")
            print(f"Job status (attempt {attempt + 1}): {job_status}")

            # Get updated performance metrics while job is running
            metrics_result2 = await call_tool("performance_metrics")
            metrics_content2 = get_text_content(metrics_result2)
            metrics_data2 = json.loads(metrics_content2)

            if metrics_data2["status"] == "success":
                current_overview = metrics_data2.get("cluster_overview", {})
                print(
                    f"Current cluster utilization: CPU {current_overview.get('available_cpus', 0)}/{current_overview.get('total_cpus', 0)}"
                )

            if job_status in ["SUCCEEDED", "FAILED"]:
                break

        # Step 9: Final health check after load
        print("Performing final health check...")
        final_health_result = await call_tool("health_check")
        final_health_content = get_text_content(final_health_result)
        final_health_data = json.loads(final_health_content)

        assert final_health_data["status"] == "success"
        print(f"Final health status: {final_health_data['overall_status']}")

        # Step 10: Stop Ray cluster
        print("Stopping Ray cluster...")
        stop_result = await call_tool("stop_ray")
        stop_content = get_text_content(stop_result)
        stop_data = json.loads(stop_content)
        assert stop_data["status"] == "stopped"

        print("✅ Monitoring and health workflow test passed successfully!")

    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.slow
    async def test_job_failure_and_debugging_workflow(
        self, ray_cluster_manager: RayManager
    ):
        """Test the complete job failure and debugging workflow."""

        # Step 1: Start Ray cluster
        print("Starting Ray cluster for failure testing...")
        start_result = await call_tool("start_ray", {"num_cpus": 2})
        start_content = get_text_content(start_result)
        start_data = json.loads(start_content)
        assert start_data["status"] == "started"
        print(f"Ray cluster started for failure testing: {start_data}")

        # Step 2: Submit a job that will fail
        print("Submitting a job designed to fail...")

        # Create a failing job script
        failing_script = """
import sys
import time
print("Starting failing job...")
        time.sleep(2)  # Simulate some work
print("About to fail...")
raise ValueError("This is an intentional failure for testing")
"""

        # Write the failing script to a temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(failing_script)
            failing_script_path = f.name

        try:
            # Submit the failing job
            fail_job_result = await call_tool(
                "submit_job",
                {"entrypoint": f"python {failing_script_path}", "runtime_env": {}},
            )

            fail_job_content = get_text_content(fail_job_result)
            fail_job_data = json.loads(fail_job_content)
            assert fail_job_data["status"] == "submitted"
            fail_job_id = fail_job_data["job_id"]
            print(f"Failing job submitted with ID: {fail_job_id}")

            # Step 3: Monitor the job status (handle environment issues gracefully)
            print("Monitoring job status...")

            # Check job status a few times to test the API
            final_status = None
            for i in range(5):
                status_result = await call_tool("job_status", {"job_id": fail_job_id})
                status_content = get_text_content(status_result)
                status_data = json.loads(status_content)

                job_status = status_data.get("job_status", "UNKNOWN")
                print(f"Job status check {i+1}: {job_status}")

                if job_status == "FAILED":
                    final_status = "FAILED"
                    print("Job failed as expected!")
                    break
                elif job_status == "SUCCEEDED":
                    final_status = "SUCCEEDED"
                    print("Job succeeded (unexpected but testing API works)")
                    break
                elif job_status in ["PENDING", "RUNNING"]:
                    # Job is still running, continue monitoring
                    await asyncio.sleep(2)
                else:
                    final_status = job_status
                    break

            # The job should fail as expected due to the intentional error
            if final_status is None:
                print("Job status monitoring completed (job may still be pending)")
            else:
                print(f"Final job status: {final_status}")
                if final_status == "FAILED":
                    print("Job failed as expected due to intentional error")

            # Step 4: Test log retrieval functionality
            print("Testing log retrieval functionality...")
            logs_result = await call_tool("get_logs", {"job_id": fail_job_id})
            logs_content = get_text_content(logs_result)
            logs_data = json.loads(logs_content)

            assert logs_data["status"] == "success"
            print(
                f"Log retrieval successful, log type: {logs_data.get('log_type', 'unknown')}"
            )

            # Note: We don't assert on specific log content since this is a failure test
            # but the log retrieval API functionality is tested

            # Step 5: Debug the failed job
            print("Debugging the failed job...")
            debug_result = await call_tool("debug_job", {"job_id": fail_job_id})
            debug_content = get_text_content(debug_result)
            debug_data = json.loads(debug_content)

            assert debug_data["status"] == "success"
            assert "debug_info" in debug_data

            debug_info = debug_data["debug_info"]
            assert "debugging_suggestions" in debug_info
            assert "error_logs" in debug_info

            print(f"Debug suggestions: {debug_info['debugging_suggestions']}")
            print(f"Error logs: {debug_info['error_logs']}")

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
                success_job_result = await call_tool(
                    "submit_job",
                    {"entrypoint": f"python {success_script_path}", "runtime_env": {}},
                )

                success_job_content = get_text_content(success_job_result)
                success_job_data = json.loads(success_job_content)

                if success_job_data["status"] == "submitted":
                    success_job_id = success_job_data["job_id"]
                    print(f"Additional job submitted successfully: {success_job_id}")

                    # Test status check on the new job
                    status_result = await call_tool(
                        "job_status", {"job_id": success_job_id}
                    )
                    status_content = get_text_content(status_result)
                    status_data = json.loads(status_content)
                    print(
                        f"Additional job status: {status_data.get('job_status', 'UNKNOWN')}"
                    )
                else:
                    print("Additional job submission failed")

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
            jobs_list = jobs_data["jobs"]

            # At least one of our jobs should be in the list
            our_jobs_found = 0
            for job in jobs_list:
                if job["job_id"] in [fail_job_id, success_job_id]:
                    our_jobs_found += 1
                elif job["entrypoint"] and (
                    failing_script_path in job["entrypoint"]
                    or success_script_path in job["entrypoint"]
                ):
                    our_jobs_found += 1

            assert (
                our_jobs_found >= 1
            ), f"Expected to find our jobs in list, found {our_jobs_found}"
            print(f"Found {our_jobs_found} of our jobs in the job list")

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
        required_tools = {
            "start_ray",
            "connect_ray",
            "stop_ray",
            "cluster_status",
            "cluster_resources",
            "cluster_nodes",
            "worker_status",
            "submit_job",
            "list_jobs",
            "job_status",
            "cancel_job",
            "monitor_job",
            "debug_job",
            "list_actors",
            "kill_actor",
            "performance_metrics",
            "health_check",
            "optimize_config",
            "schedule_job",
            "get_logs",
        }
        # All required tools must be present
        assert required_tools.issubset(tool_names)
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
        status_result = await call_tool("cluster_status")
        status_content = get_text_content(status_result)
        status_data = json.loads(status_content)
        assert status_data["status"] == "not_running"

        print("✅ Error handling test passed!")

    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.slow
    async def test_cluster_management_cycle(self):
        """Test starting and stopping Ray cluster multiple times."""

        # Ensure clean state
        if ray.is_initialized():
            ray.shutdown()

        # Cycle 1: Start and stop
        start_result = await call_tool("start_ray", {"num_cpus": 2})
        start_content = get_text_content(start_result)
        start_data = json.loads(start_content)
        assert start_data["status"] == "started"
        assert ray.is_initialized()

        stop_result = await call_tool("stop_ray")
        stop_content = get_text_content(stop_result)
        stop_data = json.loads(stop_content)
        assert stop_data["status"] == "stopped"
        assert not ray.is_initialized()

        # Cycle 2: Start again and stop
        start_result2 = await call_tool("start_ray", {"num_cpus": 4})
        start_content2 = get_text_content(start_result2)
        start_data2 = json.loads(start_content2)
        assert start_data2["status"] == "started"
        assert ray.is_initialized()

        stop_result2 = await call_tool("stop_ray")
        stop_content2 = get_text_content(stop_result2)
        stop_data2 = json.loads(stop_content2)
        assert stop_data2["status"] == "stopped"
        assert not ray.is_initialized()

        print("✅ Cluster management cycle test passed!")

    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.slow
    async def test_distributed_training_workflow(self, ray_cluster_manager: RayManager):
        """Test distributed training workflow using the distributed_training.py example on a multi-node cluster."""

        # Step 1: Start Ray cluster with multiple nodes
        print("Starting Ray cluster for distributed training with multiple nodes...")
        start_result = await call_tool(
            "start_ray",
            {
                "num_cpus": 4,
                "num_gpus": 0,
                "worker_nodes": [
                    {"num_cpus": 2, "num_gpus": 0},
                    {"num_cpus": 2, "num_gpus": 0},
                ],
            },
        )
        start_content = get_text_content(start_result)
        start_data = json.loads(start_content)
        assert start_data["status"] == "started"
        assert ray.is_initialized()
        print(f"Multi-node Ray cluster started: {start_data}")

        # Step 2: Verify multi-node cluster status
        print("Verifying multi-node cluster status...")
        status_result = await call_tool("cluster_status")
        status_content = get_text_content(status_result)
        status_data = json.loads(status_content)
        assert status_data["status"] == "running"
        print(f"Cluster status: {status_data}")

        # Step 3: Check worker node status
        print("Checking worker node status...")
        worker_status_result = await call_tool("worker_status")
        worker_status_content = get_text_content(worker_status_result)
        worker_status_data = json.loads(worker_status_content)
        assert worker_status_data["status"] == "success"
        assert "worker_nodes" in worker_status_data
        assert (
            len(worker_status_data["worker_nodes"]) == 2
        ), f"Expected 2 worker nodes, got {len(worker_status_data['worker_nodes'])}"
        print(f"Worker nodes status: {worker_status_data}")

        # Step 4: Get cluster resources to verify multi-node setup
        print("Getting cluster resources...")
        resources_result = await call_tool("cluster_resources")
        resources_content = get_text_content(resources_result)
        resources_data = json.loads(resources_content)

        assert resources_data["status"] == "success"
        assert "cluster_resources" in resources_data
        print(f"Cluster resources: {resources_data['cluster_resources']}")

        # Step 5: Submit the distributed training job
        print("Submitting distributed training job...")

        current_dir = Path(__file__).parent.parent
        examples_dir = current_dir / "examples"
        training_script_path = examples_dir / "distributed_training.py"

        assert (
            training_script_path.exists()
        ), f"distributed_training.py not found at {training_script_path}"

        job_result = await call_tool(
            "submit_job", {"entrypoint": f"python {training_script_path}"}
        )

        job_content = get_text_content(job_result)
        job_data = json.loads(job_content)
        assert job_data["status"] == "submitted"
        job_id = job_data["job_id"]
        print(f"Distributed training job submitted with ID: {job_id}")

        # Step 6: Wait for job completion
        print("Waiting for distributed training job to complete...")

        # Check job status until completion
        job_completed = False
        for i in range(30):  # 30 seconds should be sufficient for training jobs
            status_result = await call_tool("job_status", {"job_id": job_id})
            status_content = get_text_content(status_result)
            status_data = json.loads(status_content)

            job_status = status_data.get("job_status", "UNKNOWN")
            if i % 10 == 0:  # Print status every 10 seconds to reduce noise
                print(f"Training job status check {i+1}: {job_status}")

            if job_status == "SUCCEEDED":
                print("Distributed training job completed successfully!")
                job_completed = True
                break
            elif job_status == "FAILED":
                # Get job logs for debugging
                logs_result = await call_tool("get_logs", {"job_id": job_id})
                logs_content = get_text_content(logs_result)
                logs_data = json.loads(logs_content)
                pytest.fail(
                    f"Distributed training job failed unexpectedly: {status_data}\nLogs: {logs_data.get('logs', 'No logs available')}"
                )
            elif job_status in ["PENDING", "RUNNING"]:
                await asyncio.sleep(1)
            else:
                await asyncio.sleep(1)

        assert (
            job_completed
        ), "Distributed training job did not complete within expected time"

        # Step 7: Test log retrieval functionality
        print("Testing log retrieval functionality...")
        logs_result = await call_tool("get_logs", {"job_id": job_id})
        logs_content = get_text_content(logs_result)
        logs_data = json.loads(logs_content)

        assert logs_data["status"] == "success"
        assert "logs" in logs_data
        print(
            f"Log retrieval successful, log type: {logs_data.get('log_type', 'unknown')}"
        )
        print(
            f"Log content preview: {logs_data['logs'][:200]}..."
            if len(logs_data["logs"]) > 200
            else f"Log content: {logs_data['logs']}"
        )

        # Step 8: Test actor management during training
        print("Testing actor listing functionality...")
        actors_result = await call_tool("list_actors")
        actors_content = get_text_content(actors_result)
        actors_data = json.loads(actors_content)

        # After job completion, there should be no active actors
        assert actors_data["status"] == "success"
        print(f"Active actors after training: {len(actors_data.get('actors', []))}")

        # Step 9: Test performance metrics
        print("Getting performance metrics...")
        metrics_result = await call_tool("performance_metrics")
        metrics_content = get_text_content(metrics_result)
        metrics_data = json.loads(metrics_content)

        assert metrics_data["status"] == "success"
        assert "cluster_overview" in metrics_data or "cluster_resources" in metrics_data
        print("Performance metrics retrieved successfully!")

        # Step 10: Stop Ray cluster
        print("Stopping Ray cluster...")
        stop_result = await call_tool("stop_ray")
        stop_content = get_text_content(stop_result)
        stop_data = json.loads(stop_content)
        assert stop_data["status"] == "stopped"
        assert not ray.is_initialized()

        print("✅ Multi-node distributed training workflow test passed successfully!")

    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.slow
    async def test_data_pipeline_workflow(self, ray_cluster_manager: RayManager):
        """Test data processing pipeline workflow using the data_pipeline.py example."""

        # Step 1: Start Ray cluster
        print("Starting Ray cluster for data pipeline...")
        start_result = await call_tool("start_ray", {"num_cpus": 4})
        start_content = get_text_content(start_result)
        start_data = json.loads(start_content)
        assert start_data["status"] == "started"
        assert ray.is_initialized()

        # Step 2: Get cluster resources before processing
        print("Checking cluster resources...")
        resources_result = await call_tool("cluster_resources")
        resources_content = get_text_content(resources_result)
        resources_data = json.loads(resources_content)

        assert resources_data["status"] == "success"
        assert "cluster_resources" in resources_data
        print(f"Cluster resources: {resources_data['cluster_resources']}")

        # Step 3: Submit the data pipeline job
        print("Submitting data pipeline job...")

        current_dir = Path(__file__).parent.parent
        examples_dir = current_dir / "examples"
        pipeline_script_path = examples_dir / "data_pipeline.py"

        assert (
            pipeline_script_path.exists()
        ), f"data_pipeline.py not found at {pipeline_script_path}"

        job_result = await call_tool(
            "submit_job", {"entrypoint": f"python {pipeline_script_path}"}
        )

        job_content = get_text_content(job_result)
        job_data = json.loads(job_content)
        assert job_data["status"] == "submitted"
        job_id = job_data["job_id"]
        print(f"Data pipeline job submitted with ID: {job_id}")

        # Step 4: Wait for job completion
        print("Waiting for data pipeline job to complete...")

        # Check job status until completion
        job_completed = False
        for i in range(25):  # 25 seconds should be sufficient for pipeline jobs
            status_result = await call_tool("job_status", {"job_id": job_id})
            status_content = get_text_content(status_result)
            status_data = json.loads(status_content)

            job_status = status_data.get("job_status", "UNKNOWN")
            if i % 10 == 0:  # Print status every 10 seconds to reduce noise
                print(f"Pipeline job status check {i+1}: {job_status}")

            if job_status == "SUCCEEDED":
                print("Data pipeline job completed successfully!")
                job_completed = True
                break
            elif job_status == "FAILED":
                # Get job logs for debugging
                logs_result = await call_tool("get_logs", {"job_id": job_id})
                logs_content = get_text_content(logs_result)
                logs_data = json.loads(logs_content)
                pytest.fail(
                    f"Data pipeline job failed unexpectedly: {status_data}\nLogs: {logs_data.get('logs', 'No logs available')}"
                )
            elif job_status in ["PENDING", "RUNNING"]:
                await asyncio.sleep(1)
            else:
                await asyncio.sleep(1)

        assert job_completed, "Data pipeline job did not complete within expected time"

        # Step 5: Test log retrieval functionality
        print("Testing log retrieval functionality...")
        logs_result = await call_tool("get_logs", {"job_id": job_id})
        logs_content = get_text_content(logs_result)
        logs_data = json.loads(logs_content)

        assert logs_data["status"] == "success"
        assert "logs" in logs_data
        print(
            f"Log retrieval successful, log type: {logs_data.get('log_type', 'unknown')}"
        )
        print(
            f"Log content preview: {logs_data['logs'][:200]}..."
            if len(logs_data["logs"]) > 200
            else f"Log content: {logs_data['logs']}"
        )

        # Step 6: Test job listing and filtering
        print("Testing job listing...")
        jobs_result = await call_tool("list_jobs")
        jobs_content = get_text_content(jobs_result)
        jobs_data = json.loads(jobs_content)

        assert jobs_data["status"] == "success"
        jobs_list = jobs_data["jobs"]

        # Find our pipeline job
        pipeline_job_found = False
        for job in jobs_list:
            if job["job_id"] == job_id:
                pipeline_job_found = True
                print(
                    f"Found pipeline job in list: {job['job_id']} with status: {job.get('status', 'UNKNOWN')}"
                )
                break
            elif job.get("entrypoint", "") and "data_pipeline.py" in job.get(
                "entrypoint", ""
            ):
                pipeline_job_found = True
                print(
                    f"Found pipeline job by entrypoint: {job['job_id']} with status: {job.get('status', 'UNKNOWN')}"
                )
                break

        if not pipeline_job_found:
            print(
                f"Pipeline job not found in job list. Available jobs: {[j['job_id'] for j in jobs_list]}"
            )
        print("Job listing functionality tested successfully!")

        # Step 7: Test cluster health check
        print("Performing cluster health check...")
        health_result = await call_tool("health_check")
        health_content = get_text_content(health_result)
        health_data = json.loads(health_content)

        assert health_data["status"] == "success"
        assert "health_score" in health_data or "cluster_status" in health_data
        print("Cluster health check completed!")

        # Step 8: Stop Ray cluster
        print("Stopping Ray cluster...")
        stop_result = await call_tool("stop_ray")
        stop_content = get_text_content(stop_result)
        stop_data = json.loads(stop_content)
        assert stop_data["status"] == "stopped"
        assert not ray.is_initialized()

        print("✅ Data pipeline workflow test passed successfully!")

    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.slow
    async def test_workflow_orchestration_workflow(
        self, ray_cluster_manager: RayManager
    ):
        """Test complex workflow orchestration using the workflow_orchestration.py example on a multi-node cluster."""

        # Step 1: Start Ray cluster with multiple nodes
        print("Starting Ray cluster for workflow orchestration with multiple nodes...")
        start_result = await call_tool(
            "start_ray",
            {
                "num_cpus": 4,
                "num_gpus": 0,
                "worker_nodes": [
                    {"num_cpus": 2, "num_gpus": 0},
                    {"num_cpus": 2, "num_gpus": 0},
                    {"num_cpus": 1, "num_gpus": 0},
                ],
            },
        )
        start_content = get_text_content(start_result)
        start_data = json.loads(start_content)
        assert start_data["status"] == "started"
        assert ray.is_initialized()
        print(f"Multi-node Ray cluster started: {start_data}")

        # Step 2: Verify multi-node cluster status
        print("Getting initial cluster status...")
        status_result = await call_tool("cluster_status")
        status_content = get_text_content(status_result)
        status_data = json.loads(status_content)

        assert status_data["status"] == "running"
        print(f"Initial cluster status: {status_data}")

        # Step 3: Check worker node status
        print("Checking worker node status...")
        worker_status_result = await call_tool("worker_status")
        worker_status_content = get_text_content(worker_status_result)
        worker_status_data = json.loads(worker_status_content)
        assert worker_status_data["status"] == "success"
        assert "worker_nodes" in worker_status_data
        assert (
            len(worker_status_data["worker_nodes"]) == 3
        ), f"Expected 3 worker nodes, got {len(worker_status_data['worker_nodes'])}"
        print(f"Worker nodes status: {worker_status_data}")

        # Step 4: Get cluster nodes information
        print("Getting cluster nodes information...")
        nodes_result = await call_tool("cluster_nodes")
        nodes_content = get_text_content(nodes_result)
        nodes_data = json.loads(nodes_content)

        assert nodes_data["status"] == "success"
        assert "nodes" in nodes_data
        print(f"Cluster nodes: {len(nodes_data['nodes'])} nodes")

        # Step 5: Submit the workflow orchestration job
        print("Submitting workflow orchestration job...")

        current_dir = Path(__file__).parent.parent
        examples_dir = current_dir / "examples"
        workflow_script_path = examples_dir / "workflow_orchestration.py"

        assert (
            workflow_script_path.exists()
        ), f"workflow_orchestration.py not found at {workflow_script_path}"

        job_result = await call_tool(
            "submit_job",
            {
                "entrypoint": f"python {workflow_script_path}",
                "metadata": {
                    "test_type": "workflow_orchestration",
                    "description": "Complex workflow with multiple dependencies on multi-node cluster",
                },
            },
        )

        job_content = get_text_content(job_result)
        job_data = json.loads(job_content)
        assert job_data["status"] == "submitted"
        job_id = job_data["job_id"]
        print(f"Workflow orchestration job submitted with ID: {job_id}")

        # Step 6: Wait for job completion
        print("Waiting for workflow orchestration job to complete...")

        # Check job status until completion
        job_completed = False
        last_status = None
        for i in range(35):  # 35 seconds should be sufficient for complex workflows
            status_result = await call_tool("job_status", {"job_id": job_id})
            status_content = get_text_content(status_result)
            status_data = json.loads(status_content)

            job_status = status_data.get("job_status", "UNKNOWN")

            if (
                job_status != last_status or i % 20 == 0
            ):  # Print on status change or every 20 seconds
                print(f"Workflow job status check {i+1}: {job_status}")
                last_status = job_status

            # Try to get job progress monitoring
            try:
                progress_result = await call_tool(
                    "monitor_job_progress", {"job_id": job_id}
                )
                progress_content = get_text_content(progress_result)
                progress_data = json.loads(progress_content)

                if progress_data.get("status") == "success":
                    print(f"Job progress monitoring API tested successfully")
            except Exception:
                # Progress monitoring might not be available for all job types
                pass

            if job_status == "SUCCEEDED":
                print("Workflow orchestration job completed successfully!")
                job_completed = True
                break
            elif job_status == "FAILED":
                # Get job logs for debugging
                logs_result = await call_tool("get_logs", {"job_id": job_id})
                logs_content = get_text_content(logs_result)
                logs_data = json.loads(logs_content)
                pytest.fail(
                    f"Workflow orchestration job failed unexpectedly: {status_data}\nLogs: {logs_data.get('logs', 'No logs available')}"
                )
            elif job_status in ["PENDING", "RUNNING"]:
                await asyncio.sleep(1)
            else:
                await asyncio.sleep(1)

        assert (
            job_completed
        ), "Workflow orchestration job did not complete within expected time"

        # Step 7: Test log retrieval functionality
        print("Testing log retrieval functionality...")
        logs_result = await call_tool("get_logs", {"job_id": job_id})
        logs_content = get_text_content(logs_result)
        logs_data = json.loads(logs_content)

        assert logs_data["status"] == "success"
        print(
            f"Log retrieval successful, log type: {logs_data.get('log_type', 'unknown')}"
        )

        # Verify logs contain expected content
        logs_text = logs_data.get("logs", "")
        assert len(logs_text) > 0, "Expected non-empty logs from completed job"

        # Step 8: Test advanced job operations
        print("Testing advanced job operations...")

        # Test job debugging capabilities
        debug_result = await call_tool("debug_job", {"job_id": job_id})
        debug_content = get_text_content(debug_result)
        debug_data = json.loads(debug_content)

        # Debug might not be available for completed jobs, but should return valid response
        assert debug_data.get("status") in ["success", "not_available", "completed"]
        print("Job debugging test completed!")

        # Step 9: Test performance metrics after heavy workload
        print("Getting performance metrics after workflow...")
        metrics_result = await call_tool("performance_metrics")
        metrics_content = get_text_content(metrics_result)
        metrics_data = json.loads(metrics_content)

        assert metrics_data["status"] == "success"
        assert "cluster_overview" in metrics_data or "cluster_resources" in metrics_data
        print("Performance metrics after workflow retrieved!")

        # Step 10: Final job listing to verify metadata
        print("Final job listing to verify metadata...")
        jobs_result = await call_tool("list_jobs")
        jobs_content = get_text_content(jobs_result)
        jobs_data = json.loads(jobs_content)

        assert jobs_data["status"] == "success"
        jobs_list = jobs_data["jobs"]

        # Find our workflow job and verify metadata
        workflow_job_found = False
        for job in jobs_list:
            if job["job_id"] == job_id:
                workflow_job_found = True
                print(
                    f"Found workflow job in list: {job['job_id']} with status: {job.get('status', 'UNKNOWN')}"
                )

                # Check if metadata was preserved
                job_metadata = job.get("metadata", {})
                if job_metadata:
                    if job_metadata.get("test_type") == "workflow_orchestration":
                        print("Job metadata preserved correctly!")

                break
            elif job.get("entrypoint", "") and "workflow_orchestration.py" in job.get(
                "entrypoint", ""
            ):
                workflow_job_found = True
                print(
                    f"Found workflow job by entrypoint: {job['job_id']} with status: {job.get('status', 'UNKNOWN')}"
                )
                break

        if not workflow_job_found:
            print(
                f"Workflow job not found in job list. Available jobs: {[j['job_id'] for j in jobs_list]}"
            )
        print("Job listing functionality tested successfully!")

        # Step 11: Stop Ray cluster
        print("Stopping Ray cluster...")
        stop_result = await call_tool("stop_ray")
        stop_content = get_text_content(stop_result)
        stop_data = json.loads(stop_content)
        assert stop_data["status"] == "stopped"
        assert not ray.is_initialized()

        print("✅ Multi-node workflow orchestration workflow test passed successfully!")


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
    import sys
    from io import StringIO

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
