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
import subprocess
import tempfile
import time
from typing import Any, Dict, List

from mcp.types import TextContent
import pytest

# Import the actual server components (no mocking)
from ray_mcp.main import call_tool
from ray_mcp.tools import get_ray_tools


@pytest.fixture(scope="session", autouse=True)
def cleanup_after_all_tests():
    """Enhanced final cleanup after all tests complete."""
    yield  # This runs after all tests

    # Enhanced final cleanup with Ray-specific thread targeting
    try:
        # Set environment to force Ray cleanup

        os.environ["RAY_DISABLE_USAGE_STATS"] = "1"
        os.environ["RAY_memory_monitor_refresh_ms"] = "0"

        cleanup_all_ray_processes()

        # Enhanced thread cleanup with specific Ray thread targeting
        import threading
        import time

        print("🧹 Final cleanup: checking background threads...")
        main_thread = threading.current_thread()
        ray_threads = []

        for thread in threading.enumerate():
            if thread is not main_thread and thread.is_alive():
                thread_name_lower = thread.name.lower()
                is_ray_thread = any(
                    keyword in thread_name_lower
                    for keyword in [
                        "ray",
                        "raylet",
                        "gcs",
                        "plasma",
                        "dashboard",
                        "monitor",
                        "listener",
                        "logger",
                    ]
                )

                print(
                    f"  Found thread: {thread.name} (daemon: {thread.daemon}, ray: {is_ray_thread})"
                )

                if is_ray_thread:
                    ray_threads.append(thread)

        # Force terminate Ray-specific threads
        for thread in ray_threads:
            try:
                if hasattr(thread, "_stop"):
                    thread._stop()
                thread.daemon = True  # Convert to daemon
                thread.join(timeout=0.5)
            except Exception as e:
                print(f"  Failed to stop thread {thread.name}: {e}")
                pass

        # Force garbage collection
        import gc

        gc.collect()
        
        # Reset the global LLM parser to clean up OpenAI client
        try:
            import asyncio
            from ray_mcp.llm_parser import reset_global_parser
            # Only reset if not in an async context - session cleanup is sync
            try:
                asyncio.run(reset_global_parser())
            except RuntimeError:
                # If there's already an event loop running, skip the reset
                # This will be handled in individual test teardowns
                print("Skipping parser reset in session cleanup - will be handled in test teardown")
        except Exception as e:
            print(f"Failed to reset global parser in cleanup: {e}")

        # Final process cleanup with more comprehensive patterns

        try:
            # Kill Ray processes more comprehensively
            ray_process_patterns = [
                "ray",
                "raylet",
                "gcs_server",
                "dashboard",
                "ray-mcp",
            ]
            for pattern in ray_process_patterns:
                subprocess.run(
                    ["pkill", "-9", "-f", pattern],
                    capture_output=True,
                    check=False,
                    timeout=3,
                )
        except Exception as e:
            print(f"  Process cleanup error: {e}")
            pass

        print("🧹 Final cleanup completed")

    except Exception as e:
        print(f"🚨 Final cleanup failed: {e}")
        pass


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

    @staticmethod
    def validate_openai_config():
        """Validate OpenAI configuration for e2e tests."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            pytest.skip("OPENAI_API_KEY not set - skipping e2e tests that require OpenAI")
        return api_key


async def cleanup_ray():
    """Enhanced Ray cleanup with proper thread and event loop management."""
    try:
        import asyncio
        import threading

        import ray

        # Step 1: Shutdown Ray with timeout
        if ray.is_initialized():
            try:
                # Use run_in_executor for thread safety with timeout
                loop = asyncio.get_event_loop()
                executor_task = loop.run_in_executor(None, ray.shutdown)
                await asyncio.wait_for(executor_task, timeout=10.0)
                # Give a moment for the executor task to complete
                await asyncio.sleep(0.1)
            except asyncio.TimeoutError:
                print("Ray shutdown timed out, forcing cleanup...")
                pass

        # Step 2: Force terminate Ray daemon threads
        main_thread = threading.current_thread()
        for thread in threading.enumerate():
            if thread is not main_thread and thread.is_alive():
                # Target specific Ray threads
                thread_name_lower = thread.name.lower()
                if any(
                    name in thread_name_lower
                    for name in [
                        "ray",
                        "listener",
                        "logger",
                        "monitor",
                        "raylet",
                        "gcs",
                        "plasma",
                    ]
                ):
                    try:
                        # Set as daemon thread to allow process to exit
                        if not thread.daemon:
                            thread.daemon = True
                    except:
                        pass

        # Step 3: Close asyncio event loop executors - ONLY if no tasks are pending
        try:
            loop = asyncio.get_running_loop()
            # Check if there are any pending tasks before shutting down executor
            pending_tasks = [task for task in asyncio.all_tasks() if not task.done()]
            if not pending_tasks and hasattr(loop, "shutdown_default_executor"):
                await asyncio.wait_for(loop.shutdown_default_executor(), timeout=2.0)
        except (RuntimeError, asyncio.TimeoutError):
            pass

        # Brief wait for cleanup
        await asyncio.sleep(0.2)

    except Exception as e:
        print(f"Ray cleanup error: {e}")
        pass

    # Force cleanup any stubborn Ray processes immediately
    try:

        # Kill all Ray-related processes more aggressively
        processes_to_kill = [
            "ray::",
            "ray_",
            "raylet",
            "gcs_server",
            "dashboard",
            "python.*ray",
        ]

        for process_pattern in processes_to_kill:
            try:
                subprocess.run(
                    ["pkill", "-9", "-f", process_pattern],
                    capture_output=True,
                    check=False,
                    timeout=2,
                )
            except:
                pass

        # Brief wait for process cleanup
        await asyncio.sleep(0.1)
    except:
        pass

    # Also try command line cleanup
    try:

        subprocess.run(["ray", "stop"], capture_output=True, check=False, timeout=3)
    except:
        pass


def cleanup_all_ray_processes():
    """Nuclear cleanup option - use only when tests are completely stuck."""
    try:

        # Kill all Ray-related processes
        processes_to_kill = [
            "ray::",
            "ray_",
            "raylet",
            "gcs_server",
            "dashboard",
            "python.*ray",
            "python.*pytest.*e2e",
        ]

        for process_pattern in processes_to_kill:
            try:
                subprocess.run(
                    ["pkill", "-f", process_pattern],
                    capture_output=True,
                    check=False,
                    timeout=5,
                )
            except:
                pass

        # Force kill any remaining processes
        try:
            subprocess.run(
                ["pkill", "-9", "-f", "ray"],
                capture_output=True,
                check=False,
                timeout=5,
            )
        except:
            pass

    except:
        pass


def create_test_script(script_content: str) -> str:
    """Create a temporary test script and return its path."""

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
        # Validate OpenAI configuration 
        E2ETestConfig.validate_openai_config()

        # Store original Ray environment variables for restoration
        self.original_gcs_timeout = os.environ.get(
            "RAY_gcs_server_request_timeout_seconds"
        )
        self.original_ray_log_level = os.environ.get("RAY_LOG_LEVEL")
        self.original_memory_monitor = os.environ.get("RAY_memory_monitor_refresh_ms")
        self.original_kill_child = os.environ.get(
            "RAY_kill_child_processes_on_worker_exit"
        )

        # Set Ray environment variables to prevent background processes and hanging
        os.environ["RAY_gcs_server_request_timeout_seconds"] = (
            "5"  # Fast timeout for invalid connections
        )
        os.environ["RAY_LOG_LEVEL"] = "CRITICAL"  # Suppress all but critical logs
        os.environ["RAY_DISABLE_USAGE_STATS"] = (
            "1"  # Disable usage statistics collection
        )
        os.environ["RAY_memory_monitor_refresh_ms"] = "0"  # Disable memory monitor
        os.environ["RAY_kill_child_processes_on_worker_exit"] = (
            "true"  # Kill child processes
        )
        os.environ["RAY_worker_register_timeout_seconds"] = (
            "10"  # Faster worker timeout
        )

        # Configure LLM model for faster testing (use cheaper/faster model if available)
        if not os.getenv("LLM_MODEL"):
            os.environ["LLM_MODEL"] = "gpt-3.5-turbo"
        
        # Enable enhanced output for better debugging
        os.environ["RAY_MCP_ENHANCED_OUTPUT"] = "true"

    async def teardown_method(self):
        """Clean up after each test."""
        # Restore original Ray environment variables
        if self.original_gcs_timeout is not None:
            os.environ["RAY_gcs_server_request_timeout_seconds"] = (
                self.original_gcs_timeout
            )
        else:
            os.environ.pop("RAY_gcs_server_request_timeout_seconds", None)

        if self.original_ray_log_level is not None:
            os.environ["RAY_LOG_LEVEL"] = self.original_ray_log_level
        else:
            os.environ.pop("RAY_LOG_LEVEL", None)

        if self.original_memory_monitor is not None:
            os.environ["RAY_memory_monitor_refresh_ms"] = self.original_memory_monitor
        else:
            os.environ.pop("RAY_memory_monitor_refresh_ms", None)

        if self.original_kill_child is not None:
            os.environ["RAY_kill_child_processes_on_worker_exit"] = (
                self.original_kill_child
            )
        else:
            os.environ.pop("RAY_kill_child_processes_on_worker_exit", None)

        # Enhanced cleanup
        await cleanup_ray()
        
        # Reset the global LLM parser to clean up OpenAI client
        try:
            from ray_mcp.llm_parser import reset_global_parser
            await reset_global_parser()
        except Exception as e:
            print(f"Failed to reset global parser: {e}")

        # Force garbage collection to clean up any lingering objects
        import gc

        gc.collect()

        # Clear any remaining asyncio tasks with timeout
        try:
            import asyncio

            tasks = [task for task in asyncio.all_tasks() if not task.done()]
            for task in tasks:
                if not task.cancelled():
                    task.cancel()
            if tasks:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True), timeout=1.0
                )
        except (asyncio.TimeoutError, RuntimeError):
            pass

    @pytest.mark.asyncio
    async def test_complete_ray_workflow(self):
        """Test complete Ray workflow: create cluster, submit job, get logs, cleanup."""
        print("🚀 Testing complete Ray workflow...")

        await cleanup_ray()

        try:
            # Step 1: Create local Ray cluster
            print("📡 Creating Ray cluster...")
            result = await call_tool(
                "ray_cluster",
                {
                    "prompt": f"Create a local Ray cluster with {E2ETestConfig.CPU_LIMIT} CPUs and dashboard on port {E2ETestConfig.DASHBOARD_PORT}"
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
            result = await call_tool(
                "ray_cluster", {"prompt": "Check the status of the current Ray cluster"}
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
                result = await call_tool(
                    "ray_job", {"prompt": f"Submit a Ray job using script {script_path}"}
                )

                response = parse_tool_response(result)
                print(f"Job submission response: {response}")

                assert (
                    response["status"] == "success"
                ), f"Job submission failed: {response}"
                # Job ID might be in job_id or job_name field depending on implementation
                job_id = response.get("job_id") or response.get("job_name")
                assert job_id is not None, f"No job ID found in response: {response}"

                # Step 4: Wait for job completion and check status
                print(f"⏳ Waiting for job {job_id} to complete...")

                max_wait_time = E2ETestConfig.JOB_COMPLETION_TIMEOUT
                wait_interval = 5
                elapsed_time = 0

                job_status = None
                while elapsed_time < max_wait_time:
                    result = await call_tool(
                        "ray_job", {"prompt": f"Get the status of Ray job {job_id}"}
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
                    result = await call_tool(
                        "ray_job", {"prompt": f"Get the logs for Ray job {job_id}"}
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
                result = await call_tool(
                    "ray_job", {"prompt": f"Get the logs for Ray job {job_id}"}
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
                result = await call_tool("ray_job", {"prompt": "List all Ray jobs"})

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
                result = await call_tool(
                    "ray_cluster", {"prompt": "Stop the current Ray cluster"}
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
        result = await call_tool(
            "ray_job", {"prompt": "Submit a Ray job using script nonexistent.py"}
        )

        response = parse_tool_response(result)
        assert response["status"] == "error"
        assert (
            "not running" in response["message"].lower()
            or "not available" in response["message"].lower()
        )

        # Test 2: Try to connect to invalid cluster
        print("Test 2: Connect to invalid cluster...")
        result = await call_tool(
            "ray_cluster", {"prompt": "Connect to Ray cluster at address 192.0.2.1:9999"}
        )

        response = parse_tool_response(result)
        assert response["status"] == "error"

        # Explicitly clean up any Ray processes that might have started
        # This is especially important after invalid connection attempts
        await cleanup_ray()

        # Extra cleanup for stubborn background processes
        try:

            # Force kill any remaining ray processes
            subprocess.run(["pkill", "-f", "ray"], capture_output=True, check=False)
            await asyncio.sleep(1)
        except:
            pass

        # Test 3: Try to inspect non-existent cluster
        print("Test 3: Inspect non-existent cluster...")
        result = await call_tool("ray_cluster", {"prompt": "Check the status of the Ray cluster"})

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
            ("ray_job", "Submit a Ray job using script train.py"),  # Mixed case
            ("ray_job", "List all jobs"),  # Minimal
            ("cloud", "Authenticate with GCP"),  # Abbreviated
        ]

        for tool_name, prompt in valid_prompts:
            print(f"Testing: {tool_name} - '{prompt}'")
            result = await call_tool(tool_name, {"prompt": prompt})
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
                "ray_cluster": "Check cluster status",
                "ray_job": "List all jobs",
                "cloud": "Check cloud environment",
            }

            prompt = minimal_prompts.get(tool.name)
            if prompt:
                print(f"Testing tool: {tool.name}")
                result = await call_tool(tool.name, {"prompt": prompt})
                response = parse_tool_response(result)

                # All tools should return valid responses (success or error)
                assert "status" in response
                assert response["status"] in ["success", "error"]

                # All responses should include a message (some may have it empty for list operations)
                # For list operations, message might not be present
                if "message" in response:
                    assert isinstance(response["message"], str)
                    assert len(response["message"]) > 0

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test concurrent operations don't interfere with each other."""
        print("🔄 Testing concurrent operations...")

        await cleanup_ray()

        # Test concurrent cluster inspections (should be safe)
        tasks = [
            call_tool("ray_cluster", {"prompt": "Check cluster status"})
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
        result = await call_tool(
            "ray_cluster",
            {"prompt": f"Create a Ray cluster with {E2ETestConfig.CPU_LIMIT} CPUs"},
        )
        response = parse_tool_response(result)

        if response["status"] == "success":
            # Verify it's running
            result = await call_tool("ray_cluster", {"prompt": "Check cluster status"})
            response = parse_tool_response(result)
            assert response["status"] == "success"
            assert response["cluster_status"] == "running"

            # Stop it
            result = await call_tool("ray_cluster", {"prompt": "Stop the cluster"})
            response = parse_tool_response(result)
            assert response["status"] == "success"

            # Verify it's stopped
            await asyncio.sleep(2)
            result = await call_tool("ray_cluster", {"prompt": "Check cluster status"})
            response = parse_tool_response(result)
            assert response["status"] == "success"
            assert response["cluster_status"] == "not_running"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
