#!/usr/bin/env python3
"""Tests for core Ray MCP system functionality.

This file consolidates tests for:
- Tool registry and MCP protocol integration
- Unified manager architecture and delegation
- System interfaces and contracts
- Foundation components critical to system operation

Focus: Behavior-driven tests for critical system functionality.
"""

import asyncio
from inspect import Parameter, Signature
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ray_mcp.handlers import RayHandlers
from ray_mcp.managers.unified_manager import RayUnifiedManager
from ray_mcp.tools import get_ray_tools


@pytest.mark.fast
class TestTools:
    """Test tool definitions and structure."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_ray_manager = Mock()
        self.handlers = RayHandlers(self.mock_ray_manager)

    def test_tool_definitions_structure(self):
        """Test that tools are properly defined with correct structure."""
        # Test tool discovery
        tools = get_ray_tools()
        assert len(tools) == 3

        # Check that we have the expected tools
        tool_names = [tool.name for tool in tools]
        expected_tools = ["ray_cluster", "ray_job", "cloud"]
        assert set(tool_names) == set(expected_tools)

        # Verify each tool has required schema structure
        for tool in tools:
            assert tool.inputSchema is not None
            assert "properties" in tool.inputSchema
            assert "prompt" in tool.inputSchema["properties"]
            assert tool.inputSchema["required"] == ["prompt"]

    def test_mcp_schema_validation(self):
        """Test that all tools have valid MCP schemas."""
        tools = get_ray_tools()

        # Verify all tools have proper MCP schema structure
        for tool in tools:
            assert hasattr(tool, "name")
            assert hasattr(tool, "description")
            assert hasattr(tool, "inputSchema")

            # Check schema structure
            schema = tool.inputSchema
            assert schema["type"] == "object"
            assert "properties" in schema
            assert "prompt" in schema["properties"]
            assert schema["properties"]["prompt"]["type"] == "string"

    def test_prompt_based_tool_functionality(self):
        """Test that tools use prompt-based interfaces."""
        tools = get_ray_tools()

        # All tools should have natural language prompts
        for tool in tools:
            properties = tool.inputSchema["properties"]
            assert "prompt" in properties
            prompt_prop = properties["prompt"]
            assert prompt_prop["type"] == "string"
            assert "description" in prompt_prop
            assert len(prompt_prop["description"]) > 50  # Should have detailed examples

    @pytest.mark.asyncio
    async def test_handlers_integration(self):
        """Test that handlers work with mock manager."""
        # Mock manager for testing
        mock_manager = Mock(spec=RayUnifiedManager)
        mock_manager.init_cluster = AsyncMock(return_value={"status": "success"})
        mock_manager.list_ray_jobs = AsyncMock(
            return_value={"status": "success", "jobs": []}
        )
        mock_manager.create_kuberay_job = AsyncMock(
            return_value={"status": "success", "job_id": "test_job"}
        )

        handlers = RayHandlers(mock_manager)

        # Test cluster action
        result = await handlers.handle_cluster("Create a local Ray cluster with 4 CPUs")
        assert result["status"] == "success"
        mock_manager.init_cluster.assert_called_once()

        # Test job action
        result = await handlers.handle_job("List all running jobs")
        assert result["status"] == "success"
        mock_manager.list_ray_jobs.assert_called_once()


@pytest.mark.fast
class TestUnifiedManagerArchitecture:
    """Test unified manager architecture and delegation patterns."""

    def test_unified_manager_component_initialization(self):
        """Test that unified manager initializes all required components."""
        manager = RayUnifiedManager()

        # Test component access methods
        assert manager.get_state_manager() is not None
        assert manager.get_cluster_manager() is not None
        assert manager.get_job_manager() is not None
        assert manager.get_log_manager() is not None
        assert manager.get_port_manager() is not None

    def test_property_delegation_to_components(self):
        """Test that properties are correctly delegated to underlying components."""
        manager = RayUnifiedManager()

        # Mock state for testing
        mock_state = {
            "initialized": True,
            "cluster_address": "127.0.0.1:10001",
            "dashboard_url": "http://127.0.0.1:8265",
            "job_client": Mock(),
        }

        with patch.object(manager._state_manager, "get_state", return_value=mock_state):
            with patch.object(
                manager._state_manager, "is_initialized", return_value=True
            ):
                assert manager.is_initialized is True
                assert manager.cluster_address == "127.0.0.1:10001"
                assert manager.dashboard_url == "http://127.0.0.1:8265"
                assert manager.job_client is not None

    @pytest.mark.asyncio
    async def test_manager_delegation_workflow(self):
        """Test that manager methods properly delegate to specialized components."""
        manager = RayUnifiedManager()

        # Mock underlying managers
        mock_cluster_manager = Mock()
        mock_job_manager = Mock()
        mock_log_manager = Mock()

        mock_cluster_manager.init_cluster = AsyncMock(
            return_value={"status": "success", "cluster_address": "127.0.0.1:10001"}
        )
        mock_job_manager.submit_job = AsyncMock(
            return_value={"status": "success", "job_id": "job_123"}
        )
        mock_log_manager.retrieve_logs = AsyncMock(
            return_value={"status": "success", "logs": "Log content"}
        )

        manager._cluster_manager = mock_cluster_manager
        manager._job_manager = mock_job_manager
        manager._log_manager = mock_log_manager

        # Test cluster management delegation
        result = await manager.init_cluster(num_cpus=4)
        assert result["status"] == "success"
        mock_cluster_manager.init_cluster.assert_called_with(num_cpus=4)

        # Test job management delegation
        result = await manager.submit_ray_job("python script.py")
        assert result["job_id"] == "job_123"
        mock_job_manager.submit_job.assert_called_once()

        # Test log management delegation
        result = await manager.retrieve_logs("job_123", log_type="job", num_lines=50)
        assert result["logs"] == "Log content"
        mock_log_manager.retrieve_logs.assert_called_with(
            "job_123", "job", 50, False, 10, None, None
        )

    @pytest.mark.asyncio
    async def test_error_propagation_across_managers(self):
        """Test that errors are properly propagated from underlying components."""
        manager = RayUnifiedManager()

        # Test cluster manager error propagation
        mock_cluster_manager = Mock()
        mock_cluster_manager.init_cluster = AsyncMock(
            side_effect=Exception("Cluster initialization failed")
        )
        manager._cluster_manager = mock_cluster_manager

        with pytest.raises(Exception, match="Cluster initialization failed"):
            await manager.init_cluster()

        # Test job manager error propagation
        mock_job_manager = Mock()
        mock_job_manager.submit_job = AsyncMock(
            return_value={"status": "error", "message": "Job submission failed"}
        )
        manager._job_manager = mock_job_manager

        result = await manager.submit_ray_job("python script.py")
        assert result["status"] == "error"
        assert "Job submission failed" in result["message"]


@pytest.mark.fast
class TestSystemInterfaces:
    """Test critical system interfaces and contracts."""

    @pytest.mark.asyncio
    async def test_mcp_server_startup_resilience(self):
        """Test that MCP server can handle startup edge cases."""
        # Test server startup when Ray is unavailable
        with patch("ray_mcp.main.RAY_AVAILABLE", False):
            with patch("ray_mcp.main.stdio_server") as mock_stdio:
                mock_read_stream = AsyncMock()
                mock_write_stream = AsyncMock()
                mock_stdio.return_value.__aenter__.return_value = (
                    mock_read_stream,
                    mock_write_stream,
                )

                with patch("ray_mcp.main.server.run", new_callable=AsyncMock):
                    # Should not raise SystemExit when Ray unavailable
                    from ray_mcp.main import main

                    await main()

    @pytest.mark.asyncio
    async def test_system_workflow_integration(self):
        """Test that core system workflows integrate properly."""
        manager = RayUnifiedManager()
        handlers = RayHandlers(manager)

        # Mock manager methods for workflow testing
        manager.init_cluster = AsyncMock(
            return_value={"status": "success", "cluster_address": "127.0.0.1:10001"}
        )

        # Mock methods for testing
        manager.create_kuberay_job = AsyncMock(
            return_value={"status": "success", "job_id": "job_123"}
        )
        manager.list_ray_jobs = AsyncMock(
            return_value={"status": "success", "jobs": [{"job_id": "job_123"}]}
        )

        # Test complete workflow: init -> submit -> list
        init_result = await handlers.handle_cluster(
            "Create a local Ray cluster with 2 CPUs"
        )
        assert init_result["status"] == "success"

        submit_result = await handlers.handle_job("Submit job from GitHub repo")
        assert submit_result["status"] == "success"

        list_result = await handlers.handle_job("List all running jobs")
        assert list_result["status"] == "success"

    def test_backward_compatibility_interface(self):
        """Test that unified manager maintains backward compatibility."""
        manager = RayUnifiedManager()

        # Test that all expected properties exist
        expected_properties = [
            "is_initialized",
            "cluster_address",
            "dashboard_url",
            "job_client",
        ]
        for prop in expected_properties:
            assert hasattr(manager, prop), f"Missing property: {prop}"

        # Test that all expected methods exist
        expected_methods = [
            "init_cluster",
            "stop_cluster",
            "inspect_ray_cluster",
            "submit_ray_job",
            "list_ray_jobs",
            "cancel_ray_job",
            "inspect_ray_job",
            "retrieve_logs",
        ]
        for method in expected_methods:
            assert hasattr(manager, method), f"Missing method: {method}"
            assert callable(getattr(manager, method)), f"Method {method} not callable"


@pytest.mark.fast
class TestFoundationComponents:
    """Test critical foundation components that support system operation."""

    def test_import_utilities_functionality(self):
        """Test that import utilities work correctly."""
        from ray_mcp.foundation.import_utils import (
            get_logging_utils,
            get_ray_imports,
            is_ray_available,
        )

        # Test logging utilities
        utils = get_logging_utils()
        assert "LoggingUtility" in utils
        assert "ResponseFormatter" in utils
        assert callable(utils["LoggingUtility"].log_info)

        # Test Ray imports
        imports = get_ray_imports()
        assert "ray" in imports
        assert "JobSubmissionClient" in imports
        assert "RAY_AVAILABLE" in imports
        assert isinstance(imports["RAY_AVAILABLE"], bool)

        # Test availability check
        ray_available = is_ray_available()
        assert isinstance(ray_available, bool)

    def test_base_manager_functionality(self):
        """Test that base managers provide expected functionality."""
        from ray_mcp.foundation.base_managers import BaseManager, ResourceManager

        # Test BaseManager
        state_manager = Mock()

        class TestManager(BaseManager):
            async def _validate_state(self) -> bool:
                return True

        manager = TestManager(state_manager)
        assert manager.state_manager == state_manager
        assert hasattr(manager, "_log_info")
        # Test response formatting through ResponseFormatter
        from ray_mcp.foundation.logging_utils import ResponseFormatter

        success_response = ResponseFormatter.format_success_response(result="test")
        assert isinstance(success_response, dict)
        assert success_response["status"] == "success"
        assert success_response["result"] == "test"

        error_response = ResponseFormatter.format_error_response(
            "operation", RuntimeError("test")
        )
        assert isinstance(error_response, dict)
        assert error_response["status"] == "error"
        assert "operation" in error_response["message"]

        # Test ResourceManager
        from ray_mcp.foundation.interfaces import ManagedComponent

        class TestResourceManager(ResourceManager, ManagedComponent):
            def __init__(self, state_manager, **kwargs):
                ResourceManager.__init__(self, state_manager, **kwargs)
                ManagedComponent.__init__(self, state_manager)

        resource_manager = TestResourceManager(
            state_manager, enable_ray=True, enable_kubernetes=False, enable_cloud=False
        )
        assert hasattr(resource_manager, "_ensure_ray_available")
        assert hasattr(
            resource_manager, "_ensure_ray_initialized"
        )  # Now in ManagedComponent

    def test_validation_and_utility_methods(self):
        """Test that validation and utility methods work correctly."""
        from ray_mcp.foundation.base_managers import BaseManager

        state_manager = Mock()
        state_manager.get_state.return_value = {"test_key": "test_value"}
        state_manager.is_initialized.return_value = True

        class TestManager(BaseManager):
            async def _validate_state(self) -> bool:
                return True

        manager = TestManager(state_manager)

        # Test job ID validation
        assert manager._validate_job_id("valid_job_id", "test") is None
        error_response = manager._validate_job_id("", "test")
        assert error_response is not None
        assert "job_id" in error_response.get("message", "")

        # Test state access
        assert manager._get_state() == {"test_key": "test_value"}
        assert manager._get_state_value("test_key") == "test_value"
        assert manager._get_state_value("missing_key", "default") == "default"
        assert manager._is_state_initialized() is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
