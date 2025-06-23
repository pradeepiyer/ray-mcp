# Ray MCP Server Configuration

This directory contains configuration files for setting up the Ray MCP Server with different MCP clients.

## Configuration Files

### `claude_desktop_config.json`
Clean configuration file for Claude Desktop. Copy this content to your Claude Desktop configuration file:

**Location**: 
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

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

**Note**: Replace `/path/to/your/venv/bin/ray-mcp` with the actual path to your console script. You can find it with `which ray-mcp`.

### `mcp_server_config.json`
Comprehensive configuration with examples and documentation for different Ray cluster connection scenarios.

## Environment Variables

### `RAY_ADDRESS`
- **Purpose**: Default Ray cluster address
- **Default**: Empty (use tool parameters)
- **Examples**: 
  - `ray://127.0.0.1:10001`
  - `ray://production-cluster:10001`
- **Note**: Leave empty to use `start_ray` or `connect_ray` tool parameters

### `RAY_DASHBOARD_HOST`
- **Purpose**: Ray dashboard host binding
- **Default**: `0.0.0.0`
- **Production**: Consider restricting to specific IPs for security

### `RAY_DASHBOARD_PORT`
- **Purpose**: Ray dashboard port
- **Default**: `8265`
- **Note**: Only needed if you change Ray's default dashboard port

## Usage Scenarios

### Development Setup
```json
{
  "mcpServers": {
    "ray-mcp": {
      "command": "/path/to/your/venv/bin/ray-mcp",
      "env": {
        "RAY_ADDRESS": ""
      }
    }
  }
}
```
- Server starts without Ray initialization
- Use `start_ray` tool to create local clusters (default: 4 CPUs)
- Full control over cluster resources
- Clean shutdown with `stop_ray`

### Production Setup
```json
{
  "mcpServers": {
    "ray-mcp": {
      "command": "/path/to/your/venv/bin/ray-mcp",
      "env": {
        "RAY_ADDRESS": "ray://prod-cluster:10001",
        "RAY_DASHBOARD_HOST": "127.0.0.1"
      }
    }
  }
}
```
- Server starts without Ray initialization
- Use `connect_ray` tool to connect to persistent clusters
- `RAY_ADDRESS` environment variable is available for tools but doesn't auto-connect
- Restrict dashboard host for security

## Ray Initialization Behavior

**Important**: The server does NOT automatically initialize Ray on startup. This provides:

- **Flexibility**: Choose when and how to initialize Ray
- **Resource Control**: No unnecessary Ray processes
- **Explicit Control**: Clear distinction between server startup and Ray initialization
- **Error Prevention**: Avoid connection issues during server startup

**Workflow**:
1. Start MCP server (Ray not initialized)
2. Use `start_ray` or `connect_ray` to initialize Ray
3. Use other tools that require Ray
4. Optionally use `stop_ray` to shutdown Ray

## Tool Usage

### Start New Cluster
```json
{
  "tool": "start_ray",
  "arguments": {
    "num_cpus": 8,
    "num_gpus": 2,
    "object_store_memory": 2000000000
  }
}
```

**Note**: If you don't specify `num_cpus`, it defaults to 4 CPUs.

### Connect to Existing Cluster
```json
{
  "tool": "connect_ray",
  "arguments": {
    "address": "ray://cluster.example.com:10001"
  }
}
```

## Troubleshooting

### Common Issues

1. **Console script not found**
   - Ensure the package is installed: `pip install -e .`
   - Check the script path: `which ray-mcp`
   - Use full path in configuration

2. **Module not found**
   - Install the package: `pip install -e .`
   - Check virtual environment activation

3. **Ray connection issues**
   - Verify Ray cluster is running
   - Check network connectivity and firewall settings
   - Validate address format

### Debug Mode
Add debug environment variable:
```json
{
  "env": {
    "RAY_LOG_LEVEL": "DEBUG",
    "RAY_ADDRESS": ""
  }
}
```

## Security Considerations

- **Dashboard Access**: Restrict `RAY_DASHBOARD_HOST` in production
- **Network Security**: Use secure networks for cluster communication
- **Authentication**: Consider Ray's authentication features for production
- **Firewall**: Ensure appropriate ports are open (default: 10001, 8265) 