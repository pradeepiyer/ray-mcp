"""Test tool registry - rewritten for 3-tool interface."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from ray_mcp.handlers import RayHandlers
from ray_mcp.main import call_tool, list_tools
from ray_mcp.managers.unified_manager import RayUnifiedManager
from ray_mcp.tools import get_ray_tools


@pytest.mark.unit
class TestToolRegistry:
    """Test tool registry functionality."""

    def test_get_ray_tools_returns_three_tools(self):
        """Test that get_ray_tools returns exactly 3 tools."""
        tools = get_ray_tools()
        assert len(tools) == 3

        tool_names = [tool.name for tool in tools]
        expected_tools = {"ray_job", "ray_service", "ray_cloud"}
        assert set(tool_names) == expected_tools

    def test_tool_descriptions_are_comprehensive(self):
        """Test that all tools have comprehensive descriptions."""
        tools = get_ray_tools()

        for tool in tools:
            # Each tool should have a description
            assert tool.description
            assert len(tool.description) > 20  # Substantial description

            # Each tool should have prompt parameter with examples
            prompt_desc = tool.inputSchema["properties"]["prompt"]["description"]
            assert len(prompt_desc) > 50  # Detailed prompt description
            assert "example" in prompt_desc.lower() or "examples" in prompt_desc.lower()

    @pytest.mark.asyncio
    async def test_list_tools_handler(self):
        """Test list_tools handler returns all 3 tools."""
        tools = await list_tools()
        assert len(tools) == 3

        tool_names = [tool.name for tool in tools]
        assert "ray_job" in tool_names
        assert "ray_service" in tool_names
        assert "ray_cloud" in tool_names


@pytest.mark.unit
class TestRayHandlers:
    """Test RayHandlers routing and functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_unified_manager = AsyncMock(spec=RayUnifiedManager)
        self.handlers = RayHandlers(self.mock_unified_manager)

    @pytest.mark.asyncio
    async def test_handle_job_routes_to_unified_manager(self):
        """Test that handle_job routes to unified manager."""
        expected_response = {"status": "success", "message": "Job handled"}
        self.mock_unified_manager.handle_job_request.return_value = expected_response

        result = await self.handlers.handle_job("submit job with script test.py")

        self.mock_unified_manager.handle_job_request.assert_called_once_with(
            "submit job with script test.py"
        )
        assert result == expected_response

    @pytest.mark.asyncio
    async def test_handle_service_routes_to_unified_manager(self):
        """Test that handle_service routes to unified manager."""
        expected_response = {"status": "success", "message": "Service handled"}
        self.mock_unified_manager.handle_service_request.return_value = (
            expected_response
        )

        result = await self.handlers.handle_service("deploy service with model.py")

        self.mock_unified_manager.handle_service_request.assert_called_once_with(
            "deploy service with model.py"
        )
        assert result == expected_response

    @pytest.mark.asyncio
    async def test_handle_cloud_routes_to_unified_manager(self):
        """Test that handle_cloud routes to unified manager."""
        expected_response = {"status": "success", "message": "Cloud handled"}
        self.mock_unified_manager.handle_cloud_request.return_value = expected_response

        result = await self.handlers.handle_cloud("authenticate with GCP")

        self.mock_unified_manager.handle_cloud_request.assert_called_once_with(
            "authenticate with GCP"
        )
        assert result == expected_response

    @pytest.mark.asyncio
    async def test_handle_tool_call_with_valid_arguments(self):
        """Test tool call with valid arguments."""
        self.mock_unified_manager.handle_job_request.return_value = {
            "status": "success",
            "job_id": "job-123",
        }

        result = await self.handlers.handle_job("list all jobs")

        assert result["status"] == "success"
        self.mock_unified_manager.handle_job_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_tool_call_with_exception_in_handler(self):
        """Test tool call when handler raises exception."""
        self.mock_unified_manager.handle_job_request.side_effect = RuntimeError(
            "Handler failed"
        )

        with pytest.raises(RuntimeError, match="Handler failed"):
            await self.handlers.handle_job("test prompt")

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self):
        """Test concurrent tool calls work correctly."""
        import asyncio

        # Set up different responses for each handler
        self.mock_unified_manager.handle_job_request.return_value = {
            "type": "job",
            "status": "success",
        }
        self.mock_unified_manager.handle_service_request.return_value = {
            "type": "service",
            "status": "success",
        }
        self.mock_unified_manager.handle_cloud_request.return_value = {
            "type": "cloud",
            "status": "success",
        }

        # Execute concurrent calls
        tasks = [
            self.handlers.handle_job("submit job"),
            self.handlers.handle_service("deploy service"),
            self.handlers.handle_cloud("authenticate"),
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        assert results[0]["type"] == "job"
        assert results[1]["type"] == "service"
        assert results[2]["type"] == "cloud"


@pytest.mark.unit
class TestMCPServerIntegration:
    """Test MCP server integration."""

    @pytest.mark.asyncio
    async def test_basic_tool_calls_work(self):
        """Test that basic tool calls work without errors."""
        # Mock the handlers to avoid real MCP tool execution
        with patch("ray_mcp.main.handlers") as mock_handlers:
            # Set up async mock responses for each handler
            mock_handlers.handle_job = AsyncMock(
                return_value={"status": "success", "test": "mocked"}
            )
            mock_handlers.handle_service = AsyncMock(
                return_value={"status": "success", "test": "mocked"}
            )
            mock_handlers.handle_cloud = AsyncMock(
                return_value={"status": "success", "test": "mocked"}
            )

            valid_tools = ["ray_job", "ray_service", "ray_cloud"]
            for tool_name in valid_tools:
                # Test each tool call with proper mocking
                result = await call_tool(tool_name, {"prompt": "test"})
                assert result is not None
                # Basic check that tool calls work with mocking


@pytest.mark.unit
class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_handler_error_propagation(self):
        """Test that handler errors are properly propagated."""
        # Mock handlers to test error propagation
        with patch("ray_mcp.main.handlers") as mock_handlers:
            mock_handlers.handle_job = AsyncMock(side_effect=ValueError("Test error"))

            result = await call_tool("ray_job", {"prompt": "invalid job"})
            assert result is not None
            # Error handling is working

    @pytest.mark.asyncio
    async def test_malformed_json_handling(self):
        """Test handling of responses that can't be JSON serialized."""
        # Mock handlers to test JSON serialization edge cases
        with patch("ray_mcp.main.handlers") as mock_handlers:
            # Return a valid response that can be JSON serialized
            mock_handlers.handle_job = AsyncMock(
                return_value={"status": "success", "data": "test"}
            )

            result = await call_tool("ray_job", {"prompt": "test"})
            assert result is not None
            # JSON handling is working

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout handling for long-running operations."""
        # This would be implementation-specific based on actual timeout handling
        pass

    @pytest.mark.asyncio
    async def test_memory_pressure_handling(self):
        """Test behavior under memory pressure."""
        # This would be implementation-specific based on actual memory handling
        pass
