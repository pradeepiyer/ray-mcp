"""Log management tool schemas for Ray MCP server."""

from typing import Any, Dict


def get_retrieve_logs_schema() -> Dict[str, Any]:
    """Schema for retrieve_logs tool."""
    return {
        "type": "object",
        "properties": {
            "identifier": {
                "type": "string",
                "description": "Job ID, task ID, or component name to retrieve logs for",
            },
            "log_type": {
                "type": "string",
                "enum": ["job", "task", "worker", "system"],
                "default": "job",
                "description": "Type of logs to retrieve: 'job' for job logs, 'task' for task logs, 'worker' for worker logs, 'system' for system logs",
            },
            "num_lines": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10000,
                "default": 100,
                "description": "Number of log lines to retrieve (max 10000)",
            },
            "include_errors": {
                "type": "boolean",
                "default": False,
                "description": "Whether to include error analysis in the response",
            },
            "max_size_mb": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "default": 10,
                "description": "Maximum size of logs to retrieve in MB (max 100MB)",
            },
            "page": {
                "type": "integer",
                "minimum": 1,
                "description": "Page number for paginated log retrieval",
            },
            "page_size": {
                "type": "integer",
                "minimum": 10,
                "maximum": 1000,
                "default": 100,
                "description": "Number of lines per page for paginated retrieval",
            },
            "filter": {
                "type": "string",
                "description": "Filter pattern to search within logs",
            },
            "level": {
                "type": "string",
                "enum": ["debug", "info", "warning", "error", "critical"],
                "description": "Minimum log level to include",
            },
            "since": {
                "type": "string",
                "description": "Retrieve logs since this timestamp (ISO format)",
            },
            "until": {
                "type": "string",
                "description": "Retrieve logs until this timestamp (ISO format)",
            },
        },
        "required": ["identifier"],
    }
