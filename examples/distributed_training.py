#!/usr/bin/env python3
"""Distributed training example for testing the MCP server."""

import ray
import numpy as np
import time
from typing import List, Tuple, Dict, Any
import json


@ray.remote
class ParameterServer:
    """A parameter server that maintains model parameters."""
    
    def __init__(self, model_size: int):
        self.model_size = model_size
        self.parameters = np.random.randn(model_size) * 0.1
        self.gradients_received = 0
        self.training_history: List[Dict[str, Any]] = []
        print(f"Parameter server initialized with model size: {model_size}")
    
    def get_parameters(self) -> np.ndarray:
        """Get current model parameters."""
        return self.parameters.copy()
    
    def update_parameters(self, gradients: np.ndarray, learning_rate: float = 0.01) -> Dict[str, Any]:
        """Update parameters with gradients."""
        self.parameters -= learning_rate * gradients
        self.gradients_received += 1
        
        # Track training metrics
        param_norm = np.linalg.norm(self.parameters)
        grad_norm = np.linalg.norm(gradients)
        
        metrics = {
            "step": self.gradients_received,
            "parameter_norm": float(param_norm),
            "gradient_norm": float(grad_norm),
            "learning_rate": learning_rate,
            "timestamp": time.time()
        }
        
        self.training_history.append(metrics)
        print(f"Parameters updated - Step: {self.gradients_received}, Param norm: {param_norm:.4f}")
        
        return metrics
    
    def get_training_stats(self) -> Dict[str, Any]:
        """Get training statistics."""
        if not self.training_history:
            return {"steps": 0, "avg_param_norm": 0.0, "avg_grad_norm": 0.0}
        
        return {
            "steps": len(self.training_history),
            "avg_param_norm": np.mean([h["parameter_norm"] for h in self.training_history]),
            "avg_grad_norm": np.mean([h["gradient_norm"] for h in self.training_history]),
            "final_param_norm": self.training_history[-1]["parameter_norm"],
            "history": self.training_history[-5:]  # Last 5 steps
        }


@ray.remote
class Worker:
    """A worker that computes gradients."""
    
    def __init__(self, worker_id: str, data_size: int = 1000):
        self.worker_id = worker_id
        self.data_size = data_size
        # Generate synthetic training data
        self.X = np.random.randn(data_size, 10)  # Features
        self.y = np.random.randn(data_size)      # Targets
        self.iterations_completed = 0
        print(f"Worker {worker_id} initialized with {data_size} data points")
    
    def compute_gradients(self, parameters: np.ndarray, batch_size: int = 100) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Compute gradients using synthetic data."""
        # Select random batch
        batch_indices = np.random.choice(self.data_size, batch_size, replace=False)
        X_batch = self.X[batch_indices]
        y_batch = self.y[batch_indices]
        
        # Simple linear regression gradients (for demonstration)
        predictions = X_batch @ parameters[:10]  # Use first 10 params as weights
        errors = predictions - y_batch
        gradients = np.zeros_like(parameters)
        gradients[:10] = X_batch.T @ errors / batch_size
        
        # Add some noise to simulate realistic gradients
        gradients += np.random.randn(*gradients.shape) * 0.001
        
        self.iterations_completed += 1
        
        # Compute metrics
        loss = np.mean(errors ** 2)
        grad_norm = np.linalg.norm(gradients)
        
        metrics = {
            "worker_id": self.worker_id,
            "iteration": self.iterations_completed,
            "loss": float(loss),
            "gradient_norm": float(grad_norm),
            "batch_size": batch_size
        }
        
        print(f"Worker {self.worker_id} - Iteration {self.iterations_completed}, Loss: {loss:.4f}")
        
        return gradients, metrics
    
    def get_worker_stats(self) -> Dict[str, Any]:
        """Get worker statistics."""
        return {
            "worker_id": self.worker_id,
            "iterations_completed": self.iterations_completed,
            "data_size": self.data_size
        }


@ray.remote
def evaluate_model(parameters: np.ndarray, test_size: int = 500) -> Dict[str, Any]:
    """Evaluate the model on test data."""
    # Generate test data
    X_test = np.random.randn(test_size, 10)
    y_test = np.random.randn(test_size)
    
    # Make predictions
    predictions = X_test @ parameters[:10]
    
    # Compute metrics
    mse = np.mean((predictions - y_test) ** 2)
    mae = np.mean(np.abs(predictions - y_test))
    
    return {
        "test_mse": float(mse),
        "test_mae": float(mae),
        "test_size": test_size,
        "parameter_norm": float(np.linalg.norm(parameters))
    }


def main():
    """Main function to demonstrate distributed training."""
    # Initialize Ray
    ray.init()
    print("Ray initialized successfully!")
    
    print("=== Distributed Training Example ===")
    
    # Configuration
    model_size = 20
    num_workers = 3
    num_iterations = 10
    learning_rate = 0.01
    
    print(f"\nConfiguration:")
    print(f"  Model size: {model_size}")
    print(f"  Number of workers: {num_workers}")
    print(f"  Training iterations: {num_iterations}")
    print(f"  Learning rate: {learning_rate}")
    
    # Create parameter server
    print(f"\n--- Creating Parameter Server ---")
    param_server = ParameterServer.remote(model_size)
    
    # Create workers
    print(f"\n--- Creating Workers ---")
    workers = [Worker.remote(f"worker_{i}") for i in range(num_workers)]
    
    # Training loop
    print(f"\n--- Starting Distributed Training ---")
    
    all_worker_metrics = []
    
    for iteration in range(num_iterations):
        print(f"\nIteration {iteration + 1}/{num_iterations}")
        
        # Get current parameters
        current_params = ray.get(param_server.get_parameters.remote())  # type: ignore
        
        # Compute gradients on all workers
        gradient_futures = []
        for worker in workers:
            future = worker.compute_gradients.remote(current_params, batch_size=50)  # type: ignore
            gradient_futures.append(future)
        
        # Collect gradients and metrics
        gradient_results = ray.get(gradient_futures)
        gradients = [result[0] for result in gradient_results]
        worker_metrics = [result[1] for result in gradient_results]
        all_worker_metrics.extend(worker_metrics)
        
        # Average gradients
        avg_gradients = np.mean(np.array(gradients), axis=0)
        
        # Update parameters
        update_metrics = ray.get(param_server.update_parameters.remote(avg_gradients, learning_rate))  # type: ignore
        
        # Print iteration summary
        avg_loss = np.mean([m["loss"] for m in worker_metrics])
        print(f"  Average worker loss: {avg_loss:.4f}")
        print(f"  Parameter norm: {update_metrics['parameter_norm']:.4f}")  # type: ignore
        print(f"  Gradient norm: {update_metrics['gradient_norm']:.4f}")  # type: ignore
    
    # Final evaluation
    print(f"\n--- Final Model Evaluation ---")
    final_params = ray.get(param_server.get_parameters.remote())  # type: ignore
    eval_metrics = ray.get(evaluate_model.remote(final_params))  # type: ignore
    
    print(f"Final evaluation metrics:")
    print(f"  Test MSE: {eval_metrics['test_mse']:.4f}")
    print(f"  Test MAE: {eval_metrics['test_mae']:.4f}")
    print(f"  Parameter norm: {eval_metrics['parameter_norm']:.4f}")
    
    # Get training statistics
    print(f"\n--- Training Statistics ---")
    param_server_stats = ray.get(param_server.get_training_stats.remote())  # type: ignore
    worker_stats_futures = [worker.get_worker_stats.remote() for worker in workers]  # type: ignore
    worker_stats = ray.get(worker_stats_futures)
    
    print(f"Parameter server stats:")
    print(f"  Total steps: {param_server_stats['steps']}")  # type: ignore
    print(f"  Average parameter norm: {param_server_stats['avg_param_norm']:.4f}")  # type: ignore
    print(f"  Average gradient norm: {param_server_stats['avg_grad_norm']:.4f}")  # type: ignore
    
    print(f"Worker stats:")
    for stats in worker_stats:
        print(f"  {stats['worker_id']}: {stats['iterations_completed']} iterations completed")
    
    # Summary metrics for verification
    summary = {
        "training_completed": True,
        "total_iterations": num_iterations,
        "total_workers": num_workers,
        "final_test_mse": eval_metrics['test_mse'],
        "final_param_norm": eval_metrics['parameter_norm'],
        "total_gradient_updates": param_server_stats['steps'],  # type: ignore
        "worker_iterations": sum(stats['iterations_completed'] for stats in worker_stats)
    }
    
    print(f"\n--- Training Summary ---")
    print(json.dumps(summary, indent=2))
    
    print("\nDistributed training example completed!")
    
    # Shutdown Ray
    ray.shutdown()
    print("Ray shutdown complete.")
    
    return summary


if __name__ == "__main__":
    main() 