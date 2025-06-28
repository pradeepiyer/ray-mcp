# Ray MCP Server Configuration

This document provides comprehensive configuration information for the Ray MCP Server.

## Environment Variables

The Ray MCP Server supports several environment variables for configuration:

### Core Configuration

- `RAY_ADDRESS`: Ray cluster address to connect to (e.g., "ray://127.0.0.1:10001")
- `RAY_DASHBOARD_HOST`: Host address for Ray dashboard (default: "0.0.0.0")
- `RAY_MCP_ENHANCED_OUTPUT`: Enable enhanced output mode (default: "false")

### Ray-Specific Configuration

- `RAY_HEAD_NODE_PORT`: Default port for head node (default: auto-assigned)
- `RAY_DASHBOARD_PORT`: Default port for dashboard (default: auto-assigned)
- `RAY_HEAD_NODE_HOST`: Default host for head node (default: "127.0.0.1")

## MCP Client Configuration

### Claude Desktop Configuration

For Claude Desktop, add the following to your configuration:

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

### Generic MCP Client Configuration

For other MCP clients, use this configuration format:

```json
{
  "mcpServers": {
    "ray-mcp": {
      "command": "/path/to/your/venv/bin/ray-mcp",
      "env": {
        "RAY_ADDRESS": "",
        "RAY_DASHBOARD_HOST": "0.0.0.0",
        "RAY_MCP_ENHANCED_OUTPUT": "false"
      }
    }
  }
}
```

## Cluster Configuration Options

### Basic Cluster Configuration

```json
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4,
    "num_gpus": 1,
    "object_store_memory": 1000000000
  }
}
```

### Multi-Node Cluster Configuration

```json
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 2,
    "num_gpus": 0,
    "object_store_memory": 1000000000,
    "worker_nodes": [
      {
        "num_cpus": 4,
        "num_gpus": 1,
        "object_store_memory": 2000000000,
        "node_name": "gpu-worker-1"
      },
      {
        "num_cpus": 2,
        "num_gpus": 0,
        "object_store_memory": 1000000000,
        "node_name": "cpu-worker-1"
      }
    ],
    "head_node_port": 10001,
    "dashboard_port": 8265,
    "head_node_host": "127.0.0.1"
  }
}
```

### Advanced Cluster Configuration

```json
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 8,
    "num_gpus": 2,
    "object_store_memory": 4000000000,
    "worker_nodes": [
      {
        "num_cpus": 16,
        "num_gpus": 4,
        "object_store_memory": 8000000000,
        "resources": {
          "custom_gpu": 2,
          "high_memory": 1,
          "fast_storage": 1
        },
        "node_name": "high-performance-worker"
      }
    ],
    "head_node_port": 10001,
    "dashboard_port": 8265,
    "head_node_host": "0.0.0.0"
  }
}
```

## Runtime Environment Configuration

### Basic Runtime Environment

```json
{
  "tool": "submit_job",
  "arguments": {
    "entrypoint": "python examples/simple_job.py",
    "runtime_env": {
      "pip": ["numpy", "pandas"]
    }
  }
}
```

### Advanced Runtime Environment

```json
{
  "tool": "submit_job",
  "arguments": {
    "entrypoint": "python examples/distributed_training.py",
    "runtime_env": {
      "pip": ["torch==2.0.0", "numpy==1.24.0", "scikit-learn==1.3.0"],
      "env_vars": {
        "CUDA_VISIBLE_DEVICES": "0,1",
        "OMP_NUM_THREADS": "4",
        "RAY_OBJECT_STORE_ALLOW_SLOW_STORAGE": "1"
      },
      "working_dir": "/path/to/code",
      "py_modules": ["my_module"]
    }
  }
}
```

## Enhanced Output Configuration

### Enable Enhanced Output

Set the environment variable to enable enhanced output mode:

```bash
export RAY_MCP_ENHANCED_OUTPUT=true
```

Or in your MCP client configuration:

```json
{
  "mcpServers": {
    "ray-mcp": {
      "command": "/path/to/your/venv/bin/ray-mcp",
      "env": {
        "RAY_MCP_ENHANCED_OUTPUT": "true"
      }
    }
  }
}
```

### Enhanced Output Features

When enabled, tool responses include:

- **Tool Result Summary**: Brief summary of what the tool call accomplished
- **Context**: Additional context about what the result means
- **Suggested Next Steps**: Relevant next actions with specific tool names
- **Available Commands**: Quick reference of commonly used tools

## Network Configuration

### Local Development

For local development, use the default configuration:

```json
{
  "tool": "init_ray",
  "arguments": {
    "head_node_host": "127.0.0.1",
    "head_node_port": 10001,
    "dashboard_port": 8265
  }
}
```

### Multi-Machine Clusters

For multi-machine clusters, configure network settings:

```json
{
  "tool": "init_ray",
  "arguments": {
    "head_node_host": "0.0.0.0",
    "head_node_port": 10001,
    "dashboard_port": 8265,
    "worker_nodes": [
      {
        "num_cpus": 4,
        "node_name": "worker-1",
        "head_node_host": "192.168.1.100"
      }
    ]
  }
}
```

## Resource Configuration

### CPU Configuration

```json
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 8,
    "worker_nodes": [
      {
        "num_cpus": 16,
        "node_name": "high-cpu-worker"
      }
    ]
  }
}
```

### GPU Configuration

```json
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4,
    "num_gpus": 2,
    "worker_nodes": [
      {
        "num_cpus": 8,
        "num_gpus": 4,
        "node_name": "gpu-worker"
      }
    ]
  }
}
```

### Memory Configuration

```json
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4,
    "object_store_memory": 2000000000,
    "worker_nodes": [
      {
        "num_cpus": 8,
        "object_store_memory": 4000000000,
        "node_name": "high-memory-worker"
      }
    ]
  }
}
```

### Custom Resources

```json
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4,
    "worker_nodes": [
      {
        "num_cpus": 8,
        "resources": {
          "custom_gpu": 2,
          "high_memory": 1,
          "fast_storage": 1,
          "specialized_accelerator": 1
        },
        "node_name": "specialized-worker"
      }
    ]
  }
}
```

## Security Configuration

### Basic Security

For basic security, use localhost binding:

```json
{
  "tool": "init_ray",
  "arguments": {
    "head_node_host": "127.0.0.1",
    "head_node_port": 10001
  }
}
```

### Network Security

For network deployments, consider:

- Firewall configuration
- Network isolation
- Authentication mechanisms
- SSL/TLS encryption

## Performance Configuration

### High-Performance Setup

```json
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 16,
    "num_gpus": 4,
    "object_store_memory": 8000000000,
    "worker_nodes": [
      {
        "num_cpus": 32,
        "num_gpus": 8,
        "object_store_memory": 16000000000,
        "resources": {
          "high_performance": 1
        },
        "node_name": "compute-node-1"
      }
    ]
  }
}
```

### Memory-Optimized Setup

```json
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4,
    "object_store_memory": 4000000000,
    "worker_nodes": [
      {
        "num_cpus": 8,
        "object_store_memory": 8000000000,
        "node_name": "memory-node-1"
      }
    ]
  }
}
```

## Troubleshooting Configuration

### Common Configuration Issues

1. **Port Conflicts**: Use automatic port allocation or specify unique ports
2. **Resource Conflicts**: Ensure worker resources don't exceed head node capacity
3. **Network Issues**: Verify network connectivity for multi-node clusters
4. **Memory Issues**: Configure appropriate object store memory

### Debug Configuration

Enable debug logging by setting environment variables:

```bash
export RAY_MCP_DEBUG=true
export RAY_LOG_LEVEL=DEBUG
```

### Configuration Validation

The Ray MCP Server validates configuration parameters and provides helpful error messages for:

- Invalid resource specifications
- Port conflicts
- Network connectivity issues
- Memory configuration problems

## Best Practices

1. **Start Simple**: Begin with basic configurations and add complexity gradually
2. **Monitor Resources**: Use `inspect_ray` to monitor resource usage
3. **Test Configurations**: Validate configurations in development before production
4. **Document Settings**: Keep configuration documentation up to date
5. **Use Enhanced Output**: Enable enhanced output for better debugging
6. **Plan for Scale**: Design configurations that can scale with your needs 