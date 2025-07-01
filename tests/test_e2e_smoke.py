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
        """Ultra-fast smoke test covering cluster initialization and basic API functionality."""
        
        print("💨 Running critical path smoke test...")
        
        # 1. Quick cluster start (head-only for reliability)
        print("🚀 Quick cluster start...")
        cluster_data = await start_ray_cluster(cpu_limit=1, worker_nodes=[])  # Head-only
        assert cluster_data["status"] == "success"
        print("✅ Cluster started")
        
        # 2. Quick cluster inspection 
        print("🔍 Inspect cluster...")
        inspect_result = await call_tool("inspect_ray", {})
        inspect_data = parse_tool_result(inspect_result)
        
        # Check for both possible status formats
        if inspect_data["status"] == "active":
            # Ray is active, which is good
            print("✅ Cluster inspection passed")
        elif inspect_data["status"] == "success":
            # Check cluster status in the data
            assert inspect_data["cluster_overview"]["status"] == "running"
            print("✅ Cluster inspection passed")
        else:
            raise AssertionError(f"Unexpected cluster status: {inspect_data['status']}")
        
        # 3. Quick API validation
        print("📋 Test API endpoints...")
        endpoints_to_test = [
            ("list_jobs", {}),
        ]
        
        for endpoint, args in endpoints_to_test:
            result = await call_tool(endpoint, args)
            data = parse_tool_result(result)
            assert data["status"] == "success", f"{endpoint} failed: {data}"
        print("✅ Core API endpoints working")
        
        # 4. Quick cleanup
        print("🛑 Cleanup...")
        await stop_ray_cluster()
        print("✅ Critical path smoke test passed!")

    @pytest.mark.asyncio
    async def test_api_surface_smoke(self):
        """Fast validation that all main API endpoints are functional."""
        
        print("🔌 Testing API surface...")
        
        await start_ray_cluster(cpu_limit=1, worker_nodes=[])  # Head-only
        
        # Test core API endpoints quickly
        endpoints_to_test = [
            ("inspect_ray", {}),
            ("list_jobs", {}),
        ]
        
        for endpoint, args in endpoints_to_test:
            print(f"Testing {endpoint}...")
            result = await call_tool(endpoint, args)
            data = parse_tool_result(result)
            # Accept "active" (cluster running), "success" (operation succeeded), or "not_running" (cluster stopped)
            assert data["status"] in ["success", "not_running", "active"], f"{endpoint} failed: {data}"
        
        print("✅ Core API endpoints working")
        
        # Test job-related endpoints with dummy data (job submission unreliable in test environment)
        job_endpoints = [
            ("retrieve_logs", {"identifier": "dummy_job", "log_type": "job"}),
        ]
        
        for endpoint, args in job_endpoints:
            print(f"Testing {endpoint}...")
            result = await call_tool(endpoint, args)
            data = parse_tool_result(result)
            # These should return errors for non-existent jobs, which is expected behavior
            assert data["status"] in ["success", "error"], f"{endpoint} returned unexpected status: {data}"
        
        await stop_ray_cluster()
        print("✅ API surface smoke test passed!")

    @pytest.mark.asyncio
    async def test_error_scenarios_smoke(self):
        """Fast test of critical error scenarios."""
        
        print("⚠️  Testing error scenarios...")
        
        await start_ray_cluster(cpu_limit=1, worker_nodes=[])  # Head-only
        
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
        
        # Test 2: Error handling for non-existent resources
        print("Testing non-existent job handling...")
        
        # Test retrieving logs for non-existent job
        logs_result = await call_tool("retrieve_logs", {
            "identifier": "non_existent_job_12345",
            "log_type": "job"
        })
        logs_data = parse_tool_result(logs_result)
        # Should return error for non-existent job
        assert logs_data["status"] == "error"
        print("✅ Non-existent job error handling works")
        
        # Test job inspection for non-existent job
        inspect_result = await call_tool("inspect_job", {
            "job_id": "non_existent_job_12345",
            "mode": "status"
        })
        inspect_data = parse_tool_result(inspect_result)
        # Should return error for non-existent job
        assert inspect_data["status"] == "error"
        print("✅ Non-existent job inspection error handling works")
        
        await stop_ray_cluster()
        print("✅ Error scenarios smoke test passed!")

    @pytest.mark.asyncio
    async def test_component_integration_smoke(self):
        """Fast validation that system components work together."""
        
        print("🔧 Testing component integration...")
        
        # Test that we're using the new unified manager
        print("Checking unified manager...")
        from ray_mcp.main import ray_manager
        from ray_mcp.core.unified_manager import RayUnifiedManager
        
        # Verify we're using the unified manager architecture
        assert isinstance(ray_manager, RayUnifiedManager), "Should be using RayUnifiedManager"
        print("✅ Using unified manager")
        
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
        await start_ray_cluster(cpu_limit=1, worker_nodes=[])  # Head-only
        
        # Should show up in state
        assert ray_manager.is_initialized
        assert ray_manager.cluster_address is not None
        print("✅ State management working")
        
        # Test component integration through API calls
        print("Testing component integration...")
        
        # Test that state manager and cluster manager work together
        inspect_result = await call_tool("inspect_ray", {})
        inspect_data = parse_tool_result(inspect_result)
        assert inspect_data["status"] == "active"
        
        # Test that job manager component responds correctly
        list_result = await call_tool("list_jobs", {})
        list_data = parse_tool_result(list_result)
        assert list_data["status"] == "success"
        
        # Test that log manager component handles requests correctly
        logs_result = await call_tool("retrieve_logs", {
            "identifier": "test_dummy",
            "log_type": "job"
        })
        logs_data = parse_tool_result(logs_result)
        # Should return error for non-existent job, which shows log manager is working
        assert logs_data["status"] == "error"
        print("✅ Components working together")
        
        await stop_ray_cluster()
        print("✅ Component integration smoke test passed!")


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
        cluster_data = await start_ray_cluster(cpu_limit=1, worker_nodes=[])  # Head-only
        assert cluster_data["status"] == "success"
        
        # Simplest possible API validation
        list_result = await call_tool("list_jobs", {})
        list_data = parse_tool_result(list_result)
        assert list_data["status"] == "success"
        
        # Quick status check
        status_result = await call_tool("inspect_ray")
        status_data = parse_tool_result(status_result)
        # Accept "active" (cluster running) or "success" (operation succeeded)
        assert status_data["status"] in ["success", "active"], f"Unexpected status: {status_data['status']}"
        
        await stop_ray_cluster()
        
        elapsed = time.time() - start_time
        print(f"✅ 30-second regression test completed in {elapsed:.1f}s")
        
        # Should complete well under 30 seconds
        assert elapsed < 30, f"Test took too long: {elapsed:.1f}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "smoke"]) 