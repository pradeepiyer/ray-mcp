# Available Tools

> **🛠️ Tool Registration and Extension (2024+)**
>
> The Ray MCP Server now uses a **centralized tool registry** (`ray_mcp/tool_registry.py`) to define all tool schemas, metadata, and handlers in one place. A single dispatcher function handles all MCP tool calls and routes them to the appropriate handlers via the registry.
>
> **To add or update a tool:**
> 1. Add or update the tool entry in `ToolRegistry` (schema, description, handler).
> 2. The dispatcher function automatically handles routing - no additional MCP registration needed.
> 3. No need to update multiple places or duplicate schemas—everything is now DRY and discoverable!
>
> **Old `tools.py` and individual tool functions are deprecated and removed.**

The Ray MCP Server provides a comprehensive set of tools for Ray cluster management, covering cluster operations, job management, actor management, monitoring, and scheduling:

## Cluster Operations
- `start_ray` - Start a new Ray cluster with head node and optional worker nodes
- `connect_ray` - Connect to an existing Ray cluster
- `stop_ray` - Stop the current Ray cluster
- `cluster_info` - Get comprehensive cluster information including status, resources, nodes, and worker status

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

## Tool Parameters

### start_ray
Start a new Ray cluster with head node and worker nodes. **Defaults to multi-node cluster with 2 worker nodes.**

```json
{
  "num_cpus": 1,              // Number of CPUs for head node (default: 1)
  "num_gpus": 1,              // Number of GPUs for head node
  "object_store_memory": 1000000000,  // Object store memory in bytes for head node
  "worker_nodes": [           // Array of worker node configurations (optional)
    {
      "num_cpus": 1,          // Number of CPUs for this worker
      "num_gpus": 0,          // Number of GPUs for this worker
      "object_store_memory": 500 * 1024 * 1024,  // Object store memory for this worker
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
- Worker node 1: 1 CPU, 0 GPUs, 500MB object store memory
- Worker node 2: 1 CPU, 0 GPUs, 500MB object store memory

**Note:** Default workers are configured with 1 CPU each to ensure they can start successfully with the default head node configuration (1 CPU). This prevents resource conflicts and ensures reliable cluster startup.

**Custom Worker Configuration Example:**
```json
{
  "num_cpus": 1,
  "worker_nodes": [
    {
      "num_cpus": 1,
      "num_gpus": 0,
      "node_name": "cpu-worker"
    },
    {
      "num_cpus": 1,
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

**Note:** When an address is provided, any cluster startup parameters such as
`num_cpus`, `num_gpus`, or `object_store_memory` are ignored.

### cluster_info
```json
{
  // No parameters required
}
```

**Returns comprehensive cluster information including:**
- **cluster_overview**: Overall cluster status, address, node counts, worker counts
- **resources**: Cluster resources, available resources, and resource usage breakdown
- **nodes**: Detailed information about each node in the cluster
- **worker_nodes**: Status and details of worker nodes managed by WorkerManager

**Example response structure:**
```json
{
  "status": "success",
  "cluster_overview": {
    "status": "running",
    "address": "ray://127.0.0.1:10001",
    "total_nodes": 3,
    "alive_nodes": 3,
    "total_workers": 2,
    "running_workers": 2
  },
  "resources": {
    "cluster_resources": {"CPU": 12.0, "memory": 32000000000},
    "available_resources": {"CPU": 8.0, "memory": 20000000000},
    "resource_usage": {
      "CPU": {"total": 12.0, "available": 8.0, "used": 4.0},
      "memory": {"total": 32000000000, "available": 20000000000, "used": 12000000000}
    }
  },
  "nodes": [
    {
      "node_id": "node1",
      "alive": true,
      "node_name": "head-node",
      "resources": {"CPU": 4.0},
      "used_resources": {"CPU": 2.0}
    }
  ],
  "worker_nodes": [
    {"node_id": "worker1", "status": "running"},
    {"node_id": "worker2", "status": "running"}
  ]
}
```

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
- `cluster_info` - Shows "not_running" when Ray is not initialized

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
- Worker status reporting via the `cluster_info` tool
- Enhanced cluster status with worker node information
