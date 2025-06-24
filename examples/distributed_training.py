#!/usr/bin/env python3
"""Distributed training example for testing the MCP server."""

import json
import math
import random
import time
from typing import Any, Dict, List, Tuple

import ray


@ray.remote
class ParameterServer:
    """A parameter server that maintains model parameters."""

    def __init__(self, model_size: int):
        self.model_size = model_size
        # Initialize parameters with small random values
        self.parameters = [random.gauss(0, 0.1) for _ in range(model_size)]
        self.gradients_received = 0
        self.training_history: List[Dict[str, Any]] = []
        print(f"Parameter server initialized with model size: {model_size}")

    def get_parameters(self) -> List[float]:
        """Get current model parameters."""
        return self.parameters.copy()

    def update_parameters(
        self, gradients: List[float], learning_rate: float = 0.01
    ) -> Dict[str, Any]:
        """Update parameters with gradients."""
        # Update parameters: params = params - learning_rate * gradients
        for i in range(len(self.parameters)):
            self.parameters[i] -= learning_rate * gradients[i]

        self.gradients_received += 1

        # Track training metrics
        param_norm = math.sqrt(sum(p * p for p in self.parameters))
        grad_norm = math.sqrt(sum(g * g for g in gradients))

        metrics = {
            "step": self.gradients_received,
            "parameter_norm": param_norm,
            "gradient_norm": grad_norm,
            "learning_rate": learning_rate,
            "timestamp": time.time(),
        }

        self.training_history.append(metrics)
        print(
            f"Parameters updated - Step: {self.gradients_received}, Param norm: {param_norm:.4f}"
        )

        return metrics

    def get_training_stats(self) -> Dict[str, Any]:
        """Get training statistics."""
        if not self.training_history:
            return {"steps": 0, "avg_param_norm": 0.0, "avg_grad_norm": 0.0}

        avg_param_norm = sum(h["parameter_norm"] for h in self.training_history) / len(
            self.training_history
        )
        avg_grad_norm = sum(h["gradient_norm"] for h in self.training_history) / len(
            self.training_history
        )

        return {
            "steps": len(self.training_history),
            "avg_param_norm": avg_param_norm,
            "avg_grad_norm": avg_grad_norm,
            "final_param_norm": self.training_history[-1]["parameter_norm"],
            "history": self.training_history[-5:],  # Last 5 steps
        }


@ray.remote
class Worker:
    """A worker that computes gradients."""

    def __init__(self, worker_id: str, data_size: int = 1000):
        self.worker_id = worker_id
        self.data_size = data_size
        # Generate synthetic training data
        random.seed(hash(worker_id) % 2**32)  # Deterministic seed per worker
        self.X = [
            [random.gauss(0, 1) for _ in range(10)] for _ in range(data_size)
        ]  # Features
        self.y = [random.gauss(0, 1) for _ in range(data_size)]  # Targets
        self.iterations_completed = 0
        print(f"Worker {worker_id} initialized with {data_size} data points")

    def compute_gradients(
        self, parameters: List[float], batch_size: int = 100
    ) -> Tuple[List[float], Dict[str, Any]]:
        """Compute gradients using synthetic data."""
        # Select random batch
        batch_indices = random.sample(
            range(self.data_size), min(batch_size, self.data_size)
        )
        X_batch = [self.X[i] for i in batch_indices]
        y_batch = [self.y[i] for i in batch_indices]

        # Simple linear regression gradients (for demonstration)
        gradients = [0.0] * len(parameters)
        total_loss = 0.0

        for i in range(len(X_batch)):
            # Prediction using first 10 parameters as weights
            prediction = sum(
                X_batch[i][j] * parameters[j] for j in range(min(10, len(parameters)))
            )
            error = prediction - y_batch[i]
            total_loss += error * error

            # Compute gradients for first 10 parameters
            for j in range(min(10, len(parameters))):
                gradients[j] += X_batch[i][j] * error / batch_size

        # Add some noise to simulate realistic gradients
        for i in range(len(gradients)):
            gradients[i] += random.gauss(0, 0.001)

        self.iterations_completed += 1

        # Compute metrics
        loss = total_loss / batch_size
        grad_norm = math.sqrt(sum(g * g for g in gradients))

        metrics = {
            "worker_id": self.worker_id,
            "iteration": self.iterations_completed,
            "loss": loss,
            "gradient_norm": grad_norm,
            "batch_size": batch_size,
        }

        print(
            f"Worker {self.worker_id} - Iteration {self.iterations_completed}, Loss: {loss:.4f}"
        )

        return gradients, metrics

    def get_worker_stats(self) -> Dict[str, Any]:
        """Get worker statistics."""
        return {
            "worker_id": self.worker_id,
            "iterations_completed": self.iterations_completed,
            "data_size": self.data_size,
        }


@ray.remote
def evaluate_model(parameters: List[float], test_size: int = 500) -> Dict[str, Any]:
    """Evaluate the model on test data."""
    # Generate test data
    random.seed(42)  # Fixed seed for reproducible test data
    X_test = [[random.gauss(0, 1) for _ in range(10)] for _ in range(test_size)]
    y_test = [random.gauss(0, 1) for _ in range(test_size)]

    # Make predictions
    predictions = []
    for i in range(test_size):
        pred = sum(
            X_test[i][j] * parameters[j] for j in range(min(10, len(parameters)))
        )
        predictions.append(pred)

    # Compute metrics
    mse = sum((predictions[i] - y_test[i]) ** 2 for i in range(test_size)) / test_size
    mae = sum(abs(predictions[i] - y_test[i]) for i in range(test_size)) / test_size
    param_norm = math.sqrt(sum(p * p for p in parameters))

    return {
        "test_mse": mse,
        "test_mae": mae,
        "test_size": test_size,
        "parameter_norm": param_norm,
    }


def main():
    """Main function to demonstrate distributed training."""
    ray_initialized_by_script = False

    try:
        # Check if Ray is already initialized (it should be in job context)
        if not ray.is_initialized():
            print("Ray is not initialized, initializing now...")
            ray.init()
            ray_initialized_by_script = True
        else:
            print("Ray is already initialized (job context)")

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
            gradients_list = [result[0] for result in gradient_results]
            worker_metrics = [result[1] for result in gradient_results]
            all_worker_metrics.extend(worker_metrics)

            # Average gradients
            avg_gradients = [0.0] * len(gradients_list[0])
            for gradients in gradients_list:
                for i in range(len(gradients)):
                    avg_gradients[i] += gradients[i] / len(gradients_list)

            # Update parameters
            update_metrics = ray.get(param_server.update_parameters.remote(avg_gradients, learning_rate))  # type: ignore

            # Print iteration summary
            avg_loss = sum(m["loss"] for m in worker_metrics) / len(worker_metrics)
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
            print(
                f"  {stats['worker_id']}: {stats['iterations_completed']} iterations completed"
            )

        # Summary metrics for verification
        summary = {
            "training_completed": True,
            "total_iterations": num_iterations,
            "total_workers": num_workers,
            "final_test_mse": eval_metrics["test_mse"],
            "final_param_norm": eval_metrics["parameter_norm"],
            "total_gradient_updates": param_server_stats["steps"],  # type: ignore
            "worker_iterations": sum(
                stats["iterations_completed"] for stats in worker_stats
            ),
        }

        print(f"\n--- Training Summary ---")
        print(json.dumps(summary, indent=2))

        print("\nDistributed training example completed!")

        # Only shutdown Ray if we initialized it
        if ray_initialized_by_script:
            ray.shutdown()
            print("Ray shutdown complete (initialized by script).")
        else:
            print("Job execution complete (Ray managed externally).")

        return summary

    except Exception as e:
        print(f"ERROR: Distributed training failed with exception: {e}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")

        # Cleanup: shutdown Ray if we initialized it
        if ray_initialized_by_script and ray.is_initialized():
            ray.shutdown()
            print("Ray shutdown during error cleanup.")

        raise


if __name__ == "__main__":
    main()
