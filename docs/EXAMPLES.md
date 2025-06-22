# Examples and Usage Patterns

## Basic Usage Examples

Once connected through an AI assistant, you **must first initialize Ray**:

### Initialize Ray (required first step)
```
"Start a Ray cluster with 4 CPUs"
"Start a Ray cluster with 8 CPUs and 2 GPUs"
"Connect to Ray cluster at ray://127.0.0.1:10001"
```

### Then use other features
```
"Submit a job with entrypoint 'python examples/simple_job.py'"
"Check cluster status"
"List all running jobs"
"Get resource usage information"
```

**Important**: If you try to use tools like `submit_job`, `list_jobs`, etc. before initializing Ray, you'll get an error message: "Ray is not initialized. Please start Ray first."

## Example Scripts

The `examples/` directory contains sample Ray applications:

### Simple Job (`examples/simple_job.py`)
Demonstrates basic Ray remote functions including:
- Monte Carlo pi estimation using multiple workers
- Slow tasks for monitoring job execution

```bash
# Run directly with Ray
ray start --head
python examples/simple_job.py
ray stop

# Or submit through MCP server
# "Submit a job with entrypoint 'python examples/simple_job.py'"
```

### Actor Example (`examples/actor_example.py`)
Shows Ray actor usage including:
- Counter actors with state management
- Data processing actors
- Actor lifecycle management

## Server Behavior

### Ray Initialization
The Ray MCP Server follows a **manual initialization** approach:

- **Server Startup**: Ray is NOT automatically initialized when the server starts
- **Explicit Initialization**: You must use `start_ray` or `connect_ray` tools to initialize Ray
- **Tool Dependencies**: Most tools require Ray to be initialized first
- **Clear Error Messages**: Tools will fail with helpful error messages if Ray is not initialized

## Workflow Examples

### Complete Job Lifecycle
1. Start Ray: `"Start a Ray cluster with 4 CPUs"`
2. Submit job: `"Submit a job with entrypoint 'python my_script.py'"`
3. Monitor: `"Check job status for job_id abc123"`
4. Get logs: `"Get logs for job abc123"`
5. Stop Ray: `"Stop the Ray cluster"`

### Actor Management
1. Start Ray cluster
2. Submit job that creates actors
3. List actors: `"List all actors in the cluster"`
4. Kill specific actor: `"Kill actor with ID xyz789"`

### Performance Monitoring
1. Get cluster status: `"Get cluster status"`
2. Check resources: `"Get cluster resource information"`
3. Performance metrics: `"Get performance metrics"`
4. Health check: `"Perform cluster health check"` 