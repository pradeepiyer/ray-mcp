#!/usr/bin/env python3
"""Example demonstrating connection to existing Ray clusters with parameter filtering."""

import asyncio
import json
from pathlib import Path
import sys

# Add the parent directory to the path so we can import ray_mcp
sys.path.insert(0, str(Path(__file__).parent.parent))

from ray_mcp.ray_manager import RayManager


async def demonstrate_connect_existing_cluster():
    """Demonstrate connecting to an existing Ray cluster with parameter filtering."""

    print("=== Connect to Existing Ray Cluster Example ===")

    # Create Ray manager
    ray_manager = RayManager()

    try:
        # Example 1: Connect to existing cluster with filtered parameters
        print(
            "\n1. Connecting to existing cluster with cluster-starting parameters (will be filtered)..."
        )

        # Note: These cluster-starting parameters will be filtered out and logged
        result = await ray_manager.start_cluster(
            address="ray://127.0.0.1:10001",  # Connect to existing cluster
            num_cpus=8,  # Will be filtered out (cluster-starting parameter)
            num_gpus=2,  # Will be filtered out (cluster-starting parameter)
            object_store_memory=1000000000,  # Will be filtered out (cluster-starting parameter)
            head_node_port=20001,  # Will be filtered out (cluster-starting parameter)
            dashboard_port=9000,  # Will be filtered out (cluster-starting parameter)
            head_node_host="0.0.0.0",  # Will be filtered out (cluster-starting parameter)
            worker_nodes=[
                {"num_cpus": 4}
            ],  # Will be filtered out (cluster-starting parameter)
            custom_param="should_pass",  # Will be passed through (valid parameter)
            another_param=123,  # Will be passed through (valid parameter)
        )

        print(f"Connection result: {json.dumps(result, indent=2)}")
        print("Note: Check the logs above to see which parameters were filtered out.")

        # Example 2: Use connect_cluster method with filtered parameters
        print("\n2. Using connect_cluster method with cluster-starting parameters...")

        # Create a new manager instance for this example
        ray_manager2 = RayManager()

        result2 = await ray_manager2.connect_cluster(
            "ray://127.0.0.1:10001",  # Connect to existing cluster
            num_cpus=16,  # Will be filtered out (cluster-starting parameter)
            num_gpus=4,  # Will be filtered out (cluster-starting parameter)
            object_store_memory=2000000000,  # Will be filtered out (cluster-starting parameter)
            head_node_port=30001,  # Will be filtered out (cluster-starting parameter)
            dashboard_port=10000,  # Will be filtered out (cluster-starting parameter)
            head_node_host="192.168.1.1",  # Will be filtered out (cluster-starting parameter)
            worker_nodes=[
                {"num_cpus": 8}
            ],  # Will be filtered out (cluster-starting parameter)
            custom_param="also_passes",  # Will be passed through (valid parameter)
            another_param=456,  # Will be passed through (valid parameter)
        )

        print(f"Connection result: {json.dumps(result2, indent=2)}")
        print("Note: Check the logs above to see which parameters were filtered out.")

        # Example 3: Connect with only valid parameters (no filtering needed)
        print("\n3. Connecting with only valid parameters (no filtering)...")

        ray_manager3 = RayManager()

        result3 = await ray_manager3.connect_cluster(
            "ray://127.0.0.1:10001",  # Connect to existing cluster
            custom_param="no_filtering_needed",  # Valid parameter
            another_param=789,  # Valid parameter
            ignore_reinit_error=True,  # Valid parameter
        )

        print(f"Connection result: {json.dumps(result3, indent=2)}")
        print("Note: No parameters were filtered out in this case.")

        # Example 4: Get cluster info to verify connection
        print("\n4. Getting cluster information...")
        cluster_info = await ray_manager.get_cluster_info()
        print(f"Cluster info: {json.dumps(cluster_info, indent=2)}")

        # Example 5: Stop the cluster
        print("\n5. Stopping the cluster...")
        stop_result = await ray_manager.stop_cluster()
        print(f"Stop result: {json.dumps(stop_result, indent=2)}")

        print("\n=== Example Completed Successfully ===")

    except Exception as e:
        print(f"ERROR: Example failed with exception: {e}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")

        # Cleanup: stop cluster if it was started
        try:
            await ray_manager.stop_cluster()
        except:
            pass


def main():
    """Main function to run the example."""
    asyncio.run(demonstrate_connect_existing_cluster())


if __name__ == "__main__":
    main()
