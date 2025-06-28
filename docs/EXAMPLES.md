# Ray MCP Server Examples

This document provides comprehensive examples for using the Ray MCP Server with various distributed computing scenarios.

## Quick Start Examples

### Basic Single-Node Cluster

Start a simple Ray cluster with basic resources:

```json
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4,
    "num_gpus": 1
  }
}
```

### Multi-Node Cluster

Start a multi-node cluster with worker nodes:

```json
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 2,
    "worker_nodes": [
      {
        "num_cpus": 2,
        "num_gpus": 0,
        "node_name": "cpu-worker-1"
      },
      {
        "num_cpus": 4,
        "num_gpus": 1,
        "node_name": "gpu-worker-1"
      }
    ]
  }
}
```

### Connect to Existing Cluster

Connect to an existing Ray cluster:

```json
{
  "tool": "init_ray",
  "arguments": {
    "address": "ray://192.168.1.100:10001"
  }
}
```

## Example Files

The `examples/` directory contains working examples demonstrating various Ray capabilities:

### simple_job.py

Basic Ray job example demonstrating simple distributed computation.

**Key Features**:
- Basic Ray remote function usage
- Simple data processing
- Error handling

**Usage**:
```json
{
  "tool": "submit_job",
  "arguments": {
    "entrypoint": "python examples/simple_job.py"
  }
}
```

### multi_node_cluster.py

Multi-node cluster demonstration with worker node management.

**Key Features**:
- Multi-node cluster setup
- Worker node configuration
- Resource distribution across nodes

**Usage**:
```json
{
  "tool": "submit_job",
  "arguments": {
    "entrypoint": "python examples/multi_node_cluster.py"
  }
}
```

### actor_example.py

Actor-based computation example.

**Key Features**:
- Ray actor creation and management
- Stateful distributed computation
- Actor lifecycle management

**Usage**:
```json
{
  "tool": "submit_job",
  "arguments": {
    "entrypoint": "python examples/actor_example.py"
  }
}
```

### data_pipeline.py

Data processing pipeline example.

**Key Features**:
- Multi-stage data processing
- Pipeline orchestration
- Data flow management

**Usage**:
```json
{
  "tool": "submit_job",
  "arguments": {
    "entrypoint": "python examples/data_pipeline.py"
  }
}
```

### distributed_training.py

Distributed machine learning example.

**Key Features**:
- Distributed model training
- Parameter server pattern
- Training coordination

**Usage**:
```json
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

### workflow_orchestration.py

Complex workflow orchestration example.

**Key Features**:
- Complex workflow management
- Task dependencies
- Error recovery

**Usage**:
```json
{
  "tool": "submit_job",
  "arguments": {
    "entrypoint": "python examples/workflow_orchestration.py"
  }
}
```

### connect_existing_cluster.py

Example demonstrating connection to existing Ray clusters.

**Key Features**:
- Cluster connection management
- Resource discovery
- Connection validation

**Usage**:
```json
{
  "tool": "submit_job",
  "arguments": {
    "entrypoint": "python examples/connect_existing_cluster.py"
  }
}
```

### log_retrieval_example.py

Log retrieval and analysis examples.

**Key Features**:
- Comprehensive log retrieval
- Error analysis
- Log filtering and processing

**Usage**:
```json
{
  "tool": "submit_job",
  "arguments": {
    "entrypoint": "python examples/log_retrieval_example.py"
  }
}
```

## Complete Workflow Examples

### 1. Basic Job Submission Workflow

```json
// 1. Initialize cluster
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4
  }
}

// 2. Check cluster status
{
  "tool": "cluster_info",
  "arguments": {}
}

// 3. Submit a job
{
  "tool": "submit_job",
  "arguments": {
    "entrypoint": "python examples/simple_job.py"
  }
}

// 4. Monitor job status
{
  "tool": "list_jobs",
  "arguments": {}
}

// 5. Get job logs
{
  "tool": "retrieve_logs",
  "arguments": {
    "identifier": "raysubmit_1234567890",
    "log_type": "job",
    "include_errors": true
  }
}

// 6. Stop cluster
{
  "tool": "stop_ray",
  "arguments": {}
}
```

### 2. Multi-Node Distributed Training Workflow

```json
// 1. Start multi-node cluster
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4,
    "num_gpus": 1,
    "worker_nodes": [
      {
        "num_cpus": 8,
        "num_gpus": 2,
        "node_name": "gpu-worker-1"
      },
      {
        "num_cpus": 8,
        "num_gpus": 2,
        "node_name": "gpu-worker-2"
      }
    ]
  }
}

// 2. Submit distributed training job
{
  "tool": "submit_job",
  "arguments": {
    "entrypoint": "python examples/distributed_training.py",
    "runtime_env": {
      "pip": ["torch", "numpy", "scikit-learn"]
    }
  }
}

// 3. Monitor training progress
{
  "tool": "job_inspect",
  "arguments": {
    "job_id": "raysubmit_1234567890",
    "mode": "logs"
  }
}

// 4. List actors (training workers)
{
  "tool": "list_actors",
  "arguments": {}
}
```

### 3. Data Pipeline Workflow

```json
// 1. Start cluster with data processing resources
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 8,
    "object_store_memory": 2000000000,
    "worker_nodes": [
      {
        "num_cpus": 4,
        "object_store_memory": 1000000000,
        "node_name": "data-worker-1"
      }
    ]
  }
}

// 2. Submit data pipeline job
{
  "tool": "submit_job",
  "arguments": {
    "entrypoint": "python examples/data_pipeline.py",
    "runtime_env": {
      "pip": ["pandas", "numpy", "scikit-learn"]
    }
  }
}

// 3. Monitor pipeline progress
{
  "tool": "job_inspect",
  "arguments": {
    "job_id": "raysubmit_1234567890",
    "mode": "debug"
  }
}
```

## Advanced Configuration Examples

### Custom Resource Configuration

```json
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4,
    "num_gpus": 2,
    "object_store_memory": 4000000000,
    "worker_nodes": [
      {
        "num_cpus": 8,
        "num_gpus": 4,
        "object_store_memory": 8000000000,
        "resources": {
          "custom_gpu": 2,
          "high_memory": 1
        },
        "node_name": "high-performance-worker"
      }
    ],
    "head_node_port": 10001,
    "dashboard_port": 8265,
    "head_node_host": "0.0.0.0"
  }
}
```

### Runtime Environment Configuration

```json
{
  "tool": "submit_job",
  "arguments": {
    "entrypoint": "python examples/distributed_training.py",
    "runtime_env": {
      "pip": ["torch==2.0.0", "numpy==1.24.0", "scikit-learn==1.3.0"],
      "env_vars": {
        "CUDA_VISIBLE_DEVICES": "0,1",
        "OMP_NUM_THREADS": "4"
      },
      "working_dir": "/path/to/code"
    }
  }
}
```

## Monitoring and Debugging Examples

### Comprehensive Job Inspection

```json
{
  "tool": "job_inspect",
  "arguments": {
    "job_id": "raysubmit_1234567890",
    "mode": "debug"
  }
}
```

### Actor Management

```json
// List all actors
{
  "tool": "list_actors",
  "arguments": {}
}

// Kill specific actor
{
  "tool": "kill_actor",
  "arguments": {
    "actor_id": "actor_1234567890",
    "no_restart": true
  }
}
```

### Log Analysis

```json
// Get job logs with error analysis
{
  "tool": "retrieve_logs",
  "arguments": {
    "identifier": "raysubmit_1234567890",
    "log_type": "job",
    "num_lines": 500,
    "include_errors": true
  }
}

// Get actor logs
{
  "tool": "retrieve_logs",
  "arguments": {
    "identifier": "actor_1234567890",
    "log_type": "actor",
    "num_lines": 200
  }
}

// Get node logs
{
  "tool": "retrieve_logs",
  "arguments": {
    "identifier": "node_1234567890",
    "log_type": "node",
    "num_lines": 100
  }
}
```

## Best Practices

1. **Start with simple examples** before moving to complex workflows
2. **Monitor resource usage** using `cluster_info` regularly
3. **Use appropriate runtime environments** for your specific use case
4. **Implement proper error handling** in your Ray applications
5. **Clean up resources** by stopping clusters when done
6. **Use enhanced output mode** for better debugging and monitoring

## Troubleshooting

### Common Issues

1. **Resource conflicts**: Ensure worker node resources don't exceed head node capacity
2. **Port conflicts**: Use automatic port allocation or specify unique ports
3. **Memory issues**: Configure appropriate object store memory for your workload
4. **Network connectivity**: Ensure proper network configuration for multi-node clusters

### Debugging Commands

```json
// Check cluster health
{
  "tool": "cluster_info",
  "arguments": {}
}

// Get detailed job information
{
  "tool": "job_inspect",
  "arguments": {
    "job_id": "raysubmit_1234567890",
    "mode": "debug"
  }
}

// Retrieve comprehensive logs
{
  "tool": "retrieve_logs",
  "arguments": {
    "identifier": "raysubmit_1234567890",
    "log_type": "job",
    "include_errors": true
  }
}
```
