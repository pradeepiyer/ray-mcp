# Troubleshooting Guide

Common issues and solutions for Ray MCP Server's prompt-driven architecture.

## Quick Diagnostics

### Check System Status

```bash
# Check environment setup
cloud: "check cloud environment setup"

# Test basic functionality
ray_cluster: "inspect cluster status"
ray_job: "list all jobs"
```

### Enable Debug Logging

```bash
export RAY_MCP_LOG_LEVEL=DEBUG
export RAY_MCP_ENHANCED_OUTPUT=true
uv run ray-mcp
```

## Common Issues

### Installation Problems

**Ray Import Errors**
```bash
# Install Ray with default dependencies
uv add ray[default]

# Verify installation
python -c "import ray; print(ray.__version__)"
```

**MCP Module Not Found**
```bash
# Reinstall ray-mcp
uv sync

# Check installation
python -c "import mcp; print('MCP available')"
```

**Cloud Dependencies Missing**
```bash
# Install GKE support
uv add "ray-mcp[gke]"

# Install all cloud dependencies
uv add "ray-mcp[all]"
```

### Local Ray Cluster Issues

**Cluster Initialization Failures**
```bash
# Kill existing Ray processes
ray stop --force

# Check for processes using Ray ports
lsof -i :10001
lsof -i :8265

# Kill specific processes if needed
sudo kill -9 $(lsof -t -i:10001)
```

**Permission Denied Errors**
```bash
# Check directory permissions
ls -la $(pwd)

# Ensure write permissions
chmod 755 $(pwd)

# Check firewall settings (macOS)
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate
```

### KubeRay Issues

**KubeRay Operator Not Found**
```bash
# Check if operator is installed
kubectl get pods -n kuberay-system

# Install KubeRay operator
kubectl apply -f https://raw.githubusercontent.com/ray-project/kuberay/release-0.8/deploy/kuberay-operator.yaml

# Verify operator is running
kubectl logs -n kuberay-system deployment/kuberay-operator
```

**Cluster Connection Issues**
```bash
# Test cluster connectivity
kubectl cluster-info

# Check Ray clusters
kubectl get rayclusters -A

# Check KubeRay pods
kubectl get pods -l app.kubernetes.io/name=kuberay
```

### Authentication Issues

**GCP Authentication Failures**
```bash
# Check service account
gcloud auth application-default login

# Verify credentials
gcloud auth list

# Test with environment variable
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

**Kubernetes Authentication**
```bash
# Check kubeconfig
kubectl config current-context

# Test connectivity
kubectl get nodes

# Update kubeconfig if needed
gcloud container clusters get-credentials CLUSTER_NAME --zone ZONE
```

## Environment-Specific Issues

### Claude Desktop Integration

**Configuration Issues**
```json
{
  "mcpServers": {
    "ray-mcp": {
      "command": "uv",
      "args": ["run", "ray-mcp"],
      "cwd": "/full/path/to/ray-mcp",
      "env": {
        "GOOGLE_APPLICATION_CREDENTIALS": "/full/path/to/key.json",
        "RAY_MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

**Path Issues**
- Use absolute paths for all files
- Ensure virtual environment is activated
- Check Python module paths

### Tool Response Issues

**Empty or Error Responses**
```bash
# Check tool validation
make lint-tool-functions

# Verify 3-tool architecture
python -c "from ray_mcp.tools import get_ray_tools; print([t.name for t in get_ray_tools()])"
```

**Prompt Parsing Failures**
```bash
# Test prompt parsing directly
python -c "from ray_mcp.foundation.action_parser import ActionParser; parser = ActionParser(); print(parser.parse_cluster_action('create a local cluster'))"
```

## Recovery Procedures

### Complete Reset

```bash
# Stop all Ray processes
ray stop --force

# Clean up Ray temporary files
rm -rf /tmp/ray*

# Reset Kubernetes context
kubectl config use-context default

# Restart MCP server
uv run ray-mcp
```

### Cluster Recovery

```bash
# Reset local cluster
ray_cluster: "stop the current cluster"
ray_cluster: "create a local cluster"

# Reset KubeRay cluster
ray_cluster: "delete cluster test-cluster"
ray_cluster: "create Ray cluster named test-cluster on kubernetes"
```

### Authentication Recovery

```bash
# Re-authenticate with GCP
cloud: "authenticate with GCP project YOUR_PROJECT_ID"

# Verify authentication
cloud: "check cloud environment setup"
```

## Advanced Debugging

### Component-Level Testing

```python
# Test individual components
from ray_mcp.managers.unified_manager import RayUnifiedManager

manager = RayUnifiedManager()

# Test cluster operations
result = await manager.handle_cluster_request("create a local cluster")
print(result)

# Test job operations  
result = await manager.handle_job_request("list all jobs")
print(result)
```

### MCP Protocol Debugging

```bash
# Enable MCP debug logging
export MCP_LOG_LEVEL=DEBUG
export RAY_MCP_LOG_LEVEL=DEBUG

# Run with verbose output
uv run ray-mcp --verbose
```

## Getting Help

### Log Collection

```bash
# Enable debug logging
export RAY_MCP_LOG_LEVEL=DEBUG

# Run problematic operation
ray_cluster: "create a local cluster"

# Collect logs
tail -f /tmp/ray/session_*/logs/monitor.log
```

### System Information

```bash
# Check system specs
uname -a
python --version
kubectl version

# Check Ray installation
python -c "import ray; print(ray.__version__)"

# Check available resources
ray_cluster: "show cluster resource usage"
```

When reporting issues, include:
- Error messages and stack traces
- System information (OS, Python version, Ray version)
- MCP configuration
- Steps to reproduce the issue
- Debug logs if available