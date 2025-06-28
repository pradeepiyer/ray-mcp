#!/usr/bin/env python3
"""Integration tests for Ray MCP server."""

import asyncio
import inspect
import json
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from mcp.types import TextContent
import pytest

from ray_mcp.ray_manager import RayManager
from ray_mcp.tool_registry import ToolRegistry


def get_text_content(result) -> str:
    """Extract text content from MCP response."""
    if isinstance(result, list) and len(result) > 0:
        if hasattr(result[0], "text"):
            return result[0].text
        elif isinstance(result[0], dict) and "text" in result[0]:
            return result[0]["text"]
    return str(result)


async def call_tool(
    tool_name: str, arguments: Optional[Dict[str, Any]] = None
) -> List[TextContent]:
    """Helper function to call a tool through the registry."""
    registry = ToolRegistry(RayManager())
    result = await registry.execute_tool(tool_name, arguments or {})
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


@pytest.mark.integration
class TestMCPIntegration:
    """Integration tests for MCP server functionality."""

    @pytest.fixture(autouse=True)
    def patch_ray_manager(self):
        """Patch RayManager to avoid actual Ray operations."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            yield

    @pytest.mark.asyncio
    async def test_list_tools_returns_all_tools(self):
        """Test that list_tools returns all available tools."""
        registry = ToolRegistry(RayManager())
        tools = registry.get_tool_list()

        # Check that we have the expected tools
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
            assert expected_tool in tool_names, f"Missing tool: {expected_tool}"

        # Check that all tools have proper schemas
        for tool in tools:
            assert hasattr(tool, "inputSchema")
            assert isinstance(tool.inputSchema, dict)

    @pytest.mark.asyncio
    async def test_tool_schemas_are_valid(self):
        """Test that tool schemas are valid JSON schemas."""
        registry = ToolRegistry(RayManager())
        tools = registry.get_tool_list()

        for tool in tools:
            schema = tool.inputSchema
            assert "type" in schema
            assert schema["type"] == "object"
            if "properties" in schema:
                assert isinstance(schema["properties"], dict)

    @pytest.mark.asyncio
    async def test_complete_workflow_cluster_management(self):
        """Test complete workflow for cluster management."""
        registry = ToolRegistry(RayManager())

        # Mock RayManager methods
        with patch.object(registry.ray_manager, "init_cluster") as mock_init:
            with patch.object(registry.ray_manager, "stop_cluster") as mock_stop:
                mock_init.return_value = {
                    "status": "started",
                    "cluster_address": "ray://127.0.0.1:10001",
                }
                mock_stop.return_value = {
                    "status": "stopped",
                    "message": "Ray cluster stopped successfully",
                }

                # Test cluster initialization
                result = await registry.execute_tool("init_ray", {"num_cpus": 4})
                assert result["status"] == "started"
                mock_init.assert_called_once()

                # Test cluster stop
                result = await registry.execute_tool("stop_ray", {})
                assert result["status"] == "stopped"
                mock_stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_workflow_job_lifecycle(self):
        """Test complete workflow for job lifecycle."""
        registry = ToolRegistry(RayManager())

        # Mock RayManager methods
        with patch.object(registry.ray_manager, "submit_job") as mock_submit:
            with patch.object(registry.ray_manager, "inspect_job") as mock_inspect:
                with patch.object(registry.ray_manager, "cancel_job") as mock_cancel:
                    mock_submit.return_value = {
                        "status": "submitted",
                        "job_id": "job_123",
                    }
                    mock_inspect.return_value = {
                        "status": "success",
                        "job_id": "job_123",
                        "job_status": "RUNNING",
                    }
                    mock_cancel.return_value = {
                        "status": "cancelled",
                        "job_id": "job_123",
                    }

                    # Mock Ray availability and initialization
                    with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
                        with patch("ray_mcp.ray_manager.ray") as mock_ray:
                            mock_ray.is_initialized.return_value = True
                            registry.ray_manager._is_initialized = True

                            # Test job submission
                            result = await registry.execute_tool(
                                "submit_job",
                                {"entrypoint": "python test.py"},
                            )
                            assert result["status"] == "submitted"
                            mock_submit.assert_called_once()

                            # Test job inspection
                            result = await registry.execute_tool(
                                "inspect_job", {"job_id": "job_123"}
                            )
                            assert result["status"] == "success"
                            mock_inspect.assert_called_once()

                            # Test job cancellation
                            result = await registry.execute_tool(
                                "cancel_job", {"job_id": "job_123"}
                            )
                            assert result["status"] == "cancelled"
                            mock_cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_propagation(self):
        """Test that errors are properly propagated from RayManager to tool registry."""
        registry = ToolRegistry(RayManager())

        with patch.object(registry.ray_manager, "init_cluster") as mock_init:
            mock_init.side_effect = Exception("Ray initialization failed")

            result = await registry.execute_tool("init_ray", {"num_cpus": 4})
            assert result["status"] == "error"
            assert "Ray initialization failed" in result["message"]

    @pytest.mark.asyncio
    async def test_ray_unavailable_error(self):
        """Test error handling when Ray is not available."""
        registry = ToolRegistry(RayManager())

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", False):
            result = await registry.execute_tool("init_ray", {"num_cpus": 4})
            assert result["status"] == "error"
            assert "Ray is not available" in result["message"]

    @pytest.mark.asyncio
    async def test_parameter_validation_integration(self):
        """Test parameter validation at the integration level."""
        registry = ToolRegistry(RayManager())

        # Test with invalid parameters
        with patch.object(registry.ray_manager, "init_cluster") as mock_init:
            mock_init.return_value = {"status": "started"}

            # Test with valid parameters
            result = await registry.execute_tool(
                "init_ray", {"num_cpus": 4, "num_gpus": 1}
            )
            assert result["status"] == "started"

            # Verify that parameters were passed correctly
            mock_init.assert_called_once()
            call_args = mock_init.call_args[1]
            assert call_args["num_cpus"] == 4
            assert call_args["num_gpus"] == 1

    @pytest.mark.asyncio
    async def test_response_format_consistency(self):
        """Test that all tool responses have consistent format."""
        registry = ToolRegistry(RayManager())

        with patch.object(registry.ray_manager, "init_cluster") as mock_init:
            mock_init.return_value = {
                "status": "started",
                "cluster_address": "ray://127.0.0.1:10001",
            }

            result = await registry.execute_tool("init_ray", {"num_cpus": 4})

            # Check response format
            assert isinstance(result, dict)
            assert "status" in result
            assert isinstance(result["status"], str)

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self):
        """Test that multiple tool calls can be made concurrently."""
        registry = ToolRegistry(RayManager())

        with patch.object(registry.ray_manager, "init_cluster") as mock_init:
            mock_init.return_value = {"status": "started"}

            # Make concurrent calls
            tasks = [
                registry.execute_tool("init_ray", {"num_cpus": 4}),
                registry.execute_tool("init_ray", {"num_cpus": 8}),
                registry.execute_tool("init_ray", {"num_cpus": 2}),
            ]

            results = await asyncio.gather(*tasks)

            # All calls should succeed
            for result in results:
                assert result["status"] == "started"

            # All calls should have been made
            assert mock_init.call_count == 3

    @pytest.mark.asyncio
    async def test_tool_call_with_complex_parameters(self):
        """Test tool calls with complex parameter structures."""
        registry = ToolRegistry(RayManager())

        with patch.object(registry.ray_manager, "init_cluster") as mock_init:
            mock_init.return_value = {"status": "started"}

            complex_params = {
                "num_cpus": 4,
                "num_gpus": 1,
                "object_store_memory": 1000000000,
                "worker_nodes": [
                    {"num_cpus": 2, "num_gpus": 0, "node_name": "worker-1"},
                    {"num_cpus": 2, "num_gpus": 1, "node_name": "worker-2"},
                ],
                "dashboard_port": 8265,
                "head_node_host": "127.0.0.1",
            }

            result = await registry.execute_tool("init_ray", complex_params)
            assert result["status"] == "started"

            # Verify complex parameters were passed correctly
            mock_init.assert_called_once()
            call_args = mock_init.call_args[1]
            assert call_args["num_cpus"] == 4
            assert call_args["worker_nodes"] == complex_params["worker_nodes"]

    @pytest.mark.asyncio
    async def test_retrieve_logs_tool(self):
        """Test retrieve_logs tool integration."""
        registry = ToolRegistry(RayManager())

        with patch.object(registry.ray_manager, "retrieve_logs") as mock_retrieve:
            mock_retrieve.return_value = {
                "status": "success",
                "logs": "Job log line 1\nJob log line 2",
                "log_type": "job",
                "identifier": "job_123",
            }

            result = await registry.execute_tool(
                "retrieve_logs",
                {
                    "identifier": "job_123",
                    "log_type": "job",
                    "num_lines": 100,
                    "include_errors": False,
                },
            )

            assert result["status"] == "success"
            assert "logs" in result
            assert result["log_type"] == "job"
            assert result["identifier"] == "job_123"

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


@pytest.mark.integration
class TestIntegration:
    # Add more integration tests as needed, using registry.execute_tool or the actual server interface
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
