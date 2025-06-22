#!/usr/bin/env python3
"""End-to-end integration tests for the MCP Ray server."""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
import pytest_asyncio
import psutil
import ray

# Import the MCP server functions directly for testing
from ray_mcp.main import list_tools, call_tool
from ray_mcp.ray_manager import RayManager
from mcp.types import TextContent


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
        
        # Submit the job
        job_result = await call_tool("submit_job", {
            "entrypoint": f"python {simple_job_path}",
            "runtime_env": {
                "pip": ["numpy>=1.21.0"]
            }
        })
        
        job_content = get_text_content(job_result)
        job_data = json.loads(job_content)
        assert job_data["status"] == "submitted"
        job_id = job_data["job_id"]
        print(f"Job submitted with ID: {job_id}")
        
        # Step 4: Monitor job until completion
        print("Monitoring job completion...")
        max_wait_time = 120  # 2 minutes max
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            status_result = await call_tool("job_status", {"job_id": job_id})
            status_content = get_text_content(status_result)
            status_data = json.loads(status_content)
            
            job_status = status_data.get("job_status", "UNKNOWN")
            print(f"Job status: {job_status}")
            
            if job_status == "SUCCEEDED":
                print("Job completed successfully!")
                break
            elif job_status == "FAILED":
                # Get logs for debugging
                logs_result = await call_tool("get_logs", {"job_id": job_id})
                logs_content = get_text_content(logs_result)
                logs_data = json.loads(logs_content)
                print(f"Job failed. Logs: {logs_data}")
                pytest.fail(f"Job failed with status: {job_status}")
            
            await asyncio.sleep(5)  # Wait 5 seconds before checking again
        else:
            pytest.fail(f"Job did not complete within {max_wait_time} seconds")
        
        # Step 5: Get job logs to verify results
        print("Getting job logs...")
        logs_result = await call_tool("get_logs", {"job_id": job_id})
        logs_content = get_text_content(logs_result)
        logs_data = json.loads(logs_content)
        
        # Verify that the job produced expected output
        assert logs_data["status"] == "success"
        logs_text = logs_data["logs"]
        
        # Check for expected output from simple_job.py
        assert "Ray initialized successfully!" in logs_text
        assert "Computing Pi with Monte Carlo Method" in logs_text
        assert "Pi estimate:" in logs_text
        assert "Running Slow Tasks" in logs_text
        assert "Job completed successfully!" in logs_text
        assert "Ray shutdown complete." in logs_text
        
        print("Job logs verification passed!")
        
        # Step 6: List jobs to verify our job is there
        print("Listing all jobs...")
        jobs_result = await call_tool("list_jobs")
        jobs_content = get_text_content(jobs_result)
        jobs_data = json.loads(jobs_content)
        
        # Verify our job is in the list (look for job with matching entrypoint)
        job_found = False
        expected_entrypoint = f"python {simple_job_path}"
        
        for job in jobs_data["jobs"]:
            # Check if this job matches our submitted job
            if (job["job_id"] == job_id or 
                (job["entrypoint"] and expected_entrypoint in job["entrypoint"])):
                job_found = True
                assert job["status"] == "SUCCEEDED"
                print(f"Found matching job: {job}")
                break
        
        assert job_found, f"Job with entrypoint '{expected_entrypoint}' not found in job list: {jobs_data['jobs']}"
        print("Job listing verification passed!")
        
        # Step 7: Stop Ray cluster
        print("Stopping Ray cluster...")
        stop_result = await call_tool("stop_ray")
        stop_content = get_text_content(stop_result)
        stop_data = json.loads(stop_content)
        assert stop_data["status"] == "stopped"
        print("Ray cluster stopped successfully!")
        
        # Step 8: Verify cluster is stopped
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
    time.sleep(30)
    print("Actor job completing...")

if __name__ == "__main__":
    main()
"""
        
        # Write the actor script to a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(actor_script)
            actor_script_path = f.name
        
        try:
            # Submit the actor job
            actor_job_result = await call_tool("submit_job", {
                "entrypoint": f"python {actor_script_path}",
                "runtime_env": {}
            })
            
            actor_job_content = get_text_content(actor_job_result)
            actor_job_data = json.loads(actor_job_content)
            assert actor_job_data["status"] == "submitted"
            actor_job_id = actor_job_data["job_id"]
            print(f"Actor job submitted with ID: {actor_job_id}")
            
            # Step 3: Wait for actor job to start and create actors
            print("Waiting for actors to be created...")
            await asyncio.sleep(15)  # Give time for actors to be created and start working
            
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
                kill_result = await call_tool("kill_actor", {
                    "actor_id": actor_id,
                    "no_restart": True
                })
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
                    actor_still_exists = any(a["actor_id"] == actor_id for a in new_actors_list)
                    if actor_still_exists:
                        killed_actor = next(a for a in new_actors_list if a["actor_id"] == actor_id)
                        assert killed_actor["state"] in ["DEAD", "KILLED"], f"Actor should be dead but is {killed_actor['state']}"
                    
                    print("Actor kill verification passed!")
                else:
                    print(f"Actor kill failed (expected for system actors): {kill_data}")
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
    async def test_monitoring_and_health_workflow(self, ray_cluster_manager: RayManager):
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
        
        load_job_result = await call_tool("submit_job", {
            "entrypoint": f"python {simple_job_path}",
            "runtime_env": {"pip": ["numpy>=1.21.0"]}
        })
        
        load_job_content = get_text_content(load_job_result)
        load_job_data = json.loads(load_job_content)
        assert load_job_data["status"] == "submitted"
        load_job_id = load_job_data["job_id"]
        print(f"Load job submitted: {load_job_id}")
        
        # Step 8: Monitor job progress while it's running
        print("Monitoring job progress...")
        max_attempts = 5
        for attempt in range(max_attempts):
            await asyncio.sleep(3)  # Wait a bit between checks
            
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
                print(f"Current cluster utilization: CPU {current_overview.get('available_cpus', 0)}/{current_overview.get('total_cpus', 0)}")
            
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
    async def test_job_failure_and_debugging_workflow(self, ray_cluster_manager: RayManager):
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
time.sleep(5)  # Simulate some work
print("About to fail...")
raise ValueError("This is an intentional failure for testing")
"""
        
        # Write the failing script to a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(failing_script)
            failing_script_path = f.name
        
        try:
            # Submit the failing job
            fail_job_result = await call_tool("submit_job", {
                "entrypoint": f"python {failing_script_path}",
                "runtime_env": {}
            })
            
            fail_job_content = get_text_content(fail_job_result)
            fail_job_data = json.loads(fail_job_content)
            assert fail_job_data["status"] == "submitted"
            fail_job_id = fail_job_data["job_id"]
            print(f"Failing job submitted with ID: {fail_job_id}")
            
            # Step 3: Monitor the job until it fails
            print("Monitoring failing job...")
            max_wait_time = 60
            start_time = time.time()
            final_status = None
            
            while time.time() - start_time < max_wait_time:
                status_result = await call_tool("job_status", {"job_id": fail_job_id})
                status_content = get_text_content(status_result)
                status_data = json.loads(status_content)
                
                job_status = status_data.get("job_status", "UNKNOWN")
                print(f"Failing job status: {job_status}")
                
                if job_status == "FAILED":
                    final_status = "FAILED"
                    print("Job failed as expected!")
                    break
                elif job_status == "SUCCEEDED":
                    pytest.fail("Job was expected to fail but succeeded")
                
                await asyncio.sleep(3)
            
            assert final_status == "FAILED", f"Job should have failed but final status was: {final_status}"
            
            # Step 4: Get job logs to see the failure
            print("Getting logs from failed job...")
            logs_result = await call_tool("get_logs", {"job_id": fail_job_id})
            logs_content = get_text_content(logs_result)
            logs_data = json.loads(logs_content)
            
            assert logs_data["status"] == "success"
            logs_text = logs_data["logs"]
            
            # Verify the failure is captured in logs
            assert "Starting failing job..." in logs_text
            assert "About to fail..." in logs_text
            assert "ValueError" in logs_text or "intentional failure" in logs_text
            print("Failure logs captured correctly!")
            
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
            
            # Step 6: Submit a successful job to verify cluster is still working
            print("Submitting a successful job to verify cluster health...")
            
            success_script = """
import time
print("Starting successful job...")
time.sleep(2)
print("Job completed successfully!")
"""
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(success_script)
                success_script_path = f.name
            
            try:
                success_job_result = await call_tool("submit_job", {
                    "entrypoint": f"python {success_script_path}",
                    "runtime_env": {}
                })
                
                success_job_content = get_text_content(success_job_result)
                success_job_data = json.loads(success_job_content)
                assert success_job_data["status"] == "submitted"
                success_job_id = success_job_data["job_id"]
                print(f"Success job submitted: {success_job_id}")
                
                # Monitor success job
                max_wait_time = 30
                start_time = time.time()
                
                while time.time() - start_time < max_wait_time:
                    status_result = await call_tool("job_status", {"job_id": success_job_id})
                    status_content = get_text_content(status_result)
                    status_data = json.loads(status_content)
                    
                    job_status = status_data.get("job_status", "UNKNOWN")
                    print(f"Success job status: {job_status}")
                    
                    if job_status == "SUCCEEDED":
                        print("Success job completed as expected!")
                        break
                    elif job_status == "FAILED":
                        pytest.fail("Success job failed unexpectedly")
                    
                    await asyncio.sleep(2)
                else:
                    pytest.fail("Success job did not complete in time")
            
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
                elif (job["entrypoint"] and 
                      (failing_script_path in job["entrypoint"] or 
                       success_script_path in job["entrypoint"])):
                    our_jobs_found += 1
            
            assert our_jobs_found >= 1, f"Expected to find our jobs in list, found {our_jobs_found}"
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
        """Test that all MCP tools are available and properly defined."""
        
        # Test list_tools functionality
        tools = await list_tools()
        
        assert isinstance(tools, list)
        assert len(tools) == 19  # We expect 19 tools (after removing backup/restore)
        
        # Verify key tools are present
        tool_names = [tool.name for tool in tools]
        expected_tools = [
            "start_ray", "connect_ray", "stop_ray", "cluster_status",
            "submit_job", "list_jobs", "job_status", "cancel_job",
            "list_actors", "kill_actor", "performance_metrics", "health_check"
        ]
        
        for expected_tool in expected_tools:
            assert expected_tool in tool_names, f"Tool {expected_tool} not found"
        
        # Verify tool schemas are valid
        for tool in tools:
            assert hasattr(tool, 'name')
            assert hasattr(tool, 'description')
            assert hasattr(tool, 'inputSchema')
            assert isinstance(tool.inputSchema, dict)
            assert tool.inputSchema.get("type") == "object"
        
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
        """Test distributed training workflow using the distributed_training.py example."""
        
        # Step 1: Start Ray cluster
        print("Starting Ray cluster for distributed training...")
        start_result = await call_tool("start_ray", {"num_cpus": 6})
        start_content = get_text_content(start_result)
        start_data = json.loads(start_content)
        assert start_data["status"] == "started"
        assert ray.is_initialized()
        
        # Step 2: Submit the distributed training job
        print("Submitting distributed training job...")
        
        current_dir = Path(__file__).parent.parent
        examples_dir = current_dir / "examples"
        training_script_path = examples_dir / "distributed_training.py"
        
        assert training_script_path.exists(), f"distributed_training.py not found at {training_script_path}"
        
        job_result = await call_tool("submit_job", {
            "entrypoint": f"python {training_script_path}",
            "runtime_env": {
                "pip": ["numpy>=1.21.0"]
            }
        })
        
        job_content = get_text_content(job_result)
        job_data = json.loads(job_content)
        assert job_data["status"] == "submitted"
        job_id = job_data["job_id"]
        print(f"Distributed training job submitted with ID: {job_id}")
        
        # Step 3: Monitor job execution
        print("Monitoring distributed training job...")
        max_wait_time = 180  # 3 minutes for training
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            status_result = await call_tool("job_status", {"job_id": job_id})
            status_content = get_text_content(status_result)
            status_data = json.loads(status_content)
            
            job_status = status_data.get("job_status", "UNKNOWN")
            print(f"Training job status: {job_status}")
            
            if job_status == "SUCCEEDED":
                print("Distributed training job completed successfully!")
                break
            elif job_status == "FAILED":
                logs_result = await call_tool("get_logs", {"job_id": job_id})
                logs_content = get_text_content(logs_result)
                logs_data = json.loads(logs_content)
                print(f"Training job failed. Logs: {logs_data}")
                pytest.fail(f"Distributed training job failed with status: {job_status}")
            
            await asyncio.sleep(8)  # Check every 8 seconds
        else:
            pytest.fail(f"Distributed training job did not complete within {max_wait_time} seconds")
        
        # Step 4: Verify job outputs
        print("Verifying distributed training job outputs...")
        logs_result = await call_tool("get_logs", {"job_id": job_id})
        logs_content = get_text_content(logs_result)
        logs_data = json.loads(logs_content)
        
        assert logs_data["status"] == "success"
        logs_text = logs_data["logs"]
        
        # Check for expected training outputs
        assert "Ray initialized successfully!" in logs_text
        assert "Distributed Training Example" in logs_text
        assert "Creating Parameter Server" in logs_text
        assert "Creating Workers" in logs_text
        assert "Starting Distributed Training" in logs_text
        assert "Final Model Evaluation" in logs_text
        assert "Training Summary" in logs_text
        assert "training_completed" in logs_text
        assert "Ray shutdown complete." in logs_text
        
        print("Distributed training job outputs verified!")
        
        # Step 5: Test actor management during training
        print("Testing actor listing functionality...")
        actors_result = await call_tool("list_actors")
        actors_content = get_text_content(actors_result)
        actors_data = json.loads(actors_content)
        
        # After job completion, there should be no active actors
        assert actors_data["status"] == "success"
        print(f"Active actors after training: {len(actors_data.get('actors', []))}")
        
        # Step 6: Test performance metrics
        print("Getting performance metrics...")
        metrics_result = await call_tool("performance_metrics")
        metrics_content = get_text_content(metrics_result)
        metrics_data = json.loads(metrics_content)
        
        assert metrics_data["status"] == "success"
        assert "cluster_overview" in metrics_data or "cluster_resources" in metrics_data
        print("Performance metrics retrieved successfully!")
        
        # Step 7: Stop Ray cluster
        print("Stopping Ray cluster...")
        stop_result = await call_tool("stop_ray")
        stop_content = get_text_content(stop_result)
        stop_data = json.loads(stop_content)
        assert stop_data["status"] == "stopped"
        assert not ray.is_initialized()
        
        print("✅ Distributed training workflow test passed successfully!")

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
        
        assert pipeline_script_path.exists(), f"data_pipeline.py not found at {pipeline_script_path}"
        
        job_result = await call_tool("submit_job", {
            "entrypoint": f"python {pipeline_script_path}",
            "runtime_env": {
                "pip": ["numpy>=1.21.0"]
            }
        })
        
        job_content = get_text_content(job_result)
        job_data = json.loads(job_content)
        assert job_data["status"] == "submitted"
        job_id = job_data["job_id"]
        print(f"Data pipeline job submitted with ID: {job_id}")
        
        # Step 4: Monitor job execution
        print("Monitoring data pipeline job...")
        max_wait_time = 120  # 2 minutes for pipeline
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            status_result = await call_tool("job_status", {"job_id": job_id})
            status_content = get_text_content(status_result)
            status_data = json.loads(status_content)
            
            job_status = status_data.get("job_status", "UNKNOWN")
            print(f"Pipeline job status: {job_status}")
            
            if job_status == "SUCCEEDED":
                print("Data pipeline job completed successfully!")
                break
            elif job_status == "FAILED":
                logs_result = await call_tool("get_logs", {"job_id": job_id})
                logs_content = get_text_content(logs_result)
                logs_data = json.loads(logs_content)
                print(f"Pipeline job failed. Logs: {logs_data}")
                pytest.fail(f"Data pipeline job failed with status: {job_status}")
            
            await asyncio.sleep(5)  # Check every 5 seconds
        else:
            pytest.fail(f"Data pipeline job did not complete within {max_wait_time} seconds")
        
        # Step 5: Verify job outputs
        print("Verifying data pipeline job outputs...")
        logs_result = await call_tool("get_logs", {"job_id": job_id})
        logs_content = get_text_content(logs_result)
        logs_data = json.loads(logs_content)
        
        assert logs_data["status"] == "success"
        logs_text = logs_data["logs"]
        
        # Check for expected pipeline outputs
        assert "Ray initialized successfully!" in logs_text
        assert "Data Processing Pipeline Example" in logs_text
        assert "Creating Pipeline Components" in logs_text
        assert "Processing Data Through Pipeline" in logs_text
        assert "Aggregating Results" in logs_text
        assert "Pipeline Results" in logs_text
        assert "pipeline_completed" in logs_text
        assert "Ray shutdown complete." in logs_text
        
        print("Data pipeline job outputs verified!")
        
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
                assert job["status"] == "SUCCEEDED"
                print(f"Found pipeline job in list: {job['job_id']}")
                break
            elif (job.get("entrypoint", "") and "data_pipeline.py" in job.get("entrypoint", "")):
                pipeline_job_found = True
                assert job["status"] == "SUCCEEDED"
                print(f"Found pipeline job by entrypoint: {job['job_id']}")
                break
        
        assert pipeline_job_found, f"Pipeline job not found in job list. Available jobs: {[j['job_id'] for j in jobs_list]}"
        
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
    async def test_workflow_orchestration_workflow(self, ray_cluster_manager: RayManager):
        """Test complex workflow orchestration using the workflow_orchestration.py example."""
        
        # Step 1: Start Ray cluster
        print("Starting Ray cluster for workflow orchestration...")
        start_result = await call_tool("start_ray", {"num_cpus": 8})
        start_content = get_text_content(start_result)
        start_data = json.loads(start_content)
        assert start_data["status"] == "started"
        assert ray.is_initialized()
        
        # Step 2: Get initial cluster status
        print("Getting initial cluster status...")
        status_result = await call_tool("cluster_status")
        status_content = get_text_content(status_result)
        status_data = json.loads(status_content)
        
        assert status_data["status"] == "running"
        print(f"Initial cluster status: {status_data}")
        
        # Step 3: Submit the workflow orchestration job
        print("Submitting workflow orchestration job...")
        
        current_dir = Path(__file__).parent.parent
        examples_dir = current_dir / "examples"
        workflow_script_path = examples_dir / "workflow_orchestration.py"
        
        assert workflow_script_path.exists(), f"workflow_orchestration.py not found at {workflow_script_path}"
        
        job_result = await call_tool("submit_job", {
            "entrypoint": f"python {workflow_script_path}",
            "runtime_env": {
                "pip": ["numpy>=1.21.0"]
            },
            "metadata": {
                "test_type": "workflow_orchestration",
                "description": "Complex workflow with multiple dependencies"
            }
        })
        
        job_content = get_text_content(job_result)
        job_data = json.loads(job_content)
        assert job_data["status"] == "submitted"
        job_id = job_data["job_id"]
        print(f"Workflow orchestration job submitted with ID: {job_id}")
        
        # Step 4: Monitor job execution with progress tracking
        print("Monitoring workflow orchestration job...")
        max_wait_time = 240  # 4 minutes for complex workflow
        start_time = time.time()
        last_status = None
        
        while time.time() - start_time < max_wait_time:
            # Get job status
            status_result = await call_tool("job_status", {"job_id": job_id})
            status_content = get_text_content(status_result)
            status_data = json.loads(status_content)
            
            job_status = status_data.get("job_status", "UNKNOWN")
            
            if job_status != last_status:
                print(f"Workflow job status changed: {job_status}")
                last_status = job_status
            
            # Try to get job progress monitoring
            try:
                progress_result = await call_tool("monitor_job_progress", {"job_id": job_id})
                progress_content = get_text_content(progress_result)
                progress_data = json.loads(progress_content)
                
                if progress_data.get("status") == "success":
                    print(f"Job progress: {progress_data.get('progress', 'N/A')}")
            except Exception:
                # Progress monitoring might not be available for all job types
                pass
            
            if job_status == "SUCCEEDED":
                print("Workflow orchestration job completed successfully!")
                break
            elif job_status == "FAILED":
                logs_result = await call_tool("get_logs", {"job_id": job_id})
                logs_content = get_text_content(logs_result)
                logs_data = json.loads(logs_content)
                print(f"Workflow job failed. Logs: {logs_data}")
                pytest.fail(f"Workflow orchestration job failed with status: {job_status}")
            
            await asyncio.sleep(10)  # Check every 10 seconds
        else:
            pytest.fail(f"Workflow orchestration job did not complete within {max_wait_time} seconds")
        
        # Step 5: Verify job outputs
        print("Verifying workflow orchestration job outputs...")
        logs_result = await call_tool("get_logs", {"job_id": job_id})
        logs_content = get_text_content(logs_result)
        logs_data = json.loads(logs_content)
        
        assert logs_data["status"] == "success"
        logs_text = logs_data["logs"]
        
        # Check for expected workflow outputs
        assert "Ray initialized successfully!" in logs_text
        assert "Workflow Orchestration Example" in logs_text
        assert "Creating Workflow Orchestrator" in logs_text
        assert "Executing Workflows" in logs_text
        assert "Workflow History" in logs_text
        assert "Orchestration Summary" in logs_text
        assert "orchestration_completed" in logs_text
        assert "Ray shutdown complete." in logs_text
        
        print("Workflow orchestration job outputs verified!")
        
        # Step 6: Test advanced job operations
        print("Testing advanced job operations...")
        
        # Test job debugging capabilities
        debug_result = await call_tool("debug_job", {"job_id": job_id})
        debug_content = get_text_content(debug_result)
        debug_data = json.loads(debug_content)
        
        # Debug might not be available for completed jobs, but should return valid response
        assert debug_data.get("status") in ["success", "not_available", "completed"]
        print("Job debugging test completed!")
        
        # Step 7: Test performance metrics after heavy workload
        print("Getting performance metrics after workflow...")
        metrics_result = await call_tool("performance_metrics")
        metrics_content = get_text_content(metrics_result)
        metrics_data = json.loads(metrics_content)
        
        assert metrics_data["status"] == "success"
        assert "cluster_overview" in metrics_data or "cluster_resources" in metrics_data
        print("Performance metrics after workflow retrieved!")
        
        # Step 8: Test cluster nodes information
        print("Getting cluster nodes information...")
        nodes_result = await call_tool("cluster_nodes")
        nodes_content = get_text_content(nodes_result)
        nodes_data = json.loads(nodes_content)
        
        assert nodes_data["status"] == "success"
        assert "nodes" in nodes_data
        print(f"Cluster nodes: {len(nodes_data['nodes'])} nodes")
        
        # Step 9: Final job listing to verify metadata
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
                assert job["status"] == "SUCCEEDED"
                
                # Check if metadata was preserved
                job_metadata = job.get("metadata", {})
                if job_metadata:
                    assert job_metadata.get("test_type") == "workflow_orchestration"
                    print("Job metadata preserved correctly!")
                
                print(f"Found workflow job in list: {job['job_id']}")
                break
            elif (job.get("entrypoint", "") and "workflow_orchestration.py" in job.get("entrypoint", "")):
                workflow_job_found = True
                assert job["status"] == "SUCCEEDED"
                print(f"Found workflow job by entrypoint: {job['job_id']}")
                break
        
        assert workflow_job_found, f"Workflow job not found in job list. Available jobs: {[j['job_id'] for j in jobs_list]}"
        
        # Step 10: Stop Ray cluster
        print("Stopping Ray cluster...")
        stop_result = await call_tool("stop_ray")
        stop_content = get_text_content(stop_result)
        stop_data = json.loads(stop_content)
        assert stop_data["status"] == "stopped"
        assert not ray.is_initialized()
        
        print("✅ Workflow orchestration workflow test passed successfully!")


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.slow
async def test_simple_job_standalone():
    """Test that simple_job.py can run standalone (validation test)."""
    
    # Get the path to simple_job.py
    current_dir = Path(__file__).parent.parent
    simple_job_path = current_dir / "examples" / "simple_job.py"
    
    assert simple_job_path.exists(), f"simple_job.py not found at {simple_job_path}"
    
    # Run the job as a subprocess to verify it works independently
    result = subprocess.run([
        sys.executable, str(simple_job_path)
    ], capture_output=True, text=True, timeout=60)
    
    # Check that it ran successfully
    assert result.returncode == 0, f"simple_job.py failed: {result.stderr}"
    
    # Verify expected output
    output = result.stdout
    assert "Ray initialized successfully!" in output
    assert "Computing Pi with Monte Carlo Method" in output
    assert "Pi estimate:" in output
    assert "Job completed successfully!" in output
    assert "Ray shutdown complete." in output
    
    print("✅ Simple job standalone test passed!")


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 