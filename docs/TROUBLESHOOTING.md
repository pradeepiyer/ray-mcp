# Ray MCP Server Troubleshooting Guide

This document provides comprehensive troubleshooting information for common issues with the Ray MCP Server.

## Common Issues and Solutions

### 1. Ray Initialization Problems

#### Issue: "Ray is not initialized. Please start Ray first."

**Symptoms**: Tools return this error when trying to use Ray functionality.

**Causes**:
- Ray cluster hasn't been started
- Ray initialization failed
- Connection to existing cluster failed

**Solutions**:
```json
// First, initialize Ray
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4
  }
}

// Then use other tools
{
  "tool": "cluster_info",
  "arguments": {}
}
```

#### Issue: Port conflicts during cluster startup

**Symptoms**: Error messages about ports being in use.

**Solutions**:
```json
// Use automatic port allocation
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4
    // Don't specify head_node_port or dashboard_port
  }
}

// Or specify different ports
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4,
    "head_node_port": 10002,
    "dashboard_port": 8266
  }
}
```

### 2. Multi-Node Cluster Issues

#### Issue: Worker nodes fail to start

**Symptoms**: Head node starts but worker nodes show errors.

**Causes**:
- Resource conflicts between head and worker nodes
- Network connectivity issues
- Insufficient system resources

**Solutions**:
```json
// Ensure worker resources don't exceed head node capacity
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4,
    "worker_nodes": [
      {
        "num_cpus": 2,  // Less than head node
        "node_name": "worker-1"
      }
    ]
  }
}

// Check cluster status
{
  "tool": "cluster_info",
  "arguments": {}
}
```

#### Issue: Worker nodes not connecting to head node

**Symptoms**: Workers start but don't appear in cluster info.

**Solutions**:
- Check network connectivity between nodes
- Verify firewall settings
- Ensure head node is accessible from worker machines

### 3. Job Submission Issues

#### Issue: Job submission fails

**Symptoms**: `submit_job` returns error or job doesn't start.

**Causes**:
- Invalid entrypoint path
- Missing dependencies
- Runtime environment issues

**Solutions**:
```json
// Check job status
{
  "tool": "list_jobs",
  "arguments": {}
}

// Inspect specific job
{
  "tool": "inspect_job",
  "arguments": {
    "job_id": "raysubmit_1234567890",
    "mode": "debug"
  }
}

// Get job logs
{
  "tool": "retrieve_logs",
  "arguments": {
    "identifier": "raysubmit_1234567890",
    "log_type": "job",
    "include_errors": true
  }
}
```

#### Issue: Runtime environment problems

**Symptoms**: Jobs fail due to missing dependencies.

**Solutions**:
```json
// Specify runtime environment
{
  "tool": "submit_job",
  "arguments": {
    "entrypoint": "python examples/distributed_training.py",
    "runtime_env": {
      "pip": ["torch", "numpy", "scikit-learn"]
    }
  }
}
```

### 4. Log Retrieval Issues

#### Issue: Can't retrieve logs

**Symptoms**: `retrieve_logs` returns errors or empty results.

**Solutions**:
```json
// Try different log types
{
  "tool": "retrieve_logs",
  "arguments": {
    "identifier": "raysubmit_1234567890",
    "log_type": "job",
    "num_lines": 100
  }
}

// Use retrieve_logs for job logs
{
  "tool": "retrieve_logs",
  "arguments": {
    "identifier": "raysubmit_1234567890",
    "log_type": "job",
    "num_lines": 100
  }
}
```

### 5. Resource Management Issues

#### Issue: Insufficient resources

**Symptoms**: Jobs fail due to resource constraints.

**Solutions**:
```json
// Check current resource usage
{
  "tool": "cluster_info",
  "arguments": {}
}

// Start cluster with more resources
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 8,
    "num_gpus": 2,
    "object_store_memory": 4000000000
  }
}
```

## Debugging Commands

### Cluster Health Check

```json
{
  "tool": "cluster_info",
  "arguments": {}
}
```

### Job Debugging

```json
// List all jobs
{
  "tool": "list_jobs",
  "arguments": {}
}

// Detailed job inspection
{
  "tool": "inspect_job",
  "arguments": {
    "job_id": "raysubmit_1234567890",
    "mode": "debug"
  }
}

// Get comprehensive logs
{
  "tool": "retrieve_logs",
  "arguments": {
    "identifier": "raysubmit_1234567890",
    "log_type": "job",
    "num_lines": 500,
    "include_errors": true
  }
}
```

## Environment-Specific Issues

### Development Environment

#### Issue: Import errors

**Solutions**:
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
uv sync
uv pip install -e .
```

#### Issue: Test failures

**Solutions**:
```bash
# Clean up Ray processes
./scripts/ray_cleanup.sh

# Run tests with cleanup
make test-e2e
```

### Production Environment

#### Issue: Network connectivity

**Solutions**:
- Verify firewall settings
- Check network routes
- Ensure ports are accessible

#### Issue: Resource constraints

**Solutions**:
- Monitor system resources
- Adjust cluster configuration
- Use appropriate worker node specifications

## Performance Issues

### Slow Job Execution

**Causes**:
- Insufficient resources
- Network latency
- Inefficient code

**Solutions**:
```json
// Monitor resource usage
{
  "tool": "cluster_info",
  "arguments": {}
}

// Optimize cluster configuration
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 16,
    "object_store_memory": 8000000000,
    "worker_nodes": [
      {
        "num_cpus": 8,
        "object_store_memory": 4000000000
      }
    ]
  }
}
```

### Memory Issues

**Symptoms**: Out of memory errors or slow performance.

**Solutions**:
- Increase object store memory
- Monitor memory usage
- Optimize data processing patterns

## Error Messages and Meanings

### Common Error Messages

1. **"Ray is not initialized"**: Start Ray cluster first
2. **"Port already in use"**: Use different ports or automatic allocation
3. **"Job submission failed"**: Check entrypoint and runtime environment
4. **"Worker node failed to start"**: Check resource configuration
5. **"Connection refused"**: Check network connectivity

### Error Response Format

```json
{
  "status": "error",
  "message": "Error description",
  "error": "Detailed error information"
}
```

## Recovery Procedures

### Cluster Recovery

```json
// Stop current cluster
{
  "tool": "stop_ray",
  "arguments": {}
}

// Restart with clean configuration
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4
  }
}
```

### Job Recovery

```json
// Cancel problematic job
{
  "tool": "cancel_job",
  "arguments": {
    "job_id": "raysubmit_1234567890"
  }
}

// Resubmit with corrected configuration
{
  "tool": "submit_job",
  "arguments": {
    "entrypoint": "python examples/simple_job.py"
  }
}
```

## Prevention Best Practices

1. **Monitor Resources**: Regularly check cluster status
2. **Use Appropriate Configuration**: Match cluster size to workload
3. **Handle Errors Gracefully**: Implement proper error handling in jobs
4. **Clean Up Resources**: Stop clusters when not in use
5. **Test Configurations**: Validate setups in development first
6. **Use Enhanced Output**: Enable enhanced output for better debugging

## Getting Help

### Debug Information

When reporting issues, include:

1. **Cluster Configuration**: The `init_ray` arguments used
2. **Job Configuration**: The `submit_job` arguments used
3. **Error Messages**: Complete error responses
4. **System Information**: OS, Python version, Ray version
5. **Logs**: Relevant log output from tools

### Useful Commands

```bash
# Check Ray status
ray status

# Clean up Ray processes
./scripts/ray_cleanup.sh

# Check system resources
htop
df -h
free -h

# Check network connectivity
ping <head-node-ip>
telnet <head-node-ip> <port>
```

### Enhanced Output Mode

Enable enhanced output for better debugging:

```bash
export RAY_MCP_ENHANCED_OUTPUT=true
```

This provides additional context and suggestions for resolving issues. 