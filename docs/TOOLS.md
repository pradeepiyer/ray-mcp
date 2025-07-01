# Tools Reference

Complete reference for all Ray MCP tools available to LLM agents.

## Cluster Management

### `init_ray`

Initialize or connect to a Ray cluster.

**Parameters:**
- `address` (string, optional) - Ray cluster address to connect to. If omitted, starts new cluster
- `num_cpus` (integer, optional) - CPUs for head node (new clusters only)
- `num_gpus` (integer, optional) - GPUs for head node (new clusters only)
- `worker_nodes` (array, optional) - Worker configurations. Empty array `[]` for head-only cluster
- `head_node_port` (integer, optional) - Head node port (auto-selected if not specified)
- `dashboard_port` (integer, optional) - Dashboard port (auto-selected if not specified)

**Examples:**
```python
# Start new cluster with default workers
init_ray()

# Head-node only cluster
init_ray(worker_nodes=[])

# Connect to existing cluster
init_ray(address="127.0.0.1:10001")

# Custom cluster configuration
init_ray(
    num_cpus=4,
    worker_nodes=[
        {"num_cpus": 2, "num_gpus": 1},
        {"num_cpus": 1}
    ]
)
```

### `stop_ray`

Stop the Ray cluster and clean up resources.

**Parameters:** None

### `inspect_ray`

Get comprehensive cluster information including status, resources, and nodes.

**Parameters:** None

**Returns:** Cluster status, node information, and resource utilization.

## Job Management

### `submit_job`

Submit a job to the Ray cluster.

**Parameters:**
- `entrypoint` (string, required) - Command to execute (e.g., "python script.py")
- `runtime_env` (object, optional) - Runtime environment specification
- `job_id` (string, optional) - Custom job ID
- `metadata` (object, optional) - Job metadata

**Example:**
```python
submit_job(
    entrypoint="python examples/simple_job.py",
    runtime_env={"pip": ["numpy", "pandas"]},
    metadata={"user": "alice", "project": "ml-training"}
)
```

### `list_jobs`

List all jobs in the cluster with status and metadata.

**Parameters:** None

### `inspect_job`

Inspect a specific job with detailed information.

**Parameters:**
- `job_id` (string, required) - Job ID to inspect
- `mode` (string, optional) - Inspection mode:
  - `"status"` - Basic job information (default)
  - `"logs"` - Include job logs
  - `"debug"` - Comprehensive debugging information

**Example:**
```python
inspect_job(job_id="job_12345", mode="debug")
```

### `cancel_job`

Cancel a running job.

**Parameters:**
- `job_id` (string, required) - Job ID to cancel

## Log Management

### `retrieve_logs`

Retrieve job logs with error analysis and memory protection.

**Parameters:**
- `identifier` (string, required) - Job ID 
- `log_type` (string, optional) - Type: only "job" is supported (default: "job")
- `num_lines` (integer, optional) - Number of lines to retrieve (default: 100, max: 10000)
- `include_errors` (boolean, optional) - Include error analysis (default: false)
- `max_size_mb` (integer, optional) - Maximum log size in MB (default: 10, max: 100)

**Example:**
```python
retrieve_logs(
    identifier="job_12345",
    num_lines=500,
    include_errors=true
)
```

### `retrieve_logs_paginated`

Retrieve job logs with pagination support for large log files.

**Parameters:**
- `identifier` (string, required) - Job ID
- `log_type` (string, optional) - Type: only "job" is supported (default: "job")
- `page` (integer, optional) - Page number (1-based, default: 1)
- `page_size` (integer, optional) - Lines per page (default: 100, max: 1000)
- `max_size_mb` (integer, optional) - Maximum log size in MB (default: 10, max: 100)
- `include_errors` (boolean, optional) - Include error analysis (default: false)

**Example:**
```python
retrieve_logs_paginated(
    identifier="job_12345",
    page=2,
    page_size=200,
    include_errors=true
)
```

## Tool Response Format

All tools return structured responses with:
- `status` - Success/failure indicator
- `message` - Human-readable description
- `data` - Tool-specific response data
- `timestamp` - Operation timestamp

## Enhanced Output Mode

Set `RAY_MCP_ENHANCED_OUTPUT=true` to enable LLM-optimized response formatting with:
- Contextual summaries
- Suggested next steps
- Quick reference information 