# Ray MCP Examples

Comprehensive examples demonstrating Ray MCP capabilities across local and Kubernetes environments.

## Quick Start Examples

### Basic Local Ray Cluster

```python
# Start a local Ray cluster
init_ray_cluster()

# Submit a simple job
submit_ray_job(entrypoint="python examples/simple_job.py")

# Check job status
list_ray_jobs()

# Get cluster information
inspect_ray_cluster()

# Stop the cluster
stop_ray_cluster()
```

### Head-Only Local Cluster

```python
# Start head-only cluster (no worker nodes)
init_ray_cluster(worker_nodes=[])

# Submit a job that runs on the head node
submit_ray_job(
    entrypoint="python cpu_task.py",
    runtime_env={"pip": ["numpy", "pandas"]}
)
```

### Custom Local Cluster

```python
# Create cluster with custom resource configuration
init_ray_cluster(
    num_cpus=8,
    num_gpus=2,
    worker_nodes=[
        {"num_cpus": 4, "num_gpus": 1},
        {"num_cpus": 2, "num_gpus": 0},
        {"num_cpus": 4, "num_gpus": 1}
    ]
)

# Submit job with runtime environment
submit_ray_job(
    entrypoint="python distributed_training.py",
    runtime_env={
        "pip": ["torch>=1.12", "transformers", "datasets"],
        "env_vars": {
            "CUDA_VISIBLE_DEVICES": "0,1",
            "MODEL_PATH": "/data/models"
        }
    },
    metadata={"project": "ml-training", "user": "data-scientist"}
)
```

## KubeRay Examples

### Basic KubeRay Cluster

```python
# Create a basic KubeRay cluster
init_ray_cluster(
    cluster_type="kubernetes",
    cluster_name="basic-ray-cluster",
    namespace="ray-system"
)

# Submit a job to the KubeRay cluster
submit_ray_job(
    entrypoint="python distributed_job.py",
    job_type="kubernetes",
    namespace="ray-system"
)

# Scale the cluster
scale_ray_cluster(
    cluster_name="basic-ray-cluster",
    namespace="ray-system",
    worker_group_name="worker-group",
    replicas=5
)
```

### Advanced KubeRay Cluster with GPU Support

```python
# Create KubeRay cluster with multiple worker groups
init_ray_cluster(
    cluster_type="kubernetes",
    cluster_name="gpu-ray-cluster",
    namespace="ml-workloads",
    ray_version="2.47.0",
    head_node_spec={
        "num_cpus": 4,
        "memory_request": "8Gi",
        "memory_limit": "16Gi",
        "service_type": "LoadBalancer",
        "service_annotations": {
            "cloud.google.com/load-balancer-type": "External"
        }
    },
    worker_node_specs=[
        {
            "group_name": "cpu-workers",
            "replicas": 3,
            "min_replicas": 1,
            "max_replicas": 10,
            "num_cpus": 4,
            "memory_request": "8Gi",
            "memory_limit": "16Gi",
            "node_selector": {
                "workload-type": "cpu-intensive"
            }
        },
        {
            "group_name": "gpu-workers",
            "replicas": 2,
            "min_replicas": 0,
            "max_replicas": 5,
            "num_cpus": 8,
            "num_gpus": 2,
            "gpu_type": "nvidia.com/gpu",
            "memory_request": "16Gi",
            "memory_limit": "32Gi",
            "node_selector": {
                "accelerator": "nvidia-tesla-v100"
            },
            "tolerations": [
                {
                    "key": "nvidia.com/gpu",
                    "operator": "Equal",
                    "value": "true",
                    "effect": "NoSchedule"
                }
            ]
        }
    ]
)

# Submit GPU training job
submit_ray_job(
    entrypoint="python gpu_training.py --gpus 2",
    job_type="kubernetes",
    job_name="gpu-training-job",
    namespace="ml-workloads",
    cluster_selector="gpu-ray-cluster",
    runtime_env={
        "pip": ["torch>=1.12", "torchvision", "transformers"],
        "env_vars": {
            "CUDA_VISIBLE_DEVICES": "0,1",
            "PYTORCH_CUDA_ALLOC_CONF": "max_split_size_mb:128"
        }
    }
)
```

### KubeRay Job with Ephemeral Cluster

```python
# Submit job that creates its own temporary cluster
submit_ray_job(
    entrypoint="python batch_processing.py --input /data/input",
    job_type="kubernetes",
    job_name="batch-processing-job",
    namespace="batch-jobs",
    shutdown_after_job_finishes=True,
    ttl_seconds_after_finished=3600,  # Clean up after 1 hour
    runtime_env={
        "pip": ["pandas", "numpy", "scikit-learn"],
        "working_dir": "/workspace",
        "env_vars": {
            "DATA_PATH": "/data",
            "OUTPUT_PATH": "/output"
        }
    }
)
```

### Production KubeRay Cluster with Monitoring

```python
# Create production cluster with monitoring and ingress
init_ray_cluster(
    cluster_type="kubernetes",
    cluster_name="production-ray-cluster",
    namespace="production",
    enable_ingress=True,
    head_node_spec={
        "num_cpus": 8,
        "memory_request": "16Gi",
        "service_type": "LoadBalancer",
        "service_annotations": {
            "cloud.google.com/load-balancer-type": "External",
            "prometheus.io/scrape": "true",
            "prometheus.io/port": "8080"
        },
        "env": [
            {"name": "RAY_ENABLE_RECORD_STATS", "value": "true"},
            {"name": "RAY_GRAFANA_IFRAME_HOST", "value": "grafana.company.com"}
        ]
    },
    worker_node_specs=[
        {
            "group_name": "standard-workers",
            "replicas": 5,
            "min_replicas": 2,
            "max_replicas": 20,
            "num_cpus": 4,
            "memory_request": "8Gi",
            "env": [
                {"name": "RAY_ENABLE_RECORD_STATS", "value": "true"}
            ]
        }
    ]
)

# Connect to existing production cluster
init_ray_cluster(
    address="production-ray-cluster.production.svc.cluster.local:8265",
    cluster_type="kubernetes",
    cluster_name="production-ray-cluster"
)
```

## Cloud Provider Examples

### GKE Setup and Usage

```python
# Detect cloud environment
detect_cloud_provider()

# Authenticate with GKE
authenticate_cloud_provider(
    provider="gke",
    service_account_path="/path/to/service-account.json",
    project_id="my-gcp-project"
)

# List available GKE clusters
list_kubernetes_clusters(
    provider="gke",
    project_id="my-gcp-project"
)

# Create a new GKE cluster
create_kubernetes_cluster(
    provider="gke",
    cluster_spec={
        "name": "ray-gke-cluster",
        "zone": "us-central1-a",
        "node_count": 4,
        "machine_type": "n1-standard-4"
    },
    project_id="my-gcp-project"
)

# Connect to the GKE cluster
connect_kubernetes_cluster(
    provider="gke",
    cluster_name="ray-gke-cluster",
    zone="us-central1-a",
    project_id="my-gcp-project"
)

# Create KubeRay cluster on GKE
init_ray_cluster(
    cluster_type="kubernetes",
    cluster_name="ray-on-gke",
    namespace="ray-system",
    head_node_spec={
        "service_type": "LoadBalancer",
        "node_selector": {
            "cloud.google.com/gke-nodepool": "ray-nodes"
        }
    }
)
```

### Local Kubernetes Setup

```python
# Check local Kubernetes environment
check_environment(provider="local")

# Authenticate with local cluster
authenticate_cloud_provider(
    provider="local",
    config_file="~/.kube/config",
    context="minikube"
)

# List local clusters
list_kubernetes_clusters(provider="local")

# Connect to local cluster
connect_kubernetes_cluster(
    provider="local",
    cluster_name="minikube",
    context="minikube"
)
```

### Multi-Cloud Workflow

```python
# Check all available providers
check_environment(provider="all")

# Get cloud provider status
get_cloud_provider_status(provider="all")

# Switch between providers
disconnect_cloud_provider(provider="gke")
authenticate_cloud_provider(provider="local")

# Get configuration templates
get_cloud_config_template(
    provider="gke",
    config_type="authentication"
)
```

## Advanced Job Management

### Job with Complex Runtime Environment

```python
submit_ray_job(
    entrypoint="python complex_pipeline.py",
    runtime_env={
        "pip": [
            "torch>=1.12",
            "transformers>=4.20",
            "datasets>=2.0",
            "wandb>=0.12"
        ],
        "conda": {
            "name": "ml-env",
            "channels": ["conda-forge", "pytorch"],
            "dependencies": [
                "python=3.9",
                "cudatoolkit=11.7",
                "pytorch::pytorch",
                "pytorch::torchvision"
            ]
        },
        "env_vars": {
            "WANDB_PROJECT": "ray-experiments",
            "CUDA_VISIBLE_DEVICES": "0,1,2,3",
            "OMP_NUM_THREADS": "4",
            "MKL_NUM_THREADS": "4"
        },
        "working_dir": "/workspace/ml-project"
    },
    metadata={
        "experiment_name": "large_model_training",
        "model_type": "transformer",
        "dataset": "custom_dataset_v2"
    }
)
```

### Job Monitoring and Debugging

```python
# Submit job with debugging enabled
job_result = submit_ray_job(
    entrypoint="python debug_job.py",
    job_id="debug-job-001"
)

# Monitor job progress
inspect_ray_job(job_id="debug-job-001", mode="status")

# Get job logs with error analysis
retrieve_logs(
    identifier="debug-job-001",
    include_errors=True,
    max_size_mb=100
)

# Get paginated logs
retrieve_logs(
    identifier="debug-job-001",
    page=1,
    page_size=500,
    filter="ERROR"
)

# Get detailed debugging information
inspect_ray_job(job_id="debug-job-001", mode="debug")
```

### Batch Job Processing

```python
# Submit multiple jobs for batch processing
job_ids = []

for i in range(10):
    result = submit_ray_job(
        entrypoint=f"python process_batch.py --batch-id {i}",
        job_id=f"batch-job-{i:03d}",
        runtime_env={
            "pip": ["pandas", "numpy"],
            "env_vars": {
                "BATCH_ID": str(i),
                "INPUT_PATH": f"/data/batch_{i}",
                "OUTPUT_PATH": f"/output/batch_{i}"
            }
        }
    )
    job_ids.append(result.get("job_id"))

# Monitor all jobs
for job_id in job_ids:
    inspect_ray_job(job_id=job_id, mode="status")
```

## Log Management Examples

### Basic Log Retrieval

```python
# Get recent job logs
retrieve_logs(
    identifier="job_abc123",
    num_lines=1000
)

# Get logs with error analysis
retrieve_logs(
    identifier="job_abc123",
    include_errors=True,
    max_size_mb=50
)
```

### Advanced Log Analysis

```python
# Get system logs
retrieve_logs(
    identifier="ray-head-node",
    log_type="system",
    filter="ERROR|WARN",
    num_lines=5000
)

# Get worker logs
retrieve_logs(
    identifier="worker-group-1",
    log_type="worker",
    page=1,
    page_size=1000,
    include_errors=True
)

# Get task-specific logs
retrieve_logs(
    identifier="task_456789",
    log_type="task",
    filter="completed|failed",
    num_lines=500
)
```

## Cluster Management Examples

### Cluster Scaling

```python
# Scale up cluster
scale_ray_cluster(
    cluster_name="production-cluster",
    namespace="production",
    worker_group_name="cpu-workers",
    replicas=10,
    min_replicas=5,
    max_replicas=15
)

# Scale down cluster
scale_ray_cluster(
    cluster_name="production-cluster",
    namespace="production",
    worker_group_name="cpu-workers",
    replicas=3
)
```

### Cluster Monitoring

```python
# List all clusters
list_ray_clusters(all_namespaces=True)

# Get detailed cluster info
inspect_ray_cluster(
    cluster_name="production-cluster",
    namespace="production"
)

# Check cluster health across namespaces
for namespace in ["production", "staging", "development"]:
    cluster_info = inspect_ray_cluster(namespace=namespace)
    print(f"Cluster health in {namespace}: {cluster_info}")
```

## Complete Workflows

### ML Training Pipeline

```python
# 1. Set up GKE environment
authenticate_cloud_provider(
    provider="gke",
    service_account_path="/path/to/service-account.json",
    project_id="ml-project"
)

# 2. Create training cluster
init_ray_cluster(
    cluster_type="kubernetes",
    cluster_name="ml-training-cluster",
    namespace="ml-workloads",
    head_node_spec={
        "num_cpus": 8,
        "memory_request": "16Gi",
        "service_type": "LoadBalancer"
    },
    worker_node_specs=[
        {
            "group_name": "gpu-workers",
            "replicas": 4,
            "num_cpus": 8,
            "num_gpus": 2,
            "memory_request": "32Gi"
        }
    ]
)

# 3. Submit training job
training_job = submit_ray_job(
    entrypoint="python train_model.py --config config.yaml",
    job_type="kubernetes",
    job_name="model-training",
    namespace="ml-workloads",
    cluster_selector="ml-training-cluster",
    runtime_env={
        "pip": ["torch", "transformers", "datasets", "wandb"],
        "working_dir": "/workspace/ml-project"
    }
)

# 4. Monitor training progress
inspect_ray_job(job_id=training_job["job_id"], mode="debug")

# 5. Clean up after training
stop_ray_cluster(
    cluster_name="ml-training-cluster",
    namespace="ml-workloads"
)
```

### Batch Processing Pipeline

```python
# 1. Create ephemeral cluster for batch processing
batch_job = submit_ray_job(
    entrypoint="python batch_processor.py --input-path /data/input",
    job_type="kubernetes",
    job_name="batch-processing",
    namespace="batch-jobs",
    shutdown_after_job_finishes=True,
    ttl_seconds_after_finished=7200,  # 2 hours
    runtime_env={
        "pip": ["pandas", "numpy", "dask"],
        "env_vars": {
            "BATCH_SIZE": "1000",
            "PARALLEL_WORKERS": "8"
        }
    }
)

# 2. Monitor batch processing
while True:
    status = inspect_ray_job(job_id=batch_job["job_id"])
    if status["data"]["status"] in ["SUCCEEDED", "FAILED"]:
        break
    time.sleep(30)

# 3. Get processing results
retrieve_logs(
    identifier=batch_job["job_id"],
    include_errors=True,
    filter="processed|completed"
)
```

### Development and Testing

```python
# 1. Start local development cluster
init_ray_cluster(
    num_cpus=4,
    worker_nodes=[{"num_cpus": 2}]
)

# 2. Test job locally
test_job = submit_ray_job(
    entrypoint="python test_job.py",
    runtime_env={
        "pip": ["pytest", "mock"],
        "working_dir": "./tests"
    }
)

# 3. Debug if needed
if test_job["status"] != "SUCCEEDED":
    retrieve_logs(
        identifier=test_job["job_id"],
        include_errors=True,
        mode="debug"
    )

# 4. Deploy to staging
authenticate_cloud_provider(provider="gke")
init_ray_cluster(
    cluster_type="kubernetes",
    cluster_name="staging-cluster",
    namespace="staging"
)

# 5. Run staging tests
staging_job = submit_ray_job(
    entrypoint="python integration_tests.py",
    job_type="kubernetes",
    namespace="staging"
)
```

## Best Practices

### Resource Management

```python
# Use appropriate resource requests and limits
init_ray_cluster(
    cluster_type="kubernetes",
    head_node_spec={
        "cpu_request": 2,
        "cpu_limit": 4,
        "memory_request": "4Gi",
        "memory_limit": "8Gi"
    },
    worker_node_specs=[
        {
            "replicas": 3,
            "cpu_request": 1,
            "cpu_limit": 2,
            "memory_request": "2Gi",
            "memory_limit": "4Gi",
            "min_replicas": 1,
            "max_replicas": 10
        }
    ]
)
```

### Job Lifecycle Management

```python
# Use meaningful job names and metadata
submit_ray_job(
    entrypoint="python job.py",
    job_id="ml-training-experiment-001",
    metadata={
        "experiment_id": "exp_001",
        "model_version": "v1.2",
        "dataset": "training_set_v3",
        "owner": "ml-team"
    }
)

# Set appropriate TTL for cleanup
submit_ray_job(
    entrypoint="python batch_job.py",
    job_type="kubernetes",
    shutdown_after_job_finishes=True,
    ttl_seconds_after_finished=3600,  # 1 hour cleanup
    active_deadline_seconds=7200      # 2 hour timeout
)
```

### Error Handling and Monitoring

```python
# Always check job status
job_result = submit_ray_job(entrypoint="python job.py")

if job_result["status"] == "success":
    job_id = job_result["job_id"]
    
    # Monitor job completion
    while True:
        status = inspect_ray_job(job_id=job_id)
        if status["data"]["status"] in ["SUCCEEDED", "FAILED"]:
            break
        time.sleep(10)
    
    # Get logs if job failed
    if status["data"]["status"] == "FAILED":
        retrieve_logs(
            identifier=job_id,
            include_errors=True,
            max_size_mb=100
        )
```

These examples demonstrate the full capabilities of Ray MCP across local and Kubernetes environments, showcasing unified tools, cloud provider integration, and comprehensive job management features.