#!/usr/bin/env python3
"""MCP integration tests for Ray MCP server.

Tests the MCP integration layer including tool registry, server startup,
schema validation, and tool dispatch mechanism. These tests focus on
the MCP-specific functionality that bridges between the LLM and the
Ray components.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from ray_mcp.core.unified_manager import RayUnifiedManager
from ray_mcp.tool_registry import ToolRegistry


@pytest.mark.fast
@pytest.mark.integration
class TestMCPServer:
    """Test MCP server startup and core functionality."""

    @pytest.mark.asyncio
    async def test_mcp_server_startup_ray_unavailable(self):
        """Test MCP server can start even when Ray is not available."""
        with patch("ray_mcp.main.RAY_AVAILABLE", False):
            # Should not exit when Ray is not available, just log warning
            with patch("ray_mcp.main.stdio_server") as mock_stdio:
                mock_stdio.return_value.__aenter__.return_value = (Mock(), Mock())
                with patch("ray_mcp.main.server.run") as mock_run:
                    mock_run.return_value = None
                    # Should not raise SystemExit
                    from ray_mcp.main import main

                    await main()

    @pytest.mark.asyncio
    async def test_tool_registry_schema_validation(self):
        """Test that all tools are available with valid MCP schemas."""
        registry = ToolRegistry(RayUnifiedManager())
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

        # Check that all tools have valid MCP schemas
        for tool in tools:
            assert hasattr(tool, "inputSchema")
            assert isinstance(tool.inputSchema, dict)
            assert "type" in tool.inputSchema
            assert tool.inputSchema["type"] == "object"
            assert hasattr(tool, "name")
            assert hasattr(tool, "description")


@pytest.mark.fast
class TestToolRegistry:
    """Test tool registry initialization and dispatch mechanism."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_ray_manager = Mock()
        self.registry = ToolRegistry(self.mock_ray_manager)

    def test_tool_registry_initialization(self):
        """Test ToolRegistry initialization and structure."""
        assert self.registry.ray_manager == self.mock_ray_manager
        assert len(self.registry._tools) > 0

        # Test get_tool_list returns proper Tool objects
        tools = self.registry.get_tool_list()
        assert len(tools) > 0

        # Test tool handler functionality
        handler = self.registry.get_tool_handler("init_ray")
        assert handler is not None
        assert callable(handler)

        handler = self.registry.get_tool_handler("unknown_tool")
        assert handler is None

        # Test list_tool_names
        names = self.registry.list_tool_names()
        assert len(names) > 0
        assert "init_ray" in names
        assert "stop_ray" in names

    @pytest.mark.asyncio
    async def test_tool_dispatch_mechanism(self):
        """Test tool dispatch and error handling."""
        # Test unknown tool
        result = await self.registry.execute_tool("unknown_tool", {})
        assert result["status"] == "error"
        assert "Unknown tool" in result["message"]

        # Test successful tool execution
        self.mock_ray_manager.init_cluster = AsyncMock(
            return_value={
                "status": "success",
                "result_type": "connected",
                "message": "Successfully connected to Ray cluster",
                "cluster_address": "127.0.0.1:10001",
            }
        )

        result = await self.registry.execute_tool("init_ray", {"num_cpus": 4})
        assert result["status"] == "success"
        assert result.get("result_type") == "connected"
        self.mock_ray_manager.init_cluster.assert_called_once()

        # Test tool execution with exception
        self.mock_ray_manager.init_cluster = AsyncMock(
            side_effect=Exception("Test error")
        )

        result = await self.registry.execute_tool("init_ray", {})
        assert result["status"] == "error"
        assert "Test error" in result["message"]

    def test_system_prompt_formatting(self):
        """Test LLM system prompt generation."""
        result = {"status": "success", "message": "test"}
        prompt = self.registry._wrap_with_system_prompt("test_tool", result)

        assert "test_tool" in prompt
        assert "Tool Result Summary:" in prompt
        assert "Context:" in prompt
        assert "Suggested Next Steps:" in prompt
        assert "Available Commands:" in prompt
        assert "Original Response:" in prompt


@pytest.mark.integration
class TestMCPWorkflow:
    """Test complete MCP workflow integration."""

    @pytest.fixture(autouse=True)
    def patch_ray_manager(self):
        """Patch Ray availability for integration tests."""
        with patch("ray_mcp.main.RAY_AVAILABLE", True):
            yield

    @pytest.mark.asyncio
    async def test_mcp_error_handling(self):
        """Test MCP-level error handling and response formatting."""
        registry = ToolRegistry(RayUnifiedManager())

        # Test Ray unavailable scenario - patch at the cluster manager level
        with patch("ray_mcp.core.cluster_manager.RAY_AVAILABLE", False):
            result = await registry.execute_tool("init_ray", {"num_cpus": 4})
            assert result["status"] == "error"
            assert "Ray is not available" in result["message"]

        # Test unknown tool handling
        result = await registry.execute_tool("nonexistent_tool", {})
        assert result["status"] == "error"
        assert "Unknown tool" in result["message"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
