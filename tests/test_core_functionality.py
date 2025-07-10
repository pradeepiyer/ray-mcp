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

from ray_mcp.managers.unified_manager import RayUnifiedManager
from ray_mcp.tool_registry import ToolRegistry


@pytest.mark.fast
class TestToolRegistry:
    """Test tool registry core functionality and MCP integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_ray_manager = Mock()
        self.registry = ToolRegistry(self.mock_ray_manager)

    def test_tool_registry_initialization_and_structure(self):
        """Test that tool registry initializes correctly with proper structure."""
        # Test basic initialization
        assert self.registry.ray_manager == self.mock_ray_manager
        assert len(self.registry._tools) > 0

        # Test tool discovery
        tools = self.registry.get_tool_list()
        assert len(tools) > 0

        # Test tool handler access
        handler = self.registry.get_tool_handler("init_ray_cluster")
        assert handler is not None
        assert callable(handler)

        # Test unknown tool handling
        handler = self.registry.get_tool_handler("unknown_tool")
        assert handler is None

    def test_mcp_schema_validation(self):
        """Test that all tools have valid MCP schemas."""
        tools = self.registry.get_tool_list()

        # Core tools that must be present
        expected_tools = [
            "init_ray_cluster",
            "stop_ray_cluster",
            "inspect_ray_cluster",
            "submit_ray_job",
            "list_ray_jobs",
            "inspect_ray_job",
            "cancel_ray_job",
            "retrieve_logs",
        ]

        tool_names = [tool.name for tool in tools]
        for expected_tool in expected_tools:
            assert (
                expected_tool in tool_names
            ), f"Missing critical tool: {expected_tool}"

        # Validate MCP schema structure
        for tool in tools:
            assert hasattr(tool, "inputSchema")
            assert isinstance(tool.inputSchema, dict)
            assert tool.inputSchema["type"] == "object"
            assert hasattr(tool, "name")
            assert hasattr(tool, "description")

    @pytest.mark.asyncio
    async def test_tool_execution_workflow(self):
        """Test complete tool execution workflow including error handling."""
        # Test unknown tool handling
        result = await self.registry.execute_tool("unknown_tool", {})
        assert result["status"] == "error"
        assert "Unknown tool" in result["message"]

        # Test successful tool execution
        self.mock_ray_manager.init_cluster = AsyncMock(
            return_value={
                "status": "success",
                "result_type": "connected",
                "cluster_address": "127.0.0.1:10001",
            }
        )

        result = await self.registry.execute_tool("init_ray_cluster", {"num_cpus": 4})
        assert result["status"] == "success"
        assert result.get("result_type") == "connected"
        self.mock_ray_manager.init_cluster.assert_called_once()

        # Test exception handling in tool execution
        self.mock_ray_manager.init_cluster = AsyncMock(
            side_effect=Exception("Test error")
        )
        result = await self.registry.execute_tool("init_ray_cluster", {})
        assert result["status"] == "error"
        assert "Test error" in result["message"]

    def test_tool_extensions_and_unified_functionality(self):
        """Test that tool extensions for KubeRay are properly integrated."""
        tools = self.registry.get_tool_list()
        tool_names = self.registry.list_tool_names()

        # Test unified tools are present
        unified_tools = ["list_ray_clusters", "scale_ray_cluster"]
        for tool_name in unified_tools:
            assert tool_name in tool_names

        # Test init_ray_cluster has KubeRay extensions
        init_tool = next(tool for tool in tools if tool.name == "init_ray_cluster")
        properties = init_tool.inputSchema["properties"]

        assert "cluster_type" in properties
        assert "kubernetes_config" in properties
        assert properties["cluster_type"]["enum"] == ["local", "kubernetes", "k8s"]

        # Test submit_ray_job has KubeRay extensions
        submit_tool = next(tool for tool in tools if tool.name == "submit_ray_job")
        properties = submit_tool.inputSchema["properties"]

        assert "job_type" in properties
        assert "kubernetes_config" in properties
        assert properties["job_type"]["enum"] == ["local", "kubernetes", "k8s", "auto"]

    @pytest.mark.asyncio
    async def test_kuberay_integration_behavior(self):
        """Test KubeRay integration behavior through tool registry."""
        # Mock manager for KubeRay functionality
        manager = Mock(spec=RayUnifiedManager)
        manager.is_initialized = False
        manager.is_kubernetes_connected = False
        manager.kuberay_clusters = {}
        manager.kuberay_jobs = {}
        manager.init_cluster = AsyncMock(return_value={"status": "success"})
        manager.create_kuberay_cluster = AsyncMock(return_value={"status": "success"})
        manager.create_kuberay_job = AsyncMock(return_value={"status": "success"})

        registry = ToolRegistry(manager)

        # Test local cluster initialization
        result = await registry.execute_tool(
            "init_ray_cluster", {"cluster_type": "local", "num_cpus": 4}
        )
        manager.init_cluster.assert_called_once_with(num_cpus=4)
        assert result["status"] == "success"

        # Test KubeRay cluster creation
        result = await registry.execute_tool(
            "init_ray_cluster",
            {
                "cluster_type": "kubernetes",
                "kubernetes_config": {"namespace": "ray-system"},
                "num_cpus": 4,
            },
        )
        manager.create_kuberay_cluster.assert_called_once()
        assert result["status"] == "success"

        # Test KubeRay job submission
        result = await registry.execute_tool(
            "submit_ray_job",
            {
                "entrypoint": "python script.py",
                "job_type": "kubernetes",
                "kubernetes_config": {"namespace": "ray-system"},
            },
        )
        manager.create_kuberay_job.assert_called_once()
        assert result["status"] == "success"


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
        registry = ToolRegistry(manager)

        # Mock manager methods for workflow testing
        manager.init_cluster = AsyncMock(
            return_value={"status": "success", "cluster_address": "127.0.0.1:10001"}
        )

        # Create a proper async mock for submit_ray_job with signature inspection support
        async def mock_submit_ray_job(
            entrypoint, runtime_env=None, job_id=None, metadata=None, **kwargs
        ):
            return {"status": "success", "job_id": "job_123"}

        manager.submit_ray_job = mock_submit_ray_job

        # Mock the actual method that list_ray_jobs tool calls
        manager._job_manager = Mock()
        manager._job_manager.list_jobs = AsyncMock(
            return_value={"status": "success", "jobs": [{"job_id": "job_123"}]}
        )

        # Test complete workflow: init -> submit -> list
        init_result = await registry.execute_tool("init_ray_cluster", {"num_cpus": 2})
        assert init_result["status"] == "success"

        submit_result = await registry.execute_tool(
            "submit_ray_job", {"entrypoint": "python script.py"}
        )
        assert submit_result["status"] == "success"

        list_result = await registry.execute_tool("list_ray_jobs", {})
        assert list_result["status"] == "success"
        assert len(list_result["jobs"]) > 0

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
            pass

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
            pass

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
