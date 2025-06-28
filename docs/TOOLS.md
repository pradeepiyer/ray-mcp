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
- `init_ray` - Initialize Ray cluster - start a new cluster or connect to existing one
- `stop_ray` - Stop the current Ray cluster
- `cluster_info` - Get comprehensive cluster information including status, resources, nodes, and worker status

## Job Operations
- `submit_job` - Submit a new job to the cluster
- `list_jobs` - List all jobs (running, completed, failed)
- `job_inspect` - Inspect a job with different modes: 'status' (basic info), 'logs' (with logs), or 'debug' (comprehensive debugging info)
- `cancel_job` - Cancel a running or queued job
- `get_logs` - Retrieve job logs and outputs

## Actor Operations
- `list_actors` - List all actors in the cluster
- `kill_actor` - Terminate a specific actor

## Enhanced Monitoring
- `performance_metrics` - Get detailed cluster performance metrics
- `health_check` - Perform comprehensive cluster health check
- `optimize_config` - Get cluster optimization recommendations

## Tool Parameters

### init_ray
Initialize Ray cluster - start a new cluster or connect to existing one. If address is provided, connects to existing cluster; otherwise starts a new cluster with optional worker specifications.

**For new cluster creation:**
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

**For connecting to existing cluster:**
```json
{
  "address": "ray://127.0.0.1:10001"  // Required: Ray cluster address
}
```

**Parameter Filtering for Existing Clusters:**
When `address` is provided, cluster-starting parameters (`num_cpus`, `num_gpus`, `object_store_memory`, `head_node_port`, `dashboard_port`, `head_node_host`, `worker_nodes`) are automatically filtered out and logged. Only valid connection parameters are passed to `ray.init()`.

**Default Multi-Node Configuration:**
When no `worker_nodes` parameter is specified and no `address` is provided, the cluster will start with:
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

**Supported address formats for connecting to existing clusters:**
- `ray://127.0.0.1:10001` (recommended)
- `127.0.0.1:10001`
- `ray://head-node-ip:10001`
- `ray://cluster.example.com:10001`

**Parameter Filtering:**
When connecting to an existing cluster, the following cluster-starting parameters are automatically filtered out and logged:
- `num_cpus` - Number of CPUs (only valid for new cluster creation)
- `num_gpus` - Number of GPUs (only valid for new cluster creation)
- `object_store_memory` - Object store memory (only valid for new cluster creation)
- `head_node_port` - Head node port (only valid for new cluster creation)
- `dashboard_port` - Dashboard port (only valid for new cluster creation)
- `head_node_host` - Head node host (only valid for new cluster creation)
- `worker_nodes` - Worker node configurations (only valid for new cluster creation)

**Example with filtered parameters:**
```json
{
  "address": "ray://127.0.0.1:10001",
  "num_cpus": 8,  // This will be filtered out and logged
  "num_gpus": 2   // This will be filtered out and logged
}
```

**Result:**
```json
{
  "status": "connected",
  "message": "Successfully connected to Ray cluster at ray://127.0.0.1:10001",
  "address": "ray://127.0.0.1:10001",
  "dashboard_url": "http://127.0.0.1:8265",
  "node_id": "node_id_here",
  "session_name": "session_name_here",
  "job_client_status": "ready"
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

### job_inspect
Inspect a job with different modes to get varying levels of detail.

```json
{
  "job_id": "job_123",     // Required: Job ID to inspect
  "mode": "status"         // Optional: Inspection mode - "status", "logs", or "debug" (default: "status")
}
```

**Available modes:**
- **`status`** (default): Basic job information including status, entrypoint, start/end times, metadata, and runtime environment
- **`logs`**: All status information plus the complete job logs
- **`debug`**: All status and logs information plus comprehensive debugging analysis including error logs, recent logs, and debugging suggestions

**Example responses:**

**Status mode:**
```json
{
  "status": "success",
  "job_id": "job_123",
  "job_status": "RUNNING",
  "entrypoint": "python my_script.py",
  "start_time": 1234567890,
  "end_time": null,
  "metadata": {"team": "data-science"},
  "runtime_env": {"pip": ["requests"]},
  "message": "Job is running",
  "inspection_mode": "status"
}
```

**Logs mode:**
```json
{
  "status": "success",
  "job_id": "job_123",
  "job_status": "RUNNING",
  "entrypoint": "python my_script.py",
  "start_time": 1234567890,
  "end_time": null,
  "metadata": {},
  "runtime_env": {},
  "message": "",
  "inspection_mode": "logs",
  "logs": "Starting job...\nProcessing data...\nJob completed successfully!"
}
```

**Debug mode:**
```json
{
  "status": "success",
  "job_id": "job_123",
  "job_status": "FAILED",
  "entrypoint": "python my_script.py",
  "start_time": 1234567890,
  "end_time": 1234567895,
  "metadata": {},
  "runtime_env": {},
  "message": "Job failed",
  "inspection_mode": "debug",
  "logs": "Error: Import failed\nTraceback...",
  "debug_info": {
    "error_logs": ["Error: Import failed"],
    "recent_logs": ["Error: Import failed", "Traceback..."],
    "debugging_suggestions": [
      "Job failed. Check error logs for specific error messages.",
      "Import error detected. Check if all required packages are installed in the runtime environment."
    ]
  }
}
```

**Notes:**
- The `job_id` parameter is required
- The `mode` parameter defaults to "status" if not specified
- All modes return the same basic job information
- Logs and debug modes include additional information as specified
- Works with both Ray Job Submission API and Ray Client mode

### retrieve_logs
Retrieve logs from Ray cluster for jobs, actors, or nodes with comprehensive error analysis.

```json
{
  "identifier": "job_123",     // Required: Job ID, actor ID/name, or node ID
  "log_type": "job",           // Optional: Type of logs - "job", "actor", or "node" (default: "job")
  "num_lines": 100,            // Optional: Number of log lines to retrieve (default: 100, 0 for all)
  "include_errors": false      // Optional: Whether to include error analysis for job logs (default: false)
}
```

**Supported log types:**
- **`job`**: Retrieve job logs (fully supported)
- **`actor`**: Retrieve actor logs (limited - provides actor info and suggestions)
- **`node`**: Retrieve node logs (limited - provides node info and suggestions)

**Example responses:**

**Job logs (success):**
```json
{
  "status": "success",
  "log_type": "job",
  "identifier": "job_123",
  "logs": "Job started...\nProcessing data...\nJob completed successfully!"
}
```

**Job logs with error analysis:**
```json
{
  "status": "success",
  "log_type": "job",
  "identifier": "job_123",
  "logs": "Error: Import failed\nTraceback...",
  "error_analysis": {
    "error_count": 1,
    "errors": ["Error: Import failed"],
    "suggestions": [
      "Import error detected. Check if all required packages are installed in the runtime environment."
    ]
  }
}
```

**Actor logs (limited support):**
```json
{
  "status": "partial",
  "log_type": "actor",
  "identifier": "my_actor",
  "message": "Actor logs are not directly accessible through Ray Python API",
  "actor_info": {
    "actor_id": "abc123...",
    "state": "ALIVE"
  },
  "suggestions": [
    "Check Ray dashboard for actor logs",
    "Use Ray CLI: ray logs --actor-id <actor_id>",
    "Monitor actor through dashboard at http://localhost:8265"
  ]
}
```

**Node logs (limited support):**
```json
{
  "status": "partial",
  "log_type": "node",
  "identifier": "node_123",
  "message": "Node logs are not directly accessible through Ray Python API",
  "node_info": {
    "node_id": "node_123",
    "alive": true,
    "node_name": "worker-1",
    "node_manager_address": "127.0.0.1:12345"
  },
  "suggestions": [
    "Check Ray dashboard for node logs",
    "Use Ray CLI: ray logs --node-id <node_id>",
    "Check log files at /tmp/ray/session_*/logs/",
    "Monitor node through dashboard at http://localhost:8265"
  ]
}
```

**Notes:**
- The `identifier` parameter is required and should be a job ID, actor ID/name, or node ID
- Job logs are fully supported and provide comprehensive logging
- Actor and node logs have limited support due to Ray API limitations but provide helpful information and suggestions
- Error analysis is only available for job logs when `include_errors` is true
- Works with both Ray Job Submission API and Ray Client mode

### get_logs (Legacy)
```json
{
  "job_id": "job_123",     // Required: Job ID to get logs for
  "num_lines": 100         // Optional: Number of log lines to retrieve (default: 100)
}
```

**Returns job logs with the following structure:**
```json
{
  "status": "success",
  "log_type": "job",
  "job_id": "job_123",
  "logs": "Job log line 1\nJob log line 2\nJob log line 3..."
}
```

**Notes:**
- **Legacy tool** - Use `retrieve_logs` for more comprehensive logging capabilities
- Only job logs are supported (actor and node logs are not implemented)
- The `job_id` parameter is required
- Logs are returned as the last N lines where N is the `num_lines` parameter
- If no `num_lines` is specified, defaults to 100 lines
- Works with both Ray Job Submission API and Ray Client mode

## Tool Categories by Ray Dependency

**✅ Works without Ray initialization:**
- `cluster_info` - Shows "not_running" when Ray is not initialized

**❌ Requires Ray initialization:**
- All job management tools (`submit_job`, `list_jobs`, etc.)
- All actor management tools (`list_actors`, `kill_actor`)
- All monitoring tools (`performance_metrics`, `health_check`, etc.)

**🔧 Ray initialization tools:**
- `init_ray` - Start a new Ray cluster
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
- Worker node startup when using `init_ray` with `worker_nodes` parameter
- Worker node shutdown when using `stop_ray`
- Worker status reporting via the `cluster_info` tool
- Enhanced cluster status with worker node information