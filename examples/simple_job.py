#!/usr/bin/env python3
"""Simple Ray job example for testing the MCP server."""

import ray
import time
import numpy as np


@ray.remote
def compute_pi(n_samples: int) -> float:
    """Monte Carlo method to estimate pi."""
    np.random.seed()
    inside_circle = 0
    
    for _ in range(n_samples):
        x, y = np.random.uniform(-1, 1, 2)
        if x**2 + y**2 <= 1:
            inside_circle += 1
    
    return 4.0 * inside_circle / n_samples


@ray.remote
def slow_task(duration: int, task_id: int) -> str:
    """A slow task for testing job monitoring."""
    print(f"Task {task_id} starting, will take {duration} seconds")
    time.sleep(duration)
    print(f"Task {task_id} completed")
    return f"Task {task_id} completed after {duration} seconds"


def main():
    """Main function to run the example."""
    # Initialize Ray
    ray.init()
    print("Ray initialized successfully!")
    
    # Get cluster resources
    print("Cluster resources:", ray.cluster_resources())
    print("Available resources:", ray.available_resources())
    
    # Example 1: Compute pi using multiple workers
    print("\n=== Computing Pi with Monte Carlo Method ===")
    n_samples_per_task = 1000000
    n_tasks = 4
    
    # Submit tasks
    pi_futures = [compute_pi.remote(n_samples_per_task) for _ in range(n_tasks)]
    pi_estimates = ray.get(pi_futures)
    
    # Average the estimates
    pi_estimate = sum(pi_estimates) / len(pi_estimates)
    print(f"Pi estimate: {pi_estimate} (using {n_tasks * n_samples_per_task} samples)")
    
    # Example 2: Run some slow tasks for monitoring
    print("\n=== Running Slow Tasks ===")
    slow_futures = [slow_task.remote(5, i) for i in range(3)]
    slow_results = ray.get(slow_futures)
    
    for result in slow_results:
        print(result)
    
    print("\nJob completed successfully!")
    
    # Shutdown Ray
    ray.shutdown()
    print("Ray shutdown complete.")


if __name__ == "__main__":
    main() 