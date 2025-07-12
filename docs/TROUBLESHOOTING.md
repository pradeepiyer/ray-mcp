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
