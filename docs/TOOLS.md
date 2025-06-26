# Available Tools

The Ray MCP Server provides a comprehensive set of tools for Ray cluster management, covering cluster operations, job management, actor management, monitoring, and scheduling:

## Cluster Operations
- `start_ray` - Start a new Ray cluster with head node and optional worker nodes
- `connect_ray` - Connect to an existing Ray cluster
- `stop_ray` - Stop the current Ray cluster
- `cluster_status` - Get comprehensive cluster status
- `cluster_resources` - Get resource usage information
- `cluster_nodes` - List all cluster nodes
- `worker_status` - Get detailed status of worker nodes (powered by the new `WorkerManager` class)

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
Start a new Ray cluster with head node and worker nodes. **Defaults to multi-node cluster with 2 worker nodes.**
Set `head_node` to `false` to attach additional workers to an existing cluster specified via `address`.

```json
{
  "head_node": true,         // Start a head node (set false to add workers only)
  "address": "ray://127.0.0.1:10001",  // Existing cluster address when head_node is false
  "num_cpus": 1,              // Number of CPUs for head node (default: 1)
  "num_gpus": 1,              // Number of GPUs for head node
  "object_store_memory": 1000000000,  // Object store memory in bytes for head node
  "worker_nodes": [           // Array of worker node configurations (optional)
    {
      "num_cpus": 2,          // Number of CPUs for this worker
      "num_gpus": 0,          // Number of GPUs for this worker
      "object_store_memory": 500000000,  // Object store memory for this worker
      "node_name": "worker-1", // Optional name for this worker
      "resources": {           // Optional custom resources
        "custom_resource": 2
      }
    }
  ],
  "head_node_port": 10001,    // Port for head node (default: 10001)
  "dashboard_port": 8265,     // Port for Ray dashboard (default: 8265)
  "head_node_host": "127.0.0.1"  // Host address for head node (default: 127.0.0.1)
}
```

**Default Multi-Node Configuration:**
When no `worker_nodes` parameter is specified, the cluster will start with:
- Head node: 1 CPU, 0 GPUs, 1GB object store memory
- Worker node 1: 2 CPUs, 0 GPUs, 500MB object store memory
- Worker node 2: 2 CPUs, 0 GPUs, 500MB object store memory

**Custom Worker Configuration Example:**
```json
{
  "num_cpus": 1,
  "worker_nodes": [
    {
      "num_cpus": 2,
      "num_gpus": 0,
      "node_name": "cpu-worker"
    },
    {
      "num_cpus": 2,
      "num_gpus": 1,
      "node_name": "gpu-worker"
    }
  ]
}
```

**Single-Node Cluster (if needed):**
```json
{
  "num_cpus": 8,
  "worker_nodes": []  // Empty array for single-node cluster
}
```

When `head_node` is `false`, you must provide the `address` of the running cluster to attach workers.

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

### worker_status
```json
{
  // No parameters required
}
```

**Returns detailed information about worker nodes including:**
- Status of each worker node (running/stopped)
- Process IDs
- Node names
- Configuration details

### submit_job
```json
{
  "entrypoint": "python my_script.py",  // Required: command to run
  "runtime_env": {                      // Optional: runtime environment
    "pip": ["requests", "click"],
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

## WorkerManager Class

The Ray MCP Server includes a new `WorkerManager` class (`ray_mcp/worker_manager.py`) that provides comprehensive worker node lifecycle management:

### Key Features
- **Worker Node Startup**: Start multiple worker nodes with custom configurations
- **Process Management**: Monitor and manage worker node subprocesses
- **Status Reporting**: Get detailed status of all worker nodes
- **Graceful Shutdown**: Stop worker nodes gracefully or force termination
- **Error Handling**: Robust error handling for worker node failures

### Worker Node Configuration
Each worker node can be configured with:
- **num_cpus**: Number of CPUs (required)
- **num_gpus**: Number of GPUs (optional)
- **object_store_memory**: Memory allocation in bytes (optional)
- **node_name**: Custom name for the worker (optional)
- **resources**: Custom resources (optional)

### Integration with RayManager
The `WorkerManager` is integrated into the `RayManager` class and automatically handles:
- Worker node startup when using `start_ray` with `worker_nodes` parameter
- Worker node shutdown when using `stop_ray`
- Worker status reporting via the `worker_status` tool
- Enhanced cluster status with worker node information 