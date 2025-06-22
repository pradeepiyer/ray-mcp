# Ray MCP Server

A Model Context Protocol (MCP) server for interacting with [Ray](https://github.com/ray-project/ray) distributed computing clusters. This server provides AI assistants with tools to manage Ray clusters, submit jobs, monitor resources, and perform various Ray operations.

## Features

- **Cluster Management** - Start, stop, and connect to Ray clusters
- **Job Management** - Submit, monitor, and control Ray jobs  
- **Actor Management** - List and manage Ray actors
- **Resource Monitoring** - Track cluster performance and health
- **Advanced Operations** - Health checks, optimization recommendations, and debugging

## Quick Start

### Installation
```bash
git clone https://github.com/pradeepiyer/ray-mcp.git
cd ray-mcp
pip install -e .
```

### Run the Server
```bash
ray-mcp
```

### Configure with AI Assistant
Add to your MCP client configuration (e.g., Claude Desktop):

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

### Basic Usage
**Important**: You must initialize Ray first before using other tools.

```
"Start a Ray cluster with 4 CPUs"
"Submit a job with entrypoint 'python examples/simple_job.py'"
"Check cluster status"
"List all running jobs"
```

## Available Tools

The server provides **19 tools** organized into categories:

- **Cluster Operations** (6 tools): `start_ray`, `connect_ray`, `stop_ray`, `cluster_status`, `cluster_resources`, `cluster_nodes`
- **Job Operations** (7 tools): `submit_job`, `list_jobs`, `job_status`, `cancel_job`, `monitor_job`, `debug_job`, `get_logs`
- **Actor Operations** (2 tools): `list_actors`, `kill_actor`
- **Monitoring** (3 tools): `performance_metrics`, `health_check`, `optimize_config`
- **Scheduling** (1 tool): `schedule_job`

## Documentation

- **[📖 Detailed Tools Reference](docs/TOOLS.md)** - Complete tool parameters and usage
- **[🚀 Examples and Usage Patterns](docs/EXAMPLES.md)** - Example workflows and scripts
- **[⚙️ Configuration Guide](docs/CONFIGURATION.md)** - Environment setup and client config
- **[🔧 Development Guide](docs/DEVELOPMENT.md)** - Architecture, testing, and contributing
- **[🩺 Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and debugging

## Prerequisites

- Python 3.8 or higher
- Ray 2.30.0 or higher
- MCP SDK 1.0.0 or higher

## Server Behavior

⚠️ **Important**: Ray is NOT automatically initialized when the server starts. You must use `start_ray` or `connect_ray` tools first before using other functionality.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

See [Development Guide](docs/DEVELOPMENT.md) for detailed instructions.

## License

MIT License - see LICENSE file for details.

## Related Projects

- [Ray](https://github.com/ray-project/ray) - Distributed computing framework
- [Model Context Protocol](https://github.com/modelcontextprotocol) - Protocol specification
- [Claude Desktop](https://claude.ai/desktop) - AI assistant with MCP support 