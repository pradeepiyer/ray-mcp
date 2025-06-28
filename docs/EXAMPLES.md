# Examples

This document provides comprehensive examples for using the Ray MCP Server, including basic usage, advanced configurations, and testing scenarios.

## Basic Usage Examples

### 1. Simple Cluster Initialization

Initialize a basic Ray cluster with default settings:

```json
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4
  }
}
```

**Response**:
```json
{
  "status": "started",
  "message": "Ray cluster started successfully",
  "cluster_address": "ray://127.0.0.1:30000",
  "dashboard_url": "http://127.0.0.1:8265",
  "node_id": "abc123...",
  "session_name": "session_2024_01_01_12_00_00_123456",
  "job_client_status": "ready",
  "worker_nodes": [
    {
      "status": "started",
      "node_name": "default-worker-1",
      "message": "Worker node 'default-worker-1' started successfully",
      "process_id": 12345,
      "config": {
        "num_cpus": 1,
        "num_gpus": 0,
        "object_store_memory": 524288000,
        "node_name": "default-worker-1"
      }
    },
    {
      "status": "started",
      "node_name": "default-worker-2",
      "message": "Worker node 'default-worker-2' started successfully",
      "process_id": 12346,
      "config": {
        "num_cpus": 1,
        "num_gpus": 0,
        "object_store_memory": 524288000,
        "node_name": "default-worker-2"
      }
    }
  ]
}
```

### 2. CI-Optimized Cluster (Head Node Only)

For CI environments, use head node only for minimal resource usage:

```json
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 1,
    "worker_nodes": []
  }
}
```

**Response**:
```json
{
  "status": "started",
  "message": "Ray cluster started successfully",
  "cluster_address": "ray://127.0.0.1:30000",
  "dashboard_url": "http://127.0.0.1:8265",
  "node_id": "abc123...",
  "session_name": "session_2024_01_01_12_00_00_123456",
  "job_client_status": "ready",
  "worker_nodes": null
}
```

### 3. Custom Multi-Node Cluster

Configure a cluster with specific worker nodes:

```json
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4,
    "num_gpus": 1,
    "object_store_memory": 2000000000,
    "worker_nodes": [
      {
        "num_cpus": 2,
        "num_gpus": 0,
        "object_store_memory": 1000000000,
        "node_name": "cpu-worker-1"
      },
      {
        "num_cpus": 4,
        "num_gpus": 1,
        "object_store_memory": 2000000000,
        "node_name": "gpu-worker-1",
        "resources": {
          "custom_resource": 2
        }
      }
    ]
  }
}
```

## Job Management Examples

### 1. Submit a Simple Job

Submit a basic Python script:

```json
{
  "tool": "submit_job",
  "arguments": {
    "entrypoint": "python examples/simple_job.py"
  }
}
```

**Response**:
```json
{
  "status": "submitted",
  "job_id": "raysubmit_abc123def456",
  "message": "Job submitted successfully"
}
```

### 2. Submit Job with Runtime Environment

Submit a job with specific dependencies:

```json
{
  "tool": "submit_job",
  "arguments": {
    "entrypoint": "python examples/data_pipeline.py",
    "runtime_env": {
      "pip": ["numpy", "pandas", "scikit-learn"]
    }
  }
}
```

### 3. Monitor Job Status

Check the status of a submitted job:

```json
{
  "tool": "inspect_job",
  "arguments": {
    "job_id": "raysubmit_abc123def456"
  }
}
```

**Response**:
```json
{
  "status": "success",
  "job_id": "raysubmit_abc123def456",
  "job_status": "SUCCEEDED",
  "entrypoint": "python examples/simple_job.py",
  "submission_id": "raysubmit_abc123def456",
  "start_time": "2024-01-01T12:00:00Z",
  "end_time": "2024-01-01T12:01:30Z",
  "runtime_env": {},
  "message": "Job completed successfully"
}
```

### 4. Debug Job Issues

Get detailed debugging information for a job:

```json
{
  "tool": "inspect_job",
  "arguments": {
    "job_id": "raysubmit_abc123def456",
    "mode": "debug"
  }
}
```

**Response**:
```json
{
  "status": "success",
  "job_id": "raysubmit_abc123def456",
  "job_status": "FAILED",
  "debug_info": {
    "error_message": "ModuleNotFoundError: No module named 'missing_package'",
    "stack_trace": "...",
    "runtime_env": {},
    "entrypoint": "python examples/failing_job.py",
    "submission_time": "2024-01-01T12:00:00Z",
    "start_time": "2024-01-01T12:00:05Z",
    "end_time": "2024-01-01T12:00:10Z"
  }
}
```

## Logging and Debugging Examples

### 1. Retrieve Job Logs

Get logs from a completed job:

```json
{
  "tool": "retrieve_logs",
  "arguments": {
    "identifier": "raysubmit_abc123def456",
    "log_type": "job"
  }
}
```

**Response**:
```json
{
  "status": "success",
  "log_type": "job",
  "identifier": "raysubmit_abc123def456",
  "logs": [
    "2024-01-01 12:00:05,123 INFO: Starting job execution",
    "2024-01-01 12:00:05,456 INFO: Initializing Ray tasks",
    "2024-01-01 12:00:06,789 INFO: Task completed successfully",
    "2024-01-01 12:00:07,012 INFO: Job finished"
  ],
  "error_analysis": {
    "has_errors": false,
    "error_count": 0,
    "error_lines": []
  }
}
```

### 2. Retrieve Logs with Error Analysis

Get logs with comprehensive error analysis:

```json
{
  "tool": "retrieve_logs",
  "arguments": {
    "identifier": "raysubmit_abc123def456",
    "log_type": "job",
    "num_lines": 100,
    "include_errors": true
  }
}
```

**Response** (for failed job):
```json
{
  "status": "success",
  "log_type": "job",
  "identifier": "raysubmit_abc123def456",
  "logs": [
    "2024-01-01 12:00:05,123 INFO: Starting job execution",
    "2024-01-01 12:00:05,456 ERROR: ModuleNotFoundError: No module named 'missing_package'",
    "2024-01-01 12:00:05,789 ERROR: Traceback (most recent call last):",
    "2024-01-01 12:00:05,890 ERROR:   File \"examples/failing_job.py\", line 5, in <module>",
    "2024-01-01 12:00:05,991 ERROR:     import missing_package",
    "2024-01-01 12:00:06,092 ERROR: ModuleNotFoundError: No module named 'missing_package'"
  ],
  "error_analysis": {
    "has_errors": true,
    "error_count": 1,
    "error_lines": [
      "ModuleNotFoundError: No module named 'missing_package'"
    ],
    "error_summary": "Job failed due to missing Python package 'missing_package'"
  }
}
```

## Cluster Monitoring Examples

### 1. Get Cluster Status

Check the overall status of the Ray cluster:

```json
{
  "tool": "inspect_ray",
  "arguments": {}
}
```

**Response**:
```json
{
  "status": "success",
  "timestamp": 1704110400.123,
  "cluster_overview": {
    "status": "running",
    "address": "ray://127.0.0.1:30000",
    "total_nodes": 3,
    "alive_nodes": 3,
    "total_workers": 2,
    "running_workers": 2
  },
  "resources": {
    "cluster_resources": {
      "CPU": 6.0,
      "object_store_memory": 4000000000.0,
      "memory": 16000000000.0
    },
    "available_resources": {
      "CPU": 4.0,
      "object_store_memory": 3000000000.0,
      "memory": 12000000000.0
    }
  },
  "health_check": {
    "overall_status": "excellent",
    "health_score": 95.0,
    "checks": {
      "all_nodes_alive": true,
      "has_available_cpu": true,
      "has_available_memory": true,
      "cluster_responsive": true
    },
    "recommendations": [
      "Cluster health is good. No immediate action required."
    ]
  }
}
```

### 2. List All Jobs

Get information about all jobs in the cluster:

```json
{
  "tool": "list_jobs",
  "arguments": {}
}
```

**Response**:
```json
{
  "status": "success",
  "jobs": [
    {
      "job_id": "raysubmit_abc123def456",
      "status": "SUCCEEDED",
      "entrypoint": "python examples/simple_job.py",
      "submission_id": "raysubmit_abc123def456",
      "start_time": "2024-01-01T12:00:00Z",
      "end_time": "2024-01-01T12:01:30Z"
    },
    {
      "job_id": "raysubmit_def456ghi789",
      "status": "RUNNING",
      "entrypoint": "python examples/long_running_job.py",
      "submission_id": "raysubmit_def456ghi789",
      "start_time": "2024-01-01T12:05:00Z",
      "end_time": null
    }
  ]
}
```

## Testing Examples

### 1. E2E Test Workflow

Complete end-to-end testing workflow:

```python
# Test complete Ray workflow
async def test_complete_ray_workflow():
    # 1. Start cluster
    start_result = await call_tool("init_ray", {
        "num_cpus": 1,
        "worker_nodes": []  # Head node only for CI
    })
    assert start_result["status"] == "started"
    
    # 2. Submit job
    job_result = await call_tool("submit_job", {
        "entrypoint": "python test_script.py"
    })
    assert job_result["status"] == "submitted"
    job_id = job_result["job_id"]
    
    # 3. Monitor job
    for i in range(10):  # 10 second timeout
        status_result = await call_tool("inspect_job", {
            "job_id": job_id
        })
        if status_result["job_status"] == "SUCCEEDED":
            break
        await asyncio.sleep(1)
    
    # 4. Stop cluster
    stop_result = await call_tool("stop_ray", {})
    assert stop_result["status"] == "stopped"
```

### 2. CI-Optimized Test

Test optimized for CI environments:

```python
# CI-optimized test
async def test_ci_optimized_workflow():
    # Use minimal resources for CI
    cpu_limit = 1 if os.environ.get("CI") else 2
    worker_nodes = [] if os.environ.get("CI") else None
    max_wait = 10 if os.environ.get("CI") else 30
    
    # Start cluster
    start_result = await call_tool("init_ray", {
        "num_cpus": cpu_limit,
        "worker_nodes": worker_nodes
    })
    assert start_result["status"] == "started"
    
    # Submit lightweight job
    job_result = await call_tool("submit_job", {
        "entrypoint": "python -c 'import ray; print(\"Hello Ray!\")'"
    })
    assert job_result["status"] == "submitted"
    
    # Wait with appropriate timeout
    job_id = job_result["job_id"]
    for i in range(max_wait):
        status_result = await call_tool("inspect_job", {
            "job_id": job_id
        })
        if status_result["job_status"] == "SUCCEEDED":
            break
        await asyncio.sleep(1)
    
    # Cleanup
    await call_tool("stop_ray", {})
```

## Advanced Configuration Examples

### 1. High-Performance Cluster

Configure a cluster for high-performance workloads:

```json
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 16,
    "num_gpus": 4,
    "object_store_memory": 8000000000,
    "worker_nodes": [
      {
        "num_cpus": 32,
        "num_gpus": 8,
        "object_store_memory": 16000000000,
        "resources": {
          "high_performance": 1
        },
        "node_name": "compute-node-1"
      }
    ]
  }
}
```

### 2. Memory-Optimized Cluster

Configure a cluster optimized for memory-intensive workloads:

```json
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4,
    "object_store_memory": 4000000000,
    "worker_nodes": [
      {
        "num_cpus": 8,
        "object_store_memory": 8000000000,
        "node_name": "memory-node-1"
      }
    ]
  }
}
```

### 3. Custom Resource Cluster

Configure a cluster with custom resources:

```json
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4,
    "worker_nodes": [
      {
        "num_cpus": 2,
        "resources": {
          "custom_gpu": 2,
          "high_memory": 1,
          "fast_storage": 1
        },
        "node_name": "specialized-worker"
      }
    ]
  }
}
```

## Error Handling Examples

### 1. Graceful Error Handling

Handle errors gracefully in your application:

```python
async def safe_ray_operation():
    try:
        # Initialize cluster
        result = await call_tool("init_ray", {"num_cpus": 4})
        if result["status"] != "started":
            raise Exception(f"Failed to start cluster: {result['message']}")
        
        # Submit job
        job_result = await call_tool("submit_job", {
            "entrypoint": "python my_script.py"
        })
        if job_result["status"] != "submitted":
            raise Exception(f"Failed to submit job: {job_result['message']}")
        
        return job_result["job_id"]
        
    except Exception as e:
        # Cleanup on error
        await call_tool("stop_ray", {})
        raise e
```

### 2. Job Failure Recovery

Handle job failures and recover:

```python
async def handle_job_failure(job_id):
    # Get detailed job information
    job_info = await call_tool("inspect_job", {
        "job_id": job_id,
        "mode": "debug"
    })
    
    if job_info["job_status"] == "FAILED":
        # Get logs for analysis
        logs = await call_tool("retrieve_logs", {
            "identifier": job_id,
            "log_type": "job",
            "include_errors": true
        })
        
        # Analyze error
        if logs["error_analysis"]["has_errors"]:
            error_summary = logs["error_analysis"]["error_summary"]
            print(f"Job failed: {error_summary}")
            
            # Take recovery action based on error type
            if "ModuleNotFoundError" in error_summary:
                # Resubmit with correct runtime environment
                return await resubmit_with_dependencies(job_id)
            elif "OutOfMemoryError" in error_summary:
                # Resubmit with more memory
                return await resubmit_with_more_memory(job_id)
    
    return None
```

## Performance Monitoring Examples

### 1. Resource Monitoring

Monitor cluster resource usage:

```python
async def monitor_cluster_performance():
    # Get cluster status
    status = await call_tool("inspect_ray", {})
    
    # Extract performance metrics
    resources = status["resources"]
    cluster_resources = resources["cluster_resources"]
    available_resources = resources["available_resources"]
    
    # Calculate utilization
    cpu_utilization = (
        (cluster_resources["CPU"] - available_resources["CPU"]) / 
        cluster_resources["CPU"] * 100
    )
    
    memory_utilization = (
        (cluster_resources["memory"] - available_resources["memory"]) / 
        cluster_resources["memory"] * 100
    )
    
    print(f"CPU Utilization: {cpu_utilization:.1f}%")
    print(f"Memory Utilization: {memory_utilization:.1f}%")
    
    # Check health recommendations
    health = status["health_check"]
    for recommendation in health["recommendations"]:
        print(f"Recommendation: {recommendation}")
```

### 2. Job Performance Tracking

Track job performance over time:

```python
async def track_job_performance(job_id):
    # Get job details
    job_info = await call_tool("inspect_job", {"job_id": job_id})
    
    # Calculate execution time
    start_time = datetime.fromisoformat(job_info["start_time"].replace("Z", "+00:00"))
    end_time = datetime.fromisoformat(job_info["end_time"].replace("Z", "+00:00"))
    execution_time = end_time - start_time
    
    print(f"Job {job_id} execution time: {execution_time}")
    
    # Get resource usage from logs
    logs = await call_tool("retrieve_logs", {
        "identifier": job_id,
        "log_type": "job"
    })
    
    # Analyze performance patterns
    # ... performance analysis logic ...
```

## Best Practices

### 1. Environment-Specific Configuration

Always consider the environment when configuring clusters:

```python
def get_cluster_config():
    if os.environ.get("CI"):
        # CI environment: minimal resources
        return {
            "num_cpus": 1,
            "worker_nodes": []
        }
    else:
        # Local development: full cluster
        return {
            "num_cpus": 2,
            "worker_nodes": None  # Use defaults
        }
```

### 2. Proper Cleanup

Always clean up resources after use:

```python
async def safe_cluster_usage():
    try:
        # Use cluster
        await call_tool("init_ray", {"num_cpus": 4})
        # ... perform operations ...
    finally:
        # Always cleanup
        await call_tool("stop_ray", {})
```

### 3. Error Monitoring

Monitor and log errors for debugging:

```python
async def monitored_operation():
    try:
        result = await call_tool("submit_job", {
            "entrypoint": "python my_script.py"
        })
        return result
    except Exception as e:
        # Log error with context
        logger.error(f"Job submission failed: {e}")
        
        # Get cluster status for debugging
        cluster_status = await call_tool("inspect_ray", {})
        logger.info(f"Cluster status: {cluster_status}")
        
        raise e
```

These examples demonstrate the key features and best practices for using the Ray MCP Server effectively across different environments and use cases.