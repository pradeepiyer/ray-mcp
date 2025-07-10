# Tools Reference

Complete reference for all Ray MCP tools available to LLM agents. This server provides unified tools that work seamlessly with both local Ray clusters and Kubernetes-based Ray clusters using the KubeRay operator.

## Unified Ray Management

These tools automatically detect and work with both local Ray clusters and KubeRay clusters on Kubernetes.

### `init_ray_cluster`

Initialize Ray cluster - create a new local cluster, connect to existing cluster, or create a Kubernetes cluster via KubeRay.

**Parameters:**
- `address` (string, optional) - Ray cluster address to connect to. If provided, connects to existing cluster
- `cluster_type` (string, optional) - Type of cluster: `"local"` (default), `"kubernetes"`, `"k8s"`
- `num_cpus` (integer, optional) - CPUs for head node (new local clusters only)
- `num_gpus` (integer, optional) - GPUs for head node (new local clusters only)
- `worker_nodes` (array, optional) - Worker configurations. Empty array `[]` for head-only cluster
- `head_node_port` (integer, optional) - Head node port (auto-selected if not specified)
- `dashboard_port` (integer, optional) - Dashboard port (auto-selected if not specified)

**KubeRay Parameters:**
- `cluster_name` (string, optional) - Name for KubeRay cluster
- `namespace` (string, optional) - Kubernetes namespace (default: `"default"`)
- `ray_version` (string, optional) - Ray version for KubeRay cluster (default: `"2.47.0"`)
- `head_node_spec` (object, optional) - Head node specification for KubeRay
- `worker_node_specs` (array, optional) - Worker node specifications for KubeRay
- `enable_ingress` (boolean, optional) - Enable ingress for KubeRay cluster
- `suspend` (boolean, optional) - Create cluster in suspended state

**KubeRay Head Node Spec:**
- `num_cpus` (integer, optional) - CPU count (default: 2)
- `num_gpus` (integer, optional) - GPU count (default: 0)
- `memory_request` (string, optional) - Memory request (default: `"4Gi"`)
- `memory_limit` (string, optional) - Memory limit (default: same as request)
- `cpu_request` (integer, optional) - CPU request (default: same as num_cpus)
- `cpu_limit` (integer, optional) - CPU limit (default: same as request)
- `image` (string, optional) - Container image (default: `"rayproject/ray:2.47.0"`)
- `service_type` (string, optional) - Service type: `"LoadBalancer"`, `"ClusterIP"`, `"NodePort"`
- `service_annotations` (object, optional) - Service annotations
- `node_selector` (object, optional) - Node selector for pod placement
- `tolerations` (array, optional) - Pod tolerations
- `env` (array, optional) - Environment variables

**KubeRay Worker Node Spec:**
- `group_name` (string, optional) - Worker group name
- `replicas` (integer, optional) - Number of replicas (default: 2)
- `min_replicas` (integer, optional) - Minimum replicas for autoscaling (default: 0)
- `max_replicas` (integer, optional) - Maximum replicas for autoscaling
- `num_cpus` (integer, optional) - CPU count (default: 2)
- `num_gpus` (integer, optional) - GPU count (default: 0)
- `gpu_type` (string, optional) - GPU type (default: `"nvidia.com/gpu"`)
- `memory_request` (string, optional) - Memory request (default: `"4Gi"`)
- `memory_limit` (string, optional) - Memory limit
- `cpu_request` (integer, optional) - CPU request
- `cpu_limit` (integer, optional) - CPU limit
- `image` (string, optional) - Container image
- `node_selector` (object, optional) - Node selector for pod placement
- `tolerations` (array, optional) - Pod tolerations
- `env` (array, optional) - Environment variables

**Examples:**

```python
# Local cluster with default settings
init_ray_cluster()

# Head-only local cluster
init_ray_cluster(worker_nodes=[])

# Connect to existing local cluster
init_ray_cluster(address="127.0.0.1:10001")

# Custom local cluster
init_ray_cluster(
    num_cpus=4,
    worker_nodes=[
        {"num_cpus": 2, "num_gpus": 1},
        {"num_cpus": 1}
    ]
)

# Create KubeRay cluster
init_ray_cluster(
    cluster_type="kubernetes",
    cluster_name="my-ray-cluster",
    namespace="ray-system",
    head_node_spec={
        "num_cpus": 4,
        "memory_request": "8Gi",
        "service_type": "LoadBalancer"
    },
    worker_node_specs=[
        {
            "group_name": "cpu-workers",
            "replicas": 3,
            "num_cpus": 2,
            "memory_request": "4Gi"
        },
        {
            "group_name": "gpu-workers", 
            "replicas": 1,
            "num_cpus": 4,
            "num_gpus": 1,
            "gpu_type": "nvidia.com/gpu"
        }
    ]
)

# Connect to existing KubeRay cluster
init_ray_cluster(
    address="10.0.1.100:8265",
    cluster_type="kubernetes",
    cluster_name="existing-cluster"
)
```

### `stop_ray_cluster`

Stop or delete a Ray cluster. Supports both local Ray clusters (stop) and KubeRay clusters (delete).

**Parameters:**
- `cluster_name` (string, optional) - Name of KubeRay cluster to delete
- `namespace` (string, optional) - Kubernetes namespace (default: `"default"`)

**Examples:**

```python
# Stop local cluster
stop_ray_cluster()

# Delete KubeRay cluster
stop_ray_cluster(
    cluster_name="my-ray-cluster",
    namespace="ray-system"
)
```

### `inspect_ray_cluster`

Get comprehensive cluster information including status, resources, and nodes.

**Parameters:**
- `cluster_name` (string, optional) - Name of KubeRay cluster to inspect
- `namespace` (string, optional) - Kubernetes namespace (default: `"default"`)

**Returns:**
- Cluster status and health
- Node information and resources
- Resource utilization
- KubeRay cluster specifications (if applicable)

### `scale_ray_cluster`

Scale Ray cluster worker nodes. Supports both local Ray clusters and KubeRay clusters.

**Parameters:**
- `cluster_name` (string, optional) - Name of KubeRay cluster to scale
- `namespace` (string, optional) - Kubernetes namespace (default: `"default"`)
- `worker_group_name` (string, optional) - Worker group name for KubeRay
- `replicas` (integer, optional) - Target number of replicas
- `min_replicas` (integer, optional) - Minimum replicas for autoscaling
- `max_replicas` (integer, optional) - Maximum replicas for autoscaling

### `list_ray_clusters`

List available Ray clusters (both local and KubeRay).

**Parameters:**
- `namespace` (string, optional) - Kubernetes namespace to search (default: `"default"`)
- `all_namespaces` (boolean, optional) - Search all namespaces (default: false)

## Job Management

These tools work with both local Ray jobs and KubeRay jobs, automatically detecting the appropriate job type.

### `submit_ray_job`

Submit a job to the Ray cluster. Supports both local clusters and KubeRay.

**Parameters:**
- `entrypoint` (string, required) - Command to execute
- `job_type` (string, optional) - Job type: `"local"`, `"kubernetes"`, `"k8s"`, `"auto"` (default)
- `runtime_env` (object, optional) - Runtime environment specification
- `job_id` (string, optional) - Custom job ID
- `metadata` (object, optional) - Job metadata

**KubeRay Job Parameters:**
- `job_name` (string, optional) - KubeRay job name
- `namespace` (string, optional) - Kubernetes namespace
- `cluster_selector` (string, optional) - Existing cluster to use
- `suspend` (boolean, optional) - Create job in suspended state
- `ttl_seconds_after_finished` (integer, optional) - TTL for cleanup (default: 86400)
- `active_deadline_seconds` (integer, optional) - Job timeout
- `backoff_limit` (integer, optional) - Retry limit (default: 0)
- `shutdown_after_job_finishes` (boolean, optional) - Shutdown cluster after job

**Runtime Environment:**
- `working_dir` (string, optional) - Working directory
- `pip` (array/object, optional) - Pip packages to install
- `conda` (array/string/object, optional) - Conda packages or environment
- `env_vars` (object, optional) - Environment variables

**Examples:**

```python
# Simple local job
submit_ray_job(entrypoint="python script.py")

# Job with runtime environment
submit_ray_job(
    entrypoint="python train_model.py",
    runtime_env={
        "pip": ["torch>=1.12", "numpy"],
        "env_vars": {"MODEL_PATH": "/data/model"}
    }
)

# KubeRay job with existing cluster
submit_ray_job(
    entrypoint="python distributed_job.py",
    job_type="kubernetes",
    job_name="training-job",
    namespace="ml-workloads",
    cluster_selector="production-cluster",
    runtime_env={
        "pip": ["transformers", "datasets"],
        "working_dir": "/workspace"
    }
)

# KubeRay job with ephemeral cluster
submit_ray_job(
    entrypoint="python batch_processing.py",
    job_type="kubernetes",
    shutdown_after_job_finishes=True,
    ttl_seconds_after_finished=3600
)
```

### `list_ray_jobs`

List all jobs in the Ray cluster.

**Parameters:**
- `namespace` (string, optional) - Kubernetes namespace (default: `"default"`)
- `all_namespaces` (boolean, optional) - Search all namespaces

### `inspect_ray_job`

Get detailed information about a specific Ray job.

**Parameters:**
- `job_id` (string, required) - Job ID to inspect
- `namespace` (string, optional) - Kubernetes namespace (default: `"default"`)
- `mode` (string, optional) - Inspection mode: `"status"`, `"logs"`, `"debug"`

### `cancel_ray_job`

Cancel a running Ray job.

**Parameters:**
- `job_id` (string, required) - Job ID to cancel
- `namespace` (string, optional) - Kubernetes namespace (default: `"default"`)

## Log Management

### `retrieve_logs`

Retrieve logs from Ray cluster components, jobs, or tasks with pagination and error analysis.

**Parameters:**
- `identifier` (string, required) - Job ID, task ID, or component name
- `log_type` (string, optional) - Log type: `"job"`, `"task"`, `"worker"`, `"system"` (default: `"job"`)
- `num_lines` (integer, optional) - Number of lines to retrieve (1-10000, default: 100)
- `include_errors` (boolean, optional) - Include error analysis (default: false)
- `max_size_mb` (integer, optional) - Maximum log size in MB (1-100, default: 10)
- `page` (integer, optional) - Page number for pagination (1-based)
- `page_size` (integer, optional) - Lines per page (10-1000, default: 100)
- `filter` (string, optional) - Filter pattern to search within logs

**Examples:**

```python
# Basic log retrieval
retrieve_logs(identifier="job_12345", num_lines=500)

# Logs with error analysis
retrieve_logs(
    identifier="job_12345",
    include_errors=True,
    max_size_mb=50
)

# Paginated log retrieval
retrieve_logs(
    identifier="job_12345",
    page=1,
    page_size=200,
    filter="ERROR"
)
```

## Cloud Provider Management

### `detect_cloud_provider`

Detect the current cloud provider environment and available authentication methods.

**Parameters:** None

**Returns:**
- Detected cloud provider
- Available authentication methods
- Provider-specific status

### `check_environment`

Check environment setup, dependencies, and authentication status.

**Parameters:**
- `provider` (string, optional) - Cloud provider: `"gke"`, `"local"`, `"all"`

### `authenticate_cloud_provider`

Authenticate with a cloud provider (GKE).

**Parameters:**
- `provider` (string, required) - Cloud provider: 'gke' for Google Kubernetes Engine
- `service_account_path` (string, optional) - Path to service account JSON file (GKE only)
- `project_id` (string, optional) - Google Cloud project ID (GKE only)
- `region` (string, optional) - Cloud provider region
- `config_file` (string, optional) - Path to configuration file
- `context` (string, optional) - Context name for configuration

**Examples:**

```python
# GKE authentication
authenticate_cloud_provider(
    provider="gke",
    service_account_path="/path/to/service-account.json",
    project_id="my-gcp-project"
)

# Local Kubernetes authentication
authenticate_cloud_provider(
    provider="local",
    config_file="~/.kube/config",
    context="minikube"
)
```

### `list_kubernetes_clusters`

List available Kubernetes clusters from cloud providers.

**Parameters:**
- `provider` (string, required) - Cloud provider: `"gke"`, `"local"`
- `project_id` (string, optional) - Google Cloud project ID (GKE)
- `zone` (string, optional) - Zone to list clusters from (GKE)

### `connect_kubernetes_cluster`

Connect to an existing Kubernetes cluster.

**Parameters:**
- `provider` (string, required) - Cloud provider: `"gke"`, `"local"`
- `cluster_name` (string, required) - Cluster name
- `zone` (string, optional) - Cluster zone (GKE)
- `project_id` (string, optional) - Google Cloud project ID (GKE)
- `context` (string, optional) - Kubernetes context name (local)

### `create_kubernetes_cluster`

Create a new managed Kubernetes cluster (currently supports GKE).

**Parameters:**
- `provider` (string, required) - Cloud provider: `"gke"`
- `cluster_spec` (object, required) - Cluster specification
- `project_id` (string, optional) - Google Cloud project ID

**GKE Cluster Spec:**
- `name` (string, required) - Cluster name
- `zone` (string, required) - Zone to create cluster in
- `node_count` (integer, optional) - Number of nodes (minimum 1, default: 3)
- `machine_type` (string, optional) - Machine type (default: `"e2-medium"`)

**Example:**

```python
create_kubernetes_cluster(
    provider="gke",
    cluster_spec={
        "name": "ray-cluster",
        "zone": "us-central1-a",
        "node_count": 4,
        "machine_type": "n1-standard-4"
    },
    project_id="my-gcp-project"
)
```

### `get_kubernetes_cluster_info`

Get detailed information about a Kubernetes cluster.

**Parameters:**
- `provider` (string, required) - Cloud provider: `"gke"`, `"local"`
- `cluster_name` (string, required) - Cluster name
- `zone` (string, optional) - Cluster zone (GKE)
- `project_id` (string, optional) - Google Cloud project ID (GKE)

### `get_cloud_provider_status`

Get current status and connection information for cloud providers.

**Parameters:**
- `provider` (string, optional) - Cloud provider: `"gke"`, `"local"`, `"all"`

### `disconnect_cloud_provider`

Disconnect from the specified cloud provider.

**Parameters:**
- `provider` (string, required) - Cloud provider: `"gke"`, `"local"`

### `get_cloud_config_template`

Get configuration templates for cloud provider setup.

**Parameters:**
- `provider` (string, required) - Cloud provider: `"gke"`, `"local"`
- `config_type` (string, optional) - Template type: `"authentication"`, `"cluster"`, `"full"` (default)

## Response Format

All tools return structured responses with:
- `status` - Success/failure indicator (`"success"` or `"error"`)
- `message` - Human-readable description
- `data` - Tool-specific response data
- `timestamp` - Operation timestamp

## Enhanced Output Mode

Set environment variable `RAY_MCP_ENHANCED_OUTPUT=true` to enable LLM-optimized response formatting with:
- Contextual summaries
- Suggested next steps
- Error analysis and recommendations
- Formatted output for better readability

## Tool Categories

- **Unified Ray Management**: Work with both local and KubeRay clusters
- **Job Management**: Submit and manage jobs across cluster types
- **Log Management**: Retrieve and analyze logs with advanced features
- **Cloud Provider Management**: Authenticate and manage cloud resources
- **KubeRay Operations**: Kubernetes-specific Ray cluster operations 