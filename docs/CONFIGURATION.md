# Configuration

## Environment Variables
- `RAY_ADDRESS` - Ray cluster address (used by tools when provided, but doesn't auto-initialize Ray)
- `RAY_DASHBOARD_HOST` - Dashboard host (default: 0.0.0.0)
- `RAY_DASHBOARD_PORT` - Dashboard port (default: 8265)

## MCP Client Configuration

### Claude Desktop
Add to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "ray-mcp": {
      "command": "/path/to/your/venv/bin/ray-mcp",
      "env": {
        "RAY_ADDRESS": "",
        "RAY_DASHBOARD_HOST": "0.0.0.0"
      }
    }
  }
}
```

### Other MCP Clients
The server can be configured with any MCP-compatible client by pointing to the `ray-mcp` command.

## Runtime Environment Support
The server supports Ray's runtime environment features:
- Python dependencies (`pip`, `conda`, `uv`)
- Environment variables
- Working directory specification
- Container images

### Example Runtime Environment
```json
{
  "runtime_env": {
    "pip": ["requests", "click", "rich"],
    "env_vars": {
      "PYTHONPATH": "/custom/path",
      "MY_CONFIG": "production"
    },
    "working_dir": "./my_project"
  }
}
```

**Note**: While Ray's runtime environment still uses `pip` for dependency specification, the Ray MCP server itself is managed with `uv` for better dependency resolution and faster installation.

## Ray Cluster Configuration

### Local Development
```bash
# Start simple local cluster
ray start --head

# Start with specific resources
ray start --head --num-cpus=8 --num-gpus=2

# Start with dashboard on specific port
ray start --head --dashboard-host=0.0.0.0 --dashboard-port=8265
```

### Remote Cluster Connection
```bash
# Connect to remote cluster
export RAY_ADDRESS="ray://remote-head:10001"
```

## Debug Configuration

Enable debug logging:
```bash
export RAY_LOG_LEVEL=DEBUG
ray-mcp
```

Access Ray dashboard:
```
http://localhost:8265
``` 