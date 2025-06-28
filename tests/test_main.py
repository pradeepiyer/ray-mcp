#!/usr/bin/env python3
"""Unit tests for main.py functions."""

import asyncio
from io import StringIO
import json
import os
import sys
from typing import Any, Dict, List, Optional, cast
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from mcp.types import TextContent
import pytest

from ray_mcp.main import list_tools, run_server
from ray_mcp.ray_manager import RayManager
from ray_mcp.tool_registry import ToolRegistry


@pytest.mark.fast
class TestMain:
    """Test cases for main.py functions."""

    def test_run_server_exists(self):
        """Test that run_server function exists and is callable."""
        assert callable(run_server)
        assert run_server.__name__ == "run_server"

    def test_main_function_import(self):
        """Test that main function can be imported."""
        from ray_mcp.main import main

        assert callable(main)
        assert main.__name__ == "main"

    def test_asyncio_run_mock(self):
        """Test that asyncio.run is called in run_server."""
        with patch("asyncio.run") as mock_run:
            with patch("ray_mcp.main.main") as mock_main:
                mock_main.return_value = None
                run_server()
                mock_run.assert_called_once()

    def test_run_server_entrypoint(self, monkeypatch):
        """Test run_server as entry point."""
        mock_asyncio_run = Mock()
        mock_main = AsyncMock()

        def fake_main():
            return mock_main

        def fake_run(coro):
            return coro

        monkeypatch.setattr("ray_mcp.main.asyncio.run", fake_run)
        monkeypatch.setattr("ray_mcp.main.main", fake_main)

        run_server()
        # Should not raise any exceptions

    @pytest.mark.asyncio
    async def test_main_ray_unavailable_branch(self, monkeypatch):
        """Test main function when Ray is not available."""
        with patch("ray_mcp.main.RAY_AVAILABLE", False):
            # Should not exit when Ray is not available, just log warning
            with patch("ray_mcp.main.stdio_server") as mock_stdio:
                mock_stdio.return_value.__aenter__.return_value = (Mock(), Mock())
                with patch("ray_mcp.main.server.run") as mock_run:
                    mock_run.return_value = None
                    # Should not raise SystemExit
                    from ray_mcp.main import main

                    await main()


class TestToolRegistry:
    """Test cases for ToolRegistry."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_ray_manager = Mock()
        self.registry = ToolRegistry(self.mock_ray_manager)

    def test_tool_registry_initialization(self):
        """Test ToolRegistry initialization."""
        assert self.registry.ray_manager == self.mock_ray_manager
        assert len(self.registry._tools) > 0

    def test_get_tool_list(self):
        """Test get_tool_list returns proper Tool objects."""
        tools = self.registry.get_tool_list()
        assert len(tools) > 0

        # Check that all tools have required attributes
        for tool in tools:
            assert hasattr(tool, "name")
            assert hasattr(tool, "description")
            assert hasattr(tool, "inputSchema")

    def test_get_tool_handler(self):
        """Test get_tool_handler returns correct handlers."""
        handler = self.registry.get_tool_handler("init_ray")
        assert handler is not None
        assert callable(handler)

        handler = self.registry.get_tool_handler("unknown_tool")
        assert handler is None

    def test_list_tool_names(self):
        """Test list_tool_names returns all tool names."""
        names = self.registry.list_tool_names()
        assert len(names) > 0
        assert "init_ray" in names
        assert "stop_ray" in names

    @pytest.mark.asyncio
    async def test_execute_tool_unknown_tool(self):
        """Test execute_tool with unknown tool."""
        result = await self.registry.execute_tool("unknown_tool", {})
        assert result["status"] == "error"
        assert "Unknown tool" in result["message"]

    @pytest.mark.asyncio
    async def test_execute_tool_success(self):
        """Test execute_tool with valid tool."""
        self.mock_ray_manager.init_cluster = AsyncMock(
            return_value={
                "status": "started",
                "cluster_address": "ray://localhost:10001",
            }
        )

        result = await self.registry.execute_tool("init_ray", {"num_cpus": 4})
        assert result["status"] == "started"
        self.mock_ray_manager.init_cluster.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_tool_error(self):
        """Test execute_tool with tool that raises exception."""
        self.mock_ray_manager.init_cluster = AsyncMock(
            side_effect=Exception("Test error")
        )

        result = await self.registry.execute_tool("init_ray", {})
        assert result["status"] == "error"
        assert "Test error" in result["message"]

    @pytest.mark.asyncio
    async def test_execute_tool_enhanced_output(self):
        """Test tool execution with enhanced output format."""
        registry = ToolRegistry(RayManager())

        # Mock Ray availability and initialization
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True

                # Mock the init_cluster method to return success
                with patch.object(registry.ray_manager, "init_cluster") as mock_init:
                    mock_init.return_value = {
                        "status": "started",
                        "message": "Ray cluster started successfully",
                        "address": "ray://127.0.0.1:10001",
                        "dashboard_url": "http://127.0.0.1:8265",
                        "node_id": "node_123",
                        "session_name": "test_session",
                    }

                    result = await registry.execute_tool(
                        "init_ray",
                        {
                            "num_cpus": 4,
                            "num_gpus": 0,
                            "object_store_memory": 1000000000,
                            "dashboard_port": 8265,
                            "dashboard_host": "127.0.0.1",
                            "include_dashboard": True,
                            "log_to_driver": True,
                            "worker_nodes": [],
                        },
                    )

                    assert result["status"] == "started"
                    assert "Ray cluster started successfully" in result["message"]
                    assert result["address"] == "ray://127.0.0.1:10001"
                    assert result["dashboard_url"] == "http://127.0.0.1:8265"

    def test_wrap_with_system_prompt(self):
        """Test _wrap_with_system_prompt function."""
        result = {"status": "success", "message": "test"}
        prompt = self.registry._wrap_with_system_prompt("test_tool", result)

        assert "test_tool" in prompt
        assert "Tool Result Summary:" in prompt
        assert "Context:" in prompt
        assert "Suggested Next Steps:" in prompt
        assert "Available Commands:" in prompt
        assert "Original Response:" in prompt


class TestToolFunctions:
    """Test cases for individual tool functions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_ray_manager = Mock()
        self.registry = ToolRegistry(self.mock_ray_manager)
        self.mock_server = Mock()

    @pytest.mark.asyncio
    async def test_init_ray_function(self):
        """Test init_ray tool function."""

        # Mock the server.call_tool decorator to return the function directly
        def mock_call_tool_decorator():
            def decorator(func):
                return func

            return decorator

        # Define the tool function using the mock decorator
        @mock_call_tool_decorator()
        async def init_ray(
            num_cpus: int = 1,
            num_gpus: Optional[int] = None,
            address: Optional[str] = None,
        ):
            return await self.registry.execute_tool(
                "init_ray",
                {"num_cpus": num_cpus, "num_gpus": num_gpus, "address": address},
            )

        self.registry.execute_tool = AsyncMock(
            return_value={
                "status": "success",
                "cluster_address": "ray://localhost:10001",
            }
        )

        result = await init_ray(num_cpus=4, num_gpus=2)
        assert result["status"] == "success"
        self.registry.execute_tool.assert_called_once_with(
            "init_ray", {"num_cpus": 4, "num_gpus": 2, "address": None}
        )

    @pytest.mark.asyncio
    async def test_init_ray_function_with_address(self):
        """Test init_ray tool function with address parameter."""

        def mock_call_tool_decorator():
            def decorator(func):
                return func

            return decorator

        @mock_call_tool_decorator()
        async def init_ray(address: str):
            return await self.registry.execute_tool("init_ray", {"address": address})

        self.registry.execute_tool = AsyncMock(
            return_value={"status": "success", "connected": True}
        )

        result = await init_ray(address="ray://localhost:10001")
        assert result["status"] == "success"
        self.registry.execute_tool.assert_called_once_with(
            "init_ray", {"address": "ray://localhost:10001"}
        )

    @pytest.mark.asyncio
    async def test_stop_ray_function(self):
        """Test stop_ray tool function."""

        def mock_call_tool_decorator():
            def decorator(func):
                return func

            return decorator

        @mock_call_tool_decorator()
        async def stop_ray():
            return await self.registry.execute_tool("stop_ray", {})

        self.registry.execute_tool = AsyncMock(
            return_value={"status": "success", "stopped": True}
        )

        result = await stop_ray()
        assert result["status"] == "success"
        self.registry.execute_tool.assert_called_once_with("stop_ray", {})

    @pytest.mark.asyncio
    async def test_format_response_enhanced(self):
        """Test _format_response with enhanced output."""
        from ray_mcp.tool_functions import _format_response

        result = {
            "status": "success",
            "enhanced_output": "Enhanced response text",
            "raw_result": {"status": "success"},
        }

        response = _format_response(result)

        assert len(response) == 1
        assert isinstance(response[0], TextContent)
        assert response[0].text == "Enhanced response text"

    @pytest.mark.asyncio
    async def test_format_response_standard(self):
        """Test _format_response with standard output."""
        from ray_mcp.tool_functions import _format_response

        result = {"status": "success", "message": "test"}

        response = _format_response(result)

        assert len(response) == 1
        assert isinstance(response[0], TextContent)
        assert "test" in response[0].text


if __name__ == "__main__":
    pytest.main([__file__])
