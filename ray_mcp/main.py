#!/usr/bin/env python3
"""Main entry point for the Ray MCP server."""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Union

# Import MCP types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Content, EmbeddedResource, ImageContent, TextContent, Tool

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
    ActorConfig,
    ActorId,
    ActorInfo,
    ActorState,
    ClusterHealth,
    ErrorResponse,
    HealthStatus,
    JobId,
    JobInfo,
    JobStatus,
    JobSubmissionConfig,
    NodeId,
    NodeInfo,
    PerformanceMetrics,
    Response,
    SuccessResponse,
)

# Initialize server and ray manager
server = Server("ray-mcp")
ray_manager = RayManager()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available Ray tools with their schemas and descriptions.

    Returns a comprehensive list of all available Ray cluster management tools
    that can be called by LLM agents. Each tool includes detailed input schemas
    with parameter descriptions, types, and validation rules.

    Returns:
        List[Tool]: List of Tool objects containing:
            - name: Tool identifier (e.g., "start_ray", "submit_job")
            - description: Human-readable description of tool functionality
            - inputSchema: JSON schema defining required and optional parameters
                with types, constraints, and descriptions for each parameter

    The tools are organized into categories:
    - Basic cluster management: start_ray, connect_ray, stop_ray, cluster_info
    - Job management: submit_job, list_jobs, job_status, cancel_job, monitor_job, debug_job
    - Actor management: list_actors, kill_actor
    - Enhanced monitoring: performance_metrics, health_check, optimize_config
    - Workflow & orchestration: schedule_job
    - Logs & debugging: get_logs

    Failure modes:
        - No tools available: Returns empty list (should not occur in normal operation)
        - Schema generation errors: Returns tools with basic schemas
    """
    return [
        # Basic cluster management
        Tool(
            name="start_ray",
            description="Start a new Ray cluster with head node and worker nodes (defaults to multi-node with 2 workers)",
            inputSchema={
                "type": "object",
                "properties": {
                    "num_cpus": {
                        "type": "integer",
                        "minimum": 1,
                        "default": 1,
                        "description": "Number of CPUs for head node",
                    },
                    "num_gpus": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Number of GPUs for head node",
                    },
                    "object_store_memory": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Object store memory in bytes for head node",
                    },
                    "worker_nodes": {
                        "type": "array",
                        "description": "Configuration for worker nodes to start",
                        "items": {
                            "type": "object",
                            "properties": {
                                "num_cpus": {
                                    "type": "integer",
                                    "minimum": 1,
                                    "description": "Number of CPUs for this worker node",
                                },
                                "num_gpus": {
                                    "type": "integer",
                                    "minimum": 0,
                                    "description": "Number of GPUs for this worker node",
                                },
                                "object_store_memory": {
                                    "type": "integer",
                                    "minimum": 0,
                                    "description": "Object store memory in bytes for this worker node",
                                },
                                "resources": {
                                    "type": "object",
                                    "description": "Additional custom resources for this worker node",
                                },
                                "node_name": {
                                    "type": "string",
                                    "description": "Optional name for this worker node",
                                },
                            },
                            "required": ["num_cpus"],
                        },
                    },
                    "head_node_port": {
                        "type": "integer",
                        "minimum": 10000,
                        "maximum": 65535,
                        "default": 10001,
                        "description": "Port for head node",
                    },
                    "dashboard_port": {
                        "type": "integer",
                        "minimum": 1000,
                        "maximum": 65535,
                        "default": 8265,
                        "description": "Port for Ray dashboard",
                    },
                    "head_node_host": {
                        "type": "string",
                        "default": "127.0.0.1",
                        "description": "Host address for head node",
                    },
                },
            },
        ),
        Tool(
            name="connect_ray",
            description="Connect to an existing Ray cluster",
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Ray cluster address (e.g., 'ray://127.0.0.1:10001' or '127.0.0.1:10001')",
                    }
                },
                "required": ["address"],
            },
        ),
        Tool(
            name="stop_ray",
            description="Stop the Ray cluster",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="cluster_info",
            description="Get comprehensive cluster information including status, resources, nodes, and worker status",
            inputSchema={"type": "object", "properties": {}},
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
                    "metadata": {"type": "object"},
                },
                "required": ["entrypoint"],
            },
        ),
        Tool(
            name="list_jobs",
            description="List all jobs in the cluster",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="job_status",
            description="Get the status of a specific job",
            inputSchema={
                "type": "object",
                "properties": {"job_id": {"type": "string"}},
                "required": ["job_id"],
            },
        ),
        Tool(
            name="cancel_job",
            description="Cancel a running job",
            inputSchema={
                "type": "object",
                "properties": {"job_id": {"type": "string"}},
                "required": ["job_id"],
            },
        ),
        Tool(
            name="monitor_job",
            description="Get real-time progress monitoring for a job",
            inputSchema={
                "type": "object",
                "properties": {"job_id": {"type": "string"}},
                "required": ["job_id"],
            },
        ),
        Tool(
            name="debug_job",
            description="Interactive debugging tools for jobs",
            inputSchema={
                "type": "object",
                "properties": {"job_id": {"type": "string"}},
                "required": ["job_id"],
            },
        ),
        # Actor management
        Tool(
            name="list_actors",
            description="List actors in the cluster",
            inputSchema={
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": "Optional filters for actor list",
                    }
                },
            },
        ),
        Tool(
            name="kill_actor",
            description="Kill an actor",
            inputSchema={
                "type": "object",
                "properties": {
                    "actor_id": {"type": "string"},
                    "no_restart": {"type": "boolean", "default": False},
                },
                "required": ["actor_id"],
            },
        ),
        # Enhanced monitoring
        Tool(
            name="performance_metrics",
            description="Get detailed performance metrics for the cluster",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="health_check",
            description="Perform automated cluster health monitoring",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="optimize_config",
            description="Analyze cluster usage and suggest optimizations",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="schedule_job",
            description="Schedule a job to run periodically",
            inputSchema={
                "type": "object",
                "properties": {
                    "entrypoint": {"type": "string"},
                    "schedule": {"type": "string"},
                },
                "required": ["entrypoint", "schedule"],
            },
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
                    "num_lines": {"type": "integer", "minimum": 1, "default": 100},
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(
    name: str, arguments: Optional[Dict[str, Any]] = None
) -> List[TextContent]:
    """Execute a Ray cluster management tool with the provided arguments.

    This is the main handler that routes tool calls to the appropriate Ray manager
    methods. It handles parameter validation, error handling, and response formatting
    for all available Ray tools.

    Args:
        name: The name of the tool to execute (e.g., "start_ray", "submit_job")
        arguments: Optional dictionary containing tool-specific parameters.
            The structure depends on the tool being called and should match
            the tool's input schema.

    Returns:
        List[TextContent]: List containing a single TextContent object with:

            When RAY_MCP_ENHANCED_OUTPUT=true:
            - LLM-enhanced response with structured format including:
                - Tool Result Summary: Brief summary of what the tool accomplished
                - Context: Additional context about what this means for the Ray cluster
                - Suggested Next Steps: 2-3 relevant next actions with specific tool names
                - Available Commands: Quick reference of commonly used Ray MCP tools
                - Original Response: Complete JSON response for reference
            - The enhanced output is formatted as a system prompt that instructs
              the calling LLM to provide human-readable summaries and actionable
              next steps based on the tool response

            When RAY_MCP_ENHANCED_OUTPUT=false (default):
            - Raw JSON response with tool execution results
            - Standard error response if tool execution fails

            Error responses include detailed error messages and context for debugging.

    Tool Categories and Common Parameters:

    Cluster Management:
        - start_ray: num_cpus, num_gpus, worker_nodes, head_node_port, dashboard_port
        - connect_ray: address (required)
        - stop_ray: no parameters
        - cluster_info: no parameters

    Job Management:
        - submit_job: entrypoint (required), runtime_env, job_id, metadata
        - list_jobs: no parameters
        - job_status: job_id (required)
        - cancel_job: job_id (required)
        - monitor_job: job_id (required)
        - debug_job: job_id (required)

    Actor Management:
        - list_actors: filters (optional)
        - kill_actor: actor_id (required), no_restart (optional)

    Monitoring & Optimization:
        - performance_metrics: no parameters
        - health_check: no parameters
        - optimize_config: no parameters

    Workflow & Logging:
        - schedule_job: entrypoint (required), schedule (required)
        - get_logs: job_id, actor_id, node_id, num_lines (all optional)

    Failure modes:
        - Ray not available: Returns error message about missing Ray installation
        - Unknown tool: Returns "Unknown tool" error with tool name
        - Invalid parameters: Returns parameter validation errors
        - Tool execution errors: Returns specific error messages from Ray operations
        - Network/connection issues: Returns connection timeout or network errors
        - Permission issues: Returns access denied errors
        - Resource constraints: Returns insufficient resources errors

    Environment Variables:
        - RAY_MCP_ENHANCED_OUTPUT: When set to "true", enables LLM-enhanced responses
          with summaries, context, and suggested next steps. When "false" or unset,
          returns raw JSON responses for backward compatibility.
    """
    if not RAY_AVAILABLE:
        return [
            TextContent(
                type="text",
                text="Ray is not available. Please install Ray to use this MCP server.",
            )
        ]

    args = arguments or {}

    try:
        # Basic cluster management
        if name == "start_ray":
            result = await ray_manager.start_cluster(**args)
        elif name == "connect_ray":
            result = await ray_manager.connect_cluster(**args)
        elif name == "stop_ray":
            result = await ray_manager.stop_cluster()
        elif name == "cluster_info":
            result = await ray_manager.get_cluster_info()

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
            result = await ray_manager.kill_actor(
                args["actor_id"], args.get("no_restart", False)
            )

        # Enhanced monitoring
        elif name == "performance_metrics":
            result = await ray_manager.get_performance_metrics()
        elif name == "health_check":
            result = await ray_manager.cluster_health_check()
        elif name == "optimize_config":
            result = await ray_manager.optimize_cluster_config()

        elif name == "schedule_job":
            result = await ray_manager.schedule_job(**args)

        # Logs & debugging
        elif name == "get_logs":
            result = await ray_manager.get_logs(**args)

        else:
            result = {"status": "error", "message": f"Unknown tool: {name}"}

        # Check if enhanced output is enabled via environment variable
        enhanced_output = (
            os.getenv("RAY_MCP_ENHANCED_OUTPUT", "false").lower() == "true"
        )

        if enhanced_output:
            # Wrap the result with a system prompt for LLM enhancement
            enhanced_output = _wrap_with_system_prompt(name, result)
            return [TextContent(type="text", text=enhanced_output)]
        else:
            # Return original JSON response for backward compatibility
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        logger.error(f"Error executing {name}: {e}")
        error_result = {
            "status": "error",
            "message": f"Error executing {name}: {str(e)}",
        }

        # Check if enhanced output is enabled
        enhanced_output = (
            os.getenv("RAY_MCP_ENHANCED_OUTPUT", "false").lower() == "true"
        )

        if enhanced_output:
            enhanced_error = _wrap_with_system_prompt(name, error_result)
            return [TextContent(type="text", text=enhanced_error)]
        else:
            return [TextContent(type="text", text=json.dumps(error_result, indent=2))]


def _wrap_with_system_prompt(tool_name: str, result: Dict[str, Any]) -> str:
    """Wrap tool output with a system prompt for LLM enhancement.

    This approach uses the LLM's capabilities to generate suggestions and next steps
    based on the tool response, without requiring external API calls.

    Args:
        tool_name: The name of the tool that was executed
        result: The result dictionary from the tool execution

    Returns:
        str: A formatted system prompt that instructs the LLM to enhance the output
             with human-readable summaries, context, and suggested next steps

    The enhanced output includes:
        - Tool Result Summary: Brief summary of what the tool accomplished
        - Context: Additional context about what this means for the Ray cluster
        - Suggested Next Steps: 2-3 relevant next actions with specific tool names
        - Available Commands: Quick reference of commonly used Ray MCP tools
        - Original Response: The complete JSON response for reference
    """

    # Convert result to JSON string
    result_json = json.dumps(result, indent=2)

    # Create a system prompt that instructs the LLM to enhance the output
    system_prompt = f"""You are an AI assistant helping with Ray cluster management. A user just called the '{tool_name}' tool and received the following response:

{result_json}

Please provide a human-readable summary of what happened, add relevant context, and suggest logical next steps. Format your response as follows:

**Tool Result Summary:**
[Brief summary of what the tool call accomplished or revealed]

**Context:**
[Additional context about what this means for the Ray cluster or workflow]

**Suggested Next Steps:**
[List 2-3 relevant next actions the user might want to take, with specific tool names]

**Available Commands:**
[Quick reference of commonly used Ray MCP tools]

Keep your response concise, helpful, and actionable. Focus on practical next steps that would be most useful for someone managing a Ray cluster.

---
**Original Response (JSON):**
{result_json}"""

    return system_prompt


async def main():
    """Main entry point for the MCP server.

    Initializes and runs the Ray MCP server using stdio communication.
    The server provides tools for Ray cluster management that can be called
    by LLM agents through the MCP protocol.

    The server:
        - Validates Ray availability before starting
        - Sets up stdio communication channels
        - Registers tool handlers for Ray operations
        - Handles graceful shutdown on interruption
        - Cleans up Ray resources on exit

    Failure modes:
        - Ray not available: Exits with error code 1 and error message
        - Communication setup failure: Logs error and exits
        - Unexpected exceptions: Logs error and exits with error code 1
        - Keyboard interrupt: Gracefully shuts down and exits
    """
    if not RAY_AVAILABLE:
        logger.error("Ray is not available. Please install Ray.")
        sys.exit(1)

    try:
        # Start the MCP server without initializing Ray
        # Ray will be initialized only when start_ray or connect_ray tools are called
        print("Ray MCP Server starting (Ray not initialized yet)", file=sys.stderr)

        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream, write_stream, server.create_initialization_options()
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
    """Synchronous entry point for console script.

    Provides a synchronous wrapper around the async main() function for use
    as a console script entry point. This allows the MCP server to be run
    directly from the command line.

    Usage:
        python -m ray_mcp.main
        # or as a console script if installed via pip

    The function:
        - Runs the async main() function in an event loop
        - Handles any unhandled exceptions from the main function
        - Ensures proper cleanup of resources

    Failure modes:
        - Event loop errors: Propagates exceptions from main()
        - Resource cleanup issues: Logs warnings but doesn't prevent shutdown
    """
    asyncio.run(main())


if __name__ == "__main__":
    run_server()
