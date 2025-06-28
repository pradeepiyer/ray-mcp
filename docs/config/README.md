# Ray MCP Server Configuration Examples

This directory contains configuration examples for different MCP clients and deployment scenarios.

## Configuration Files

### claude_desktop_config.json

Configuration for Claude Desktop with enhanced output enabled.

**Features**:
- Enhanced output mode for better LLM integration
- Local development setup
- Comprehensive environment variables

**Usage**:
1. Copy the configuration to your Claude Desktop config
2. Update the command path to match your installation
3. Restart Claude Desktop

### mcp_server_config.json

Comprehensive configuration examples for various MCP clients.

**Includes**:
- Basic configuration
- Enhanced output configuration
- Multi-node cluster setup
- Runtime environment examples
- Network configuration

## Quick Setup

### 1. Install Ray MCP Server

```bash
# Clone and install
git clone <repository-url>
cd ray-mcp
uv sync
uv pip install -e .
```

### 2. Configure MCP Client

Choose the appropriate configuration file and update the command path:

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

### 3. Test Configuration

Start your MCP client and test the connection:

```json
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4
  }
}
```

## Configuration Options

### Environment Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `RAY_ADDRESS` | Ray cluster address | `""` | `"ray://127.0.0.1:10001"` |
| `RAY_DASHBOARD_HOST` | Dashboard host | `"0.0.0.0"` | `"127.0.0.1"` |
| `RAY_MCP_ENHANCED_OUTPUT` | Enable enhanced output | `"false"` | `"true"` |

### Enhanced Output Mode

Enable enhanced output for better LLM integration:

```json
{
  "env": {
    "RAY_MCP_ENHANCED_OUTPUT": "true"
  }
}
```

This provides:
- Human-readable summaries
- Context about results
- Suggested next steps
- Available commands reference

### Network Configuration

For local development:
```json
{
  "env": {
    "RAY_DASHBOARD_HOST": "127.0.0.1"
  }
}
```

For network access:
```json
{
  "env": {
    "RAY_DASHBOARD_HOST": "0.0.0.0"
  }
}
```

## Deployment Scenarios

### Local Development

```json
{
  "mcpServers": {
    "ray-mcp": {
      "command": "/path/to/venv/bin/ray-mcp",
      "env": {
        "RAY_ADDRESS": "",
        "RAY_DASHBOARD_HOST": "127.0.0.1",
        "RAY_MCP_ENHANCED_OUTPUT": "true"
      }
    }
  }
}
```

### Production Deployment

```json
{
  "mcpServers": {
    "ray-mcp": {
      "command": "/usr/local/bin/ray-mcp",
      "env": {
        "RAY_ADDRESS": "",
        "RAY_DASHBOARD_HOST": "0.0.0.0",
        "RAY_MCP_ENHANCED_OUTPUT": "false"
      }
    }
  }
}
```

### Multi-Node Cluster

```json
{
  "mcpServers": {
    "ray-mcp": {
      "command": "/path/to/venv/bin/ray-mcp",
      "env": {
        "RAY_ADDRESS": "",
        "RAY_DASHBOARD_HOST": "0.0.0.0",
        "RAY_MCP_ENHANCED_OUTPUT": "true"
      }
    }
  }
}
```

## Troubleshooting

### Common Issues

1. **Command not found**: Update the command path in configuration
2. **Permission denied**: Ensure the script is executable
3. **Connection refused**: Check if Ray MCP server is running
4. **Enhanced output not working**: Verify environment variable is set to "true"

### Debug Configuration

Enable debug logging:

```json
{
  "env": {
    "RAY_LOG_LEVEL": "DEBUG",
    "RAY_MCP_DEBUG": "true"
  }
}
```

### Verification Commands

Test the configuration:

```bash
# Check if ray-mcp is available
which ray-mcp

# Test server startup
ray-mcp --help

# Check environment variables
env | grep RAY
```

## Best Practices

1. **Use Virtual Environments**: Install in isolated environments
2. **Test Configurations**: Validate before production use
3. **Monitor Resources**: Use appropriate cluster configurations
4. **Enable Enhanced Output**: For better debugging and user experience
5. **Secure Network Access**: Use appropriate host bindings
6. **Document Changes**: Keep configuration documentation updated

## Advanced Configuration

### Custom Ray Configuration

```json
{
  "env": {
    "RAY_HEAD_NODE_PORT": "10001",
    "RAY_DASHBOARD_PORT": "8265",
    "RAY_HEAD_NODE_HOST": "127.0.0.1"
  }
}
```

### Runtime Environment

```json
{
  "env": {
    "PYTHONPATH": "/path/to/custom/modules",
    "RAY_OBJECT_STORE_ALLOW_SLOW_STORAGE": "1"
  }
}
```

### Security Configuration

```json
{
  "env": {
    "RAY_DASHBOARD_HOST": "127.0.0.1",
    "RAY_HEAD_NODE_HOST": "127.0.0.1"
  }
}
```

## Integration Examples

### Claude Desktop Integration

1. Copy `claude_desktop_config.json` to your Claude Desktop config
2. Update the command path
3. Restart Claude Desktop
4. Test with basic Ray commands

### Other MCP Clients

1. Use `mcp_server_config.json` as a reference
2. Adapt the configuration to your client's format
3. Update paths and environment variables
4. Test the connection

### CI/CD Integration

```yaml
# Example GitHub Actions configuration
- name: Install Ray MCP Server
  run: |
    uv sync
    uv pip install -e .

- name: Test Configuration
  run: |
    ray-mcp --help
    python -c "import ray_mcp; print('Import successful')"
```

## Support

For configuration issues:

1. Check the troubleshooting guide in `docs/TROUBLESHOOTING.md`
2. Verify environment setup in `docs/DEVELOPMENT.md`
3. Review configuration options in `docs/CONFIGURATION.md`
4. Test with basic examples in `docs/EXAMPLES.md`
