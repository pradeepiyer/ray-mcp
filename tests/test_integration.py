#!/usr/bin/env python3
"""Integration tests for the complete Ray MCP server flow."""

import asyncio
import json
from typing import Any, Dict, List, cast
from unittest.mock import AsyncMock, Mock, patch

import pytest

from mcp.types import TextContent, Tool
from ray_mcp.main import call_tool, list_tools


def get_text_content(result: Any, index: int = 0) -> TextContent:
    """Helper function to get TextContent from result with proper typing."""
    return cast(TextContent, result[index])


@pytest.mark.fast
class TestMCPIntegration:
    """Integration tests for the complete MCP server workflow."""

    @pytest.mark.asyncio
    async def test_list_tools_returns_all_tools(self):
        """Test that list_tools returns all expected tools."""
        tools = await list_tools()

        assert isinstance(tools, list)

        # Check that all tools are Tool instances
        for tool in tools:
            assert isinstance(tool, Tool)
            assert hasattr(tool, "name")
            assert hasattr(tool, "description")
            assert hasattr(tool, "inputSchema")

        # Check specific tool names instead of hardcoded count
        tool_names = {tool.name for tool in tools}
        required_tools = {
            "start_ray",
            "connect_ray",
            "stop_ray",
            "cluster_status",
            "cluster_resources",
            "cluster_nodes",
            "worker_status",
            "submit_job",
            "list_jobs",
            "job_status",
            "cancel_job",
            "monitor_job",
            "debug_job",
            "list_actors",
            "kill_actor",
            "performance_metrics",
            "health_check",
            "optimize_config",
            "schedule_job",
            "get_logs",
        }

        # All required tools must be present
        assert required_tools.issubset(
            tool_names
        ), f"Missing tools: {required_tools - tool_names}"

        # Optionally check that we don't have unexpected tools
        unexpected_tools = tool_names - required_tools
        if unexpected_tools:
            print(f"Note: Found additional tools: {unexpected_tools}")

    @pytest.mark.asyncio
    async def test_tool_schemas_are_valid(self):
        """Test that all tool schemas are valid JSON schemas."""
        tools = await list_tools()

        for tool in tools:
            schema = tool.inputSchema

            # Basic schema validation
            assert isinstance(schema, dict)
            assert "type" in schema
            assert schema["type"] == "object"
            assert "properties" in schema

            # Check that required fields are in properties
            if "required" in schema:
                for required_field in schema["required"]:
                    assert (
                        required_field in schema["properties"]
                    ), f"Required field {required_field} not in properties for tool {tool.name}"

    @pytest.mark.asyncio
    async def test_complete_workflow_cluster_management(self):
        """Test a complete workflow for cluster management."""
        mock_ray_manager = Mock()
        mock_ray_manager.start_cluster = AsyncMock(
            return_value={
                "status": "started",
                "address": "ray://127.0.0.1:10001",
                "message": "Cluster started successfully",
            }
        )
        mock_ray_manager.get_cluster_status = AsyncMock(
            return_value={
                "status": "running",
                "cluster_resources": {"CPU": 8, "memory": 16000000000},
                "available_resources": {"CPU": 4, "memory": 8000000000},
                "nodes": 2,
                "alive_nodes": 2,
            }
        )
        mock_ray_manager.stop_cluster = AsyncMock(
            return_value={
                "status": "stopped",
                "message": "Cluster stopped successfully",
            }
        )

        with patch("ray_mcp.main.ray_manager", mock_ray_manager):
            with patch("ray_mcp.main.RAY_AVAILABLE", True):

                # Step 1: Start cluster
                result = await call_tool("start_ray", {"num_cpus": 8})
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "started"

                # Step 2: Check status
                result = await call_tool("cluster_status")
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "running"
                assert response_data["nodes"] == 2

                # Step 3: Stop cluster
                result = await call_tool("stop_ray")
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "stopped"

    @pytest.mark.asyncio
    async def test_complete_workflow_job_lifecycle(self):
        """Test a complete job lifecycle workflow."""
        mock_ray_manager = Mock()
        mock_ray_manager.submit_job = AsyncMock(
            return_value={
                "status": "submitted",
                "job_id": "job_123",
                "message": "Job submitted successfully",
            }
        )
        mock_ray_manager.get_job_status = AsyncMock(
            return_value={
                "status": "success",
                "job_id": "job_123",
                "job_status": "RUNNING",
                "entrypoint": "python train.py",
            }
        )
        mock_ray_manager.monitor_job_progress = AsyncMock(
            return_value={
                "status": "success",
                "job_id": "job_123",
                "progress": "75%",
                "estimated_time_remaining": "5 minutes",
            }
        )
        mock_ray_manager.cancel_job = AsyncMock(
            return_value={
                "status": "cancelled",
                "job_id": "job_123",
                "message": "Job cancelled successfully",
            }
        )

        with patch("ray_mcp.main.ray_manager", mock_ray_manager):
            with patch("ray_mcp.main.RAY_AVAILABLE", True):

                # Step 1: Submit job
                result = await call_tool(
                    "submit_job",
                    {
                        "entrypoint": "python train.py",
                        "runtime_env": {"pip": ["requests", "click"]},
                    },
                )
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "submitted"
                job_id = response_data["job_id"]

                # Step 2: Check job status
                result = await call_tool("job_status", {"job_id": job_id})
                response_data = json.loads(get_text_content(result).text)
                assert response_data["job_status"] == "RUNNING"

                # Step 3: Monitor progress
                result = await call_tool("monitor_job", {"job_id": job_id})
                response_data = json.loads(get_text_content(result).text)
                assert "progress" in response_data

                # Step 4: Cancel job
                result = await call_tool("cancel_job", {"job_id": job_id})
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_error_propagation(self):
        """Test that errors are properly propagated through the system."""
        mock_ray_manager = Mock()
        mock_ray_manager.start_cluster = AsyncMock(
            side_effect=Exception("Ray initialization failed")
        )

        with patch("ray_mcp.main.ray_manager", mock_ray_manager):
            with patch("ray_mcp.main.RAY_AVAILABLE", True):

                result = await call_tool("start_ray")
                response_data = json.loads(get_text_content(result).text)

                assert response_data["status"] == "error"
                assert "Ray initialization failed" in response_data["message"]

    @pytest.mark.asyncio
    async def test_ray_unavailable_handling(self):
        """Test handling when Ray is not available."""
        with patch("ray_mcp.main.RAY_AVAILABLE", False):

            result = await call_tool("start_ray")
            response_text = get_text_content(result).text

            assert "Ray is not available" in response_text

    @pytest.mark.asyncio
    async def test_parameter_validation_integration(self):
        """Test parameter validation in the complete flow."""
        mock_ray_manager = Mock()
        mock_ray_manager.get_job_status = AsyncMock(
            return_value={"status": "success", "job_status": "RUNNING"}
        )

        with patch("ray_mcp.main.ray_manager", mock_ray_manager):
            with patch("ray_mcp.main.RAY_AVAILABLE", True):

                # Test with missing required parameter
                result = await call_tool("job_status", {})  # Missing job_id
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "error"

                # Test with valid parameters
                result = await call_tool("job_status", {"job_id": "test_job"})
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "success"

    @pytest.mark.asyncio
    async def test_response_format_consistency(self):
        """Test that all tool responses follow consistent format."""
        mock_ray_manager = Mock()
        # Set up mock responses for different tools
        mock_ray_manager.start_cluster = AsyncMock(return_value={"status": "started"})
        mock_ray_manager.list_jobs = AsyncMock(
            return_value={"status": "success", "jobs": []}
        )
        mock_ray_manager.get_performance_metrics = AsyncMock(
            return_value={"status": "success", "metrics": {}}
        )

        with patch("ray_mcp.main.ray_manager", mock_ray_manager):
            with patch("ray_mcp.main.RAY_AVAILABLE", True):

                # Test multiple tools
                tools_to_test = ["start_ray", "list_jobs", "performance_metrics"]

                for tool_name in tools_to_test:
                    result = await call_tool(tool_name)

                    # Check response format
                    assert isinstance(result, list)
                    assert len(result) == 1
                    assert isinstance(result[0], TextContent)
                    assert result[0].type == "text"

                    # Check JSON response structure
                    response_data = json.loads(get_text_content(result).text)
                    assert isinstance(response_data, dict)
                    assert "status" in response_data

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self):
        """Test handling concurrent tool calls."""
        mock_ray_manager = Mock()
        mock_ray_manager.get_cluster_status = AsyncMock(
            return_value={"status": "running"}
        )
        mock_ray_manager.list_jobs = AsyncMock(
            return_value={"status": "success", "jobs": []}
        )
        mock_ray_manager.list_actors = AsyncMock(
            return_value={"status": "success", "actors": []}
        )

        with patch("ray_mcp.main.ray_manager", mock_ray_manager):
            with patch("ray_mcp.main.RAY_AVAILABLE", True):

                # Run multiple tool calls concurrently
                tasks = [
                    call_tool("cluster_status"),
                    call_tool("list_jobs"),
                    call_tool("list_actors"),
                ]

                results = await asyncio.gather(*tasks)

                # Check that all calls completed successfully
                assert len(results) == 3
                for result in results:
                    response_data = json.loads(get_text_content(result).text)
                    assert response_data["status"] in ["running", "success"]

    @pytest.mark.asyncio
    async def test_tool_call_with_complex_parameters(self):
        """Test tool calls with complex parameter structures."""
        mock_ray_manager = Mock()
        mock_ray_manager.submit_job = AsyncMock(
            return_value={"status": "submitted", "job_id": "complex_job"}
        )

        with patch("ray_mcp.main.ray_manager", mock_ray_manager):
            with patch("ray_mcp.main.RAY_AVAILABLE", True):

                # Test complex job submission
                complex_args = {
                    "entrypoint": "python complex_job.py",
                    "runtime_env": {
                        "pip": ["requests==2.28.0", "click==8.0.0"],
                        "env_vars": {"CUDA_VISIBLE_DEVICES": "0,1"},
                        "working_dir": "/workspace",
                    },
                    "metadata": {
                        "owner": "data_team",
                        "project": "nlp_training",
                        "priority": "high",
                        "tags": ["gpu", "distributed"],
                    },
                }

                result = await call_tool("submit_job", complex_args)
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "submitted"

                # Verify the complex parameters were passed correctly
                mock_ray_manager.submit_job.assert_called_once_with(**complex_args)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
