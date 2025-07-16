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
from typing import Any, List
from unittest.mock import AsyncMock, Mock, patch

from mcp.types import TextContent
import pytest

from ray_mcp.main import call_tool
from ray_mcp.tools import get_ray_tools


def parse_tool_response(result: Any) -> dict:
    """Helper to parse tool response."""
    # Type checker satisfaction - cast to expected type
    from typing import cast

    result_list = cast(List[TextContent], result)
    assert len(result_list) == 1
    text_content = cast(TextContent, result_list[0])
    assert isinstance(text_content, TextContent)
    return json.loads(text_content.text)


@pytest.mark.unit
class TestRayTools:
    """Test the 3 Ray MCP tool definitions."""

    def test_get_ray_tools_structure(self):
        """Test that get_ray_tools returns properly structured tools."""
        tools = get_ray_tools()

        # Should return exactly 3 tools
        assert len(tools) == 3

        # Check each tool has required attributes
        for tool in tools:
            assert hasattr(tool, "name")
            assert hasattr(tool, "description")
            assert hasattr(tool, "inputSchema")
            assert isinstance(tool.name, str)
            assert tool.description is None or isinstance(tool.description, str)

        # Check tool names are exactly what we expect
        tool_names = [tool.name for tool in tools]
        assert set(tool_names) == {"ray_cluster", "ray_job", "cloud"}

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

        # Verify input schema
        schema = job_tool.inputSchema
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

    def test_cloud_tool_schema(self):
        """Test cloud tool schema."""
        tools = get_ray_tools()
        cloud_tool = next(tool for tool in tools if tool.name == "cloud")

        # Verify basic structure
        assert cloud_tool.name == "cloud"
        assert "cloud" in cloud_tool.description.lower()

        # Verify input schema
        schema = cloud_tool.inputSchema
        assert schema["type"] == "object"
        assert "prompt" in schema["properties"]
        assert schema["required"] == ["prompt"]

        # Verify prompt property
        prompt_prop = schema["properties"]["prompt"]
        assert prompt_prop["type"] == "string"
        assert "description" in prompt_prop

    def test_tool_descriptions_contain_examples(self):
        """Test that tool descriptions contain helpful examples."""
        tools = get_ray_tools()

        for tool in tools:
            description = tool.description
            if description is not None:
                assert len(description) > 50  # Should be substantial

                # Check that descriptions contain helpful keywords
                if tool.name == "ray_cluster":
                    assert any(
                        keyword in description.lower()
                        for keyword in ["cluster", "connect", "create", "manage"]
                    )
                elif tool.name == "ray_job":
                    assert any(
                        keyword in description.lower()
                        for keyword in ["job", "submit", "run", "execute"]
                    )
                elif tool.name == "cloud":
                    assert any(
                        keyword in description.lower()
                        for keyword in ["cloud", "gcp", "gke", "kubernetes"]
                    )


@pytest.mark.unit
class TestRayHandlers:
    """Test RayHandlers integration via call_tool."""

    @pytest.mark.asyncio
    async def test_handle_ray_cluster_tool(self):
        """Test handling ray_cluster tool calls."""
        with patch("ray_mcp.main.handlers.handle_cluster") as mock_handle_cluster:
            # Mock successful cluster operation
            mock_handle_cluster.return_value = {
                "status": "success",
                "message": "Cluster created successfully",
                "cluster_address": "localhost:8265",
            }

            # Simulate tool call
            result = await call_tool(
                "ray_cluster", {"prompt": "create a local cluster with 4 CPUs"}
            )

            # Verify handler was called correctly
            mock_handle_cluster.assert_called_once_with(
                "create a local cluster with 4 CPUs"
            )

            # Verify response format and content
            response_data = parse_tool_response(result)
            assert response_data["status"] == "success"
            assert response_data["message"] == "Cluster created successfully"
            assert response_data["cluster_address"] == "localhost:8265"

    @pytest.mark.asyncio
    async def test_handle_ray_job_tool(self):
        """Test handling ray_job tool calls."""
        with patch("ray_mcp.main.handlers.handle_job") as mock_handle_job:
            # Mock successful job operation
            mock_handle_job.return_value = {
                "status": "success",
                "job_id": "raysubmit_123",
                "message": "Job submitted successfully",
            }

            # Simulate tool call
            result = await call_tool(
                "ray_job", {"prompt": "submit job with script train.py"}
            )

            # Verify handler was called correctly
            mock_handle_job.assert_called_once_with("submit job with script train.py")

            # Verify response content
            response_data = parse_tool_response(result)
            assert response_data["status"] == "success"
            assert response_data["job_id"] == "raysubmit_123"
            assert response_data["message"] == "Job submitted successfully"

    @pytest.mark.asyncio
    async def test_handle_cloud_tool(self):
        """Test handling cloud tool calls."""
        with patch("ray_mcp.main.handlers.handle_cloud") as mock_handle_cloud:
            # Mock successful cloud operation
            mock_handle_cloud.return_value = {
                "status": "success",
                "message": "Authenticated with GCP",
                "project_id": "ml-experiments",
            }

            # Simulate tool call
            result = await call_tool(
                "cloud", {"prompt": "authenticate with GCP project ml-experiments"}
            )

            # Verify handler was called correctly
            mock_handle_cloud.assert_called_once_with(
                "authenticate with GCP project ml-experiments"
            )

            # Verify response content
            response_data = parse_tool_response(result)
            assert response_data["status"] == "success"
            assert response_data["message"] == "Authenticated with GCP"
            assert response_data["project_id"] == "ml-experiments"

    @pytest.mark.asyncio
    async def test_handle_invalid_tool_name(self):
        """Test handling calls to invalid tool names."""
        result = await call_tool("invalid_tool", {"prompt": "some prompt"})

        # Should return error
        response_data = parse_tool_response(result)
        assert response_data["status"] == "error"
        assert "Unknown tool" in response_data["message"]

    @pytest.mark.asyncio
    async def test_handle_missing_prompt_argument(self):
        """Test handling calls without prompt argument."""
        # Test completely missing arguments
        result = await call_tool("ray_cluster", None)
        response_data = parse_tool_response(result)
        assert response_data["status"] == "error"
        assert "prompt required" in response_data["message"].lower()

        # Test empty arguments
        result = await call_tool("ray_cluster", {})
        response_data = parse_tool_response(result)
        assert response_data["status"] == "error"
        assert "prompt required" in response_data["message"].lower()

        # Test arguments without prompt
        result = await call_tool("ray_cluster", {"other_field": "value"})
        response_data = parse_tool_response(result)
        assert response_data["status"] == "error"
        assert "prompt required" in response_data["message"].lower()

    @pytest.mark.asyncio
    async def test_handle_handler_exception(self):
        """Test handling exceptions in handlers."""
        with patch("ray_mcp.main.handlers.handle_cluster") as mock_handle_cluster:
            # Mock exception from cluster handler
            mock_handle_cluster.side_effect = Exception("Cluster error")

            result = await call_tool("ray_cluster", {"prompt": "create cluster"})

            # Should return error
            response_data = parse_tool_response(result)
            assert response_data["status"] == "error"
            assert "Cluster error" in response_data["message"]

    @pytest.mark.asyncio
    async def test_handle_job_exception(self):
        """Test handling exceptions in job handlers."""
        with patch("ray_mcp.main.handlers.handle_job") as mock_handle_job:
            # Mock exception from job handler
            mock_handle_job.side_effect = Exception("Job error")

            result = await call_tool("ray_job", {"prompt": "submit job"})

            # Should return error
            response_data = parse_tool_response(result)
            assert response_data["status"] == "error"
            assert "Job error" in response_data["message"]

    @pytest.mark.asyncio
    async def test_handle_cloud_exception(self):
        """Test handling exceptions in cloud handlers."""
        with patch("ray_mcp.main.handlers.handle_cloud") as mock_handle_cloud:
            # Mock exception from cloud handler
            mock_handle_cloud.side_effect = Exception("Cloud error")

            result = await call_tool("cloud", {"prompt": "authenticate"})

            # Should return error
            response_data = parse_tool_response(result)
            assert response_data["status"] == "error"
            assert "Cloud error" in response_data["message"]

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self):
        """Test that handlers can handle concurrent tool calls."""
        import asyncio

        with (
            patch("ray_mcp.main.handlers.handle_cluster") as mock_handle_cluster,
            patch("ray_mcp.main.handlers.handle_job") as mock_handle_job,
            patch("ray_mcp.main.handlers.handle_cloud") as mock_handle_cloud,
        ):
            # Mock different responses for different calls
            mock_handle_cluster.return_value = {"status": "success", "type": "cluster"}
            mock_handle_job.return_value = {"status": "success", "type": "job"}
            mock_handle_cloud.return_value = {"status": "success", "type": "cloud"}

            # Make concurrent calls
            tasks = [
                call_tool("ray_cluster", {"prompt": "cluster prompt"}),
                call_tool("ray_job", {"prompt": "job prompt"}),
                call_tool("cloud", {"prompt": "cloud prompt"}),
            ]

            results = await asyncio.gather(*tasks)

            # All should succeed
            assert len(results) == 3

            # Parse responses
            responses = [parse_tool_response(result) for result in results]

            # Should have different types as expected
            types = [resp["type"] for resp in responses]
            assert "cluster" in types
            assert "job" in types
            assert "cloud" in types


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
