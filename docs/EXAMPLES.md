# Usage Examples

Common patterns and workflows for Ray MCP server.

## Basic Cluster Operations

### Start a Default Cluster

```python
# Initialize cluster with default configuration (head + 2 workers)
init_ray()

# Check cluster status
inspect_ray()
```

### Head-Node Only Cluster

```python
# Start cluster without worker nodes
init_ray(worker_nodes=[])

# Verify single-node setup
inspect_ray()
```

### Connect to Existing Cluster

```python
# Connect to running Ray cluster
init_ray(address="127.0.0.1:10001")

# Inspect connected cluster
inspect_ray()
```

## Job Workflows

### Simple Job Submission

```python
# Submit a basic Python job
submit_job(entrypoint="python examples/simple_job.py")

# List all jobs to get job ID
list_jobs()

# Monitor job progress
inspect_job(job_id="job_12345", mode="status")
```

### Job with Runtime Environment

```python
# Submit job with dependencies
submit_job(
    entrypoint="python ml_training.py",
    runtime_env={
        "pip": ["scikit-learn==1.3.0", "pandas"],
        "env_vars": {"CUDA_VISIBLE_DEVICES": "0"}
    }
)
```

### Job Monitoring and Debugging

```python
# Submit job and get job ID
result = submit_job(entrypoint="python failing_job.py")
job_id = result["data"]["job_id"]

# Monitor with logs
inspect_job(job_id=job_id, mode="logs")

# Full debugging info if job fails
inspect_job(job_id=job_id, mode="debug")

# Retrieve detailed logs with error analysis
retrieve_logs(
    identifier=job_id,
    include_errors=true,
    num_lines=1000
)
```

## Advanced Configurations

### Custom Worker Setup

```python
# Mixed worker configuration
init_ray(worker_nodes=[
    {"num_cpus": 4, "num_gpus": 1, "node_name": "gpu-worker"},
    {"num_cpus": 2, "object_store_memory": 2000000000, "node_name": "cpu-worker-1"},
    {"num_cpus": 2, "node_name": "cpu-worker-2"}
])
```

### Resource-Specific Jobs

```python
# Submit job to specific resource type
submit_job(
    entrypoint="python gpu_training.py",
    runtime_env={
        "pip": ["torch", "torchvision"]
    },
    metadata={"requires_gpu": "true"}
)
```

## Log Management

### Paginated Log Retrieval

```python
# Get first page of logs
logs_page1 = retrieve_logs_paginated(
    identifier="job_12345",
    page=1,
    page_size=100
)

# Get subsequent pages if needed
logs_page2 = retrieve_logs_paginated(
    identifier="job_12345",
    page=2,
    page_size=100
)
```

### Job Log Analysis

```python
# Job logs with error analysis
retrieve_logs(
    identifier="job_12345",
    log_type="job",
    include_errors=true,
    num_lines=500
)
```

## Complete Workflow Example

```python
# 1. Initialize cluster
init_ray(worker_nodes=[
    {"num_cpus": 2},
    {"num_cpus": 2}
])

# 2. Submit multiple jobs
job1 = submit_job(entrypoint="python job1.py")
job2 = submit_job(entrypoint="python job2.py")

# 3. Monitor all jobs
list_jobs()

# 4. Debug failed jobs
inspect_job(job_id="job_12345", mode="debug")

# 5. Clean up
stop_ray()
```

## Error Handling Patterns

```python
# Check cluster status before operations
cluster_info = inspect_ray()
if cluster_info["status"] == "error":
    # Handle cluster issues
    init_ray()

# Verify job submission
result = submit_job(entrypoint="python script.py")
if result["status"] == "success":
    job_id = result["data"]["job_id"]
    # Monitor job progress
    inspect_job(job_id=job_id, mode="status")
``` 