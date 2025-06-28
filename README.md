# Ray MCP Server

A Model Context Protocol (MCP) server that provides comprehensive Ray cluster management and job orchestration capabilities through a standardized interface.

## Overview

The Ray MCP Server enables AI assistants and other MCP clients to interact with Ray clusters for distributed computing tasks. It provides tools for cluster initialization, job submission, monitoring, debugging, and resource management.

## Features

### 🚀 **Cluster Management**
- Initialize Ray clusters with configurable resources
- Start multi-node clusters with worker nodes
- Monitor cluster health and performance
- Gracefully shutdown clusters

### 📊 **Job Orchestration**
- Submit distributed jobs to Ray clusters
- Monitor job status and progress
- Retrieve job logs and debug information
- List and manage multiple jobs

### 🔍 **Monitoring & Debugging**
- Real-time cluster status monitoring
- Resource utilization analysis
- Health checks and optimization recommendations
- Comprehensive logging and error analysis

### ⚡ **Performance Optimized**
- CI-optimized test suite with minimal resource usage
- Automatic environment detection (CI vs local)
- Efficient resource allocation and cleanup
- Fast startup and shutdown times

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd mcp

# Install dependencies
uv sync --all-extras --dev
```

### Basic Usage

```python
# Initialize a Ray cluster
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4,
    "worker_nodes": [
      {
        "num_cpus": 2,
        "node_name": "worker-1"
      }
    ]
  }
}

# Submit a job
{
  "tool": "submit_job",
  "arguments": {
    "entrypoint": "python my_script.py"
  }
}

# Monitor cluster status
{
  "tool": "inspect_ray",
  "arguments": {}
}
```

## Configuration

### Environment-Specific Optimization

The server automatically optimizes resource usage based on the environment:

- **CI Environments**: Head node only (1 CPU) for minimal resource usage
- **Local Development**: Full cluster with worker nodes for comprehensive testing

### Resource Constraints

| Environment | CPU Allocation | Worker Nodes | Wait Time |
|-------------|----------------|--------------|-----------|
| CI          | 1 CPU          | None         | 10s       |
| Local       | 2 CPUs         | 2 workers    | 30s       |

## Testing

### Test Suite Overview

The project includes a comprehensive test suite optimized for different environments:

- **Unit Tests**: Core functionality tests with fast execution
- **Integration Tests**: End-to-end workflow testing
- **E2E Tests**: Optimized integration tests for CI and local environments

### Running Tests

```bash
# Run all tests (including e2e)
uv run pytest tests/

# Run unit tests only
uv run pytest tests/ -k "not e2e"

# Run e2e tests only
uv run pytest tests/test_e2e_integration.py

# Run with coverage
uv run pytest tests/ --cov=ray_mcp --cov-report=html
```

### Test Performance

- **Unit Tests**: Fast execution with comprehensive coverage
- **E2E Tests (CI)**: Optimized for minimal resource usage
- **E2E Tests (Local)**: Full cluster testing with comprehensive coverage
- **Overall Coverage**: Combined coverage from unit and e2e tests

## Available Tools

### Cluster Operations
- `init_ray` - Initialize or connect to Ray clusters
- `stop_ray` - Gracefully shutdown Ray clusters
- `inspect_ray` - Get comprehensive cluster information

### Job Management
- `submit_job` - Submit jobs to Ray clusters
- `list_jobs` - List all jobs in the cluster
- `inspect_job` - Get detailed job information
- `cancel_job` - Cancel running jobs

### Logging & Debugging
- `retrieve_logs` - Retrieve logs from jobs, actors, or nodes

## Architecture

### Core Components

- **RayManager**: Manages Ray cluster lifecycle and operations
- **WorkerManager**: Handles multi-node cluster worker processes
- **ToolRegistry**: Provides MCP-compliant tool interface
- **Tool Functions**: Individual tool implementations

### MCP Integration

The server implements the Model Context Protocol (MCP) specification, providing:
- Standardized tool definitions and schemas
- JSON-RPC communication protocol
- Type-safe parameter validation
- Consistent error handling

## Development

### Project Structure

```
mcp/
├── ray_mcp/                 # Core server implementation
│   ├── main.py             # MCP server entry point
│   ├── ray_manager.py      # Ray cluster management
│   ├── worker_manager.py   # Worker node management
│   ├── tool_registry.py    # MCP tool registry
│   └── tool_functions.py   # Individual tool functions
├── tests/                  # Test suite
│   ├── test_e2e_integration.py  # Optimized e2e tests
│   ├── test_integration.py      # Integration tests
│   ├── test_ray_manager.py      # Unit tests
│   └── test_worker_manager.py   # Worker management tests
├── examples/               # Example scripts and configurations
├── docs/                   # Documentation
└── scripts/                # Utility scripts
```

### Development Workflow

1. **Setup**: Install dependencies with `uv sync --all-extras --dev`
2. **Testing**: Run tests with `uv run pytest tests/`
3. **Linting**: Check code quality with `uv run black`, `uv run isort`, `uv run pyright`
4. **Documentation**: Update docs in the `docs/` directory

### CI/CD Integration

The project is optimized for CI environments:
- Automatic environment detection
- Resource-constrained testing
- Fast execution times
- Comprehensive coverage reporting

## Documentation

- **[Tools Reference](docs/TOOLS.md)** - Complete tool documentation
- **[Configuration Guide](docs/CONFIGURATION.md)** - Setup and configuration
- **[Development Guide](docs/DEVELOPMENT.md)** - Development workflow
- **[Examples](docs/EXAMPLES.md)** - Usage examples and patterns
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run the test suite
5. Submit a pull request

## License

[License information]

## Support

For issues and questions:
- Check the [Troubleshooting Guide](docs/TROUBLESHOOTING.md)
- Review the [Examples](docs/EXAMPLES.md)
- Open an issue on GitHub 