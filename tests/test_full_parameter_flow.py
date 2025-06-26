#!/usr/bin/env python3
"""Tests for full parameter flow through the MCP server stack."""

import asyncio
import json
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ray_mcp.ray_manager import RayManager
from ray_mcp.tool_registry import ToolRegistry


@pytest.mark.fast
class TestFullParameterFlow:
    """Test that parameters flow correctly through the entire stack."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a real RayManager but mock its methods
        self.ray_manager = RayManager()

        # Create a real ToolRegistry
        self.tool_registry = ToolRegistry(self.ray_manager)

        # (No need to create the MCP server for these parameter flow tests)

    @pytest.mark.asyncio
    async def test_full_get_logs_parameter_flow(self):
        """Test full parameter flow for get_logs through the entire stack."""
        # Mock the RayManager method to capture what parameters it receives
        with patch.object(self.ray_manager, "get_logs") as mock_get_logs:
            mock_get_logs.return_value = {
                "status": "success",
                "logs": "Sample log output...",
                "job_id": "job_123",
            }

            # Mock Ray initialization
            with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
                with patch("ray_mcp.ray_manager.ray") as mock_ray:
                    mock_ray.is_initialized.return_value = True
                    self.ray_manager._is_initialized = True

                    # Call the tool through the registry (simulating MCP server call)
                    result = await self.tool_registry.execute_tool(
                        "get_logs", {"job_id": "test_job_123", "num_lines": 50}
                    )

                    # Verify the RayManager method was called with correct parameters
                    mock_get_logs.assert_called_once()
                    call_args = mock_get_logs.call_args

                    # Verify only expected parameters are passed to RayManager
                    expected_params = {"job_id", "num_lines"}
                    actual_params = set(call_args.kwargs.keys())
                    unexpected_params = actual_params - expected_params

                    assert (
                        not unexpected_params
                    ), f"Unexpected parameters passed to RayManager: {unexpected_params}"
                    assert call_args.kwargs["job_id"] == "test_job_123"
                    assert call_args.kwargs["num_lines"] == 50

    @pytest.mark.asyncio
    async def test_full_start_ray_parameter_flow(self):
        """Test full parameter flow for start_ray through the entire stack."""
        # Mock the RayManager method to capture what parameters it receives
        with patch.object(self.ray_manager, "start_cluster") as mock_start_cluster:
            mock_start_cluster.return_value = {
                "status": "started",
                "address": "ray://127.0.0.1:10001",
            }

            # Call the tool through the registry
            result = await self.tool_registry.execute_tool(
                "start_ray", {"num_cpus": 4, "num_gpus": 1, "head_node_port": 10001}
            )

            # Verify the RayManager method was called with correct parameters
            mock_start_cluster.assert_called_once()
            call_args = mock_start_cluster.call_args

            # Verify only expected parameters are passed to RayManager
            expected_params = {"num_cpus", "num_gpus", "head_node_port"}
            actual_params = set(call_args.kwargs.keys())
            unexpected_params = actual_params - expected_params

            assert (
                not unexpected_params
            ), f"Unexpected parameters passed to RayManager: {unexpected_params}"
            assert call_args.kwargs["num_cpus"] == 4
            assert call_args.kwargs["num_gpus"] == 1
            assert call_args.kwargs["head_node_port"] == 10001

    @pytest.mark.asyncio
    async def test_full_submit_job_parameter_flow(self):
        """Test full parameter flow for submit_job through the entire stack."""
        # Mock the RayManager method to capture what parameters it receives
        with patch.object(self.ray_manager, "submit_job") as mock_submit_job:
            mock_submit_job.return_value = {
                "status": "submitted",
                "job_id": "job_123",
            }

            # Mock Ray initialization
            with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
                with patch("ray_mcp.ray_manager.ray") as mock_ray:
                    mock_ray.is_initialized.return_value = True
                    self.ray_manager._is_initialized = True

                    # Call the tool through the registry
                    result = await self.tool_registry.execute_tool(
                        "submit_job",
                        {
                            "entrypoint": "python test.py",
                            "runtime_env": {"pip": ["requests"]},
                            "job_id": "custom_job_id",
                        },
                    )

                    # Verify the RayManager method was called with correct parameters
                    mock_submit_job.assert_called_once()
                    call_args = mock_submit_job.call_args

                    # Verify only expected parameters are passed to RayManager
                    expected_params = {"entrypoint", "runtime_env", "job_id"}
                    actual_params = set(call_args.kwargs.keys())
                    unexpected_params = actual_params - expected_params

                    assert (
                        not unexpected_params
                    ), f"Unexpected parameters passed to RayManager: {unexpected_params}"
                    assert call_args.kwargs["entrypoint"] == "python test.py"
                    assert call_args.kwargs["runtime_env"] == {"pip": ["requests"]}
                    assert call_args.kwargs["job_id"] == "custom_job_id"

    @pytest.mark.asyncio
    async def test_parameter_flow_with_extra_parameters(self):
        """Test that extra parameters are not passed through the stack."""
        # Mock the RayManager method to capture what parameters it receives
        with patch.object(self.ray_manager, "get_logs") as mock_get_logs:
            mock_get_logs.return_value = {
                "status": "success",
                "logs": "Sample log output...",
            }

            # Mock Ray initialization
            with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
                with patch("ray_mcp.ray_manager.ray") as mock_ray:
                    mock_ray.is_initialized.return_value = True
                    self.ray_manager._is_initialized = True

                    # Call with extra parameters that should be filtered out
                    result = await self.tool_registry.execute_tool(
                        "get_logs",
                        {
                            "job_id": "test_job_123",
                            "num_lines": 50,
                            "extra_param": "should_not_be_passed",
                            "tool_registry": "should_not_be_passed",
                        },
                    )

                    # Verify the RayManager method was called
                    mock_get_logs.assert_called_once()
                    call_args = mock_get_logs.call_args

                    # Verify extra parameters are NOT passed to RayManager
                    forbidden_params = {"extra_param", "tool_registry"}
                    actual_params = set(call_args.kwargs.keys())
                    passed_forbidden_params = actual_params & forbidden_params

                    assert (
                        not passed_forbidden_params
                    ), f"Forbidden parameters passed to RayManager: {passed_forbidden_params}"

    @pytest.mark.asyncio
    async def test_parameter_flow_error_handling(self):
        """Test parameter flow error handling through the stack."""
        # Mock the RayManager method to raise an exception
        with patch.object(self.ray_manager, "get_logs") as mock_get_logs:
            mock_get_logs.side_effect = Exception("Test error")

            # Mock Ray initialization
            with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
                with patch("ray_mcp.ray_manager.ray") as mock_ray:
                    mock_ray.is_initialized.return_value = True
                    self.ray_manager._is_initialized = True

                    # Call the tool through the registry
                    result = await self.tool_registry.execute_tool(
                        "get_logs", {"job_id": "test_job_123"}
                    )

                    # Verify error is properly handled and returned
                    assert result["status"] == "error"
                    assert "Test error" in result["message"]

    @pytest.mark.asyncio
    async def test_all_tool_parameter_flows(self):
        """Test parameter flow for all tools to ensure consistency."""
        # Test all tools that accept parameters
        tool_tests = [
            ("get_logs", {"job_id": "test_job", "num_lines": 100}),
            ("start_ray", {"num_cpus": 2, "num_gpus": 0}),
            ("submit_job", {"entrypoint": "python script.py"}),
            ("job_status", {"job_id": "test_job"}),
            ("cancel_job", {"job_id": "test_job"}),
            ("monitor_job", {"job_id": "test_job"}),
            ("debug_job", {"job_id": "test_job"}),
            ("kill_actor", {"actor_id": "test_actor", "no_restart": True}),
        ]

        for tool_name, test_params in tool_tests:
            # Mock the corresponding RayManager method
            ray_manager_method = getattr(
                self.ray_manager, tool_name.replace("_", ""), None
            )
            if ray_manager_method:
                with patch.object(
                    self.ray_manager, tool_name.replace("_", "")
                ) as mock_method:
                    mock_method.return_value = {"status": "success"}

                    # Mock Ray initialization
                    with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
                        with patch("ray_mcp.ray_manager.ray") as mock_ray:
                            mock_ray.is_initialized.return_value = True
                            self.ray_manager._is_initialized = True

                            # Call the tool through the registry
                            result = await self.tool_registry.execute_tool(
                                tool_name, test_params
                            )

                            # Verify the method was called
                            mock_method.assert_called_once()

                            # Verify only expected parameters are passed
                            call_args = mock_method.call_args
                            actual_params = set(call_args.kwargs.keys())
                            test_param_keys = set(test_params.keys())
                            unexpected_params = actual_params - test_param_keys

                            assert (
                                not unexpected_params
                            ), f"Tool {tool_name}: Unexpected parameters passed: {unexpected_params}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
