"""Single tool definition for Ray MCP server with LLM-based routing."""

from mcp.types import Tool


def get_ray_tools() -> list[Tool]:
    """Single Ray MCP tool with natural language interface and LLM-based routing."""
    return [
        Tool(
            name="ray",
            description="Unified Ray management tool for jobs, services, and cloud operations on Kubernetes clusters via KubeRay. Automatically routes requests based on natural language intent.",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "What you want to do with Ray in plain English. The system will automatically determine whether this is a job, service, or cloud operation. Examples:\n\nJOB OPERATIONS: 'Submit job script train.py', 'Submit job with script data_processing.py', 'Submit training job from https://github.com/user/ml-repo/train.py with 2 GPUs', 'List all running jobs', 'Get logs for job ray-job-abc123', 'Cancel job training-run-456'\n\nSERVICE OPERATIONS: 'Create Ray service with inference model serve.py', 'Deploy service named image-classifier with model classifier.py', 'List all Ray services in production namespace', 'Get status of service model-serving', 'Scale service inference-api to 5 replicas', 'Delete service recommendation-engine', 'Get logs for service text-analyzer'\n\nCLOUD OPERATIONS: 'Authenticate with GCP project ml-experiments', 'Authenticate with AWS', 'List cloud clusters', 'Connect to cluster ml-training in us-west1-c', 'Create cloud cluster named ai-cluster', 'Check cloud environment setup'",
                    }
                },
                "required": ["prompt"],
            },
        ),
    ]
