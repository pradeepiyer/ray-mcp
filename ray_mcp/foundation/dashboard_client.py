"""Ray Dashboard API client for job operations."""

import asyncio
from typing import Any, Optional

import aiohttp


class DashboardAPIError(Exception):
    """Dashboard API specific errors."""

    def __init__(
        self, status_code: int, message: str, details: Optional[dict[str, Any]] = None
    ):
        self.status_code = status_code
        self.message = message
        self.details = details or {}
        super().__init__(f"Dashboard API Error {status_code}: {message}")


class DashboardClient:
    """Async HTTP client for Ray Dashboard API."""

    def __init__(self, dashboard_url: str, timeout: float = 30.0):
        self.dashboard_url = dashboard_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()

    async def submit_job(
        self,
        entrypoint: str,
        runtime_env: Optional[dict[str, Any]] = None,
        job_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Submit a job to the Ray cluster."""
        payload = {
            "entrypoint": entrypoint,
            "runtime_env": runtime_env or {},
            "metadata": metadata or {},
        }
        if job_id:
            payload["job_id"] = job_id

        async with self._session.post(
            f"{self.dashboard_url}/api/jobs/", json=payload
        ) as response:
            return await self._handle_response(response)

    async def get_job_info(self, job_id: str) -> dict[str, Any]:
        """Get information about a specific job."""
        async with self._session.get(
            f"{self.dashboard_url}/api/jobs/{job_id}"
        ) as response:
            return await self._handle_response(response)

    async def list_jobs(self) -> dict[str, Any]:
        """List all jobs in the cluster."""
        async with self._session.get(f"{self.dashboard_url}/api/jobs/") as response:
            return await self._handle_response(response)

    async def stop_job(self, job_id: str) -> dict[str, Any]:
        """Stop a running job."""
        async with self._session.post(
            f"{self.dashboard_url}/api/jobs/{job_id}/stop"
        ) as response:
            return await self._handle_response(response)

    async def get_job_logs(self, job_id: str) -> dict[str, Any]:
        """Get logs for a specific job."""
        async with self._session.get(
            f"{self.dashboard_url}/api/jobs/{job_id}/logs"
        ) as response:
            return await self._handle_response(response)

    async def _handle_response(
        self, response: aiohttp.ClientResponse
    ) -> dict[str, Any]:
        """Handle HTTP response with proper error handling."""
        try:
            data = await response.json()
        except Exception:
            # If JSON parsing fails, try to get text
            text = await response.text()
            data = {"message": text}

        if response.status == 200:
            return data
        elif response.status == 404:
            raise DashboardAPIError(404, "Resource not found", data)
        elif response.status == 400:
            raise DashboardAPIError(400, "Invalid request", data)
        elif response.status >= 500:
            raise DashboardAPIError(response.status, "Internal server error", data)
        else:
            raise DashboardAPIError(response.status, f"HTTP {response.status}", data)
