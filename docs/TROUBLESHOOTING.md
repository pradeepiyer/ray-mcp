# Troubleshooting

## Common Issues

### 1. Ray not starting
**Problem**: Ray cluster fails to start or connect

**Solutions**:
```bash
# Check Ray installation
uv add ray[default]
# or if using development environment:
uv sync

# Check port availability
ray start --head --port=6379

# Check for existing Ray processes
ray stop
pkill -f ray

# Start with explicit configuration
ray start --head --num-cpus=4 --dashboard-host=0.0.0.0
```

### 2. Job submission fails
**Problem**: Jobs fail to submit or execute

**Solutions**:
```bash
# Verify runtime environment and entrypoint
# Test job submission manually
from ray.job_submission import JobSubmissionClient
client = JobSubmissionClient("http://127.0.0.1:8265")

# Check job dependencies
uv pip list | grep ray
# or: uv tree | grep ray

# Verify script exists and is executable
python my_script.py
```

### 3. MCP connection issues
**Problem**: AI assistant can't connect to Ray MCP server

**Solutions**:
```bash
# Check server logs
ray-mcp

# Verify configuration
cat ~/.config/claude-desktop/claude_desktop_config.json

# Test server directly
ray-mcp --help

# Check process is running
ps aux | grep ray-mcp
```

### 4. "Ray is not initialized" errors
**Problem**: Tools fail with initialization errors

**Solution**:
You must initialize Ray first:
```
"Start a Ray cluster with 4 CPUs"
# or
"Connect to Ray cluster at ray://127.0.0.1:10001"
```

### 5. Permission denied errors
**Problem**: Ray fails to create directories or files

**Solutions**:
```bash
# Check permissions
ls -la /tmp/ray

# Clean up old Ray sessions
ray stop
rm -rf /tmp/ray/session_*

# Start with different temp directory
export RAY_TMPDIR=/home/user/ray_tmp
mkdir -p $RAY_TMPDIR
ray start --head
```

### 6. Memory or resource errors
**Problem**: Out of memory or resource allocation failures

**Solutions**:
```bash
# Start with limited resources
ray start --head --num-cpus=2 --object-store-memory=1000000000

# Check system resources
free -h
df -h

# Monitor Ray resource usage
ray status
```

## Debugging

### Enable Debug Logging
```bash
export RAY_LOG_LEVEL=DEBUG
ray-mcp
```

### Check Ray Dashboard
Open in browser:
```
http://localhost:8265
```

### Ray Status Commands
```bash
# Check cluster status
ray status

# List running jobs
ray job list

# Get job logs
ray job logs <job_id>

# Check Ray processes
ray summary
```

### MCP Server Debugging
```bash
# Run server with verbose output
ray-mcp --log-level DEBUG

# Check MCP protocol communication
# (Enable debug in your MCP client)
```

## Log Locations

### Ray Logs
- **Default location**: `/tmp/ray/session_*/logs/`
- **Dashboard logs**: `/tmp/ray/session_*/logs/dashboard.log`
- **Worker logs**: `/tmp/ray/session_*/logs/worker-*.log`

### Ray MCP Server Logs
- **Stdout/stderr**: Check terminal where `ray-mcp` was started
- **System logs**: Check system logging (varies by OS)

## Performance Issues

### Slow Job Execution
1. Check cluster resources: `ray status`
2. Monitor resource usage in dashboard
3. Optimize job parallelization
4. Check network connectivity for distributed setups

### High Memory Usage
1. Reduce object store memory: `--object-store-memory=500 * 1024 * 1024`
2. Use Ray object references efficiently
3. Clean up unused objects: `ray.shutdown()`

## Getting Help

1. **Check Ray documentation**: https://docs.ray.io/
2. **Ray GitHub issues**: https://github.com/ray-project/ray/issues
3. **MCP specification**: https://spec.modelcontextprotocol.io/
4. **Create issue**: In this repository for Ray MCP Server specific issues

## Known Limitations

- **Log Retrieval**: Actor and node log retrieval has some limitations (job logs fully supported)
- **Authentication**: No built-in authentication (relies on Ray cluster security)
- **Multi-cluster**: Currently supports single cluster per server instance
- **Windows**: Some Ray features may have limited Windows support

## Multi-Node Cluster Issues

### Worker Node Startup Failures
**Problem**: Worker nodes fail to start or connect to the head node.

**Solutions**:
1. **Check Network Connectivity**: Ensure worker nodes can reach the head node
2. **Verify Port Configuration**: Check that head_node_port (default: 10001) is accessible
3. **Resource Availability**: Ensure sufficient CPU/memory resources for worker nodes
4. **Firewall Settings**: Verify that Ray ports are open between nodes

**Debug Steps**:
```bash
# Check worker node status
"Use cluster_info tool to check worker node status and cluster connectivity"

# Check cluster status
"Use cluster_info tool to verify cluster connectivity"

# Check Ray logs
"Check Ray logs in /tmp/ray/session_*/logs/"
```

### Worker Node Process Management
**Problem**: Worker nodes stop unexpectedly or become unresponsive.

**Solutions**:
1. **Process Monitoring**: Use `cluster_info` tool to monitor worker processes
2. **Resource Monitoring**: Check CPU/memory usage on worker nodes
3. **Graceful Shutdown**: Use `stop_ray` to properly shutdown all worker nodes
4. **Force Restart**: If needed, manually kill worker processes and restart

### Configuration Issues
**Problem**: Worker node configuration errors or invalid parameters.

**Solutions**:
1. **Parameter Validation**: Ensure all required parameters (num_cpus) are provided
2. **Resource Limits**: Check that requested resources are available
3. **Node Names**: Ensure unique node names if specified
4. **Custom Resources**: Verify custom resource syntax and availability 