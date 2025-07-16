#!/usr/bin/env python3
"""Unit tests for tool registry and MCP server functionality.

This module tests the MCP server tool registration, routing, and handler
functionality with full mocking for fast execution.

Test Focus:
- Tool registration and discovery
- MCP server tool routing
- Handler validation and execution
- Error handling in tool calls
"""

import json
from typing import Any, Dict, List, cast
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from mcp.types import TextContent, Tool
import pytest

from ray_mcp.handlers import RayHandlers

# Import the components we're testing
from ray_mcp.main import call_tool, list_tools, server
from ray_mcp.managers.unified_manager import RayUnifiedManager
from ray_mcp.tools import get_ray_tools


def parse_tool_response(result: Any) -> Dict[str, Any]:
    """Helper function to parse tool response with proper type checking."""
    # Type checker satisfaction - cast to expected type
    result_list = cast(List[TextContent], result)
    assert len(result_list) == 1
    text_content = cast(TextContent, result_list[0])
    assert isinstance(text_content, TextContent)
    return json.loads(text_content.text)


@pytest.mark.unit
class TestToolRegistry:
    """Test tool registration and discovery functionality."""

    def test_get_ray_tools_returns_three_tools(self):
        """Test that get_ray_tools returns exactly 3 tools."""
        tools = get_ray_tools()

        assert len(tools) == 3
        assert all(isinstance(tool, Tool) for tool in tools)

        # Check tool names
        tool_names = [tool.name for tool in tools]
        assert "ray_cluster" in tool_names
        assert "ray_job" in tool_names
        assert "cloud" in tool_names

    def test_tool_schema_validation(self):
        """Test that all tools have proper schema validation."""
        tools = get_ray_tools()

        for tool in tools:
            # Check required fields
            assert tool.name is not None
            assert tool.description is not None
            assert tool.inputSchema is not None

            # Check input schema has required prompt field
            properties = tool.inputSchema.get("properties", {})
            assert "prompt" in properties

            # Check prompt field is required
            required_fields = tool.inputSchema.get("required", [])
            assert "prompt" in required_fields

    def test_tool_descriptions_are_comprehensive(self):
        """Test that tool descriptions contain expected content."""
        tools = get_ray_tools()
        tool_by_name = {tool.name: tool for tool in tools}

        # Check ray_cluster tool description
        cluster_desc = tool_by_name["ray_cluster"].description
        assert "cluster" in cluster_desc.lower()
        assert "create" in cluster_desc.lower()
        assert "connect" in cluster_desc.lower()

        # Check ray_job tool description
        job_desc = tool_by_name["ray_job"].description
        assert "job" in job_desc.lower()
        assert "submit" in job_desc.lower()
        assert "logs" in job_desc.lower()

        # Check cloud tool description
        cloud_desc = tool_by_name["cloud"].description
        assert "cloud" in cloud_desc.lower()
        assert "authenticate" in cloud_desc.lower()

    @pytest.mark.asyncio
    async def test_list_tools_handler(self):
        """Test the MCP server list_tools handler."""
        tools = await list_tools()

        assert len(tools) == 3
        assert all(isinstance(tool, Tool) for tool in tools)

        # Verify the tools are properly formatted
        tool_names = [tool.name for tool in tools]
        assert "ray_cluster" in tool_names
        assert "ray_job" in tool_names
        assert "cloud" in tool_names


@pytest.mark.unit
class TestRayHandlers:
    """Test RayHandlers routing and execution."""

    def setup_method(self):
        """Set up test fixtures."""
        self.unified_manager_mock = AsyncMock()
        self.handlers = RayHandlers(self.unified_manager_mock)

    @pytest.mark.asyncio
    async def test_handle_cluster_routes_to_unified_manager(self):
        """Test that cluster requests are routed to unified manager."""
        prompt = "create a local cluster with 4 CPUs"
        expected_response = {"status": "success", "message": "Cluster created"}

        self.unified_manager_mock.handle_cluster_request.return_value = (
            expected_response
        )

        result = await self.handlers.handle_cluster(prompt)

        self.unified_manager_mock.handle_cluster_request.assert_called_once_with(prompt)
        assert result == expected_response

    @pytest.mark.asyncio
    async def test_handle_job_routes_to_unified_manager(self):
        """Test that job requests are routed to unified manager."""
        prompt = "submit job with script train.py"
        expected_response = {"status": "success", "job_id": "raysubmit_123"}

        self.unified_manager_mock.handle_job_request.return_value = expected_response

        result = await self.handlers.handle_job(prompt)

        self.unified_manager_mock.handle_job_request.assert_called_once_with(prompt)
        assert result == expected_response

    @pytest.mark.asyncio
    async def test_handle_cloud_routes_to_unified_manager(self):
        """Test that cloud requests are routed to unified manager."""
        prompt = "authenticate with GCP project ml-experiments"
        expected_response = {"status": "success", "message": "Authenticated"}

        self.unified_manager_mock.handle_cloud_request.return_value = expected_response

        result = await self.handlers.handle_cloud(prompt)

        self.unified_manager_mock.handle_cloud_request.assert_called_once_with(prompt)
        assert result == expected_response

    @pytest.mark.asyncio
    async def test_handle_tool_call_with_valid_arguments(self):
        """Test call_tool with valid arguments."""
        with patch("ray_mcp.main.handlers.handle_cluster") as mock_handle_cluster:
            expected_response = {"status": "success", "message": "Cluster created"}
            mock_handle_cluster.return_value = expected_response

            result = await call_tool("ray_cluster", {"prompt": "create cluster"})

            response_data = parse_tool_response(result)
            assert response_data == expected_response

    @pytest.mark.asyncio
    async def test_handle_tool_call_with_none_arguments(self):
        """Test call_tool with None arguments."""
        result = await call_tool("ray_cluster", None)

        response_data = parse_tool_response(result)
        assert response_data["status"] == "error"
        assert "prompt required" in response_data["message"]

    @pytest.mark.asyncio
    async def test_handle_tool_call_with_empty_arguments(self):
        """Test call_tool with empty arguments dict."""
        result = await call_tool("ray_cluster", {})

        response_data = parse_tool_response(result)
        assert response_data["status"] == "error"
        assert "prompt required" in response_data["message"]

    @pytest.mark.asyncio
    async def test_handle_tool_call_with_missing_prompt(self):
        """Test call_tool with arguments missing prompt."""
        result = await call_tool("ray_cluster", {"other_field": "value"})

        response_data = parse_tool_response(result)
        assert response_data["status"] == "error"
        assert "prompt required" in response_data["message"]

    @pytest.mark.asyncio
    async def test_handle_tool_call_with_unknown_tool(self):
        """Test call_tool with unknown tool name."""
        result = await call_tool("unknown_tool", {"prompt": "test prompt"})

        response_data = parse_tool_response(result)
        assert response_data["status"] == "error"
        assert "Unknown tool: unknown_tool" in response_data["message"]

    @pytest.mark.asyncio
    async def test_handle_tool_call_with_exception_in_handler(self):
        """Test call_tool when handler raises exception."""
        with patch("ray_mcp.main.handlers.handle_cluster") as mock_handle_cluster:
            mock_handle_cluster.side_effect = Exception("Test exception")

            result = await call_tool("ray_cluster", {"prompt": "create cluster"})

            response_data = parse_tool_response(result)
            assert response_data["status"] == "error"
            assert "Test exception" in response_data["message"]

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self):
        """Test that handlers can handle concurrent tool calls."""
        import asyncio

        with (
            patch("ray_mcp.main.handlers.handle_cluster") as mock_handle_cluster,
            patch("ray_mcp.main.handlers.handle_job") as mock_handle_job,
            patch("ray_mcp.main.handlers.handle_cloud") as mock_handle_cloud,
        ):
            # Set up different responses for different tools
            mock_handle_cluster.return_value = {"status": "success", "type": "cluster"}
            mock_handle_job.return_value = {"status": "success", "type": "job"}
            mock_handle_cloud.return_value = {"status": "success", "type": "cloud"}

            # Make concurrent calls
            tasks = [
                call_tool("ray_cluster", {"prompt": "create cluster"}),
                call_tool("ray_job", {"prompt": "submit job"}),
                call_tool("cloud", {"prompt": "authenticate"}),
            ]

            results = await asyncio.gather(*tasks)

            # All should succeed
            assert len(results) == 3
            for result in results:
                response_data = parse_tool_response(result)
                assert response_data["status"] == "success"


@pytest.mark.unit
class TestMCPServerIntegration:
    """Test MCP server integration with tool registry."""

    @pytest.mark.asyncio
    async def test_call_tool_with_valid_cluster_request(self):
        """Test MCP server call_tool with valid cluster request."""
        with patch("ray_mcp.main.handlers.handle_cluster") as mock_handle_cluster:
            mock_handle_cluster.return_value = {
                "status": "success",
                "message": "Cluster created",
            }

            result = await call_tool("ray_cluster", {"prompt": "create cluster"})
            response_data = parse_tool_response(result)
            assert response_data["status"] == "success"
            assert response_data["message"] == "Cluster created"

    @pytest.mark.asyncio
    async def test_call_tool_with_valid_job_request(self):
        """Test MCP server call_tool with valid job request."""
        with patch("ray_mcp.main.handlers.handle_job") as mock_handle_job:
            mock_handle_job.return_value = {
                "status": "success",
                "job_id": "raysubmit_123",
            }

            result = await call_tool("ray_job", {"prompt": "submit job"})
            response_data = parse_tool_response(result)
            assert response_data["status"] == "success"
            assert response_data["job_id"] == "raysubmit_123"

    @pytest.mark.asyncio
    async def test_call_tool_with_valid_cloud_request(self):
        """Test MCP server call_tool with valid cloud request."""
        with patch("ray_mcp.main.handlers.handle_cloud") as mock_handle_cloud:
            mock_handle_cloud.return_value = {
                "status": "success",
                "message": "Authenticated",
            }

            result = await call_tool("cloud", {"prompt": "authenticate"})
            response_data = parse_tool_response(result)
            assert response_data["status"] == "success"
            assert response_data["message"] == "Authenticated"

    @pytest.mark.asyncio
    async def test_call_tool_with_no_arguments(self):
        """Test MCP server call_tool with no arguments."""
        result = await call_tool("ray_cluster", None)

        response_data = parse_tool_response(result)
        assert response_data["status"] == "error"
        assert "prompt required" in response_data["message"]

    @pytest.mark.asyncio
    async def test_call_tool_with_empty_arguments(self):
        """Test MCP server call_tool with empty arguments."""
        result = await call_tool("ray_cluster", {})

        response_data = parse_tool_response(result)
        assert response_data["status"] == "error"
        assert "prompt required" in response_data["message"]

    @pytest.mark.asyncio
    async def test_call_tool_with_missing_prompt(self):
        """Test MCP server call_tool with missing prompt."""
        result = await call_tool("ray_cluster", {"other_field": "value"})

        response_data = parse_tool_response(result)
        assert response_data["status"] == "error"
        assert "prompt required" in response_data["message"]

    @pytest.mark.asyncio
    async def test_call_tool_with_unknown_tool(self):
        """Test MCP server call_tool with unknown tool."""
        result = await call_tool("unknown_tool", {"prompt": "test"})

        response_data = parse_tool_response(result)
        assert response_data["status"] == "error"
        assert "Unknown tool: unknown_tool" in response_data["message"]

    @pytest.mark.asyncio
    async def test_call_tool_with_handler_exception(self):
        """Test MCP server call_tool when handler raises exception."""
        with patch("ray_mcp.main.handlers") as mock_handlers:
            mock_handlers.handle_cluster.side_effect = Exception("Handler error")

            result = await call_tool("ray_cluster", {"prompt": "create cluster"})

            response_data = parse_tool_response(result)
            assert response_data["status"] == "error"
            assert "Handler error" in response_data["message"]

    @pytest.mark.asyncio
    async def test_tool_routing_consistency(self):
        """Test that tool routing is consistent between call_tool and handlers."""
        with (
            patch("ray_mcp.main.handlers.handle_cluster") as mock_handle_cluster,
            patch("ray_mcp.main.handlers.handle_job") as mock_handle_job,
            patch("ray_mcp.main.handlers.handle_cloud") as mock_handle_cloud,
        ):

            # Set up mock responses
            mock_handle_cluster.return_value = {"tool": "cluster"}
            mock_handle_job.return_value = {"tool": "job"}
            mock_handle_cloud.return_value = {"tool": "cloud"}

            # Test each tool routing
            cluster_result = await call_tool("ray_cluster", {"prompt": "test"})
            job_result = await call_tool("ray_job", {"prompt": "test"})
            cloud_result = await call_tool("cloud", {"prompt": "test"})

            # Verify correct handlers were called
            mock_handle_cluster.assert_called_once_with("test")
            mock_handle_job.assert_called_once_with("test")
            mock_handle_cloud.assert_called_once_with("test")

            # Verify responses
            cluster_data = parse_tool_response(cluster_result)
            job_data = parse_tool_response(job_result)
            cloud_data = parse_tool_response(cloud_result)

            assert cluster_data["tool"] == "cluster"
            assert job_data["tool"] == "job"
            assert cloud_data["tool"] == "cloud"


@pytest.mark.unit
class TestToolValidation:
    """Test tool validation and error handling."""

    def test_tool_input_schema_validation(self):
        """Test that tool input schemas are properly validated."""
        tools = get_ray_tools()

        for tool in tools:
            schema = tool.inputSchema

            # Check schema structure
            assert "type" in schema
            assert schema["type"] == "object"
            assert "properties" in schema
            assert "required" in schema

            # Check prompt field
            properties = schema["properties"]
            assert "prompt" in properties

            prompt_schema = properties["prompt"]
            assert "type" in prompt_schema
            assert prompt_schema["type"] == "string"
            assert "description" in prompt_schema

            # Check prompt is required
            assert "prompt" in schema["required"]

    def test_tool_name_uniqueness(self):
        """Test that all tool names are unique."""
        tools = get_ray_tools()
        tool_names = [tool.name for tool in tools]

        # Check for duplicates
        assert len(tool_names) == len(set(tool_names))

    def test_tool_description_quality(self):
        """Test that tool descriptions are meaningful and helpful."""
        tools = get_ray_tools()

        for tool in tools:
            description = tool.description

            # Type checker satisfaction
            assert description is not None
            assert isinstance(description, str)

            # Check minimum length
            assert len(description) > 20

            # Check for helpful keywords
            assert any(
                keyword in description.lower()
                for keyword in ["manage", "control", "handle", "operate"]
            )

            # Check no placeholder text
            assert "TODO" not in description
            assert "FIXME" not in description


@pytest.mark.unit
class TestErrorHandling:
    """Test comprehensive error handling in tool registry."""

    @pytest.mark.asyncio
    async def test_handler_error_propagation(self):
        """Test that errors from handlers are properly propagated."""
        with patch("ray_mcp.main.handlers.handle_cluster") as mock_handle_cluster:
            # Test different types of exceptions
            exceptions = [
                ValueError("Invalid input"),
                RuntimeError("Runtime error"),
                ConnectionError("Connection failed"),
                Exception("Generic error"),
            ]

            for exception in exceptions:
                mock_handle_cluster.side_effect = exception

                result = await call_tool("ray_cluster", {"prompt": "test"})

                response_data = parse_tool_response(result)
                assert response_data["status"] == "error"
                assert str(exception) in response_data["message"]

    @pytest.mark.asyncio
    async def test_malformed_json_handling(self):
        """Test handling of malformed JSON in responses."""
        with patch("ray_mcp.main.handlers.handle_cluster") as mock_handle_cluster:
            # Mock handler returning invalid JSON structure
            invalid_response = "not a json object"
            mock_handle_cluster.return_value = invalid_response

            result = await call_tool("ray_cluster", {"prompt": "test"})

            # Should still return valid JSON even with invalid input
            response_data = parse_tool_response(result)
            assert response_data == invalid_response

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test handling of timeouts in tool calls."""
        import asyncio

        with patch("ray_mcp.main.handlers.handle_cluster") as mock_handle_cluster:
            # Mock handler that times out
            async def timeout_handler(prompt):
                await asyncio.sleep(10)  # Simulate timeout
                return {"status": "success"}

            mock_handle_cluster.side_effect = timeout_handler

            # Test with timeout
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(
                    call_tool("ray_cluster", {"prompt": "test"}),
                    timeout=0.1,
                )

    @pytest.mark.asyncio
    async def test_memory_pressure_handling(self):
        """Test handling of memory pressure scenarios."""
        with patch("ray_mcp.main.handlers.handle_cluster") as mock_handle_cluster:
            # Mock handler that consumes excessive memory
            def memory_intensive_handler(prompt):
                # Simulate memory pressure
                return {"status": "success", "large_data": "x" * 10000}

            mock_handle_cluster.side_effect = memory_intensive_handler

            result = await call_tool("ray_cluster", {"prompt": "test"})

            # Should handle large responses gracefully
            response_data = parse_tool_response(result)
            assert response_data["status"] == "success"
            assert "large_data" in response_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
