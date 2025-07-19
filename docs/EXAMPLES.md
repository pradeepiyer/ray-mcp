# Examples

Common usage patterns and examples for Ray MCP Server.

## Basic Local Ray

### Create and Use Local Cluster

```bash
# Create local cluster
ray_cluster: "create a local cluster with 4 CPUs"

# Submit a job
ray_job: "submit job with script train.py"

# Check job status
ray_job: "list all running jobs"

# Get job logs
ray_job: "get logs for job raysubmit_123"

# Stop cluster
ray_cluster: "stop the current cluster"
```

### Head-Only Cluster

```bash
# Create head-only cluster (no workers)
ray_cluster: "create head-only cluster"

# Submit job to head node
ray_job: "submit job with script lightweight_task.py"
```

### Connect to Existing Cluster

```bash
# Connect to existing Ray cluster
ray_cluster: "connect to cluster at 192.168.1.100:10001"

# Use the cluster
ray_job: "list all running jobs"
```

## Kubernetes and KubeRay

### Create KubeRay Cluster

```bash
# Simple KubeRay cluster
ray_cluster: "create Ray cluster named ml-cluster with 3 workers on kubernetes"

# Submit job
ray_job: "submit job with script distributed_training.py on kubernetes"

# Check cluster status
ray_cluster: "inspect cluster status"
```

### Advanced KubeRay Configuration

```bash
# Create cluster with specific resources
ray_cluster: "create Ray cluster named gpu-cluster with 2 CPU workers and 1 GPU worker on kubernetes"

# Submit job with resource requirements
ray_job: "submit job with script gpu_training.py requiring 1 GPU on kubernetes"

# Scale cluster
ray_cluster: "scale cluster gpu-cluster to 5 workers"
```

### Manage KubeRay Jobs

```bash
# List jobs in specific namespace
ray_job: "list jobs in namespace production"

# Get job logs from kubernetes
ray_job: "get logs for job training-job-123 in namespace ml-workloads"

# Cancel kubernetes job
ray_job: "cancel job training-job-123 in namespace ml-workloads"
```

## Cloud Provider Integration

### Google Cloud (GKE)

```bash
# Authenticate with GCP
cloud: "authenticate with GCP project my-ml-project"

# List GKE clusters
cloud: "list all GKE clusters"

# Connect to GKE cluster
cloud: "connect to GKE cluster production-cluster in zone us-central1-a"

# Create new GKE cluster
cloud: "create GKE cluster ml-cluster with 4 nodes in zone us-central1-a"
```

### Environment Check

```bash
# Check environment setup
cloud: "check cloud environment setup"

# Verify authentication
cloud: "check GCP authentication status"
```

## Job Management Patterns

### Simple Job Submission

```bash
# Basic job
ray_job: "submit job with script process_data.py"

# Job with arguments
ray_job: "submit job with script train.py --epochs 10 --batch-size 32"

# Job with resource requirements
ray_job: "submit job with script distributed_job.py requiring 4 CPUs"
```

### Job Monitoring

```bash
# List all jobs
ray_job: "list all jobs"

# List only running jobs
ray_job: "list running jobs"

# Check specific job status
ray_job: "get status for job raysubmit_456"

# Get job logs
ray_job: "get logs for job raysubmit_456"
```

### Job Lifecycle

```bash
# Submit job
ray_job: "submit job with script long_running_task.py"

# Monitor progress
ray_job: "get status for job raysubmit_789"

# Cancel if needed
ray_job: "cancel job raysubmit_789"
```

## Ray Service Management

### Deploy and Manage Services

```bash
# Deploy inference service
ray_service: "deploy service with inference model serve.py"

# Create named service  
ray_service: "create service named image-classifier with model classifier.py"

# List all services
ray_service: "list all services"

# Get service status
ray_service: "get status of service image-classifier"
```

### Service Scaling and Management

```bash
# Scale service replicas
ray_service: "scale service model-api to 5 replicas"

# Update service configuration
ray_service: "update service recommendation-engine with new model updated_model.py"

# Get service logs
ray_service: "get logs for service text-analyzer"

# Delete service
ray_service: "delete service old-model-service"
```

### Production Service Patterns

```bash
# Deploy production inference service
ray_service: "create service named prod-inference with model production_model.py in namespace production"

# Monitor service health
ray_service: "get status of service prod-inference"

# Scale based on load
ray_service: "scale service prod-inference to 10 replicas"

# Update with zero downtime
ray_service: "update service prod-inference with model updated_production_model.py"
```

## Advanced Scenarios

### Multi-Environment Workflow

```bash
# 1. Start with local development
ray_cluster: "create local cluster with 2 CPUs"
ray_job: "submit job with script test_model.py"

# 2. Move to kubernetes for larger scale
ray_cluster: "create Ray cluster named dev-cluster with 5 workers on kubernetes"
ray_job: "submit job with script full_training.py on kubernetes"

# 3. Deploy to production GKE with services
cloud: "connect to GKE cluster production-cluster"
ray_service: "deploy service named production-api with model inference_model.py"
```

### Resource Management

```bash
# Create cluster with specific resources
ray_cluster: "create Ray cluster named compute-cluster with 8 CPU workers and 2 GPU workers"

# Submit jobs with different requirements
ray_job: "submit job with script cpu_task.py requiring 2 CPUs"
ray_job: "submit job with script gpu_task.py requiring 1 GPU"

# Scale based on workload
ray_cluster: "scale cluster compute-cluster to 12 workers"
```

### Debugging and Monitoring

```bash
# Check cluster health
ray_cluster: "inspect cluster status"

# Monitor job progress
ray_job: "get logs for job raysubmit_123"

# Check resource usage
ray_cluster: "show cluster resource usage"

# Debug failed jobs
ray_job: "get error logs for job raysubmit_456"
```

## Common Patterns

### Development to Production

```bash
# 1. Local development
ray_cluster: "create local cluster"
ray_job: "submit job with script prototype.py"

# 2. Kubernetes testing
ray_cluster: "create Ray cluster named test-cluster on kubernetes"
ray_job: "submit job with script prototype.py on kubernetes"

# 3. Production deployment
cloud: "connect to GKE cluster production"
ray_job: "submit job with script production_model.py on kubernetes"
```

### Batch Processing

```bash
# Create ephemeral cluster for batch job
ray_cluster: "create Ray cluster named batch-cluster with 10 workers on kubernetes"

# Submit batch job
ray_job: "submit job with script batch_processing.py on kubernetes"

# Monitor completion
ray_job: "get status for job batch-processing-job"

# Cleanup
ray_cluster: "delete cluster batch-cluster"
```

### Interactive Development

```bash
# Create persistent cluster
ray_cluster: "create Ray cluster named interactive-cluster with 4 workers on kubernetes"

# Submit multiple experiments
ray_job: "submit job with script experiment_1.py"
ray_job: "submit job with script experiment_2.py"
ray_job: "submit job with script experiment_3.py"

# Monitor all experiments
ray_job: "list all jobs"
```

## Error Handling

### Common Issues

```bash
# Check if cluster is running
ray_cluster: "inspect cluster status"

# If authentication fails
cloud: "check cloud environment setup"

# If job fails
ray_job: "get logs for job raysubmit_123"

# If resources insufficient
ray_cluster: "scale cluster to 8 workers"
```

### Recovery Patterns

```bash
# Restart failed job
ray_job: "cancel job raysubmit_123"
ray_job: "submit job with script fixed_model.py"

# Scale up for resource issues
ray_cluster: "scale cluster to 10 workers"
ray_job: "submit job with script resource_intensive.py"
```