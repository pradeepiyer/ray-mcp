#!/usr/bin/env python3
"""Tests for the Ray manager."""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any, List

from ray_mcp.ray_manager import RayManager


class TestRayManager:
    """Test cases for RayManager."""

    @pytest.fixture
    def manager(self):
        """Create a RayManager instance for testing."""
        return RayManager()

    @pytest.fixture
    def initialized_manager(self):
        """Create an initialized RayManager instance."""
        manager = RayManager()
        manager._is_initialized = True
        manager._cluster_address = "ray://127.0.0.1:10001"
        manager._job_client = Mock()
        return manager

    def test_init(self):
        """Test RayManager initialization."""
        manager = RayManager()
        assert not manager.is_initialized
        assert manager._job_client is None
        assert manager._cluster_address is None

    @pytest.mark.asyncio
    async def test_start_cluster_success(self):
        """Test successful cluster start."""
        manager = RayManager()
        
        # Mock ray.init and related functions
        mock_context = Mock()
        mock_context.address_info = {
            "address": "ray://127.0.0.1:10001",
        }
        mock_context.dashboard_url = "http://127.0.0.1:8265"
        mock_context.session_name = "test_session"
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.init.return_value = mock_context
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = "test_node_id"
                
                with patch('ray_mcp.ray_manager.JobSubmissionClient'):
                    result = await manager.start_cluster()
                    
                    assert result["status"] == "started"
                    assert result["address"] == "ray://127.0.0.1:10001"
                    assert manager._is_initialized

    @pytest.mark.asyncio
    async def test_start_cluster_already_running(self):
        """Test cluster start when already running."""
        manager = RayManager()
        
        # Mock ray.init to work properly with ignore_reinit_error=True
        mock_context = Mock()
        mock_context.address_info = {"address": "ray://127.0.0.1:10001"}
        mock_context.dashboard_url = "http://127.0.0.1:8265"
        mock_context.session_name = "test_session"
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.init.return_value = mock_context
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = "test_node"
                
                with patch('ray_mcp.ray_manager.JobSubmissionClient'):
                    result = await manager.start_cluster()
                    
                    # When Ray is already running, ray.init with ignore_reinit_error=True
                    # will still return successfully, so we expect "started" status
                    assert result["status"] == "started"
                    assert result["address"] == "ray://127.0.0.1:10001"

    @pytest.mark.asyncio
    async def test_stop_cluster(self):
        """Test cluster stop."""
        manager = RayManager()
        manager._is_initialized = True
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.shutdown.return_value = None
                
                result = await manager.stop_cluster()
                
                assert result["status"] == "stopped"
                assert not manager._is_initialized
                assert manager._job_client is None

    @pytest.mark.asyncio
    async def test_stop_cluster_not_running(self):
        """Test cluster stop when not running."""
        manager = RayManager()
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = False
                
                result = await manager.stop_cluster()
                
                assert result["status"] == "not_running"

    @pytest.mark.asyncio
    async def test_get_cluster_status_not_running(self):
        """Test get cluster status when not running."""
        manager = RayManager()
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = False
                
                result = await manager.get_cluster_status()
                
                assert result["status"] == "not_running"

    @pytest.mark.asyncio
    async def test_get_cluster_status_running(self):
        """Test get cluster status when running."""
        manager = RayManager()
        manager._is_initialized = True
        manager._cluster_address = "ray://127.0.0.1:10001"
        
        mock_context = Mock()
        mock_context.session_name = "test_session"
        mock_context.node_id = Mock()
        mock_context.node_id.hex.return_value = "test_node_id"
        mock_context.get_job_id.return_value = "test_job_id"
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.cluster_resources.return_value = {"CPU": 4, "memory": 8000000000}
                mock_ray.available_resources.return_value = {"CPU": 2, "memory": 4000000000}
                mock_ray.nodes.return_value = [
                    {
                        "NodeID": "node1",
                        "Alive": True,
                        "NodeName": "test_node",
                        "Resources": {"CPU": 4}
                    }
                ]
                mock_ray.get_runtime_context.return_value = mock_context
                
                result = await manager.get_cluster_status()
                
                assert result["status"] == "running"
                assert "cluster_resources" in result
                assert "available_resources" in result
                assert "nodes" in result

    def test_ensure_initialized_not_initialized(self):
        """Test _ensure_initialized when not initialized."""
        manager = RayManager()
        
        with pytest.raises(RuntimeError, match="Ray is not initialized. Please start Ray first."):
            manager._ensure_initialized()

    def test_ensure_initialized_initialized(self):
        """Test _ensure_initialized when initialized."""
        manager = RayManager()
        manager._is_initialized = True
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                # Should not raise
                manager._ensure_initialized()

    # ===== CONNECT CLUSTER TESTS =====

    @pytest.mark.asyncio
    async def test_connect_cluster_success(self, manager):
        """Test successful cluster connection."""
        mock_context = Mock()
        mock_context.address_info = {"address": "ray://remote:10001"}
        mock_context.dashboard_url = "http://remote:8265"
        mock_context.session_name = "remote_session"
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.init.return_value = mock_context
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = "remote_node"
                
                with patch('ray_mcp.ray_manager.JobSubmissionClient') as mock_client:
                    result = await manager.connect_cluster("ray://remote:10001")
                    
                    assert result["status"] == "connected"
                    assert result["address"] == "ray://remote:10001"
                    assert manager._is_initialized
                    assert manager._cluster_address == "ray://remote:10001"

    @pytest.mark.asyncio
    async def test_connect_cluster_ray_unavailable(self, manager):
        """Test cluster connection when Ray is unavailable."""
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', False):
            result = await manager.connect_cluster("ray://remote:10001")
            
            assert result["status"] == "error"
            assert "Ray is not available" in result["message"]

    @pytest.mark.asyncio
    async def test_submit_job_success(self, initialized_manager):
        """Test successful job submission."""
        mock_job_client = initialized_manager._job_client
        mock_job_client.submit_job.return_value = "submitted_job_123"
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                
                result = await initialized_manager.submit_job(
                    entrypoint="python train.py",
                    runtime_env={"pip": ["numpy"]},
                    job_id="custom_job",
                    metadata={"owner": "test"}
                )
                
                assert result["status"] == "submitted"
                assert result["job_id"] == "submitted_job_123"

    @pytest.mark.asyncio
    async def test_submit_job_not_initialized(self, manager):
        """Test job submission when not initialized."""
        result = await manager.submit_job("python test.py")
        assert result["status"] == "error"
        assert "Ray is not initialized" in result["message"]

    @pytest.mark.asyncio
    async def test_get_cluster_resources_success(self, initialized_manager):
        """Test successful cluster resources retrieval."""
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.cluster_resources.return_value = {"CPU": 12.0, "memory": 32000000000}
                mock_ray.available_resources.return_value = {"CPU": 8.0, "memory": 16000000000}
                
                result = await initialized_manager.get_cluster_resources()
                
                assert result["status"] == "success"
                assert "total_resources" in result or "cluster_resources" in result

    @pytest.mark.asyncio
    async def test_list_actors_success(self, initialized_manager):
        """Test successful actor listing."""
        mock_named_actors = [
            {
                "name": "test_actor",
                "namespace": "default"
            }
        ]
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.util.list_named_actors.return_value = mock_named_actors
                
                # Mock actor handle
                mock_actor_handle = Mock()
                mock_actor_handle._actor_id.hex.return_value = "actor123"
                mock_ray.get_actor.return_value = mock_actor_handle
                
                result = await initialized_manager.list_actors()
                
                assert result["status"] == "success"
                assert len(result["actors"]) == 1

    @pytest.mark.asyncio
    async def test_kill_actor_success(self, initialized_manager):
        """Test successful actor killing."""
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.kill.return_value = None
                
                result = await initialized_manager.kill_actor("actor123", no_restart=True)
                
                assert result["status"] == "killed"
                assert result["actor_id"] == "actor123"

    @pytest.mark.asyncio
    async def test_get_logs_job_success(self, initialized_manager):
        """Test successful job log retrieval."""
        mock_job_client = initialized_manager._job_client
        mock_job_client.get_job_logs.return_value = "Job log output"
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                
                result = await initialized_manager.get_logs(job_id="test_job", num_lines=50)
                
                assert result["status"] == "success"
                assert result["logs"] == "Job log output"

    @pytest.mark.asyncio
    async def test_get_performance_metrics_success(self, initialized_manager):
        """Test successful performance metrics retrieval."""
        mock_cluster_resources = {"CPU": 12.0, "memory": 32000000000}
        mock_available_resources = {"CPU": 8.0, "memory": 20000000000}
        mock_nodes = [
            {"NodeID": "node1", "Alive": True},
            {"NodeID": "node2", "Alive": True}
        ]
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.cluster_resources.return_value = mock_cluster_resources
                mock_ray.available_resources.return_value = mock_available_resources
                mock_ray.nodes.return_value = mock_nodes
                
                result = await initialized_manager.get_performance_metrics()
                
                assert result["status"] == "success"
                assert "cluster_overview" in result or "cluster_utilization" in result

    @pytest.mark.asyncio
    async def test_cluster_health_check_success(self, initialized_manager):
        """Test successful cluster health check."""
        mock_nodes = [{"NodeID": "node1", "Alive": True}]
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.nodes.return_value = mock_nodes
                mock_ray.cluster_resources.return_value = {"CPU": 8.0}
                mock_ray.available_resources.return_value = {"CPU": 4.0}
                
                result = await initialized_manager.cluster_health_check()
                
                assert result["status"] == "success"
                assert "health_score" in result

    def test_generate_health_recommendations(self, manager):
        """Test health recommendation generation."""
        # Test with all checks passing
        health_checks = {
            "all_nodes_alive": True,
            "has_available_cpu": True,
            "has_available_memory": True,
            "cluster_responsive": True
        }
        recommendations = manager._generate_health_recommendations(health_checks)
        assert len(recommendations) == 1
        assert "good" in recommendations[0].lower()
        
        # Test with failing checks
        health_checks = {
            "all_nodes_alive": False,
            "has_available_cpu": False,
            "has_available_memory": False,
            "cluster_responsive": True
        }
        recommendations = manager._generate_health_recommendations(health_checks)
        assert len(recommendations) == 3
        assert any("nodes" in rec.lower() for rec in recommendations)
        assert any("cpu" in rec.lower() for rec in recommendations)
        assert any("memory" in rec.lower() for rec in recommendations)

    # ===== ERROR HANDLING AND EDGE CASES =====

    @pytest.mark.asyncio
    async def test_start_cluster_ray_unavailable(self, manager):
        """Test start cluster when Ray is not available."""
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', False):
            result = await manager.start_cluster()
            assert result["status"] == "error"
            assert "Ray is not available" in result["message"]

    @pytest.mark.asyncio
    async def test_start_cluster_exception(self, manager):
        """Test start cluster with exception."""
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.init.side_effect = Exception("Connection failed")
                
                result = await manager.start_cluster()
                assert result["status"] == "error"
                assert "Connection failed" in result["message"]

    @pytest.mark.asyncio
    async def test_start_cluster_with_all_parameters(self, manager):
        """Test start cluster with all parameters specified."""
        mock_context = Mock()
        mock_context.address_info = {"address": "ray://127.0.0.1:10001"}
        mock_context.dashboard_url = "http://127.0.0.1:8265"
        mock_context.session_name = "test_session"
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.init.return_value = mock_context
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = "test_node"
                
                with patch('ray_mcp.ray_manager.JobSubmissionClient'):
                    result = await manager.start_cluster(
                        head_node=True,
                        num_cpus=8,
                        num_gpus=2,
                        object_store_memory=1000000000,
                        custom_param="test"
                    )
                    
                    assert result["status"] == "started"
                    # Verify all parameters were passed to ray.init
                    call_kwargs = mock_ray.init.call_args[1]
                    assert call_kwargs["num_cpus"] == 8
                    assert call_kwargs["num_gpus"] == 2
                    assert call_kwargs["object_store_memory"] == 1000000000
                    assert call_kwargs["custom_param"] == "test"
                    assert call_kwargs["ignore_reinit_error"] is True

    @pytest.mark.asyncio
    async def test_connect_cluster_exception(self, manager):
        """Test connect cluster with exception."""
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.init.side_effect = Exception("Connection refused")
                
                result = await manager.connect_cluster("ray://remote:10001")
                assert result["status"] == "error"
                assert "Connection refused" in result["message"]

    @pytest.mark.asyncio
    async def test_stop_cluster_ray_unavailable(self, manager):
        """Test stop cluster when Ray is not available."""
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', False):
            result = await manager.stop_cluster()
            assert result["status"] == "error"
            assert "Ray is not available" in result["message"]

    @pytest.mark.asyncio
    async def test_stop_cluster_exception(self, manager):
        """Test stop cluster with exception."""
        manager._is_initialized = True
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.shutdown.side_effect = Exception("Shutdown failed")
                
                result = await manager.stop_cluster()
                assert result["status"] == "error"
                assert "Shutdown failed" in result["message"]

    @pytest.mark.asyncio
    async def test_get_cluster_status_ray_unavailable(self, manager):
        """Test get cluster status when Ray is not available."""
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', False):
            result = await manager.get_cluster_status()
            assert result["status"] == "unavailable"
            assert "Ray is not available" in result["message"]

    @pytest.mark.asyncio
    async def test_get_cluster_status_exception(self, manager):
        """Test get cluster status with exception."""
        manager._is_initialized = True
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.cluster_resources.side_effect = Exception("Status error")
                
                result = await manager.get_cluster_status()
                assert result["status"] == "error"
                assert "Status error" in result["message"]

    # ===== JOB MANAGEMENT ERROR CASES =====

    @pytest.mark.asyncio
    async def test_submit_job_no_client(self, initialized_manager):
        """Test submit job when job client is not available."""
        initialized_manager._job_client = None
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                
                result = await initialized_manager.submit_job("python test.py")
                assert result["status"] == "error"
                assert "Job submission client not available" in result["message"]

    @pytest.mark.asyncio
    async def test_submit_job_exception(self, initialized_manager):
        """Test submit job with exception."""
        initialized_manager._job_client.submit_job.side_effect = Exception("Submit failed")
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                
                result = await initialized_manager.submit_job("python test.py")
                assert result["status"] == "error"
                assert "Submit failed" in result["message"]

    @pytest.mark.asyncio
    async def test_list_jobs_not_initialized(self, manager):
        """Test list jobs when not initialized."""
        result = await manager.list_jobs()
        assert result["status"] == "error"
        assert "Ray is not initialized" in result["message"]

    @pytest.mark.asyncio
    async def test_list_jobs_no_client(self, initialized_manager):
        """Test list jobs when job client is not available."""
        initialized_manager._job_client = None
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                
                result = await initialized_manager.list_jobs()
                assert result["status"] == "error"
                assert "Job submission client not available" in result["message"]

    @pytest.mark.asyncio
    async def test_get_job_status_not_initialized(self, manager):
        """Test get job status when not initialized."""
        result = await manager.get_job_status("test_job")
        assert result["status"] == "error"
        assert "Ray is not initialized" in result["message"]

    @pytest.mark.asyncio
    async def test_get_job_status_no_client(self, initialized_manager):
        """Test get job status when job client is not available."""
        initialized_manager._job_client = None
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                
                result = await initialized_manager.get_job_status("test_job")
                assert result["status"] == "error"
                assert "Job submission client not available" in result["message"]

    @pytest.mark.asyncio
    async def test_cancel_job_not_initialized(self, manager):
        """Test cancel job when not initialized."""
        result = await manager.cancel_job("test_job")
        assert result["status"] == "error"
        assert "Ray is not initialized" in result["message"]

    @pytest.mark.asyncio
    async def test_cancel_job_no_client(self, initialized_manager):
        """Test cancel job when job client is not available."""
        initialized_manager._job_client = None
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                
                result = await initialized_manager.cancel_job("test_job")
                assert result["status"] == "error"
                assert "Job submission client not available" in result["message"]

    # ===== RESOURCE AND NODE MANAGEMENT ERROR CASES =====

    @pytest.mark.asyncio
    async def test_get_cluster_resources_not_initialized(self, manager):
        """Test get cluster resources when not initialized."""
        result = await manager.get_cluster_resources()
        assert result["status"] == "error"
        assert "Ray is not initialized" in result["message"]

    @pytest.mark.asyncio
    async def test_get_cluster_resources_exception(self, initialized_manager):
        """Test get cluster resources with exception."""
        with patch('ray_mcp.ray_manager.ray') as mock_ray:
            mock_ray.cluster_resources.side_effect = Exception("Resource error")
            
            result = await initialized_manager.get_cluster_resources()
            assert result["status"] == "error"
            assert "Resource error" in result["message"]

    @pytest.mark.asyncio
    async def test_get_cluster_nodes_not_initialized(self, manager):
        """Test get cluster nodes when not initialized."""
        result = await manager.get_cluster_nodes()
        assert result["status"] == "error"
        assert "Ray is not initialized" in result["message"]

    @pytest.mark.asyncio
    async def test_get_cluster_nodes_exception(self, initialized_manager):
        """Test get cluster nodes with exception."""
        with patch('ray_mcp.ray_manager.ray') as mock_ray:
            mock_ray.nodes.side_effect = Exception("Nodes error")
            
            result = await initialized_manager.get_cluster_nodes()
            assert result["status"] == "error"
            assert "Nodes error" in result["message"]

    # ===== ACTOR MANAGEMENT ERROR CASES =====

    @pytest.mark.asyncio
    async def test_list_actors_not_initialized(self, manager):
        """Test list actors when not initialized."""
        result = await manager.list_actors()
        assert result["status"] == "error"
        assert "Ray is not initialized" in result["message"]

    @pytest.mark.asyncio
    async def test_list_actors_exception(self, initialized_manager):
        """Test list actors with exception."""
        with patch('ray_mcp.ray_manager.ray') as mock_ray:
            mock_ray.util.list_named_actors.side_effect = Exception("Actor list error")
            
            result = await initialized_manager.list_actors()
            assert result["status"] == "error"
            assert "Actor list error" in result["message"]

    @pytest.mark.asyncio
    async def test_kill_actor_not_initialized(self, manager):
        """Test kill actor when not initialized."""
        result = await manager.kill_actor("test_actor")
        assert result["status"] == "error"
        assert "Ray is not initialized" in result["message"]

    @pytest.mark.asyncio
    async def test_kill_actor_exception(self, initialized_manager):
        """Test kill actor with exception."""
        with patch('ray_mcp.ray_manager.ray') as mock_ray:
            mock_ray.get_actor.side_effect = Exception("Actor not found")
            
            result = await initialized_manager.kill_actor("test_actor")
            assert result["status"] == "error"
            assert "Actor not found" in result["message"]

    # ===== MONITORING AND DEBUGGING ERROR CASES =====

    @pytest.mark.asyncio
    async def test_get_logs_not_initialized(self, manager):
        """Test get logs when not initialized."""
        result = await manager.get_logs(job_id="test_job")
        assert result["status"] == "error"
        assert "Ray is not initialized" in result["message"]

    @pytest.mark.asyncio
    async def test_get_logs_no_client(self, initialized_manager):
        """Test get logs when job client is not available."""
        initialized_manager._job_client = None
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray') as mock_ray:
                mock_ray.is_initialized.return_value = True
                
                result = await initialized_manager.get_logs(job_id="test_job")
                assert result["status"] == "partial"
                assert "not fully implemented" in result["message"]

    @pytest.mark.asyncio
    async def test_get_performance_metrics_not_initialized(self, manager):
        """Test get performance metrics when not initialized."""
        result = await manager.get_performance_metrics()
        assert result["status"] == "error"
        assert "Ray is not initialized" in result["message"]

    @pytest.mark.asyncio
    async def test_get_performance_metrics_exception(self, initialized_manager):
        """Test get performance metrics with exception."""
        with patch('ray_mcp.ray_manager.ray') as mock_ray:
            mock_ray.cluster_resources.side_effect = Exception("Metrics error")
            
            result = await initialized_manager.get_performance_metrics()
            assert result["status"] == "error"
            assert "Metrics error" in result["message"]

    @pytest.mark.asyncio
    async def test_cluster_health_check_not_initialized(self, manager):
        """Test cluster health check when not initialized."""
        result = await manager.cluster_health_check()
        assert result["status"] == "error"
        assert "Ray is not initialized" in result["message"]



    @pytest.mark.asyncio
    async def test_cluster_health_check_exception(self, initialized_manager):
        """Test cluster health check with exception."""
        with patch('ray_mcp.ray_manager.ray') as mock_ray:
            mock_ray.nodes.side_effect = Exception("Health check error")
            
            result = await initialized_manager.cluster_health_check()
            assert result["status"] == "error"
            assert "Health check error" in result["message"]


if __name__ == "__main__":
    pytest.main([__file__]) 