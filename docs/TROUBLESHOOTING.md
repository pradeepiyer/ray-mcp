# Troubleshooting Guide

Common issues and solutions for Ray MCP server.

## Installation Issues

### Ray Import Errors

**Problem:** `ImportError: No module named 'ray'`

**Solutions:**
```bash
# Install Ray
pip install ray[default]>=2.47.0

# Or with uv
uv add ray[default]
```

### MCP Module Not Found

**Problem:** `ImportError: No module named 'mcp'`

**Solutions:**
```bash
# Install MCP
pip install mcp>=1.0.0

# Or reinstall ray-mcp
pip install -e .
```

## Cluster Initialization Issues

### Port Already in Use

**Problem:** `OSError: [Errno 48] Address already in use`

**Solutions:**
- Ray MCP automatically finds free ports
- Kill existing Ray processes: `ray stop --force`
- Check for processes on ports: `lsof -i :10001`

### Permission Denied

**Problem:** `PermissionError: [Errno 13] Permission denied`

**Solutions:**
- Ensure write permissions in working directory
- Check firewall settings for port binding
- Run with appropriate user permissions

### Cluster Connection Timeout

**Problem:** Cluster initialization hangs or times out

**Solutions:**
```bash
# Check Ray status
ray status

# Force cleanup
ray stop --force

# Restart with debug logging
RAY_LOG_LEVEL=debug ray-mcp
```

## Job Submission Issues

### Job Submission Fails

**Problem:** Jobs fail to submit or start

**Diagnosis:**
```python
# Check cluster status first
inspect_ray()

# Verify job client connection
list_jobs()
```

**Solutions:**
- Ensure cluster is initialized: `init_ray()`
- Check resource availability in cluster status
- Verify entrypoint syntax and file paths

### Runtime Environment Errors

**Problem:** Jobs fail with package import errors

**Solutions:**
```python
# Specify runtime environment explicitly
submit_job(
    entrypoint="python script.py",
    runtime_env={
        "pip": ["package1", "package2==1.0.0"],
        "working_dir": "/path/to/code"
    }
)
```

## MCP Client Issues

### Server Not Responding

**Problem:** MCP client cannot connect to Ray MCP server

**Diagnosis:**
- Check server process is running
- Verify MCP client configuration
- Check server logs for errors

**Solutions:**
```bash
# Test server directly
ray-mcp

# Check configuration file
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

### Tool Call Failures

**Problem:** Tool calls return errors or hang

**Solutions:**
- Enable debug logging: `RAY_MCP_LOG_LEVEL=DEBUG`
- Check tool parameters match schema
- Verify Ray cluster status before tool calls

## Performance Issues

### Slow Tool Responses

**Problem:** Tool calls take too long to respond

**Solutions:**
- Check cluster resource utilization: `inspect_ray()`
- Reduce log retrieval size: `num_lines=100`
- Use pagination for large log files
- Monitor system resources (CPU, memory)

### Memory Issues

**Problem:** High memory usage or out-of-memory errors

**Solutions:**
- Limit log retrieval size: `max_size_mb=10`
- Use paginated log retrieval
- Check object store memory in cluster config
- Monitor Ray memory usage in dashboard

## Log Retrieval Issues

### No Logs Available

**Problem:** `retrieve_logs` returns empty or no logs

**Solutions:**
```python
# Verify job ID exists
list_jobs()

# Check job logs
retrieve_logs(identifier="job_123", log_type="job")

# Increase line count
retrieve_logs(identifier="job_123", num_lines=1000)
```

### Log Size Limits

**Problem:** Logs are truncated or too large

**Solutions:**
```python
# Use pagination for large logs
retrieve_logs_paginated(
    identifier="job_123",
    page=1,
    page_size=500,
    max_size_mb=50
)

# Adjust size limits
retrieve_logs(identifier="job_123", max_size_mb=100)
```

## Platform-Specific Issues

### Windows/macOS Multi-Node

**Problem:** Worker nodes fail to connect on Windows/macOS

**Solution:**
```bash
export RAY_ENABLE_WINDOWS_OR_OSX_CLUSTER=1
ray-mcp
```

### Firewall Issues

**Problem:** Cluster nodes cannot communicate

**Solutions:**
- Allow Ray ports through firewall (10001+, 8265+)
- Use localhost/loopback for local testing
- Check network configuration for multi-machine setups

## Debug Information Collection

### Collect Debug Info

```bash
# Ray status
ray status

# System info
python -c "import sys, ray; print(f'Python: {sys.version}'); print(f'Ray: {ray.__version__}')"

# Process info
ps aux | grep ray

# Port usage
lsof -i :10001
lsof -i :8265
```

### Enable Comprehensive Logging

```bash
export RAY_MCP_LOG_LEVEL=DEBUG
export RAY_LOG_LEVEL=debug
export RAY_DISABLE_USAGE_STATS=1
ray-mcp
```

## Getting Help

If issues persist:

1. Check Ray documentation: https://docs.ray.io/
2. Verify MCP client compatibility
3. Create minimal reproduction case
4. Submit issue with debug information 