# Ray MCP Server Tools

This document provides comprehensive documentation for all available tools in the Ray MCP Server.

## Tool Categories

The Ray MCP Server provides tools organized into the following categories:

1. **Cluster Operations** - Initialize, stop, and monitor Ray clusters
2. **Job Management** - Submit, monitor, and manage distributed jobs
3. **Actor Management** - List and manage Ray actors
4. **Logging & Debugging** - Retrieve logs and debug issues

## Cluster Operations

### init_ray

Initialize Ray cluster - start a new cluster or connect to existing one.

**Description**: If address is provided, connects to existing cluster; otherwise starts a new cluster with optional worker specifications.

**Parameters**:
- `address` (string, optional): Ray cluster address to connect to (e.g., 'ray://127.0.0.1:10001'). If provided, connects to existing cluster; if not provided, starts a new cluster.
- `num_cpus` (integer, optional, default: 1): Number of CPUs for head node (only used when starting new cluster)
- `num_gpus` (integer, optional, default: 0): Number of GPUs for head node (only used when starting new cluster)
- `object_store_memory` (integer, optional): Object store memory in bytes for head node (only used when starting new cluster)
- `worker_nodes` (array, optional): Configuration for worker nodes to start (only used when starting new cluster)
  - `num_cpus` (integer, required): Number of CPUs for this worker node
  - `num_gpus` (integer, optional): Number of GPUs for this worker node
  - `object_store_memory` (integer, optional): Object store memory in bytes for this worker node
  - `resources` (object, optional): Additional custom resources for this worker node
  - `node_name` (string, optional): Optional name for this worker node
- `head_node_port` (integer, optional): Port for head node (only used when starting new cluster, if None, a free port will be found)
- `dashboard_port` (integer, optional): Port for Ray dashboard (only used when starting new cluster, if None, a free port will be found)
- `head_node_host` (string, optional, default: "127.0.0.1"): Host address for head node (only used when starting new cluster)

**Example**:
```json
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4,
    "num_gpus": 1,
    "worker_nodes": [
      {
        "num_cpus": 2,
        "num_gpus": 0,
        "node_name": "cpu-worker-1"
      }
    ]
  }
}
```

### stop_ray

Stop the Ray cluster.

**Description**: Gracefully shuts down the current Ray cluster and cleans up resources.

**Parameters**: None

**Example**:
```json
{
  "tool": "stop_ray",
  "arguments": {}
}
```

### cluster_info

Get comprehensive cluster information including status, resources, nodes, worker status, performance metrics, health check, and optimization recommendations.

**Description**: Provides detailed information about the current Ray cluster state, including resource usage, node status, and health metrics.

**Parameters**: None

**Example**:
```json
{
  "tool": "cluster_info",
  "arguments": {}
}
```

## Job Management

### submit_job

Submit a job to the Ray cluster.

**Description**: Submits a new job to the Ray cluster with the specified entrypoint and optional runtime environment.

**Parameters**:
- `entrypoint` (string, required): Command to run for the job
- `runtime_env` (object, optional): Runtime environment configuration
- `job_id` (string, optional): Custom job ID
- `metadata` (object, optional): Job metadata

**Example**:
```json
{
  "tool": "submit_job",
  "arguments": {
    "entrypoint": "python examples/simple_job.py",
    "runtime_env": {
      "pip": ["numpy", "pandas"]
    }
  }
}
```

### list_jobs

List all jobs in the Ray cluster.

**Description**: Returns information about all jobs (running, completed, failed) in the cluster.

**Parameters**: None

**Example**:
```json
{
  "tool": "list_jobs",
  "arguments": {}
}
```

### inspect_job

Inspect a job with different modes: 'status' (basic info), 'logs' (with logs), or 'debug' (comprehensive debugging info).

**Description**: Provides detailed information about a specific job with optional log retrieval and debugging information.

**Parameters**:
- `job_id` (string, required): Job ID to inspect
- `mode` (string, optional, default: "status"): Inspection mode: 'status' for basic job info, 'logs' to include job logs, 'debug' for comprehensive debugging information

**Example**:
```json
{
  "tool": "inspect_job",
  "arguments": {
    "job_id": "raysubmit_1234567890",
    "mode": "debug"
  }
}
```

### cancel_job

Cancel a running job.

**Description**: Cancels a running or queued job by its ID.

**Parameters**:
- `job_id` (string, required): Job ID to cancel

**Example**:
```json
{
  "tool": "cancel_job",
  "arguments": {
    "job_id": "raysubmit_1234567890"
  }
}
```

## Actor Management

### list_actors

List all actors in the Ray cluster.

**Description**: Returns information about all actors currently running in the cluster.

**Parameters**:
- `filters` (object, optional): Optional filters to apply to actor list

**Example**:
```json
{
  "tool": "list_actors",
  "arguments": {
    "filters": {
      "state": "ALIVE"
    }
  }
}
```

### kill_actor

Kill a specific actor.

**Description**: Terminates a specific actor by its ID.

**Parameters**:
- `actor_id` (string, required): Actor ID to kill
- `no_restart` (boolean, optional, default: false): Whether to prevent actor restart

**Example**:
```json
{
  "tool": "kill_actor",
  "arguments": {
    "actor_id": "actor_1234567890",
    "no_restart": true
  }
}
```

## Logging & Debugging

### retrieve_logs

Retrieve logs from Ray cluster for jobs, actors, or nodes with comprehensive error analysis.

**Description**: Retrieves logs from various Ray components with optional error analysis and filtering.

**Parameters**:
- `identifier` (string, required): Job ID, actor ID/name, or node ID to get logs for
- `log_type` (string, optional, default: "job"): Type of logs to retrieve: 'job' for job logs, 'actor' for actor logs, 'node' for node logs
- `num_lines` (integer, optional, default: 100): Number of log lines to retrieve (0 for all lines)
- `include_errors` (boolean, optional, default: false): Whether to include error analysis for job logs

**Example**:
```json
{
  "tool": "retrieve_logs",
  "arguments": {
    "identifier": "raysubmit_1234567890",
    "log_type": "job",
    "num_lines": 200,
    "include_errors": true
  }
}
```

## Tool Response Format

All tools return responses in a consistent JSON format:

### Success Response
```json
{
  "status": "success",
  "message": "Operation completed successfully",
  "data": {
    // Tool-specific data
  }
}
```

### Error Response
```json
{
  "status": "error",
  "message": "Error description",
  "error": "Detailed error information"
}
```

## Enhanced Output Mode

When `RAY_MCP_ENHANCED_OUTPUT=true` is set, tool responses are wrapped with system prompts that provide:

- **Tool Result Summary**: Brief summary of what the tool call accomplished
- **Context**: Additional context about what the result means
- **Suggested Next Steps**: Relevant next actions with specific tool names
- **Available Commands**: Quick reference of commonly used tools

This enhanced output leverages the LLM's capabilities to provide actionable insights without requiring external API calls.

## Best Practices

1. **Always check cluster status** before submitting jobs using `cluster_info`
2. **Use appropriate log levels** when retrieving logs to avoid overwhelming output
3. **Monitor job status** regularly using `list_jobs` and `inspect_job`
4. **Clean up resources** by stopping the cluster when done using `stop_ray`
5. **Use enhanced output mode** for better LLM integration and user experience

## Error Handling

The Ray MCP Server provides comprehensive error handling:

- **Connection errors**: Automatic retry logic for cluster connections
- **Resource conflicts**: Validation of resource requirements before cluster startup
- **Job failures**: Detailed error analysis and debugging information
- **Log retrieval**: Graceful handling of missing or inaccessible logs

All errors include descriptive messages and suggestions for resolution.