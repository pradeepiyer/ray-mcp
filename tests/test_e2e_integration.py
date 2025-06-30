#!/usr/bin/env python3
"""End-to-end integration tests for the Ray MCP server."""

import pytest
import pytest_asyncio

from ray_mcp.ray_manager import RayManager
from tests.conftest import (
    E2EConfig,
    TestScripts,
    call_tool,
    parse_tool_result,
    start_ray_cluster,
    stop_ray_cluster,
    submit_and_wait_for_job,
    verify_cluster_status,
)


@pytest.mark.e2e
class TestE2EIntegration:
    """End-to-end integration tests that test the complete workflow without mocking."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_complete_ray_workflow(self, e2e_ray_manager: RayManager):
        """Test the complete Ray workflow: start cluster, submit job, verify results, cleanup."""
        
        # Step 1: Start Ray cluster using MCP tools
        await start_ray_cluster()

        # Step 2: Verify cluster status
        await verify_cluster_status()

        # Step 3: Submit and wait for job completion
        job_id, job_status = await submit_and_wait_for_job(
            TestScripts.QUICK_SUCCESS,
            expected_status="SUCCEEDED"
        )
        print(f"Job {job_id} completed successfully!")

        # Step 4: Test job listing functionality
        print("Testing job listing functionality...")
        jobs_result = await call_tool("list_jobs")
        jobs_data = parse_tool_result(jobs_result)
        assert jobs_data["status"] == "success"
        print(f"Found {len(jobs_data['jobs'])} jobs in the cluster")

        # Step 5: Stop Ray cluster
        await stop_ray_cluster()

        print("✅ Complete end-to-end test passed successfully!")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_job_failure_and_debugging_workflow(self, e2e_ray_manager: RayManager):
        """Test job failure handling, debugging, and recovery workflows."""

        # Step 1: Start Ray cluster
        await start_ray_cluster()
        print("Ray cluster started for failure testing")

        # Step 2: Submit a job that will fail
        print("Submitting a job designed to fail...")
        fail_job_id, fail_status = await submit_and_wait_for_job(
            TestScripts.INTENTIONAL_FAILURE,
            expected_status="FAILED"
        )
        print(f"Failing job {fail_job_id} failed as expected")

        # Step 3: Test log retrieval functionality
        print("Testing log retrieval functionality...")
        logs_result = await call_tool(
            "retrieve_logs", {"identifier": fail_job_id, "log_type": "job"}
        )
        logs_data = parse_tool_result(logs_result)
        assert logs_data["status"] == "success"
        print("Log retrieval successful")

        # Step 4: Debug the failed job
        print("Debugging the failed job...")
        debug_result = await call_tool(
            "inspect_job", {"job_id": fail_job_id, "mode": "debug"}
        )
        debug_data = parse_tool_result(debug_result)
        assert debug_data["status"] == "success"
        assert "debug_info" in debug_data
        print("Debug functionality working")

        # Step 5: Test a lightweight success job to verify cluster health
        print("Testing lightweight success job...")
        success_job_id, success_status = await submit_and_wait_for_job(
            TestScripts.LIGHTWEIGHT_SUCCESS,
            expected_status="SUCCEEDED",
            runtime_env={}
        )
        print(f"Success job {success_job_id} completed successfully!")

        # Step 6: List all jobs to verify both are recorded
        print("Listing all jobs...")
        jobs_result = await call_tool("list_jobs")
        jobs_data = parse_tool_result(jobs_result)
        assert jobs_data["status"] == "success"
        print(f"Found {len(jobs_data['jobs'])} jobs in the cluster")

        # Step 7: Stop Ray cluster
        await stop_ray_cluster()

        print("✅ Job failure and debugging workflow test passed successfully!")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
