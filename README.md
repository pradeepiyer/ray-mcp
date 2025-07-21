# Ray MCP Server

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Ray 2.47+](https://img.shields.io/badge/ray-2.47+-orange.svg)](https://docs.ray.io/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)

**Model Context Protocol (MCP) server for Ray distributed computing.** Enables LLM agents to manage Ray clusters, submit jobs, and monitor workloads through natural language prompts.

## ✨ Features

- **Single Tool**: `ray` with automatic operation detection
- **Natural Language Interface**: Single prompt parameter per tool
- **Kubernetes-Only**: Focused on KubeRay, GKE, and AWS EKS clusters
- **Intelligent Routing**: Direct cloud provider and operation detection

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
ray: "submit job with script train.py"
ray: "list all running jobs"
ray: "get logs for job raysubmit_123"

# Service operations
ray: "deploy service with inference model serve.py"
ray: "list all services"
ray: "scale service model-api to 3 replicas"

# Cloud providers
ray: "authenticate with GCP project ml-experiments"
ray: "list all GKE clusters"
ray: "authenticate with AWS region us-west-2"
ray: "list all EKS clusters"
ray: "connect to cluster production-cluster"
```

## 🎯 Tool Reference

### `ray`
Unified Ray management with automatic operation detection.

**Job Operations:**
- `"submit job with script train.py"`
- `"submit job with script train.py and 2 CPUs"`
- `"list all running jobs"`
- `"get logs for job raysubmit_123"`
- `"cancel job raysubmit_456"`

**Service Operations:**
- `"deploy service with inference model serve.py"`
- `"create service named image-classifier with model classifier.py"`
- `"list all services"`
- `"scale service model-api to 5 replicas"`
- `"get status of service inference-engine"`
- `"delete service recommendation-api"`

**Cloud Operations:**
- `"authenticate with GCP project ml-experiments"`
- `"list all GKE clusters"`
- `"authenticate with AWS region us-west-2"`
- `"list all EKS clusters"`
- `"connect to GKE cluster production-cluster"`
- `"connect to EKS cluster training-cluster in region us-west-2"`
- `"check environment setup"`
- `"create GKE cluster ml-cluster with 3 nodes"`

**Key Components:**
- **LLM Parser**: Uses OpenAI to convert natural language prompts to structured actions
- **Kubernetes Managers**: Direct operation routing to cloud providers
- **MCP Tool**: Single `ray` tool with automatic operation routing

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

- **Python**: 3.11+
- **Ray**: 2.47.0+
- **Kubernetes**: 1.20+ (for KubeRay features)

**Optional:**
- **Google Cloud SDK**: For GKE integration
- **AWS SDK**: For EKS integration
- **kubectl**: For Kubernetes management

## 📚 Examples

Common usage patterns for Ray MCP Server (Kubernetes-only).

### Job Operations

#### Submit and Manage Jobs

```bash
# Submit a job
ray: "submit job with script train.py"

# Submit job with resources
ray: "submit job with script train.py requiring 2 CPUs and 1 GPU"

# Submit job with runtime environment
ray: "submit job with script train.py and pip packages pandas numpy"

# List jobs
ray: "list all running jobs"
ray: "list jobs in namespace production"

# Get job status and logs
ray: "get status for job raysubmit_123"
ray: "get logs for job raysubmit_123"

# Cancel job
ray: "cancel job raysubmit_123"
```

### Service Operations

#### Deploy and Manage Services

```bash
# Deploy a service
ray: "deploy service with inference model serve.py"

# Deploy named service
ray: "create service named image-classifier with model classifier.py"

# List services
ray: "list all services"
ray: "list services in namespace production"

# Manage services
ray: "get status of service image-classifier"
ray: "scale service model-api to 5 replicas"
ray: "get logs for service text-analyzer"
ray: "delete service old-model-service"
```

### Cloud Operations

#### Authentication

```bash
# Google Cloud (GKE)
ray: "authenticate with GCP project ml-experiments"
ray: "authenticate with GCP"

# Amazon Web Services (EKS)
ray: "authenticate with AWS region us-west-2"
ray: "authenticate with AWS"

# Azure (AKS)
ray: "authenticate with Azure"
```

#### Cluster Discovery and Management

```bash
# List clusters
ray: "list all GKE clusters"
ray: "list all EKS clusters"
ray: "list all AKS clusters"

# Connect to clusters
ray: "connect to GKE cluster production-cluster in us-west1-c"
ray: "connect to EKS cluster training-cluster in us-west-2"
ray: "connect to AKS cluster ml-cluster in eastus2"

# Check environment
ray: "check environment setup"
```

### Workflow Examples

#### Development Workflow

```bash
# 1. Authenticate
ray: "authenticate with GCP project my-ml-project"

# 2. Connect to cluster
ray: "connect to cluster dev-cluster in us-central1-a"

# 3. Submit test job
ray: "submit job with script test_model.py"

# 4. Check results
ray: "get logs for job raysubmit_123"
```

#### Production Deployment

```bash
# 1. Connect to production cluster
ray: "connect to cluster production-cluster in us-west1-c"

# 2. Deploy service
ray: "create service named prod-inference with model production_model.py in namespace production"

# 3. Scale for load
ray: "scale service prod-inference to 10 replicas"

# 4. Monitor
ray: "get status of service prod-inference"
```

#### Batch Processing

```bash
# 1. Connect to compute cluster
ray: "connect to cluster batch-cluster"

# 2. Submit batch job
ray: "submit job with script batch_processing.py requiring 8 CPUs"

# 3. Monitor progress
ray: "get status for job batch-processing-job"

# 4. Get results
ray: "get logs for job batch-processing-job"
```

### Advanced Examples

#### Multi-Environment Setup

```bash
# Development
ray: "authenticate with GCP project dev-project"
ray: "connect to cluster dev-cluster"
ray: "submit job with script experiment.py"

# Staging
ray: "authenticate with AWS region us-east-1"
ray: "connect to cluster staging-cluster"
ray: "submit job with script validation.py"

# Production
ray: "authenticate with GCP project prod-project"
ray: "connect to cluster prod-cluster"
ray: "deploy service with model final_model.py"
```

#### Resource-Specific Operations

```bash
# CPU-intensive job
ray: "submit job with script data_processing.py requiring 4 CPUs"

# GPU training job
ray: "submit job with script gpu_training.py requiring 2 GPUs"

# Mixed workload
ray: "submit job with script hybrid_task.py requiring 2 CPUs and 1 GPU"
```

#### Error Handling and Debugging

```bash
# Check cluster status
ray: "check environment setup"

# Get detailed logs
ray: "get error logs for job raysubmit_456"

# List failed jobs
ray: "list failed jobs"

# Restart failed job
ray: "cancel job raysubmit_456"
ray: "submit job with script fixed_model.py"
```

## 📄 License

Licensed under the [Apache License 2.0](LICENSE).
