# Ray MCP Server

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Ray 2.47+](https://img.shields.io/badge/ray-2.47+-orange.svg)](https://docs.ray.io/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)

**Model Context Protocol (MCP) server for Ray distributed computing.** Enables LLM agents to manage Ray clusters, submit jobs, and monitor workloads through natural language prompts.

## ✨ Features

- **3 Simple Tools**: `ray_cluster`, `ray_job`, `cloud`
- **Natural Language Interface**: Single prompt parameter per tool
- **Unified Management**: Works with local Ray, KubeRay, and cloud providers
- **Automatic Detection**: Intelligent routing between environments

## 🚀 Quick Start

### Installation

```bash
uv add ray-mcp
```

### Configure MCP Client

Add to your MCP client configuration:

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

### Basic Usage

```bash
# Cluster management
ray_cluster: "create a local cluster with 4 CPUs"
ray_cluster: "connect to kubernetes cluster my-cluster"
ray_cluster: "inspect cluster status"

# Job operations
ray_job: "submit job with script train.py"
ray_job: "list all running jobs"
ray_job: "get logs for job raysubmit_123"

# Cloud providers
cloud: "authenticate with GCP project ml-experiments"
cloud: "list all GKE clusters"
cloud: "connect to cluster production-cluster"
```

## 🎯 Tool Reference

### `ray_cluster`
Manage Ray clusters with natural language prompts.

**Examples:**
- `"create a local cluster with 4 CPUs"`
- `"create head-only cluster"`
- `"connect to cluster at 192.168.1.100:10001"`
- `"create Ray cluster named ml-cluster with 3 workers on kubernetes"`
- `"stop the current cluster"`
- `"inspect cluster status"`

### `ray_job`
Submit and manage Ray jobs.

**Examples:**
- `"submit job with script train.py"`
- `"submit job with script train.py and 2 CPUs"`
- `"list all running jobs"`
- `"get logs for job raysubmit_123"`
- `"cancel job raysubmit_456"`
- `"create Ray job with training script on kubernetes"`

### `cloud`
Manage cloud providers and authentication.

**Examples:**
- `"authenticate with GCP project ml-experiments"`
- `"list all GKE clusters"`
- `"connect to GKE cluster production-cluster"`
- `"check cloud environment setup"`
- `"create GKE cluster ml-cluster with 3 nodes"`

## 🏗️ Architecture

```
┌─────────────────┐    Natural Language    ┌─────────────────┐
│   LLM Agent     │──────────────────────►│   Ray MCP       │
│                 │     Single Prompt      │   Server        │
└─────────────────┘                        └─────────┬───────┘
                                                     │
                   ┌─────────────────────────────────┼─────────────────────────────┐
                   │                                 │                             │
                   ▼                                 ▼                             ▼
            ┌─────────────┐                  ┌─────────────┐              ┌─────────────┐
            │ Local Ray   │                  │  KubeRay    │              │   Cloud     │
            │ Clusters    │                  │ Clusters    │              │ Providers   │
            └─────────────┘                  └─────────────┘              └─────────────┘
```

**Key Components:**
- **ActionParser**: Converts natural language to structured actions
- **RayUnifiedManager**: Routes requests between specialized managers
- **RayHandlers**: Processes MCP tool calls with validation

## 🔧 Environment Setup

### Cloud Provider Authentication

#### Google Cloud (GKE)
```bash
# Install with GKE support
uv add "ray-mcp[gke]"

# Set up authentication
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

#### Local Kubernetes
```bash
# Install KubeRay operator
kubectl apply -f https://raw.githubusercontent.com/ray-project/kuberay/release-0.8/deploy/kuberay-operator.yaml
```

### Environment Variables

```bash
# Enhanced LLM-friendly output
export RAY_MCP_ENHANCED_OUTPUT=true

# Disable Ray usage statistics
export RAY_DISABLE_USAGE_STATS=1

# Set logging level
export RAY_MCP_LOG_LEVEL=INFO
```

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [Configuration](docs/CONFIGURATION.md) | Authentication and setup guides |
| [Examples](docs/EXAMPLES.md) | Common usage patterns |
| [Development](docs/DEVELOPMENT.md) | Contributing and development setup |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common issues and solutions |

## 🛠️ Development

```bash
# Install development dependencies
make dev-install

# Run tests
make test-fast      # Unit tests with mocking
make test-e2e       # End-to-end integration tests
make test           # Complete test suite

# Code quality
make lint           # Run linting
make format         # Format code
```

## 📋 Requirements

- **Python**: 3.10+
- **Ray**: 2.47.0+
- **Kubernetes**: 1.20+ (for KubeRay features)

**Optional:**
- **Google Cloud SDK**: For GKE integration
- **kubectl**: For Kubernetes management

## 📄 License

Licensed under the [Apache License 2.0](LICENSE).