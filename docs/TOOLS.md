# Tools Reference

This document provides a comprehensive reference for all tools available in the Ray MCP Server.

## Tool Overview

The Ray MCP Server provides 8 core tools for managing Ray clusters, jobs, and distributed computing workflows:

### Cluster Management Tools
- `init_ray` - Initialize or connect to Ray clusters
- `stop_ray` - Gracefully shutdown Ray clusters
- `inspect_ray` - Get comprehensive cluster information

### Job Management Tools
- `submit_job` - Submit jobs to Ray clusters
- `list_jobs` - List all jobs in the cluster
- `inspect_job` - Get detailed job information
- `cancel_job` - Cancel running jobs

### Logging & Debugging Tools
- `retrieve_logs` - Retrieve logs from jobs, actors, or nodes

## Tool Details

### 1. init_ray

Initialize a new Ray cluster or connect to an existing one.

**Parameters:**
```json
{
  "num_cpus": {
    "type": "integer",
    "description": "Number of CPUs for the head node",
    "default": 1
  },
  "num_gpus": {
    "type": "integer",
    "description": "Number of GPUs for the head node",
    "default": 0
  },
  "object_store_memory": {
    "type": "integer",
    "description": "Object store memory in bytes",
    "default": 1000000000
  },
  "worker_nodes": {
    "type": "array",
    "description": "List of worker node configurations",
    "items": {
      "type": "object",
      "properties": {
        "num_cpus": {"type": "integer"},
        "num_gpus": {"type": "integer"},
        "object_store_memory": {"type": "integer"},
        "node_name": {"type": "string"},
        "resources": {"type": "object"}
      }
    }
  },
  "head_node_port": {
    "type": "integer",
    "description": "Port for the head node",
    "default": "auto"
  },
  "dashboard_port": {
    "type": "integer",
    "description": "Port for the Ray dashboard",
    "default": "auto"
  },
  "head_node_host": {
    "type": "string",
    "description": "Host for the head node",
    "default": "127.0.0.1"
  }
}
```

**Example Usage:**
```json
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4,
    "worker_nodes": [
      {
        "num_cpus": 2,
        "node_name": "worker-1"
      }
    ]
  }
}
```

**Response:**
```json
{
  "status": "started",
  "message": "Ray cluster started successfully",
  "cluster_address": "ray://127.0.0.1:30000",
  "dashboard_url": "http://127.0.0.1:8265",
  "node_id": "abc123...",
  "session_name": "session_2024_01_01_12_00_00_123456",
  "job_client_status": "ready",
  "worker_nodes": [
    {
      "status": "started",
      "node_name": "worker-1",
      "message": "Worker node 'worker-1' started successfully",
      "process_id": 12345,
      "config": {
        "num_cpus": 2,
        "num_gpus": 0,
        "object_store_memory": 524288000,
        "node_name": "worker-1"
      }
    }
  ]
}
```

**CI Optimization:** In CI environments, use `"worker_nodes": []` for head node only configuration.

### 2. stop_ray

Gracefully shutdown the current Ray cluster.

**Parameters:**
```json
{}
```

**Example Usage:**
```json
{
  "tool": "stop_ray",
  "arguments": {}
}
```

**Response:**
```json
{
  "status": "stopped",
  "message": "Ray cluster stopped successfully",
  "stopped_workers": [
    {
      "node_name": "worker-1",
      "status": "stopped",
      "message": "Worker node 'worker-1' stopped successfully"
    }
  ]
}
```

### 3. inspect_ray

Get comprehensive information about the current Ray cluster.

**Parameters:**
```json
{}
```

**Example Usage:**
```json
{
  "tool": "inspect_ray",
  "arguments": {}
}
```

**Response:**
```json
{
  "status": "success",
  "timestamp": 1704110400.123,
  "cluster_overview": {
    "status": "running",
    "address": "ray://127.0.0.1:30000",
    "total_nodes": 3,
    "alive_nodes": 3,
    "total_workers": 2,
    "running_workers": 2
  },
  "resources": {
    "cluster_resources": {
      "CPU": 6.0,
      "object_store_memory": 4000000000.0,
      "memory": 16000000000.0
    },
    "available_resources": {
      "CPU": 4.0,
      "object_store_memory": 3000000000.0,
      "memory": 12000000000.0
    }
  },
  "health_check": {
    "overall_status": "excellent",
    "health_score": 95.0,
    "checks": {
      "all_nodes_alive": true,
      "has_available_cpu": true,
      "has_available_memory": true,
      "cluster_responsive": true
    },
    "recommendations": [
      "Cluster health is good. No immediate action required."
    ]
  },
  "worker_nodes": [
    {
      "status": "started",
      "node_name": "worker-1",
      "config": {
        "num_cpus": 2,
        "num_gpus": 0,
        "object_store_memory": 524288000
      }
    }
  ]
}
```

### 4. submit_job

Submit a new job to the Ray cluster.

**Parameters:**
```json
{
  "entrypoint": {
    "type": "string",
    "description": "Command to execute for the job"
  },
  "runtime_env": {
    "type": "object",
    "description": "Runtime environment configuration",
    "properties": {
      "pip": {
        "type": "array",
        "items": {"type": "string"},
        "description": "List of pip packages to install"
      },
      "env_vars": {
        "type": "object",
        "description": "Environment variables"
      },
      "working_dir": {
        "type": "string",
        "description": "Working directory for the job"
      }
    }
  }
}
```

**Example Usage:**
```json
{
  "tool": "submit_job",
  "arguments": {
    "entrypoint": "python examples/simple_job.py",
    "runtime_env": {
      "pip": ["numpy", "pandas"]
    }
  }
}
```

**Response:**
```json
{
  "status": "submitted",
  "job_id": "raysubmit_abc123def456",
  "message": "Job submitted successfully"
}
```

### 5. list_jobs

List all jobs in the cluster.

**Parameters:**
```json
{}
```

**Example Usage:**
```json
{
  "tool": "list_jobs",
  "arguments": {}
}
```

**Response:**
```json
{
  "status": "success",
  "jobs": [
    {
      "job_id": "raysubmit_abc123def456",
      "status": "SUCCEEDED",
      "entrypoint": "python examples/simple_job.py",
      "submission_id": "raysubmit_abc123def456",
      "start_time": "2024-01-01T12:00:00Z",
      "end_time": "2024-01-01T12:01:30Z"
    },
    {
      "job_id": "raysubmit_def456ghi789",
      "status": "RUNNING",
      "entrypoint": "python examples/long_running_job.py",
      "submission_id": "raysubmit_def456ghi789",
      "start_time": "2024-01-01T12:05:00Z",
      "end_time": null
    }
  ]
}
```

### 6. inspect_job

Get detailed information about a specific job.

**Parameters:**
```json
{
  "job_id": {
    "type": "string",
    "description": "ID of the job to inspect"
  },
  "mode": {
    "type": "string",
    "description": "Inspection mode: 'status', 'logs', or 'debug'",
    "enum": ["status", "logs", "debug"],
    "default": "status"
  }
}
```

**Example Usage:**
```json
{
  "tool": "inspect_job",
  "arguments": {
    "job_id": "raysubmit_abc123def456",
    "mode": "debug"
  }
}
```

**Response (status mode):**
```json
{
  "status": "success",
  "job_id": "raysubmit_abc123def456",
  "job_status": "SUCCEEDED",
  "entrypoint": "python examples/simple_job.py",
  "submission_id": "raysubmit_abc123def456",
  "start_time": "2024-01-01T12:00:00Z",
  "end_time": "2024-01-01T12:01:30Z",
  "runtime_env": {},
  "message": "Job completed successfully"
}
```

**Response (debug mode):**
```json
{
  "status": "success",
  "job_id": "raysubmit_abc123def456",
  "job_status": "FAILED",
  "debug_info": {
    "error_message": "ModuleNotFoundError: No module named 'missing_package'",
    "stack_trace": "...",
    "runtime_env": {},
    "entrypoint": "python examples/failing_job.py",
    "submission_time": "2024-01-01T12:00:00Z",
    "start_time": "2024-01-01T12:00:05Z",
    "end_time": "2024-01-01T12:00:10Z"
  }
}
```

### 7. cancel_job

Cancel a running or queued job.

**Parameters:**
```json
{
  "job_id": {
    "type": "string",
    "description": "ID of the job to cancel"
  }
}
```

**Example Usage:**
```json
{
  "tool": "cancel_job",
  "arguments": {
    "job_id": "raysubmit_abc123def456"
  }
}
```

**Response:**
```json
{
  "status": "cancelled",
  "job_id": "raysubmit_abc123def456",
  "message": "Job cancelled successfully"
}
```

### 8. retrieve_logs

Retrieve logs from jobs, actors, or nodes with optional error analysis.

**Parameters:**
```json
{
  "identifier": {
    "type": "string",
    "description": "Job ID, actor ID, or node ID"
  },
  "log_type": {
    "type": "string",
    "description": "Type of logs to retrieve",
    "enum": ["job", "actor", "node"],
    "default": "job"
  },
  "num_lines": {
    "type": "integer",
    "description": "Number of log lines to retrieve",
    "default": 100
  },
  "include_errors": {
    "type": "boolean",
    "description": "Include error analysis",
    "default": false
  }
}
```

**Example Usage:**
```json
{
  "tool": "retrieve_logs",
  "arguments": {
    "identifier": "raysubmit_abc123def456",
    "log_type": "job",
    "num_lines": 200,
    "include_errors": true
  }
}
```

**Response:**
```json
{
  "status": "success",
  "log_type": "job",
  "identifier": "raysubmit_abc123def456",
  "logs": [
    "2024-01-01 12:00:05,123 INFO: Starting job execution",
    "2024-01-01 12:00:05,456 INFO: Initializing Ray tasks",
    "2024-01-01 12:00:06,789 INFO: Task completed successfully",
    "2024-01-01 12:00:07,012 INFO: Job finished"
  ],
  "error_analysis": {
    "has_errors": false,
    "error_count": 0,
    "error_lines": []
  }
}
```

**Response (with errors):**
```json
{
  "status": "success",
  "log_type": "job",
  "identifier": "raysubmit_abc123def456",
  "logs": [
    "2024-01-01 12:00:05,123 INFO: Starting job execution",
    "2024-01-01 12:00:05,456 ERROR: ModuleNotFoundError: No module named 'missing_package'",
    "2024-01-01 12:00:05,789 ERROR: Traceback (most recent call last):",
    "2024-01-01 12:00:05,890 ERROR:   File \"examples/failing_job.py\", line 5, in <module>",
    "2024-01-01 12:00:05,991 ERROR:     import missing_package",
    "2024-01-01 12:00:06,092 ERROR: ModuleNotFoundError: No module named 'missing_package'"
  ],
  "error_analysis": {
    "has_errors": true,
    "error_count": 1,
    "error_lines": [
      "ModuleNotFoundError: No module named 'missing_package'"
    ],
    "error_summary": "Job failed due to missing Python package 'missing_package'"
  }
}
```

## Environment-Specific Optimizations

### CI Environment

For CI environments, the tools automatically optimize resource usage:

**init_ray in CI:**
```json
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 1,
    "worker_nodes": []  // Head node only
  }
}
```

**Benefits:**
- Minimal resource usage (1 CPU)
- Fast startup and shutdown
- Reduced wait times (10s vs 30s)
- Automatic environment detection

### Local Development

For local development, use full cluster configuration:

**init_ray in Local:**
```json
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 2,
    "worker_nodes": null  // Use defaults (2 workers)
  }
}
```

**Benefits:**
- Comprehensive testing
- Full cluster functionality
- Longer wait times for stability
- Complete resource utilization

## Error Handling

All tools return consistent error responses:

**Error Response Format:**
```json
{
  "status": "error",
  "message": "Error description",
  "error": "Detailed error information"
}
```

**Common Error Scenarios:**

1. **Ray not initialized:**
```json
{
  "status": "error",
  "message": "Ray is not initialized. Please start Ray first.",
  "error": "Ray cluster not found"
}
```

2. **Job not found:**
```json
{
  "status": "error",
  "message": "Job not found",
  "error": "Job ID 'invalid_id' does not exist"
}
```

3. **Resource conflicts:**
```json
{
  "status": "error",
  "message": "Failed to start worker node",
  "error": "Resource configuration conflicts with head node"
}
```

## Performance Considerations

### Resource Allocation

- **Head Node**: Minimum 1 CPU, recommended 2+ CPUs for production
- **Worker Nodes**: Configure based on workload requirements
- **Memory**: Object store memory should be 25-50% of total system memory
- **Network**: Ensure proper connectivity for multi-node clusters

### Job Optimization

- **Runtime Environment**: Use specific package versions for reproducibility
- **Entrypoint**: Use absolute paths for reliable execution
- **Resource Requirements**: Specify resource requirements in job code
- **Error Handling**: Implement proper error handling in job scripts

### Monitoring

- **Regular Inspection**: Use `inspect_ray` to monitor cluster health
- **Job Monitoring**: Track job status and logs for debugging
- **Resource Usage**: Monitor CPU and memory utilization
- **Health Checks**: Follow health recommendations from `inspect_ray`

## Best Practices

### 1. Cluster Management

- Start with minimal resources and scale up as needed
- Use environment-specific configurations (CI vs local)
- Always clean up clusters with `stop_ray`
- Monitor cluster health regularly

### 2. Job Management

- Use descriptive job entrypoints
- Implement proper error handling in job scripts
- Monitor job status and logs
- Cancel long-running jobs when appropriate

### 3. Debugging

- Use `inspect_job` with `mode: "debug"` for detailed information
- Retrieve logs with error analysis for failed jobs
- Check cluster status when jobs fail
- Use health recommendations for optimization

### 4. Performance

- Configure appropriate resource allocation
- Use runtime environments for dependency management
- Monitor resource utilization
- Follow performance best practices for Ray applications

## Tool Integration

The tools are designed to work together seamlessly:

**Typical Workflow:**
1. `init_ray` - Start cluster
2. `submit_job` - Submit jobs
3. `inspect_job` - Monitor progress
4. `retrieve_logs` - Debug issues
5. `stop_ray` - Clean up

**Error Recovery:**
1. `inspect_ray` - Check cluster status
2. `inspect_job` - Get job details
3. `retrieve_logs` - Analyze errors
4. `cancel_job` - Cancel problematic jobs
5. `submit_job` - Resubmit with fixes

This comprehensive tool set provides everything needed to manage Ray clusters effectively across different environments and use cases.