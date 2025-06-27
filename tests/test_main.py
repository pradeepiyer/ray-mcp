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
from ray_mcp.tool_registry import ToolRegistry


@pytest.mark.fast
class TestMain:
    """Test cases for main.py functions."""

    @pytest.mark.asyncio
    async def test_list_tools_complete(self):
        """Test that list_tools returns all expected tools."""
        tools = await list_tools()

        tool_names = [tool.name for tool in tools]

        # Check that key tools are present
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
            "get_logs",
        ]

        for expected_tool in expected_tools:
            assert (
                expected_tool in tool_names
            ), f"Tool {expected_tool} not found in tools list"

        # Verify tool schemas
        start_ray_tool = next(tool for tool in tools if tool.name == "start_ray")
        assert "num_cpus" in start_ray_tool.inputSchema["properties"]
        assert start_ray_tool.inputSchema["properties"]["num_cpus"]["default"] == 1

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
        handler = self.registry.get_tool_handler("start_ray")
        assert handler is not None
        assert callable(handler)

        handler = self.registry.get_tool_handler("unknown_tool")
        assert handler is None

    def test_list_tool_names(self):
        """Test list_tool_names returns all tool names."""
        names = self.registry.list_tool_names()
        assert len(names) > 0
        assert "start_ray" in names
        assert "connect_ray" in names
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
        self.mock_ray_manager.start_cluster = AsyncMock(
            return_value={"status": "success"}
        )

        result = await self.registry.execute_tool("start_ray", {"num_cpus": 4})
        assert result["status"] == "success"
        self.mock_ray_manager.start_cluster.assert_called_once_with(num_cpus=4)

    @pytest.mark.asyncio
    async def test_execute_tool_exception_handling(self):
        """Test execute_tool exception handling."""
        self.mock_ray_manager.start_cluster = AsyncMock(
            side_effect=Exception("Test error")
        )

        result = await self.registry.execute_tool("start_ray", {})
        assert result["status"] == "error"
        assert "Test error" in result["message"]

    @pytest.mark.asyncio
    async def test_execute_tool_enhanced_output(self):
        """Test execute_tool with enhanced output enabled."""
        with patch.dict(os.environ, {"RAY_MCP_ENHANCED_OUTPUT": "true"}):
            self.mock_ray_manager.start_cluster = AsyncMock(
                return_value={"status": "success"}
            )

            result = await self.registry.execute_tool("start_ray", {})
            assert result["status"] == "success"
            assert "enhanced_output" in result
            assert "raw_result" in result

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
    async def test_start_ray_function(self):
        """Test start_ray tool function."""

        # Mock the server.call_tool decorator to return the function directly
        def mock_call_tool_decorator():
            def decorator(func):
                return func

            return decorator

        # Define the tool function using the mock decorator
        @mock_call_tool_decorator()
        async def start_ray(num_cpus: int = 1, num_gpus: Optional[int] = None):
            return await self.registry.execute_tool(
                "start_ray", {"num_cpus": num_cpus, "num_gpus": num_gpus}
            )

        self.registry.execute_tool = AsyncMock(
            return_value={
                "status": "success",
                "cluster_address": "ray://localhost:10001",
            }
        )

        result = await start_ray(num_cpus=4, num_gpus=2)
        assert result["status"] == "success"
        self.registry.execute_tool.assert_called_once_with(
            "start_ray", {"num_cpus": 4, "num_gpus": 2}
        )

    @pytest.mark.asyncio
    async def test_connect_ray_function(self):
        """Test connect_ray tool function."""

        def mock_call_tool_decorator():
            def decorator(func):
                return func

            return decorator

        @mock_call_tool_decorator()
        async def connect_ray(address: str):
            return await self.registry.execute_tool("connect_ray", {"address": address})

        self.registry.execute_tool = AsyncMock(
            return_value={"status": "success", "connected": True}
        )

        result = await connect_ray(address="ray://localhost:10001")
        assert result["status"] == "success"
        self.registry.execute_tool.assert_called_once_with(
            "connect_ray", {"address": "ray://localhost:10001"}
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
