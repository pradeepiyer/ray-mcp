"""Clean 3-tool definitions for Ray MCP server."""

from mcp.types import Tool


def get_ray_tools() -> list[Tool]:
    """The 3 Ray MCP tools with natural language interfaces."""
    return [
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
            name="ray_service",
            description="Deploy and manage Ray services: create long-running services for model inference and serving, scale replicas, monitor service health",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "What you want to do with Ray services in plain English. Examples: 'Create Ray service with inference model serve.py', 'Deploy service named image-classifier with model classifier.py', 'List all Ray services in production namespace', 'Get status of service model-serving', 'Scale service inference-api to 5 replicas', 'Delete service recommendation-engine', 'Get logs for service text-analyzer'",
                    }
                },
                "required": ["prompt"],
            },
        ),
        Tool(
            name="cloud",
            description="Manage cloud authentication and cluster discovery: authenticate with cloud providers (GCP, AWS, Azure), list/discover available clusters",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "What you want to do with cloud authentication and cluster discovery in plain English. Examples: 'Authenticate with GCP project ml-experiments', 'Authenticate with AWS', 'List cloud clusters', 'Connect to cluster ml-training in us-west1-c', 'Create cloud cluster named ai-cluster', 'Check cloud environment setup'",
                    }
                },
                "required": ["prompt"],
            },
        ),
    ]
