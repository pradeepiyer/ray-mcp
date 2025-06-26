"""Tool functions for Ray cluster operations.

This module provides high-level tool functions that wrap Ray cluster management operations.
Each function takes a RayManager instance and returns JSON-formatted results suitable for
LLM consumption. All functions are async and handle error cases gracefully.
"""

import json
from typing import Any, Dict, List, Optional

from .ray_manager import RayManager

# ===== BASIC CLUSTER MANAGEMENT =====


async def start_ray_cluster(
    ray_manager: RayManager,
    head_node: bool = True,
    address: Optional[str] = None,
    num_cpus: Optional[int] = None,
    num_gpus: Optional[int] = None,
    object_store_memory: Optional[int] = None,
    worker_nodes: Optional[List[Dict[str, Any]]] = None,
    head_node_port: int = 10001,
    dashboard_port: int = 8265,
    head_node_host: str = "127.0.0.1",
    **kwargs: Any,
) -> str:
    """Start a Ray cluster with head node and optional worker nodes.

    This function initializes a Ray cluster either by starting a new one or connecting
    to an existing cluster. For new clusters, it can configure resources and worker nodes.

    Args:
        ray_manager: The RayManager instance to use for cluster operations
        head_node: Whether to start a head node (default: True)
        address: Address of existing cluster to connect to (e.g., 'ray://127.0.0.1:10001')
        num_cpus: Number of CPUs to allocate to the head node
        num_gpus: Number of GPUs to allocate to the head node
        object_store_memory: Object store memory in bytes for head node
        worker_nodes: List of worker node configurations, each with num_cpus, num_gpus, etc.
        head_node_port: Port for the head node (default: 10001)
        dashboard_port: Port for Ray dashboard (default: 8265)
        head_node_host: Host address for head node (default: "127.0.0.1")
        **kwargs: Additional Ray initialization parameters

    Returns:
        JSON string containing cluster status, address, dashboard URL, and any errors.

        When RAY_MCP_ENHANCED_OUTPUT=true, returns LLM-enhanced output with:
        - Tool Result Summary: Brief summary of what the tool accomplished
        - Context: Additional context about what this means for the Ray cluster
        - Suggested Next Steps: 2-3 relevant next actions with specific tool names
        - Available Commands: Quick reference of commonly used Ray MCP tools
        - Original Response: Complete JSON response for reference

        When RAY_MCP_ENHANCED_OUTPUT=false (default), returns raw JSON response.

    Failure modes:
        - Ray not installed: Returns error message about missing Ray installation
        - Port conflicts: Automatically finds free ports or returns port binding errors
        - Network issues: Returns connection errors for existing cluster connections
        - Resource allocation failures: Returns specific resource configuration errors
    """
    result = await ray_manager.start_cluster(
        head_node=head_node,
        address=address,
        num_cpus=num_cpus,
        num_gpus=num_gpus,
        object_store_memory=object_store_memory,
        worker_nodes=worker_nodes,
        head_node_port=head_node_port,
        dashboard_port=dashboard_port,
        head_node_host=head_node_host,
        **kwargs,
    )
    return json.dumps(result, indent=2)


async def connect_ray_cluster(
    ray_manager: RayManager, address: str, **kwargs: Any
) -> str:
    """Connect to an existing Ray cluster.

    Connects to a running Ray cluster at the specified address. This is useful when
    the cluster was started separately or on a different machine.

    Args:
        ray_manager: The RayManager instance to use for cluster operations
        address: Ray cluster address (e.g., 'ray://127.0.0.1:10001' or '127.0.0.1:10001')
        **kwargs: Additional connection parameters

    Returns:
        JSON string containing connection status, cluster info, and any errors.

        When RAY_MCP_ENHANCED_OUTPUT=true, returns LLM-enhanced output with:
        - Tool Result Summary: Brief summary of what the tool accomplished
        - Context: Additional context about what this means for the Ray cluster
        - Suggested Next Steps: 2-3 relevant next actions with specific tool names
        - Available Commands: Quick reference of commonly used Ray MCP tools
        - Original Response: Complete JSON response for reference

        When RAY_MCP_ENHANCED_OUTPUT=false (default), returns raw JSON response.

    Failure modes:
        - Invalid address format: Returns parsing errors
        - Cluster not running: Returns connection refused errors
        - Network unreachable: Returns network timeout errors
        - Authentication issues: Returns authentication errors if cluster requires auth
    """
    result = await ray_manager.connect_cluster(address=address, **kwargs)
    return json.dumps(result, indent=2)


async def stop_ray_cluster(ray_manager: RayManager) -> str:
    """Stop the Ray cluster and clean up resources.

    Gracefully shuts down the Ray cluster, terminating all running jobs, actors,
    and worker processes. This should be called when done with cluster operations.

    Args:
        ray_manager: The RayManager instance to use for cluster operations

    Returns:
        JSON string containing shutdown status and any errors.

        When RAY_MCP_ENHANCED_OUTPUT=true, returns LLM-enhanced output with:
        - Tool Result Summary: Brief summary of what the tool accomplished
        - Context: Additional context about what this means for the Ray cluster
        - Suggested Next Steps: 2-3 relevant next actions with specific tool names
        - Available Commands: Quick reference of commonly used Ray MCP tools
        - Original Response: Complete JSON response for reference

        When RAY_MCP_ENHANCED_OUTPUT=false (default), returns raw JSON response.

    Failure modes:
        - Cluster not running: Returns "already stopped" status
        - Jobs still running: Attempts to cancel jobs before shutdown
        - Process termination issues: Returns specific process cleanup errors
        - Resource cleanup failures: Returns warnings about incomplete cleanup
    """
    result = await ray_manager.stop_cluster()
    return json.dumps(result, indent=2)


async def get_cluster_info(ray_manager: RayManager) -> str:
    """Get comprehensive cluster information including status, resources, nodes, and worker status.

    Retrieves detailed information about the current Ray cluster state, including
    node status, resource utilization, running jobs, and system health metrics.

    Args:
        ray_manager: The RayManager instance to use for cluster operations

    Returns:
        JSON string containing cluster information with the following structure:
        - cluster_status: Overall cluster health and status
        - nodes: List of all nodes with their resource allocation and status
        - resources: Available and used CPU/GPU/memory resources
        - jobs: Currently running and completed jobs
        - actors: Active actors and their states
        - dashboard_url: URL for the Ray dashboard

        When RAY_MCP_ENHANCED_OUTPUT=true, returns LLM-enhanced output with:
        - Tool Result Summary: Brief summary of what the tool accomplished
        - Context: Additional context about what this means for the Ray cluster
        - Suggested Next Steps: 2-3 relevant next actions with specific tool names
        - Available Commands: Quick reference of commonly used Ray MCP tools
        - Original Response: Complete JSON response for reference

        When RAY_MCP_ENHANCED_OUTPUT=false (default), returns raw JSON response.

    Failure modes:
        - Cluster not initialized: Returns error about Ray not being started
        - Connection issues: Returns network or timeout errors
        - Partial data available: Returns available information with warnings
        - Permission issues: Returns access denied errors for certain metrics
    """
    result = await ray_manager.get_cluster_info()
    return json.dumps(result, indent=2)


# ===== JOB MANAGEMENT =====


async def submit_job(
    ray_manager: RayManager,
    entrypoint: str,
    runtime_env: Optional[Dict[str, Any]] = None,
    job_id: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
    **kwargs: Any,
) -> str:
    """Submit a job to the Ray cluster for execution.

    Submits a Python script or command to the Ray cluster for distributed execution.
    The job will run on available cluster resources and can be monitored and managed.

    Args:
        ray_manager: The RayManager instance to use for cluster operations
        entrypoint: Command or Python script to execute (e.g., "python script.py")
        runtime_env: Runtime environment configuration including:
            - pip: List of pip packages to install
            - conda: Conda environment specification
            - env_vars: Environment variables to set
            - working_dir: Working directory for the job
        job_id: Optional custom job identifier (auto-generated if not provided)
        metadata: Optional key-value pairs for job metadata
        **kwargs: Additional job submission parameters

    Returns:
        JSON string containing job submission status, job_id, and any errors.

        When RAY_MCP_ENHANCED_OUTPUT=true, returns LLM-enhanced output with:
        - Tool Result Summary: Brief summary of what the tool accomplished
        - Context: Additional context about what this means for the Ray cluster
        - Suggested Next Steps: 2-3 relevant next actions with specific tool names
        - Available Commands: Quick reference of commonly used Ray MCP tools
        - Original Response: Complete JSON response for reference

        When RAY_MCP_ENHANCED_OUTPUT=false (default), returns raw JSON response.

    Failure modes:
        - Invalid entrypoint: Returns command parsing or file not found errors
        - Runtime environment issues: Returns package installation or environment setup errors
        - Resource constraints: Returns insufficient resources errors
        - Job ID conflicts: Returns duplicate job ID errors
        - Cluster not ready: Returns cluster initialization errors
    """
    result = await ray_manager.submit_job(
        entrypoint=entrypoint,
        runtime_env=runtime_env,
        job_id=job_id,
        metadata=metadata,
        **kwargs,
    )
    return json.dumps(result, indent=2)


async def list_jobs(ray_manager: RayManager) -> str:
    """List all jobs in the Ray cluster with their current status.

    Retrieves information about all jobs that have been submitted to the cluster,
    including their current status, submission time, and basic metadata.

    Args:
        ray_manager: The RayManager instance to use for cluster operations

    Returns:
        JSON string containing list of jobs with the following information:
        - job_id: Unique job identifier
        - status: Current job status (PENDING, RUNNING, SUCCEEDED, FAILED, etc.)
        - entrypoint: Command or script being executed
        - submission_time: When the job was submitted
        - start_time: When the job started running
        - end_time: When the job completed (if finished)
        - metadata: Job metadata if provided

        When RAY_MCP_ENHANCED_OUTPUT=true, returns LLM-enhanced output with:
        - Tool Result Summary: Brief summary of what the tool accomplished
        - Context: Additional context about what this means for the Ray cluster
        - Suggested Next Steps: 2-3 relevant next actions with specific tool names
        - Available Commands: Quick reference of commonly used Ray MCP tools
        - Original Response: Complete JSON response for reference

        When RAY_MCP_ENHANCED_OUTPUT=false (default), returns raw JSON response.

    Failure modes:
        - Cluster not initialized: Returns error about Ray not being started
        - Connection issues: Returns network or timeout errors
        - Permission issues: Returns access denied errors
        - Partial data: Returns available job information with warnings
    """
    result = await ray_manager.list_jobs()
    return json.dumps(result, indent=2)


async def get_job_status(ray_manager: RayManager, job_id: str) -> str:
    """Get the detailed status of a specific job.

    Retrieves comprehensive information about a specific job including its current
    status, resource usage, logs, and any error messages.

    Args:
        ray_manager: The RayManager instance to use for cluster operations
        job_id: The unique identifier of the job to check

    Returns:
        JSON string containing detailed job information:
        - job_id: Job identifier
        - status: Current status (PENDING, RUNNING, SUCCEEDED, FAILED, etc.)
        - entrypoint: Command being executed
        - submission_time: Job submission timestamp
        - start_time: Job start timestamp
        - end_time: Job completion timestamp
        - runtime_env: Runtime environment used
        - metadata: Job metadata
        - logs: Recent log output
        - error_message: Error details if job failed

        When RAY_MCP_ENHANCED_OUTPUT=true, returns LLM-enhanced output with:
        - Tool Result Summary: Brief summary of what the tool accomplished
        - Context: Additional context about what this means for the Ray cluster
        - Suggested Next Steps: 2-3 relevant next actions with specific tool names
        - Available Commands: Quick reference of commonly used Ray MCP tools
        - Original Response: Complete JSON response for reference

        When RAY_MCP_ENHANCED_OUTPUT=false (default), returns raw JSON response.

    Failure modes:
        - Job not found: Returns "job not found" error
        - Invalid job_id: Returns format validation errors
        - Cluster not initialized: Returns Ray initialization errors
        - Connection issues: Returns network or timeout errors
    """
    result = await ray_manager.get_job_status(job_id)
    return json.dumps(result, indent=2)


async def cancel_job(ray_manager: RayManager, job_id: str) -> str:
    """Cancel a running job and clean up its resources.

    Attempts to gracefully stop a running job and release its allocated resources.
    The job will be marked as cancelled and any running tasks will be terminated.

    Args:
        ray_manager: The RayManager instance to use for cluster operations
        job_id: The unique identifier of the job to cancel

    Returns:
        JSON string containing cancellation status and any errors.

        When RAY_MCP_ENHANCED_OUTPUT=true, returns LLM-enhanced output with:
        - Tool Result Summary: Brief summary of what the tool accomplished
        - Context: Additional context about what this means for the Ray cluster
        - Suggested Next Steps: 2-3 relevant next actions with specific tool names
        - Available Commands: Quick reference of commonly used Ray MCP tools
        - Original Response: Complete JSON response for reference

        When RAY_MCP_ENHANCED_OUTPUT=false (default), returns raw JSON response.

    Failure modes:
        - Job not found: Returns "job not found" error
        - Job already completed: Returns "job already finished" status
        - Job already cancelled: Returns "job already cancelled" status
        - Permission issues: Returns access denied errors
        - Resource cleanup failures: Returns warnings about incomplete cleanup
    """
    result = await ray_manager.cancel_job(job_id)
    return json.dumps(result, indent=2)


async def monitor_job_progress(ray_manager: RayManager, job_id: str) -> str:
    """Get real-time progress monitoring for a job.

    Provides detailed monitoring information for a running job including resource
    usage, task progress, and performance metrics.

    Args:
        ray_manager: The RayManager instance to use for cluster operations
        job_id: The unique identifier of the job to monitor

    Returns:
        JSON string containing monitoring information:
        - job_id: Job identifier
        - status: Current job status
        - progress: Task completion progress (if available)
        - resource_usage: CPU, memory, and GPU utilization
        - active_tasks: Number of currently running tasks
        - completed_tasks: Number of completed tasks
        - failed_tasks: Number of failed tasks
        - estimated_completion: Estimated time to completion
        - recent_logs: Latest log entries

        When RAY_MCP_ENHANCED_OUTPUT=true, returns LLM-enhanced output with:
        - Tool Result Summary: Brief summary of what the tool accomplished
        - Context: Additional context about what this means for the Ray cluster
        - Suggested Next Steps: 2-3 relevant next actions with specific tool names
        - Available Commands: Quick reference of commonly used Ray MCP tools
        - Original Response: Complete JSON response for reference

        When RAY_MCP_ENHANCED_OUTPUT=false (default), returns raw JSON response.

    Failure modes:
        - Job not found: Returns "job not found" error
        - Job not running: Returns "job not active" status
        - Monitoring not available: Returns "monitoring unavailable" error
        - Connection issues: Returns network or timeout errors
    """
    result = await ray_manager.monitor_job_progress(job_id)
    return json.dumps(result, indent=2)


async def debug_job(ray_manager: RayManager, job_id: str) -> str:
    """Interactive debugging tools for jobs.

    Provides debugging information and suggestions for troubleshooting job issues,
    including error analysis, log analysis, and recommended fixes.

    Args:
        ray_manager: The RayManager instance to use for cluster operations
        job_id: The unique identifier of the job to debug

    Returns:
        JSON string containing debugging information:
        - job_id: Job identifier
        - status: Current job status
        - error_analysis: Analysis of any errors encountered
        - log_analysis: Analysis of job logs for issues
        - resource_analysis: Analysis of resource usage patterns
        - suggestions: Recommended debugging steps and fixes
        - common_issues: List of common issues and solutions

        When RAY_MCP_ENHANCED_OUTPUT=true, returns LLM-enhanced output with:
        - Tool Result Summary: Brief summary of what the tool accomplished
        - Context: Additional context about what this means for the Ray cluster
        - Suggested Next Steps: 2-3 relevant next actions with specific tool names
        - Available Commands: Quick reference of commonly used Ray MCP tools
        - Original Response: Complete JSON response for reference

        When RAY_MCP_ENHANCED_OUTPUT=false (default), returns raw JSON response.

    Failure modes:
        - Job not found: Returns "job not found" error
        - Job running successfully: Returns "no issues detected" status
        - Debug information unavailable: Returns "debug info not available" error
        - Permission issues: Returns access denied errors
    """
    result = await ray_manager.debug_job(job_id)
    return json.dumps(result, indent=2)


# ===== ACTOR MANAGEMENT =====


async def list_actors(
    ray_manager: RayManager, filters: Optional[Dict[str, Any]] = None
) -> str:
    """List actors in the cluster with optional filtering.

    Retrieves information about all actors running in the cluster, including their
    state, resource usage, and metadata. Supports filtering by various criteria.

    Args:
        ray_manager: The RayManager instance to use for cluster operations
        filters: Optional filters to apply to the actor list:
            - state: Filter by actor state (ALIVE, DEAD, PENDING_RESTART, etc.)
            - class_name: Filter by actor class name
            - node_id: Filter by node where actor is running
            - resource_usage: Filter by resource usage thresholds

    Returns:
        JSON string containing list of actors with information:
        - actor_id: Unique actor identifier
        - class_name: Actor class name
        - state: Current actor state
        - node_id: Node where actor is running
        - resource_usage: CPU, memory, and GPU usage
        - creation_time: When actor was created
        - metadata: Actor metadata if available

        When RAY_MCP_ENHANCED_OUTPUT=true, returns LLM-enhanced output with:
        - Tool Result Summary: Brief summary of what the tool accomplished
        - Context: Additional context about what this means for the Ray cluster
        - Suggested Next Steps: 2-3 relevant next actions with specific tool names
        - Available Commands: Quick reference of commonly used Ray MCP tools
        - Original Response: Complete JSON response for reference

        When RAY_MCP_ENHANCED_OUTPUT=false (default), returns raw JSON response.

    Failure modes:
        - Cluster not initialized: Returns Ray initialization errors
        - Invalid filters: Returns filter validation errors
        - Connection issues: Returns network or timeout errors
        - Permission issues: Returns access denied errors
    """
    result = await ray_manager.list_actors(filters)
    return json.dumps(result, indent=2)


async def kill_actor(
    ray_manager: RayManager, actor_id: str, no_restart: bool = False
) -> str:
    """Kill an actor and optionally prevent restart.

    Terminates a running actor and releases its resources. Can optionally prevent
    the actor from being automatically restarted if it was configured with restart policies.

    Args:
        ray_manager: The RayManager instance to use for cluster operations
        actor_id: The unique identifier of the actor to kill
        no_restart: If True, prevents the actor from being restarted (default: False)

    Returns:
        JSON string containing termination status and any errors.

        When RAY_MCP_ENHANCED_OUTPUT=true, returns LLM-enhanced output with:
        - Tool Result Summary: Brief summary of what the tool accomplished
        - Context: Additional context about what this means for the Ray cluster
        - Suggested Next Steps: 2-3 relevant next actions with specific tool names
        - Available Commands: Quick reference of commonly used Ray MCP tools
        - Original Response: Complete JSON response for reference

        When RAY_MCP_ENHANCED_OUTPUT=false (default), returns raw JSON response.

    Failure modes:
        - Actor not found: Returns "actor not found" error
        - Actor already dead: Returns "actor already terminated" status
        - Permission issues: Returns access denied errors
        - Resource cleanup failures: Returns warnings about incomplete cleanup
        - Restart prevention failed: Returns warnings if restart prevention fails
    """
    result = await ray_manager.kill_actor(actor_id, no_restart)
    return json.dumps(result, indent=2)


# ===== ENHANCED MONITORING =====


async def get_performance_metrics(ray_manager: RayManager) -> str:
    """Get detailed performance metrics for the cluster.

    Retrieves comprehensive performance metrics including resource utilization,
    throughput, latency, and system health indicators.

    Args:
        ray_manager: The RayManager instance to use for cluster operations

    Returns:
        JSON string containing performance metrics:
        - cluster_metrics: Overall cluster performance indicators
        - node_metrics: Per-node performance data
        - resource_utilization: CPU, memory, GPU, and network usage
        - throughput_metrics: Task completion rates and throughput
        - latency_metrics: Task execution and communication latency
        - error_rates: Error and failure rates
        - recommendations: Performance optimization suggestions

        When RAY_MCP_ENHANCED_OUTPUT=true, returns LLM-enhanced output with:
        - Tool Result Summary: Brief summary of what the tool accomplished
        - Context: Additional context about what this means for the Ray cluster
        - Suggested Next Steps: 2-3 relevant next actions with specific tool names
        - Available Commands: Quick reference of commonly used Ray MCP tools
        - Original Response: Complete JSON response for reference

        When RAY_MCP_ENHANCED_OUTPUT=false (default), returns raw JSON response.

    Failure modes:
        - Cluster not initialized: Returns Ray initialization errors
        - Metrics unavailable: Returns "metrics not available" error
        - Partial data: Returns available metrics with warnings
        - Permission issues: Returns access denied errors
    """
    result = await ray_manager.get_performance_metrics()
    return json.dumps(result, indent=2)


async def cluster_health_check(ray_manager: RayManager) -> str:
    """Perform automated cluster health monitoring.

    Runs comprehensive health checks on the cluster including node connectivity,
    resource availability, system stability, and potential issues.

    Args:
        ray_manager: The RayManager instance to use for cluster operations

    Returns:
        JSON string containing health check results:
        - overall_status: Overall cluster health status (HEALTHY, WARNING, CRITICAL)
        - node_health: Health status of each node
        - resource_health: Resource availability and usage health
        - connectivity_health: Network connectivity between nodes
        - system_health: Operating system and Ray service health
        - issues: List of detected issues and their severity
        - recommendations: Suggested actions to resolve issues

        When RAY_MCP_ENHANCED_OUTPUT=true, returns LLM-enhanced output with:
        - Tool Result Summary: Brief summary of what the tool accomplished
        - Context: Additional context about what this means for the Ray cluster
        - Suggested Next Steps: 2-3 relevant next actions with specific tool names
        - Available Commands: Quick reference of commonly used Ray MCP tools
        - Original Response: Complete JSON response for reference

        When RAY_MCP_ENHANCED_OUTPUT=false (default), returns raw JSON response.

    Failure modes:
        - Cluster not initialized: Returns Ray initialization errors
        - Health checks unavailable: Returns "health checks not available" error
        - Partial health data: Returns available health information with warnings
        - Permission issues: Returns access denied errors
    """
    result = await ray_manager.cluster_health_check()
    return json.dumps(result, indent=2)


async def optimize_cluster_config(ray_manager: RayManager) -> str:
    """Analyze cluster usage and suggest optimizations.

    Analyzes current cluster configuration and usage patterns to provide
    recommendations for improving performance, resource utilization, and cost efficiency.

    Args:
        ray_manager: The RayManager instance to use for cluster operations

    Returns:
        JSON string containing optimization analysis:
        - current_config: Current cluster configuration
        - usage_analysis: Analysis of resource usage patterns
        - performance_analysis: Performance bottlenecks and opportunities
        - recommendations: Specific optimization suggestions
        - cost_analysis: Cost optimization opportunities
        - implementation_steps: Steps to implement suggested optimizations

        When RAY_MCP_ENHANCED_OUTPUT=true, returns LLM-enhanced output with:
        - Tool Result Summary: Brief summary of what the tool accomplished
        - Context: Additional context about what this means for the Ray cluster
        - Suggested Next Steps: 2-3 relevant next actions with specific tool names
        - Available Commands: Quick reference of commonly used Ray MCP tools
        - Original Response: Complete JSON response for reference

        When RAY_MCP_ENHANCED_OUTPUT=false (default), returns raw JSON response.

    Failure modes:
        - Cluster not initialized: Returns Ray initialization errors
        - Insufficient data: Returns "insufficient usage data" error
        - Analysis unavailable: Returns "analysis not available" error
        - Permission issues: Returns access denied errors
    """
    result = await ray_manager.optimize_cluster_config()
    return json.dumps(result, indent=2)


# ===== WORKFLOW & ORCHESTRATION =====


async def schedule_job(
    ray_manager: RayManager, entrypoint: str, schedule: str, **kwargs: Any
) -> str:
    """Schedule a job with cron-like scheduling.

    Schedules a job to run periodically using cron-like syntax. The job will be
    automatically submitted to the cluster according to the specified schedule.

    Args:
        ray_manager: The RayManager instance to use for cluster operations
        entrypoint: Command or Python script to execute
        schedule: Cron-like schedule string (e.g., "0 0 * * *" for daily at midnight)
        **kwargs: Additional job submission parameters (runtime_env, metadata, etc.)

    Returns:
        JSON string containing scheduling status and job information:
        - schedule_id: Unique identifier for the scheduled job
        - entrypoint: Command to be executed
        - schedule: Cron schedule string
        - next_run: Next scheduled execution time
        - status: Schedule status (ACTIVE, PAUSED, etc.)
        - job_history: List of previous executions

        When RAY_MCP_ENHANCED_OUTPUT=true, returns LLM-enhanced output with:
        - Tool Result Summary: Brief summary of what the tool accomplished
        - Context: Additional context about what this means for the Ray cluster
        - Suggested Next Steps: 2-3 relevant next actions with specific tool names
        - Available Commands: Quick reference of commonly used Ray MCP tools
        - Original Response: Complete JSON response for reference

        When RAY_MCP_ENHANCED_OUTPUT=false (default), returns raw JSON response.

    Failure modes:
        - Invalid schedule format: Returns schedule parsing errors
        - Invalid entrypoint: Returns command validation errors
        - Scheduling service unavailable: Returns "scheduling not available" error
        - Permission issues: Returns access denied errors
        - Resource constraints: Returns insufficient resources errors
    """
    result = await ray_manager.schedule_job(
        entrypoint=entrypoint, schedule=schedule, **kwargs
    )
    return json.dumps(result, indent=2)


# ===== LOGS & DEBUGGING =====


async def get_logs(
    ray_manager: RayManager,
    job_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    node_id: Optional[str] = None,
    num_lines: int = 100,
) -> str:
    """Get logs from Ray cluster components.

    Retrieves log output from various cluster components including jobs, actors,
    and nodes. Can filter by specific component or get logs from all sources.

    Args:
        ray_manager: The RayManager instance to use for cluster operations
        job_id: Optional job ID to get logs for a specific job
        actor_id: Optional actor ID to get logs for a specific actor
        node_id: Optional node ID to get logs for a specific node
        num_lines: Number of log lines to retrieve (default: 100, max: 1000)

    Returns:
        JSON string containing log information:
        - logs: List of log entries with timestamps and content
        - source: Source of the logs (job, actor, node, or cluster)
        - total_lines: Total number of log lines available
        - truncated: Whether logs were truncated due to line limit
        - error_logs: Any error messages found in the logs
        - warnings: Any warning messages found in the logs

        When RAY_MCP_ENHANCED_OUTPUT=true, returns LLM-enhanced output with:
        - Tool Result Summary: Brief summary of what the tool accomplished
        - Context: Additional context about what this means for the Ray cluster
        - Suggested Next Steps: 2-3 relevant next actions with specific tool names
        - Available Commands: Quick reference of commonly used Ray MCP tools
        - Original Response: Complete JSON response for reference

        When RAY_MCP_ENHANCED_OUTPUT=false (default), returns raw JSON response.

    Failure modes:
        - Component not found: Returns "component not found" error
        - Logs not available: Returns "logs not available" error
        - Invalid parameters: Returns parameter validation errors
        - Permission issues: Returns access denied errors
        - Log file access issues: Returns file system errors
    """
    result = await ray_manager.get_logs(
        job_id=job_id, actor_id=actor_id, node_id=node_id, num_lines=num_lines
    )
    return json.dumps(result, indent=2)
