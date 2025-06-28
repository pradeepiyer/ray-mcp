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
            "job_inspect",
            "cancel_job",
            "list_actors",
            "kill_actor",
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

        job_inspect_mock = AsyncMock(
            return_value={"status": "success", "job_status": "RUNNING"}
        )
        job_inspect_mock.__signature__ = inspect.signature(RayManager.job_inspect)

        list_jobs_mock = AsyncMock(return_value={"jobs": [{"job_id": "job123"}]})
        list_jobs_mock.__signature__ = inspect.signature(RayManager.list_jobs)

        cancel_job_mock = AsyncMock(return_value={"status": "cancelled"})
        cancel_job_mock.__signature__ = inspect.signature(RayManager.cancel_job)

        with patch.object(RayManager, "start_cluster", start_cluster_mock):
            with patch.object(RayManager, "submit_job", submit_job_mock):
                with patch.object(RayManager, "job_inspect", job_inspect_mock):
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
                                "job_inspect", {"job_id": "job123"}
                            )
                            assert result["status"] == "success"
                            assert result["job_status"] == "RUNNING"

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

        job_inspect_mock = AsyncMock(
            return_value={"status": "success", "job_status": "RUNNING"}
        )
        job_inspect_mock.__signature__ = inspect.signature(RayManager.job_inspect)

        with (
            patch.object(ray_manager, "start_cluster", start_cluster_mock),
            patch.object(ray_manager, "job_inspect", job_inspect_mock),
        ):
            with patch("ray_mcp.main.RAY_AVAILABLE", True):
                result = await call_tool("job_inspect", {"job_id": "test_job"})
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

        mock_ray_manager.start_cluster = start_cluster_mock
        mock_ray_manager.list_jobs = list_jobs_mock

        with patch("ray_mcp.main.ray_manager", mock_ray_manager):
            with patch("ray_mcp.main.RAY_AVAILABLE", True):

                # Test multiple tools
                tools_to_test = ["start_ray", "list_jobs", "cluster_info"]

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
        """Test tool calls with complex nested parameters."""
        registry = ToolRegistry(RayManager())

        # Mock RayManager methods
        start_cluster_mock = AsyncMock(return_value={"status": "success"})
        start_cluster_mock.__signature__ = inspect.signature(RayManager.start_cluster)

        submit_job_mock = AsyncMock(return_value={"status": "submitted"})
        submit_job_mock.__signature__ = inspect.signature(RayManager.submit_job)

        with patch.object(RayManager, "start_cluster", start_cluster_mock):
            with patch.object(RayManager, "submit_job", submit_job_mock):

                # Test complex runtime environment
                complex_runtime_env = {
                    "pip": ["torch==2.0.0", "transformers", "datasets"],
                    "conda": {"channels": ["conda-forge"], "dependencies": ["numpy"]},
                    "env_vars": {
                        "CUDA_VISIBLE_DEVICES": "0,1",
                        "PYTHONPATH": "/custom/path",
                        "OMP_NUM_THREADS": "4",
                    },
                    "working_dir": "/tmp/custom_working_dir",
                }

                result = await registry.execute_tool(
                    "submit_job",
                    {
                        "entrypoint": "python train.py --epochs 100 --batch_size 32",
                        "runtime_env": complex_runtime_env,
                        "job_id": "complex_job_123",
                        "metadata": {
                            "owner": "ml_team",
                            "project": "transformer_training",
                            "priority": "high",
                        },
                    },
                )

                assert result["status"] == "submitted"

                # Verify complex parameters were passed correctly
                submit_job_mock.assert_called_once()
                call_args = submit_job_mock.call_args[1]
                assert call_args["runtime_env"] == complex_runtime_env
                assert call_args["job_id"] == "complex_job_123"

    # ===== UNIQUE TESTS FROM test_mcp_tools.py =====

    @pytest.mark.asyncio
    async def test_list_actors_tool_with_filters(self):
        """Test list_actors tool with filters."""
        registry = ToolRegistry(RayManager())

        # Mock RayManager method
        list_actors_mock = AsyncMock(
            return_value={
                "status": "success",
                "actors": [
                    {"actor_id": "actor_1", "state": "ALIVE"},
                    {"actor_id": "actor_2", "state": "DEAD"},
                ],
            }
        )
        list_actors_mock.__signature__ = inspect.signature(RayManager.list_actors)

        with patch.object(RayManager, "list_actors", list_actors_mock):
            filters = {"namespace": "test"}
            result = await registry.execute_tool("list_actors", {"filters": filters})

            assert isinstance(result, dict)
            assert len(result["actors"]) == 2
            list_actors_mock.assert_called_once_with(filters)

    @pytest.mark.asyncio
    async def test_kill_actor_tool(self):
        """Test kill_actor tool."""
        registry = ToolRegistry(RayManager())

        # Mock RayManager method
        kill_actor_mock = AsyncMock(
            return_value={"status": "killed", "actor_id": "actor_123"}
        )
        kill_actor_mock.__signature__ = inspect.signature(RayManager.kill_actor)

        with patch.object(RayManager, "kill_actor", kill_actor_mock):
            result = await registry.execute_tool(
                "kill_actor", {"actor_id": "actor_123", "no_restart": True}
            )

            assert isinstance(result, dict)
            assert result["status"] == "killed"
            kill_actor_mock.assert_called_once_with(
                actor_id="actor_123", no_restart=True
            )

    @pytest.mark.asyncio
    async def test_get_logs_tool(self):
        """Test get_logs tool."""
        registry = ToolRegistry(RayManager())

        # Mock RayManager method
        get_logs_mock = AsyncMock(
            return_value={
                "status": "success",
                "logs": ["log line 1", "log line 2"],
            }
        )
        get_logs_mock.__signature__ = inspect.signature(RayManager.get_logs)

        with patch.object(RayManager, "get_logs", get_logs_mock):
            result = await registry.execute_tool("get_logs", {"job_id": "test_job"})

            assert isinstance(result, dict)
            assert "logs" in result
            get_logs_mock.assert_called_once_with(job_id="test_job", num_lines=100)

    @pytest.mark.asyncio
    async def test_ray_unavailable_error(self):
        """Test tool calls when Ray is not available."""
        registry = ToolRegistry(RayManager())

        # Mock RayManager method to raise an exception
        start_cluster_mock = AsyncMock(side_effect=Exception("Ray is not available"))
        start_cluster_mock.__signature__ = inspect.signature(RayManager.start_cluster)

        with patch.object(RayManager, "start_cluster", start_cluster_mock):
            result = await registry.execute_tool(
                "start_ray", {"num_cpus": 4, "num_gpus": 1}
            )

            assert isinstance(result, dict)
            assert result["status"] == "error"
            assert "Ray is not available" in result["message"]

    @pytest.mark.asyncio
    async def test_unknown_tool_error(self):
        """Test calling unknown tool."""
        registry = ToolRegistry(RayManager())

        result = await registry.execute_tool("unknown_tool", {})

        assert isinstance(result, dict)
        assert result["status"] == "error"
        assert "Unknown tool" in result["message"]

    # ===== PARAMETER FLOW TESTS FROM test_tool_functions.py AND test_full_parameter_flow.py =====

    @pytest.mark.asyncio
    async def test_parameter_isolation_get_logs(self):
        """Test that get_logs function only passes expected parameters."""
        registry = ToolRegistry(RayManager())
        called_params = {}

        async def fake_get_logs(**kwargs):
            called_params.update(kwargs)
            return {
                "status": "success",
                "logs": "Sample log output...",
                "job_id": "job_123",
            }

        mock = AsyncMock(side_effect=fake_get_logs)
        mock.__signature__ = inspect.signature(RayManager.get_logs)

        with patch.object(RayManager, "get_logs", mock):
            with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
                with patch("ray_mcp.ray_manager.ray") as mock_ray:
                    mock_ray.is_initialized.return_value = True
                    registry.ray_manager._is_initialized = True

                    result = await registry.execute_tool(
                        "get_logs", {"job_id": "test_job_123", "num_lines": 50}
                    )

                    # Verify only expected parameters are passed to RayManager
                    expected_params = {"job_id", "num_lines"}
                    actual_params = set(called_params.keys())
                    unexpected_params = actual_params - expected_params

                    assert (
                        not unexpected_params
                    ), f"Unexpected parameters passed to RayManager: {unexpected_params}"
                    assert called_params["job_id"] == "test_job_123"
                    assert called_params["num_lines"] == 50

    @pytest.mark.asyncio
    async def test_parameter_isolation_start_ray(self):
        """Test that start_ray function only passes expected parameters."""
        registry = ToolRegistry(RayManager())
        called_params = {}

        async def fake_start_cluster(**kwargs):
            called_params.update(kwargs)
            return {
                "status": "started",
                "address": "ray://127.0.0.1:10001",
            }

        mock = AsyncMock(side_effect=fake_start_cluster)
        mock.__signature__ = inspect.signature(RayManager.start_cluster)

        with patch.object(RayManager, "start_cluster", mock):
            result = await registry.execute_tool(
                "start_ray", {"num_cpus": 4, "num_gpus": 1, "head_node_port": 10001}
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
    async def test_parameter_flow_with_extra_parameters(self):
        """Test that extra parameters are not passed through the stack."""
        registry = ToolRegistry(RayManager())
        called_params = {}

        async def fake_get_logs(**kwargs):
            called_params.update(kwargs)
            return {
                "status": "success",
                "logs": "Sample log output...",
            }

        mock = AsyncMock(side_effect=fake_get_logs)
        mock.__signature__ = inspect.signature(RayManager.get_logs)

        with patch.object(RayManager, "get_logs", mock):
            with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
                with patch("ray_mcp.ray_manager.ray") as mock_ray:
                    mock_ray.is_initialized.return_value = True
                    registry.ray_manager._is_initialized = True
                    result = await registry.execute_tool(
                        "get_logs",
                        {
                            "job_id": "test_job_123",
                            "num_lines": 50,
                            "extra_param": "should_not_be_passed",
                            "tool_registry": "should_not_be_passed",
                        },
                    )
                    forbidden_params = {"extra_param", "tool_registry"}
                    actual_params = set(called_params.keys())
                    passed_forbidden_params = actual_params & forbidden_params
                    assert (
                        not passed_forbidden_params
                    ), f"Forbidden parameters passed to RayManager: {passed_forbidden_params}"

    @pytest.mark.asyncio
    async def test_parameter_flow_error_handling(self):
        """Test parameter flow error handling through the stack."""
        registry = ToolRegistry(RayManager())

        # Mock the RayManager method to raise an exception
        mock = AsyncMock(side_effect=Exception("Test error"))
        mock.__signature__ = inspect.signature(RayManager.get_logs)

        with patch.object(RayManager, "get_logs", mock):
            with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
                with patch("ray_mcp.ray_manager.ray") as mock_ray:
                    mock_ray.is_initialized.return_value = True
                    registry.ray_manager._is_initialized = True

                    result = await registry.execute_tool(
                        "get_logs", {"job_id": "test_job_123"}
                    )

                    # Verify error is properly handled and returned
                    assert result["status"] == "error"
                    assert "Test error" in result["message"]

    @pytest.mark.asyncio
    async def test_job_inspect_tool(self):
        """Test job_inspect tool with different modes."""
        registry = ToolRegistry(RayManager())

        # Mock RayManager method
        job_inspect_mock = AsyncMock(
            return_value={
                "status": "success",
                "job_id": "job_123",
                "job_status": "RUNNING",
                "entrypoint": "python test.py",
                "inspection_mode": "status",
            }
        )
        job_inspect_mock.__signature__ = inspect.signature(RayManager.job_inspect)

        with patch.object(RayManager, "job_inspect", job_inspect_mock):
            # Test status mode (default)
            result = await registry.execute_tool("job_inspect", {"job_id": "job_123"})
            assert isinstance(result, dict)
            assert result["job_status"] == "RUNNING"
            assert result["inspection_mode"] == "status"
            job_inspect_mock.assert_called_with("job_123", "status")

            # Test logs mode
            job_inspect_mock.return_value["inspection_mode"] = "logs"
            job_inspect_mock.return_value["logs"] = "Job log line 1\nJob log line 2"
            result = await registry.execute_tool(
                "job_inspect", {"job_id": "job_123", "mode": "logs"}
            )
            assert "logs" in result
            assert result["inspection_mode"] == "logs"
            job_inspect_mock.assert_called_with("job_123", "logs")

            # Test debug mode
            job_inspect_mock.return_value["inspection_mode"] = "debug"
            job_inspect_mock.return_value["debug_info"] = {
                "error_logs": [],
                "debugging_suggestions": [],
            }
            result = await registry.execute_tool(
                "job_inspect", {"job_id": "job_123", "mode": "debug"}
            )
            assert "debug_info" in result
            assert result["inspection_mode"] == "debug"
            job_inspect_mock.assert_called_with("job_123", "debug")


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
