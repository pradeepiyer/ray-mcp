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
- **Cloud Provider Support**: Native support for GKE, EKS, and local Kubernetes clusters
- **Multi-Cloud Operations**: Seamlessly switch between cloud providers and manage clusters across environments

## Installation

Ray MCP can be installed using pip or uv (recommended):

```bash
# Using uv (recommended - faster and more reliable)
uv add ray-mcp

# Using pip
pip install ray-mcp
```

## Cloud Provider Setup

For cloud provider support (GKE, EKS), install the appropriate optional dependencies:

```bash
# For Google Kubernetes Engine (GKE)
uv add "ray-mcp[gke]"  # or pip install "ray-mcp[gke]"

# For Amazon Elastic Kubernetes Service (EKS) 
uv add "ray-mcp[eks]"  # or pip install "ray-mcp[eks]"

# For all cloud providers
uv add "ray-mcp[cloud]"  # or pip install "ray-mcp[cloud]"
```

### Claude Desktop Setup

When using Ray MCP with Claude Desktop, the MCP server runs in a separate Python environment. To ensure cloud provider support works:

1. **Install with cloud dependencies in the same environment where you installed ray-mcp:**
   ```bash
   # Navigate to your ray-mcp directory
   cd /path/to/ray-mcp
   
   # Install cloud dependencies
   uv sync --extra gke  # For GKE support
   # or
   uv sync --extra cloud  # For all cloud providers
   ```

2. **Verify installation:**
   ```bash
   python -c "
   try:
       from google.cloud import container_v1
       print('✅ Google Cloud SDK installed')
   except ImportError:
       print('❌ Google Cloud SDK not found')
       
   try:
       import boto3
       print('✅ AWS SDK installed') 
   except ImportError:
       print('❌ AWS SDK not found')
   "
   ```

3. **Restart Claude Desktop** after installing dependencies so it picks up the new packages.

### Troubleshooting Claude Desktop

If you encounter issues with cloud provider support in Claude Desktop:

1. **Check Environment Status:**
   Use the built-in environment checker:
   ```
   check_environment
   ```
   This will show you exactly what's installed and what's missing.

2. **Automatic Setup (Development):**
   If you're working with the development version:
   ```bash
   cd /path/to/ray-mcp
   PYTHONPATH=. python scripts/setup_claude_desktop.py
   ```

3. **Manual Installation for Claude Desktop:**
   ```bash
   # Find where ray-mcp is installed
   python -c "import ray_mcp; print(ray_mcp.__file__)"
   
   # Install in the same environment
   pip install "ray-mcp[gke]"  # For GKE
   pip install "ray-mcp[eks]"  # For EKS  
   pip install "ray-mcp[cloud]"  # For all cloud providers
   ```

4. **Verify Installation:**
   ```bash
   python -c "
   try:
       from google.cloud import container_v1
       print('✅ Google Cloud SDK installed')
   except ImportError:
       print('❌ Google Cloud SDK not found')
   "
   ```

5. **Common Issues:**
   - **Error: `'str' object has no attribute 'isoformat'`** → Fixed in latest version
   - **Error: `Google Cloud SDK not available`** → Install with `pip install "ray-mcp[gke]"`
   - **Error: `Not authenticated with gke`** → Ensure `gcloud auth login` is done
   - **Works in terminal but not Claude Desktop** → Install dependencies in the same Python environment

## Environment Setup

### MCP Server Environment (Important)

The MCP server runs in its own environment separate from your terminal. To ensure cloud provider functionality works in Claude Desktop, you need to:

1. **Install Python SDKs** (Required):
   ```bash
   # Install all cloud provider dependencies
   uv sync --extra all
   
   # Or install specific providers
   uv sync --extra gke  # For Google Kubernetes Engine
   uv sync --extra eks  # For Amazon EKS
   uv sync --extra aws  # For general AWS support
   ```

2. **Set up authentication** through the MCP tools:
   - Use `authenticate_cloud_provider` tool for explicit authentication
   - Or configure ambient authentication (see Authentication section)

3. **Verify setup** using the `check_environment` tool

### Authentication

**Important**: CLI tools (gcloud, aws, kubectl) are not used as fallbacks. Python SDKs must be properly installed and configured.

#### Google Cloud Platform (GKE)
```bash
# Method 1: Service Account Key (Recommended for MCP)
# Use the authenticate_cloud_provider tool with your service account JSON

# Method 2: Application Default Credentials (if available)
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
export GOOGLE_CLOUD_PROJECT="your-project-id"
```

#### Amazon Web Services (EKS)
```bash
# Method 1: Direct credentials
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-west-2"

# Method 2: Use authenticate_cloud_provider tool
```

#### Local Kubernetes
```bash
# Ensure kubeconfig exists and is properly configured
ls ~/.kube/config

# Test with kubernetes Python client
python -c "from kubernetes import client, config; config.load_kube_config(); print('Success')"
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
# Local Ray cluster
init_ray_cluster()
submit_ray_job(entrypoint="python my_script.py")
inspect_ray_cluster()

# Cloud provider workflow
detect_cloud_provider()
authenticate_cloud_provider(provider="gke", project_id="my-project")
list_kubernetes_clusters(provider="gke") 
connect_kubernetes_cluster(provider="gke", cluster_name="my-cluster", zone="us-central1-a")

# Create and manage cloud clusters
create_kubernetes_cluster(
    provider="gke",
    cluster_spec={
        "name": "ray-cluster",
        "zone": "us-central1-a", 
        "machine_type": "n1-standard-4",
        "initial_node_count": 3
    }
)
```

## Available Tools

### Unified Ray Management (Local & Kubernetes)
- `init_ray_cluster` - Initialize or connect to Ray cluster (supports both local and KubeRay)
- `stop_ray_cluster` - Stop Ray cluster or delete KubeRay cluster
- `inspect_ray_cluster` - Get cluster status and information (local and KubeRay)
- `list_ray_clusters` - List Ray clusters (both local and Kubernetes)

### Job Management (Local & KubeRay)
- `submit_ray_job` - Submit jobs to the cluster (auto-detects local vs KubeRay)
- `list_ray_jobs` - List all jobs (auto-detects local vs KubeRay)
- `inspect_ray_job` - Inspect job with logs/debug info (supports both local and KubeRay jobs)
- `cancel_ray_job` - Cancel/delete running jobs (supports both local and KubeRay jobs)
- `retrieve_logs` - Get logs with pagination and error analysis (supports both local and KubeRay jobs)

### Cloud Provider Management
- `detect_cloud_provider` - Auto-detect available cloud environments
- `authenticate_cloud_provider` - Authenticate with GKE/EKS/local clusters
- `list_kubernetes_clusters` - Discover Kubernetes clusters across cloud providers
- `connect_kubernetes_cluster` - Connect to specific Kubernetes clusters
- `create_kubernetes_cluster` - Create new GKE/EKS clusters
- `get_kubernetes_cluster_info` - Get detailed Kubernetes cluster information
- `get_cloud_provider_status` - Check authentication/connection status
- `disconnect_cloud_provider` - Disconnect from cloud providers
- `get_cloud_config_template` - Get cluster configuration templates

### Kubernetes & KubeRay
- `list_ray_clusters` - List Ray clusters (both local and Kubernetes)
- `scale_ray_cluster` - Scale Ray cluster workers (KubeRay only, local returns info)  
- `list_kuberay_jobs` - List KubeRay jobs

**Note**: Most KubeRay operations are now unified with their local counterparts:
- Use `inspect_ray_cluster` for both local clusters and KubeRay clusters
- Use `stop_ray_cluster` for both stopping local clusters and deleting KubeRay clusters  
- Use `inspect_ray_job`, `cancel_ray_job`, `retrieve_logs` for both local and KubeRay jobs

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
                                       │ │PortManager  │ │
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

## Troubleshooting

### Common Issues

1. **"Not authenticated" errors**:
   - Use `check_environment` tool to verify authentication setup
   - Ensure Python SDKs are installed: `uv sync --extra all`
   - Configure proper credentials (see Authentication section)

2. **"SDK not available" errors**:
   ```bash
   # Install missing dependencies
   uv sync --extra gke  # For GKE
   uv sync --extra eks  # For EKS
   uv sync --extra kubernetes  # For Kubernetes
   ```

3. **Environment isolation issues**:
   - MCP server runs in separate environment from terminal
   - Must install SDKs in the same Python environment as MCP server
   - Use `check_environment` tool to verify setup

4. **Cluster discovery fails**:
   - Verify authentication: `get_cloud_provider_status`
   - Check project/region configuration
   - Ensure proper permissions for cluster access

### Verification Steps

1. **Check environment**:
   ```bash
   # Use MCP tool
   check_environment
   ```

2. **Verify authentication**:
   ```bash
   # Check specific provider
   get_cloud_provider_status gke
   get_cloud_provider_status eks
   ```

3. **Test cluster operations**:
   ```bash
   # List clusters
   list_kubernetes_clusters gke
   list_kubernetes_clusters eks
   ``` 