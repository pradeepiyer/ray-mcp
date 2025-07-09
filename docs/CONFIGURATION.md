# Configuration Guide

## MCP Client Configuration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ray-mcp": {
      "command": "uv",
      "args": ["run", "ray-mcp"],
      "cwd": "/path/to/ray-mcp",
      "env": {
        "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/your/service-account-key.json",
        "RAY_MCP_ENHANCED_OUTPUT": "true"
      }
    }
  }
}
```

### Alternative Command Options

```json
{
  "mcpServers": {
    "ray-mcp": {
      "command": "python",
      "args": ["-m", "ray_mcp.main"],
      "cwd": "/path/to/ray-mcp",
      "env": {
        "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/your/service-account-key.json",
        "RAY_MCP_ENHANCED_OUTPUT": "true"
      }
    }
  }
}
```

Or with direct script execution:

```json
{
  "mcpServers": {
    "ray-mcp": {
      "command": "ray-mcp",
      "args": [],
      "env": {
        "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/your/service-account-key.json"
      }
    }
  }
}
```

## Environment Variables

### Google Cloud Authentication

- `GOOGLE_APPLICATION_CREDENTIALS` - Path to Google Cloud service account JSON key file
  - **Required for GKE functionality** - Enables authentication with Google Kubernetes Engine
  - **Example**: `/path/to/your/service-account-key.json`
  - **Note**: Alternative to using `gcloud auth application-default login`

### Ray Configuration

- `RAY_DISABLE_USAGE_STATS=1` - Disable Ray usage statistics
- `RAY_ENABLE_WINDOWS_OR_OSX_CLUSTER=1` - Enable multi-node on Windows/macOS

### MCP Server Options

- `RAY_MCP_ENHANCED_OUTPUT=true` - Enable enhanced LLM-friendly output formatting
- `RAY_MCP_LOG_LEVEL=INFO` - Set logging level (DEBUG, INFO, WARNING, ERROR)

### Example Environment Setup

```bash
export RAY_DISABLE_USAGE_STATS=1
export RAY_ENABLE_WINDOWS_OR_OSX_CLUSTER=1
export RAY_MCP_ENHANCED_OUTPUT=true
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
ray-mcp
```

## Google Cloud Configuration

### Service Account Setup

To use Google Kubernetes Engine (GKE) features, you need to configure Google Cloud authentication:

#### 1. Create a Service Account

```bash
# Set your project ID
export PROJECT_ID="your-gcp-project-id"

# Create a service account
gcloud iam service-accounts create ray-mcp-service-account \
    --description="Service account for Ray MCP" \
    --display-name="Ray MCP Service Account"
```

#### 2. Grant Required Permissions

```bash
# Grant Kubernetes Engine Developer role
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:ray-mcp-service-account@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/container.developer"

# Grant Kubernetes Engine Cluster Admin role (for cluster creation)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:ray-mcp-service-account@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/container.clusterAdmin"
```

#### 3. Download Service Account Key

```bash
# Create and download the key file
gcloud iam service-accounts keys create ~/ray-mcp-key.json \
    --iam-account=ray-mcp-service-account@$PROJECT_ID.iam.gserviceaccount.com
```

### Authentication Methods

#### Option 1: Service Account Key File (Recommended for MCP)

Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/ray-mcp-key.json"
```

#### Option 2: Application Default Credentials

```bash
# Authenticate with your user account
gcloud auth application-default login

# Or use a service account
gcloud auth activate-service-account --key-file=/path/to/ray-mcp-key.json
```

### Required Google Cloud APIs

Ensure these APIs are enabled in your project:

```bash
# Enable required APIs
gcloud services enable container.googleapis.com
gcloud services enable compute.googleapis.com
```

### GKE Cluster Requirements

For Ray MCP to work with existing GKE clusters:

- **Kubernetes version**: 1.20+ (recommended: 1.24+)
- **Node resources**: At least 2 vCPUs and 4GB RAM per node
- **RBAC**: Enabled (default in GKE)
- **Workload Identity**: Recommended for production

### Verification

Test your Google Cloud configuration:

```bash
# Check authentication
gcloud auth list

# Test GKE access
gcloud container clusters list

# Verify API access
gcloud container clusters describe CLUSTER_NAME --zone=ZONE
```

## Resource Configuration

### Default Cluster Settings

- Head node: 1 CPU, 0 GPUs
- Worker nodes: 2 workers with 1 CPU each (when not specified)
- Object store memory: Ray defaults (minimum 75MB per node)

### Custom Worker Configuration

```python
# Head-node only cluster
init_ray(worker_nodes=[])

# Custom worker setup
init_ray(worker_nodes=[
    {"num_cpus": 2, "num_gpus": 1},
    {"num_cpus": 1, "object_store_memory": 1000000000}
])
```

## Logging Configuration

Ray MCP uses Python's logging module. Configure via environment or code:

```python
import logging
logging.getLogger('ray_mcp').setLevel(logging.DEBUG)
```

## Troubleshooting Configuration

### Google Cloud Authentication Issues

#### Problem: "DefaultCredentialsError" or "Could not automatically determine credentials"

**Solution 1**: Set service account key file
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json"
```

**Solution 2**: Authenticate with gcloud
```bash
gcloud auth application-default login
```

**Solution 3**: Verify service account permissions
```bash
# Check if service account has required roles
gcloud projects get-iam-policy $PROJECT_ID \
    --flatten="bindings[].members" \
    --format="table(bindings.role)" \
    --filter="bindings.members:ray-mcp-service-account@$PROJECT_ID.iam.gserviceaccount.com"
```

#### Problem: "Permission denied" when accessing GKE clusters

**Solution**: Ensure the service account has the `container.developer` or `container.clusterAdmin` role:
```bash
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:ray-mcp-service-account@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/container.developer"
```

#### Problem: "API not enabled" errors

**Solution**: Enable required Google Cloud APIs:
```bash
gcloud services enable container.googleapis.com
gcloud services enable compute.googleapis.com
```

### Port Conflicts

Ray MCP automatically finds free ports for:
- Ray head node (starts at 10001)
- Ray dashboard (starts at 8265)

### File Permissions

Ensure the MCP client can execute the ray-mcp command and access the working directory.

### Ray Installation

Verify Ray is properly installed:

```bash
python -c "import ray; print(ray.__version__)"
```

### Google Cloud SDK Installation

Verify Google Cloud SDK is properly installed:

```bash
gcloud version
python -c "import google.cloud.container_v1; print('GKE client available')"
``` 