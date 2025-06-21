#!/usr/bin/env python3
"""Main entry point for the MCP Ray server."""

import asyncio
import json
import logging
import sys
from typing import Dict, Any, List, Optional, Union

# Import MCP types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    Content
)

# Import Ray modules with proper error handling
try:
    import ray
    from ray import job_submission
    RAY_AVAILABLE = True
except ImportError:
    RAY_AVAILABLE = False
    ray = None
    job_submission = None

from .ray_manager import RayManager
from .types import (
    JobId, ActorId, NodeId, 
    JobStatus, ActorState, HealthStatus,
    JobInfo, ActorInfo, NodeInfo,
    JobSubmissionConfig, ActorConfig,
    PerformanceMetrics, ClusterHealth,
    Response, SuccessResponse, ErrorResponse
)

# Initialize server and ray manager
server = Server("ray-mcp")
ray_manager = RayManager()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available Ray tools."""
    return [
        # Basic cluster management
        Tool(
            name="start_ray",
            description="Start a new Ray cluster (head node)",
            inputSchema={
                "type": "object",
                "properties": {
                    "num_cpus": {"type": "integer", "minimum": 1, "default": 4},
                    "num_gpus": {"type": "integer", "minimum": 0},
                    "object_store_memory": {"type": "integer", "minimum": 0}
                }
            }
        ),
        Tool(
            name="connect_ray",
            description="Connect to an existing Ray cluster",
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string", 
                        "description": "Ray cluster address (e.g., 'ray://127.0.0.1:10001' or '127.0.0.1:10001')"
                    }
                },
                "required": ["address"]
            }
        ),
        Tool(
            name="stop_ray",
            description="Stop the Ray cluster",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="cluster_status",
            description="Get Ray cluster status",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="cluster_resources",
            description="Get cluster resource information",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="cluster_nodes",
            description="Get cluster node information",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="scale_cluster",
            description="Scale the cluster by adding workers",
            inputSchema={
                "type": "object",
                "properties": {
                    "num_workers": {"type": "integer", "minimum": 1}
                },
                "required": ["num_workers"]
            }
        ),
        
        # Job management
        Tool(
            name="submit_job",
            description="Submit a job to the Ray cluster",
            inputSchema={
                "type": "object",
                "properties": {
                    "entrypoint": {"type": "string"},
                    "runtime_env": {"type": "object"},
                    "job_id": {"type": "string"},
                    "metadata": {"type": "object"}
                },
                "required": ["entrypoint"]
            }
        ),
        Tool(
            name="list_jobs",
            description="List all jobs in the cluster",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="job_status",
            description="Get the status of a specific job",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"}
                },
                "required": ["job_id"]
            }
        ),
        Tool(
            name="cancel_job",
            description="Cancel a running job",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"}
                },
                "required": ["job_id"]
            }
        ),
        Tool(
            name="monitor_job",
            description="Monitor job progress",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"}
                },
                "required": ["job_id"]
            }
        ),
        Tool(
            name="debug_job",
            description="Debug a job with detailed information",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"}
                },
                "required": ["job_id"]
            }
        ),
        
        # Actor management
        Tool(
            name="list_actors",
            description="List all actors in the cluster",
            inputSchema={
                "type": "object",
                "properties": {
                    "filters": {"type": "object"}
                }
            }
        ),
        Tool(
            name="kill_actor",
            description="Kill an actor",
            inputSchema={
                "type": "object",
                "properties": {
                    "actor_id": {"type": "string"},
                    "no_restart": {"type": "boolean", "default": False}
                },
                "required": ["actor_id"]
            }
        ),
        
        # Machine learning & AI features
        Tool(
            name="train_model",
            description="Train a machine learning model using Ray",
            inputSchema={
                "type": "object",
                "properties": {
                    "algorithm": {"type": "string", "enum": ["torch", "tensorflow", "xgboost", "sklearn"]},
                    "dataset_path": {"type": "string"},
                    "model_config": {"type": "object"}
                },
                "required": ["algorithm", "dataset_path", "model_config"]
            }
        ),
        Tool(
            name="tune_hyperparameters",
            description="Tune hyperparameters using Ray Tune",
            inputSchema={
                "type": "object",
                "properties": {
                    "script_path": {"type": "string"},
                    "search_space": {"type": "object"},
                    "metric": {"type": "string"}
                },
                "required": ["script_path", "search_space", "metric"]
            }
        ),
        Tool(
            name="deploy_model",
            description="Deploy a model using Ray Serve",
            inputSchema={
                "type": "object",
                "properties": {
                    "model_path": {"type": "string"},
                    "deployment_name": {"type": "string"},
                    "num_replicas": {"type": "integer", "minimum": 1, "default": 1}
                },
                "required": ["model_path", "deployment_name"]
            }
        ),
        Tool(
            name="list_deployments",
            description="List all model deployments",
            inputSchema={"type": "object", "properties": {}}
        ),
        
        # Data processing features
        Tool(
            name="create_dataset",
            description="Create a Ray dataset",
            inputSchema={
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "format": {"type": "string", "enum": ["parquet", "csv", "json", "images", "text"], "default": "parquet"}
                },
                "required": ["source"]
            }
        ),
        Tool(
            name="transform_data",
            description="Transform data using Ray Data",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string"},
                    "transformation": {"type": "string"}
                },
                "required": ["dataset_id", "transformation"]
            }
        ),
        Tool(
            name="batch_inference",
            description="Run batch inference on a dataset",
            inputSchema={
                "type": "object",
                "properties": {
                    "model_path": {"type": "string"},
                    "dataset_path": {"type": "string"},
                    "output_path": {"type": "string"}
                },
                "required": ["model_path", "dataset_path", "output_path"]
            }
        ),
        
        # Enhanced monitoring
        Tool(
            name="performance_metrics",
            description="Get detailed cluster performance metrics",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="health_check",
            description="Perform comprehensive cluster health check",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="optimize_config",
            description="Get cluster optimization recommendations",
            inputSchema={"type": "object", "properties": {}}
        ),
        
        # Workflow & orchestration
        Tool(
            name="create_workflow",
            description="Create a Ray workflow",
            inputSchema={
                "type": "object",
                "properties": {
                    "workflow_definition": {"type": "object"}
                },
                "required": ["workflow_definition"]
            }
        ),
        Tool(
            name="schedule_job",
            description="Schedule a job to run periodically",
            inputSchema={
                "type": "object",
                "properties": {
                    "entrypoint": {"type": "string"},
                    "schedule": {"type": "string"}
                },
                "required": ["entrypoint", "schedule"]
            }
        ),
        
        # Backup & recovery
        Tool(
            name="backup_cluster",
            description="Backup cluster state",
            inputSchema={
                "type": "object",
                "properties": {
                    "backup_path": {"type": "string"}
                },
                "required": ["backup_path"]
            }
        ),
        Tool(
            name="restore_cluster",
            description="Restore cluster from backup",
            inputSchema={
                "type": "object",
                "properties": {
                    "backup_path": {"type": "string"}
                },
                "required": ["backup_path"]
            }
        ),
        
        # Logs & debugging
        Tool(
            name="get_logs",
            description="Get logs from jobs, actors, or nodes",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "actor_id": {"type": "string"},
                    "node_id": {"type": "string"},
                    "num_lines": {"type": "integer", "minimum": 1, "default": 100}
                }
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Optional[Dict[str, Any]] = None) -> List[TextContent]:
    """Call a Ray tool."""
    if not RAY_AVAILABLE:
        return [TextContent(
            type="text",
            text="Ray is not available. Please install Ray to use this MCP server."
        )]
    
    args = arguments or {}
    
    try:
        # Basic cluster management
        if name == "start_ray":
            result = await ray_manager.start_cluster(**args)
        elif name == "connect_ray":
            result = await ray_manager.connect_cluster(**args)
        elif name == "stop_ray":
            result = await ray_manager.stop_cluster()
        elif name == "cluster_status":
            result = await ray_manager.get_cluster_status()
        elif name == "cluster_resources":
            result = await ray_manager.get_cluster_resources()
        elif name == "cluster_nodes":
            result = await ray_manager.get_cluster_nodes()
        elif name == "scale_cluster":
            result = await ray_manager.scale_cluster(args.get("num_workers", 1))
            
        # Job management
        elif name == "submit_job":
            result = await ray_manager.submit_job(**args)
        elif name == "list_jobs":
            result = await ray_manager.list_jobs()
        elif name == "job_status":
            result = await ray_manager.get_job_status(args["job_id"])
        elif name == "cancel_job":
            result = await ray_manager.cancel_job(args["job_id"])
        elif name == "monitor_job":
            result = await ray_manager.monitor_job_progress(args["job_id"])
        elif name == "debug_job":
            result = await ray_manager.debug_job(args["job_id"])
            
        # Actor management
        elif name == "list_actors":
            result = await ray_manager.list_actors(args.get("filters"))
        elif name == "kill_actor":
            result = await ray_manager.kill_actor(args["actor_id"], args.get("no_restart", False))
            
        # Machine learning & AI features
        elif name == "train_model":
            result = await ray_manager.train_model(**args)
        elif name == "tune_hyperparameters":
            result = await ray_manager.tune_hyperparameters(**args)
        elif name == "deploy_model":
            result = await ray_manager.deploy_model(**args)
        elif name == "list_deployments":
            result = await ray_manager.list_deployments()
            
        # Data processing features
        elif name == "create_dataset":
            result = await ray_manager.create_dataset(**args)
        elif name == "transform_data":
            result = await ray_manager.transform_data(**args)
        elif name == "batch_inference":
            result = await ray_manager.batch_inference(**args)
            
        # Enhanced monitoring
        elif name == "performance_metrics":
            result = await ray_manager.get_performance_metrics()
        elif name == "health_check":
            result = await ray_manager.cluster_health_check()
        elif name == "optimize_config":
            result = await ray_manager.optimize_cluster_config()
            
        # Workflow & orchestration
        elif name == "create_workflow":
            result = await ray_manager.create_workflow(**args)
        elif name == "schedule_job":
            result = await ray_manager.schedule_job(**args)
            
        # Backup & recovery
        elif name == "backup_cluster":
            result = await ray_manager.backup_cluster_state(args["backup_path"])
        elif name == "restore_cluster":
            result = await ray_manager.restore_cluster_state(args["backup_path"])
            
        # Logs & debugging
        elif name == "get_logs":
            result = await ray_manager.get_logs(**args)
            
        else:
            result = {"status": "error", "message": f"Unknown tool: {name}"}
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
        
    except Exception as e:
        logger.error(f"Error executing {name}: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "status": "error",
                "message": f"Error executing {name}: {str(e)}"
            }, indent=2)
        )]

async def main():
    """Main entry point for the MCP server."""
    if not RAY_AVAILABLE:
        logger.error("Ray is not available. Please install Ray.")
        sys.exit(1)
    
    try:
        # Start the MCP server without initializing Ray
        # Ray will be initialized only when start_ray or connect_ray tools are called
        print("Ray MCP Server starting (Ray not initialized yet)", file=sys.stderr)
        
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
    finally:
        # Clean up Ray if it was initialized
        if RAY_AVAILABLE and ray is not None and ray.is_initialized():
            print("Shutting down Ray cluster", file=sys.stderr)
            ray.shutdown()


def run_server():
    """Synchronous entry point for console script."""
    asyncio.run(main())


if __name__ == "__main__":
    run_server() 