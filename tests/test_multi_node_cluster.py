#!/usr/bin/env python3
"""Tests for multi-node Ray cluster functionality."""

import asyncio
import json
import subprocess
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ray_mcp.ray_manager import RayManager
from ray_mcp.worker_manager import WorkerManager


@pytest.mark.fast
class TestMultiNodeCluster:
    """Test cases for multi-node cluster functionality."""

    @pytest.fixture
    def ray_manager(self):
        """Create a RayManager instance for testing."""
        return RayManager()

    @pytest.fixture
    def worker_manager(self):
        """Create a WorkerManager instance for testing."""
        return WorkerManager()

    @pytest.mark.asyncio
    async def test_start_cluster_with_worker_nodes(self):
        """Test starting a cluster with worker nodes."""
        worker_configs = [
            {"num_cpus": 2, "num_gpus": 0},
            {"num_cpus": 2, "num_gpus": 0},
        ]
        expected_worker_count = len(worker_configs)
        expected_total_nodes = 1 + expected_worker_count  # 1 head + workers

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray.is_initialized", return_value=True):
                with patch("ray_mcp.ray_manager.ray.init") as mock_init:
                    with patch(
                        "ray_mcp.ray_manager.ray.get_runtime_context"
                    ) as mock_get_runtime_context:
                        mock_context = Mock()
                        mock_context.address_info = {"address": "ray://127.0.0.1:10001"}
                        mock_context.dashboard_url = "http://127.0.0.1:8265"
                        mock_context.session_name = "test_session"
                        mock_init.return_value = mock_context
                        mock_get_runtime_context.return_value.get_node_id.return_value = (
                            "test_node"
                        )
                        ray_manager = RayManager()
                        with patch.object(
                            ray_manager._worker_manager,
                            "start_worker_nodes",
                            new_callable=AsyncMock,
                        ) as mock_start_workers:
                            mock_start_workers.return_value = [
                                {
                                    "status": "started",
                                    "node_name": f"worker-{i}",
                                    "message": f"Worker node 'worker-{i}' started successfully",
                                    "process_id": 1000 + i,
                                    "config": config,
                                }
                                for i, config in enumerate(worker_configs)
                            ]
                            result = await ray_manager.start_cluster(
                                num_cpus=4,
                                worker_nodes=worker_configs,
                                head_node_port=10001,
                                dashboard_port=8265,
                            )
                            # Verify result
                            assert result["status"] == "started"
                            assert result["total_nodes"] == expected_total_nodes
                            assert "worker_nodes" in result
                            assert len(result["worker_nodes"]) == expected_worker_count
                            # Verify worker manager was called
                            mock_start_workers.assert_called_once_with(
                                worker_configs, "ray://127.0.0.1:10001"
                            )

    @pytest.mark.asyncio
    async def test_start_cluster_without_worker_nodes(self):
        """Test starting a cluster without worker nodes (now defaults to multi-node)."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray.is_initialized", return_value=True):
                with patch("ray_mcp.ray_manager.ray.init") as mock_init:
                    with patch(
                        "ray_mcp.ray_manager.ray.get_runtime_context"
                    ) as mock_get_runtime_context:
                        mock_context = Mock()
                        mock_context.address_info = {"address": "ray://127.0.0.1:10001"}
                        mock_context.dashboard_url = "http://127.0.0.1:8265"
                        mock_context.session_name = "test_session"
                        mock_init.return_value = mock_context
                        mock_get_runtime_context.return_value.get_node_id.return_value = (
                            "test_node"
                        )
                        ray_manager = RayManager()
                        with patch.object(
                            ray_manager._worker_manager,
                            "start_worker_nodes",
                            new_callable=AsyncMock,
                        ) as mock_start_workers:
                            mock_start_workers.return_value = [
                                {
                                    "status": "started",
                                    "node_name": "default-worker-1",
                                    "message": "Worker node 'default-worker-1' started successfully",
                                    "process_id": 1001,
                                    "config": {
                                        "num_cpus": 2,
                                        "num_gpus": 0,
                                        "object_store_memory": 500000000,
                                        "node_name": "default-worker-1",
                                    },
                                },
                                {
                                    "status": "started",
                                    "node_name": "default-worker-2",
                                    "message": "Worker node 'default-worker-2' started successfully",
                                    "process_id": 1002,
                                    "config": {
                                        "num_cpus": 2,
                                        "num_gpus": 0,
                                        "object_store_memory": 500000000,
                                        "node_name": "default-worker-2",
                                    },
                                },
                            ]
                            result = await ray_manager.start_cluster(num_cpus=4)
                            assert result["status"] == "started"
                            assert (
                                result["total_nodes"] == 3
                            )  # 1 head + 2 default workers
                            assert "worker_nodes" in result
                            assert len(result["worker_nodes"]) == 2  # 2 default workers

    @pytest.mark.asyncio
    async def test_stop_cluster_with_workers(self):
        """Test stopping a cluster with worker nodes."""
        mock_worker_results = [
            {
                "status": "stopped",
                "node_name": "worker-1",
                "message": "Worker node 'worker-1' stopped gracefully",
            }
        ]
        expected_worker_count = len(mock_worker_results)

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray.is_initialized", return_value=True):
                with patch("ray_mcp.ray_manager.ray.shutdown") as mock_shutdown:
                    ray_manager = RayManager()
                    with patch.object(
                        ray_manager._worker_manager,
                        "stop_all_workers",
                        new_callable=AsyncMock,
                    ) as mock_stop_workers:
                        mock_stop_workers.return_value = mock_worker_results
                        result = await ray_manager.stop_cluster()
                        assert result["status"] == "stopped"
                        assert "worker_nodes" in result
                        assert len(result["worker_nodes"]) == expected_worker_count
                        mock_stop_workers.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_worker_status(self):
        """Test getting worker node status."""
        mock_worker_status = [
            {
                "status": "running",
                "node_name": "worker-1",
                "process_id": 12345,
                "message": "Worker node 'worker-1' is running",
            }
        ]
        expected_total_workers = len(mock_worker_status)
        expected_running_workers = len(
            [w for w in mock_worker_status if w["status"] == "running"]
        )

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray.is_initialized", return_value=True):
                ray_manager = RayManager()
                ray_manager._is_initialized = True
                with patch.object(
                    ray_manager._worker_manager,
                    "get_worker_status",
                    return_value=mock_worker_status,
                ) as mock_get_status:
                    result = await ray_manager.get_worker_status()
                    assert result["status"] == "success"
                    assert result["total_workers"] == expected_total_workers
                    assert result["running_workers"] == expected_running_workers
                    assert "worker_nodes" in result
                    assert len(result["worker_nodes"]) == expected_total_workers
                    mock_get_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_cluster_status_with_workers(self):
        """Test cluster status includes worker information."""
        mock_worker_status = [
            {
                "status": "running",
                "node_name": "worker-1",
                "process_id": 12345,
                "message": "Worker node 'worker-1' is running",
            }
        ]

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray.is_initialized", return_value=True):
                with patch(
                    "ray_mcp.ray_manager.ray.cluster_resources"
                ) as mock_cluster_resources:
                    with patch(
                        "ray_mcp.ray_manager.ray.available_resources"
                    ) as mock_available_resources:
                        with patch("ray_mcp.ray_manager.ray.nodes") as mock_nodes:
                            mock_cluster_resources.return_value = {
                                "CPU": 8,
                                "memory": 16000000000,
                            }
                            mock_available_resources.return_value = {
                                "CPU": 4,
                                "memory": 8000000000,
                            }
                            mock_nodes.return_value = [
                                {"NodeID": "node1", "Alive": True},
                                {"NodeID": "node2", "Alive": True},
                            ]

                            ray_manager = RayManager()
                            ray_manager._is_initialized = True
                            ray_manager._cluster_address = "ray://127.0.0.1:10001"
                            with patch.object(
                                ray_manager._worker_manager,
                                "get_worker_status",
                                return_value=mock_worker_status,
                            ) as mock_get_status:
                                result = await ray_manager.get_cluster_status()
                                assert result["status"] == "running"
                                assert "worker_nodes" in result
                                assert len(result["worker_nodes"]) == 1
                                assert result["worker_nodes"][0]["status"] == "running"
