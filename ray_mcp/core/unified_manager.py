"""Unified Ray MCP manager that composes focused components."""

from typing import Any, Dict, List, Optional

from .cluster_manager import RayClusterManager
from .interfaces import (
    ClusterManager,
    JobManager,
    LogManager,
    PortManager,
    StateManager,
)
from .job_manager import RayJobManager
from .log_manager import RayLogManager
from .port_manager import RayPortManager
from .state_manager import RayStateManager


class RayUnifiedManager:
    """Unified manager that composes focused Ray MCP components.

    This class provides a clean facade over the individual focused components,
    maintaining the same interface as the original monolithic RayManager while
    internally delegating to specialized components.
    """

    def __init__(self):
        # Initialize core components
        self._state_manager = RayStateManager()
        self._port_manager = RayPortManager()

        # Initialize specialized managers with dependencies
        self._cluster_manager = RayClusterManager(
            self._state_manager, self._port_manager
        )
        self._job_manager = RayJobManager(self._state_manager)
        self._log_manager = RayLogManager(self._state_manager)

    # Delegate properties to state manager
    @property
    def is_initialized(self) -> bool:
        """Check if Ray is initialized."""
        return self._state_manager.is_initialized()

    @property
    def cluster_address(self) -> Optional[str]:
        """Get cluster address."""
        return self._state_manager.get_state().get("cluster_address")

    @property
    def dashboard_url(self) -> Optional[str]:
        """Get dashboard URL."""
        return self._state_manager.get_state().get("dashboard_url")

    @property
    def job_client(self) -> Optional[Any]:
        """Get job client."""
        return self._state_manager.get_state().get("job_client")

    # Cluster management methods
    async def init_cluster(self, **kwargs) -> Dict[str, Any]:
        """Initialize Ray cluster."""
        return await self._cluster_manager.init_cluster(**kwargs)

    async def stop_cluster(self) -> Dict[str, Any]:
        """Stop Ray cluster."""
        return await self._cluster_manager.stop_cluster()

    async def inspect_ray(self) -> Dict[str, Any]:
        """Inspect Ray cluster."""
        return await self._cluster_manager.inspect_cluster()

    # Job management methods
    async def submit_job(
        self,
        entrypoint: str,
        runtime_env: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Submit a job to the Ray cluster."""
        return await self._job_manager.submit_job(
            entrypoint, runtime_env, job_id, metadata, **kwargs
        )

    async def list_jobs(self) -> Dict[str, Any]:
        """List all jobs in the Ray cluster."""
        return await self._job_manager.list_jobs()

    async def cancel_job(self, job_id: str) -> Dict[str, Any]:
        """Cancel a running job."""
        return await self._job_manager.cancel_job(job_id)

    async def inspect_job(self, job_id: str, mode: str = "status") -> Dict[str, Any]:
        """Inspect job details."""
        return await self._job_manager.inspect_job(job_id, mode)

    # Log management methods
    async def retrieve_logs(
        self,
        identifier: str,
        log_type: str = "job",
        num_lines: int = 100,
        include_errors: bool = False,
        max_size_mb: int = 10,
        **kwargs,
    ) -> Dict[str, Any]:
        """Retrieve logs from Ray cluster."""
        return await self._log_manager.retrieve_logs(
            identifier, log_type, num_lines, include_errors, max_size_mb, **kwargs
        )

    async def retrieve_logs_paginated(
        self,
        identifier: str,
        log_type: str = "job",
        page: int = 1,
        page_size: int = 100,
        max_size_mb: int = 10,
        include_errors: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Retrieve logs with pagination."""
        return await self._log_manager.retrieve_logs_paginated(
            identifier, log_type, page, page_size, max_size_mb, include_errors, **kwargs
        )

    # Port management methods (for internal use)
    async def find_free_port(self, start_port: int = 10001, max_tries: int = 50) -> int:
        """Find a free port."""
        return await self._port_manager.find_free_port(start_port, max_tries)

    def cleanup_port_lock(self, port: int) -> None:
        """Clean up port lock file."""
        self._port_manager.cleanup_port_lock(port)

    # Component access for advanced usage
    def get_state_manager(self) -> RayStateManager:
        """Get the state manager component."""
        return self._state_manager

    def get_cluster_manager(self) -> RayClusterManager:
        """Get the cluster manager component."""
        return self._cluster_manager

    def get_job_manager(self) -> RayJobManager:
        """Get the job manager component."""
        return self._job_manager

    def get_log_manager(self) -> RayLogManager:
        """Get the log manager component."""
        return self._log_manager

    def get_port_manager(self) -> RayPortManager:
        """Get the port manager component."""
        return self._port_manager
