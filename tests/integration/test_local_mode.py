#!/usr/bin/env python3
"""
Comprehensive local mode testing for Ray MCP server without Claude Desktop.
This script tests all core functionality using direct tool calls.
"""

import asyncio
import json
from pathlib import Path
import sys

# Add the ray_mcp package to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.helpers.e2e import (
    start_ray_cluster,
    stop_ray_cluster,
    submit_and_wait_for_job,
)
from tests.helpers.utils import call_tool, parse_tool_result


async def test_local_cluster_lifecycle():
    """Test complete local cluster lifecycle."""
    print("🔧 Testing local cluster lifecycle...")

    # Test cluster creation
    result = await call_tool(
        "ray_cluster", {"prompt": "create a local cluster with 4 CPUs"}
    )
    response = parse_tool_result(result)
    print(f"✅ Cluster creation: {response['status']}")

    if response["status"] != "success":
        print(f"❌ Cluster creation failed: {response['message']}")
        return False

    # Test cluster inspection
    result = await call_tool("ray_cluster", {"prompt": "inspect cluster status"})
    response = parse_tool_result(result)
    print(f"✅ Cluster inspection: {response['status']}")

    # Test cluster shutdown
    result = await call_tool("ray_cluster", {"prompt": "stop cluster"})
    response = parse_tool_result(result)
    print(f"✅ Cluster shutdown: {response['status']}")

    return True


async def test_local_job_submission():
    """Test local job submission and monitoring."""
    print("💼 Testing local job submission...")

    try:
        # Start cluster first
        await start_ray_cluster(cpu_limit=2)

        # Create a simple test script
        test_script = """#!/usr/bin/env python3
import time
import sys

# Simple test job that doesn't require Ray imports
def simple_task(x):
    time.sleep(0.1)
    return x * 2

# Run tasks
results = []
for i in range(5):
    result = simple_task(i)
    results.append(result)
    
print(f"Results: {results}")
print("Job completed successfully!")
"""

        try:
            # Submit job
            print("Debug - About to submit job...")
            job_id, final_status = await submit_and_wait_for_job(
                test_script, expected_status="SUCCEEDED"
            )
            print(
                f"Debug - Job submission result: job_id={job_id}, final_status={final_status}"
            )
            print(f"✅ Job {job_id} completed successfully")

            # Test job logs
            result = await call_tool(
                "ray_job", {"prompt": f"get logs for job {job_id}"}
            )
            response = parse_tool_result(result)
            print(f"Debug - Job logs response: {response}")
            print(f"✅ Job logs retrieved: {response['status']}")

        finally:
            # Clean up
            await stop_ray_cluster()

        return True

    except Exception as e:
        print(f"Debug - Exception in test_local_job_submission: {e}")
        print(f"Debug - Exception type: {type(e)}")
        import traceback

        traceback.print_exc()
        return False


async def test_local_error_handling():
    """Test error handling in local mode."""
    print("🚨 Testing error handling...")

    # Test job submission without cluster
    result = await call_tool("ray_job", {"prompt": "submit job with script test.py"})
    response = parse_tool_result(result)
    print(f"✅ No cluster error handling: {response['status']}")

    # Test invalid cluster operations (use quick-failing operations)
    result = await call_tool("ray_cluster", {"prompt": "stop nonexistent cluster"})
    response = parse_tool_result(result)
    print(f"✅ Invalid cluster operation handling: {response['status']}")

    # Test invalid job operations
    result = await call_tool("ray_job", {"prompt": "cancel nonexistent job"})
    response = parse_tool_result(result)
    print(f"✅ Invalid job operation handling: {response['status']}")

    return True


async def test_all_tools_consistency():
    """Test that all tools follow consistent patterns."""
    print("🔧 Testing tool consistency...")

    tools = ["ray_cluster", "ray_job", "cloud"]
    minimal_prompts = {
        "ray_cluster": "inspect cluster status",
        "ray_job": "list all jobs",
        "cloud": "check environment",
    }

    # Expected behaviors for each tool when no cluster is running
    expected_behaviors = {
        "ray_cluster": ["success", "error"],  # May return success (no cluster) or error
        "ray_job": ["error"],  # Should return error when no cluster is running
        "cloud": ["success", "error"],  # May return success or error depending on setup
    }

    for tool_name in tools:
        prompt = minimal_prompts[tool_name]
        result = await call_tool(tool_name, {"prompt": prompt})
        response = parse_tool_result(result)

        # All tools should return valid responses
        assert "status" in response
        assert (
            response["status"] in expected_behaviors[tool_name]
        ), f"{tool_name} returned unexpected status: {response['status']}"
        assert "message" in response

        print(
            f"✅ {tool_name}: {response['status']} (expected: {expected_behaviors[tool_name]})"
        )

    return True


async def main():
    """Run all local mode tests."""
    print("🚀 Starting comprehensive local mode testing...")
    print("=" * 60)

    tests = [
        test_all_tools_consistency,
        test_local_error_handling,
        test_local_cluster_lifecycle,
        test_local_job_submission,
    ]

    results = []

    for test in tests:
        try:
            print(f"\n🧪 Running {test.__name__}...")
            result = await test()
            results.append((test.__name__, result))
            print(f"✅ {test.__name__}: {'PASS' if result else 'FAIL'}")
        except Exception as e:
            print(f"❌ {test.__name__}: ERROR - {str(e)}")
            results.append((test.__name__, False))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary:")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")

    print(f"\n🎯 Results: {passed}/{total} tests passed")

    return passed == total


async def cleanup_resources():
    """Ensure all Ray resources are properly cleaned up."""
    try:
        import subprocess

        import ray

        # Force shutdown Ray if it's still running
        if ray.is_initialized():
            ray.shutdown()

        # Run ray stop to clean up any external processes
        subprocess.run(["ray", "stop"], capture_output=True, check=False, timeout=5)

        print("✅ Resource cleanup completed")
    except Exception as e:
        print(f"⚠️  Resource cleanup warning: {e}")


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        # Basic cleanup before exit
        asyncio.run(cleanup_resources())

        if success:
            print("🎉 All tests completed successfully!")
        else:
            print("💥 Some tests failed!")

        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n🛑 Testing interrupted by user")
        asyncio.run(cleanup_resources())
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Testing failed with error: {e}")
        asyncio.run(cleanup_resources())
        sys.exit(1)
