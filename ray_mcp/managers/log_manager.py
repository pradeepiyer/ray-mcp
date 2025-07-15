"""Centralized log management for Ray clusters."""

from typing import Any, Dict, Optional

from ..foundation.resource_manager import ResourceManager


class LogManager(ResourceManager):
    """Manages Ray log retrieval and processing operations.

    Note: Job logs are now handled directly by JobManager via Dashboard API.
    This manager is kept for potential future log aggregation features.
    """

    def __init__(self):
        super().__init__(
            enable_ray=True,
            enable_kubernetes=False,
            enable_cloud=False,
        )

    async def execute_request(self, prompt: str) -> Dict[str, Any]:
        """Execute log operations using natural language prompts.

        Job logs are now handled directly by JobManager via Dashboard API.
        This method is kept for potential future log aggregation features.
        """
        return self._ResponseFormatter.format_error_response(
            "log manager execute_request",
            Exception(
                "Job logs are handled by JobManager. Use 'get logs for job <job_id>' with the job tool."
            ),
        )

    async def retrieve_logs(
        self,
        identifier: str,
        log_type: str = "job",
        **kwargs,
    ) -> Dict[str, Any]:
        """Retrieve logs from Ray cluster.

        Note: Job logs are now handled by JobManager via Dashboard API.
        Use the job tool directly for job log retrieval.
        """
        return self._ResponseFormatter.format_error_response(
            "retrieve logs",
            Exception(
                "Job logs are handled by JobManager. Use 'get logs for job <job_id>' with the job tool."
            ),
        )
