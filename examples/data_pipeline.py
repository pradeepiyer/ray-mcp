#!/usr/bin/env python3
"""Data processing pipeline example for testing the MCP server."""

import json
import random
import statistics
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import ray


@ray.remote
class DataGenerator:
    """Generate synthetic data for the pipeline."""

    def __init__(self, generator_id: str):
        self.generator_id = generator_id
        self.records_generated = 0
        # Seed random generator for reproducible results per generator
        random.seed(hash(generator_id) % 2**32)
        print(f"DataGenerator {generator_id} initialized")

    def generate_batch(self, batch_size: int = 1000) -> Dict[str, Any]:
        """Generate a batch of synthetic data."""
        records = []
        for i in range(batch_size):
            record = {
                "id": f"{self.generator_id}_{self.records_generated + i}",
                "value": random.uniform(0, 100),
                "category": f"category_{random.randint(1, 5)}",
                "timestamp": datetime.now().isoformat(),
            }
            records.append(record)

        self.records_generated += batch_size

        return {
            "generator_id": self.generator_id,
            "records": records,
            "count": batch_size,
            "total_generated": self.records_generated,
        }


@ray.remote
class DataProcessor:
    """Process and transform data."""

    def __init__(self, processor_id: str):
        self.processor_id = processor_id
        self.records_processed = 0
        print(f"DataProcessor {processor_id} initialized")

    def process_batch(self, batch: Dict[str, Any]) -> Dict[str, Any]:
        """Process a batch of records."""
        records = batch["records"]
        processed_records = []

        for record in records:
            # Transform the record
            processed_record = record.copy()
            processed_record["value_squared"] = record["value"] ** 2
            processed_record["value_category"] = (
                "high" if record["value"] > 50 else "low"
            )
            processed_record["processed_by"] = self.processor_id
            processed_record["processed_at"] = datetime.now().isoformat()

            processed_records.append(processed_record)

        self.records_processed += len(records)

        return {
            "processor_id": self.processor_id,
            "processed_records": processed_records,
            "input_count": len(records),
            "output_count": len(processed_records),
            "total_processed": self.records_processed,
        }


@ray.remote
def aggregate_data(processed_batches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate processed data from multiple batches."""
    all_records = []
    total_input = 0
    total_output = 0

    for batch in processed_batches:
        all_records.extend(batch["processed_records"])
        total_input += batch["input_count"]
        total_output += batch["output_count"]

    # Calculate statistics
    values = [record["value"] for record in all_records]
    categories = [record["category"] for record in all_records]

    category_counts = {}
    for cat in categories:
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # Calculate statistics using built-in functions
    value_mean = statistics.mean(values) if values else 0.0
    value_stdev = statistics.stdev(values) if len(values) > 1 else 0.0
    value_min = min(values) if values else 0.0
    value_max = max(values) if values else 0.0

    stats = {
        "total_records": len(all_records),
        "total_input": total_input,
        "total_output": total_output,
        "value_stats": {
            "mean": value_mean,
            "std": value_stdev,
            "min": value_min,
            "max": value_max,
        },
        "category_distribution": category_counts,
        "aggregated_at": datetime.now().isoformat(),
    }

    return stats


def main():
    """Main function to demonstrate the data processing pipeline."""
    ray_initialized_by_script = False

    try:
        # Check if Ray is already initialized (it should be in job context)
        if not ray.is_initialized():
            print("Ray is not initialized, initializing now...")
            ray.init()
            ray_initialized_by_script = True
        else:
            print("Ray is already initialized (job context)")

        print("=== Data Processing Pipeline Example ===")

        # Configuration
        num_generators = 2
        num_processors = 2
        batch_size = 500
        num_batches = 3

        print(f"\nConfiguration:")
        print(f"  Generators: {num_generators}")
        print(f"  Processors: {num_processors}")
        print(f"  Batch size: {batch_size}")
        print(f"  Number of batches: {num_batches}")

        # Create components
        print("\n--- Creating Pipeline Components ---")
        generators = [DataGenerator.remote(f"gen_{i}") for i in range(num_generators)]
        processors = [DataProcessor.remote(f"proc_{i}") for i in range(num_processors)]

        # Process data through the pipeline
        print("\n--- Processing Data Through Pipeline ---")

        all_processed_batches = []

        for batch_num in range(num_batches):
            print(f"\nBatch {batch_num + 1}/{num_batches}")

            # Generate data
            generation_futures = [gen.generate_batch.remote(batch_size) for gen in generators]  # type: ignore
            generated_batches = ray.get(generation_futures)
            print(f"  Generated {len(generated_batches)} batches")

            # Process data
            processing_futures = []
            for i, batch in enumerate(generated_batches):
                processor = processors[i % len(processors)]
                future = processor.process_batch.remote(batch)  # type: ignore
                processing_futures.append(future)

            processed_batches = ray.get(processing_futures)
            all_processed_batches.extend(processed_batches)
            print(f"  Processed {len(processed_batches)} batches")

        # Aggregate all results
        print("\n--- Aggregating Results ---")
        final_stats = ray.get(aggregate_data.remote(all_processed_batches))

        print("\n--- Pipeline Results ---")
        print(f"Total records processed: {final_stats['total_records']}")
        print(f"Value statistics: {final_stats['value_stats']}")
        print(f"Category distribution: {final_stats['category_distribution']}")

        # Pipeline summary
        pipeline_summary = {
            "pipeline_completed": True,
            "total_batches_processed": len(all_processed_batches),
            "total_records": final_stats["total_records"],
            "processing_efficiency": (
                final_stats["total_output"] / final_stats["total_input"]
                if final_stats["total_input"] > 0
                else 1.0
            ),
            "category_diversity": len(final_stats["category_distribution"]),
            "average_value": final_stats["value_stats"]["mean"],
        }

        print(f"\n--- Pipeline Summary ---")
        print(json.dumps(pipeline_summary, indent=2))

        print("\nData processing pipeline example completed!")

        # Only shutdown Ray if we initialized it
        if ray_initialized_by_script:
            ray.shutdown()
            print("Ray shutdown complete (initialized by script).")
        else:
            print("Job execution complete (Ray managed externally).")

        return pipeline_summary

    except Exception as e:
        print(f"ERROR: Data pipeline failed with exception: {e}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")

        # Cleanup: shutdown Ray if we initialized it
        if ray_initialized_by_script and ray.is_initialized():
            ray.shutdown()
            print("Ray shutdown during error cleanup.")

        raise


if __name__ == "__main__":
    main()
