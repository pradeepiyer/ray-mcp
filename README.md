# MCP Ray Server

A Model Context Protocol (MCP) server for interacting with [Ray](https://github.com/ray-project/ray) distributed computing clusters. This server provides AI assistants with tools to manage Ray clusters, submit jobs, monitor resources, and perform various Ray operations.

## Features

### Cluster Management
- **Start Ray clusters** - Initialize new local Ray clusters with custom resources (default: 4 CPUs)
- **Connect to existing clusters** - Connect to pre-existing Ray clusters via address
- **Cluster status monitoring** - Get real-time cluster information and resource usage
- **Node management** - List and monitor cluster nodes
- **Resource monitoring** - Track CPU, GPU, memory, and custom resource usage

### Job Management  
- **Job submission** - Submit Python scripts and applications to Ray clusters
- **Job monitoring** - List, track, and get detailed status of running jobs
- **Job control** - Cancel or stop running jobs
- **Log retrieval** - Access job logs and outputs

### Actor Management
- **Actor listing** - View all actors running in the cluster
- **Actor control** - Kill specific actors with restart options
- **Actor monitoring** - Track actor states and resources

### Machine Learning & AI
- **Model training** - Distributed model training with Ray Train
- **Hyperparameter tuning** - Optimize model parameters with Ray Tune
- **Model deployment** - Deploy models with Ray Serve
- **Batch inference** - Large-scale batch inference on datasets

### Data Processing
- **Dataset creation** - Create Ray datasets from various sources
- **Data transformation** - Transform data using Ray Data
- **Batch processing** - Process large datasets efficiently

### Advanced Features
- **Performance monitoring** - Detailed cluster performance metrics
- **Health checks** - Comprehensive cluster health assessment
- **Configuration optimization** - Get cluster optimization recommendations
- **Workflow orchestration** - Create and manage Ray workflows
- **Job scheduling** - Schedule jobs with cron expressions
- **Backup & recovery** - Backup and restore cluster state

### Scaling Operations
- **Cluster scaling** - Scale clusters up or down (with autoscaler support)
- **Resource allocation** - Configure CPU, GPU, and memory allocation

## Installation

### Prerequisites
- Python 3.8 or higher
- Ray 2.30.0 or higher (current latest: 2.47.1)
- MCP SDK 1.0.0 or higher

### Install from source
```bash
git clone <repository-url>
cd ray-mcp
pip install -e .
```

### Install dependencies only
```bash
pip install -r requirements.txt
```

## Quick Start

### 1. Run the MCP server directly
```bash
# Using the console script (recommended)
ray-mcp

# Or using Python module
python -m ray_mcp
```

**Note**: The server starts without initializing Ray. You must use the `start_ray` or `connect_ray` tools to initialize Ray before using other features.

### 2. Configure for use with AI assistants
Add to your MCP client configuration (e.g., Claude Desktop):

```json
{
  "mcpServers": {
    "ray-mcp": {
      "command": "/path/to/your/venv/bin/ray-mcp",
      "env": {
        "RAY_ADDRESS": "",
        "RAY_DASHBOARD_HOST": "0.0.0.0"
      }
    }
  }
}
```

### 3. Basic usage examples
Once connected through an AI assistant, you **must first initialize Ray**:

**Initialize Ray (required first step):**
```
"Start a Ray cluster with 4 CPUs"
"Start a Ray cluster with 8 CPUs and 2 GPUs"
"Connect to Ray cluster at ray://127.0.0.1:10001"
```

**Then use other features:**
```
"Submit a job with entrypoint 'python examples/simple_job.py'"
"Check cluster status"
"List all running jobs"
"Get resource usage information"
```

**Important**: If you try to use tools like `submit_job`, `list_jobs`, etc. before initializing Ray, you'll get an error message: "Ray is not initialized. Please start Ray first."

## Server Behavior

### Ray Initialization
The MCP Ray Server follows a **manual initialization** approach:

- **Server Startup**: Ray is NOT automatically initialized when the server starts
- **Explicit Initialization**: You must use `start_ray` or `connect_ray` tools to initialize Ray
- **Tool Dependencies**: Most tools require Ray to be initialized first
- **Clear Error Messages**: Tools will fail with helpful error messages if Ray is not initialized

### Tool Categories by Ray Dependency

**✅ Works without Ray initialization:**
- `cluster_status` - Shows "not_running" when Ray is not initialized

**❌ Requires Ray initialization:**
- All job management tools (`submit_job`, `list_jobs`, etc.)
- All actor management tools (`list_actors`, `kill_actor`)
- All ML/AI tools (`train_model`, `deploy_model`, etc.)
- All data processing tools (`create_dataset`, `batch_inference`, etc.)
- All monitoring tools (`performance_metrics`, `health_check`, etc.)

**🔧 Ray initialization tools:**
- `start_ray` - Start a new Ray cluster
- `connect_ray` - Connect to an existing Ray cluster
- `stop_ray` - Stop the current Ray cluster

## Available Tools

The server provides **30 tools** for comprehensive Ray cluster management:

### Cluster Operations
- `start_ray` - Start a new Ray cluster (head node)
- `connect_ray` - Connect to an existing Ray cluster
- `stop_ray` - Stop the current Ray cluster
- `cluster_status` - Get comprehensive cluster status
- `cluster_resources` - Get resource usage information
- `cluster_nodes` - List all cluster nodes
- `scale_cluster` - Scale the cluster to specified size

### Job Operations
- `submit_job` - Submit a new job to the cluster
- `list_jobs` - List all jobs (running, completed, failed)
- `job_status` - Get detailed status of a specific job
- `cancel_job` - Cancel a running or queued job
- `monitor_job` - Monitor job progress
- `debug_job` - Debug a job with detailed information
- `get_logs` - Retrieve job logs and outputs

### Actor Operations
- `list_actors` - List all actors in the cluster
- `kill_actor` - Terminate a specific actor

### Machine Learning & AI Operations
- `train_model` - Train a machine learning model using Ray
- `