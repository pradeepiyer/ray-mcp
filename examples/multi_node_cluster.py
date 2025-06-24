#!/usr/bin/env python3
"""Example demonstrating multi-node Ray cluster setup."""

import asyncio
import json
import sys
from pathlib import Path

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
                "object_store_memory": 500000000,  # 500MB
                "node_name": "worker-1"
            },
            {
                "num_cpus": 4,
                "num_gpus": 0,
                "object_store_memory": 1000000000,  # 1GB
                "node_name": "worker-2",
                "resources": {"custom_resource": 2}
            }
        ]
        
        result = await ray_manager.start_cluster(
            num_cpus=4,  # Head node: 4 CPUs
            num_gpus=0,  # Head node: 0 GPUs
            object_store_memory=1000000000,  # Head node: 1GB
            worker_nodes=worker_configs,
            head_node_port=10001,
            dashboard_port=8265,
            head_node_host="127.0.0.1"
        )
        
        print(f"Cluster start result: {json.dumps(result, indent=2)}")
        
        # Example 2: Get cluster status
        print("\n2. Getting cluster status...")
        status = await ray_manager.get_cluster_status()
        print(f"Cluster status: {json.dumps(status, indent=2)}")
        
        # Example 3: Get worker status
        print("\n3. Getting worker node status...")
        worker_status = await ray_manager.get_worker_status()
        print(f"Worker status: {json.dumps(worker_status, indent=2)}")
        
        # Example 4: Get cluster resources
        print("\n4. Getting cluster resources...")
        resources = await ray_manager.get_cluster_resources()
        print(f"Cluster resources: {json.dumps(resources, indent=2)}")
        
        # Example 5: Get cluster nodes
        print("\n5. Getting cluster nodes...")
        nodes = await ray_manager.get_cluster_nodes()
        print(f"Cluster nodes: {json.dumps(nodes, indent=2)}")
        
        # Example 6: Stop the cluster
        print("\n6. Stopping the cluster...")
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