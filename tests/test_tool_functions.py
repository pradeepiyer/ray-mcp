#!/usr/bin/env python3
"""Tests for the tool functions layer to catch parameter passing issues."""

import asyncio
import inspect
import json
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ray_mcp.ray_manager import RayManager
from ray_mcp.tool_registry import ToolRegistry


@pytest.mark.fast
class TestToolFunctions:
    """Test the tool functions layer specifically."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a real RayManager but mock its methods
        self.ray_manager = RayManager()

        # Create a real ToolRegistry with the mocked RayManager
        self.tool_registry = ToolRegistry(self.ray_manager)

    @pytest.mark.asyncio
    async def test_get_logs_tool_function_parameter_isolation(self):
        """Test that get_logs function only passes expected parameters."""
        called_params = {}

        async def fake_get_logs(**kwargs):
            called_params.update(kwargs)
            return {
                "status": "success",
                "logs": "Sample log output...",
                "job_id": "job_123",
            }

        mock = AsyncMock(side_effect=fake_get_logs)
        mock.__signature__ = inspect.signature(self.ray_manager.get_logs)
        with patch.object(self.ray_manager, "get_logs", mock):
            # Mock Ray initialization
            with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
                with patch("ray_mcp.ray_manager.ray") as mock_ray:
                    mock_ray.is_initialized.return_value = True
                    self.ray_manager._is_initialized = True

                    # Call the tool through the registry (simulating what the tool function would do)
                    result = await self.tool_registry.execute_tool(
                        "get_logs", {"job_id": "test_job_123", "num_lines": 50}
                    )

                    # Verify the RayManager method was called with correct parameters
                    mock.assert_called_once()

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
    async def test_start_ray_tool_function_parameter_isolation(self):
        """Test that start_ray function only passes expected parameters."""
        called_params = {}

        async def fake_start_cluster(**kwargs):
            called_params.update(kwargs)
            return {
                "status": "started",
                "address": "ray://127.0.0.1:10001",
            }

        mock = AsyncMock(side_effect=fake_start_cluster)
        mock.__signature__ = inspect.signature(self.ray_manager.start_cluster)
        with patch.object(self.ray_manager, "start_cluster", mock):
            result = await self.tool_registry.execute_tool(
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
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_job_tool_function_parameter_isolation(self):
        """Test that submit_job function only passes expected parameters."""
        called_params = {}

        async def fake_submit_job(**kwargs):
            called_params.update(kwargs)
            return {
                "status": "submitted",
                "job_id": "job_123",
            }

        mock = AsyncMock(side_effect=fake_submit_job)
        mock.__signature__ = inspect.signature(self.ray_manager.submit_job)
        with patch.object(self.ray_manager, "submit_job", mock):
            with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
                with patch("ray_mcp.ray_manager.ray") as mock_ray:
                    mock_ray.is_initialized.return_value = True
                    self.ray_manager._is_initialized = True
                    result = await self.tool_registry.execute_tool(
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
                    mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_tool_function_error_handling(self):
        """Test that tool functions handle errors gracefully."""

        async def fake_get_logs(**kwargs):
            raise Exception("Test error")

        mock = AsyncMock(side_effect=fake_get_logs)
        mock.__signature__ = inspect.signature(self.ray_manager.get_logs)
        with patch.object(self.ray_manager, "get_logs", mock):
            with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
                with patch("ray_mcp.ray_manager.ray") as mock_ray:
                    mock_ray.is_initialized.return_value = True
                    self.ray_manager._is_initialized = True
                    result = await self.tool_registry.execute_tool(
                        "get_logs", {"job_id": "test_job"}
                    )
                    assert result["status"] == "error"
                    assert "Test error" in result["message"]
                    mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_tool_function_response_formatting(self):
        """Test that tool functions return properly formatted responses."""

        async def fake_get_logs(**kwargs):
            return {
                "status": "success",
                "data": {"key": "value"},
                "message": "Operation completed",
            }

        mock = AsyncMock(side_effect=fake_get_logs)
        mock.__signature__ = inspect.signature(self.ray_manager.get_logs)
        with patch.object(self.ray_manager, "get_logs", mock):
            with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
                with patch("ray_mcp.ray_manager.ray") as mock_ray:
                    mock_ray.is_initialized.return_value = True
                    self.ray_manager._is_initialized = True
                    result = await self.tool_registry.execute_tool(
                        "get_logs", {"job_id": "test_job"}
                    )
                    assert isinstance(result, dict)
                    assert result["status"] == "success"
                    assert "data" in result
                    assert "message" in result
                    mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_parameter_flow_with_extra_parameters(self):
        """Test that extra parameters are not passed through the stack."""
        called_params = {}

        async def fake_get_logs(**kwargs):
            called_params.update(kwargs)
            return {
                "status": "success",
                "logs": "Sample log output...",
            }

        mock = AsyncMock(side_effect=fake_get_logs)
        mock.__signature__ = inspect.signature(self.ray_manager.get_logs)
        with patch.object(self.ray_manager, "get_logs", mock):
            with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
                with patch("ray_mcp.ray_manager.ray") as mock_ray:
                    mock_ray.is_initialized.return_value = True
                    self.ray_manager._is_initialized = True
                    result = await self.tool_registry.execute_tool(
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
                    mock.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
