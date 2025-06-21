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
                    runtime_env={"pip": ["numpy", "pandas"]},
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
        job1.runtime_env = {"pip": ["torch"]}
        
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

    # ===== MACHINE LEARNING TESTS =====

    @pytest.mark.asyncio
    async def test_train_model_torch(self, ray_manager):
        """Test training a PyTorch model."""
        ray_manager._is_initialized = True
        
        with patch('ray_mcp.ray_manager.RAY_TRAIN_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
                with patch('ray_mcp.ray_manager.ray') as mock_ray:
                    mock_ray.is_initialized.return_value = True
                    
                    # Mock the imports that happen inside the method
                    with patch.dict('sys.modules', {
                        'ray.train': Mock(),
                        'ray.train.torch': Mock(),
                        'ray.train.tensorflow': Mock(),
                        'ray.train.xgboost': Mock(),
                        'ray.train.sklearn': Mock()
                    }):
                        result = await ray_manager.train_model(
                            algorithm="torch",
                            dataset_path="/data/train.parquet",
                            model_config={"learning_rate": 0.001, "epochs": 10}
                        )
                        
                        assert result["status"] == "training_started"
                        assert result["algorithm"] == "torch"
                        assert result["dataset_path"] == "/data/train.parquet"

    @pytest.mark.asyncio
    async def test_train_model_unsupported_algorithm(self, ray_manager):
        """Test training with unsupported algorithm."""
        ray_manager._is_initialized = True
        
        with patch('ray_mcp.ray_manager.RAY_TRAIN_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
                with patch('ray_mcp.ray_manager.ray') as mock_ray:
                    mock_ray.is_initialized.return_value = True
                    
                    # Mock the imports that happen inside the method
                    with patch.dict('sys.modules', {
                        'ray.train': Mock(),
                        'ray.train.torch': Mock(),
                        'ray.train.tensorflow': Mock(),
                        'ray.train.xgboost': Mock(),
                        'ray.train.sklearn': Mock()
                    }):
                        result = await ray_manager.train_model(
                            algorithm="unsupported",
                            dataset_path="/data/train.parquet",
                            model_config={}
                        )
                        
                        assert result["status"] == "error"
                        assert "Unsupported algorithm" in result["message"]

    @pytest.mark.asyncio
    async def test_train_model_ray_train_not_available(self, ray_manager):
        """Test training when Ray Train is not available."""
        ray_manager._is_initialized = True
        
        with patch('ray_mcp.ray_manager.RAY_TRAIN_AVAILABLE', False):
            with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
                with patch('ray_mcp.ray_manager.ray') as mock_ray:
                    mock_ray.is_initialized.return_value = True
                    
                    result = await ray_manager.train_model(
                        algorithm="torch",
                        dataset_path="/data/train.parquet",
                        model_config={}
                    )
                    
                    assert result["status"] == "error"
                    assert "Ray Train not available" in result["message"]

    @pytest.mark.asyncio
    async def test_tune_hyperparameters(self, ray_manager):
        """Test hyperparameter tuning."""
        ray_manager._is_initialized = True
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                
                # Mock Ray Tune imports
                with patch.dict('sys.modules', {
                    'ray.tune': Mock(),
                    'ray.tune.search.basic_variant': Mock()
                }):
                    result = await ray_manager.tune_hyperparameters(
                        script_path="/scripts/train.py",
                        search_space={"lr": [0.001, 0.01], "batch_size": [16, 32]},
                        metric="accuracy",
                        mode="max",
                        num_samples=20
                    )
                    
                    assert result["status"] == "tuning_started"
                    assert result["metric"] == "accuracy"
                    assert result["config"]["num_samples"] == 20

    # ===== DATA PROCESSING TESTS =====

    @pytest.mark.asyncio
    async def test_create_dataset_parquet(self, ray_manager):
        """Test creating a Parquet dataset."""
        ray_manager._is_initialized = True
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                
                # Mock Ray Data imports
                with patch.dict('sys.modules', {'ray.data': Mock()}):
                    result = await ray_manager.create_dataset(
                        source="/data/input.parquet",
                        format="parquet"
                    )
                    
                    assert result["status"] == "dataset_created"
                    assert result["source"] == "/data/input.parquet"
                    assert result["format"] == "parquet"

    @pytest.mark.asyncio
    async def test_create_dataset_unsupported_format(self, ray_manager):
        """Test creating dataset with unsupported format."""
        ray_manager._is_initialized = True
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                
                # Mock Ray Data imports
                with patch.dict('sys.modules', {'ray.data': Mock()}):
                    result = await ray_manager.create_dataset(
                        source="/data/input.xyz",
                        format="unsupported"
                    )
                    
                    assert result["status"] == "error"
                    assert "Unsupported format" in result["message"]

    @pytest.mark.asyncio
    async def test_batch_inference(self, ray_manager):
        """Test batch inference."""
        ray_manager._is_initialized = True
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                
                # Mock Ray Data imports
                with patch.dict('sys.modules', {'ray.data': Mock()}):
                    result = await ray_manager.batch_inference(
                        model_path="/models/trained_model.pkl",
                        dataset_path="/data/test.parquet",
                        output_path="/results/predictions.parquet",
                        batch_size=64,
                        num_workers=8
                    )
                    
                    assert result["status"] == "inference_started"
                    assert result["config"]["batch_size"] == 64
                    assert result["config"]["num_workers"] == 8

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

    # ===== BACKUP & RECOVERY TESTS =====

    @pytest.mark.asyncio
    async def test_backup_cluster_state(self, ray_manager):
        """Test backing up cluster state."""
        ray_manager._is_initialized = True
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.cluster_resources.return_value = {"CPU": 8}
                mock_ray.nodes.return_value = [{"NodeID": "node1", "Alive": True}]
                
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tmp:
                    backup_path = tmp.name
                
                try:
                    result = await ray_manager.backup_cluster_state(backup_path)
                    
                    assert result["status"] == "backup_created"
                    assert result["backup_path"] == backup_path
                    assert os.path.exists(backup_path)
                    
                    # Verify backup content
                    with open(backup_path, 'r') as f:
                        backup_data = json.load(f)
                    assert "timestamp" in backup_data
                    assert "cluster_resources" in backup_data
                    assert "nodes" in backup_data
                    
                finally:
                    if os.path.exists(backup_path):
                        os.unlink(backup_path)

    @pytest.mark.asyncio
    async def test_restore_cluster_state(self, ray_manager):
        """Test restoring cluster state."""
        ray_manager._is_initialized = True
        
        # Create a temporary backup file
        backup_data = {
            "timestamp": 1234567890,
            "cluster_resources": {"CPU": 8},
            "nodes": [{"NodeID": "node1", "Alive": True}]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tmp:
            json.dump(backup_data, tmp)
            backup_path = tmp.name
        
        try:
            with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
                with patch('ray_mcp.ray_manager.ray') as mock_ray:
                    mock_ray.is_initialized.return_value = True
                    
                    result = await ray_manager.restore_cluster_state(backup_path)
                    
                    assert result["status"] == "restore_info"
                    assert result["backup_path"] == backup_path
                    assert result["backup_timestamp"] == 1234567890
            
        finally:
            if os.path.exists(backup_path):
                os.unlink(backup_path)

    @pytest.mark.asyncio
    async def test_restore_cluster_state_file_not_found(self, ray_manager):
        """Test restoring from non-existent backup file."""
        ray_manager._is_initialized = True
        
        result = await ray_manager.restore_cluster_state("/nonexistent/backup.json")
        
        assert result["status"] == "error"
        assert "Failed to restore cluster state" in result["message"]

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 