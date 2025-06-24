#!/usr/bin/env python3
"""Ray actor example for testing the MCP server."""

import time
from typing import List

import ray


@ray.remote
class Counter:
    """A simple counter actor."""

    def __init__(self, initial_value: int = 0):
        self.value = initial_value
        print(f"Counter initialized with value: {initial_value}")

    def increment(self, amount: int = 1) -> int:
        """Increment the counter."""
        self.value += amount
        print(f"Counter incremented by {amount}, new value: {self.value}")
        return self.value

    def decrement(self, amount: int = 1) -> int:
        """Decrement the counter."""
        self.value -= amount
        print(f"Counter decremented by {amount}, new value: {self.value}")
        return self.value

    def get_value(self) -> int:
        """Get the current value."""
        return self.value

    def reset(self) -> int:
        """Reset the counter to zero."""
        self.value = 0
        print("Counter reset to 0")
        return self.value


@ray.remote
class DataProcessor:
    """A data processing actor."""

    def __init__(self, processor_id: str):
        self.processor_id = processor_id
        self.processed_items: List[int] = []
        print(f"DataProcessor {processor_id} initialized")

    def process_data(self, data: List[int]) -> List[int]:
        """Process a list of data."""
        processed = [x * 2 for x in data]  # Simple processing: multiply by 2
        self.processed_items.extend(processed)
        print(f"Processor {self.processor_id} processed {len(data)} items")
        return processed

    def get_stats(self) -> dict:
        """Get processing statistics."""
        return {
            "processor_id": self.processor_id,
            "total_processed": len(self.processed_items),
            "last_processed": (
                self.processed_items[-10:] if self.processed_items else []
            ),
        }

    def clear_history(self) -> None:
        """Clear processing history."""
        self.processed_items.clear()
        print(f"Processor {self.processor_id} history cleared")


def main():
    """Main function to demonstrate actors."""
    ray_initialized_by_script = False

    try:
        # Check if Ray is already initialized (it should be in job context)
        if not ray.is_initialized():
            print("Ray is not initialized, initializing now...")
            ray.init()
            ray_initialized_by_script = True
        else:
            print("Ray is already initialized (job context)")

        print("=== Ray Actor Example ===")

        # Create counter actors
        print("\n--- Creating Counter Actors ---")
        counter1 = Counter.remote()  # type: ignore
        counter2 = Counter.remote(100)  # type: ignore

        # Use counters
        print("\n--- Using Counters ---")
        result1 = ray.get(counter1.increment.remote(5))  # type: ignore
        result2 = ray.get(counter2.decrement.remote(10))  # type: ignore

        print(f"Counter 1 value: {result1}")
        print(f"Counter 2 value: {result2}")

        # Create data processors
        print("\n--- Creating Data Processors ---")
        processors = [DataProcessor.remote(f"processor_{i}") for i in range(3)]  # type: ignore

        # Process data
        print("\n--- Processing Data ---")
        test_data = [list(range(i * 10, (i + 1) * 10)) for i in range(3)]

        futures = []
        for i, processor in enumerate(processors):
            future = processor.process_data.remote(test_data[i])  # type: ignore
            futures.append(future)

        results = ray.get(futures)
        print("Processing results:")
        for i, result in enumerate(results):
            print(f"  Processor {i}: {result[:5]}...")  # Show first 5 items

        # Get stats from processors
        print("\n--- Processor Statistics ---")
        stats_futures = [processor.get_stats.remote() for processor in processors]  # type: ignore
        stats = ray.get(stats_futures)

        for stat in stats:
            print(
                f"  {stat['processor_id']}: processed {stat['total_processed']} items"
            )

        print("\nActor example completed!")

        # Only shutdown Ray if we initialized it
        if ray_initialized_by_script:
            ray.shutdown()
            print("Ray shutdown complete (initialized by script).")
        else:
            print("Job execution complete (Ray managed externally).")

    except Exception as e:
        print(f"ERROR: Actor example failed with exception: {e}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")

        # Cleanup: shutdown Ray if we initialized it
        if ray_initialized_by_script and ray.is_initialized():
            ray.shutdown()
            print("Ray shutdown during error cleanup.")

        raise


if __name__ == "__main__":
    main()
