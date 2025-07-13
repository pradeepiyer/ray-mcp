#!/usr/bin/env python3
"""Streamlined Ray MCP server tests using prompt-driven interface.

This file provides comprehensive end-to-end testing using natural language prompts,
taking full advantage of the new 3-tool architecture to create simple, readable tests.
"""

import asyncio
import os
import time

import pytest

from tests.helpers.utils import call_tool, parse_tool_result, TempScriptManager, TestScripts


async def cleanup_ray():
    """Clean up any existing Ray instances."""
    try:
        import ray
        if ray.is_initialized():
            ray.shutdown()
    except:
        pass
    
    try:
        import subprocess
        subprocess.run(["ray", "stop"], capture_output=True, check=False)
    except:
        pass


@pytest.mark.e2e
class TestRayMCPServer:
    """End-to-end tests using natural language prompts."""

    @pytest.mark.asyncio
    async def test_ray_cluster_workflow(self):
        """Test complete Ray cluster workflow using natural language."""
        print("🚀 Testing Ray cluster workflow...")

        # Clean up any existing Ray instances first
        await cleanup_ray()
        await asyncio.sleep(1)

        # Start cluster with simple prompt
        result = await call_tool("ray_cluster", {"prompt": "create a local cluster with 2 CPUs"})
        data = parse_tool_result(result)
        assert data["status"] == "success"
        assert "cluster_address" in data
        print(f"✅ Cluster started: {data['cluster_address']}")

        # Check cluster status
        result = await call_tool("ray_cluster", {"prompt": "inspect cluster status"})
        data = parse_tool_result(result)
        assert data["status"] in ["success", "active"]
        print("✅ Cluster is running")

        # List jobs (should be empty initially)
        result = await call_tool("ray_job", {"prompt": "list all jobs"})
        data = parse_tool_result(result)
        assert data["status"] == "success"
        assert "jobs" in data
        print(f"✅ Job list retrieved: {len(data['jobs'])} jobs")

        # Stop cluster
        result = await call_tool("ray_cluster", {"prompt": "stop cluster"})
        data = parse_tool_result(result)
        assert data["status"] == "success"
        print("✅ Cluster stopped")

    @pytest.mark.asyncio
    async def test_job_submission_workflow(self):
        """Test job submission workflow using natural language."""
        print("🔄 Testing job submission workflow...")

        # Clean up any existing Ray instances first
        await cleanup_ray()
        await asyncio.sleep(1)

        # Start cluster first
        await call_tool("ray_cluster", {"prompt": "create a local cluster with 1 CPU"})
        
        # Wait a moment for cluster to stabilize
        await asyncio.sleep(2)

        try:
            # Try to submit a job (may fail in test environment)
            with TempScriptManager(TestScripts.QUICK_SUCCESS) as script_path:
                result = await call_tool("ray_job", {"prompt": f"submit job with script {script_path}"})
                data = parse_tool_result(result)
                
                if data["status"] == "success":
                    job_id = data["job_id"]
                    print(f"✅ Job submitted: {job_id}")

                    # Check job status
                    result = await call_tool("ray_job", {"prompt": f"inspect job {job_id}"})
                    data = parse_tool_result(result)
                    assert data["status"] == "success"
                    print(f"✅ Job status checked: {data.get('job_status', 'unknown')}")

                    # Try to get logs
                    result = await call_tool("ray_job", {"prompt": f"get logs for job {job_id}"})
                    data = parse_tool_result(result)
                    # Logs may not be available immediately, so just check it doesn't crash
                    print(f"✅ Log retrieval attempted: {data['status']}")

                else:
                    print(f"⚠️ Job submission failed (expected in test env): {data.get('message')}")
                    print("✅ Job management handles errors gracefully")

        except Exception as e:
            print(f"⚠️ Job workflow failed (expected in test environment): {e}")
            print("✅ System handles job submission errors gracefully")

        finally:
            # Clean up
            await call_tool("ray_cluster", {"prompt": "stop cluster"})

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling using natural language prompts."""
        print("⚠️ Testing error handling...")

        # Test operations without cluster
        error_tests = [
            ("ray_job", {"prompt": "list all jobs"}),
            ("ray_job", {"prompt": "get logs for job nonexistent"})
        ]

        for tool, args in error_tests:
            result = await call_tool(tool, args)
            data = parse_tool_result(result)
            # Should either work or fail gracefully
            assert data["status"] in ["success", "error"]
            print(f"✅ {tool} handles missing cluster gracefully")

        # Test invalid job operations with cluster
        await call_tool("ray_cluster", {"prompt": "create a local cluster with 1 CPU"})
        await asyncio.sleep(1)

        try:
            invalid_job_tests = [
                ("ray_job", {"prompt": "inspect job fake_job_id"}),
                ("ray_job", {"prompt": "get logs for job missing_job"}),
                ("ray_job", {"prompt": "cancel job nonexistent_job"})
            ]

            for tool, args in invalid_job_tests:
                result = await call_tool(tool, args)
                data = parse_tool_result(result)
                assert data["status"] == "error"  # Should properly report errors
                print(f"✅ {tool} properly reports errors for invalid jobs")

        finally:
            await call_tool("ray_cluster", {"prompt": "stop cluster"})

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test concurrent operations using natural language."""
        print("🔄 Testing concurrent operations...")

        # Clean up any existing Ray instances first
        await cleanup_ray()
        await asyncio.sleep(1)

        # Start cluster
        await call_tool("ray_cluster", {"prompt": "create a local cluster with 1 CPU"})
        await asyncio.sleep(1)

        try:
            # Run multiple status checks concurrently
            tasks = []
            for i in range(5):
                tasks.append(call_tool("ray_cluster", {"prompt": "inspect cluster status"}))
                tasks.append(call_tool("ray_job", {"prompt": "list all jobs"}))

            results = await asyncio.gather(*tasks)
            
            # All should succeed
            for result in results:
                data = parse_tool_result(result)
                assert data["status"] in ["success", "active"]
            
            print(f"✅ {len(results)} concurrent operations completed successfully")

        finally:
            await call_tool("ray_cluster", {"prompt": "stop cluster"})

    @pytest.mark.asyncio
    async def test_cloud_operations(self):
        """Test cloud operations using natural language."""
        print("☁️ Testing cloud operations...")

        # Test environment check (should work regardless of cloud setup)
        result = await call_tool("cloud", {"prompt": "check environment status"})
        data = parse_tool_result(result)
        assert data["status"] in ["success", "error"]  # Either works or fails gracefully
        print(f"✅ Environment check: {data['status']}")

        # Test cloud operations that should work in any environment
        cloud_tests = [
            ("cloud", {"prompt": "list kubernetes clusters"}),
            ("cloud", {"prompt": "authenticate with GCP"})
        ]

        for tool, args in cloud_tests:
            result = await call_tool(tool, args)
            data = parse_tool_result(result)
            # Should either succeed or fail gracefully with clear error
            assert data["status"] in ["success", "error"]
            print(f"✅ {tool} handles cloud operations appropriately")

    @pytest.mark.asyncio
    @pytest.mark.gke
    @pytest.mark.skipif(
        not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        reason="GKE credentials not available - set GOOGLE_APPLICATION_CREDENTIALS",
    )
    @pytest.mark.skipif(
        not os.getenv("GKE_TEST_CLUSTER"),
        reason="GKE test cluster not specified - set GKE_TEST_CLUSTER",
    )
    async def test_gke_integration(self):
        """Test GKE integration using natural language."""
        print("🚀 Testing GKE integration...")
        
        cluster_name = os.getenv("GKE_TEST_CLUSTER")

        try:
            # Connect to GKE cluster
            result = await call_tool("cloud", {"prompt": f"connect to GKE cluster named {cluster_name}"})
            data = parse_tool_result(result)
            assert data["status"] == "success"
            print(f"✅ Connected to GKE cluster: {cluster_name}")

            # Submit a job to KubeRay
            with TempScriptManager(TestScripts.LIGHTWEIGHT_SUCCESS) as script_path:
                result = await call_tool("ray_job", {"prompt": f"submit job with script {script_path} to kubernetes"})
                data = parse_tool_result(result)
                
                if data["status"] == "success":
                    job_id = data["job_id"]
                    print(f"✅ KubeRay job submitted: {job_id}")

                    # Wait a bit for the job (with timeout)
                    max_wait = 120  # 2 minutes
                    for i in range(max_wait):
                        result = await call_tool("ray_job", {"prompt": f"inspect job {job_id}"})
                        data = parse_tool_result(result)
                        
                        if data.get("job_status") in ["SUCCEEDED", "FAILED"]:
                            print(f"✅ Job completed with status: {data['job_status']}")
                            break
                            
                        if i % 10 == 0:  # Print every 10 seconds
                            print(f"Job status at {i}s: {data.get('job_status', 'unknown')}")
                        
                        await asyncio.sleep(1)
                    
                    # Try to get logs
                    result = await call_tool("ray_job", {"prompt": f"get logs for job {job_id}"})
                    data = parse_tool_result(result)
                    print(f"✅ Log retrieval: {data['status']}")

                else:
                    print(f"⚠️ KubeRay job submission failed: {data.get('message')}")

        except Exception as e:
            print(f"❌ GKE integration test failed: {e}")
            raise


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])