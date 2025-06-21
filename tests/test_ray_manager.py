#!/usr/bin/env python3
"""Tests for the Ray manager."""

import asyncio
import pytest
from unittest.mock import Mock, patch

from ray_mcp.ray_manager import RayManager


class TestRayManager:
    """Test cases for RayManager."""

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


if __name__ == "__main__":
    pytest.main([__file__]) 