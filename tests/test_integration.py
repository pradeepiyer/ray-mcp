#!/usr/bin/env python3
"""Integration tests for Ray MCP server - Essential functionality only."""

from unittest.mock import patch
import pytest

from ray_mcp.ray_manager import RayManager
from ray_mcp.tool_registry import ToolRegistry


@pytest.mark.integration
class TestMCPIntegration:
    """Essential integration tests for MCP server functionality."""

    @pytest.fixture(autouse=True)
    def patch_ray_manager(self):
        """Patch RayManager to avoid actual Ray operations."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            yield

    @pytest.mark.asyncio
    async def test_tool_registry_and_schema_validation(self):
        """Test that all tools are available with valid schemas."""
        registry = ToolRegistry(RayManager())
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

        # Check that all tools have valid schemas
        for tool in tools:
            assert hasattr(tool, "inputSchema")
            assert isinstance(tool.inputSchema, dict)
            assert "type" in tool.inputSchema
            assert tool.inputSchema["type"] == "object"

    @pytest.mark.asyncio
    async def test_complete_mcp_workflow(self):
        """Test a complete MCP workflow through the tool registry."""
        registry = ToolRegistry(RayManager())

        # Mock RayManager methods for workflow integration
        with patch.object(registry.ray_manager, "init_cluster") as mock_init:
            with patch.object(registry.ray_manager, "submit_job") as mock_submit:
                with patch.object(registry.ray_manager, "stop_cluster") as mock_stop:
                    # Setup mock responses
                    mock_init.return_value = {
                        "status": "connected",
                        "cluster_address": "127.0.0.1:10001",
                        "dashboard_url": "http://127.0.0.1:8265",
                    }
                    mock_submit.return_value = {
                        "status": "success",
                        "result_type": "submitted",
                        "job_id": "job_123",
                    }
                    mock_stop.return_value = {
                        "status": "stopped",
                        "message": "Ray cluster stopped successfully",
                    }

                    # Mock Ray availability for job operations
                    with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
                        with patch("ray_mcp.ray_manager.ray") as mock_ray:
                            mock_ray.is_initialized.return_value = True
                            registry.ray_manager._update_state(initialized=True)

                            # Test MCP tool integration workflow
                            # 1. Initialize cluster through MCP
                            result = await registry.execute_tool("init_ray", {"num_cpus": 4})
                            assert result["status"] == "connected"
                            mock_init.assert_called_once()

                            # 2. Submit job through MCP
                            result = await registry.execute_tool(
                                "submit_job", {"entrypoint": "python test.py"}
                            )
                            assert result["status"] == "success"
                            assert result["result_type"] == "submitted"
                            mock_submit.assert_called_once()

                            # 3. Stop cluster through MCP
                            result = await registry.execute_tool("stop_ray", {})
                            assert result["status"] == "stopped"
                            mock_stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_mcp_error_handling(self):
        """Test MCP-level error handling and response formatting."""
        registry = ToolRegistry(RayManager())

        # Test Ray unavailable scenario
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", False):
            result = await registry.execute_tool("init_ray", {"num_cpus": 4})
            assert result["status"] == "error"
            assert "Ray is not available" in result["message"]

        # Test unknown tool handling
        result = await registry.execute_tool("nonexistent_tool", {})
        assert result["status"] == "error"
        assert "Unknown tool" in result["message"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
