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
            "init_ray",
            "stop_ray",
            "inspect_ray",
            "submit_job",
            "list_jobs",
            "inspect_job",
            "cancel_job",
            "retrieve_logs",
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
        """Test complete workflow for cluster management."""
        registry = ToolRegistry(RayManager())
        # Mock the ray manager to avoid actual Ray operations
        start_cluster_mock = AsyncMock(
            return_value={
                "status": "started",
                "cluster_address": "ray://localhost:10001",
            }
        )
        start_cluster_mock.__signature__ = inspect.signature(RayManager.init_cluster)

        with patch.object(RayManager, "init_cluster", start_cluster_mock):
            # Test cluster initialization
            result = await registry.execute_tool("init_ray", {"num_cpus": 8})
            assert result["status"] == "started"
            start_cluster_mock.assert_called_once()

            # Test cluster info
            inspect_ray_mock = AsyncMock(return_value={"status": "success"})
            inspect_ray_mock.__signature__ = inspect.signature(RayManager.inspect_ray)

            with patch.object(RayManager, "inspect_ray", inspect_ray_mock):
                result = await registry.execute_tool("inspect_ray")
                assert result["status"] == "success"
                inspect_ray_mock.assert_called_once()

            # Test cluster stop
            stop_cluster_mock = AsyncMock(return_value={"status": "stopped"})
            stop_cluster_mock.__signature__ = inspect.signature(RayManager.stop_cluster)

            with patch.object(RayManager, "stop_cluster", stop_cluster_mock):
                result = await registry.execute_tool("stop_ray")
                assert result["status"] == "stopped"
                stop_cluster_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_workflow_job_lifecycle(self):
        """Test complete workflow for job lifecycle."""
        registry = ToolRegistry(RayManager())
        # Mock the ray manager to avoid actual Ray operations
        start_cluster_mock = AsyncMock(return_value={"status": "success"})
        start_cluster_mock.__signature__ = inspect.signature(RayManager.init_cluster)

        with patch.object(RayManager, "init_cluster", start_cluster_mock):
            # Test cluster initialization
            result = await registry.execute_tool("init_ray", {"num_cpus": 4})
            assert result["status"] == "success"
            start_cluster_mock.assert_called_once()

            # Test job submission
            submit_job_mock = AsyncMock(
                return_value={"status": "submitted", "job_id": "job_123"}
            )
            submit_job_mock.__signature__ = inspect.signature(RayManager.submit_job)

            with patch.object(RayManager, "submit_job", submit_job_mock):
                result = await registry.execute_tool(
                    "submit_job", {"entrypoint": "python test.py"}
                )
                assert result["status"] == "submitted"
                submit_job_mock.assert_called_once()

            # Test job listing
            list_jobs_mock = AsyncMock(return_value={"status": "success", "jobs": []})
            list_jobs_mock.__signature__ = inspect.signature(RayManager.list_jobs)

            with patch.object(RayManager, "list_jobs", list_jobs_mock):
                result = await registry.execute_tool("list_jobs")
                assert result["status"] == "success"
                list_jobs_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_propagation(self):
        """Test that errors are properly propagated through the tool execution."""
        registry = ToolRegistry(RayManager())
        # Mock the ray manager to raise an exception
        start_cluster_mock = AsyncMock(side_effect=Exception("Test error"))
        start_cluster_mock.__signature__ = inspect.signature(RayManager.init_cluster)

        with patch.object(RayManager, "init_cluster", start_cluster_mock):
            result = await registry.execute_tool("init_ray", {"num_cpus": 4})
            assert result["status"] == "error"
            assert "Test error" in result["message"]

    @pytest.mark.asyncio
    async def test_ray_unavailable_error(self):
        """Test error handling when Ray is not available."""
        registry = ToolRegistry(RayManager())
        # Mock the ray manager to simulate Ray unavailability
        start_cluster_mock = AsyncMock(side_effect=Exception("Ray is not available"))
        start_cluster_mock.__signature__ = inspect.signature(RayManager.init_cluster)

        with patch.object(RayManager, "init_cluster", start_cluster_mock):
            result = await registry.execute_tool("init_ray", {"num_cpus": 4})
            assert result["status"] == "error"
            assert "Ray is not available" in result["message"]

    @pytest.mark.asyncio
    async def test_parameter_validation_integration(self):
        """Test parameter validation in the complete tool execution flow."""
        registry = ToolRegistry(RayManager())
        # Mock the ray manager to return success
        start_cluster_mock = AsyncMock(return_value={"status": "started"})
        start_cluster_mock.__signature__ = inspect.signature(RayManager.init_cluster)

        with patch.object(RayManager, "init_cluster", start_cluster_mock):
            # Test with valid parameters
            result = await registry.execute_tool(
                "init_ray", {"num_cpus": 4, "num_gpus": 1}
            )
            assert result["status"] == "started"
            start_cluster_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_response_format_consistency(self):
        """Test that all tools return consistent response formats."""
        registry = ToolRegistry(RayManager())
        # Mock the ray manager to return a consistent response
        start_cluster_mock = AsyncMock(return_value={"status": "started"})
        start_cluster_mock.__signature__ = inspect.signature(RayManager.init_cluster)

        with patch.object(RayManager, "init_cluster", start_cluster_mock):
            result = await registry.execute_tool("init_ray", {"num_cpus": 4})
            assert isinstance(result, dict)
            assert "status" in result
            assert result["status"] == "started"

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self):
        """Test that multiple tool calls work correctly."""
        registry = ToolRegistry(RayManager())
        # Mock the ray manager to return success
        start_cluster_mock = AsyncMock(return_value={"status": "started"})
        start_cluster_mock.__signature__ = inspect.signature(RayManager.init_cluster)

        with patch.object(RayManager, "init_cluster", start_cluster_mock):
            # Make multiple concurrent calls
            tasks = [
                registry.execute_tool("init_ray", {"num_cpus": 4}),
                registry.execute_tool("init_ray", {"num_cpus": 8}),
            ]
            results = await asyncio.gather(*tasks)

            # Verify all calls succeeded
            for result in results:
                assert result["status"] == "started"

            # Verify the mock was called twice
            assert start_cluster_mock.call_count == 2

    @pytest.mark.asyncio
    async def test_tool_call_with_complex_parameters(self):
        """Test tool calls with complex parameter structures."""
        registry = ToolRegistry(RayManager())
        # Mock the ray manager to return success
        start_cluster_mock = AsyncMock(return_value={"status": "started"})
        start_cluster_mock.__signature__ = inspect.signature(RayManager.init_cluster)

        with patch.object(RayManager, "init_cluster", start_cluster_mock):
            # Test with complex worker node configuration
            complex_params = {
                "num_cpus": 4,
                "num_gpus": 1,
                "worker_nodes": [
                    {
                        "num_cpus": 2,
                        "num_gpus": 0,
                        "node_name": "cpu-worker",
                        "resources": {"custom_resource": 1},
                    },
                    {
                        "num_cpus": 2,
                        "num_gpus": 1,
                        "node_name": "gpu-worker",
                        "resources": {"custom_resource": 2},
                    },
                ],
            }

            result = await registry.execute_tool("init_ray", complex_params)
            assert result["status"] == "started"
            start_cluster_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_logs_tool(self):
        """Test retrieve_logs tool functionality."""
        registry = ToolRegistry(RayManager())
        # Mock the ray manager to return success
        start_cluster_mock = AsyncMock(return_value={"status": "started"})
        start_cluster_mock.__signature__ = inspect.signature(RayManager.init_cluster)

        with patch.object(RayManager, "init_cluster", start_cluster_mock):
            # First initialize the cluster
            result = await registry.execute_tool("init_ray", {"num_cpus": 4})
            assert result["status"] == "started"

            # Then test retrieve_logs
            retrieve_logs_mock = AsyncMock(return_value={"status": "success"})
            retrieve_logs_mock.__signature__ = inspect.signature(
                RayManager.retrieve_logs
            )

            with patch.object(RayManager, "retrieve_logs", retrieve_logs_mock):
                result = await registry.execute_tool(
                    "retrieve_logs",
                    {
                        "identifier": "job_123",
                        "log_type": "job",
                        "num_lines": 100,
                        "include_errors": True,
                    },
                )
                assert result["status"] == "success"
                retrieve_logs_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_tool_error(self):
        """Test error handling for unknown tools."""
        registry = ToolRegistry(RayManager())
        result = await registry.execute_tool("unknown_tool", {})
        assert result["status"] == "error"
        assert "Unknown tool" in result["message"]

    @pytest.mark.asyncio
    async def test_parameter_isolation_init_ray(self):
        """Test that init_ray function only passes expected parameters."""
        registry = ToolRegistry(RayManager())
        called_params = {}

        async def fake_init_cluster(**kwargs):
            called_params.update(kwargs)
            return {
                "status": "started",
                "address": "ray://127.0.0.1:10001",
            }

        mock = AsyncMock(side_effect=fake_init_cluster)
        mock.__signature__ = inspect.signature(RayManager.init_cluster)

        with patch.object(RayManager, "init_cluster", mock):
            result = await registry.execute_tool(
                "init_ray", {"num_cpus": 4, "num_gpus": 1, "head_node_port": 10001}
            )
            expected_params = {"num_cpus", "num_gpus", "head_node_port"}
            actual_params = set(called_params.keys())
            unexpected_params = actual_params - expected_params
            assert (
                not unexpected_params
            ), f"Unexpected parameters passed to RayManager: {unexpected_params}"
            assert called_params["num_cpus"] == 4
            assert called_params["num_gpus"] == 1
            assert called_params["head_node_port"] == 10001

    @pytest.mark.asyncio
    async def test_parameter_isolation_submit_job(self):
        """Test that submit_job function only passes expected parameters."""
        registry = ToolRegistry(RayManager())
        called_params = {}

        async def fake_submit_job(**kwargs):
            called_params.update(kwargs)
            return {
                "status": "submitted",
                "job_id": "job_123",
            }

        mock = AsyncMock(side_effect=fake_submit_job)
        mock.__signature__ = inspect.signature(RayManager.submit_job)

        with patch.object(RayManager, "submit_job", mock):
            with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
                with patch("ray_mcp.ray_manager.ray") as mock_ray:
                    mock_ray.is_initialized.return_value = True
                    registry.ray_manager._is_initialized = True
                    result = await registry.execute_tool(
                        "submit_job",
                        {
                            "entrypoint": "python test.py",
                            "runtime_env": {"pip": ["requests"]},
                            "job_id": "custom_job_id",
                        },
                    )
                    expected_params = {"entrypoint", "runtime_env", "job_id"}
                    actual_params = set(called_params.keys())
                    unexpected_params = actual_params - expected_params
                    assert (
                        not unexpected_params
                    ), f"Unexpected parameters passed to RayManager: {unexpected_params}"
                    assert called_params["entrypoint"] == "python test.py"
                    assert called_params["runtime_env"] == {"pip": ["requests"]}
                    assert called_params["job_id"] == "custom_job_id"

    @pytest.mark.asyncio
    async def test_inspect_job_tool(self):
        """Test inspect_job tool with different modes."""
        registry = ToolRegistry(RayManager())

        # Mock RayManager method
        inspect_job_mock = AsyncMock(
            return_value={
                "status": "success",
                "job_id": "job_123",
                "job_status": "RUNNING",
                "entrypoint": "python test.py",
                "inspection_mode": "status",
            }
        )
        inspect_job_mock.__signature__ = inspect.signature(RayManager.inspect_job)

        with patch.object(RayManager, "inspect_job", inspect_job_mock):
            # Test status mode (default)
            result = await registry.execute_tool("inspect_job", {"job_id": "job_123"})
            assert isinstance(result, dict)
            assert result["job_status"] == "RUNNING"
            assert result["inspection_mode"] == "status"
            inspect_job_mock.assert_called_with("job_123", "status")

            # Test logs mode
            inspect_job_mock.return_value["inspection_mode"] = "logs"
            inspect_job_mock.return_value["logs"] = "Job log line 1\nJob log line 2"
            result = await registry.execute_tool(
                "inspect_job", {"job_id": "job_123", "mode": "logs"}
            )
            assert "logs" in result
            assert result["inspection_mode"] == "logs"
            inspect_job_mock.assert_called_with("job_123", "logs")

            # Test debug mode
            inspect_job_mock.return_value["inspection_mode"] = "debug"
            inspect_job_mock.return_value["debug_info"] = {
                "error_logs": [],
                "debugging_suggestions": [],
            }
            result = await registry.execute_tool(
                "inspect_job", {"job_id": "job_123", "mode": "debug"}
            )
            assert "debug_info" in result
            assert result["inspection_mode"] == "debug"
            inspect_job_mock.assert_called_with("job_123", "debug")

    @pytest.mark.asyncio
    async def test_init_ray_basic_functionality(self):
        """Test basic init_ray functionality."""
        registry = ToolRegistry(RayManager())
        # Mock the ray manager to avoid actual Ray operations
        with patch.object(registry.ray_manager, "init_cluster") as mock_init:
            mock_init.return_value = {
                "status": "started",
                "cluster_address": "ray://localhost:10001",
            }

            result = await registry.execute_tool("init_ray", {"num_cpus": 8})
            assert result["status"] == "started"
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_ray_with_worker_nodes(self):
        """Test init_ray with worker node configuration."""
        registry = ToolRegistry(RayManager())
        worker_config = [
            {"num_cpus": 2, "num_gpus": 1, "node_name": "worker-1"},
            {"num_cpus": 2, "num_gpus": 0, "node_name": "worker-2"},
        ]

        with patch.object(registry.ray_manager, "init_cluster") as mock_init:
            mock_init.return_value = {
                "status": "started",
                "cluster_address": "ray://localhost:10001",
            }

            result = await registry.execute_tool(
                "init_ray", {"num_cpus": 4, "worker_nodes": worker_config}
            )
            assert result["status"] == "started"
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_ray_connect_to_existing(self):
        """Test init_ray connecting to existing cluster."""
        registry = ToolRegistry(RayManager())
        with patch.object(registry.ray_manager, "init_cluster") as mock_init:
            mock_init.return_value = {
                "status": "connected",
                "cluster_address": "ray://localhost:10001",
            }

            result = await registry.execute_tool(
                "init_ray", {"address": "ray://localhost:10001"}
            )
            assert result["status"] == "connected"
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_ray_with_gpu_configuration(self):
        """Test init_ray with GPU configuration."""
        registry = ToolRegistry(RayManager())
        with patch.object(registry.ray_manager, "init_cluster") as mock_init:
            mock_init.return_value = {
                "status": "started",
                "cluster_address": "ray://localhost:10001",
            }

            result = await registry.execute_tool(
                "init_ray", {"num_cpus": 4, "num_gpus": 1}
            )
            assert result["status"] == "started"
            mock_init.assert_called_once()


@pytest.mark.integration
class TestIntegration:
    # Add more integration tests as needed, using registry.execute_tool or the actual server interface
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
