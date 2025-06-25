# Ray MCP Server

A Model Context Protocol (MCP) server for managing Ray clusters, jobs, and distributed computing workflows.

## Features

- **Multi-Node Cluster Management**: Start and manage Ray clusters with head nodes and worker nodes
- **Job Management**: Submit, monitor, and manage Ray jobs
- **Actor Management**: Create and manage Ray actors
- **Real-time Monitoring**: Get cluster status, resource usage, and performance metrics
- **Logging and Debugging**: Access logs and debug job issues
- **Scheduling**: Schedule jobs with cron-like syntax
- **LLM-Enhanced Output**: Optional system prompts that generate human-readable summaries and next steps

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd ray-mcp

# Install dependencies
uv sync

# Install the package
uv pip install -e .

# activate venv
source .venv/bin/activate
```

### Starting Ray Clusters

The server supports both single-node and multi-node cluster configurations:

#### Simple Single-Node Cluster

```json
{
  "tool": "start_ray",
  "arguments": {
    "num_cpus": 4,
    "num_gpus": 1
  }
}
```

#### Multi-Node Cluster (Default)

The server now defaults to starting multi-node clusters with 2 worker nodes:

```json
{
  "tool": "start_ray",
  "arguments": {
    "num_cpus": 1
  }
}
```

This creates:
- Head node: 1 CPU, 0 GPUs, 1GB object store memory
- Worker node 1: 2 CPUs, 0 GPUs, 500MB object store memory  
- Worker node 2: 2 CPUs, 0 GPUs, 500MB object store memory

#### Custom Multi-Node Setup

For advanced configurations, you can specify custom worker nodes:

```json
{
  "tool": "start_ray",
  "arguments": {
    "num_cpus": 4,
    "num_gpus": 0,
    "object_store_memory": 1000000000,
    "worker_nodes": [
      {
        "num_cpus": 2,
        "num_gpus": 0,
        "object_store_memory": 500000000,
        "node_name": "cpu-worker-1"
      },
      {
        "num_cpus": 4,
        "num_gpus": 1,
        "object_store_memory": 1000000000,
        "node_name": "gpu-worker-1",
        "resources": {"custom_resource": 2}
      }
    ],
    "head_node_port": 10001,
    "dashboard_port": 8265,
    "head_node_host": "127.0.0.1"
  }
}
```

### Basic Usage

```python
# Check cluster status
{
  "tool": "cluster_status"
}

# Submit a job
{
  "tool": "submit_job",
  "arguments": {
    "entrypoint": "python examples/simple_job.py"
  }
}
```

## Enhanced Output Configuration

The Ray MCP Server supports LLM-enhanced tool responses that provide human-readable summaries, context, and suggested next steps. This feature is controlled by the `RAY_MCP_ENHANCED_OUTPUT` environment variable:

### Default Behavior (RAY_MCP_ENHANCED_OUTPUT=false)
Returns standard JSON responses for backward compatibility:
```json
{
  "status": "success",
  "message": "Ray cluster started successfully",
  "cluster_info": {
    "num_cpus": 4,
    "num_gpus": 1
  }
}
```

### Enhanced Output (RAY_MCP_ENHANCED_OUTPUT=true)
Wraps responses with system prompts that instruct the LLM to generate:
- **Tool Result Summary**: Brief summary of what the tool call accomplished
- **Context**: Additional context about what the result means
- **Suggested Next Steps**: Relevant next actions with specific tool names
- **Available Commands**: Quick reference of commonly used tools

**Configuration Example:**
```json
{
  "mcpServers": {
    "ray-mcp": {
      "command": "/path/to/your/venv/bin/ray-mcp",
      "env": {
        "RAY_ADDRESS": "",
        "RAY_DASHBOARD_HOST": "0.0.0.0",
        "RAY_MCP_ENHANCED_OUTPUT": "true"
      }
    }
  }
}
```

This approach leverages the LLM's capabilities to provide actionable insights without requiring external API calls or tool-specific code.

## Available Tools

The server provides a comprehensive set of tools for Ray management, covering cluster operations, job management, actor management, monitoring, and scheduling:

### Cluster Operations
- `start_ray` - Start a new Ray cluster with head node and optional worker nodes
- `connect_ray` - Connect to an existing Ray cluster
- `stop_ray` - Stop the current Ray cluster
- `cluster_status` - Get comprehensive cluster status
- `cluster_resources` - Get resource usage information
- `cluster_nodes` - List all cluster nodes
- `worker_status` - Get detailed status of worker nodes

### Job Operations
- `submit_job` - Submit a new job to the cluster
- `list_jobs` - List all jobs (running, completed, failed)
- `job_status` - Get detailed status of a specific job
- `cancel_job` - Cancel a running or queued job
- `monitor_job` - Monitor job progress
- `debug_job` - Debug a job with detailed information
- `get_logs` - Retrieve job logs and outputs

### Actor Operations
- `list_actors` - List all actors in the cluster
- `kill_actor` - Terminate a specific actor

### Enhanced Monitoring
- `performance_metrics` - Get detailed cluster performance metrics
- `health_check` - Perform comprehensive cluster health check
- `optimize_config` - Get cluster optimization recommendations

### Job Scheduling
- `schedule_job` - Configure job scheduling parameters

## Examples

See the `examples/` directory for working examples:

- `simple_job.py` - Basic Ray job example
- `multi_node_cluster.py` - Multi-node cluster demonstration with worker node management
- `actor_example.py` - Actor-based computation
- `data_pipeline.py` - Data processing pipeline
- `distributed_training.py` - Distributed machine learning
- `workflow_orchestration.py` - Complex workflow orchestration

## Configuration

See `docs/config/` for configuration examples and setup instructions.

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test categories
uv run pytest tests/test_mcp_tools.py
uv run pytest tests/test_multi_node_cluster.py
uv run pytest tests/test_e2e_integration.py
```

### Code Quality

```bash
# Run linting and formatting checks
make lint

# Format code automatically
make format

# Run type checking
uv run pyright ray_mcp/

# Run code formatting
uv run black ray_mcp/
uv run isort ray_mcp/
```

## License

This project is licensed under the Apache License, Version 2.0 - see the LICENSE file for details. 