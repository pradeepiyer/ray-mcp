#!/usr/bin/env python3
"""Workflow orchestration example for testing the MCP server."""

import ray
import numpy as np
import time
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio


@ray.remote
def fetch_data_task(source_id: str, delay: float = 1.0) -> Dict[str, Any]:
    """Simulate fetching data from an external source."""
    print(f"Fetching data from source: {source_id}")
    time.sleep(delay)  # Simulate network delay
    
    # Generate synthetic data
    data = {
        "source_id": source_id,
        "records": [{"id": i, "value": np.random.uniform(0, 100)} for i in range(100)],
        "metadata": {
            "fetched_at": datetime.now().isoformat(),
            "record_count": 100,
            "status": "success"
        }
    }
    
    print(f"Data fetched from {source_id}: {len(data['records'])} records")
    return data


@ray.remote
def validate_data_task(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the fetched data."""
    source_id = data["source_id"]
    records = data["records"]
    
    print(f"Validating data from source: {source_id}")
    
    valid_records = []
    invalid_records = []
    
    for record in records:
        if 0 <= record["value"] <= 100:
            valid_records.append(record)
        else:
            invalid_records.append(record)
    
    validation_result = {
        "source_id": source_id,
        "original_count": len(records),
        "valid_count": len(valid_records),
        "invalid_count": len(invalid_records),
        "valid_records": valid_records,
        "validation_rate": len(valid_records) / len(records),
        "validated_at": datetime.now().isoformat()
    }
    
    print(f"Validation complete for {source_id}: {len(valid_records)}/{len(records)} valid records")
    return validation_result


@ray.remote
def transform_data_task(validation_result: Dict[str, Any], transform_type: str = "normalize") -> Dict[str, Any]:
    """Transform the validated data."""
    source_id = validation_result["source_id"]
    valid_records = validation_result["valid_records"]
    
    print(f"Transforming data from source: {source_id} using {transform_type}")
    
    transformed_records = []
    
    if transform_type == "normalize":
        # Normalize values to 0-1 range
        values = [record["value"] for record in valid_records]
        min_val, max_val = min(values), max(values)
        value_range = max_val - min_val if max_val != min_val else 1
        
        for record in valid_records:
            transformed_record = record.copy()
            transformed_record["normalized_value"] = (record["value"] - min_val) / value_range
            transformed_record["transform_type"] = transform_type
            transformed_records.append(transformed_record)
    
    elif transform_type == "categorize":
        # Categorize values
        for record in valid_records:
            transformed_record = record.copy()
            value = record["value"]
            if value < 33:
                category = "low"
            elif value < 67:
                category = "medium"
            else:
                category = "high"
            
            transformed_record["category"] = category
            transformed_record["transform_type"] = transform_type
            transformed_records.append(transformed_record)
    
    transform_result = {
        "source_id": source_id,
        "transform_type": transform_type,
        "input_count": len(valid_records),
        "output_count": len(transformed_records),
        "transformed_records": transformed_records,
        "transformed_at": datetime.now().isoformat()
    }
    
    print(f"Transformation complete for {source_id}: {len(transformed_records)} records transformed")
    return transform_result


@ray.remote
def merge_data_task(transform_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge transformed data from multiple sources."""
    print("Merging data from multiple sources")
    
    all_records = []
    source_stats = {}
    
    for result in transform_results:
        source_id = result["source_id"]
        records = result["transformed_records"]
        
        all_records.extend(records)
        source_stats[source_id] = {
            "record_count": len(records),
            "transform_type": result["transform_type"]
        }
    
    # Calculate merged statistics
    if all_records:
        if "normalized_value" in all_records[0]:
            normalized_values = [r["normalized_value"] for r in all_records]
            stats = {
                "mean_normalized": np.mean(normalized_values),
                "std_normalized": np.std(normalized_values)
            }
        elif "category" in all_records[0]:
            categories = [r["category"] for r in all_records]
            category_counts = {}
            for cat in categories:
                category_counts[cat] = category_counts.get(cat, 0) + 1
            stats = {"category_distribution": category_counts}
        else:
            stats = {}
    else:
        stats = {}
    
    merge_result = {
        "total_records": len(all_records),
        "source_count": len(transform_results),
        "source_stats": source_stats,
        "merged_records": all_records,
        "statistics": stats,
        "merged_at": datetime.now().isoformat()
    }
    
    print(f"Data merge complete: {len(all_records)} total records from {len(transform_results)} sources")
    return merge_result


@ray.remote
def save_results_task(merge_result: Dict[str, Any], output_format: str = "summary") -> Dict[str, Any]:
    """Save the final results."""
    print(f"Saving results in {output_format} format")
    
    if output_format == "summary":
        # Save summary statistics only
        saved_data = {
            "total_records": merge_result["total_records"],
            "source_count": merge_result["source_count"],
            "source_stats": merge_result["source_stats"],
            "statistics": merge_result["statistics"],
            "saved_at": datetime.now().isoformat()
        }
    else:
        # Save full data
        saved_data = merge_result.copy()
        saved_data["saved_at"] = datetime.now().isoformat()
    
    # Simulate saving to storage
    time.sleep(0.5)
    
    save_result = {
        "save_status": "success",
        "output_format": output_format,
        "records_saved": merge_result["total_records"],
        "file_size_estimate": len(str(saved_data)),
        "saved_at": datetime.now().isoformat()
    }
    
    print(f"Results saved: {merge_result['total_records']} records")
    return save_result


@ray.remote
class WorkflowOrchestrator:
    """Orchestrate complex workflows with dependencies."""
    
    def __init__(self):
        self.workflow_history: List[Dict[str, Any]] = []
        self.active_workflows: Dict[str, Dict[str, Any]] = {}
        print("WorkflowOrchestrator initialized")
    
    def execute_workflow(self, workflow_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a complete workflow."""
        print(f"Starting workflow: {workflow_id}")
        
        workflow_start = time.time()
        self.active_workflows[workflow_id] = {
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "config": config
        }
        
        try:
            # Execute workflow based on config
            result = self._execute_data_pipeline_workflow(config)
            
            execution_time = time.time() - workflow_start
            
            # Record workflow completion
            workflow_result = {
                "workflow_id": workflow_id,
                "status": "completed",
                "execution_time": execution_time,
                "result": result,
                "completed_at": datetime.now().isoformat()
            }
            
            self.workflow_history.append(workflow_result)
            self.active_workflows[workflow_id]["status"] = "completed"
            
            print(f"Workflow {workflow_id} completed in {execution_time:.2f} seconds")
            return workflow_result
            
        except Exception as e:
            # Handle workflow failure
            execution_time = time.time() - workflow_start
            
            error_result = {
                "workflow_id": workflow_id,
                "status": "failed",
                "error": str(e),
                "execution_time": execution_time,
                "failed_at": datetime.now().isoformat()
            }
            
            self.workflow_history.append(error_result)
            self.active_workflows[workflow_id]["status"] = "failed"
            
            print(f"Workflow {workflow_id} failed after {execution_time:.2f} seconds")
            return error_result
    
    def _execute_data_pipeline_workflow(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the data pipeline workflow."""
        sources = config.get("sources", ["source_1", "source_2"])
        transform_type = config.get("transform_type", "normalize")
        output_format = config.get("output_format", "summary")
        
        # Step 1: Fetch data from multiple sources
        fetch_futures = []
        for source_id in sources:
            future = fetch_data_task.remote(source_id, delay=np.random.uniform(0.5, 2.0))
            fetch_futures.append(future)
        
        fetched_data = ray.get(fetch_futures)
        
        # Step 2: Validate data
        validation_futures = []
        for data in fetched_data:
            future = validate_data_task.remote(data)
            validation_futures.append(future)
        
        validation_results = ray.get(validation_futures)
        
        # Step 3: Transform data
        transform_futures = []
        for validation_result in validation_results:
            future = transform_data_task.remote(validation_result, transform_type)
            transform_futures.append(future)
        
        transform_results = ray.get(transform_futures)
        
        # Step 4: Merge data
        merge_result = ray.get(merge_data_task.remote(transform_results))
        
        # Step 5: Save results
        save_result = ray.get(save_results_task.remote(merge_result, output_format))
        
        return {
            "pipeline_steps": {
                "fetch": {"sources": len(sources), "records_fetched": sum(len(d["records"]) for d in fetched_data)},
                "validate": {"batches": len(validation_results), "total_valid": sum(r["valid_count"] for r in validation_results)},
                "transform": {"batches": len(transform_results), "total_transformed": sum(r["output_count"] for r in transform_results)},
                "merge": {"total_records": merge_result["total_records"], "sources": merge_result["source_count"]},
                "save": {"status": save_result["save_status"], "records_saved": save_result["records_saved"]}
            },
            "final_statistics": merge_result["statistics"],
            "performance_metrics": {
                "total_records_processed": merge_result["total_records"],
                "sources_processed": len(sources),
                "transform_type": transform_type,
                "output_format": output_format
            }
        }
    
    def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get the status of a specific workflow."""
        if workflow_id in self.active_workflows:
            return self.active_workflows[workflow_id]
        else:
            return {"status": "not_found"}
    
    def get_workflow_history(self) -> List[Dict[str, Any]]:
        """Get the history of all executed workflows."""
        return self.workflow_history


def main():
    """Main function to demonstrate workflow orchestration."""
    # Initialize Ray
    ray.init()
    print("Ray initialized successfully!")
    
    print("=== Workflow Orchestration Example ===")
    
    # Create workflow orchestrator
    print("\n--- Creating Workflow Orchestrator ---")
    orchestrator = WorkflowOrchestrator.remote()
    
    # Define workflow configurations
    workflows = [
        {
            "id": "normalize_workflow",
            "config": {
                "sources": ["source_A", "source_B"],
                "transform_type": "normalize",
                "output_format": "summary"
            }
        },
        {
            "id": "categorize_workflow",
            "config": {
                "sources": ["source_C", "source_D", "source_E"],
                "transform_type": "categorize",
                "output_format": "full"
            }
        }
    ]
    
    print(f"\nExecuting {len(workflows)} workflows:")
    for workflow in workflows:
        print(f"  - {workflow['id']}: {workflow['config']}")
    
    # Execute workflows
    print("\n--- Executing Workflows ---")
    workflow_futures = []
    
    for workflow in workflows:
        future = orchestrator.execute_workflow.remote(workflow["id"], workflow["config"])
        workflow_futures.append((workflow["id"], future))
    
    # Wait for all workflows to complete
    workflow_results = []
    for workflow_id, future in workflow_futures:
        result = ray.get(future)
        workflow_results.append(result)
        print(f"Workflow {workflow_id} result: {result['status']}")
    
    # Get workflow history
    print("\n--- Workflow History ---")
    history = ray.get(orchestrator.get_workflow_history.remote())
    
    for workflow_record in history:
        print(f"Workflow: {workflow_record['workflow_id']}")
        print(f"  Status: {workflow_record['status']}")
        print(f"  Execution time: {workflow_record['execution_time']:.2f}s")
        if workflow_record["status"] == "completed":
            result = workflow_record["result"]
            print(f"  Records processed: {result['performance_metrics']['total_records_processed']}")
        print()
    
    # Summary statistics
    completed_workflows = [w for w in workflow_results if w["status"] == "completed"]
    failed_workflows = [w for w in workflow_results if w["status"] == "failed"]
    
    total_records_processed = sum(
        w["result"]["performance_metrics"]["total_records_processed"] 
        for w in completed_workflows
    )
    
    total_execution_time = sum(w["execution_time"] for w in workflow_results)
    
    orchestration_summary = {
        "orchestration_completed": True,
        "total_workflows": len(workflows),
        "completed_workflows": len(completed_workflows),
        "failed_workflows": len(failed_workflows),
        "total_records_processed": total_records_processed,
        "total_execution_time": total_execution_time,
        "average_execution_time": total_execution_time / len(workflow_results),
        "success_rate": len(completed_workflows) / len(workflow_results)
    }
    
    print("--- Orchestration Summary ---")
    print(json.dumps(orchestration_summary, indent=2))
    
    print("\nWorkflow orchestration example completed!")
    
    # Shutdown Ray
    ray.shutdown()
    print("Ray shutdown complete.")
    
    return orchestration_summary


if __name__ == "__main__":
    main() 