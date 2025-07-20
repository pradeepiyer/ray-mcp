# Ray MCP Server

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Ray 2.47+](https://img.shields.io/badge/ray-2.47+-orange.svg)](https://docs.ray.io/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)

**Model Context Protocol (MCP) server for Ray distributed computing.** Enables LLM agents to manage Ray clusters, submit jobs, and monitor workloads through natural language prompts.

## ✨ Features

- **3 Simple Tools**: `ray_job`, `ray_service`, `ray_cloud`
- **Natural Language Interface**: Single prompt parameter per tool
- **Unified Management**: Works with local Ray, KubeRay, GKE, and AWS EKS
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

# Job operations
ray_job: "submit job with script train.py"
ray_job: "list all running jobs"
ray_job: "get logs for job raysubmit_123"

# Service operations
ray_service: "deploy service with inference model serve.py"
ray_service: "list all services"
ray_service: "scale service model-api to 3 replicas"

# Cloud providers
ray_cloud: "authenticate with GCP project ml-experiments"
ray_cloud: "list all GKE clusters"
ray_cloud: "authenticate with AWS region us-west-2"
ray_cloud: "list all EKS clusters"
ray_cloud: "connect to cluster production-cluster"
```

## 🎯 Tool Reference


### `ray_job`
Submit and manage Ray jobs.

**Examples:**
- `"submit job with script train.py"`
- `"submit job with script train.py and 2 CPUs"`
- `"list all running jobs"`
- `"get logs for job raysubmit_123"`
- `"cancel job raysubmit_456"`
- `"create Ray job with training script on kubernetes"`

### `ray_service`
Deploy and manage Ray services for long-running inference and serving.

**Examples:**
- `"deploy service with inference model serve.py"`
- `"create service named image-classifier with model classifier.py"`
- `"list all services"`
- `"scale service model-api to 5 replicas"`
- `"get status of service inference-engine"`
- `"delete service recommendation-api"`

### `ray_cloud`
Manage cloud providers and authentication.

**Examples:**
- `"authenticate with GCP project ml-experiments"`
- `"list all GKE clusters"`
- `"authenticate with AWS region us-west-2"`
- `"list all EKS clusters"`
- `"connect to GKE cluster production-cluster"`
- `"connect to EKS cluster training-cluster in region us-west-2"`
- `"check ray_cloud environment setup"`
- `"create GKE cluster ml-cluster with 3 nodes"`
-  "create EKS cluster ml-cluster with 3 nodes"

**Key Components:**
- **LLM Parser**: Uses Anthropic Claude to convert natural language prompts to structured actions
- **ActionParser**: Processes parsed prompts into Ray operations  
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

#### Amazon Web Services (EKS)
```bash
# Install with EKS support
uv add "ray-mcp[eks]"

# Set up authentication
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export AWS_DEFAULT_REGION="us-west-2"
```

#### Local Kubernetes
```bash
# Install KubeRay operator
kubectl apply -f https://raw.githubusercontent.com/ray-project/kuberay/release-0.8/deploy/kuberay-operator.yaml
```

### Environment Variables

```bash
# LLM Processing Configuration (Required)
export OPENAI_API_KEY="your_api_key_here"       # Required for natural language parsing

# LLM Processing Configuration (Optional)
export LLM_MODEL="gpt-3.5-turbo"                # OpenAI model for prompt processing

# Output and Logging
export RAY_MCP_ENHANCED_OUTPUT=true             # Enhanced LLM-friendly responses
export RAY_MCP_LOG_LEVEL=INFO                   # Logging level (DEBUG, INFO, WARNING, ERROR)

# Ray Configuration
export RAY_DISABLE_USAGE_STATS=1                # Disable Ray usage statistics
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
- **AWS SDK**: For EKS integration
- **kubectl**: For Kubernetes management

## 📄 License

Licensed under the [Apache License 2.0](LICENSE).
