#!/usr/bin/env python3
"""Unit tests for MCP server tools and handlers.

This module tests the MCP tool definitions, handlers, and the integration
between the server layer and the manager layer.

Test Focus:
- Tool schema validation
- Handler routing and delegation
- MCP protocol compliance
- Error propagation and formatting
"""

import json
from typing import List
from unittest.mock import AsyncMock, Mock, patch

from mcp.types import TextContent
import pytest

from ray_mcp.handlers import RayHandlers
from ray_mcp.tools import get_ray_tools


@pytest.mark.unit
class TestRayTools:
    """Test the 3 Ray MCP tool definitions."""

    def test_get_ray_tools_structure(self):
        """Test that get_ray_tools returns properly structured tools."""
        tools = get_ray_tools()

        # Should return exactly 3 tools
        assert len(tools) == 3

        # Extract tool names
        tool_names = [tool.name for tool in tools]
        expected_names = ["ray_cluster", "ray_job", "cloud"]

        assert set(tool_names) == set(expected_names)

    def test_ray_cluster_tool_schema(self):
        """Test ray_cluster tool schema."""
        tools = get_ray_tools()
        cluster_tool = next(tool for tool in tools if tool.name == "ray_cluster")

        # Verify basic structure
        assert cluster_tool.name == "ray_cluster"
        assert "cluster" in cluster_tool.description.lower()

        # Verify input schema
        schema = cluster_tool.inputSchema
        assert schema["type"] == "object"
        assert "prompt" in schema["properties"]
        assert schema["required"] == ["prompt"]

        # Verify prompt property
        prompt_prop = schema["properties"]["prompt"]
        assert prompt_prop["type"] == "string"
        assert "description" in prompt_prop
        assert (
            "example" in prompt_prop["description"].lower()
            or "Examples" in prompt_prop["description"]
        )

    def test_ray_job_tool_schema(self):
        """Test ray_job tool schema."""
        tools = get_ray_tools()
        job_tool = next(tool for tool in tools if tool.name == "ray_job")

        # Verify basic structure
        assert job_tool.name == "ray_job"
        assert "job" in job_tool.description.lower()

        # Verify input schema follows same pattern
        schema = job_tool.inputSchema
        assert schema["type"] == "object"
        assert "prompt" in schema["properties"]
        assert schema["required"] == ["prompt"]
        assert schema["properties"]["prompt"]["type"] == "string"

    def test_cloud_tool_schema(self):
        """Test cloud tool schema."""
        tools = get_ray_tools()
        cloud_tool = next(tool for tool in tools if tool.name == "cloud")

        # Verify basic structure
        assert cloud_tool.name == "cloud"
        assert "cloud" in cloud_tool.description.lower()

        # Verify input schema follows same pattern
        schema = cloud_tool.inputSchema
        assert schema["type"] == "object"
        assert "prompt" in schema["properties"]
        assert schema["required"] == ["prompt"]
        assert schema["properties"]["prompt"]["type"] == "string"

    def test_tool_descriptions_contain_examples(self):
        """Test that all tool descriptions contain helpful examples."""
        tools = get_ray_tools()

        for tool in tools:
            description = tool.inputSchema["properties"]["prompt"]["description"]

            # Should contain examples or example text
            assert any(
                keyword in description.lower() for keyword in ["example", "examples"]
            )

            # Should contain practical usage patterns
            if tool.name == "ray_cluster":
                assert any(
                    keyword in description.lower()
                    for keyword in ["create", "connect", "stop"]
                )
            elif tool.name == "ray_job":
                assert any(
                    keyword in description.lower()
                    for keyword in ["submit", "list", "logs", "cancel"]
                )
            elif tool.name == "cloud":
                assert any(
                    keyword in description.lower()
                    for keyword in ["authenticate", "cluster", "gke"]
                )


@pytest.mark.unit
class TestRayHandlers:
    """Test RayHandlers integration with RayUnifiedManager."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create mock unified manager
        self.unified_manager_mock = AsyncMock()
        self.handlers = RayHandlers(self.unified_manager_mock)

    @pytest.mark.asyncio
    async def test_handle_ray_cluster_tool(self):
        """Test handling ray_cluster tool calls."""
        # Mock successful cluster operation
        self.unified_manager_mock.handle_cluster_request.return_value = {
            "status": "success",
            "message": "Cluster created successfully",
            "cluster_address": "localhost:8265",
        }

        # Simulate tool call
        arguments = {"prompt": "create a local cluster with 4 CPUs"}
        result = await self.handlers.handle_tool_call("ray_cluster", arguments)

        # Verify manager was called correctly
        self.unified_manager_mock.handle_cluster_request.assert_called_once_with(
            "create a local cluster with 4 CPUs"
        )

        # Verify response format
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)

        # Parse the JSON response
        response_data = json.loads(result[0].text)
        assert response_data["status"] == "success"
        assert "Cluster created successfully" in response_data["message"]

    @pytest.mark.asyncio
    async def test_handle_ray_job_tool(self):
        """Test handling ray_job tool calls."""
        # Mock successful job operation
        self.unified_manager_mock.handle_job_request.return_value = {
            "status": "success",
            "job_id": "raysubmit_123",
            "message": "Job submitted successfully",
        }

        arguments = {"prompt": "submit job with script train.py"}
        result = await self.handlers.handle_tool_call("ray_job", arguments)

        # Verify manager was called
        self.unified_manager_mock.handle_job_request.assert_called_once_with(
            "submit job with script train.py"
        )

        # Verify response
        response_data = json.loads(result[0].text)
        assert response_data["status"] == "success"
        assert response_data["job_id"] == "raysubmit_123"

    @pytest.mark.asyncio
    async def test_handle_cloud_tool(self):
        """Test handling cloud tool calls."""
        # Mock successful cloud operation
        self.unified_manager_mock.handle_cloud_request.return_value = {
            "status": "success",
            "message": "Authenticated with GCP",
            "project_id": "ml-experiments",
        }

        arguments = {"prompt": "authenticate with GCP project ml-experiments"}
        result = await self.handlers.handle_tool_call("cloud", arguments)

        # Verify manager was called
        self.unified_manager_mock.handle_cloud_request.assert_called_once_with(
            "authenticate with GCP project ml-experiments"
        )

        # Verify response
        response_data = json.loads(result[0].text)
        assert response_data["status"] == "success"
        assert "Authenticated with GCP" in response_data["message"]

    @pytest.mark.asyncio
    async def test_handle_invalid_tool_name(self):
        """Test handling calls to invalid tool names."""
        arguments = {"prompt": "some prompt"}
        result = await self.handlers.handle_tool_call("invalid_tool", arguments)

        # Should return error
        response_data = json.loads(result[0].text)
        assert response_data["status"] == "error"
        assert "Unknown tool" in response_data["message"]

    @pytest.mark.asyncio
    async def test_handle_missing_prompt_argument(self):
        """Test handling calls without prompt argument."""
        # Test completely missing arguments
        result = await self.handlers.handle_tool_call("ray_cluster", None)
        response_data = json.loads(result[0].text)
        assert response_data["status"] == "error"
        assert "arguments required" in response_data["message"].lower()

        # Test empty arguments (should proceed to prompt validation)
        result = await self.handlers.handle_tool_call("ray_cluster", {})
        response_data = json.loads(result[0].text)
        assert response_data["status"] == "error"
        assert "prompt required" in response_data["message"].lower()

        # Test arguments without prompt
        result = await self.handlers.handle_tool_call(
            "ray_cluster", {"other_field": "value"}
        )
        response_data = json.loads(result[0].text)
        assert response_data["status"] == "error"
        assert "prompt required" in response_data["message"].lower()

    @pytest.mark.asyncio
    async def test_error_propagation_from_manager(self):
        """Test that errors from managers are properly propagated."""
        # Mock manager returning error
        self.unified_manager_mock.handle_cluster_request.return_value = {
            "status": "error",
            "message": "Ray is not available",
        }

        arguments = {"prompt": "create cluster"}
        result = await self.handlers.handle_tool_call("ray_cluster", arguments)

        # Error should be propagated
        response_data = json.loads(result[0].text)
        assert response_data["status"] == "error"
        assert "Ray is not available" in response_data["message"]

    @pytest.mark.asyncio
    async def test_exception_handling_in_handlers(self):
        """Test that exceptions in managers are caught and handled."""
        # Mock manager raising exception
        self.unified_manager_mock.handle_job_request.side_effect = Exception(
            "Unexpected error"
        )

        arguments = {"prompt": "submit job"}
        result = await self.handlers.handle_tool_call("ray_job", arguments)

        # Exception should be caught and converted to error response
        response_data = json.loads(result[0].text)
        assert response_data["status"] == "error"
        assert "error" in response_data["message"].lower()

    @pytest.mark.asyncio
    async def test_response_json_serialization(self):
        """Test that all responses are valid JSON."""
        # Test various response types
        test_cases = [
            {
                "tool": "ray_cluster",
                "mock_response": {
                    "status": "success",
                    "cluster_address": "localhost:8265",
                    "dashboard_url": "http://localhost:8265",
                    "nodes": [{"id": "node1", "resources": {"CPU": 4}}],
                },
            },
            {
                "tool": "ray_job",
                "mock_response": {
                    "status": "success",
                    "jobs": [
                        {"job_id": "job1", "status": "RUNNING"},
                        {"job_id": "job2", "status": "SUCCEEDED"},
                    ],
                },
            },
            {
                "tool": "cloud",
                "mock_response": {
                    "status": "error",
                    "message": "Authentication failed",
                    "details": {"error_code": 401, "retry_after": 60},
                },
            },
        ]

        for case in test_cases:
            # Set up mock response
            if case["tool"] == "ray_cluster":
                self.unified_manager_mock.handle_cluster_request.return_value = case[
                    "mock_response"
                ]
            elif case["tool"] == "ray_job":
                self.unified_manager_mock.handle_job_request.return_value = case[
                    "mock_response"
                ]
            elif case["tool"] == "cloud":
                self.unified_manager_mock.handle_cloud_request.return_value = case[
                    "mock_response"
                ]

            # Make tool call
            result = await self.handlers.handle_tool_call(
                case["tool"], {"prompt": "test"}
            )

            # Verify JSON is valid and parseable
            response_text = result[0].text
            parsed = json.loads(response_text)  # Should not raise exception

            # Verify structure matches expectation
            assert parsed == case["mock_response"]

    def test_handler_initialization(self):
        """Test that handlers are properly initialized."""
        manager = Mock()
        handlers = RayHandlers(manager)

        # Should store the manager reference
        assert handlers.unified_manager is manager

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self):
        """Test that handlers can handle concurrent tool calls."""
        import asyncio

        # Mock different responses for different calls
        self.unified_manager_mock.handle_cluster_request.return_value = {
            "status": "success",
            "type": "cluster",
        }
        self.unified_manager_mock.handle_job_request.return_value = {
            "status": "success",
            "type": "job",
        }
        self.unified_manager_mock.handle_cloud_request.return_value = {
            "status": "success",
            "type": "cloud",
        }

        # Make concurrent calls
        tasks = [
            self.handlers.handle_tool_call("ray_cluster", {"prompt": "cluster prompt"}),
            self.handlers.handle_tool_call("ray_job", {"prompt": "job prompt"}),
            self.handlers.handle_tool_call("cloud", {"prompt": "cloud prompt"}),
        ]

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert len(results) == 3

        # Parse responses
        responses = [json.loads(result[0].text) for result in results]

        # Should have different types as expected
        types = [resp["type"] for resp in responses]
        assert "cluster" in types
        assert "job" in types
        assert "cloud" in types


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
