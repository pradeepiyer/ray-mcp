# Configuration Guide

## MCP Client Configuration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ray-mcp": {
      "command": "uv",
      "args": ["run", "ray-mcp"],
      "cwd": "/path/to/ray-mcp"
    }
  }
}
```

### Alternative Command Options

```json
{
  "mcpServers": {
    "ray-mcp": {
      "command": "python",
      "args": ["-m", "ray_mcp.main"],
      "cwd": "/path/to/ray-mcp"
    }
  }
}
```

Or with direct script execution:

```json
{
  "mcpServers": {
    "ray-mcp": {
      "command": "ray-mcp",
      "args": []
    }
  }
}
```

## Environment Variables

### Ray Configuration

- `RAY_DISABLE_USAGE_STATS=1` - Disable Ray usage statistics
- `RAY_ENABLE_WINDOWS_OR_OSX_CLUSTER=1` - Enable multi-node on Windows/macOS

### MCP Server Options

- `RAY_MCP_ENHANCED_OUTPUT=true` - Enable enhanced LLM-friendly output formatting
- `RAY_MCP_LOG_LEVEL=INFO` - Set logging level (DEBUG, INFO, WARNING, ERROR)

### Example Environment Setup

```bash
export RAY_DISABLE_USAGE_STATS=1
export RAY_ENABLE_WINDOWS_OR_OSX_CLUSTER=1
export RAY_MCP_ENHANCED_OUTPUT=true
ray-mcp
```

## Resource Configuration

### Default Cluster Settings

- Head node: 1 CPU, 0 GPUs
- Worker nodes: 2 workers with 1 CPU each (when not specified)
- Object store memory: Ray defaults (minimum 75MB per node)

### Custom Worker Configuration

```python
# Head-node only cluster
init_ray(worker_nodes=[])

# Custom worker setup
init_ray(worker_nodes=[
    {"num_cpus": 2, "num_gpus": 1},
    {"num_cpus": 1, "object_store_memory": 1000000000}
])
```

## Logging Configuration

Ray MCP uses Python's logging module. Configure via environment or code:

```python
import logging
logging.getLogger('ray_mcp').setLevel(logging.DEBUG)
```

## Troubleshooting Configuration

### Port Conflicts

Ray MCP automatically finds free ports for:
- Ray head node (starts at 10001)
- Ray dashboard (starts at 8265)

### File Permissions

Ensure the MCP client can execute the ray-mcp command and access the working directory.

### Ray Installation

Verify Ray is properly installed:

```bash
python -c "import ray; print(ray.__version__)"
``` 