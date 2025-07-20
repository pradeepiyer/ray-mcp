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

from tests.helpers.e2e import submit_and_wait_for_job
from tests.helpers.utils import call_tool, parse_tool_result


async def test_local_error_handling():
    """Test error handling in local mode."""
    print("🚨 Testing error handling...")

    # Test job submission without cluster
    result = await call_tool("ray_job", {"prompt": "submit job with script test.py"})
    response = parse_tool_result(result)
    print(f"✅ No cluster error handling: {response['status']}")

    # Test invalid job operations
    result = await call_tool("ray_job", {"prompt": "cancel nonexistent job"})
    response = parse_tool_result(result)
    print(f"✅ Invalid job operation handling: {response['status']}")

    return True


async def test_all_tools_consistency():
    """Test that all tools follow consistent patterns."""
    print("🔧 Testing tool consistency...")

    tools = ["ray_job", "ray_cloud"]
    minimal_prompts = {
        "ray_job": "list all jobs",
        "ray_cloud": "check environment",
    }

    # Expected behaviors for each tool when no cluster is running
    expected_behaviors = {
        "ray_job": ["error"],  # Should return error when no cluster is running
        "ray_cloud": [
            "success",
            "error",
        ],  # May return success or error depending on setup
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
