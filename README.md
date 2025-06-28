# Ray MCP Server

A Model Context Protocol (MCP) server for managing Ray clusters, jobs, and distributed computing workflows.

## Features

- **Multi-Node Cluster Management**: Start and manage Ray clusters with head nodes and worker nodes
- **Job Management**: Submit, monitor, and cancel distributed jobs
- **Actor Management**: List and manage Ray actors
- **Enhanced Logging**: Comprehensive log retrieval with error analysis
- **LLM-Enhanced Output**: Optional enhanced responses with context and suggestions

## MCP Server Architecture

The Ray MCP Server uses a **dispatcher pattern** to handle tool routing and ensure reliable MCP protocol compliance:

### Tool Registration and Routing
- **Centralized Tool Registry**: All tool schemas, metadata, and handlers are defined in `ray_mcp/tool_registry.py`
- **Single Dispatcher Function**: A single `@server.call_tool()`-decorated function (`dispatch_tool_call`) handles all tool requests
- **Tool Name Routing**: The dispatcher receives the tool name and arguments, then delegates to the appropriate handler via `tool_registry.execute_tool()`

### Architecture Benefits
- **Reliable Routing**: Eliminates MCP server routing issues where all tool calls might be directed to a single function
- **Centralized Logic**: All tool logic is centralized in the `ToolRegistry` class
- **Type Safety**: Maintains proper parameter validation and type checking
- **Extensibility**: Easy to add new tools by updating only the registry

### Key Components
```
ray_mcp/
├── main.py              # MCP server with dispatcher pattern
├── tool_registry.py     # Centralized tool registry and handlers
├── ray_manager.py       # Core Ray cluster management logic
├── worker_manager.py    # Worker node management
└── types.py             # Type definitions
```

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

# Activate virtual environment
source .venv/bin/activate
```

### Starting Ray Clusters

The server supports both single-node and multi-node cluster configurations:

#### Simple Single-Node Cluster

```json
{
  "tool": "init_ray",
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
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 1
  }
}
```

This creates:
- Head node: 1 CPU, 0 GPUs, 1GB object store memory
- Worker node 1: 1 CPU, 0 GPUs, 500MB object store memory  
- Worker node 2: 1 CPU, 0 GPUs, 500MB object store memory

**Note:** Default workers are configured with 1 CPU each to ensure they can start successfully with the default head node configuration (1 CPU). This prevents resource conflicts and ensures reliable cluster startup.

#### Custom Multi-Node Setup

For advanced configurations, you can specify custom worker nodes:

```json
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4,
    "num_gpus": 0,
    "object_store_memory": 1000000000,
    "worker_nodes": [
      {
        "num_cpus": 2,
        "num_gpus": 0,
        "object_store_memory": 500 * 1024 * 1024,
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
  "tool": "cluster_info"
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

The server provides a comprehensive set of tools for Ray management:

### Cluster Operations
- `init_ray` - Initialize Ray cluster - start a new cluster or connect to existing one
- `stop_ray` - Stop the current Ray cluster
- `cluster_info` - Get comprehensive cluster information including status, resources, nodes, and worker status

### Job Operations
- `submit_job` - Submit a new job to the cluster
- `list_jobs` - List all jobs (running, completed, failed)
- `inspect_job` - Inspect a job with different modes: 'status' (basic info), 'logs' (with logs), or 'debug' (comprehensive debugging info)
- `cancel_job` - Cancel a running or queued job
- `retrieve_logs` - Retrieve logs from jobs, actors, or nodes with comprehensive error analysis

### Actor Operations
- `list_actors` - List all actors in the cluster
- `kill_actor` - Terminate a specific actor

## Examples

See the `examples/` directory for working examples:

- `simple_job.py` - Basic Ray job example
- `multi_node_cluster.py` - Multi-node cluster demonstration with worker node management
- `actor_example.py` - Actor-based computation
- `data_pipeline.py` - Data processing pipeline
- `distributed_training.py` - Distributed machine learning
- `workflow_orchestration.py` - Complex workflow orchestration
- `connect_existing_cluster.py` - Connect to existing Ray cluster
- `log_retrieval_example.py` - Log retrieval and analysis examples

## Configuration

See `docs/config/` for configuration examples and setup instructions.

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test categories
uv run pytest tests/test_ray_manager.py
uv run pytest tests/test_multi_node_cluster.py
uv run pytest tests/test_e2e_integration.py

# Run fast tests (excludes e2e)
make test-fast

# Run e2e tests with cleanup
make test-e2e
```

### Test Categories

The test suite includes comprehensive coverage:

- **Unit Tests**: Fast, isolated tests for individual components
- **Integration Tests**: Medium-speed tests with Ray interaction
- **End-to-End Tests**: Comprehensive tests with full Ray workflows
- **Multi-Node Tests**: Tests for multi-node cluster functionality

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

# Check for locals() usage in tool functions (static analysis)
make lint-tool-functions
```

## License

This project is licensed under the Apache License, Version 2.0 - see the LICENSE file for details. 