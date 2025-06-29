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
                "status": "connected",
                "message": "Successfully connected to Ray cluster at 127.0.0.1:10001",
                "cluster_address": "127.0.0.1:10001",
                "dashboard_url": "http://127.0.0.1:8265",
                "node_id": "node_123",
                "job_client_status": "ready",
            }
        )

        result = await self.registry.execute_tool("init_ray", {"num_cpus": 4})
        assert result["status"] == "connected"
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
                        "status": "connected",
                        "message": "Successfully connected to Ray cluster at 127.0.0.1:10001",
                        "cluster_address": "127.0.0.1:10001",
                        "dashboard_url": "http://127.0.0.1:8265",
                        "node_id": "node_123",
                        "job_client_status": "ready",
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

                    assert result["status"] == "connected"
                    assert (
                        "Successfully connected to Ray cluster at 127.0.0.1:10001"
                        in result["message"]
                    )
                    assert result["cluster_address"] == "127.0.0.1:10001"
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


if __name__ == "__main__":
    pytest.main([__file__])
