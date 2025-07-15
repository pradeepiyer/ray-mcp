# Configuration Guide

This guide covers authentication and setup for Ray MCP Server with different environments.

**Note:** Ray MCP Server uses native Kubernetes and Google Cloud APIs internally. The `kubectl` and `gcloud` commands shown in this guide are for initial setup and troubleshooting only.

## MCP Client Configuration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

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

### Other MCP Clients

```json
{
  "name": "ray-mcp",
  "command": "uv",
  "args": ["run", "ray-mcp"],
  "cwd": "/path/to/ray-mcp"
}
```

## Cloud Provider Setup

### Google Cloud (GKE)

#### 1. Install Dependencies

```bash
uv add "ray-mcp[gke]"
```

#### 2. Service Account Setup

Create a service account with required permissions:

```bash
# Create service account
gcloud iam service-accounts create ray-mcp-sa \
  --display-name="Ray MCP Service Account"

# Grant permissions
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:ray-mcp-sa@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/container.admin"

# Create key
gcloud iam service-accounts keys create ~/ray-mcp-key.json \
  --iam-account=ray-mcp-sa@PROJECT_ID.iam.gserviceaccount.com
```

#### 3. Environment Variables

```bash
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/ray-mcp-key.json"
export GOOGLE_CLOUD_PROJECT="your-project-id"
```

#### 4. Authentication

```bash
cloud: "authenticate with GCP project your-project-id"
```

### Local Kubernetes

#### 1. Install KubeRay Operator

```bash
kubectl apply -f https://raw.githubusercontent.com/ray-project/kuberay/release-0.8/deploy/kuberay-operator.yaml
```

#### 2. Verify Installation

```bash
kubectl get pods -n kuberay-system
```

#### 3. Authentication

```bash
cloud: "authenticate with local kubernetes"
```

## Environment Variables

### Core Settings

```bash
# Enhanced LLM-friendly output
export RAY_MCP_ENHANCED_OUTPUT=true

# Disable Ray usage statistics
export RAY_DISABLE_USAGE_STATS=1

# Set logging level (DEBUG, INFO, WARNING, ERROR)
export RAY_MCP_LOG_LEVEL=INFO
```

### Authentication

```bash
# Google Cloud
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
export GOOGLE_CLOUD_PROJECT="your-project-id"

# Kubernetes
export KUBECONFIG="/path/to/kubeconfig"
```

## Troubleshooting

### Common Issues

#### Authentication Errors
```bash
# Check GCP authentication
gcloud auth application-default login

# Verify service account
gcloud auth list
```

#### KubeRay Issues
```bash
# Check operator status
kubectl get pods -n kuberay-system

# View operator logs
kubectl logs -n kuberay-system -l app.kubernetes.io/name=kuberay-operator
```

#### Connection Problems
```bash
# Test cluster connectivity
kubectl cluster-info

# Check Ray cluster status
kubectl get rayclusters -A
```

### Debug Mode

Enable debug logging:

```bash
export RAY_MCP_LOG_LEVEL=DEBUG
```

Then restart the MCP server and check logs for detailed information.