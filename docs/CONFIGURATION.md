# Configuration Guide

This guide covers MCP client configuration, cloud provider setup, and environment configuration for Ray MCP.

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
        "RAY_MCP_ENHANCED_OUTPUT": "true",
        "GOOGLE_CLOUD_PROJECT": "your-gcp-project-id"
      }
    }
  }
}
```

### Alternative Command Options

#### Using Python Module

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

#### Using Direct Script Execution

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

## Cloud Provider Setup

### Google Kubernetes Engine (GKE)

#### Prerequisites

1. **Install Dependencies**
   ```bash
   # Install GKE dependencies
   uv add "ray-mcp[gke]"
   # or
   pip install "ray-mcp[gke]"
   ```

2. **Google Cloud Project Setup**
   - Enable required APIs in your Google Cloud project:
     - Kubernetes Engine API
     - Container Registry API (if using custom images)
     - Compute Engine API

#### Authentication Methods

##### Method 1: Service Account Key (Recommended for MCP)

1. **Create Service Account**
   ```bash
   # Create service account
   gcloud iam service-accounts create ray-mcp-service \
       --display-name="Ray MCP Service Account"
   
   # Grant necessary roles
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
       --member="serviceAccount:ray-mcp-service@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
       --role="roles/container.admin"
   
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
       --member="serviceAccount:ray-mcp-service@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
       --role="roles/compute.viewer"
   
   # Create and download key
   gcloud iam service-accounts keys create ~/ray-mcp-service-key.json \
       --iam-account=ray-mcp-service@YOUR_PROJECT_ID.iam.gserviceaccount.com
   ```

2. **Configure Environment**
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="$HOME/ray-mcp-service-key.json"
   export GOOGLE_CLOUD_PROJECT="YOUR_PROJECT_ID"
   ```

3. **Authenticate via MCP Tools**
   ```python
   # Authenticate with GKE
   authenticate_cloud_provider(
       provider="gke",
       service_account_path="/home/user/ray-mcp-service-key.json",
       project_id="your-gcp-project"
   )
   ```

##### Method 2: Application Default Credentials

1. **Set up ADC**
   ```bash
   gcloud auth application-default login
   gcloud config set project YOUR_PROJECT_ID
   ```

2. **Configure Environment**
   ```bash
   export GOOGLE_CLOUD_PROJECT="YOUR_PROJECT_ID"
   ```

#### GKE Cluster Management

##### Creating a GKE Cluster for Ray

```python
# Create GKE cluster optimized for Ray workloads
create_kubernetes_cluster(
    provider="gke",
    cluster_spec={
        "name": "ray-cluster",
        "zone": "us-central1-a",
        "node_count": 4,
        "machine_type": "n1-standard-4"
    },
    project_id="your-gcp-project"
)
```

##### Connecting to Existing GKE Cluster

```python
# List available clusters
list_kubernetes_clusters(
    provider="gke",
    project_id="your-gcp-project"
)

# Connect to specific cluster
connect_kubernetes_cluster(
    provider="gke",
    cluster_name="existing-cluster",
    zone="us-central1-a",
    project_id="your-gcp-project"
)
```

##### KubeRay with Node Affinity

```python
# Create KubeRay cluster with node affinity
init_ray_cluster(
    cluster_type="kubernetes",
    cluster_name="ray-gke-cluster",
    namespace="ray-system",
    head_node_spec={
        "num_cpus": 4,
        "memory_request": "8Gi",
        "service_type": "LoadBalancer",
        "node_selector": {
            "ray-node-type": "head"
        },
        "tolerations": [
            {
                "key": "ray-node-type",
                "operator": "Equal",
                "value": "head",
                "effect": "NoSchedule"
            }
        ]
    },
    worker_node_specs=[
        {
            "group_name": "cpu-workers",
            "replicas": 3,
            "num_cpus": 8,
            "memory_request": "16Gi",
            "node_selector": {
                "ray-node-type": "worker"
            }
        },
        {
            "group_name": "gpu-workers",
            "replicas": 0,
            "min_replicas": 0,
            "max_replicas": 5,
            "num_cpus": 4,
            "num_gpus": 1,
            "memory_request": "16Gi",
            "node_selector": {
                "ray-node-type": "gpu-worker"
            }
        }
    ]
)
```

#### Installing KubeRay Operator

```bash
# Install KubeRay operator
kubectl create namespace kuberay-system
kubectl apply -f https://raw.githubusercontent.com/ray-project/kuberay/release-0.8/ray-operator/config/crd/bases/ray.io_rayclusters.yaml
kubectl apply -f https://raw.githubusercontent.com/ray-project/kuberay/release-0.8/ray-operator/config/crd/bases/ray.io_rayjobs.yaml
kubectl apply -f https://raw.githubusercontent.com/ray-project/kuberay/release-0.8/ray-operator/config/crd/bases/ray.io_rayservices.yaml
kubectl apply -f https://raw.githubusercontent.com/ray-project/kuberay/release-0.8/deploy/kuberay-operator.yaml
```

### 8. Environment Variables

#### Universal Settings
- `RAY_MCP_LOG_LEVEL` - Log level: DEBUG, INFO, WARNING, ERROR (default: INFO)
- `RAY_MCP_ENHANCED_OUTPUT` - Enable enhanced output for tools (default: false)

#### Google Cloud Platform (GKE)
- `GOOGLE_APPLICATION_CREDENTIALS` - Path to service account JSON
- `GOOGLE_CLOUD_PROJECT` - Default project ID
- `GOOGLE_CLOUD_ZONE` - Default zone/region

## Example Environment Setup

### Development Environment

```bash
# Basic development setup
export RAY_DISABLE_USAGE_STATS=1
export RAY_MCP_ENHANCED_OUTPUT=true
export RAY_MCP_LOG_LEVEL=INFO

# Local Kubernetes
export KUBECONFIG="$HOME/.kube/config"

# Start Ray MCP
ray-mcp
```

### Production Environment with GKE

```bash
# Production GKE setup
export GOOGLE_APPLICATION_CREDENTIALS="/etc/ray-mcp/service-account.json"
export GOOGLE_CLOUD_PROJECT="production-project"
export GOOGLE_CLOUD_REGION="us-central1"
export GOOGLE_CLOUD_ZONE="us-central1-a"

export RAY_DISABLE_USAGE_STATS=1
export RAY_MCP_ENHANCED_OUTPUT=false
export RAY_MCP_LOG_LEVEL=WARNING

# Start Ray MCP
ray-mcp
```
