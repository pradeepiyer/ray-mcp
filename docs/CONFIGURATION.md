# Ray MCP Server: Configuration Guide

This guide covers the most common configuration options for the Ray MCP Server.

## Environment Variables
- `RAY_ADDRESS`: Ray cluster address (e.g. "ray://127.0.0.1:10001")
- `RAY_DASHBOARD_HOST`: Dashboard host (default: "0.0.0.0")
- `RAY_MCP_ENHANCED_OUTPUT`: Enable enhanced output ("true"/"false")

## MCP Client Example

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

## Cluster Configuration

### Basic
```json
{
  "tool": "init_ray",
  "arguments": {"num_cpus": 4}
}
```

### Multi-Node
```json
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 2,
    "worker_nodes": [
      {"num_cpus": 4, "node_name": "worker-1"}
    ]
  }
}
```

## Job Runtime Environment

```json
{
  "tool": "submit_job",
  "arguments": {
    "entrypoint": "python examples/simple_job.py",
    "runtime_env": {"pip": ["numpy", "pandas"]}
  }
}
```

## Network & Resource Options
- `head_node_host`: Host for head node (default: 127.0.0.1)
- `head_node_port`: Port for head node (default: auto)
- `dashboard_port`: Port for dashboard (default: auto)
- `object_store_memory`: Memory for Ray object store (bytes)

## Best Practices
- Use minimal resources in CI: `{ "num_cpus": 1, "worker_nodes": [] }`
- Use full cluster for local dev: `{ "num_cpus": 2, "worker_nodes": null }`
- Always stop clusters after use

---

For more, see [TOOLS.md](TOOLS.md) and [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
