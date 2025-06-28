#!/usr/bin/env python3
"""Example demonstrating multi-node Ray cluster setup."""

import asyncio
import json
from pathlib import Path
import sys

# Add the parent directory to the path so we can import ray_mcp
sys.path.insert(0, str(Path(__file__).parent.parent))

from ray_mcp.ray_manager import RayManager


async def demonstrate_multi_node_cluster():
    """Demonstrate starting a Ray cluster with multiple worker nodes."""

    print("=== Multi-Node Ray Cluster Example ===")

    # Create Ray manager
    ray_manager = RayManager()

    try:
        # Example 1: Start a cluster with 2 worker nodes
        print("\n1. Starting cluster with head node and 2 worker nodes...")

        worker_configs = [
            {
                "num_cpus": 2,
                "num_gpus": 0,
                "object_store_memory": 500 * 1024 * 1024,  # 500MB
                "node_name": "worker-1",
            },
            {
                "num_cpus": 4,
                "num_gpus": 0,
                "object_store_memory": 1000000000,  # 1GB
                "node_name": "worker-2",
                "resources": {"custom_resource": 2},
            },
        ]

        result = await ray_manager.init_cluster(
            num_cpus=4,  # Head node: 4 CPUs
            num_gpus=0,  # Head node: 0 GPUs
            object_store_memory=1000000000,  # Head node: 1GB
            worker_nodes=worker_configs,
            head_node_port=10001,
            dashboard_port=8265,
            head_node_host="127.0.0.1",
        )

        print(f"Cluster start result: {json.dumps(result, indent=2)}")

        # Example 2: Get cluster info
        print("\n2. Getting cluster info...")
        inspect_ray = await ray_manager.inspect_ray()
        print(f"Cluster info: {json.dumps(inspect_ray, indent=2)}")

        # Example 3: Stop the cluster
        print("\n3. Stopping the cluster...")
        stop_result = await ray_manager.stop_cluster()
        print(f"Stop result: {json.dumps(stop_result, indent=2)}")

        print("\n=== Example completed successfully! ===")

    except Exception as e:
        print(f"Error during example: {e}")
        import traceback

        traceback.print_exc()


def main():
    """Main entry point."""
    asyncio.run(demonstrate_multi_node_cluster())


if __name__ == "__main__":
    main()
