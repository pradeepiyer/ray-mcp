"""Interfaces and protocols for Ray MCP components."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class StateManager(Protocol):
    """Protocol for managing Ray cluster state."""

    def get_state(self) -> Dict[str, Any]:
        """Get current cluster state."""
        ...

    def update_state(self, **kwargs) -> None:
        """Update cluster state."""
        ...

    def reset_state(self) -> None:
        """Reset state to initial values."""
        ...

    def is_initialized(self) -> bool:
        """Check if Ray is initialized."""
        ...


@runtime_checkable
class ClusterManager(Protocol):
    """Protocol for Ray cluster lifecycle management."""

    async def init_cluster(self, **kwargs) -> Dict[str, Any]:
        """Initialize Ray cluster."""
        ...

    async def stop_cluster(self) -> Dict[str, Any]:
        """Stop Ray cluster."""
        ...

    async def inspect_cluster(self) -> Dict[str, Any]:
        """Get cluster information."""
        ...


@runtime_checkable
class JobManager(Protocol):
    """Protocol for Ray job management."""

    async def submit_job(self, entrypoint: str, **kwargs) -> Dict[str, Any]:
        """Submit a job to the cluster."""
        ...

    async def list_jobs(self) -> Dict[str, Any]:
        """List all jobs."""
        ...

    async def cancel_job(self, job_id: str) -> Dict[str, Any]:
        """Cancel a job."""
        ...

    async def inspect_job(self, job_id: str, mode: str = "status") -> Dict[str, Any]:
        """Inspect job details."""
        ...


@runtime_checkable
class LogManager(Protocol):
    """Protocol for log retrieval and processing."""

    async def retrieve_logs(
        self,
        identifier: str,
        log_type: str = "job",
        num_lines: int = 100,
        include_errors: bool = False,
        max_size_mb: int = 10,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Retrieve logs from Ray cluster with optional pagination."""
        ...


@runtime_checkable
class PortManager(Protocol):
    """Protocol for port management."""

    async def find_free_port(self, start_port: int = 10001, max_tries: int = 50) -> int:
        """Find a free port."""
        ...

    def cleanup_port_lock(self, port: int) -> None:
        """Clean up port lock file."""
        ...


@runtime_checkable
class ProcessManager(Protocol):
    """Protocol for process management."""

    async def spawn_process(self, cmd: List[str], **kwargs) -> Optional[Any]:
        """Spawn a new process."""
        ...

    async def terminate_process(self, process: Any, timeout: int = 5) -> Dict[str, Any]:
        """Terminate a process gracefully."""
        ...


class RayComponent(ABC):
    """Base class for Ray MCP components."""

    def __init__(self, state_manager: StateManager):
        self._state_manager = state_manager

    @property
    def state_manager(self) -> StateManager:
        """Get the state manager."""
        return self._state_manager

    def _ensure_initialized(self) -> None:
        """Ensure Ray is initialized."""
        if not self._state_manager.is_initialized():
            raise RuntimeError("Ray is not initialized. Please start Ray first.")
