#!/usr/bin/env python3
"""End-to-end integration tests for the refactored Ray MCP architecture.

These tests validate that the new component-based architecture works seamlessly
in real scenarios without any mocking. They focus on:

1. Component integration across the new architecture
2. Backward compatibility with existing workflows  
3. Critical user journeys end-to-end
4. Error handling across component boundaries
5. Performance with real Ray clusters

Tests are designed to run fast while providing high confidence.
"""

import pytest

from tests.conftest import (
    TestScripts,
    call_tool,
    parse_tool_result,
    start_ray_cluster,
    stop_ray_cluster,
    submit_and_wait_for_job,
    verify_cluster_status,
    E2EConfig,
    TempScriptManager,
)


@pytest.mark.e2e
class TestRefactoredArchitectureE2E:
    """E2E tests validating the refactored component architecture."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_unified_manager_complete_workflow(self):
        """Test that the unified manager handles complete workflows seamlessly."""
        
        # Test 1: Cluster Lifecycle via Unified Manager
        print("🚀 Testing unified manager cluster lifecycle...")
        
        cluster_data = await start_ray_cluster(cpu_limit=1)
        assert "cluster_address" in cluster_data
        print(f"✅ Cluster started: {cluster_data['cluster_address']}")
        
        # Test 2: State Management Consistency
        print("🔍 Testing state management consistency...")
        status_data = await verify_cluster_status()
        assert status_data["cluster_overview"]["status"] == "running"
        print("✅ State management working correctly")
        
        # Test 3: Job Management Integration
        print("📋 Testing job management integration...")
        job_id, job_status = await submit_and_wait_for_job(
            TestScripts.QUICK_SUCCESS, 
            expected_status="SUCCEEDED",
            max_wait=15
        )
        assert job_status["job_status"] == "SUCCEEDED"
        print(f"✅ Job management working: {job_id}")
        
        # Test 4: Log Management Integration
        print("📜 Testing log management integration...")
        logs_result = await call_tool("retrieve_logs", {
            "identifier": job_id,
            "log_type": "job",
            "num_lines": 50
        })
        logs_data = parse_tool_result(logs_result)
        assert logs_data["status"] == "success"
        assert "Task result: 25" in logs_data["logs"]
        print("✅ Log management working correctly")
        
        # Test 5: Component State Sharing
        print("🔗 Testing component state sharing...")
        jobs_result = await call_tool("list_jobs")
        jobs_data = parse_tool_result(jobs_result)
        assert jobs_data["status"] == "success"
        assert len(jobs_data["jobs"]) >= 1
        found_job = any(job["job_id"] == job_id for job in jobs_data["jobs"])
        assert found_job, "Job should be found in listing"
        print("✅ Component state sharing working")
        
        # Test 6: Clean Shutdown
        print("🛑 Testing clean shutdown...")
        await stop_ray_cluster()
        print("✅ Unified manager complete workflow test passed!")

    @pytest.mark.asyncio
    @pytest.mark.slow  
    async def test_backward_compatibility_validation(self):
        """Test that refactored architecture maintains 100% backward compatibility."""
        
        print("🔄 Testing backward compatibility...")
        
        # Test 1: Same API Surface
        print("🔌 Verifying API surface compatibility...")
        
        # Start cluster using legacy API patterns
        cluster_result = await call_tool("init_ray", {
            "num_cpus": 1,
            "worker_nodes": []
        })
        cluster_data = parse_tool_result(cluster_result)
        assert cluster_data["status"] == "success"
        print("✅ Legacy init_ray API working")
        
        # Test 2: Job Submission Compatibility
        print("📤 Testing job submission compatibility...")
        
        # Submit job using legacy patterns
        with TempScriptManager(TestScripts.LIGHTWEIGHT_SUCCESS) as script_path:
            job_result = await call_tool("submit_job", {
                "entrypoint": f"python {script_path}",
                "runtime_env": {"pip": []},
                "metadata": {"test": "backward_compatibility"}
            })
            job_data = parse_tool_result(job_result)
            assert job_data["status"] == "success"
            job_id = job_data["job_id"]
            print(f"✅ Legacy job submission working: {job_id}")
        
        # Test 3: Job Inspection Compatibility  
        print("🔍 Testing job inspection compatibility...")
        
        # Wait for job completion
        import asyncio
        await asyncio.sleep(3)
        
        inspect_result = await call_tool("inspect_job", {
            "job_id": job_id,
            "mode": "status"
        })
        inspect_data = parse_tool_result(inspect_result)
        assert inspect_data["status"] == "success"
        assert "job_info" in inspect_data
        print("✅ Legacy job inspection working")
        
        # Test 4: Log Retrieval Compatibility
        print("📋 Testing log retrieval compatibility...")
        
        logs_result = await call_tool("retrieve_logs", {
            "identifier": job_id,
            "log_type": "job"
        })
        logs_data = parse_tool_result(logs_result)
        assert logs_data["status"] == "success"
        print("✅ Legacy log retrieval working")
        
        # Test 5: Cluster Inspection Compatibility
        print("📊 Testing cluster inspection compatibility...")
        
        status_result = await call_tool("inspect_ray")
        status_data = parse_tool_result(status_result)
        assert status_data["status"] == "success"
        assert "cluster_overview" in status_data
        print("✅ Legacy cluster inspection working")
        
        # Cleanup
        await stop_ray_cluster()
        print("✅ Backward compatibility validation passed!")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_error_handling_across_components(self):
        """Test error handling and recovery across component boundaries."""
        
        print("⚠️  Testing error handling across components...")
        
        # Test 1: Graceful Job Failure Handling
        print("💥 Testing job failure handling...")
        
        await start_ray_cluster(cpu_limit=1)
        
        # Submit failing job
        job_id, job_status = await submit_and_wait_for_job(
            TestScripts.INTENTIONAL_FAILURE,
            expected_status="FAILED",
            max_wait=10
        )
        assert job_status["job_status"] == "FAILED"
        print(f"✅ Job failure handled correctly: {job_id}")
        
        # Test 2: Log Retrieval from Failed Jobs
        print("📜 Testing log retrieval from failed jobs...")
        
        logs_result = await call_tool("retrieve_logs", {
            "identifier": job_id,
            "log_type": "job",
            "include_errors": True
        })
        logs_data = parse_tool_result(logs_result)
        assert logs_data["status"] == "success"
        assert "This job will fail intentionally" in logs_data["logs"]
        
        # Check error analysis
        if "error_analysis" in logs_data:
            assert logs_data["error_analysis"]["errors_found"] is True
            print("✅ Error analysis working")
        
        # Test 3: System Recovery After Failure
        print("🔄 Testing system recovery after failure...")
        
        # Submit successful job after failure
        recovery_job_id, recovery_status = await submit_and_wait_for_job(
            TestScripts.QUICK_SUCCESS,
            expected_status="SUCCEEDED",
            max_wait=10
        )
        assert recovery_status["job_status"] == "SUCCEEDED"
        print(f"✅ System recovery working: {recovery_job_id}")
        
        # Test 4: Component State Consistency After Errors
        print("🔗 Testing state consistency after errors...")
        
        jobs_result = await call_tool("list_jobs")
        jobs_data = parse_tool_result(jobs_result)
        assert jobs_data["status"] == "success"
        assert len(jobs_data["jobs"]) >= 2  # Failed + successful jobs
        print("✅ State consistency maintained")
        
        await stop_ray_cluster()
        print("✅ Error handling across components test passed!")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_performance_and_resource_efficiency(self):
        """Test performance and resource efficiency of the refactored architecture."""
        
        print("⚡ Testing performance and resource efficiency...")
        
        import time
        
        # Test 1: Fast Cluster Startup
        print("🚀 Testing cluster startup performance...")
        
        start_time = time.time()
        await start_ray_cluster(cpu_limit=1)
        startup_time = time.time() - start_time
        print(f"✅ Cluster started in {startup_time:.2f}s")
        
        # Should start reasonably quickly (less than 30s in most environments)
        assert startup_time < 30, f"Startup took too long: {startup_time}s"
        
        # Test 2: Rapid Job Submission and Completion
        print("📋 Testing job submission performance...")
        
        start_time = time.time()
        job_id, job_status = await submit_and_wait_for_job(
            TestScripts.LIGHTWEIGHT_SUCCESS,
            expected_status="SUCCEEDED", 
            max_wait=15
        )
        job_time = time.time() - start_time
        print(f"✅ Job completed in {job_time:.2f}s")
        
        # Job should complete quickly
        assert job_time < 20, f"Job took too long: {job_time}s"
        
        # Test 3: Fast Log Retrieval
        print("📜 Testing log retrieval performance...")
        
        start_time = time.time()
        logs_result = await call_tool("retrieve_logs", {
            "identifier": job_id,
            "log_type": "job"
        })
        logs_data = parse_tool_result(logs_result)
        log_time = time.time() - start_time
        
        assert logs_data["status"] == "success"
        print(f"✅ Logs retrieved in {log_time:.2f}s")
        
        # Log retrieval should be fast
        assert log_time < 5, f"Log retrieval took too long: {log_time}s"
        
        # Test 4: Multiple Concurrent Operations
        print("🔄 Testing concurrent operations...")
        
        start_time = time.time()
        
        # Submit multiple small jobs concurrently
        import asyncio
        tasks = []
        for i in range(3):
            task = submit_and_wait_for_job(
                TestScripts.LIGHTWEIGHT_SUCCESS,
                expected_status="SUCCEEDED",
                max_wait=20
            )
            tasks.append(task)
        
        # Wait for all jobs to complete
        results = await asyncio.gather(*tasks)
        concurrent_time = time.time() - start_time
        
        print(f"✅ {len(results)} concurrent jobs completed in {concurrent_time:.2f}s")
        
        # Concurrent jobs should complete efficiently
        assert concurrent_time < 40, f"Concurrent jobs took too long: {concurrent_time}s"
        
        # Verify all jobs succeeded
        for job_id, job_status in results:
            assert job_status["job_status"] == "SUCCEEDED"
        
        await stop_ray_cluster()
        print("✅ Performance and resource efficiency test passed!")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_component_isolation_and_fault_tolerance(self):
        """Test that components are properly isolated and fault-tolerant."""
        
        print("🛡️  Testing component isolation and fault tolerance...")
        
        await start_ray_cluster(cpu_limit=1)
        
        # Test 1: Job Management Independence  
        print("📋 Testing job management independence...")
        
        # Submit a job
        job_id, _ = await submit_and_wait_for_job(
            TestScripts.QUICK_SUCCESS,
            expected_status="SUCCEEDED",
            max_wait=15
        )
        
        # Verify we can retrieve logs even if job system has issues
        logs_result = await call_tool("retrieve_logs", {
            "identifier": job_id,
            "log_type": "job"
        })
        logs_data = parse_tool_result(logs_result)
        assert logs_data["status"] == "success"
        print("✅ Log management working independently")
        
        # Test 2: State Consistency Across Components
        print("🔗 Testing state consistency...")
        
        # Check cluster status
        status_result = await call_tool("inspect_ray")
        status_data = parse_tool_result(status_result)
        assert status_data["status"] == "success"
        
        # Check job listing
        jobs_result = await call_tool("list_jobs")
        jobs_data = parse_tool_result(jobs_result)
        assert jobs_data["status"] == "success"
        
        # Both should reflect consistent state
        assert len(jobs_data["jobs"]) >= 1
        print("✅ State consistency maintained across components")
        
        # Test 3: Graceful Degradation
        print("⬇️  Testing graceful degradation...")
        
        # Test invalid log type (should handle gracefully)
        invalid_logs_result = await call_tool("retrieve_logs", {
            "identifier": job_id,
            "log_type": "invalid_type"
        })
        invalid_logs_data = parse_tool_result(invalid_logs_result)
        assert invalid_logs_data["status"] == "error"
        assert "Invalid log_type" in invalid_logs_data["message"]
        print("✅ Graceful error handling working")
        
        # System should still work after errors
        status_result = await call_tool("inspect_ray")
        status_data = parse_tool_result(status_result)
        assert status_data["status"] == "success"
        print("✅ System remains functional after errors")
        
        await stop_ray_cluster()
        print("✅ Component isolation and fault tolerance test passed!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"]) 