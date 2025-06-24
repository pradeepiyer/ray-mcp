# Ray MCP Server

A Model Context Protocol (MCP) server for interacting with [Ray](https://github.com/ray-project/ray) distributed computing clusters. This server provides AI assistants with tools to manage Ray clusters, submit jobs, monitor resources, and perform various Ray operations.

## ✨ Features

- **🔧 Cluster Management** - Start, stop, and connect to Ray clusters
- **📋 Job Management** - Submit, monitor, and control Ray jobs  
- **🎭 Actor Management** - List and manage Ray actors
- **📊 Resource Monitoring** - Track cluster performance and health
- **🔍 Advanced Operations** - Health checks, optimization recommendations, and debugging
- **🚀 Modern Infrastructure** - Full UV package management with fast, reliable installs
- **📝 Comprehensive Examples** - 5 detailed examples from basic to advanced workflows
- **🧪 Robust Testing** - 177 tests with 90%+ coverage ensuring reliability

## 🚀 Quick Start

### Installation

**Prerequisites**: Install [uv](https://docs.astral.sh/uv/getting-started/installation/) first:
```bash
# Install uv
curl -Lk https://astral.sh/uv/install.sh | sh
# or: pip install uv
```

**Install Ray MCP:**
```bash
git clone https://github.com/pradeepiyer/ray-mcp.git
cd ray-mcp
uv sync  # Install all dependencies
```

**Alternative installation methods:**
```bash
# Install package only (production)
uv pip install -e .

# Development setup with all dev dependencies
make dev-install
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

## 🛠️ Available Tools

The server provides **19 tools** organized into categories:

- **Cluster Operations** (6 tools): `start_ray`, `connect_ray`, `stop_ray`, `cluster_status`, `cluster_resources`, `cluster_nodes`
- **Job Operations** (7 tools): `submit_job`, `list_jobs`, `job_status`, `cancel_job`, `monitor_job`, `debug_job`, `get_logs`
- **Actor Operations** (2 tools): `list_actors`, `kill_actor`
- **Monitoring & Health** (3 tools): `performance_metrics`, `health_check`, `optimize_config`
- **Advanced Features** (1 tool): `schedule_job`

## 📚 Documentation

- **[📖 Detailed Tools Reference](docs/TOOLS.md)** - Complete tool parameters and usage
- **[🚀 Examples and Usage Patterns](docs/EXAMPLES.md)** - 5 comprehensive examples from basic to advanced
- **[⚙️ Configuration Guide](docs/CONFIGURATION.md)** - Environment setup and client config
- **[🔧 Development Guide](docs/DEVELOPMENT.md)** - Architecture, testing, and contributing
- **[🩺 Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and debugging

## 💡 Example Scripts

The `examples/` directory contains 5 comprehensive Ray applications:

1. **`simple_job.py`** - Basic Ray remote functions and job patterns
2. **`actor_example.py`** - Stateful distributed computing with actors
3. **`data_pipeline.py`** - Multi-stage data processing pipeline
4. **`distributed_training.py`** - Parameter server pattern for ML training
5. **`workflow_orchestration.py`** - Complex multi-step workflow management

**All examples can be run directly** - they auto-initialize Ray if needed:
```bash
python examples/simple_job.py
python examples/data_pipeline.py
# ... or any other example
```

## 🔧 Prerequisites

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager (modern Python package installer)
- Ray 2.47.0 or higher  
- MCP SDK 1.0.0 or higher

> **🚀 Modern Python Package Management**: Ray MCP Server uses `uv` for fast, reliable dependency management and installation. `uv` provides faster installs, better dependency resolution, and improved reproducibility compared to `pip`.

## 📊 Quality & Testing

**Test Coverage**: ✅ **90.21%** coverage with **177 tests** all passing

- **Unit Tests**: All core functionality with mocks
- **Integration Tests**: End-to-end workflows
- **E2E Tests**: Real Ray cluster scenarios
- **Example Tests**: All example scripts verified

Run tests:
```bash
make test-full    # Complete test suite
make test-fast    # Quick development tests
make test-smoke   # Minimal verification
```

## ⚡ Server Behavior

⚠️ **Important**: Ray is NOT automatically initialized when the server starts. You must use `start_ray` or `connect_ray` tools first before using other functionality.

**This design provides**:
- 🎯 **Explicit Control** - Clear separation between server startup and Ray initialization
- 💾 **Resource Efficiency** - No unnecessary Ray processes during server startup
- 🔧 **Flexibility** - Choose your Ray cluster configuration when needed
- 🚫 **Error Prevention** - Avoid connection issues during server boot

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Install development dependencies: `make dev-install`
4. Make changes with tests: `make test-fast`
5. Submit a pull request

See [Development Guide](docs/DEVELOPMENT.md) for detailed instructions.

## 📄 License

MIT License - see LICENSE file for details.

## 🌟 Related Projects

- [Ray](https://github.com/ray-project/ray) - Distributed computing framework
- [Model Context Protocol](https://github.com/modelcontextprotocol) - Protocol specification
- [Claude Desktop](https://claude.ai/desktop) - AI assistant with MCP support
- [uv](https://docs.astral.sh/uv/) - Fast Python package installer and resolver 