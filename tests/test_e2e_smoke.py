#!/usr/bin/env python3
"""Fast smoke tests for critical Ray MCP functionality.

These tests provide rapid validation of the most essential workflows
to catch major regressions quickly. They are designed to run in under 2 minutes
and test the absolute critical paths.
"""

import pytest

from tests.conftest import (
    TestScripts,
    call_tool,
    parse_tool_result,
    start_ray_cluster,
    stop_ray_cluster,
    submit_and_wait_for_job,
    E2EConfig,
)


@pytest.mark.e2e
@pytest.mark.smoke
class TestRayMCPSmoke:
    """Fast smoke tests for essential Ray MCP functionality."""

    @pytest.mark.asyncio
    async def test_critical_path_smoke(self):
        """Ultra-fast smoke test covering the most critical user journey."""
        
        print("💨 Running critical path smoke test...")
        
        # 1. Quick cluster start
        print("🚀 Quick cluster start...")
        cluster_data = await start_ray_cluster(cpu_limit=1)
        assert cluster_data["status"] == "success"
        print("✅ Cluster started")
        
        # 2. Submit lightweight job
        print("📋 Submit job...")
        job_id, job_status = await submit_and_wait_for_job(
            TestScripts.LIGHTWEIGHT_SUCCESS,
            expected_status="SUCCEEDED",
            max_wait=10  # Fast timeout
        )
        assert job_status["job_status"] == "SUCCEEDED"
        print(f"✅ Job completed: {job_id}")
        
        # 3. Quick log check
        print("📜 Check logs...")
        logs_result = await call_tool("retrieve_logs", {
            "identifier": job_id,
            "log_type": "job",
            "num_lines": 10
        })
        logs_data = parse_tool_result(logs_result)
        assert logs_data["status"] == "success"
        assert len(logs_data["logs"]) > 0
        print("✅ Logs retrieved")
        
        # 4. Quick cleanup
        print("🛑 Cleanup...")
        await stop_ray_cluster()
        print("✅ Critical path smoke test passed!")

    @pytest.mark.asyncio
    async def test_api_surface_smoke(self):
        """Fast validation that all main API endpoints are functional."""
        
        print("🔌 Testing API surface...")
        
        await start_ray_cluster(cpu_limit=1)
        
        # Test core API endpoints quickly
        endpoints_to_test = [
            ("inspect_ray", {}),
            ("list_jobs", {}),
        ]
        
        for endpoint, args in endpoints_to_test:
            print(f"Testing {endpoint}...")
            result = await call_tool(endpoint, args)
            data = parse_tool_result(result)
            assert data["status"] in ["success", "not_running"], f"{endpoint} failed: {data}"
        
        print("✅ Core API endpoints working")
        
        # Quick job test
        job_id, _ = await submit_and_wait_for_job(
            TestScripts.LIGHTWEIGHT_SUCCESS,
            expected_status="SUCCEEDED",
            max_wait=8
        )
        
        # Test job-related endpoints
        job_endpoints = [
            ("inspect_job", {"job_id": job_id, "mode": "status"}),
            ("retrieve_logs", {"identifier": job_id, "log_type": "job"}),
        ]
        
        for endpoint, args in job_endpoints:
            print(f"Testing {endpoint}...")
            result = await call_tool(endpoint, args)
            data = parse_tool_result(result)
            assert data["status"] == "success", f"{endpoint} failed: {data}"
        
        await stop_ray_cluster()
        print("✅ API surface smoke test passed!")

    @pytest.mark.asyncio
    async def test_error_scenarios_smoke(self):
        """Fast test of critical error scenarios."""
        
        print("⚠️  Testing error scenarios...")
        
        await start_ray_cluster(cpu_limit=1)
        
        # Test 1: Invalid operations
        print("Testing invalid operations...")
        
        # Invalid log type
        result = await call_tool("retrieve_logs", {
            "identifier": "dummy",
            "log_type": "invalid"
        })
        data = parse_tool_result(result)
        assert data["status"] == "error"
        print("✅ Invalid log type handled")
        
        # Test 2: Failed job handling
        print("Testing failed job...")
        fail_job_id, fail_status = await submit_and_wait_for_job(
            TestScripts.INTENTIONAL_FAILURE,
            expected_status="FAILED",
            max_wait=8
        )
        assert fail_status["job_status"] == "FAILED"
        print(f"✅ Failed job handled: {fail_job_id}")
        
        # Should still be able to get logs from failed job
        logs_result = await call_tool("retrieve_logs", {
            "identifier": fail_job_id,
            "log_type": "job"
        })
        logs_data = parse_tool_result(logs_result)
        assert logs_data["status"] == "success"
        print("✅ Failed job logs retrieved")
        
        await stop_ray_cluster()
        print("✅ Error scenarios smoke test passed!")

    @pytest.mark.asyncio
    async def test_refactored_components_smoke(self):
        """Fast validation that refactored components work together."""
        
        print("🔧 Testing refactored components integration...")
        
        # Test that we're using the new unified manager
        print("Checking unified manager...")
        from ray_mcp.main import ray_manager
        from ray_mcp.core.unified_manager import RayUnifiedManager
        
        # Verify we're using the refactored architecture
        assert isinstance(ray_manager, RayUnifiedManager), "Should be using RayUnifiedManager"
        print("✅ Using refactored unified manager")
        
        # Test component access
        print("Testing component access...")
        state_manager = ray_manager.get_state_manager()
        cluster_manager = ray_manager.get_cluster_manager()
        job_manager = ray_manager.get_job_manager()
        log_manager = ray_manager.get_log_manager()
        port_manager = ray_manager.get_port_manager()
        
        assert state_manager is not None
        assert cluster_manager is not None
        assert job_manager is not None
        assert log_manager is not None
        assert port_manager is not None
        print("✅ All components accessible")
        
        # Test basic workflow
        print("Testing basic workflow...")
        await start_ray_cluster(cpu_limit=1)
        
        # Should show up in state
        assert ray_manager.is_initialized
        assert ray_manager.cluster_address is not None
        print("✅ State management working")
        
        # Quick job test
        job_id, _ = await submit_and_wait_for_job(
            TestScripts.LIGHTWEIGHT_SUCCESS,
            expected_status="SUCCEEDED",
            max_wait=8
        )
        
        # Components should work together
        logs_result = await call_tool("retrieve_logs", {
            "identifier": job_id,
            "log_type": "job"
        })
        logs_data = parse_tool_result(logs_result)
        assert logs_data["status"] == "success"
        print("✅ Components working together")
        
        await stop_ray_cluster()
        print("✅ Refactored components smoke test passed!")


@pytest.mark.e2e
@pytest.mark.smoke
class TestQuickRegression:
    """Extremely fast regression tests for deployment validation."""

    @pytest.mark.asyncio
    async def test_30_second_regression(self):
        """30-second regression test for deployment validation."""
        
        print("⚡ Running 30-second regression test...")
        
        import time
        start_time = time.time()
        
        # Ultra-minimal test
        cluster_data = await start_ray_cluster(cpu_limit=1)
        assert cluster_data["status"] == "success"
        
        # Simplest possible job
        job_id, job_status = await submit_and_wait_for_job(
            'print("Hello Ray MCP!")',
            expected_status="SUCCEEDED",
            max_wait=5
        )
        assert job_status["job_status"] == "SUCCEEDED"
        
        # Quick status check
        status_result = await call_tool("inspect_ray")
        status_data = parse_tool_result(status_result)
        assert status_data["status"] == "success"
        
        await stop_ray_cluster()
        
        elapsed = time.time() - start_time
        print(f"✅ 30-second regression test completed in {elapsed:.1f}s")
        
        # Should complete well under 30 seconds
        assert elapsed < 30, f"Test took too long: {elapsed:.1f}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "smoke"]) 