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

### Amazon Web Services (EKS)

#### 1. Install Dependencies

```bash
uv add "ray-mcp[eks]"
```

#### 2. AWS Credentials Setup

Configure AWS credentials using one of these methods:

**Option 1: Environment Variables**
```bash
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export AWS_DEFAULT_REGION="us-west-2"
```

**Option 2: AWS Credentials File**
```bash
# Configure using AWS CLI
aws configure

# Or manually edit ~/.aws/credentials
[default]
aws_access_key_id = your_access_key
aws_secret_access_key = your_secret_key
region = us-west-2
```

**Option 3: IAM Role** (for EC2 instances)
```bash
# Attach appropriate IAM role to EC2 instance
# No additional configuration needed
```

#### 3. Required IAM Permissions

Ensure your AWS credentials have these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "eks:DescribeCluster",
        "eks:ListClusters",
        "eks:CreateCluster",
        "eks:DeleteCluster",
        "eks:DescribeNodegroup",
        "eks:ListNodegroups",
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
```

#### 4. Authentication

```bash
cloud: "authenticate with AWS region us-west-2"
```

#### 5. Common Operations

```bash
# List EKS clusters
cloud: "list all EKS clusters in us-east-1"

# Connect to cluster
cloud: "connect to EKS cluster training-cluster in region us-west-2"

# Create cluster
cloud: "create EKS cluster ml-cluster with 3 nodes"

# Get cluster info
cloud: "get info for cluster production-cluster"
```

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

### LLM Processing Configuration

**Required for natural language parsing:**
```bash
# OpenAI API key for prompt processing
export OPENAI_API_KEY="your_api_key_here"
```

**Optional LLM settings:**
```bash
# OpenAI model selection (default: gpt-3.5-turbo)
export LLM_MODEL="gpt-3.5-turbo"
```

### Core Settings

```bash
# Enhanced LLM-friendly output with suggestions
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

# Amazon Web Services
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export AWS_DEFAULT_REGION="us-west-2"

# Kubernetes
export KUBECONFIG="/path/to/kubeconfig"
```

## Troubleshooting

### Common Issues

#### LLM Processing Errors
```bash
# Verify Anthropic API key is set
echo $ANTHROPIC_API_KEY

# Test API connectivity
curl -H "Authorization: Bearer $ANTHROPIC_API_KEY" \
     -H "Content-Type: application/json" \
     https://api.anthropic.com/v1/messages
```

#### Authentication Errors
```bash
# Check GCP authentication
gcloud auth application-default login

# Verify service account
gcloud auth list

# Check AWS authentication
aws sts get-caller-identity

# Verify AWS credentials
aws configure list
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