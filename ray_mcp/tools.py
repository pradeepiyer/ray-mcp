"""Tool functions for Ray cluster operations."""

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
    """Start a Ray cluster with head node and optional worker nodes."""
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
    """Connect to an existing Ray cluster."""
    result = await ray_manager.connect_cluster(address=address, **kwargs)
    return json.dumps(result, indent=2)


async def stop_ray_cluster(ray_manager: RayManager) -> str:
    """Stop the Ray cluster."""
    result = await ray_manager.stop_cluster()
    return json.dumps(result, indent=2)


async def get_cluster_status(ray_manager: RayManager) -> str:
    """Get the current status of the Ray cluster."""
    result = await ray_manager.get_cluster_status()
    return json.dumps(result, indent=2)


async def get_cluster_resources(ray_manager: RayManager) -> str:
    """Get cluster resource information."""
    result = await ray_manager.get_cluster_resources()
    return json.dumps(result, indent=2)


async def get_cluster_nodes(ray_manager: RayManager) -> str:
    """Get cluster node information."""
    result = await ray_manager.get_cluster_nodes()
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
    """Submit a job to the Ray cluster."""
    result = await ray_manager.submit_job(
        entrypoint=entrypoint,
        runtime_env=runtime_env,
        job_id=job_id,
        metadata=metadata,
        **kwargs,
    )
    return json.dumps(result, indent=2)


async def list_jobs(ray_manager: RayManager) -> str:
    """List all jobs in the Ray cluster."""
    result = await ray_manager.list_jobs()
    return json.dumps(result, indent=2)


async def get_job_status(ray_manager: RayManager, job_id: str) -> str:
    """Get the status of a specific job."""
    result = await ray_manager.get_job_status(job_id)
    return json.dumps(result, indent=2)


async def cancel_job(ray_manager: RayManager, job_id: str) -> str:
    """Cancel a running job."""
    result = await ray_manager.cancel_job(job_id)
    return json.dumps(result, indent=2)


async def monitor_job_progress(ray_manager: RayManager, job_id: str) -> str:
    """Get real-time progress monitoring for a job."""
    result = await ray_manager.monitor_job_progress(job_id)
    return json.dumps(result, indent=2)


async def debug_job(ray_manager: RayManager, job_id: str) -> str:
    """Interactive debugging tools for jobs."""
    result = await ray_manager.debug_job(job_id)
    return json.dumps(result, indent=2)


# ===== ACTOR MANAGEMENT =====


async def list_actors(
    ray_manager: RayManager, filters: Optional[Dict[str, Any]] = None
) -> str:
    """List actors in the cluster."""
    result = await ray_manager.list_actors(filters)
    return json.dumps(result, indent=2)


async def kill_actor(
    ray_manager: RayManager, actor_id: str, no_restart: bool = False
) -> str:
    """Kill an actor."""
    result = await ray_manager.kill_actor(actor_id, no_restart)
    return json.dumps(result, indent=2)


# ===== ENHANCED MONITORING =====


async def get_performance_metrics(ray_manager: RayManager) -> str:
    """Get detailed performance metrics for the cluster."""
    result = await ray_manager.get_performance_metrics()
    return json.dumps(result, indent=2)


async def cluster_health_check(ray_manager: RayManager) -> str:
    """Perform automated cluster health monitoring."""
    result = await ray_manager.cluster_health_check()
    return json.dumps(result, indent=2)


async def optimize_cluster_config(ray_manager: RayManager) -> str:
    """Analyze cluster usage and suggest optimizations."""
    result = await ray_manager.optimize_cluster_config()
    return json.dumps(result, indent=2)


# ===== WORKFLOW & ORCHESTRATION =====


async def schedule_job(
    ray_manager: RayManager, entrypoint: str, schedule: str, **kwargs: Any
) -> str:
    """Schedule a job with cron-like scheduling."""
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
    """Get logs from Ray cluster."""
    result = await ray_manager.get_logs(
        job_id=job_id, actor_id=actor_id, node_id=node_id, num_lines=num_lines
    )
    return json.dumps(result, indent=2)
