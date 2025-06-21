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
git clone https://github.com/pradeepiyer/ray-mcp.git
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
- `tune_hyperparameters` - Tune hyperparameters using Ray Tune
- `deploy_model` - Deploy a model using Ray Serve
- `list_deployments` - List all model deployments

### Data Processing Operations
- `create_dataset` - Create a Ray dataset
- `transform_data` - Transform data using Ray Data
- `batch_inference` - Run batch inference on a dataset

### Enhanced Monitoring
- `performance_metrics` - Get detailed cluster performance metrics
- `health_check` - Perform comprehensive cluster health check
- `optimize_config` - Get cluster optimization recommendations

### Workflow & Orchestration
- `create_workflow` - Create a Ray workflow
- `schedule_job` - Schedule a job to run periodically

### Backup & Recovery
- `backup_cluster` - Backup cluster state
- `restore_cluster` - Restore cluster from backup

## Tool Parameters

### start_ray
```json
{
  "num_cpus": 4,              // Number of CPUs to allocate (default: 4)
  "num_gpus": 1,              // Number of GPUs to allocate  
  "object_store_memory": 1000000000  // Object store memory in bytes
}
```

### connect_ray
```json
{
  "address": "ray://127.0.0.1:10001"  // Required: Ray cluster address
}
```

**Supported address formats:**
- `ray://127.0.0.1:10001` (recommended)
- `127.0.0.1:10001`
- `ray://head-node-ip:10001`
- `ray://cluster.example.com:10001`

### submit_job
```json
{
  "entrypoint": "python my_script.py",  // Required: command to run
  "runtime_env": {                      // Optional: runtime environment
    "pip": ["numpy", "pandas"],
    "env_vars": {"MY_VAR": "value"}
  },
  "job_id": "my_job_123",              // Optional: custom job ID
  "metadata": {                        // Optional: job metadata
    "team": "data-science",
    "project": "experiment-1"
  }
}
```

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

## Configuration

### Environment Variables
- `RAY_ADDRESS` - Ray cluster address (used by tools when provided, but doesn't auto-initialize Ray)
- `RAY_DASHBOARD_HOST` - Dashboard host (default: 0.0.0.0)
- `RAY_DASHBOARD_PORT` - Dashboard port (default: 8265)

### Runtime Environment Support
The server supports Ray's runtime environment features:
- Python dependencies (`pip`, `conda`)
- Environment variables
- Working directory specification
- Container images

## Development

### Running Tests
```bash
pip install -e .
pytest tests/
```

### Code Formatting
```bash
black ray_mcp/
isort ray_mcp/
```

### Type Checking
```bash
pyright .
```

## Architecture

```
ray_mcp/
├── __init__.py          # Package initialization
├── main.py              # MCP server entry point and handlers
├── ray_manager.py       # Core Ray cluster management logic
├── tools.py             # Individual tool function implementations
└── types.py             # Type definitions

examples/
├── simple_job.py        # Basic Ray job example
└── actor_example.py     # Ray actor usage example

tests/
├── test_mcp_tools.py           # MCP tool call tests
├── test_ray_manager.py         # Ray manager unit tests
├── test_ray_manager_methods.py # Detailed method tests
├── test_integration.py         # Integration tests
└── README.md                   # Test documentation

config/
├── claude_desktop_config.json # Claude Desktop configuration
├── mcp_server_config.json     # Comprehensive config examples
└── README.md                  # Configuration guide
```

### Key Components

- **MCP Server**: Main server handling MCP protocol communication
- **RayManager**: Core class managing Ray cluster operations
- **Tool Functions**: Individual async functions for each MCP tool
- **Error Handling**: Comprehensive error handling and status reporting

## Limitations

- **Log Retrieval**: Actor and node log retrieval has some limitations (job logs fully supported)
- **Cluster Scaling**: Auto-scaling depends on Ray cluster autoscaler configuration
- **Authentication**: No built-in authentication (relies on Ray cluster security)
- **Multi-cluster**: Currently supports single cluster per server instance

## Troubleshooting

### Common Issues

1. **Ray not starting**: Check Ray installation and port availability
   ```bash
   ray start --head --port=6379
   ```

2. **Job submission fails**: Verify runtime environment and entrypoint
   ```python
   # Test job submission manually
   from ray.job_submission import JobSubmissionClient
   client = JobSubmissionClient("http://127.0.0.1:8265")
   ```

3. **MCP connection issues**: Check server logs and client configuration
   ```bash
   ray-mcp
   ```

### Debugging

Enable debug logging:
```bash
export RAY_LOG_LEVEL=DEBUG
ray-mcp
```

Check Ray dashboard:
```
http://localhost:8265
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Related Projects

- [Ray](https://github.com/ray-project/ray) - The underlying distributed computing framework
- [Model Context Protocol](https://github.com/modelcontextprotocol) - The protocol specification
- [Claude Desktop](https://claude.ai/desktop) - AI assistant supporting MCP

## Support

- Ray Documentation: https://docs.ray.io/
- MCP Specification: https://spec.modelcontextprotocol.io/
- Issues: Create an issue in this repository 