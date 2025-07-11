# Ray MCP Server

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Ray 2.47+](https://img.shields.io/badge/ray-2.47+-orange.svg)](https://docs.ray.io/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)

**Model Context Protocol (MCP) server for Ray distributed computing.** Enables LLM agents to programmatically manage Ray clusters, submit jobs, and monitor distributed workloads across local and Kubernetes environments.

## ✨ Key Features

🚀 **Unified Ray Management** - Seamless operation across local Ray clusters and Kubernetes via KubeRay  
☁️ **Cloud Provider Support** - Native integration with Google Kubernetes Engine (GKE) and local Kubernetes  
🎯 **Intelligent Job Management** - Automatic detection between local and KubeRay job types  
📊 **Advanced Monitoring** - Comprehensive logging, debugging, and cluster health monitoring  
⚡ **Auto-scaling** - Dynamic worker scaling and resource management  
🔒 **Production Ready** - RBAC, service accounts, and enterprise security features

## 🚀 Quick Start

### Installation

```bash
# Basic installation
uv add ray-mcp
# or
pip install ray-mcp

# With cloud provider support
uv add "ray-mcp[cloud]"
# or  
pip install "ray-mcp[cloud]"
```

### Configure MCP Client

Add to your MCP client (e.g., Claude Desktop):

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

```python
# Start local Ray cluster
init_ray_cluster()

# Submit a job
submit_ray_job(entrypoint="python my_script.py")

# Monitor cluster
inspect_ray_cluster()
list_ray_jobs()
```

## 🎯 Core Capabilities

### Local Ray Clusters

```python
# Head-only cluster
init_ray_cluster(worker_nodes=[])

# Multi-worker cluster with custom resources
init_ray_cluster(
    num_cpus=8,
    worker_nodes=[
        {"num_cpus": 4, "num_gpus": 1},
        {"num_cpus": 2}
    ]
)
```

### KubeRay on Kubernetes

```python
# Create KubeRay cluster
init_ray_cluster(
    cluster_type="kubernetes",
    cluster_name="ml-cluster",
    head_node_spec={
        "num_cpus": 4,
        "memory_request": "8Gi",
        "service_type": "LoadBalancer"
    },
    worker_node_specs=[{
        "group_name": "workers",
        "replicas": 3,
        "num_cpus": 2,
        "memory_request": "4Gi"
    }]
)

# Scale workers dynamically
scale_ray_cluster(
    cluster_name="ml-cluster",
    worker_group_name="workers",
    replicas=10
)
```

### Cloud Provider Integration

```python
# Authenticate with GKE
authenticate_cloud_provider(
    provider="gke",
    service_account_path="/path/to/key.json",
    project_id="my-project"
)

# Create GKE cluster
create_kubernetes_cluster(
    provider="gke",
    cluster_spec={
        "name": "ray-cluster",
        "zone": "us-central1-a",
        "machine_type": "n1-standard-4",
        "node_count": 4
    }
)
```

### Advanced Job Management

```python
# Job with runtime environment
submit_ray_job(
    entrypoint="python train_model.py",
    runtime_env={
        "pip": ["torch>=1.12", "transformers"],
        "env_vars": {"CUDA_VISIBLE_DEVICES": "0,1"}
    }
)

# KubeRay job with cluster lifecycle
submit_ray_job(
    entrypoint="python batch_job.py",
    job_type="kubernetes",
    shutdown_after_job_finishes=True,
    ttl_seconds_after_finished=3600
)
```

## 🛠️ Available Tools

### Cluster Management
- `init_ray_cluster` - Create or connect to Ray clusters (local/KubeRay)
- `stop_ray_cluster` - Stop local clusters or delete KubeRay clusters  
- `inspect_ray_cluster` - Get cluster status and resource information
- `scale_ray_cluster` - Scale worker nodes dynamically
- `list_ray_clusters` - List all available clusters

### Job Operations  
- `submit_ray_job` - Submit jobs with automatic local/KubeRay detection
- `list_ray_jobs` - List jobs across all cluster types
- `inspect_ray_job` - Get detailed job information and debugging data
- `cancel_ray_job` - Cancel running jobs
- `retrieve_logs` - Get logs with pagination and error analysis

### Cloud Providers
- `detect_cloud_provider` - Auto-detect cloud environment
- `authenticate_cloud_provider` - Authenticate with GKE/local clusters
- `list_kubernetes_clusters` - Discover available Kubernetes clusters
- `connect_kubernetes_cluster` - Connect to existing clusters
- `create_kubernetes_cluster` - Create new GKE clusters
- `get_kubernetes_cluster_info` - Get detailed cluster information

## 🏗️ Architecture

```
┌─────────────────┐    MCP Protocol    ┌─────────────────┐
│   LLM Agent     │◄──────────────────►│   Ray MCP       │
│                 │                    │   Server        │
└─────────────────┘                    └─────────┬───────┘
                                                 │
                   ┌─────────────────────────────┼─────────────────────────────┐
                   │                             │                             │
                   ▼                             ▼                             ▼
            ┌─────────────┐              ┌─────────────┐              ┌─────────────┐
            │ Local Ray   │              │  KubeRay    │              │   Cloud     │
            │ Clusters    │              │ Clusters    │              │ Providers   │
            └─────────────┘              └─────────────┘              └─────────────┘
```

**Modular Design:**
- **Unified Manager** - Single interface for all cluster types
- **Cloud Integration** - Pluggable cloud provider support
- **Smart Job Routing** - Automatic detection of cluster capabilities
- **Extensible Tools** - Clean separation of concerns

## 📖 Documentation

| Guide | Description |
|-------|-------------|
| [**Tools Reference**](docs/TOOLS.md) | Complete tool documentation with all parameters |
| [**Examples**](docs/EXAMPLES.md) | Comprehensive examples for all use cases |
| [**Configuration**](docs/CONFIGURATION.md) | Setup guides for cloud providers and authentication |
| [**Troubleshooting**](docs/TROUBLESHOOTING.md) | Solutions for common issues and debugging |

## 🔧 Environment Setup

### Cloud Provider Authentication

#### Google Cloud (GKE)
```bash
# Install dependencies
uv add "ray-mcp[gke]"

# Set up service account
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
export GOOGLE_CLOUD_PROJECT="your-project-id"
```

#### Local Kubernetes
```bash
# Ensure kubectl is configured
kubectl cluster-info

# Install KubeRay operator
kubectl apply -f https://raw.githubusercontent.com/ray-project/kuberay/release-0.8/deploy/kuberay-operator.yaml
```

### Environment Variables

```bash
# Enable enhanced output for LLMs
export RAY_MCP_ENHANCED_OUTPUT=true

# Disable Ray usage statistics
export RAY_DISABLE_USAGE_STATS=1

# Set logging level
export RAY_MCP_LOG_LEVEL=INFO
```

## 🤝 Contributing

We welcome contributions! Please see our [development guide](docs/DEVELOPMENT.md) for details on:

- Setting up the development environment
- Running tests
- Code style and formatting
- Submitting pull requests

## 📋 Requirements

- **Python**: 3.10 or higher
- **Ray**: 2.47.0 or higher  
- **Kubernetes**: 1.20+ (for KubeRay features)
- **Operating Systems**: Linux, macOS, Windows

### Optional Requirements
- **Google Cloud SDK**: For GKE integration
- **Docker**: For containerized deployments
- **kubectl**: For Kubernetes cluster management

## 🆘 Support

### Getting Help
- **Documentation**: Comprehensive guides in [docs/](docs/)
- **Examples**: Ready-to-run examples in [examples/](examples/)
- **Issues**: Report bugs or request features on [GitHub Issues](https://github.com/pradeepiyer/ray-mcp/issues)

### Common Issues
- **Installation Problems**: Check installation section above
- **Authentication Errors**: Check [Configuration Guide](docs/CONFIGURATION.md)  
- **Cluster Issues**: Review [Troubleshooting Guide](docs/TROUBLESHOOTING.md)

## 📄 License

Licensed under the [Apache License 2.0](LICENSE).

## 🙏 Acknowledgments

Built on top of:
- [**Ray**](https://docs.ray.io/) - Distributed computing framework
- [**KubeRay**](https://ray-project.github.io/kuberay/) - Ray on Kubernetes operator
- [**MCP**](https://modelcontextprotocol.io/) - Model Context Protocol

---

⭐ **Star this repo** if Ray MCP helps with your distributed computing workflows! 