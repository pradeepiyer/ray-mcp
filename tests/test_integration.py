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


@pytest.mark.integration
class TestMCPIntegration:
    """Essential integration tests for MCP server functionality."""

    @pytest.fixture(autouse=True)
    def patch_ray_manager(self):
        """Patch RayManager to avoid actual Ray operations."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            yield

    @pytest.mark.asyncio
    async def test_complete_workflow_cluster_and_job_lifecycle(self):
        """Test complete workflow: cluster init -> job submit -> job inspect -> job cancel -> cluster stop."""
        registry = ToolRegistry(RayManager())

        # Mock RayManager methods for complete workflow
        with patch.object(registry.ray_manager, "init_cluster") as mock_init:
            with patch.object(registry.ray_manager, "submit_job") as mock_submit:
                with patch.object(registry.ray_manager, "inspect_job") as mock_inspect:
                    with patch.object(registry.ray_manager, "cancel_job") as mock_cancel:
                        with patch.object(registry.ray_manager, "stop_cluster") as mock_stop:
                            # Setup mock responses
                            mock_init.return_value = {
                                "status": "connected",
                                "message": "Successfully connected to Ray cluster at 127.0.0.1:10001",
                                "cluster_address": "127.0.0.1:10001",
                                "dashboard_url": "http://127.0.0.1:8265",
                                "node_id": "node_123",
                                "job_client_status": "ready",
                            }
                            mock_submit.return_value = {
                                "status": "success",
                                "result_type": "submitted",
                                "job_id": "job_123",
                            }
                            mock_inspect.return_value = {
                                "status": "success",
                                "job_id": "job_123",
                                "job_status": "RUNNING",
                            }
                            mock_cancel.return_value = {
                                "status": "success",
                                "result_type": "cancelled",
                                "job_id": "job_123",
                            }
                            mock_stop.return_value = {
                                "status": "stopped",
                                "message": "Ray cluster stopped successfully",
                            }

                            # Mock Ray availability and initialization for job operations
                            with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
                                with patch("ray_mcp.ray_manager.ray") as mock_ray:
                                    mock_ray.is_initialized.return_value = True
                                    registry.ray_manager._update_state(initialized=True)

                                    # Test complete workflow
                                    # 1. Initialize cluster
                                    result = await registry.execute_tool("init_ray", {"num_cpus": 4})
                                    assert result["status"] == "connected"
                                    mock_init.assert_called_once()

                                    # 2. Submit job
                                    result = await registry.execute_tool(
                                        "submit_job", {"entrypoint": "python test.py"}
                                    )
                                    assert result["status"] == "success"
                                    assert result["result_type"] == "submitted"
                                    assert "job_id" in result
                                    mock_submit.assert_called_once()

                                    # 3. Inspect job
                                    result = await registry.execute_tool(
                                        "inspect_job", {"job_id": "job_123"}
                                    )
                                    assert result["status"] == "success"
                                    mock_inspect.assert_called_once()

                                    # 4. Cancel job
                                    result = await registry.execute_tool(
                                        "cancel_job", {"job_id": "job_123"}
                                    )
                                    assert result["status"] == "success"
                                    assert result.get("result_type") == "cancelled"
                                    mock_cancel.assert_called_once()

                                    # 5. Stop cluster
                                    result = await registry.execute_tool("stop_ray", {})
                                    assert result["status"] == "stopped"
                                    mock_stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_tool_list_and_schema_validation(self):
        """Test that all tools are available with valid schemas."""
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

        # Check that all tools have valid schemas
        for tool in tools:
            assert hasattr(tool, "inputSchema")
            assert isinstance(tool.inputSchema, dict)
            assert "type" in tool.inputSchema
            assert tool.inputSchema["type"] == "object"

    @pytest.mark.asyncio
    async def test_error_propagation_and_ray_unavailable(self):
        """Test error handling when Ray is unavailable or tools fail."""
        registry = ToolRegistry(RayManager())

        # Test Ray unavailable
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", False):
            result = await registry.execute_tool("init_ray", {"num_cpus": 4})
            assert result["status"] == "error"
            assert "Ray is not available" in result["message"]

        # Test exception propagation
        with patch.object(registry.ray_manager, "init_cluster") as mock_init:
            mock_init.side_effect = Exception("Ray initialization failed")

            result = await registry.execute_tool("init_ray", {"num_cpus": 4})
            assert result["status"] == "error"
            assert "Ray initialization failed" in result["message"]

    @pytest.mark.asyncio
    async def test_parameter_validation_and_complex_params(self):
        """Test parameter validation and complex parameter structures."""
        registry = ToolRegistry(RayManager())

        with patch.object(registry.ray_manager, "init_cluster") as mock_init:
            mock_init.return_value = {"status": "connected"}

            # Test complex parameters
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
            assert result["status"] == "connected"

            # Verify complex parameters were passed correctly
            mock_init.assert_called_once()
            call_args = mock_init.call_args[1]
            assert call_args["num_cpus"] == 4
            assert call_args["worker_nodes"] == complex_params["worker_nodes"]

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self):
        """Test that multiple tool calls can be made concurrently."""
        registry = ToolRegistry(RayManager())

        with patch.object(registry.ray_manager, "init_cluster") as mock_init:
            mock_init.return_value = {"status": "connected"}

            # Make concurrent calls
            tasks = [
                registry.execute_tool("init_ray", {"num_cpus": 4}),
                registry.execute_tool("init_ray", {"num_cpus": 8}),
                registry.execute_tool("init_ray", {"num_cpus": 2}),
            ]

            results = await asyncio.gather(*tasks)

            # All calls should succeed
            for result in results:
                assert result["status"] == "connected"

            # All calls should have been made
            assert mock_init.call_count == 3

    @pytest.mark.asyncio
    async def test_inspect_job_modes(self):
        """Test inspect_job tool with different inspection modes."""
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
    async def test_retrieve_logs_integration(self):
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
    async def test_unknown_tool_and_response_format(self):
        """Test unknown tool handling and response format consistency."""
        registry = ToolRegistry(RayManager())
        
        # Test unknown tool
        result = await registry.execute_tool("unknown_tool", {})
        assert result["status"] == "error"
        assert "Unknown tool" in result["message"]

        # Test response format consistency
        with patch.object(registry.ray_manager, "init_cluster") as mock_init:
            mock_init.return_value = {
                "status": "connected",
                "message": "Successfully connected to Ray cluster at 127.0.0.1:10001",
                "cluster_address": "127.0.0.1:10001",
                "dashboard_url": "http://127.0.0.1:8265",
                "node_id": "node_123",
                "job_client_status": "ready",
            }

            result = await registry.execute_tool("init_ray", {"num_cpus": 4})

            # Check response format
            assert isinstance(result, dict)
            assert "status" in result
            assert isinstance(result["status"], str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
