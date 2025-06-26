#!/usr/bin/env python3
"""Comprehensive unit tests for all MCP tool calls in the Ray MCP server."""

import asyncio
import json
from typing import Any, Dict, List, Union, cast
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import warnings

import pytest

# Configure pytest to ignore coroutine warnings
pytestmark = pytest.mark.filterwarnings("ignore::RuntimeWarning")

# Suppress the specific coroutine warning at module level
warnings.filterwarnings(
    "ignore", message="coroutine 'main' was never awaited", category=RuntimeWarning
)
warnings.filterwarnings(
    "ignore", message=".*coroutine.*main.*was never awaited.*", category=RuntimeWarning
)
warnings.filterwarnings(
    "ignore", message=".*coroutine.*was never awaited.*", category=RuntimeWarning
)

from mcp.types import Content, TextContent

# Import the main server components
from ray_mcp.main import list_tools
from ray_mcp.ray_manager import RayManager
from ray_mcp.tool_registry import ToolRegistry


# Mock the main function to prevent coroutine warnings
@pytest.fixture(scope="session", autouse=True)
def mock_main_function():
    """Mock the main function to prevent unawaited coroutine warnings."""
    # Mock both the main function and run_server to prevent any coroutine creation
    with patch("ray_mcp.main.main", new_callable=AsyncMock) as mock_main:
        with patch("ray_mcp.main.run_server", new_callable=Mock) as mock_run:
            # Ensure the mock doesn't return a coroutine
            mock_main.return_value = None
            mock_run.return_value = None
            yield mock_main


def get_text_content(result: Any, index: int = 0) -> TextContent:
    """Helper function to get TextContent from result with proper typing."""
    return cast(TextContent, result[index])


@pytest.mark.fast
class TestMCPTools:
    """Test cases for all MCP tool calls."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a mock RayManager instead of a real one
        self.mock_ray_manager = Mock(spec=RayManager)
        self.registry = ToolRegistry(self.mock_ray_manager)

    @pytest.mark.asyncio
    async def test_list_tools(self):
        tools = await list_tools()
        assert any(tool.name == "start_ray" for tool in tools)

    @pytest.mark.asyncio
    async def test_cluster_info(self):
        # Set up the mock return value
        self.mock_ray_manager.get_cluster_info = AsyncMock(
            return_value={"status": "running", "nodes": []}
        )

        result = await self.registry.execute_tool("cluster_info", {})
        assert result["status"] == "running"
        assert "nodes" in result

    # ===== BASIC CLUSTER MANAGEMENT TESTS =====

    @pytest.mark.asyncio
    async def test_start_ray_tool(self):
        """Test start_ray tool with various configurations."""
        # Set up the mock return value
        self.mock_ray_manager.start_cluster = AsyncMock(
            return_value={
                "status": "started",
                "address": "ray://127.0.0.1:10001",
                "dashboard_url": "http://127.0.0.1:8265",
            }
        )

        result = await self.registry.execute_tool(
            "start_ray", {"num_cpus": 4, "num_gpus": 1}
        )

        assert isinstance(result, dict)
        assert result["status"] == "started"
        assert "address" in result
        assert "dashboard_url" in result

        # Verify the manager was called with correct arguments
        self.mock_ray_manager.start_cluster.assert_called_once_with(
            num_cpus=4, num_gpus=1
        )

    @pytest.mark.asyncio
    async def test_stop_ray_tool(self):
        """Test stop_ray tool."""
        # Set up the mock return value
        self.mock_ray_manager.stop_cluster = AsyncMock(
            return_value={
                "status": "stopped",
                "message": "Cluster stopped successfully",
            }
        )

        result = await self.registry.execute_tool("stop_ray", {})

        assert isinstance(result, dict)
        assert result["status"] == "stopped"
        self.mock_ray_manager.stop_cluster.assert_called_once()

    # ===== JOB MANAGEMENT TESTS =====

    @pytest.mark.asyncio
    async def test_submit_job_tool(self):
        """Test submit_job tool with complex arguments."""
        # Set up the mock return value
        self.mock_ray_manager.submit_job = AsyncMock(
            return_value={
                "status": "submitted",
                "job_id": "job_123",
                "message": "Job submitted successfully",
            }
        )

        complex_args = {
            "entrypoint": "python train.py --epochs 100",
            "runtime_env": {
                "pip": ["torch", "transformers", "datasets"],
                "env_vars": {"CUDA_VISIBLE_DEVICES": "0"},
            },
            "job_id": "custom_job_id",
            "metadata": {"owner": "test"},
        }

        result = await self.registry.execute_tool("submit_job", complex_args)

        assert isinstance(result, dict)
        assert result["status"] == "submitted"
        assert result["job_id"] == "job_123"

        # Verify the manager was called with correct arguments
        self.mock_ray_manager.submit_job.assert_called_once_with(**complex_args)

    @pytest.mark.asyncio
    async def test_list_jobs_tool(self):
        """Test list_jobs tool."""
        # Set up the mock return value
        self.mock_ray_manager.list_jobs = AsyncMock(
            return_value={
                "status": "success",
                "jobs": [
                    {"job_id": "job_1", "status": "RUNNING"},
                    {"job_id": "job_2", "status": "SUCCEEDED"},
                ],
            }
        )

        result = await self.registry.execute_tool("list_jobs", {})

        assert isinstance(result, dict)
        assert result["status"] == "success"
        assert len(result["jobs"]) == 2
        self.mock_ray_manager.list_jobs.assert_called_once()

    @pytest.mark.asyncio
    async def test_job_status_tool(self):
        """Test job_status tool."""
        # Set up the mock return value
        self.mock_ray_manager.get_job_status = AsyncMock(
            return_value={
                "status": "success",
                "job_id": "job_123",
                "job_status": "RUNNING",
                "entrypoint": "python train.py",
            }
        )

        result = await self.registry.execute_tool("job_status", {"job_id": "job_123"})

        assert isinstance(result, dict)
        assert result["job_status"] == "RUNNING"
        self.mock_ray_manager.get_job_status.assert_called_once_with("job_123")

    @pytest.mark.asyncio
    async def test_cancel_job_tool(self):
        """Test cancel_job tool."""
        # Set up the mock return value
        self.mock_ray_manager.cancel_job = AsyncMock(
            return_value={"status": "cancelled", "job_id": "job_123"}
        )

        result = await self.registry.execute_tool("cancel_job", {"job_id": "job_123"})

        assert isinstance(result, dict)
        assert result["status"] == "cancelled"
        self.mock_ray_manager.cancel_job.assert_called_once_with("job_123")

    @pytest.mark.asyncio
    async def test_monitor_job_tool(self):
        """Test monitor_job tool."""
        # Set up the mock return value
        self.mock_ray_manager.monitor_job_progress = AsyncMock(
            return_value={
                "status": "success",
                "job_id": "job_123",
                "progress": "75%",
                "estimated_time_remaining": "5 minutes",
            }
        )

        result = await self.registry.execute_tool("monitor_job", {"job_id": "job_123"})

        assert isinstance(result, dict)
        assert "progress" in result
        self.mock_ray_manager.monitor_job_progress.assert_called_once_with("job_123")

    @pytest.mark.asyncio
    async def test_debug_job_tool(self):
        """Test debug_job tool."""
        # Set up the mock return value
        self.mock_ray_manager.debug_job = AsyncMock(
            return_value={
                "status": "success",
                "job_id": "job_123",
                "debug_info": "Job is running normally",
            }
        )

        result = await self.registry.execute_tool("debug_job", {"job_id": "job_123"})

        assert isinstance(result, dict)
        assert "debug_info" in result
        self.mock_ray_manager.debug_job.assert_called_once_with("job_123")

    # ===== ACTOR MANAGEMENT TESTS =====

    @pytest.mark.asyncio
    async def test_list_actors_tool(self):
        """Test list_actors tool with filters."""
        # Set up the mock return value
        self.mock_ray_manager.list_actors = AsyncMock(
            return_value={
                "status": "success",
                "actors": [
                    {"actor_id": "actor_1", "state": "ALIVE"},
                    {"actor_id": "actor_2", "state": "DEAD"},
                ],
            }
        )

        filters = {"namespace": "test"}
        result = await self.registry.execute_tool("list_actors", {"filters": filters})

        assert isinstance(result, dict)
        assert len(result["actors"]) == 2
        self.mock_ray_manager.list_actors.assert_called_once_with(filters)

    @pytest.mark.asyncio
    async def test_kill_actor_tool(self):
        """Test kill_actor tool."""
        # Set up the mock return value
        self.mock_ray_manager.kill_actor = AsyncMock(
            return_value={"status": "killed", "actor_id": "actor_123"}
        )

        result = await self.registry.execute_tool(
            "kill_actor", {"actor_id": "actor_123", "no_restart": True}
        )

        assert isinstance(result, dict)
        assert result["status"] == "killed"
        self.mock_ray_manager.kill_actor.assert_called_once_with("actor_123", True)

    # ===== MONITORING TESTS =====

    @pytest.mark.asyncio
    async def test_performance_metrics_tool(self):
        """Test performance_metrics tool."""
        # Set up the mock return value
        self.mock_ray_manager.get_performance_metrics = AsyncMock(
            return_value={
                "status": "success",
                "metrics": {
                    "cpu_usage": "45%",
                    "memory_usage": "60%",
                    "gpu_usage": "30%",
                },
            }
        )

        result = await self.registry.execute_tool("performance_metrics", {})

        assert isinstance(result, dict)
        assert "metrics" in result
        self.mock_ray_manager.get_performance_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_tool(self):
        """Test health_check tool."""
        # Set up the mock return value
        self.mock_ray_manager.cluster_health_check = AsyncMock(
            return_value={
                "status": "success",
                "health": "good",
                "issues": [],
            }
        )

        result = await self.registry.execute_tool("health_check", {})

        assert isinstance(result, dict)
        assert result["health"] == "good"
        self.mock_ray_manager.cluster_health_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_optimize_config_tool(self):
        """Test optimize_config tool."""
        # Set up the mock return value
        self.mock_ray_manager.optimize_cluster_config = AsyncMock(
            return_value={
                "status": "success",
                "recommendations": ["Increase CPU allocation", "Add more workers"],
            }
        )

        result = await self.registry.execute_tool("optimize_config", {})

        assert isinstance(result, dict)
        assert "recommendations" in result
        self.mock_ray_manager.optimize_cluster_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_logs_tool(self):
        """Test get_logs tool with various parameters."""
        # Set up the mock return value
        self.mock_ray_manager.get_logs = AsyncMock(
            return_value={
                "status": "success",
                "logs": "Sample log output...",
                "job_id": "job_123",
            }
        )

        args = {"job_id": "test_job_123", "num_lines": 50}
        result = await self.registry.execute_tool("get_logs", args)

        assert isinstance(result, dict)
        assert "logs" in result
        self.mock_ray_manager.get_logs.assert_called_once_with(**args)

    # ===== ERROR HANDLING TESTS =====

    @pytest.mark.asyncio
    async def test_ray_unavailable_error(self):
        """Test tool calls when Ray is not available."""
        # Make the RayManager method raise an exception to simulate Ray unavailability
        self.mock_ray_manager.start_cluster = AsyncMock(
            side_effect=Exception("Ray is not available")
        )

        result = await self.registry.execute_tool(
            "start_ray", {"num_cpus": 4, "num_gpus": 1}
        )

        assert isinstance(result, dict)
        assert result["status"] == "error"
        assert "Ray is not available" in result["message"]

    @pytest.mark.asyncio
    async def test_unknown_tool_error(self):
        """Test calling unknown tool."""
        result = await self.registry.execute_tool("unknown_tool", {})

        assert isinstance(result, dict)
        assert result["status"] == "error"
        assert "Unknown tool" in result["message"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
