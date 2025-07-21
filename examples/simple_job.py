#!/usr/bin/env python3
"""Simple Ray job example for KubeRay deployment."""

import os
import sys

import ray


@ray.remote
def simple_task(n: int) -> str:
    """A simple task for testing on Kubernetes."""
    print(f"Running task with n={n}")
    result = n * n
    print(f"Task completed: {n}^2 = {result}")
    return f"Task result: {result}"


def main():
    """Main function to run the example on KubeRay."""
    try:
        print("=== Starting Simple Ray Job on Kubernetes ===")
        print(f"Python version: {sys.version}")
        print(f"Current directory: {os.getcwd()}")
        print(f"Ray version: {ray.__version__}")

        # Ray should be initialized by KubeRay operator
        if not ray.is_initialized():
            print("Warning: Ray not initialized by KubeRay, initializing...")
            ray.init()
        else:
            print("✅ Ray initialized by KubeRay operator")

        # Get cluster resources
        print("Getting Kubernetes cluster information...")
        cluster_resources = ray.cluster_resources()
        available_resources = ray.available_resources()
        print(f"Cluster resources: {cluster_resources}")
        print(f"Available resources: {available_resources}")

        # Run some simple tasks
        print("\n=== Running Simple Tasks on Kubernetes ===")
        futures = [simple_task.remote(i) for i in range(1, 4)]
        results = ray.get(futures)

        for result in results:
            print(result)

        print("\n=== Job Completed Successfully on Kubernetes ===")
        print("All tasks completed successfully!")

    except Exception as e:
        print(f"ERROR: Job failed with exception: {e}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        raise


if __name__ == "__main__":
    main()
