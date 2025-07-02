# Ray MCP Server

Model Context Protocol (MCP) server for Ray distributed computing. Enables LLM agents to programmatically manage Ray clusters, submit jobs, and monitor distributed workloads.

## Overview

Ray MCP provides a bridge between LLM agents and Ray distributed computing through the MCP protocol. Built with a modular, maintainable architecture using Domain-Driven Design principles.

## Features

- **Cluster Management**: Initialize, connect to, and stop Ray clusters
- **Job Operations**: Submit, monitor, cancel, and inspect distributed jobs
- **Worker Node Control**: Manage worker nodes with custom resource configurations
- **Comprehensive Logging**: Retrieve and analyze logs with error detection
- **Multi-Node Support**: Handle head-only or multi-worker cluster topologies

## Installation

```bash
# Install with uv (recommended)
git clone https://github.com/pradeepiyer/ray-mcp.git
cd ray-mcp
uv sync

# Or with pip
pip install -e .
```

## Quick Start

### 1. Configure MCP Client

Add to your MCP client configuration (e.g., Claude Desktop):

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

### 2. Basic Usage

```python
# Initialize a Ray cluster
init_ray()

# Submit a distributed job
submit_job(entrypoint="python my_script.py")

# Monitor cluster status
inspect_ray()

# Retrieve job logs
retrieve_logs(identifier="job_123")
```

## Available Tools

- `init_ray` - Initialize or connect to Ray cluster
- `stop_ray` - Stop Ray cluster
- `inspect_ray` - Get cluster status and information
- `submit_job` - Submit jobs to the cluster
- `list_jobs` - List all jobs
- `inspect_job` - Inspect specific job with logs/debug info
- `cancel_job` - Cancel running jobs
- `retrieve_logs` - Get logs with error analysis
- `retrieve_logs_paginated` - Get logs with pagination support

## Architecture

Ray MCP uses a modular architecture with focused components:

```
┌─────────────────┐    MCP Protocol    ┌─────────────────┐
│   LLM Agent     │◄──────────────────►│   Ray MCP       │
│                 │                    │   Server        │
└─────────────────┘                    └─────────┬───────┘
                                                 │
                                                 ▼
                                       ┌─────────────────┐
                                       │   Core Layer    │
                                       │                 │
                                       │ ┌─────────────┐ │
                                       │ │StateManager │ │
                                       │ └─────────────┘ │
                                       │ ┌─────────────┐ │
                                       │ │ClusterMgr   │ │
                                       │ └─────────────┘ │
                                       │ ┌─────────────┐ │
                                       │ │JobManager   │ │
                                       │ └─────────────┘ │
                                       │ ┌─────────────┐ │
                                       │ │LogManager   │ │
                                       │ └─────────────┘ │
                                       │ ┌─────────────┐ │
                                       │ │PortManager │ │
                                       │ └─────────────┘ │
                                       └─────────┬───────┘
                                                 │
                                       Ray API   │
                                                 ▼
                                       ┌─────────────────┐
                                       │   Ray Cluster   │
                                       │                 │
                                       │  ┌──────────┐   │
                                       │  │Head Node │   │
                                       │  └──────────┘   │
                                       │  ┌──────────┐   │
                                       │  │Worker 1  │   │
                                       │  └──────────┘   │
                                       │  ┌──────────┐   │
                                       │  │Worker N  │   │
                                       │  └──────────┘   │
                                       └─────────────────┘
```

### Core Components

- **StateManager**: Thread-safe cluster state management
- **ClusterManager**: Pure cluster lifecycle operations
- **JobManager**: Job operations and lifecycle management
- **LogManager**: Centralized log retrieval with memory protection
- **PortManager**: Port allocation with race condition prevention
- **UnifiedManager**: Backward compatibility facade

## Development

```bash
# Run tests
make test          # Complete test suite
make test-fast     # Unit tests only
make test-smoke    # Critical functionality validation

# Code quality
make lint          # Linting checks
make format        # Code formatting
```

## Documentation

- [Configuration Guide](docs/CONFIGURATION.md) - Setup and configuration options
- [Tools Reference](docs/TOOLS.md) - Complete tool documentation
- [Examples](docs/EXAMPLES.md) - Usage examples and patterns
- [Development](docs/DEVELOPMENT.md) - Development setup and testing
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions

## Requirements

- Python ≥ 3.10
- Ray ≥ 2.47.0
- MCP ≥ 1.0.0

## License

Apache-2.0 License

## Contributing

Contributions welcome! See [DEVELOPMENT.md](docs/DEVELOPMENT.md) for setup instructions. 