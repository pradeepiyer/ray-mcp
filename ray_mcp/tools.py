"""Clean 3-tool definitions for Ray MCP server."""

from typing import List
from mcp.types import Tool


def get_ray_tools() -> List[Tool]:
    """The 3 Ray MCP tools with natural language interfaces."""
    return [
        Tool(
            name="ray_cluster",
            description="Manage Ray clusters: create, connect, stop, scale, inspect",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "What you want to do with Ray clusters in plain English. Examples: 'Create a local Ray cluster with 4 CPUs', 'Connect to cluster at 192.168.1.5:8265', 'Scale my-cluster to 6 workers', 'Stop the training-cluster'"
                    }
                },
                "required": ["prompt"]
            }
        ),
        
        Tool(
            name="ray_job", 
            description="Manage Ray jobs: submit from repos, monitor, get logs, cancel",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string", 
                        "description": "What you want to do with Ray jobs in plain English. Examples: 'Submit training job from https://github.com/user/ml-repo/train.py with 2 GPUs', 'List all running jobs', 'Get logs for job ray-job-abc123', 'Cancel job training-run-456'"
                    }
                },
                "required": ["prompt"]
            }
        ),
        
        Tool(
            name="cloud",
            description="Manage cloud infrastructure: authenticate, manage K8s clusters",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "What you want to do with cloud infrastructure in plain English. Examples: 'Authenticate with Google Cloud project ml-experiments', 'List all GKE clusters', 'Connect to cluster ml-training in GKE', 'Create GKE cluster named ai-cluster'"
                    }
                },
                "required": ["prompt"]
            }
        )
    ]