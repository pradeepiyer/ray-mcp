# Troubleshooting Guide

Comprehensive troubleshooting guide for Ray MCP server covering local clusters, KubeRay, and cloud provider issues.

## General Diagnostic Steps

### Check Environment Setup

```python
# Check overall environment
check_environment(provider="all")

# Get cloud provider status
get_cloud_provider_status(provider="all")

# Detect available providers
detect_cloud_provider()
```

### Enable Debug Logging

```bash
export RAY_MCP_LOG_LEVEL=DEBUG
export RAY_MCP_ENHANCED_OUTPUT=true
ray-mcp
```

### Verify Dependencies

```bash
# Check Ray installation
python -c "import ray; print(ray.__version__)"

# Check Kubernetes client
python -c "from kubernetes import client, config; print('Kubernetes available')"

# Check Google Cloud client (if using GKE)
python -c "from google.cloud import container_v1; print('GKE client available')"
```

## Installation Issues

### Ray Import Errors

**Problem:** `ImportError: No module named 'ray'`

**Solutions:**
```bash
# Install Ray with default dependencies
pip install ray[default]>=2.47.0

# Or with uv
uv add ray[default]

# For specific versions
pip install ray[default]==2.47.0
```

### MCP Module Not Found

**Problem:** `ImportError: No module named 'mcp'`

**Solutions:**
```bash
# Reinstall ray-mcp
pip install -e .

# Or install with uv
uv sync

# Check if MCP is installed
python -c "import mcp; print('MCP available')"
```

### Cloud Provider Dependencies Missing

**Problem:** `ImportError: No module named 'google.cloud'` or similar

**Solutions:**
```bash
# Install GKE dependencies
uv add "ray-mcp[gke]"
# or
pip install "ray-mcp[gke]"

# Install all cloud dependencies
uv add "ray-mcp[cloud]"
# or
pip install "ray-mcp[cloud]"

# Verify installation
python -c "from google.cloud import container_v1; print('GKE client available')"
```

## Local Ray Cluster Issues

### Cluster Initialization Failures

**Problem:** Cluster fails to start with port binding errors

**Solutions:**
```bash
# Kill existing Ray processes
ray stop --force

# Check for processes using Ray ports
lsof -i :10001
lsof -i :8265

# Kill specific processes if needed
sudo kill -9 $(lsof -t -i:10001)
```

### Permission Denied Errors

**Problem:** `PermissionError: [Errno 13] Permission denied`

**Solutions:**
```bash
# Check directory permissions
ls -la $(pwd)

# Ensure write permissions in working directory
chmod 755 $(pwd)

# Check firewall settings (macOS)
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate

# Check firewall settings (Linux)
sudo ufw status
```

### Memory Issues

**Problem:** Ray cluster runs out of memory or object store space

**Solutions:**
```python
# Start cluster with more object store memory
init_ray_cluster(
    num_cpus=4,
    worker_nodes=[{
        "num_cpus": 2,
        "object_store_memory": 2000000000  # 2GB
    }]
)

# Monitor memory usage
inspect_ray_cluster()
```

### Worker Node Connection Issues

**Problem:** Worker nodes fail to connect to head node

**Solutions:**
```bash
# Check network connectivity
ping HEAD_NODE_IP

# Verify Ray ports are open
telnet HEAD_NODE_IP 10001

# Check Ray status
ray status

# Restart with explicit ports
init_ray_cluster(
    head_node_port=10001,
    dashboard_port=8265
)
```

## KubeRay Issues

### KubeRay Operator Not Found

**Problem:** `RayCluster` CRD not found or operator not running

**Solutions:**
```bash
# Check if KubeRay operator is installed
kubectl get pods -n kuberay-system

# Install KubeRay operator
kubectl create namespace kuberay-system
kubectl apply -f https://raw.githubusercontent.com/ray-project/kuberay/release-0.8/ray-operator/config/crd/bases/ray.io_rayclusters.yaml
kubectl apply -f https://raw.githubusercontent.com/ray-project/kuberay/release-0.8/ray-operator/config/crd/bases/ray.io_rayjobs.yaml
kubectl apply -f https://raw.githubusercontent.com/ray-project/kuberay/release-0.8/deploy/kuberay-operator.yaml

# Verify operator is running
kubectl get pods -n kuberay-system
kubectl logs -n kuberay-system deployment/kuberay-operator
```

### RayCluster Creation Failures

**Problem:** RayCluster fails to create or pods don't start

**Solutions:**
```bash
# Check cluster status
kubectl get rayclusters -A

# Get cluster details
kubectl describe rayc CLUSTER_NAME -n NAMESPACE

# Check pod events
kubectl get pods -n NAMESPACE
kubectl describe pod POD_NAME -n NAMESPACE

# Check resource constraints
kubectl describe nodes
kubectl top nodes
```

**Common Issues and Fixes:**

1. **Insufficient Resources:**
   ```python
   # Reduce resource requests
   init_ray_cluster(
       cluster_type="kubernetes",
       head_node_spec={
           "cpu_request": 1,  # Reduced from 2
           "memory_request": "2Gi"  # Reduced from 4Gi
       }
   )
   ```

2. **Image Pull Errors:**
   ```bash
   # Check image availability
   docker pull rayproject/ray:2.47.0
   
   # Use specific image
   init_ray_cluster(
       cluster_type="kubernetes",
       head_node_spec={"image": "rayproject/ray:2.47.0"}
   )
   ```

3. **Node Selector Issues:**
   ```bash
   # Check node labels
   kubectl get nodes --show-labels
   
   # Remove or fix node selectors
   init_ray_cluster(
       cluster_type="kubernetes",
       head_node_spec={
           "node_selector": {}  # Remove node selector
       }
   )
   ```

### RayJob Submission Failures

**Problem:** RayJob fails to submit or execute

**Solutions:**
```bash
# Check job status
kubectl get rayjobs -A

# Get job details
kubectl describe rayjob JOB_NAME -n NAMESPACE

# Check job logs
kubectl logs -n NAMESPACE $(kubectl get pods -n NAMESPACE -l ray.io/node-type=head -o jsonpath='{.items[0].metadata.name}')
```

**Common Issues:**

1. **Cluster Selector Issues:**
   ```python
   # Use existing cluster correctly
   submit_ray_job(
       entrypoint="python job.py",
       job_type="kubernetes",
       cluster_selector="existing-cluster-name",  # Exact cluster name
       shutdown_after_job_finishes=False  # Don't shutdown existing cluster
   )
   ```

2. **TTL Configuration Errors:**
   ```python
   # For ephemeral clusters only
   submit_ray_job(
       entrypoint="python job.py",
       job_type="kubernetes",
       shutdown_after_job_finishes=True,
       ttl_seconds_after_finished=3600
       # cluster_selector should NOT be specified
   )
   ```

## Cloud Provider Issues

### Google Cloud Platform (GKE)

#### Authentication Problems

**Problem:** `DefaultCredentialsError` or authentication failures

**Solutions:**
```bash
# Check authentication status
gcloud auth list
gcloud auth application-default print-access-token

# Re-authenticate
gcloud auth application-default login

# Or use service account
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
gcloud auth activate-service-account --key-file="$GOOGLE_APPLICATION_CREDENTIALS"

# Test authentication via MCP
authenticate_cloud_provider(
    provider="gke",
    service_account_path="/path/to/service-account.json",
    project_id="your-project"
)
```

#### Permission Issues

**Problem:** `403 Forbidden` or insufficient permissions

**Solutions:**
```bash
# Check current permissions
gcloud projects get-iam-policy PROJECT_ID \
    --flatten="bindings[].members" \
    --format="table(bindings.role)" \
    --filter="bindings.members:SERVICE_ACCOUNT_EMAIL"

# Grant required roles
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
    --role="roles/container.admin"

gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
    --role="roles/compute.viewer"
```

#### API Enablement Issues

**Problem:** API not enabled errors

**Solutions:**
```bash
# Enable required APIs
gcloud services enable container.googleapis.com
gcloud services enable compute.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Verify APIs are enabled
gcloud services list --enabled --filter="name:container.googleapis.com"
```

#### GKE Cluster Access Issues

**Problem:** Cannot connect to GKE clusters

**Solutions:**
```bash
# Update kubeconfig
gcloud container clusters get-credentials CLUSTER_NAME --zone=ZONE --project=PROJECT_ID

# Test cluster access
kubectl cluster-info
kubectl get nodes

# Check cluster firewall rules
gcloud compute firewall-rules list --filter="name~gke-CLUSTER_NAME"

# For private clusters, check authorized networks
gcloud container clusters describe CLUSTER_NAME --zone=ZONE --format="value(privateClusterConfig.authorizedNetworksConfig.cidrBlocks[].cidrBlock)"
```

#### Network Connectivity Issues

**Problem:** Cannot reach cluster endpoints

**Solutions:**
```bash
# Check VPN connection (for private clusters)
ping CLUSTER_ENDPOINT

# Test specific ports
telnet CLUSTER_ENDPOINT 443
telnet CLUSTER_ENDPOINT 8265

# Check NAT gateway (for private clusters)
gcloud compute routers nats list --router=ROUTER_NAME --region=REGION
```

### Local Kubernetes Issues

#### Minikube Problems

**Problem:** Minikube fails to start or connect

**Solutions:**
```bash
# Delete and recreate minikube
minikube delete
minikube start --cpus=4 --memory=8192 --disk-size=50g

# Check minikube status
minikube status

# Update kubeconfig
minikube update-context

# Check minikube logs
minikube logs
```

#### Kind Issues

**Problem:** Kind cluster issues

**Solutions:**
```bash
# Delete and recreate kind cluster
kind delete cluster
kind create cluster --config=kind-config.yaml

# Load images into kind
kind load docker-image rayproject/ray:2.47.0

# Check kind cluster
kubectl cluster-info --context kind-kind
```

#### Docker Desktop Issues

**Problem:** Docker Desktop Kubernetes not working

**Solutions:**
1. Reset Kubernetes cluster in Docker Desktop settings
2. Increase resource limits (CPU: 4+, Memory: 8GB+)
3. Restart Docker Desktop
4. Verify with: `kubectl cluster-info`

## Job Execution Issues

### Job Submission Failures

**Problem:** Jobs fail to submit

**Solutions:**
```python
# Check cluster status first
cluster_status = inspect_ray_cluster()
print(cluster_status)

# Verify cluster is ready
if cluster_status["status"] != "success":
    # Reinitialize cluster
    init_ray_cluster()

# Submit with error handling
try:
    job_result = submit_ray_job(entrypoint="python job.py")
    print(f"Job submitted: {job_result}")
except Exception as e:
    print(f"Job submission failed: {e}")
```

### Runtime Environment Errors

**Problem:** Jobs fail with package import errors

**Solutions:**
```python
# Use explicit runtime environment
submit_ray_job(
    entrypoint="python job.py",
    runtime_env={
        "pip": ["package==1.0.0"],  # Pin versions
        "working_dir": "/absolute/path",  # Use absolute paths
        "env_vars": {"PYTHONPATH": "/workspace"}
    }
)

# Test runtime environment locally first
# Create test_env.py:
# import package; print("Package imported successfully")
submit_ray_job(
    entrypoint="python test_env.py",
    runtime_env={"pip": ["package"]}
)
```

### Job Timeout Issues

**Problem:** Jobs hang or timeout

**Solutions:**
```python
# Set job timeouts
submit_ray_job(
    entrypoint="python long_job.py",
    job_type="kubernetes",
    active_deadline_seconds=7200,  # 2 hour timeout
    runtime_env={"pip": ["required-package"]}
)

# Monitor job progress
job_id = "your-job-id"
while True:
    status = inspect_ray_job(job_id=job_id)
    print(f"Job status: {status['data']['status']}")
    if status['data']['status'] in ['SUCCEEDED', 'FAILED']:
        break
    time.sleep(30)
```

## Logging and Debugging Issues

### Log Retrieval Failures

**Problem:** Cannot retrieve logs or logs are empty

**Solutions:**
```python
# Check if job/cluster exists
list_ray_jobs()
list_ray_clusters()

# Use correct identifier
retrieve_logs(
    identifier="job_abc123",  # Use actual job ID
    log_type="job",
    include_errors=True
)

# For KubeRay jobs, check pod logs directly
# kubectl logs POD_NAME -n NAMESPACE
```

### Large Log Handling

**Problem:** Logs are too large or cause memory issues

**Solutions:**
```python
# Use pagination
retrieve_logs(
    identifier="job_abc123",
    page=1,
    page_size=100,
    max_size_mb=10
)

# Filter logs
retrieve_logs(
    identifier="job_abc123",
    filter="ERROR",
    num_lines=1000
)
```

## Performance Issues

### Slow Cluster Initialization

**Problem:** Cluster takes too long to start

**Solutions:**
```python
# Use smaller resource requests
init_ray_cluster(
    cluster_type="kubernetes",
    head_node_spec={
        "cpu_request": 1,
        "memory_request": "2Gi"
    },
    worker_node_specs=[{
        "replicas": 1,  # Start with fewer workers
        "cpu_request": 1,
        "memory_request": "2Gi"
    }]
)

# Scale up after initialization
scale_ray_cluster(
    cluster_name="cluster-name",
    worker_group_name="worker-group",
    replicas=5
)
```

### Job Execution Performance

**Problem:** Jobs run slowly or fail with resource errors

**Solutions:**
```python
# Increase resource allocation
init_ray_cluster(
    cluster_type="kubernetes",
    worker_node_specs=[{
        "replicas": 5,
        "num_cpus": 4,
        "memory_request": "8Gi",
        "memory_limit": "16Gi"
    }]
)

# Use appropriate machine types for GKE
create_kubernetes_cluster(
    provider="gke",
    cluster_spec={
        "name": "high-performance-cluster",
        "machine_type": "c2-standard-8",  # High CPU
        "node_count": 4
    }
)
```

## Common Error Messages

### `'str' object has no attribute 'isoformat'`

**Solution:** Update to latest version of ray-mcp
```bash
uv add ray-mcp@latest
# or
pip install --upgrade ray-mcp
```

### `Google Cloud SDK not available`

**Solution:** Install GKE dependencies
```bash
uv add "ray-mcp[gke]"
# or
pip install "ray-mcp[gke]"
```

### `Not authenticated with gke`

**Solution:** Authenticate with GKE
```python
authenticate_cloud_provider(
    provider="gke",
    service_account_path="/path/to/key.json",
    project_id="your-project"
)
```

### `RBAC: access denied`

**Solution:** Check Kubernetes permissions
```bash
# Check current user permissions
kubectl auth can-i "*" "*"

# For service accounts, ensure proper RBAC
kubectl create clusterrolebinding ray-admin \
    --clusterrole=cluster-admin \
    --serviceaccount=default:default
```

## Environment-Specific Issues

### Claude Desktop Integration

**Problem:** Works in terminal but not in Claude Desktop

**Solutions:**
1. Install dependencies in the same Python environment
2. Use absolute paths in configuration
3. Set environment variables in Claude Desktop config
4. Check Python path and virtual environment

```json
{
  "mcpServers": {
    "ray-mcp": {
      "command": "/full/path/to/python",
      "args": ["-m", "ray_mcp.main"],
      "cwd": "/full/path/to/ray-mcp",
      "env": {
        "PYTHONPATH": "/full/path/to/ray-mcp",
        "GOOGLE_APPLICATION_CREDENTIALS": "/full/path/to/key.json"
      }
    }
  }
}
```

### Cross-Platform Issues

**Problem:** Issues running on Windows or macOS

**Solutions:**
```bash
# Enable multi-node clusters on Windows/macOS
export RAY_ENABLE_WINDOWS_OR_OSX_CLUSTER=1

# Use Docker for Kubernetes on Windows/macOS
# Install Docker Desktop and enable Kubernetes
```

## Advanced Debugging

### Kubernetes Resource Debugging

```bash
# Check all Ray-related resources
kubectl get all -l app.kubernetes.io/name=kuberay

# Check resource usage
kubectl top pods -A
kubectl top nodes

# Check events
kubectl get events --sort-by=.metadata.creationTimestamp -A

# Debug specific pod
kubectl describe pod POD_NAME -n NAMESPACE
kubectl logs POD_NAME -n NAMESPACE --previous
```

### Network Debugging

```bash
# Test connectivity from within cluster
kubectl run debug-pod --image=busybox --rm -it -- sh

# Inside the pod:
nslookup ray-cluster-head
wget -qO- http://ray-cluster-head:8265/api/cluster_status
```

### Resource Monitoring

```python
# Monitor cluster resources
while True:
    cluster_info = inspect_ray_cluster()
    print(f"Cluster status: {cluster_info}")
    time.sleep(60)

# Monitor job resources
job_info = inspect_ray_job(job_id="job_id", mode="debug")
print(f"Job resources: {job_info}")
```

## Getting Additional Help

### Collect Debug Information

```bash
# Collect system information
uv run python -c "
import ray
import sys
import platform
print(f'Python: {sys.version}')
print(f'Platform: {platform.platform()}')
print(f'Ray: {ray.__version__}')
"

# Collect Ray cluster information
ray status

# Collect Kubernetes information
kubectl version
kubectl cluster-info dump > cluster-info.txt
```

### Enable Verbose Logging

```bash
export RAY_MCP_LOG_LEVEL=DEBUG
export RAY_LOG_LEVEL=DEBUG

# For Kubernetes debugging
kubectl logs -n kuberay-system deployment/kuberay-operator -f
```

### Common Support Resources

1. **Ray Documentation**: https://docs.ray.io/
2. **KubeRay Documentation**: https://ray-project.github.io/kuberay/
3. **Ray GitHub Issues**: https://github.com/ray-project/ray/issues
4. **KubeRay GitHub Issues**: https://github.com/ray-project/kuberay/issues

Remember to include debug information, error messages, and environment details when seeking help. 