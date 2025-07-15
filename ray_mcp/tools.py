"""Clean 3-tool definitions for Ray MCP server."""

from typing import List

from mcp.types import Tool


def get_ray_tools() -> List[Tool]:
    """The 3 Ray MCP tools with natural language interfaces."""
    return [
        Tool(
            name="ray_cluster",
            description="Manage Ray cluster infrastructure: create/delete clusters, connect to existing, scale workers, inspect cluster status",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "What you want to do with Ray cluster infrastructure in plain English. Examples: 'Create a local Ray cluster with 4 CPUs', 'Connect to existing cluster at 192.168.1.5:8265', 'Scale my-cluster to 6 workers', 'Stop the training-cluster', 'Create Ray cluster on kubernetes'",
                    }
                },
                "required": ["prompt"],
            },
        ),
        Tool(
            name="ray_job",
            description="Submit and manage Ray jobs: submit to existing clusters or create ephemeral clusters, monitor execution, get logs, cancel jobs",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "What you want to do with Ray jobs in plain English. Jobs can target existing clusters (by name) or create ephemeral clusters (when no cluster specified). Examples: 'Submit job script train.py to cluster ml-training', 'Submit attached file to existing cluster production-cluster', 'Submit job with script data_processing.py on kubernetes', 'Submit training job from https://github.com/user/ml-repo/train.py with 2 GPUs', 'Run job script model.py' (creates ephemeral cluster), 'List all running jobs', 'Get logs for job ray-job-abc123', 'Cancel job training-run-456'",
                    }
                },
                "required": ["prompt"],
            },
        ),
        Tool(
            name="cloud",
            description="Manage cloud authentication and cluster discovery: authenticate with GCP, list/discover available K8s clusters",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "What you want to do with cloud authentication and cluster discovery in plain English. Examples: 'Authenticate with GCP project ml-experiments', 'List all GKE clusters', 'Connect to cluster ml-training in GKE', 'Create GCP cluster named ai-cluster', 'Check cloud environment setup'",
                    }
                },
                "required": ["prompt"],
            },
        ),
    ]
