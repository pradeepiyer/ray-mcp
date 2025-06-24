#!/usr/bin/env python3
"""Comprehensive unit tests for RayManager methods with detailed scenarios."""

import asyncio
import json
import pytest
import sys
import tempfile
import os
from unittest.mock import Mock, patch, AsyncMock, MagicMock, mock_open
from typing import Dict, Any, List

from ray_mcp.ray_manager import RayManager


class TestRayManagerMethods:
    """Detailed test cases for RayManager methods."""

    @pytest.fixture
    def ray_manager(self):
        """Create a RayManager instance for testing."""
        return RayManager()

    @pytest.fixture
    def mock_ray_context(self):
        """Create a mock Ray context."""
        context = Mock()
        context.address_info = {
            "address": "ray://127.0.0.1:10001",
            "dashboard_url": "http://127.0.0.1:8265",
            "node_id": "test_node_id",
            "session_name": "test_session"
        }
        context.dashboard_url = "http://127.0.0.1:8265"
        context.session_name = "test_session"
        return context

    @pytest.fixture
    def mock_job_client(self):
        """Create a mock JobSubmissionClient."""
        client = Mock()
        client.submit_job.return_value = "job_123"
        client.list_jobs.return_value = []
        client.get_job_info.return_value = Mock(
            job_id="job_123",
            status="RUNNING",
            entrypoint="python test.py",
            start_time=1234567890,
            end_time=None,
            metadata={},
            runtime_env={},
            message=""
        )
        client.stop_job.return_value = True
        client.get_job_logs.return_value = "test log output"
        return client

    # ===== CLUSTER MANAGEMENT TESTS =====

    @pytest.mark.asyncio
    async def test_start_cluster_success(self, ray_manager, mock_ray_context):
        """Test successful cluster start."""
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                with patch('ray_mcp.ray_manager.JobSubmissionClient') as mock_client:
                    mock_ray.init.return_value = mock_ray_context
                    mock_ray.get_runtime_context.return_value.get_node_id.return_value = "node_123"
                    
                    result = await ray_manager.start_cluster(num_cpus=4, num_gpus=1)
                    
                    assert result["status"] == "started"
                    assert result["address"] == "ray://127.0.0.1:10001"
                    assert ray_manager._is_initialized
                    mock_ray.init.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_cluster_ray_not_available(self, ray_manager):
        """Test cluster start when Ray is not available."""
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', False):
            result = await ray_manager.start_cluster()
            
            assert result["status"] == "error"
            assert "Ray is not available" in result["message"]

    @pytest.mark.asyncio
    async def test_start_cluster_with_address(self, ray_manager, mock_ray_context):
        """Test connecting to existing cluster with address."""
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                with patch('ray_mcp.ray_manager.JobSubmissionClient'):
                    mock_ray.init.return_value = mock_ray_context
                    
                    result = await ray_manager.start_cluster(address="ray://remote:10001")
                    
                    assert result["status"] == "started"
                    mock_ray.init.assert_called_once()
                    args = mock_ray.init.call_args[1]
                    assert args["address"] == "ray://remote:10001"

    @pytest.mark.asyncio
    async def test_stop_cluster_success(self, ray_manager):
        """Test successful cluster stop."""
        ray_manager._is_initialized = True
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                
                result = await ray_manager.stop_cluster()
                
                assert result["status"] == "stopped"
                assert not ray_manager._is_initialized
                mock_ray.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_cluster_not_running(self, ray_manager):
        """Test stop cluster when not running."""
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = False
                
                result = await ray_manager.stop_cluster()
                
                assert result["status"] == "not_running"

    @pytest.mark.asyncio
    async def test_get_cluster_status_detailed(self, ray_manager):
        """Test get cluster status with detailed information."""
        ray_manager._is_initialized = True
        ray_manager._cluster_address = "ray://127.0.0.1:10001"
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.cluster_resources.return_value = {"CPU": 8, "memory": 16000000000}
                mock_ray.available_resources.return_value = {"CPU": 4, "memory": 8000000000}
                mock_ray.nodes.return_value = [
                    {"NodeID": "node1", "Alive": True},
                    {"NodeID": "node2", "Alive": True},
                    {"NodeID": "node3", "Alive": False}
                ]
                
                result = await ray_manager.get_cluster_status()
                
                assert result["status"] == "running"
                assert result["nodes"] == 3
                assert result["alive_nodes"] == 2
                assert result["cluster_resources"]["CPU"] == 8

    # ===== JOB MANAGEMENT TESTS =====

    @pytest.mark.asyncio
    async def test_submit_job_with_all_params(self, ray_manager, mock_job_client):
        """Test job submission with all parameters."""
        ray_manager._is_initialized = True
        ray_manager._job_client = mock_job_client
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                
                result = await ray_manager.submit_job(
                    entrypoint="python my_script.py",
                    runtime_env={"pip": ["requests", "click"]},
                    job_id="my_custom_job",
                    metadata={"owner": "test_user", "project": "ml_project"}
                )
                
                assert result["status"] == "submitted"
                assert result["job_id"] == "job_123"
                mock_job_client.submit_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_job_no_client(self, ray_manager):
        """Test job submission when job client is not available."""
        ray_manager._is_initialized = True
        ray_manager._job_client = None
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                
                result = await ray_manager.submit_job("python test.py")
                
                assert result["status"] == "error"
                assert "Job submission client not available" in result["message"]

    @pytest.mark.asyncio
    async def test_list_jobs_with_details(self, ray_manager, mock_job_client):
        """Test listing jobs with detailed information."""
        ray_manager._is_initialized = True
        ray_manager._job_client = mock_job_client
        
        # Mock job details
        job1 = Mock()
        job1.job_id = "job_1"
        job1.status = "RUNNING"
        job1.entrypoint = "python train.py"
        job1.start_time = 1234567890
        job1.end_time = None
        job1.metadata = {"owner": "user1"}
        job1.runtime_env = {"pip": ["requests"]}
        
        job2 = Mock()
        job2.job_id = "job_2"
        job2.status = "SUCCEEDED"
        job2.entrypoint = "python inference.py"
        job2.start_time = 1234567800
        job2.end_time = 1234567900
        job2.metadata = {}
        job2.runtime_env = {}
        
        mock_job_client.list_jobs.return_value = [job1, job2]
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                
                result = await ray_manager.list_jobs()
                
                assert result["status"] == "success"
                assert len(result["jobs"]) == 2
                assert result["jobs"][0]["job_id"] == "job_1"
                assert result["jobs"][1]["status"] == "SUCCEEDED"

    @pytest.mark.asyncio
    async def test_cancel_job_success(self, ray_manager, mock_job_client):
        """Test successful job cancellation."""
        ray_manager._is_initialized = True
        ray_manager._job_client = mock_job_client
        mock_job_client.stop_job.return_value = True
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                
                result = await ray_manager.cancel_job("job_123")
                
                assert result["status"] == "cancelled"
                assert result["job_id"] == "job_123"
                mock_job_client.stop_job.assert_called_once_with("job_123")

    @pytest.mark.asyncio
    async def test_cancel_job_failure(self, ray_manager, mock_job_client):
        """Test job cancellation failure."""
        ray_manager._is_initialized = True
        ray_manager._job_client = mock_job_client
        mock_job_client.stop_job.return_value = False
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                
                result = await ray_manager.cancel_job("job_123")
                
                assert result["status"] == "error"
                assert "Failed to cancel job" in result["message"]

    # ===== ACTOR MANAGEMENT TESTS =====

    @pytest.mark.asyncio
    async def test_list_actors_success(self, ray_manager):
        """Test successful actor listing."""
        ray_manager._is_initialized = True
        
        mock_actors = [
            {"name": "actor1", "namespace": "default", "actor_id": "actor_123"},
            {"name": "actor2", "namespace": "test", "actor_id": "actor_456"}
        ]
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.util.list_named_actors.return_value = mock_actors
                
                result = await ray_manager.list_actors()
                
                assert result["status"] == "success"
                assert len(result["actors"]) == 2

    @pytest.mark.asyncio
    async def test_kill_actor_by_id(self, ray_manager):
        """Test killing actor by ID."""
        ray_manager._is_initialized = True
        
        mock_actor_handle = Mock()
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.get_actor.return_value = mock_actor_handle
                
                result = await ray_manager.kill_actor("a" * 32, no_restart=True)  # 32-char ID
                
                assert result["status"] == "killed"
                mock_ray.get_actor.assert_called_once_with("a" * 32)
                mock_ray.kill.assert_called_once_with(mock_actor_handle, no_restart=True)

    @pytest.mark.asyncio
    async def test_kill_actor_not_found(self, ray_manager):
        """Test killing non-existent actor."""
        ray_manager._is_initialized = True
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.get_actor.side_effect = ValueError("Actor not found")
                
                result = await ray_manager.kill_actor("nonexistent_actor")
                
                assert result["status"] == "error"
                assert "Actor nonexistent_actor not found" in result["message"]



    # ===== MONITORING TESTS =====

    @pytest.mark.asyncio
    async def test_get_performance_metrics(self, ray_manager):
        """Test getting performance metrics."""
        ray_manager._is_initialized = True
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.cluster_resources.return_value = {"CPU": 16, "memory": 32000000000, "GPU": 2}
                mock_ray.available_resources.return_value = {"CPU": 8, "memory": 16000000000, "GPU": 1}
                mock_ray.nodes.return_value = [
                    {"NodeID": "node1", "Alive": True, "Resources": {"CPU": 8}, "UsedResources": {"CPU": 4}},
                    {"NodeID": "node2", "Alive": True, "Resources": {"CPU": 8}, "UsedResources": {"CPU": 4}}
                ]
                
                result = await ray_manager.get_performance_metrics()
                
                assert result["status"] == "success"
                assert "timestamp" in result
                assert result["cluster_overview"]["total_cpus"] == 16
                assert result["cluster_overview"]["available_cpus"] == 8
                assert "resource_details" in result
                assert len(result["node_details"]) == 2

    @pytest.mark.asyncio
    async def test_cluster_health_check(self, ray_manager):
        """Test cluster health check."""
        ray_manager._is_initialized = True
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.nodes.return_value = [
                    {"NodeID": "node1", "Alive": True},
                    {"NodeID": "node2", "Alive": True}
                ]
                mock_ray.cluster_resources.return_value = {"CPU": 16, "memory": 32000000000}
                mock_ray.available_resources.return_value = {"CPU": 8, "memory": 16000000000}
                
                result = await ray_manager.cluster_health_check()
                
                assert result["status"] == "success"
                assert result["checks"]["all_nodes_alive"] is True
                assert result["checks"]["has_available_cpu"] is True
                assert result["checks"]["has_available_memory"] is True
                assert result["overall_status"] in ["excellent", "good", "fair", "poor"]



    # ===== ERROR HANDLING TESTS =====

    @pytest.mark.asyncio
    async def test_ensure_initialized_raises_error(self, ray_manager):
        """Test that _ensure_initialized raises error when not initialized."""
        with pytest.raises(RuntimeError, match="Ray is not initialized"):
            ray_manager._ensure_initialized()

    @pytest.mark.asyncio
    async def test_method_calls_when_not_initialized(self, ray_manager):
        """Test that methods handle uninitialized state gracefully."""
        # Ensure ray_manager is not initialized
        ray_manager._is_initialized = False
        
        result = await ray_manager.submit_job("python test.py")
        
        assert result["status"] == "error"
        assert "Ray is not initialized" in result["message"]

    @pytest.mark.asyncio
    async def test_exception_handling_in_methods(self, ray_manager):
        """Test exception handling in various methods."""
        ray_manager._is_initialized = True
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.cluster_resources.side_effect = Exception("Ray error")
                
                result = await ray_manager.get_cluster_resources()
                
                assert result["status"] == "error"
                assert "Ray error" in result["message"]


    # ===== ADVANCED MONITORING AND DEBUGGING TESTS =====

    @pytest.mark.asyncio
    async def test_monitor_job_progress(self, ray_manager, mock_job_client):
        """Test job progress monitoring."""
        ray_manager._is_initialized = True
        ray_manager._job_client = mock_job_client
        
        # Mock job info and logs
        job_info = Mock()
        job_info.status = "RUNNING"
        job_info.start_time = 1234567890
        job_info.end_time = None
        job_info.runtime_env = {"pip": ["requests"]}
        job_info.entrypoint = "python train.py"
        
        mock_job_client.get_job_info.return_value = job_info
        mock_job_client.get_job_logs.return_value = "Training started\nEpoch 1 completed\nEpoch 2 completed"
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                
                result = await ray_manager.monitor_job_progress("job_123")
                
                assert result["status"] == "success"
                assert result["progress"]["job_id"] == "job_123"
                assert result["progress"]["status"] == "RUNNING"
                assert len(result["progress"]["logs_tail"]) <= 10

    @pytest.mark.asyncio
    async def test_debug_job(self, ray_manager, mock_job_client):
        """Test job debugging functionality."""
        ray_manager._is_initialized = True
        ray_manager._job_client = mock_job_client
        
        # Mock job info with failure
        job_info = Mock()
        job_info.status = "FAILED"
        job_info.runtime_env = {"pip": ["requests"]}
        job_info.entrypoint = "python failing_script.py"
        
        mock_job_client.get_job_info.return_value = job_info
        mock_job_client.get_job_logs.return_value = "ImportError: No module named 'requests'\nTraceback (most recent call last):\n  File 'failing_script.py', line 1"
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                
                result = await ray_manager.debug_job("job_123")
                
                assert result["status"] == "success"
                assert result["debug_info"]["job_id"] == "job_123"
                assert result["debug_info"]["status"] == "FAILED"
                assert len(result["debug_info"]["error_logs"]) > 0
                assert len(result["debug_info"]["debugging_suggestions"]) > 0

    @pytest.mark.asyncio
    async def test_schedule_job(self, ray_manager):
        """Test job scheduling functionality."""
        ray_manager._is_initialized = True
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                
                result = await ray_manager.schedule_job(
                    entrypoint="python daily_report.py",
                    schedule="0 9 * * *",
                    timeout=3600,
                    retry_count=3
                )
                
                assert result["status"] == "job_scheduled"
                assert result["entrypoint"] == "python daily_report.py"
                assert result["schedule"] == "0 9 * * *"
                assert "config" in result

    @pytest.mark.asyncio
    async def test_optimize_cluster_config(self, ray_manager):
        """Test cluster optimization recommendations."""
        ray_manager._is_initialized = True
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.cluster_resources.return_value = {"CPU": 16, "memory": 32000000000, "GPU": 2}
                mock_ray.available_resources.return_value = {"CPU": 2, "memory": 4000000000, "GPU": 0}
                mock_ray.nodes.return_value = [
                    {"NodeID": "node1", "Alive": True, "Resources": {"CPU": 8, "memory": 16000000000}},
                    {"NodeID": "node2", "Alive": True, "Resources": {"CPU": 8, "memory": 16000000000, "GPU": 2}}
                ]
                
                result = await ray_manager.optimize_cluster_config()
                
                assert result["status"] == "success"
                assert "suggestions" in result
                assert "analysis" in result
                assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_get_logs_with_all_parameters(self, ray_manager, mock_job_client):
        """Test getting logs with all parameter combinations."""
        ray_manager._is_initialized = True
        ray_manager._job_client = mock_job_client
        
        mock_job_client.get_job_logs.return_value = "Job log line 1\nJob log line 2\nJob log line 3"
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                
                # Test with job_id
                result = await ray_manager.get_logs(job_id="job_123", num_lines=50)
                assert result["status"] == "success"
                assert "logs" in result
                
                # Test with actor_id (returns partial status)
                result = await ray_manager.get_logs(actor_id="actor_123", num_lines=25)
                assert result["status"] == "partial"
                
                # Test with node_id (returns partial status)
                result = await ray_manager.get_logs(node_id="node_123", num_lines=100)
                assert result["status"] == "partial"

    @pytest.mark.asyncio
    async def test_start_cluster_default_cpu_setting(self, ray_manager, mock_ray_context):
        """Test that default num_cpus is set to 4 when not specified."""
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                with patch('ray_mcp.ray_manager.JobSubmissionClient'):
                    mock_ray.init.return_value = mock_ray_context
                    mock_ray.get_runtime_context.return_value.get_node_id.return_value = "node_123"
                    
                    # Start cluster without specifying num_cpus
                    result = await ray_manager.start_cluster()
                    
                    assert result["status"] == "started"
                    # Verify default num_cpus=4 was set
                    call_kwargs = mock_ray.init.call_args[1]
                    assert call_kwargs["num_cpus"] == 4

    @pytest.mark.asyncio
    async def test_start_cluster_with_no_job_submission_client(self, ray_manager, mock_ray_context):
        """Test cluster start when JobSubmissionClient is None."""
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                with patch('ray_mcp.ray_manager.JobSubmissionClient', None):
                    mock_ray.init.return_value = mock_ray_context
                    mock_ray.get_runtime_context.return_value.get_node_id.return_value = "node_123"
                    
                    result = await ray_manager.start_cluster()
                    
                    assert result["status"] == "started"
                    # Job client should remain None
                    assert ray_manager._job_client is None

    # ===== HELPER METHOD TESTS =====

    def test_generate_debug_suggestions(self, ray_manager):
        """Test debug suggestion generation."""
        # Mock job info for failed job
        job_info = Mock()
        job_info.status = "FAILED"
        
        # Test with import error logs
        logs_with_import_error = "ImportError: No module named 'requests'\nTraceback..."
        suggestions = ray_manager._generate_debug_suggestions(job_info, logs_with_import_error)
        
        assert len(suggestions) >= 2
        assert any("failed" in suggestion.lower() for suggestion in suggestions)
        assert any("import" in suggestion.lower() for suggestion in suggestions)
        
        # Test with memory error logs
        logs_with_memory_error = "MemoryError: Unable to allocate array\nOut of memory..."
        suggestions = ray_manager._generate_debug_suggestions(job_info, logs_with_memory_error)
        
        assert any("memory" in suggestion.lower() for suggestion in suggestions)

    # ===== EDGE CASES AND EXCEPTION HANDLING =====

    @pytest.mark.asyncio
    async def test_cluster_health_check_detailed_scenarios(self, ray_manager):
        """Test cluster health check with various node states."""
        ray_manager._is_initialized = True
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                
                # Test excellent health scenario
                mock_ray.nodes.return_value = [
                    {"NodeID": "node1", "Alive": True},
                    {"NodeID": "node2", "Alive": True}
                ]
                mock_ray.cluster_resources.return_value = {"CPU": 16, "memory": 32000000000}
                mock_ray.available_resources.return_value = {"CPU": 8, "memory": 16000000000}
                
                result = await ray_manager.cluster_health_check()
                
                assert result["status"] == "success"
                assert result["overall_status"] == "excellent"
                assert result["health_score"] == 100.0
                
                # Test poor health scenario
                mock_ray.nodes.return_value = [
                    {"NodeID": "node1", "Alive": False},
                    {"NodeID": "node2", "Alive": False}
                ]
                mock_ray.available_resources.return_value = {"CPU": 0, "memory": 0}
                
                result = await ray_manager.cluster_health_check()
                
                assert result["status"] == "success"
                assert result["overall_status"] == "poor"
                assert result["health_score"] == 25.0

    @pytest.mark.asyncio
    async def test_monitor_job_progress_no_client(self, ray_manager):
        """Test monitor job progress when job client is not available."""
        ray_manager._is_initialized = True
        ray_manager._job_client = None
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                
                result = await ray_manager.monitor_job_progress("job_123")
                
                assert result["status"] == "error"
                assert "Job submission client not available" in result["message"]

    @pytest.mark.asyncio
    async def test_debug_job_no_client(self, ray_manager):
        """Test debug job when job client is not available."""
        ray_manager._is_initialized = True
        ray_manager._job_client = None
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                
                result = await ray_manager.debug_job("job_123")
                
                assert result["status"] == "error"
                assert "Job submission client not available" in result["message"]

    @pytest.mark.asyncio
    async def test_schedule_job_not_initialized(self, ray_manager):
        """Test schedule job when not initialized."""
        result = await ray_manager.schedule_job("python test.py", "0 * * * *")
        assert result["status"] == "error"
        assert "Ray is not initialized" in result["message"]

    @pytest.mark.asyncio
    async def test_optimize_cluster_config_not_initialized(self, ray_manager):
        """Test optimize cluster config when not initialized."""
        result = await ray_manager.optimize_cluster_config()
        assert result["status"] == "error"
        assert "Ray is not initialized" in result["message"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 