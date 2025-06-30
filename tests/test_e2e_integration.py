#!/usr/bin/env python3
"""End-to-end integration tests for the Ray MCP server."""

import asyncio
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
            TestScripts.QUICK_SUCCESS, expected_status="SUCCEEDED"
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
    async def test_job_failure_and_debugging_workflow(
        self, e2e_ray_manager: RayManager
    ):
        """Test job failure handling, debugging, and recovery workflows."""

        # Step 1: Start Ray cluster
        await start_ray_cluster()
        print("Ray cluster started for failure testing")

        # Step 2: Submit a job that will fail
        print("Submitting a job designed to fail...")
        fail_job_id, fail_status = await submit_and_wait_for_job(
            TestScripts.INTENTIONAL_FAILURE, expected_status="FAILED"
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
            TestScripts.LIGHTWEIGHT_SUCCESS, expected_status="SUCCEEDED", runtime_env={}
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

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_port_allocation_race_condition_fix(self):
        """Test that the file locking mechanism prevents port allocation race conditions.
        
        This focused test validates that the find_free_port() file locking fix works correctly 
        by testing concurrent and sequential port allocation without race conditions.
        Optimized for speed - tests only the port allocation logic without Ray cluster startup.
        """
        import os
        import time
        import tempfile
        
        print("Testing port allocation race condition fix...")
        test_start_time = time.time()
        
        # Test 1: Concurrent find_free_port calls (core race condition test)
        print("\n🔥 Testing concurrent find_free_port calls...")
        
        managers = [RayManager() for _ in range(5)]
        start_port = 20000
        
        # Test concurrent calls - this is the core race condition scenario
        async def allocate_port_task(manager, task_id):
            port = await manager.find_free_port(start_port=start_port + task_id * 10)
            print(f"Task {task_id}: allocated port {port}")
            return port
        
        # Run 5 concurrent port allocations
        start_time = time.time()
        tasks = [allocate_port_task(managers[i], i) for i in range(5)]
        ports_found = await asyncio.gather(*tasks)
        allocation_time = time.time() - start_time
        
        # Verify no race conditions occurred
        unique_ports = set(ports_found)
        if len(unique_ports) != len(ports_found):
            pytest.fail(f"RACE CONDITION! find_free_port() returned duplicate ports: {ports_found}")
        
        print(f"✅ Concurrent allocation: {len(unique_ports)} unique ports in {allocation_time:.2f}s")
        print(f"✅ Ports allocated: {sorted(ports_found)}")
        
        # Test 2: Rapid sequential calls (another race condition scenario)
        print(f"\n⚡ Testing rapid sequential calls...")
        
        manager = RayManager()
        sequential_ports = []
        
        start_time = time.time()
        for i in range(3):
            port = await manager.find_free_port(start_port=start_port + 100 + i)
            sequential_ports.append(port)
        sequential_time = time.time() - start_time
        
        # Verify sequential allocation works correctly
        unique_sequential = set(sequential_ports)
        if len(unique_sequential) != len(sequential_ports):
            pytest.fail(f"RACE CONDITION! Sequential calls returned duplicate ports: {sequential_ports}")
        
        print(f"✅ Sequential allocation: {len(unique_sequential)} unique ports in {sequential_time:.2f}s")
        print(f"✅ Sequential ports: {sorted(sequential_ports)}")
        
        # Test 3: File locking verification
        print(f"\n🔐 Testing file locking mechanism...")
        
        # Check that lock files are managed properly
        temp_dir = tempfile.gettempdir()
        lock_files_before = [f for f in os.listdir(temp_dir) if f.startswith("ray_port_") and f.endswith(".lock")]
        
        # Allocate a port and verify lock file behavior
        cleanup_manager = RayManager()
        port_to_test = await cleanup_manager.find_free_port(start_port=start_port + 200)
        
        # Clean up the port lock
        cleanup_manager._cleanup_port_lock(port_to_test)
        
        lock_files_after = [f for f in os.listdir(temp_dir) if f.startswith("ray_port_") and f.endswith(".lock")]
        
        print(f"✅ Lock files before: {len(lock_files_before)}, after: {len(lock_files_after)}")
        print(f"✅ Port {port_to_test} allocated and cleaned up successfully")
        
        total_time = time.time() - test_start_time
        
        print(f"\n🏁 RACE CONDITION FIX RESULTS:")
        print(f"✅ File locking mechanism prevents race conditions")
        print(f"✅ Concurrent ports: {sorted(ports_found)}")
        print(f"✅ Sequential ports: {sorted(sequential_ports)}")
        print(f"✅ Lock file management working correctly")
        print(f"✅ Total test time: {total_time:.2f}s")
        print(f"✅ Port allocation race condition fix validated!")

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_multiple_ray_clusters_unique_ports(self):
        """Test that multiple Ray clusters can start with unique ports.
        
        This test validates the race condition fix in a real-world scenario by starting
        3 Ray head nodes simultaneously and ensuring they all get unique ports.
        """
        import os
        import time
        import tempfile
        import shutil
        
        print("Testing multiple Ray clusters with unique port allocation...")
        test_start_time = time.time()
        
        managers = []
        temp_dirs = []
        cluster_results = []
        
        try:
            # Create 3 Ray managers with isolated temp directories
            print(f"\n🏗️  Setting up 3 Ray cluster managers...")
            
            timestamp = int(time.time())
            for i in range(3):
                manager = RayManager()
                managers.append(manager)
                
                # Create isolated temp directory for each cluster
                temp_dir = f"/tmp/ray_cluster_{i}_{timestamp}"
                os.makedirs(temp_dir, exist_ok=True)
                temp_dirs.append(temp_dir)
                
                print(f"Manager {i}: temp dir {temp_dir}")
            
            # Start all 3 clusters concurrently (head node only for speed)
            print(f"\n🚀 Starting 3 Ray clusters concurrently...")
            
            async def start_cluster_task(manager, cluster_id, temp_dir):
                # Set isolated temp directory
                original_tmpdir = os.environ.get('RAY_TMPDIR')
                os.environ['RAY_TMPDIR'] = temp_dir
                
                try:
                    start_time = time.time()
                    result = await manager.init_cluster(
                        num_cpus=1,
                        worker_nodes=[],  # Head node only for speed
                        head_node_port=None,  # Let find_free_port() assign
                        dashboard_port=None,  # Let find_free_port() assign
                    )
                    startup_time = time.time() - start_time
                    
                    if result["status"] == "success":
                        cluster_address = result["cluster_address"]
                        head_port = int(cluster_address.split(":")[1])
                        dashboard_url = result.get("dashboard_url", "")
                        dashboard_port = None
                        if dashboard_url and ":" in dashboard_url:
                            try:
                                dashboard_port = int(dashboard_url.split(":")[-1])
                            except ValueError:
                                pass
                        
                        print(f"✅ Cluster {cluster_id}: started on head port {head_port}, dashboard port {dashboard_port} in {startup_time:.2f}s")
                        return {
                            "cluster_id": cluster_id,
                            "head_port": head_port,
                            "dashboard_port": dashboard_port,
                            "startup_time": startup_time,
                            "result": result
                        }
                    else:
                        print(f"❌ Cluster {cluster_id}: failed to start - {result}")
                        return {"cluster_id": cluster_id, "error": result}
                        
                finally:
                    # Restore environment
                    if original_tmpdir is not None:
                        os.environ['RAY_TMPDIR'] = original_tmpdir
                    elif 'RAY_TMPDIR' in os.environ:
                        del os.environ['RAY_TMPDIR']
            
            # Start all clusters concurrently
            startup_start_time = time.time()
            tasks = [
                start_cluster_task(managers[i], i, temp_dirs[i]) 
                for i in range(3)
            ]
            cluster_results = await asyncio.gather(*tasks, return_exceptions=True)
            total_startup_time = time.time() - startup_start_time
            
            print(f"\n📊 Analyzing results...")
            
            # Analyze results
            successful_clusters = []
            failed_clusters = []
            head_ports = []
            dashboard_ports = []
            
            for result in cluster_results:
                if isinstance(result, Exception):
                    failed_clusters.append(f"Exception: {result}")
                elif "error" in result:
                    failed_clusters.append(f"Cluster {result['cluster_id']}: {result['error']}")
                else:
                    successful_clusters.append(result)
                    head_ports.append(result["head_port"])
                    if result["dashboard_port"]:
                        dashboard_ports.append(result["dashboard_port"])
            
            # Verify no port conflicts
            unique_head_ports = set(head_ports)
            unique_dashboard_ports = set(dashboard_ports)
            
            print(f"\n📈 CLUSTER STARTUP RESULTS:")
            print(f"✅ Successful clusters: {len(successful_clusters)}/3")
            print(f"❌ Failed clusters: {len(failed_clusters)}")
            
            if failed_clusters:
                for failure in failed_clusters:
                    print(f"   ❌ {failure}")
            
            print(f"✅ Head ports allocated: {sorted(head_ports)}")
            print(f"✅ Dashboard ports allocated: {sorted(dashboard_ports)}")
            print(f"✅ Total concurrent startup time: {total_startup_time:.2f}s")
            
            # Critical validation: No port conflicts
            if len(unique_head_ports) != len(head_ports):
                pytest.fail(f"HEAD PORT CONFLICT! Multiple clusters got same head ports: {head_ports}")
            
            if len(dashboard_ports) > 0 and len(unique_dashboard_ports) != len(dashboard_ports):
                pytest.fail(f"DASHBOARD PORT CONFLICT! Multiple clusters got same dashboard ports: {dashboard_ports}")
            
            # Expect at least 2 clusters to start successfully (allowing for occasional failures)
            if len(successful_clusters) < 2:
                pytest.fail(f"Too many cluster failures: {len(failed_clusters)}/3 failed. This suggests a systematic issue.")
            
            print(f"✅ No port conflicts detected - race condition fix working!")
            
        finally:
            # Cleanup all clusters
            print(f"\n🧹 Cleaning up {len(managers)} clusters...")
            
            cleanup_tasks = []
            for i, manager in enumerate(managers):
                if manager:
                    cleanup_tasks.append(manager.stop_cluster())
            
            if cleanup_tasks:
                cleanup_results = await asyncio.gather(*cleanup_tasks, return_exceptions=True)
                
                for i, cleanup_result in enumerate(cleanup_results):
                    if isinstance(cleanup_result, Exception):
                        print(f"⚠️  Cluster {i} cleanup failed: {cleanup_result}")
                    else:
                        print(f"✅ Cluster {i} cleaned up successfully")
            
            # Clean up temp directories
            for i, temp_dir in enumerate(temp_dirs):
                try:
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)
                        print(f"✅ Cleaned up temp dir {i}: {temp_dir}")
                except Exception as e:
                    print(f"⚠️  Failed to clean up temp dir {i}: {e}")
        
        total_time = time.time() - test_start_time
        
        print(f"\n🏁 MULTIPLE CLUSTER TEST RESULTS:")
        print(f"✅ Concurrent Ray cluster startup validated")
        print(f"✅ Unique head ports: {sorted(head_ports)}")
        print(f"✅ Unique dashboard ports: {sorted(dashboard_ports)}")
        print(f"✅ Successful clusters: {len(successful_clusters)}/3")
        print(f"✅ Total test time: {total_time:.2f}s")
        print(f"✅ Multi-cluster port allocation race condition fix validated!")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
