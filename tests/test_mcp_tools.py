#!/usr/bin/env python3
"""Comprehensive unit tests for all MCP tool calls in the Ray MCP server."""

import asyncio
import json
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any, List, cast, Union

# Import the main server components
from ray_mcp.main import call_tool, ray_manager
from ray_mcp.ray_manager import RayManager
from mcp.types import TextContent, Content


def get_text_content(result: Any, index: int = 0) -> TextContent:
    """Helper function to get TextContent from result with proper typing."""
    return cast(TextContent, result[index])


class TestMCPToolCalls:
    """Test cases for all MCP tool calls."""

    @pytest.fixture
    def mock_ray_manager(self):
        """Create a mock RayManager for testing."""
        manager = Mock(spec=RayManager)
        # Set up default return values for all methods
        manager.start_cluster = AsyncMock(return_value={"status": "started", "message": "Cluster started"})
        manager.stop_cluster = AsyncMock(return_value={"status": "stopped", "message": "Cluster stopped"})
        manager.get_cluster_status = AsyncMock(return_value={"status": "running", "message": "Cluster running"})
        manager.get_cluster_resources = AsyncMock(return_value={"status": "success", "resources": {}})
        manager.get_cluster_nodes = AsyncMock(return_value={"status": "success", "nodes": []})

        manager.submit_job = AsyncMock(return_value={"status": "submitted", "job_id": "test_job"})
        manager.list_jobs = AsyncMock(return_value={"status": "success", "jobs": []})
        manager.get_job_status = AsyncMock(return_value={"status": "success", "job_status": "RUNNING"})
        manager.cancel_job = AsyncMock(return_value={"status": "cancelled", "job_id": "test_job"})
        manager.monitor_job_progress = AsyncMock(return_value={"status": "success", "progress": "50%"})
        manager.debug_job = AsyncMock(return_value={"status": "success", "debug_info": {}})
        manager.list_actors = AsyncMock(return_value={"status": "success", "actors": []})
        manager.kill_actor = AsyncMock(return_value={"status": "killed", "actor_id": "test_actor"})

        manager.get_performance_metrics = AsyncMock(return_value={"status": "success", "metrics": {}})
        manager.cluster_health_check = AsyncMock(return_value={"status": "success", "health": "good"})
        manager.optimize_cluster_config = AsyncMock(return_value={"status": "success", "suggestions": []})

        manager.schedule_job = AsyncMock(return_value={"status": "job_scheduled", "schedule": "0 * * * *"})
        manager.get_logs = AsyncMock(return_value={"status": "success", "logs": "test logs"})
        manager.connect_cluster = AsyncMock(return_value={"status": "connected", "address": "ray://remote-cluster:10001", "message": "Successfully connected to Ray cluster"})
        return manager

    # ===== BASIC CLUSTER MANAGEMENT TESTS =====

    @pytest.mark.asyncio
    async def test_start_ray_tool(self, mock_ray_manager):
        """Test start_ray tool call."""
        with patch('ray_mcp.main.ray_manager', mock_ray_manager):
            with patch('ray_mcp.main.RAY_AVAILABLE', True):
                result = await call_tool("start_ray", {"num_cpus": 4, "num_gpus": 1})
                
                assert isinstance(result, list)
                assert len(result) == 1
                assert isinstance(result[0], TextContent)
                
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "started"
                
                mock_ray_manager.start_cluster.assert_called_once_with(num_cpus=4, num_gpus=1)

    @pytest.mark.asyncio
    async def test_stop_ray_tool(self, mock_ray_manager):
        """Test stop_ray tool call."""
        with patch('ray_mcp.main.ray_manager', mock_ray_manager):
            with patch('ray_mcp.main.RAY_AVAILABLE', True):
                result = await call_tool("stop_ray")
                
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "stopped"
                
                mock_ray_manager.stop_cluster.assert_called_once()

    @pytest.mark.asyncio
    async def test_cluster_status_tool(self, mock_ray_manager):
        """Test cluster_status tool call."""
        with patch('ray_mcp.main.ray_manager', mock_ray_manager):
            with patch('ray_mcp.main.RAY_AVAILABLE', True):
                result = await call_tool("cluster_status")
                
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "running"
                
                mock_ray_manager.get_cluster_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_cluster_resources_tool(self, mock_ray_manager):
        """Test cluster_resources tool call."""
        with patch('ray_mcp.main.ray_manager', mock_ray_manager):
            with patch('ray_mcp.main.RAY_AVAILABLE', True):
                result = await call_tool("cluster_resources")
                
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "success"
                
                mock_ray_manager.get_cluster_resources.assert_called_once()

    @pytest.mark.asyncio
    async def test_cluster_nodes_tool(self, mock_ray_manager):
        """Test cluster_nodes tool call."""
        with patch('ray_mcp.main.ray_manager', mock_ray_manager):
            with patch('ray_mcp.main.RAY_AVAILABLE', True):
                result = await call_tool("cluster_nodes")
                
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "success"
                
                mock_ray_manager.get_cluster_nodes.assert_called_once()



    # ===== JOB MANAGEMENT TESTS =====

    @pytest.mark.asyncio
    async def test_submit_job_tool(self, mock_ray_manager):
        """Test submit_job tool call."""
        with patch('ray_mcp.main.ray_manager', mock_ray_manager):
            with patch('ray_mcp.main.RAY_AVAILABLE', True):
                args = {
                    "entrypoint": "python my_script.py",
                    "runtime_env": {"pip": ["numpy"]},
                    "job_id": "my_job",
                    "metadata": {"owner": "test"}
                }
                result = await call_tool("submit_job", args)
                
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "submitted"
                
                mock_ray_manager.submit_job.assert_called_once_with(**args)

    @pytest.mark.asyncio
    async def test_list_jobs_tool(self, mock_ray_manager):
        """Test list_jobs tool call."""
        with patch('ray_mcp.main.ray_manager', mock_ray_manager):
            with patch('ray_mcp.main.RAY_AVAILABLE', True):
                result = await call_tool("list_jobs")
                
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "success"
                
                mock_ray_manager.list_jobs.assert_called_once()

    @pytest.mark.asyncio
    async def test_job_status_tool(self, mock_ray_manager):
        """Test job_status tool call."""
        with patch('ray_mcp.main.ray_manager', mock_ray_manager):
            with patch('ray_mcp.main.RAY_AVAILABLE', True):
                result = await call_tool("job_status", {"job_id": "test_job_123"})
                
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "success"
                
                mock_ray_manager.get_job_status.assert_called_once_with("test_job_123")

    @pytest.mark.asyncio
    async def test_cancel_job_tool(self, mock_ray_manager):
        """Test cancel_job tool call."""
        with patch('ray_mcp.main.ray_manager', mock_ray_manager):
            with patch('ray_mcp.main.RAY_AVAILABLE', True):
                result = await call_tool("cancel_job", {"job_id": "test_job_123"})
                
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "cancelled"
                
                mock_ray_manager.cancel_job.assert_called_once_with("test_job_123")

    @pytest.mark.asyncio
    async def test_monitor_job_tool(self, mock_ray_manager):
        """Test monitor_job tool call."""
        with patch('ray_mcp.main.ray_manager', mock_ray_manager):
            with patch('ray_mcp.main.RAY_AVAILABLE', True):
                result = await call_tool("monitor_job", {"job_id": "test_job_123"})
                
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "success"
                
                mock_ray_manager.monitor_job_progress.assert_called_once_with("test_job_123")

    @pytest.mark.asyncio
    async def test_debug_job_tool(self, mock_ray_manager):
        """Test debug_job tool call."""
        with patch('ray_mcp.main.ray_manager', mock_ray_manager):
            with patch('ray_mcp.main.RAY_AVAILABLE', True):
                result = await call_tool("debug_job", {"job_id": "test_job_123"})
                
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "success"
                
                mock_ray_manager.debug_job.assert_called_once_with("test_job_123")

    # ===== ACTOR MANAGEMENT TESTS =====

    @pytest.mark.asyncio
    async def test_list_actors_tool(self, mock_ray_manager):
        """Test list_actors tool call."""
        with patch('ray_mcp.main.ray_manager', mock_ray_manager):
            with patch('ray_mcp.main.RAY_AVAILABLE', True):
                filters = {"namespace": "test"}
                result = await call_tool("list_actors", {"filters": filters})
                
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "success"
                
                mock_ray_manager.list_actors.assert_called_once_with(filters)

    @pytest.mark.asyncio
    async def test_kill_actor_tool(self, mock_ray_manager):
        """Test kill_actor tool call."""
        with patch('ray_mcp.main.ray_manager', mock_ray_manager):
            with patch('ray_mcp.main.RAY_AVAILABLE', True):
                result = await call_tool("kill_actor", {"actor_id": "test_actor_123", "no_restart": True})
                
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "killed"
                
                mock_ray_manager.kill_actor.assert_called_once_with("test_actor_123", True)



    # ===== ENHANCED MONITORING TESTS =====

    @pytest.mark.asyncio
    async def test_performance_metrics_tool(self, mock_ray_manager):
        """Test performance_metrics tool call."""
        with patch('ray_mcp.main.ray_manager', mock_ray_manager):
            with patch('ray_mcp.main.RAY_AVAILABLE', True):
                result = await call_tool("performance_metrics")
                
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "success"
                
                mock_ray_manager.get_performance_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_tool(self, mock_ray_manager):
        """Test health_check tool call."""
        with patch('ray_mcp.main.ray_manager', mock_ray_manager):
            with patch('ray_mcp.main.RAY_AVAILABLE', True):
                result = await call_tool("health_check")
                
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "success"
                
                mock_ray_manager.cluster_health_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_optimize_config_tool(self, mock_ray_manager):
        """Test optimize_config tool call."""
        with patch('ray_mcp.main.ray_manager', mock_ray_manager):
            with patch('ray_mcp.main.RAY_AVAILABLE', True):
                result = await call_tool("optimize_config")
                
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "success"
                
                mock_ray_manager.optimize_cluster_config.assert_called_once()

    # ===== WORKFLOW & ORCHESTRATION TESTS =====



    @pytest.mark.asyncio
    async def test_schedule_job_tool(self, mock_ray_manager):
        """Test schedule_job tool call."""
        with patch('ray_mcp.main.ray_manager', mock_ray_manager):
            with patch('ray_mcp.main.RAY_AVAILABLE', True):
                args = {
                    "entrypoint": "python daily_job.py",
                    "schedule": "0 2 * * *"  # Daily at 2 AM
                }
                result = await call_tool("schedule_job", args)
                
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "job_scheduled"
                
                mock_ray_manager.schedule_job.assert_called_once_with(**args)



    # ===== LOGS & DEBUGGING TESTS =====

    @pytest.mark.asyncio
    async def test_get_logs_tool(self, mock_ray_manager):
        """Test get_logs tool call."""
        with patch('ray_mcp.main.ray_manager', mock_ray_manager):
            with patch('ray_mcp.main.RAY_AVAILABLE', True):
                args = {
                    "job_id": "test_job_123",
                    "num_lines": 50
                }
                result = await call_tool("get_logs", args)
                
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "success"
                
                mock_ray_manager.get_logs.assert_called_once_with(**args)

    # ===== ERROR HANDLING TESTS =====

    @pytest.mark.asyncio
    async def test_ray_not_available(self):
        """Test tool calls when Ray is not available."""
        with patch('ray_mcp.main.RAY_AVAILABLE', False):
            result = await call_tool("start_ray")
            
            response_text = get_text_content(result).text
            assert "Ray is not available" in response_text

    @pytest.mark.asyncio
    async def test_unknown_tool(self, mock_ray_manager):
        """Test calling an unknown tool."""
        with patch('ray_mcp.main.ray_manager', mock_ray_manager):
            with patch('ray_mcp.main.RAY_AVAILABLE', True):
                result = await call_tool("unknown_tool")
                
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "error"
                assert "Unknown tool" in response_data["message"]

    @pytest.mark.asyncio
    async def test_tool_exception(self, mock_ray_manager):
        """Test tool call with exception in ray_manager."""
        # Make the ray_manager method raise an exception
        mock_ray_manager.start_cluster.side_effect = Exception("Test exception")
        
        with patch('ray_mcp.main.ray_manager', mock_ray_manager):
            with patch('ray_mcp.main.RAY_AVAILABLE', True):
                result = await call_tool("start_ray")
                
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "error"
                assert "Test exception" in response_data["message"]

    @pytest.mark.asyncio
    async def test_missing_required_arguments(self, mock_ray_manager):
        """Test tool calls with missing required arguments."""
        with patch('ray_mcp.main.ray_manager', mock_ray_manager):
            with patch('ray_mcp.main.RAY_AVAILABLE', True):
                # This should raise a KeyError for missing job_id
                result = await call_tool("job_status", {})
                
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "error"

    @pytest.mark.asyncio
    async def test_optional_arguments_handling(self, mock_ray_manager):
        """Test tool calls with optional arguments."""
        with patch('ray_mcp.main.ray_manager', mock_ray_manager):
            with patch('ray_mcp.main.RAY_AVAILABLE', True):
                # Test list_actors without filters (optional)
                result = await call_tool("list_actors")
                
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "success"
                
                mock_ray_manager.list_actors.assert_called_once_with(None)

    # ===== PARAMETER VALIDATION TESTS =====



    @pytest.mark.asyncio
    async def test_kill_actor_default_no_restart(self, mock_ray_manager):
        """Test kill_actor with default no_restart value."""
        with patch('ray_mcp.main.ray_manager', mock_ray_manager):
            with patch('ray_mcp.main.RAY_AVAILABLE', True):
                # Call without no_restart argument
                result = await call_tool("kill_actor", {"actor_id": "test_actor"})
                
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "killed"
                
                # Should use default value of False
                mock_ray_manager.kill_actor.assert_called_once_with("test_actor", False)

    @pytest.mark.asyncio
    async def test_connect_ray_tool(self, mock_ray_manager):
        """Test connect_ray tool call."""
        with patch('ray_mcp.main.ray_manager', mock_ray_manager):
            with patch('ray_mcp.main.RAY_AVAILABLE', True):
                result = await call_tool("connect_ray", {"address": "ray://remote-cluster:10001"})
                
                assert isinstance(result, list)
                assert len(result) == 1
                assert isinstance(result[0], TextContent)
                
                response_data = json.loads(get_text_content(result).text)
                assert response_data["status"] == "connected"
                assert response_data["address"] == "ray://remote-cluster:10001"
                
                mock_ray_manager.connect_cluster.assert_called_once_with(address="ray://remote-cluster:10001")


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 