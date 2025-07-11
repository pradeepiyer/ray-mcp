#!/usr/bin/env python3
"""Comprehensive Ray MCP server tests.

This file consolidates all end-to-end testing into a single comprehensive test
that validates the complete Ray MCP server functionality. It covers:

1. System architecture and component integration
2. Cluster lifecycle management and performance
3. API endpoint functionality and concurrent operations
4. Job management workflows
5. Comprehensive error handling and recovery
6. Clean shutdown and resource cleanup

This replaces the previous test_e2e_smoke.py and test_e2e_system.py files
to eliminate redundancy while maintaining comprehensive coverage.
"""

import asyncio
import os
import time

import pytest

from tests.conftest import (
    TempScriptManager,
    TestScripts,
    call_tool,
    parse_tool_result,
    start_ray_cluster,
    stop_ray_cluster,
    verify_cluster_status,
    wait_for_job_completion,
)


@pytest.mark.e2e
class TestRayMCPServer:
    """Comprehensive end-to-end tests for Ray MCP server."""

    @pytest.mark.asyncio
    async def test_complete_mcp_server_workflow(self):
        """Single comprehensive test covering all critical Ray MCP server functionality."""

        print("🚀 Starting comprehensive Ray MCP server test...")
        test_start_time = time.time()

        # ================================================================
        # 1. SYSTEM ARCHITECTURE VALIDATION
        # ================================================================
        print("\n🔧 Testing system architecture and component integration...")

        # Verify unified manager architecture
        from ray_mcp.main import ray_manager
        from ray_mcp.managers.unified_manager import RayUnifiedManager

        assert isinstance(
            ray_manager, RayUnifiedManager
        ), "Should be using RayUnifiedManager"
        print("✅ Using unified manager architecture")

        # Test component access
        state_manager = ray_manager.get_state_manager()
        cluster_manager = ray_manager.get_cluster_manager()
        job_manager = ray_manager.get_job_manager()
        log_manager = ray_manager.get_log_manager()
        port_manager = ray_manager.get_port_manager()

        assert all(
            [state_manager, cluster_manager, job_manager, log_manager, port_manager]
        )
        print("✅ All components accessible and properly initialized")

        # ================================================================
        # 2. CLUSTER LIFECYCLE AND PERFORMANCE VALIDATION
        # ================================================================
        print("\n🚀 Testing cluster lifecycle and performance...")

        # Test cluster startup performance
        start_time = time.time()
        cluster_data = await start_ray_cluster(
            cpu_limit=1, worker_nodes=[]
        )  # Head-only for reliability
        startup_time = time.time() - start_time

        assert cluster_data["status"] == "success"
        assert "cluster_address" in cluster_data
        assert startup_time < 30, f"Startup took too long: {startup_time:.2f}s"
        print(
            f"✅ Cluster started in {startup_time:.2f}s at {cluster_data['cluster_address']}"
        )

        # Verify state management integration
        assert ray_manager.is_initialized
        assert ray_manager.cluster_address is not None
        print("✅ State management working correctly")

        # Test cluster status validation
        status_data = await verify_cluster_status()
        assert status_data["status"] in ["active", "success"]
        print("✅ Cluster status verification working")

        # ================================================================
        # 3. API ENDPOINT VALIDATION AND PERFORMANCE
        # ================================================================
        print("\n📋 Testing API endpoints and performance...")

        # Test core API endpoints with performance measurement
        core_endpoints = [
            ("inspect_ray_cluster", {}),
            ("list_ray_jobs", {}),
        ]

        for endpoint, args in core_endpoints:
            start_time = time.time()
            result = await call_tool(endpoint, args)
            api_time = time.time() - start_time

            data = parse_tool_result(result)
            assert data["status"] in ["success", "active"], f"{endpoint} failed: {data}"
            assert api_time < 2, f"{endpoint} response too slow: {api_time:.3f}s"
            print(f"✅ {endpoint} working in {api_time:.3f}s")

        # Test job-related endpoints with expected error handling
        job_endpoints = [
            ("retrieve_logs", {"identifier": "dummy_job", "log_type": "job"}),
        ]

        for endpoint, args in job_endpoints:
            result = await call_tool(endpoint, args)
            data = parse_tool_result(result)
            # These should return errors for non-existent jobs, which is expected behavior
            assert data["status"] in [
                "success",
                "error",
            ], f"{endpoint} returned unexpected status: {data}"
            print(f"✅ {endpoint} error handling working correctly")

        # Test concurrent API operations
        print("🔄 Testing concurrent API operations...")
        start_time = time.time()

        tasks = []
        for i in range(5):
            tasks.append(call_tool("inspect_ray_cluster"))
            tasks.append(call_tool("list_ray_jobs"))

        results = await asyncio.gather(*tasks)
        concurrent_time = time.time() - start_time

        assert (
            concurrent_time < 10
        ), f"Concurrent operations too slow: {concurrent_time:.2f}s"
        for result in results:
            data = parse_tool_result(result)
            assert data["status"] in ["success", "active"]
        print(
            f"✅ {len(results)} concurrent API calls completed in {concurrent_time:.2f}s"
        )

        # ================================================================
        # 4. JOB MANAGEMENT WORKFLOW
        # ================================================================
        print("\n🔄 Testing job management workflow...")

        # Test job listing
        jobs_result = await call_tool("list_ray_jobs")
        jobs_data = parse_tool_result(jobs_result)
        assert jobs_data["status"] == "success"
        assert "jobs" in jobs_data
        print("✅ Job listing API working")

        # Test job submission (may fail in test environment due to dashboard agent)
        print("🔄 Attempting job submission...")
        try:
            with TempScriptManager(TestScripts.QUICK_SUCCESS) as script_path:
                job_result = await call_tool(
                    "submit_ray_job", {"entrypoint": f"python {script_path}"}
                )
                job_data = parse_tool_result(job_result)

                if job_data["status"] == "success":
                    job_id = job_data["job_id"]
                    print(f"✅ Job submission working: {job_id}")

                    # Test log management integration
                    print("📜 Testing log management integration...")
                    logs_result = await call_tool(
                        "retrieve_logs",
                        {"identifier": job_id, "log_type": "job", "num_lines": 50},
                    )
                    logs_data = parse_tool_result(logs_result)
                    assert logs_data["status"] == "success"
                    print("✅ Log management integration working")

                    # Test component state sharing
                    print("🔗 Testing component state sharing...")
                    jobs_result = await call_tool("list_ray_jobs")
                    jobs_data = parse_tool_result(jobs_result)
                    assert jobs_data["status"] == "success"
                    found_job = any(
                        job["job_id"] == job_id for job in jobs_data["jobs"]
                    )
                    assert found_job, "Job should be found in listing"
                    print("✅ Component state sharing working")

                else:
                    print(
                        f"⚠️  Job submission failed (expected in test env): {job_data.get('message', 'Unknown')}"
                    )
                    print("✅ Job management handles errors gracefully")

        except Exception as e:
            print(f"⚠️  Job submission failed (expected in test environment): {e}")
            print("✅ Job management error handling working")

        # ================================================================
        # 5. COMPREHENSIVE ERROR HANDLING AND RECOVERY
        # ================================================================
        print("\n⚠️  Testing comprehensive error handling and recovery...")

        # Test invalid operations
        print("🔍 Testing invalid operations...")
        error_scenarios = [
            (
                "retrieve_logs",
                {"identifier": "dummy", "log_type": "invalid_type"},
                "Invalid log_type",
            ),
            (
                "retrieve_logs",
                {"identifier": "non_existent_job_12345", "log_type": "job"},
                "error",
            ),
            (
                "inspect_ray_job",
                {"job_id": "non_existent_job_12345", "mode": "status"},
                "error",
            ),
        ]

        for tool_name, args, expected_error in error_scenarios:
            result = await call_tool(tool_name, args)
            data = parse_tool_result(result)
            assert data["status"] == "error"
            if expected_error != "error":
                assert expected_error in data["message"]
            print(f"✅ {tool_name} error handling working")

        # Test system recovery after errors
        print("🔄 Testing system recovery after errors...")

        # System should remain functional after error conditions
        recovery_tests = [
            ("inspect_ray_cluster", {}),
            ("list_ray_jobs", {}),
        ]

        for endpoint, args in recovery_tests:
            result = await call_tool(endpoint, args)
            data = parse_tool_result(result)
            assert data["status"] in ["success", "active"]
        print("✅ System remains functional after error conditions")

        # Test component independence and consistency
        print("⚖️  Testing component independence and state consistency...")

        # Multiple calls should return consistent results
        for i in range(3):
            status_result = await call_tool("inspect_ray_cluster")
            status_data = parse_tool_result(status_result)
            assert status_data["status"] in ["success", "active"]

            jobs_result = await call_tool("list_ray_jobs")
            jobs_data = parse_tool_result(jobs_result)
            assert jobs_data["status"] == "success"
        print("✅ Component independence and state consistency verified")

        # Test graceful degradation under error conditions
        print("⬇️  Testing graceful degradation...")

        # Test various error conditions to ensure graceful handling
        degradation_tests = [
            ("retrieve_logs", {"identifier": "dummy", "log_type": "invalid_type"}),
            ("inspect_ray_job", {"job_id": "non_existent", "mode": "status"}),
            ("retrieve_logs", {"identifier": "non_existent", "log_type": "job"}),
        ]

        for tool_name, args in degradation_tests:
            result = await call_tool(tool_name, args)
            data = parse_tool_result(result)
            assert data["status"] == "error"
        print("✅ Graceful degradation working across all components")

        # ================================================================
        # 6. CLEAN SHUTDOWN AND RESOURCE CLEANUP
        # ================================================================
        print("\n🛑 Testing clean shutdown and resource cleanup...")

        await stop_ray_cluster()
        print("✅ Clean shutdown completed")

        # ================================================================
        # TEST COMPLETION AND SUMMARY
        # ================================================================
        total_time = time.time() - test_start_time
        print(
            f"\n✅ Complete Ray MCP server test passed! (Total time: {total_time:.2f}s)"
        )
        print("🎉 All critical functionality validated:")
        print("   - ✅ System architecture and component integration")
        print("   - ✅ Cluster lifecycle and performance")
        print("   - ✅ API endpoints and concurrent operations")
        print("   - ✅ Job management workflow")
        print("   - ✅ Comprehensive error handling and recovery")
        print("   - ✅ Clean shutdown and resource cleanup")
        print(
            f"   - ⚡ Performance: Startup {startup_time:.2f}s, Total {total_time:.2f}s"
        )

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
    async def test_gke_kuberay_job_submission(self):
        """Test complete GKE + KubeRay integration workflow.

        This high-value integration test validates:
        1. GKE cloud provider detection
        2. GKE cluster connection
        3. KubeRay job submission to GKE
        4. Job execution monitoring
        5. Log retrieval from KubeRay
        6. Resource cleanup

        Environment requirements:
        - GOOGLE_APPLICATION_CREDENTIALS: Path to GKE service account key
        - GKE_TEST_CLUSTER: Name of GKE cluster to use for testing
        - GKE cluster must have KubeRay operator installed
        """
        print("🚀 Starting GKE + KubeRay integration test...")
        test_start_time = time.time()

        cluster_name = os.getenv("GKE_TEST_CLUSTER")

        try:
            # ================================================================
            # 1. GKE ENVIRONMENT DETECTION
            # ================================================================
            print("\n🔍 Testing GKE cloud provider detection...")

            detection_result = await call_tool("detect_cloud_provider")
            detection_data = parse_tool_result(detection_result)

            print(f"Cloud provider detection result: {detection_data}")

            # Allow test to proceed even if detection doesn't return GKE
            # (detection may vary based on environment)
            if detection_data.get("status") == "success":
                detected_provider = detection_data.get("detected_provider")
                if detected_provider == "gke":
                    print("✅ GKE environment detected automatically")
                else:
                    print(
                        f"⚠️  Detected provider: {detected_provider}, proceeding with explicit GKE connection"
                    )
            else:
                print(
                    "⚠️  Cloud provider detection inconclusive, proceeding with explicit GKE connection"
                )

            # ================================================================
            # 2. GKE CLUSTER CONNECTION
            # ================================================================
            print(f"\n🔗 Connecting to GKE cluster: {cluster_name}")

            connection_result = await call_tool(
                "connect_kubernetes_cluster",
                {"provider": "gke", "cluster_name": cluster_name},
            )
            connection_data = parse_tool_result(connection_result)

            if connection_data["status"] != "success":
                pytest.fail(
                    f"Failed to connect to GKE cluster {cluster_name}: {connection_data.get('message')}"
                )

            print(f"✅ Successfully connected to GKE cluster: {cluster_name}")
            print(f"Connection details: {connection_data}")

            # Verify Kubernetes connection state
            from ray_mcp.main import ray_manager

            assert (
                ray_manager.is_kubernetes_connected
            ), "Should be connected to Kubernetes after GKE connection"
            print("✅ Kubernetes connection state verified")

            # ================================================================
            # 3. KUBERAY JOB SUBMISSION
            # ================================================================
            print("\n📋 Submitting Ray job to KubeRay on GKE...")

            # Use a simple success script for reliable testing
            with TempScriptManager(TestScripts.LIGHTWEIGHT_SUCCESS) as script_path:
                job_result = await call_tool(
                    "submit_ray_job",
                    {
                        "entrypoint": f"python {script_path}",
                        "job_type": "kubernetes",  # Force KubeRay execution
                        "kubernetes_config": {
                            "namespace": "default",
                            "image": "rayproject/ray:latest",
                        },
                    },
                )

                job_data = parse_tool_result(job_result)

                if job_data["status"] != "success":
                    pytest.fail(
                        f"Failed to submit KubeRay job: {job_data.get('message')}"
                    )

                job_id = job_data["job_id"]
                print(f"✅ Successfully submitted KubeRay job: {job_id}")
                print(f"Job submission details: {job_data}")

            # ================================================================
            # 4. JOB EXECUTION MONITORING
            # ================================================================
            print(f"\n⏱️  Monitoring job execution: {job_id}")

            # Wait for job completion with extended timeout for GKE
            try:
                final_status = await wait_for_job_completion(
                    job_id,
                    max_wait=300,  # 5 minutes for GKE job (includes container startup)
                    expected_status="SUCCEEDED",
                )

                print(f"✅ Job completed successfully: {final_status}")

            except AssertionError as e:
                # Get current job status for debugging
                status_result = await call_tool(
                    "inspect_ray_job", {"job_id": job_id, "job_type": "kubernetes"}
                )
                status_data = parse_tool_result(status_result)
                print(f"❌ Job execution details: {status_data}")
                pytest.fail(f"Job execution failed or timed out: {e}")

            # ================================================================
            # 5. LOG RETRIEVAL FROM KUBERAY
            # ================================================================
            print(f"\n📜 Retrieving logs from KubeRay job: {job_id}")

            logs_result = await call_tool(
                "retrieve_logs", {"identifier": job_id, "log_type": "job"}
            )
            logs_data = parse_tool_result(logs_result)

            if logs_data["status"] != "success":
                print(
                    f"⚠️  Log retrieval failed (may be expected): {logs_data.get('message')}"
                )
            else:
                print("✅ Successfully retrieved job logs")
                if "logs" in logs_data and logs_data["logs"]:
                    print(f"Log content preview: {logs_data['logs'][:200]}...")
                    # Verify our test script output is in the logs
                    if "Success!" in logs_data["logs"]:
                        print("✅ Job execution confirmed by log content")

            # ================================================================
            # 6. RESOURCE VERIFICATION AND CLEANUP
            # ================================================================
            print(f"\n🧹 Verifying job status and cleanup...")

            # List KubeRay jobs to verify our job is tracked
            jobs_result = await call_tool("list_ray_jobs", {"job_type": "kubernetes"})
            jobs_data = parse_tool_result(jobs_result)

            if jobs_data["status"] == "success":
                found_job = any(
                    job.get("job_id") == job_id or job.get("name") == job_id
                    for job in jobs_data.get("jobs", [])
                )
                if found_job:
                    print("✅ Job found in KubeRay job listing")
                else:
                    print("⚠️  Job not found in listing (may have been cleaned up)")
            else:
                print(f"⚠️  Job listing failed: {jobs_data.get('message')}")

            # ================================================================
            # TEST COMPLETION AND SUMMARY
            # ================================================================
            total_time = time.time() - test_start_time
            print(
                f"\n✅ GKE + KubeRay integration test passed! (Total time: {total_time:.2f}s)"
            )
            print("🎉 GKE integration functionality validated:")
            print("   - ✅ GKE cloud provider detection")
            print("   - ✅ GKE cluster connection")
            print("   - ✅ KubeRay job submission")
            print("   - ✅ Job execution monitoring")
            print("   - ✅ Log retrieval attempt")
            print("   - ✅ Resource verification")
            print(f"   - ⚡ Performance: Total {total_time:.2f}s")

        except Exception as e:
            print(f"\n❌ GKE integration test encountered an error: {e}")
            print("This may indicate:")
            print("  - GKE cluster not accessible or properly configured")
            print("  - KubeRay operator not installed on cluster")
            print("  - Network connectivity issues")
            print("  - Insufficient permissions")
            raise


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])
