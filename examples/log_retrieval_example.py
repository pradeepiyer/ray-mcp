#!/usr/bin/env python3
"""
Example demonstrating the consolidated log retrieval functionality.

This example shows how to use the new retrieve_logs tool to get logs from
jobs, actors, and nodes with comprehensive error analysis.
"""

import asyncio
import json
import sys
from typing import Any, Dict

# Check if Ray is available
try:
    import ray

    RAY_AVAILABLE = True
except ImportError:
    RAY_AVAILABLE = False
    print("Ray is not available. Please install Ray to run this example.")
    sys.exit(1)

# Import the Ray MCP tools
try:
    from ray_mcp.ray_manager import RayManager
    from ray_mcp.tool_registry import ToolRegistry
except ImportError:
    print(
        "Ray MCP tools not available. Please ensure you're running from the project root."
    )
    sys.exit(1)


async def demonstrate_log_retrieval():
    """Demonstrate the consolidated log retrieval functionality."""

    print("🚀 Ray MCP Log Retrieval Example")
    print("=" * 50)

    # Initialize the tool registry
    ray_manager = RayManager()
    registry = ToolRegistry(ray_manager)

    # Check if Ray is initialized
    if not ray.is_initialized():
        print("Initializing Ray cluster...")
        init_result = await registry.execute_tool("init_ray", {"num_cpus": 2})
        if init_result["status"] != "started":
            print(f"Failed to initialize Ray: {init_result}")
            return
        print("✅ Ray cluster initialized successfully")
    else:
        print("✅ Ray is already initialized")

    # Submit a simple job that will generate some logs
    print("\n📝 Submitting a test job...")
    job_script = """
import time
import sys

print("Starting test job...")
print("Processing data...")
time.sleep(1)
print("Data processing complete!")
print("Job finished successfully!")
"""

    # Create a temporary script file
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(job_script)
        script_path = f.name

    try:
        submit_result = await registry.execute_tool(
            "submit_job", {"entrypoint": f"python {script_path}"}
        )

        if submit_result["status"] != "submitted":
            print(f"Failed to submit job: {submit_result}")
            return

        job_id = submit_result["job_id"]
        print(f"✅ Job submitted with ID: {job_id}")

        # Wait a moment for the job to start
        await asyncio.sleep(2)

        # Demonstrate different log retrieval scenarios
        print("\n🔍 Demonstrating Log Retrieval Capabilities")
        print("-" * 40)

        # 1. Basic job logs
        print("\n1. Basic Job Logs:")
        job_logs = await registry.execute_tool(
            "retrieve_logs",
            {
                "identifier": job_id,
                "log_type": "job",
                "num_lines": 10,
                "include_errors": False,
            },
        )
        print(f"Status: {job_logs['status']}")
        if job_logs["status"] == "success":
            print(f"Log Type: {job_logs['log_type']}")
            print(f"Logs:\n{job_logs['logs']}")

        # 2. Job logs with error analysis
        print("\n2. Job Logs with Error Analysis:")
        job_logs_with_errors = await registry.execute_tool(
            "retrieve_logs",
            {
                "identifier": job_id,
                "log_type": "job",
                "num_lines": 10,
                "include_errors": True,
            },
        )
        print(f"Status: {job_logs_with_errors['status']}")
        if job_logs_with_errors["status"] == "success":
            print(f"Log Type: {job_logs_with_errors['log_type']}")
            if "error_analysis" in job_logs_with_errors:
                error_analysis = job_logs_with_errors["error_analysis"]
                print(f"Error Count: {error_analysis['error_count']}")
                print(f"Suggestions: {error_analysis['suggestions']}")

        # 3. Actor logs (limited support)
        print("\n3. Actor Logs (Limited Support):")

        # First, let's create an actor to demonstrate
        @ray.remote
        class TestActor:
            def __init__(self):
                self.counter = 0

            def increment(self):
                self.counter += 1
                return self.counter

        actor = TestActor.remote()
        # Use a simple string identifier for demonstration
        actor_id = "test_actor_demo"

        actor_logs = await registry.execute_tool(
            "retrieve_logs",
            {"identifier": actor_id, "log_type": "actor", "num_lines": 10},
        )
        print(f"Status: {actor_logs['status']}")
        if actor_logs["status"] == "partial":
            print(f"Message: {actor_logs['message']}")
            print(f"Actor Info: {actor_logs['actor_info']}")
            print(f"Suggestions: {actor_logs['suggestions']}")

        # 4. Node logs (limited support)
        print("\n4. Node Logs (Limited Support):")
        # Get cluster info to find a node ID
        cluster_info = await registry.execute_tool("cluster_info", {})
        if cluster_info["status"] == "success" and "nodes" in cluster_info:
            node_id = (
                cluster_info["nodes"][0]["node_id"]
                if cluster_info["nodes"]
                else "node_123"
            )

            node_logs = await registry.execute_tool(
                "retrieve_logs",
                {"identifier": node_id, "log_type": "node", "num_lines": 10},
            )
            print(f"Status: {node_logs['status']}")
            if node_logs["status"] == "partial":
                print(f"Message: {node_logs['message']}")
                print(f"Node Info: {node_logs['node_info']}")
                print(f"Suggestions: {node_logs['suggestions']}")

        # 5. Legacy get_logs method (backward compatibility)
        print("\n5. Legacy get_logs Method:")
        legacy_logs = await registry.execute_tool(
            "get_logs", {"job_id": job_id, "num_lines": 5}
        )
        print(f"Status: {legacy_logs['status']}")
        if legacy_logs["status"] == "success":
            print(f"Logs:\n{legacy_logs['logs']}")

        # 6. Error handling - unsupported log type
        print("\n6. Error Handling - Unsupported Log Type:")
        error_result = await registry.execute_tool(
            "retrieve_logs",
            {"identifier": "test", "log_type": "unsupported", "num_lines": 10},
        )
        print(f"Status: {error_result['status']}")
        print(f"Message: {error_result['message']}")
        print(f"Suggestion: {error_result['suggestion']}")

        print("\n✅ Log retrieval demonstration completed!")

    finally:
        # Clean up the temporary script
        import os

        if os.path.exists(script_path):
            os.unlink(script_path)

        # Stop Ray if we initialized it
        if ray.is_initialized():
            print("\n🛑 Stopping Ray cluster...")
            stop_result = await registry.execute_tool("stop_ray", {})
            print(f"Stop result: {stop_result['status']}")


def main():
    """Main entry point."""
    try:
        asyncio.run(demonstrate_log_retrieval())
    except KeyboardInterrupt:
        print("\n⚠️  Example interrupted by user")
    except Exception as e:
        print(f"❌ Example failed with error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
