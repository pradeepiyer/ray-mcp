#!/usr/bin/env python3
"""Comprehensive unit tests for ray_mcp/tools.py functions."""

import asyncio
import json
import pytest
import warnings
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any, Optional

# Suppress the specific coroutine warning at module level
warnings.filterwarnings("ignore", message="coroutine 'main' was never awaited", category=RuntimeWarning)

from ray_mcp.tools import (
    # Basic cluster management
    start_ray_cluster,
    connect_ray_cluster, 
    stop_ray_cluster,
    get_cluster_status,
    get_cluster_resources,
    get_cluster_nodes,
    
    # Job management
    submit_job,
    list_jobs,
    get_job_status,
    cancel_job,
    monitor_job_progress,
    debug_job,
    
    # Actor management
    list_actors,
    kill_actor,
    
    # Enhanced monitoring
    get_performance_metrics,
    cluster_health_check,
    optimize_cluster_config,
    
    # Workflow & orchestration
    schedule_job,
    
    # Logs & debugging
    get_logs
)
from ray_mcp.ray_manager import RayManager


# Mock the main function to prevent coroutine warnings
@pytest.fixture(scope="session", autouse=True)
def mock_main_function():
    """Mock the main function to prevent unawaited coroutine warnings."""
    # Simple mock that doesn't create coroutines
    with patch('ray_mcp.main.main', new_callable=AsyncMock) as mock_main:
        yield mock_main


class TestToolFunctions:
    """Test cases for all tool functions in tools.py."""

    @pytest.fixture
    def mock_ray_manager(self):
        """Create a mock RayManager for testing."""
        manager = Mock(spec=RayManager)
        return manager

    # ===== BASIC CLUSTER MANAGEMENT TESTS =====

    @pytest.mark.asyncio
    async def test_start_ray_cluster_with_defaults(self, mock_ray_manager):
        """Test start_ray_cluster with default parameters."""
        expected_result = {"status": "started", "message": "Cluster started successfully"}
        mock_ray_manager.start_cluster = AsyncMock(return_value=expected_result)
        
        result = await start_ray_cluster(mock_ray_manager)
        
        # Verify the result is properly JSON formatted
        result_data = json.loads(result)
        assert result_data == expected_result
        
        # Verify correct call to ray_manager
        mock_ray_manager.start_cluster.assert_called_once_with(
            head_node=True,
            address=None,
            num_cpus=None,
            num_gpus=None,
            object_store_memory=None
        )

    @pytest.mark.asyncio
    async def test_start_ray_cluster_with_parameters(self, mock_ray_manager):
        """Test start_ray_cluster with custom parameters."""
        expected_result = {"status": "started", "address": "ray://127.0.0.1:10001"}
        mock_ray_manager.start_cluster = AsyncMock(return_value=expected_result)
        
        result = await start_ray_cluster(
            mock_ray_manager,
            head_node=False,
            address="ray://remote:10001",
            num_cpus=8,
            num_gpus=2,
            object_store_memory=1000000000,
            custom_param="test"
        )
        
        result_data = json.loads(result)
        assert result_data == expected_result
        
        mock_ray_manager.start_cluster.assert_called_once_with(
            head_node=False,
            address="ray://remote:10001",
            num_cpus=8,
            num_gpus=2,
            object_store_memory=1000000000,
            custom_param="test"
        )

    @pytest.mark.asyncio
    async def test_connect_ray_cluster(self, mock_ray_manager):
        """Test connect_ray_cluster function."""
        expected_result = {"status": "connected", "address": "ray://remote:10001"}
        mock_ray_manager.connect_cluster = AsyncMock(return_value=expected_result)
        
        result = await connect_ray_cluster(
            mock_ray_manager,
            address="ray://remote:10001",
            custom_arg="test"
        )
        
        result_data = json.loads(result)
        assert result_data == expected_result
        
        mock_ray_manager.connect_cluster.assert_called_once_with(
            address="ray://remote:10001",
            custom_arg="test"
        )

    @pytest.mark.asyncio
    async def test_submit_job_minimal(self, mock_ray_manager):
        """Test submit_job with minimal parameters."""
        expected_result = {"status": "submitted", "job_id": "job_123"}
        mock_ray_manager.submit_job = AsyncMock(return_value=expected_result)
        
        result = await submit_job(mock_ray_manager, "python test.py")
        
        result_data = json.loads(result)
        assert result_data == expected_result
        
        mock_ray_manager.submit_job.assert_called_once_with(
            entrypoint="python test.py",
            runtime_env=None,
            job_id=None,
            metadata=None
        )

    @pytest.mark.asyncio
    async def test_list_actors_no_filters(self, mock_ray_manager):
        """Test list_actors without filters."""
        expected_result = {
            "status": "success",
            "actors": [
                {"actor_id": "actor1", "state": "ALIVE"},
                {"actor_id": "actor2", "state": "DEAD"}
            ]
        }
        mock_ray_manager.list_actors = AsyncMock(return_value=expected_result)
        
        result = await list_actors(mock_ray_manager)
        
        result_data = json.loads(result)
        assert result_data == expected_result
        
        mock_ray_manager.list_actors.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_get_logs_job_only(self, mock_ray_manager):
        """Test get_logs for a specific job."""
        expected_result = {
            "status": "success",
            "logs": "Job output:\\nTraining started...\\nEpoch 1 completed...",
            "num_lines": 100
        }
        mock_ray_manager.get_logs = AsyncMock(return_value=expected_result)
        
        result = await get_logs(mock_ray_manager, job_id="job_123")
        
        result_data = json.loads(result)
        assert result_data == expected_result
        
        mock_ray_manager.get_logs.assert_called_once_with(
            job_id="job_123",
            actor_id=None,
            node_id=None,
            num_lines=100
        )

    @pytest.mark.asyncio
    async def test_stop_ray_cluster(self, mock_ray_manager):
        """Test stop_ray_cluster function."""
        expected_result = {"status": "stopped", "message": "Cluster stopped"}
        mock_ray_manager.stop_cluster = AsyncMock(return_value=expected_result)
        
        result = await stop_ray_cluster(mock_ray_manager)
        
        result_data = json.loads(result)
        assert result_data == expected_result
        
        mock_ray_manager.stop_cluster.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cluster_status(self, mock_ray_manager):
        """Test get_cluster_status function."""
        expected_result = {
            "status": "running",
            "nodes": 3,
            "alive_nodes": 3,
            "cluster_resources": {"CPU": 12, "memory": 32000000000}
        }
        mock_ray_manager.get_cluster_status = AsyncMock(return_value=expected_result)
        
        result = await get_cluster_status(mock_ray_manager)
        
        result_data = json.loads(result)
        assert result_data == expected_result
        
        mock_ray_manager.get_cluster_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cluster_resources(self, mock_ray_manager):
        """Test get_cluster_resources function."""
        expected_result = {
            "status": "success",
            "total_resources": {"CPU": 12, "memory": 32000000000},
            "available_resources": {"CPU": 8, "memory": 16000000000}
        }
        mock_ray_manager.get_cluster_resources = AsyncMock(return_value=expected_result)
        
        result = await get_cluster_resources(mock_ray_manager)
        
        result_data = json.loads(result)
        assert result_data == expected_result
        
        mock_ray_manager.get_cluster_resources.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cluster_nodes(self, mock_ray_manager):
        """Test get_cluster_nodes function."""
        expected_result = {
            "status": "success",
            "nodes": [
                {"node_id": "node1", "alive": True, "resources": {"CPU": 4}},
                {"node_id": "node2", "alive": True, "resources": {"CPU": 8}}
            ]
        }
        mock_ray_manager.get_cluster_nodes = AsyncMock(return_value=expected_result)
        
        result = await get_cluster_nodes(mock_ray_manager)
        
        result_data = json.loads(result)
        assert result_data == expected_result
        
        mock_ray_manager.get_cluster_nodes.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_jobs(self, mock_ray_manager):
        """Test list_jobs function."""
        expected_result = {
            "status": "success",
            "jobs": [
                {"job_id": "job1", "status": "RUNNING"},
                {"job_id": "job2", "status": "SUCCEEDED"}
            ]
        }
        mock_ray_manager.list_jobs = AsyncMock(return_value=expected_result)
        
        result = await list_jobs(mock_ray_manager)
        
        result_data = json.loads(result)
        assert result_data == expected_result
        
        mock_ray_manager.list_jobs.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_job_status(self, mock_ray_manager):
        """Test get_job_status function."""
        expected_result = {
            "status": "success",
            "job_id": "job_123",
            "job_status": "RUNNING"
        }
        mock_ray_manager.get_job_status = AsyncMock(return_value=expected_result)
        
        result = await get_job_status(mock_ray_manager, "job_123")
        
        result_data = json.loads(result)
        assert result_data == expected_result
        
        mock_ray_manager.get_job_status.assert_called_once_with("job_123")

    @pytest.mark.asyncio
    async def test_cancel_job(self, mock_ray_manager):
        """Test cancel_job function."""
        expected_result = {"status": "cancelled", "job_id": "job_123"}
        mock_ray_manager.cancel_job = AsyncMock(return_value=expected_result)
        
        result = await cancel_job(mock_ray_manager, "job_123")
        
        result_data = json.loads(result)
        assert result_data == expected_result
        
        mock_ray_manager.cancel_job.assert_called_once_with("job_123")

    @pytest.mark.asyncio
    async def test_monitor_job_progress(self, mock_ray_manager):
        """Test monitor_job_progress function."""
        expected_result = {
            "status": "success",
            "job_id": "job_123",
            "progress": "75%"
        }
        mock_ray_manager.monitor_job_progress = AsyncMock(return_value=expected_result)
        
        result = await monitor_job_progress(mock_ray_manager, "job_123")
        
        result_data = json.loads(result)
        assert result_data == expected_result
        
        mock_ray_manager.monitor_job_progress.assert_called_once_with("job_123")

    @pytest.mark.asyncio
    async def test_debug_job(self, mock_ray_manager):
        """Test debug_job function."""
        expected_result = {
            "status": "success",
            "job_id": "job_123",
            "debug_info": {"errors": [], "warnings": []}
        }
        mock_ray_manager.debug_job = AsyncMock(return_value=expected_result)
        
        result = await debug_job(mock_ray_manager, "job_123")
        
        result_data = json.loads(result)
        assert result_data == expected_result
        
        mock_ray_manager.debug_job.assert_called_once_with("job_123")

    @pytest.mark.asyncio
    async def test_kill_actor(self, mock_ray_manager):
        """Test kill_actor function."""
        expected_result = {"status": "killed", "actor_id": "actor_123"}
        mock_ray_manager.kill_actor = AsyncMock(return_value=expected_result)
        
        result = await kill_actor(mock_ray_manager, "actor_123", no_restart=True)
        
        result_data = json.loads(result)
        assert result_data == expected_result
        
        mock_ray_manager.kill_actor.assert_called_once_with("actor_123", True)

    @pytest.mark.asyncio
    async def test_get_performance_metrics(self, mock_ray_manager):
        """Test get_performance_metrics function."""
        expected_result = {
            "status": "success",
            "metrics": {"cpu_utilization": 0.75, "memory_utilization": 0.60}
        }
        mock_ray_manager.get_performance_metrics = AsyncMock(return_value=expected_result)
        
        result = await get_performance_metrics(mock_ray_manager)
        
        result_data = json.loads(result)
        assert result_data == expected_result
        
        mock_ray_manager.get_performance_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_cluster_health_check(self, mock_ray_manager):
        """Test cluster_health_check function."""
        expected_result = {
            "status": "success",
            "health": "good",
            "issues": []
        }
        mock_ray_manager.cluster_health_check = AsyncMock(return_value=expected_result)
        
        result = await cluster_health_check(mock_ray_manager)
        
        result_data = json.loads(result)
        assert result_data == expected_result
        
        mock_ray_manager.cluster_health_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_optimize_cluster_config(self, mock_ray_manager):
        """Test optimize_cluster_config function."""
        expected_result = {
            "status": "success",
            "suggestions": ["Optimize node allocation"]
        }
        mock_ray_manager.optimize_cluster_config = AsyncMock(return_value=expected_result)
        
        result = await optimize_cluster_config(mock_ray_manager)
        
        result_data = json.loads(result)
        assert result_data == expected_result
        
        mock_ray_manager.optimize_cluster_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_job(self, mock_ray_manager):
        """Test schedule_job function."""
        expected_result = {
            "status": "job_scheduled",
            "schedule": "0 * * * *",
            "entrypoint": "python hourly_task.py"
        }
        mock_ray_manager.schedule_job = AsyncMock(return_value=expected_result)
        
        result = await schedule_job(
            mock_ray_manager,
            "python hourly_task.py",
            "0 * * * *"
        )
        
        result_data = json.loads(result)
        assert result_data == expected_result
        
        mock_ray_manager.schedule_job.assert_called_once_with(
            entrypoint="python hourly_task.py",
            schedule="0 * * * *"
        )

    @pytest.mark.asyncio
    async def test_get_logs_with_parameters(self, mock_ray_manager):
        """Test get_logs with various parameters."""
        expected_result = {
            "status": "success",
            "logs": "Log content here",
            "num_lines": 50
        }
        mock_ray_manager.get_logs = AsyncMock(return_value=expected_result)
        
        result = await get_logs(
            mock_ray_manager,
            job_id="job_123",
            actor_id="actor_456",
            node_id="node_789",
            num_lines=50
        )
        
        result_data = json.loads(result)
        assert result_data == expected_result
        
        mock_ray_manager.get_logs.assert_called_once_with(
            job_id="job_123",
            actor_id="actor_456",
            node_id="node_789",
            num_lines=50
        )

    @pytest.mark.asyncio
    async def test_json_formatting_indentation(self, mock_ray_manager):
        """Test that all functions return properly indented JSON."""
        complex_result = {
            "status": "success",
            "nested_data": {
                "level1": {"level2": {"level3": "value"}},
                "array": [1, 2, 3]
            }
        }
        mock_ray_manager.get_cluster_status = AsyncMock(return_value=complex_result)
        
        result = await get_cluster_status(mock_ray_manager)
        
        # Verify the JSON is properly indented (indent=2)
        expected_json = json.dumps(complex_result, indent=2)
        assert result == expected_json
        
        # Verify it can be parsed back
        parsed_result = json.loads(result)
        assert parsed_result == complex_result


if __name__ == "__main__":
    pytest.main([__file__])
