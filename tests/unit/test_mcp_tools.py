"""Test tool registry and MCP server integration - simplified architecture."""

import json
from typing import cast
from unittest.mock import AsyncMock, patch

from mcp.types import TextContent
import pytest

from ray_mcp.main import call_tool, list_tools
from ray_mcp.tools import get_ray_tools


@pytest.mark.unit
class TestToolRegistry:
    """Test tool registry functionality."""

    def test_get_ray_tools_returns_single_tool(self):
        """Test that get_ray_tools returns exactly 1 unified tool."""
        tools = get_ray_tools()
        assert len(tools) == 1

        tool_names = [tool.name for tool in tools]
        expected_tools = {"ray"}
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
        """Test list_tools handler returns the unified ray tool."""
        tools = await list_tools()
        assert len(tools) == 1

        tool_names = [tool.name for tool in tools]
        assert "ray" in tool_names


@pytest.mark.unit
class TestDirectManagerIntegration:
    """Test direct manager integration without abstraction layers."""

    @pytest.mark.asyncio
    async def test_job_manager_integration(self):
        """Test that ray tool routes to JobManager for job operations."""
        with (
            patch("ray_mcp.main.job_manager") as mock_job_mgr,
            patch("ray_mcp.main.get_parser") as mock_parser,
        ):
            expected_response = {"status": "success", "message": "Job handled"}
            mock_job_mgr.execute_request = AsyncMock(return_value=expected_response)

            # Mock the LLM parser to return job type
            mock_parser_instance = AsyncMock()
            mock_parser_instance.parse_action = AsyncMock(
                return_value={"type": "job", "operation": "create"}
            )
            mock_parser.return_value = mock_parser_instance

            result = await call_tool(
                "ray", {"prompt": "submit job with script test.py"}
            )

            # Parse the JSON response
            result_text = cast(TextContent, cast(list, result)[0]).text
            parsed_result = json.loads(result_text)

            # With the new API, managers only receive the action, not the prompt
            mock_job_mgr.execute_request.assert_called_once_with(
                {"type": "job", "operation": "create"}
            )
            assert parsed_result == expected_response

    @pytest.mark.asyncio
    async def test_service_manager_integration(self):
        """Test that ray tool routes to ServiceManager for service operations."""
        with (
            patch("ray_mcp.main.service_manager") as mock_service_mgr,
            patch("ray_mcp.main.get_parser") as mock_parser,
        ):
            expected_response = {"status": "success", "message": "Service handled"}
            mock_service_mgr.execute_request = AsyncMock(return_value=expected_response)

            # Mock the LLM parser to return service type
            mock_parser_instance = AsyncMock()
            mock_parser_instance.parse_action = AsyncMock(
                return_value={"type": "service", "operation": "create"}
            )
            mock_parser.return_value = mock_parser_instance

            result = await call_tool("ray", {"prompt": "deploy service with model.py"})

            # Parse the JSON response
            result_text = cast(TextContent, cast(list, result)[0]).text
            parsed_result = json.loads(result_text)

            # With the new API, managers only receive the action, not the prompt
            mock_service_mgr.execute_request.assert_called_once_with(
                {"type": "service", "operation": "create"}
            )
            assert parsed_result == expected_response

    @pytest.mark.asyncio
    async def test_cloud_manager_integration(self):
        """Test that ray tool routes to CloudProviderManager for cloud operations."""
        with (
            patch("ray_mcp.main.cloud_provider_manager") as mock_cloud_mgr,
            patch("ray_mcp.main.get_parser") as mock_parser,
        ):
            expected_response = {"status": "success", "message": "Cloud handled"}
            mock_cloud_mgr.execute_request = AsyncMock(return_value=expected_response)

            # Mock the LLM parser to return cloud type
            mock_parser_instance = AsyncMock()
            mock_parser_instance.parse_action = AsyncMock(
                return_value={"type": "cloud", "operation": "authenticate"}
            )
            mock_parser.return_value = mock_parser_instance

            result = await call_tool("ray", {"prompt": "authenticate with GCP"})

            # Parse the JSON response
            result_text = cast(TextContent, cast(list, result)[0]).text
            parsed_result = json.loads(result_text)

            # With the new API, managers only receive the action, not the prompt
            mock_cloud_mgr.execute_request.assert_called_once_with(
                {"type": "cloud", "operation": "authenticate"}
            )
            assert parsed_result == expected_response

    @pytest.mark.asyncio
    async def test_unknown_tool_handling(self):
        """Test handling of unknown tool names."""
        result = await call_tool("unknown_tool", {"prompt": "test"})

        # Parse the JSON response
        result_text = cast(TextContent, cast(list, result)[0]).text
        parsed_result = json.loads(result_text)

        assert parsed_result["status"] == "error"
        assert "Unknown tool: unknown_tool" in parsed_result["message"]

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self):
        """Test concurrent tool calls work correctly with LLM-based routing."""
        import asyncio

        with (
            patch("ray_mcp.main.job_manager") as mock_job_mgr,
            patch("ray_mcp.main.service_manager") as mock_service_mgr,
            patch("ray_mcp.main.cloud_provider_manager") as mock_cloud_mgr,
            patch("ray_mcp.main.get_parser") as mock_parser,
        ):

            # Set up different responses for each manager
            mock_job_mgr.execute_request = AsyncMock(
                return_value={"type": "job", "status": "success"}
            )
            mock_service_mgr.execute_request = AsyncMock(
                return_value={"type": "service", "status": "success"}
            )
            mock_cloud_mgr.execute_request = AsyncMock(
                return_value={"type": "cloud", "status": "success"}
            )

            # Mock the LLM parser to return different types based on prompt
            mock_parser_instance = AsyncMock()

            def parse_side_effect(prompt):
                if "job" in prompt:
                    return {"type": "job", "operation": "create"}
                elif "service" in prompt:
                    return {"type": "service", "operation": "create"}
                elif "authenticate" in prompt:
                    return {"type": "cloud", "operation": "authenticate"}
                else:
                    return {"type": "job", "operation": "create"}

            mock_parser_instance.parse_action = AsyncMock(side_effect=parse_side_effect)
            mock_parser.return_value = mock_parser_instance

            # Execute concurrent calls
            tasks = [
                call_tool("ray", {"prompt": "submit job"}),
                call_tool("ray", {"prompt": "deploy service"}),
                call_tool("ray", {"prompt": "authenticate"}),
            ]

            results = await asyncio.gather(*tasks)

            assert len(results) == 3

            # Parse results
            parsed_results = [
                json.loads(cast(TextContent, cast(list, result)[0]).text)
                for result in results
            ]

            assert parsed_results[0]["type"] == "job"
            assert parsed_results[1]["type"] == "service"
            assert parsed_results[2]["type"] == "cloud"


@pytest.mark.unit
class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_manager_error_propagation(self):
        """Test that manager errors are properly handled."""
        with (
            patch("ray_mcp.main.job_manager") as mock_job_mgr,
            patch("ray_mcp.main.get_parser") as mock_parser,
        ):
            mock_job_mgr.execute_request = AsyncMock(
                side_effect=ValueError("Test error")
            )

            # Mock the LLM parser to return job type
            mock_parser_instance = AsyncMock()
            mock_parser_instance.parse_action = AsyncMock(
                return_value={"type": "job", "operation": "create"}
            )
            mock_parser.return_value = mock_parser_instance

            result = await call_tool("ray", {"prompt": "invalid job"})

            # Parse the JSON response
            result_text = cast(TextContent, cast(list, result)[0]).text
            parsed_result = json.loads(result_text)

            assert parsed_result["status"] == "error"
            assert "Test error" in parsed_result["message"]

    @pytest.mark.asyncio
    async def test_missing_prompt_handling(self):
        """Test handling of missing prompt parameter."""
        result = await call_tool("ray", {})  # No prompt

        # Parse the JSON response
        result_text = cast(TextContent, cast(list, result)[0]).text
        parsed_result = json.loads(result_text)

        assert parsed_result["status"] == "error"
        assert "prompt required" in parsed_result["message"]

    @pytest.mark.asyncio
    async def test_json_serialization_handling(self):
        """Test handling of complex response data."""
        with (
            patch("ray_mcp.main.job_manager") as mock_job_mgr,
            patch("ray_mcp.main.get_parser") as mock_parser,
        ):
            complex_response = {
                "status": "success",
                "data": {
                    "nested": {"key": "value"},
                    "list": [1, 2, 3],
                    "boolean": True,
                },
            }
            mock_job_mgr.execute_request = AsyncMock(return_value=complex_response)

            # Mock the LLM parser to return job type
            mock_parser_instance = AsyncMock()
            mock_parser_instance.parse_action = AsyncMock(
                return_value={"type": "job", "operation": "create"}
            )
            mock_parser.return_value = mock_parser_instance

            result = await call_tool("ray", {"prompt": "test"})

            # Parse the JSON response
            result_text = cast(TextContent, cast(list, result)[0]).text
            parsed_result = json.loads(result_text)

            assert parsed_result == complex_response


@pytest.mark.unit
class TestMCPServerIntegration:
    """Test MCP server integration without abstraction layers."""

    @pytest.mark.asyncio
    async def test_basic_tool_calls_work(self):
        """Test that basic tool calls work without errors with LLM routing."""
        with (
            patch("ray_mcp.main.job_manager") as mock_job_mgr,
            patch("ray_mcp.main.service_manager") as mock_service_mgr,
            patch("ray_mcp.main.cloud_provider_manager") as mock_cloud_mgr,
            patch("ray_mcp.main.get_parser") as mock_parser,
        ):

            # Set up mock responses
            mock_job_mgr.execute_request = AsyncMock(
                return_value={"status": "success", "test": "mocked"}
            )
            mock_service_mgr.execute_request = AsyncMock(
                return_value={"status": "success", "test": "mocked"}
            )
            mock_cloud_mgr.execute_request = AsyncMock(
                return_value={"status": "success", "test": "mocked"}
            )

            # Mock the LLM parser to return different types based on call count
            mock_parser_instance = AsyncMock()
            call_count = 0

            def parse_side_effect(prompt):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return {"type": "job", "operation": "create"}
                elif call_count == 2:
                    return {"type": "service", "operation": "create"}
                else:
                    return {"type": "cloud", "operation": "authenticate"}

            mock_parser_instance.parse_action = AsyncMock(side_effect=parse_side_effect)
            mock_parser.return_value = mock_parser_instance

            # Test all three operation types through the unified tool
            test_prompts = ["submit job", "deploy service", "authenticate"]
            for prompt in test_prompts:
                result = await call_tool("ray", {"prompt": prompt})
                assert result is not None

                # Parse and verify response
                result_text = cast(TextContent, cast(list, result)[0]).text
                parsed_result = json.loads(result_text)
                assert parsed_result["status"] == "success"
                assert parsed_result["test"] == "mocked"

    @pytest.mark.asyncio
    async def test_tool_argument_validation(self):
        """Test that tools properly validate arguments."""
        # Test with None arguments
        result = await call_tool("ray", None)
        result_text = cast(TextContent, cast(list, result)[0]).text
        parsed_result = json.loads(result_text)
        assert parsed_result["status"] == "error"
        assert "prompt required" in parsed_result["message"]

        # Test with empty arguments
        result = await call_tool("ray", {})
        result_text = cast(TextContent, cast(list, result)[0]).text
        parsed_result = json.loads(result_text)
        assert parsed_result["status"] == "error"
        assert "prompt required" in parsed_result["message"]
