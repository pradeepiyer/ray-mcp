# Available Tools

The Ray MCP Server provides **19 tools** for comprehensive Ray cluster management:

## Cluster Operations
- `start_ray` - Start a new Ray cluster (head node)
- `connect_ray` - Connect to an existing Ray cluster
- `stop_ray` - Stop the current Ray cluster
- `cluster_status` - Get comprehensive cluster status
- `cluster_resources` - Get resource usage information
- `cluster_nodes` - List all cluster nodes

## Job Operations
- `submit_job` - Submit a new job to the cluster
- `list_jobs` - List all jobs (running, completed, failed)
- `job_status` - Get detailed status of a specific job
- `cancel_job` - Cancel a running or queued job
- `monitor_job` - Monitor job progress
- `debug_job` - Debug a job with detailed information
- `get_logs` - Retrieve job logs and outputs

## Actor Operations
- `list_actors` - List all actors in the cluster
- `kill_actor` - Terminate a specific actor

## Enhanced Monitoring
- `performance_metrics` - Get detailed cluster performance metrics
- `health_check` - Perform comprehensive cluster health check
- `optimize_config` - Get cluster optimization recommendations

## Job Scheduling
- `schedule_job` - Configure job scheduling parameters (stores metadata only)

## Tool Parameters

### start_ray
```json
{
  "num_cpus": 4,              // Number of CPUs to allocate (default: 4)
  "num_gpus": 1,              // Number of GPUs to allocate  
  "object_store_memory": 1000000000  // Object store memory in bytes
}
```

### connect_ray
```json
{
  "address": "ray://127.0.0.1:10001"  // Required: Ray cluster address
}
```

**Supported address formats:**
- `ray://127.0.0.1:10001` (recommended)
- `127.0.0.1:10001`
- `ray://head-node-ip:10001`
- `ray://cluster.example.com:10001`

### submit_job
```json
{
  "entrypoint": "python my_script.py",  // Required: command to run
  "runtime_env": {                      // Optional: runtime environment
    "pip": ["numpy", "pandas"],
    "env_vars": {"MY_VAR": "value"}
  },
  "job_id": "my_job_123",              // Optional: custom job ID
  "metadata": {                        // Optional: job metadata
    "team": "data-science",
    "project": "experiment-1"
  }
}
```

## Tool Categories by Ray Dependency

**✅ Works without Ray initialization:**
- `cluster_status` - Shows "not_running" when Ray is not initialized

**❌ Requires Ray initialization:**
- All job management tools (`submit_job`, `list_jobs`, etc.)
- All actor management tools (`list_actors`, `kill_actor`)
- All monitoring tools (`performance_metrics`, `health_check`, etc.)

**🔧 Ray initialization tools:**
- `start_ray` - Start a new Ray cluster
- `connect_ray` - Connect to an existing Ray cluster
- `stop_ray` - Stop the current Ray cluster 