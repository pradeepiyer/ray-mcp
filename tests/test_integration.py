#!/usr/bin/env python3
"""Integration tests for the Ray MCP server."""

import asyncio
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock, patch

from mcp.types import TextContent, Tool
import psutil
import pytest
import pytest_asyncio
import ray

from ray_mcp.main import list_tools, ray_manager
from ray_mcp.ray_manager import RayManager
from ray_mcp.tool_registry import ToolRegistry

SKIP_IN_CI = pytest.mark.skipif(
    os.environ.get("GITHUB_ACTIONS") == "true",
    reason="Unreliable in CI due to resource constraints",
)


def get_text_content(result) -> str:
    """Helper function to extract text content from MCP result."""
    content = list(result)[0]
    assert isinstance(content, TextContent)
    return content.text


async def call_tool(
    tool_name: str, arguments: Optional[Dict[str, Any]] = None
) -> List[TextContent]:
    """Helper function to call tools using the new ToolRegistry architecture."""
    # Use the same RayManager instance that the MCP tools use
    registry = ToolRegistry(ray_manager)

    # Execute the tool
    result = await registry.execute_tool(tool_name, arguments or {})

    # Convert the result to the expected MCP format
    result_text = json.dumps(result, indent=2)
    return [TextContent(type="text", text=result_text)]


@pytest.mark.integration
class TestMCPIntegration:
    """Integration tests for MCP tool functionality."""

    @pytest.fixture(autouse=True)
    def patch_ray_manager(self):
        with patch("ray_mcp.main.ray_manager", Mock()) as mock_ray_manager:
            yield mock_ray_manager

    @pytest.mark.asyncio
    async def test_list_tools_returns_all_tools(self):
        """Test that list_tools returns all expected tools."""
        tools = await list_tools()
        tool_names = [tool.name for tool in tools]

        expected_tools = [
            "start_ray",
            "connect_ray",
            "stop_ray",
            "cluster_info",
            "submit_job",
            "list_jobs",
            "job_status",
            "cancel_job",
            "monitor_job",
            "debug_job",
            "list_actors",
            "kill_actor",
            "performance_metrics",
            "health_check",
            "optimize_config",
            "get_logs",
        ]

        for expected_tool in expected_tools:
            assert expected_tool in tool_names, f"Tool {expected_tool} not found"

    @pytest.mark.asyncio
    async def test_tool_schemas_are_valid(self):
        """Test that all tools have valid schemas."""
        tools = await list_tools()

        for tool in tools:
            assert tool.name, "Tool must have a name"
            assert tool.description, "Tool must have a description"
            assert tool.inputSchema, "Tool must have an input schema"
            assert isinstance(tool.inputSchema, dict), "Schema must be a dictionary"

    @pytest.mark.asyncio
    async def test_complete_workflow_cluster_management(self):
        """Test complete cluster management workflow."""
        registry = ToolRegistry(RayManager())

        # Mock RayManager methods to avoid actual Ray operations
        start_cluster_mock = AsyncMock(
            return_value={"status": "success", "address": "ray://127.0.0.1:10001"}
        )
        start_cluster_mock.__signature__ = inspect.signature(RayManager.start_cluster)

        get_cluster_info_mock = AsyncMock(
            return_value={"status": "running", "nodes": []}
        )
        get_cluster_info_mock.__signature__ = inspect.signature(
            RayManager.get_cluster_info
        )

        stop_cluster_mock = AsyncMock(return_value={"status": "stopped"})
        stop_cluster_mock.__signature__ = inspect.signature(RayManager.stop_cluster)

        with patch.object(RayManager, "start_cluster", start_cluster_mock):
            with patch.object(RayManager, "get_cluster_info", get_cluster_info_mock):
                with patch.object(RayManager, "stop_cluster", stop_cluster_mock):

                    # Start cluster
                    result = await registry.execute_tool("start_ray", {"num_cpus": 8})
                    assert result["status"] == "success"
                    assert "address" in result

                    # Get cluster info
                    result = await registry.execute_tool("cluster_info", {})
                    assert result["status"] == "running"

                    # Stop cluster
                    result = await registry.execute_tool("stop_ray", {})
                    assert result["status"] == "stopped"

    @pytest.mark.asyncio
    async def test_complete_workflow_job_lifecycle(self):
        """Test complete job lifecycle workflow."""
        registry = ToolRegistry(RayManager())

        # Mock RayManager methods
        start_cluster_mock = AsyncMock(return_value={"status": "success"})
        start_cluster_mock.__signature__ = inspect.signature(RayManager.start_cluster)

        submit_job_mock = AsyncMock(
            return_value={"status": "submitted", "job_id": "job123"}
        )
        submit_job_mock.__signature__ = inspect.signature(RayManager.submit_job)

        get_job_status_mock = AsyncMock(return_value={"status": "running"})
        get_job_status_mock.__signature__ = inspect.signature(RayManager.get_job_status)

        list_jobs_mock = AsyncMock(return_value={"jobs": [{"job_id": "job123"}]})
        list_jobs_mock.__signature__ = inspect.signature(RayManager.list_jobs)

        cancel_job_mock = AsyncMock(return_value={"status": "cancelled"})
        cancel_job_mock.__signature__ = inspect.signature(RayManager.cancel_job)

        with patch.object(RayManager, "start_cluster", start_cluster_mock):
            with patch.object(RayManager, "submit_job", submit_job_mock):
                with patch.object(RayManager, "get_job_status", get_job_status_mock):
                    with patch.object(RayManager, "list_jobs", list_jobs_mock):
                        with patch.object(RayManager, "cancel_job", cancel_job_mock):

                            # Start cluster
                            result = await registry.execute_tool(
                                "start_ray", {"num_cpus": 4}
                            )
                            assert result["status"] == "success"

                            # Submit job
                            result = await registry.execute_tool(
                                "submit_job",
                                {
                                    "entrypoint": "python script.py",
                                    "runtime_env": {"pip": ["requests"]},
                                    "job_id": "job123",
                                },
                            )
                            assert result["status"] == "submitted"
                            assert result["job_id"] == "job123"

                            # Check job status
                            result = await registry.execute_tool(
                                "job_status", {"job_id": "job123"}
                            )
                            assert result["status"] == "running"

                            # List jobs
                            result = await registry.execute_tool("list_jobs", {})
                            assert "jobs" in result
                            assert len(result["jobs"]) > 0

                            # Cancel job
                            result = await registry.execute_tool(
                                "cancel_job", {"job_id": "job123"}
                            )
                            assert result["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_error_propagation(self):
        """Test that errors are properly propagated."""
        registry = ToolRegistry(RayManager())

        # Mock RayManager to raise an exception
        start_cluster_mock = AsyncMock(side_effect=Exception("Test error"))
        start_cluster_mock.__signature__ = inspect.signature(RayManager.start_cluster)

        with patch.object(RayManager, "start_cluster", start_cluster_mock):
            result = await registry.execute_tool("start_ray", {})
            assert result["status"] == "error"
            assert "Test error" in result["message"]

    @pytest.mark.asyncio
    async def test_ray_unavailable_handling(self):
        start_cluster_mock = AsyncMock(side_effect=Exception("Ray is not available"))
        start_cluster_mock.__signature__ = inspect.signature(RayManager.start_cluster)

        with patch.object(ray_manager, "start_cluster", start_cluster_mock):
            with patch("ray_mcp.main.RAY_AVAILABLE", False):
                result = await call_tool("start_ray")
                response_text = get_text_content(result)
                assert "Ray is not available" in response_text

    @pytest.mark.asyncio
    async def test_parameter_validation_integration(self):
        start_cluster_mock = AsyncMock(return_value={"status": "started"})
        start_cluster_mock.__signature__ = inspect.signature(RayManager.start_cluster)

        get_job_status_mock = AsyncMock(
            return_value={"status": "success", "job_status": "RUNNING"}
        )
        get_job_status_mock.__signature__ = inspect.signature(RayManager.get_job_status)

        with (
            patch.object(ray_manager, "start_cluster", start_cluster_mock),
            patch.object(ray_manager, "get_job_status", get_job_status_mock),
        ):
            with patch("ray_mcp.main.RAY_AVAILABLE", True):
                result = await call_tool("job_status", {})  # Missing job_id
                response_data = json.loads(get_text_content(result))
                assert response_data["status"] == "error"
                result = await call_tool("job_status", {"job_id": "test_job"})
                response_data = json.loads(get_text_content(result))
                assert response_data["status"] == "success"

    @pytest.mark.asyncio
    async def test_response_format_consistency(self):
        """Test that all tool responses follow consistent format."""
        mock_ray_manager = Mock()
        # Set up mock responses for different tools
        start_cluster_mock = AsyncMock(return_value={"status": "started"})
        start_cluster_mock.__signature__ = inspect.signature(RayManager.start_cluster)

        list_jobs_mock = AsyncMock(return_value={"status": "success", "jobs": []})
        list_jobs_mock.__signature__ = inspect.signature(RayManager.list_jobs)

        get_performance_metrics_mock = AsyncMock(
            return_value={"status": "success", "metrics": {}}
        )
        get_performance_metrics_mock.__signature__ = inspect.signature(
            RayManager.get_performance_metrics
        )

        mock_ray_manager.start_cluster = start_cluster_mock
        mock_ray_manager.list_jobs = list_jobs_mock
        mock_ray_manager.get_performance_metrics = get_performance_metrics_mock

        with patch("ray_mcp.main.ray_manager", mock_ray_manager):
            with patch("ray_mcp.main.RAY_AVAILABLE", True):

                # Test multiple tools
                tools_to_test = ["start_ray", "list_jobs", "performance_metrics"]

                for tool_name in tools_to_test:
                    result = await call_tool(tool_name)

                    # Check response format
                    assert isinstance(result, list)
                    assert len(result) == 1
                    assert isinstance(result[0], TextContent)
                    assert result[0].type == "text"

                    # Check JSON response structure
                    response_data = json.loads(get_text_content(result))
                    assert isinstance(response_data, dict)
                    assert "status" in response_data

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self):
        start_cluster_mock = AsyncMock(return_value={"status": "started"})
        start_cluster_mock.__signature__ = inspect.signature(RayManager.start_cluster)

        get_cluster_info_mock = AsyncMock(
            return_value={
                "status": "success",
                "cluster_overview": {"status": "running"},
            }
        )
        get_cluster_info_mock.__signature__ = inspect.signature(
            RayManager.get_cluster_info
        )

        list_jobs_mock = AsyncMock(return_value={"status": "success", "jobs": []})
        list_jobs_mock.__signature__ = inspect.signature(RayManager.list_jobs)

        list_actors_mock = AsyncMock(return_value={"status": "success", "actors": []})
        list_actors_mock.__signature__ = inspect.signature(RayManager.list_actors)

        with (
            patch.object(ray_manager, "start_cluster", start_cluster_mock),
            patch.object(ray_manager, "get_cluster_info", get_cluster_info_mock),
            patch.object(ray_manager, "list_jobs", list_jobs_mock),
            patch.object(ray_manager, "list_actors", list_actors_mock),
        ):
            with patch("ray_mcp.main.RAY_AVAILABLE", True):
                tasks = [
                    call_tool("cluster_info"),
                    call_tool("list_jobs"),
                    call_tool("list_actors"),
                ]
                results = await asyncio.gather(*tasks)
                assert len(results) == 3
                for result in results:
                    response_data = json.loads(get_text_content(result))
                    assert response_data["status"] == "success"

    @pytest.mark.asyncio
    async def test_tool_call_with_complex_parameters(self):
        start_cluster_mock = AsyncMock(return_value={"status": "started"})
        start_cluster_mock.__signature__ = inspect.signature(RayManager.start_cluster)

        submit_job_mock = AsyncMock(
            return_value={"status": "submitted", "job_id": "complex_job"}
        )
        submit_job_mock.__signature__ = inspect.signature(RayManager.submit_job)

        with (
            patch.object(ray_manager, "start_cluster", start_cluster_mock),
            patch.object(ray_manager, "submit_job", submit_job_mock),
        ):
            with patch("ray_mcp.main.RAY_AVAILABLE", True):
                complex_args = {
                    "entrypoint": "python complex_job.py",
                    "runtime_env": {
                        "pip": ["requests==2.28.0", "click==8.0.0"],
                        "env_vars": {"CUDA_VISIBLE_DEVICES": "0,1"},
                        "working_dir": "/workspace",
                    },
                    "metadata": {
                        "owner": "data_team",
                        "project": "nlp_training",
                        "priority": "high",
                        "tags": ["gpu", "distributed"],
                    },
                }
                result = await call_tool("submit_job", complex_args)
                response_data = json.loads(get_text_content(result))
                assert response_data["status"] == "submitted"
                submit_job_mock.assert_called_once_with(**complex_args)


@pytest.mark.integration
class TestIntegration:
    @pytest.mark.asyncio
    async def test_list_tools_integration(self):
        tools = await list_tools()
        assert any(tool.name == "start_ray" for tool in tools)

    @pytest.mark.asyncio
    async def test_submit_job_integration(self):
        registry = ToolRegistry(RayManager())
        # Patch RayManager.submit_job to avoid actually submitting a job
        submit_job_mock = AsyncMock(
            return_value={"status": "submitted", "job_id": "job123"}
        )
        submit_job_mock.__signature__ = inspect.signature(RayManager.submit_job)

        with patch.object(RayManager, "submit_job", submit_job_mock):
            result = await registry.execute_tool(
                "submit_job", {"entrypoint": "python script.py"}
            )
            assert result["status"] == "submitted"
            assert result["job_id"] == "job123"

    # Add more integration tests as needed, using registry.execute_tool or the actual server interface


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
