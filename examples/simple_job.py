#!/usr/bin/env python3
"""Simple Ray job example for testing the MCP server."""

import os
import sys
import time

import ray


@ray.remote
def simple_task(n: int) -> str:
    """A simple task for testing."""
    print(f"Running task with n={n}")
    result = n * n
    print(f"Task completed: {n}^2 = {result}")
    return f"Task result: {result}"


def main():
    """Main function to run the example."""
    ray_initialized_by_script = False

    try:
        print("=== Starting Simple Ray Job ===")
        print(f"Python version: {sys.version}")
        print(f"Current directory: {os.getcwd()}")
        print(f"Ray version: {ray.__version__}")

        # Check if Ray is already initialized (it should be in job context)
        if not ray.is_initialized():
            print("Ray is not initialized, initializing now...")
            ray.init()
            ray_initialized_by_script = True
        else:
            print("Ray is already initialized (job context)")

        # Get cluster resources
        print("Getting cluster information...")
        cluster_resources = ray.cluster_resources()
        available_resources = ray.available_resources()
        print(f"Cluster resources: {cluster_resources}")
        print(f"Available resources: {available_resources}")

        # Run some simple tasks
        print("\n=== Running Simple Tasks ===")
        futures = [simple_task.remote(i) for i in range(1, 4)]
        results = ray.get(futures)

        for result in results:
            print(result)

        print("\n=== Job Completed Successfully ===")
        print("All tasks completed successfully!")

        # Only shutdown Ray if we initialized it
        if ray_initialized_by_script:
            ray.shutdown()
            print("Ray shutdown complete (initialized by script).")
        else:
            print("Job execution complete (Ray managed externally).")

    except Exception as e:
        print(f"ERROR: Job failed with exception: {e}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")

        # Cleanup: shutdown Ray if we initialized it
        if ray_initialized_by_script and ray.is_initialized():
            ray.shutdown()
            print("Ray shutdown during error cleanup.")

        raise


if __name__ == "__main__":
    main()
