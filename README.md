# Ray MCP Server

A Model Context Protocol (MCP) server for comprehensive Ray cluster management, job submission, and monitoring.

## Features

- **Cluster Management**: Start, stop, and monitor Ray clusters
- **Multi-Node Support**: Start clusters with head node and multiple worker nodes
- **Worker Node Management**: Comprehensive worker node lifecycle management with the new `WorkerManager` class
- **Job Operations**: Submit, monitor, and manage Ray jobs
- **Actor Management**: List and control Ray actors
- **Health Monitoring**: Comprehensive cluster health checks and performance metrics
- **Resource Management**: Monitor and optimize cluster resources

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd mcp

# Install dependencies
uv sync

# Install the package
uv pip install -e .
```

### Basic Usage

```python
# Start a simple cluster (head node only)
{
  "tool": "start_ray",
  "arguments": {
    "num_cpus": 4,
    "num_gpus": 1
  }
}

# Start a multi-node cluster
{
  "tool": "start_ray",
  "arguments": {
    "num_cpus": 4,
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
}

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

## Multi-Node Cluster Support

The enhanced `start_ray` tool now supports creating clusters with multiple worker nodes:

### Worker Node Configuration

Each worker node can be configured with:
- **num_cpus**: Number of CPUs (required)
- **num_gpus**: Number of GPUs (optional)
- **object_store_memory**: Memory allocation in bytes (optional)
- **node_name**: Custom name for the worker (optional)
- **resources**: Custom resources (optional)

### Example Multi-Node Setup

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

### Worker Node Management

- **worker_status**: Get detailed status of all worker nodes
- **cluster_status**: Enhanced to include worker node information
- **stop_ray**: Automatically stops all worker nodes when stopping the cluster

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
# Run linting
uv run ruff check .

# Run type checking
uv run mypy ray_mcp/
```

## License

This project is licensed under the MIT License - see the LICENSE file for details. 