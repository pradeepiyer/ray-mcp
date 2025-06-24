# Examples and Usage Patterns

## MCP Server Usage

When using the Ray MCP Server through an AI assistant, you **must first initialize Ray**:

### Initialize Ray (required for MCP server)
```
"Start a Ray cluster with 4 CPUs"
"Start a Ray cluster with 8 CPUs and 2 GPUs"
"Connect to Ray cluster at ray://127.0.0.1:10001"
```

### Then use MCP server features
```
"Submit a job with entrypoint 'python examples/simple_job.py'"
"Check cluster status"
"List all running jobs"
"Get resource usage information"
```

**Important**: If you try to use MCP tools like `submit_job`, `list_jobs`, etc. before initializing Ray, you'll get an error message: "Ray is not initialized. Please start Ray first."

## Direct Script Execution

All example scripts can also be run directly without the MCP server. They will automatically initialize Ray if needed:

```bash
# Examples automatically handle Ray initialization
python examples/simple_job.py
python examples/actor_example.py
python examples/data_pipeline.py
# ... etc
```

## Example Scripts

The `examples/` directory contains 5 comprehensive Ray applications demonstrating different patterns and use cases:

### 1. Simple Job (`examples/simple_job.py`)
**Purpose**: Demonstrates basic Ray remote functions and job execution patterns.

**Features**:
- Basic Ray remote function decoration and execution
- Cluster resource inspection and monitoring
- Proper Ray initialization handling in job context
- Error handling and cleanup patterns

**Key Concepts**:
- `@ray.remote` function decoration
- `ray.get()` for retrieving results
- Cluster resource management
- Job lifecycle management



### 2. Actor Example (`examples/actor_example.py`)
**Purpose**: Shows Ray actor usage patterns for stateful distributed computing.

**Features**:
- Stateful `Counter` actors with increment/decrement operations
- `DataProcessor` actors for parallel data processing
- Actor lifecycle management and method invocation
- Multiple actor coordination patterns

**Key Concepts**:
- `@ray.remote` class decoration for actors
- Stateful distributed objects
- Actor method invocation with `.remote()`
- Parallel actor operations

**Actors Demonstrated**:
- **Counter**: Simple stateful counter with increment/decrement
- **DataProcessor**: Batch data processing with history tracking

### 3. Data Pipeline (`examples/data_pipeline.py`)
**Purpose**: Implements a complete data processing pipeline with multiple stages.

**Features**:
- **DataGenerator** actors for synthetic data generation
- **DataProcessor** actors for record transformation
- Batch processing with configurable sizes
- Data aggregation and statistical analysis
- Multi-stage pipeline orchestration

**Pipeline Stages**:
1. **Generation**: Multiple generators create synthetic records
2. **Processing**: Transform records (add computed fields, categorization)
3. **Aggregation**: Collect and analyze all processed data
4. **Statistics**: Calculate mean, std dev, min/max, category distributions

**Key Concepts**:
- Actor-based data generation and processing
- Batch processing patterns
- Ray task composition for aggregation
- Statistical analysis with distributed data

### 4. Distributed Training (`examples/distributed_training.py`)
**Purpose**: Demonstrates parameter server pattern for distributed machine learning.

**Features**:
- **ParameterServer** actor for centralized parameter management
- **Worker** actors for distributed gradient computation
- Synchronous distributed training loop
- Model evaluation and performance tracking
- Training metrics collection and analysis

**Training Components**:
- **ParameterServer**: Maintains model parameters, applies gradient updates
- **Workers**: Compute gradients on local data batches
- **Evaluation**: Separate evaluation function for model testing

**Training Flow**:
1. Parameter server initializes model parameters
2. Workers fetch current parameters
3. Workers compute gradients on local data
4. Parameter server aggregates and applies gradients
5. Process repeats for specified iterations
6. Final model evaluation on test data

**Key Concepts**:
- Parameter server distributed training pattern
- Gradient computation and aggregation
- Distributed model evaluation
- Training metrics and performance monitoring

### 5. Workflow Orchestration (`examples/workflow_orchestration.py`)
**Purpose**: Complex multi-step workflow orchestration with task dependencies.

**Features**:
- **WorkflowOrchestrator** actor for workflow management
- Multi-step data processing workflows
- Task dependency management and execution
- Workflow history and status tracking
- Parallel workflow execution

**Workflow Tasks**:
- **fetch_data_task**: Simulates data fetching from external sources
- **validate_data_task**: Data validation and filtering
- **transform_data_task**: Data transformation (normalize/categorize)
- **merge_data_task**: Multi-source data merging and aggregation
- **save_results_task**: Results persistence with different formats

**Workflow Types**:
- **Data Pipeline Workflow**: Complete ETL (Extract, Transform, Load) process
- **Parallel Workflow Execution**: Multiple workflows running concurrently
- **Workflow Monitoring**: Status tracking and history management

**Key Concepts**:
- Task dependency orchestration
- Multi-step workflow execution
- Workflow state management
- Parallel workflow processing

## Example Complexity Levels

### Beginner (`simple_job.py`, `actor_example.py`)
- Basic Ray concepts and patterns
- Simple remote functions and actors
- Resource management fundamentals

### Intermediate (`data_pipeline.py`)
- Multi-stage data processing
- Actor coordination patterns
- Batch processing and aggregation

### Advanced (`distributed_training.py`, `workflow_orchestration.py`)
- Complex distributed patterns (parameter server)
- Sophisticated workflow orchestration
- Performance monitoring and metrics
- Multi-component system coordination

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
2. Submit job: `"Submit a job with entrypoint 'python examples/simple_job.py'"`
3. Monitor: `"Check job status for job_id abc123"`
4. Get logs: `"Get logs for job abc123"`
5. Stop Ray: `"Stop the Ray cluster"`

### Running Examples via MCP Server
```bash
# Basic examples
"Submit a job with entrypoint 'python examples/simple_job.py'"
"Submit a job with entrypoint 'python examples/actor_example.py'"

# Advanced examples
"Submit a job with entrypoint 'python examples/data_pipeline.py'"
"Submit a job with entrypoint 'python examples/distributed_training.py'"
"Submit a job with entrypoint 'python examples/workflow_orchestration.py'"
```

### Running Examples Directly
```bash
# All examples can be run directly (auto-initialize Ray)
python examples/simple_job.py
python examples/actor_example.py
python examples/data_pipeline.py
python examples/distributed_training.py
python examples/workflow_orchestration.py

# Or with an existing Ray cluster
ray start --head
python examples/simple_job.py  # (or any other example)
ray stop
```

### Actor Management
1. Start Ray cluster
2. Submit job that creates actors (any actor example)
3. List actors: `"List all actors in the cluster"`
4. Kill specific actor: `"Kill actor with ID xyz789"`

### Performance Monitoring
1. Get cluster status: `"Get cluster status"`
2. Check resources: `"Get cluster resource information"`
3. Performance metrics: `"Get performance metrics"`
4. Health check: `"Perform cluster health check"`

## Example Selection Guide

Choose examples based on your use case:

- **Learning Ray basics**: Start with `simple_job.py`
- **Stateful distributed computing**: Use `actor_example.py`
- **Data processing pipelines**: Try `data_pipeline.py`
- **Machine learning training**: Explore `distributed_training.py`
- **Complex workflows**: Study `workflow_orchestration.py` 