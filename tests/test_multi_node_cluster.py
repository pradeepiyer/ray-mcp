#!/usr/bin/env python3
"""Tests for multi-node cluster functionality."""

import asyncio
import json
import subprocess
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

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
    async def test_stop_cluster_with_worker_nodes(self):
        """Test stopping cluster with worker nodes."""
        ray_manager = RayManager()

        # Mock Ray availability and shutdown
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.shutdown.return_value = None

                # Mock subprocess for head node stop
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 0
                    mock_run.return_value.stderr = ""

                    # Mock worker manager
                    with patch.object(
                        ray_manager._worker_manager, "stop_all_workers"
                    ) as mock_stop_workers:
                        mock_stop_workers.return_value = [
                            {"status": "stopped", "node_name": "worker-1"},
                            {"status": "stopped", "node_name": "worker-2"},
                        ]

                        result = await ray_manager.stop_cluster()

                        assert result["status"] == "stopped"
                        assert "Ray cluster stopped successfully" in result["message"]
                        assert result["worker_nodes"] == [
                            {"status": "stopped", "node_name": "worker-1"},
                            {"status": "stopped", "node_name": "worker-2"},
                        ]

                        # Verify worker manager was called
                        mock_stop_workers.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_cluster_without_worker_nodes(self):
        """Test stopping cluster without worker nodes."""
        ray_manager = RayManager()

        # Mock Ray availability and shutdown
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.shutdown.return_value = None

                # Mock subprocess for head node stop
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 0
                    mock_run.return_value.stderr = ""

                    # Mock worker manager
                    with patch.object(
                        ray_manager._worker_manager, "stop_all_workers"
                    ) as mock_stop_workers:
                        mock_stop_workers.return_value = []

                        result = await ray_manager.stop_cluster()

                        assert result["status"] == "stopped"
                        assert "Ray cluster stopped successfully" in result["message"]
                        assert result["worker_nodes"] == []

                        # Verify worker manager was called
                        mock_stop_workers.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_cluster_not_running(self):
        """Test stopping cluster when not running."""
        ray_manager = RayManager()

        # Mock Ray availability
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = False

                result = await ray_manager.stop_cluster()

                assert result["status"] == "not_running"
                assert "Ray cluster is not running" in result["message"]

    @pytest.mark.asyncio
    async def test_stop_cluster_ray_unavailable(self):
        """Test stopping cluster when Ray is not available."""
        ray_manager = RayManager()

        # Mock Ray unavailability
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", False):
            result = await ray_manager.stop_cluster()

            assert result["status"] == "error"
            assert "Ray is not available" in result["message"]

    @pytest.mark.asyncio
    async def test_stop_cluster_exception(self):
        """Test stopping cluster with exception."""
        ray_manager = RayManager()

        # Mock Ray availability and shutdown exception
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.shutdown.side_effect = Exception("Shutdown failed")

                result = await ray_manager.stop_cluster()

                assert result["status"] == "error"
                assert "Shutdown failed" in result["message"]

    @pytest.mark.asyncio
    async def test_worker_manager_integration(self):
        """Test integration between RayManager and WorkerManager."""
        ray_manager = RayManager()

        # Mock Ray availability and initialization
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = False
                mock_ray.init.return_value = Mock(
                    address_info={"address": "ray://127.0.0.1:10001"},
                    dashboard_url="http://127.0.0.1:8265",
                    session_name="test_session",
                )
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "node_123"
                )

                # Mock subprocess for head node startup
                with patch("subprocess.Popen") as mock_popen:
                    mock_process = Mock()
                    mock_process.communicate.return_value = (
                        "Ray runtime started\n--address='127.0.0.1:10001'\nView the Ray dashboard at http://127.0.0.1:8265",
                        "",
                    )
                    mock_process.poll.return_value = 0
                    mock_popen.return_value = mock_process

                    # Mock worker manager methods
                    with patch.object(
                        ray_manager._worker_manager, "start_worker_nodes"
                    ) as mock_start_workers:
                        with patch.object(
                            ray_manager._worker_manager, "stop_all_workers"
                        ) as mock_stop_workers:
                            mock_start_workers.return_value = [
                                {"status": "started", "node_name": "worker-1"},
                                {"status": "started", "node_name": "worker-2"},
                            ]
                            mock_stop_workers.return_value = [
                                {"status": "stopped", "node_name": "worker-1"},
                                {"status": "stopped", "node_name": "worker-2"},
                            ]

                            # Test cluster initialization with workers
                            result = await ray_manager.init_cluster(
                                num_cpus=4,
                                worker_nodes=[
                                    {"num_cpus": 2, "node_name": "worker-1"},
                                    {"num_cpus": 2, "node_name": "worker-2"},
                                ],
                            )

                            assert result["status"] == "started"
                            assert len(result["worker_nodes"]) == 2
                            mock_start_workers.assert_called_once()

                            # Mock Ray as initialized for stop_cluster
                            mock_ray.is_initialized.return_value = True
                            mock_ray.shutdown.return_value = None

                            # Mock subprocess for head node stop
                            with patch("subprocess.run") as mock_run:
                                mock_run.return_value.returncode = 0
                                mock_run.return_value.stderr = ""

                                # Test cluster stop
                                result = await ray_manager.stop_cluster()

                                assert result["status"] == "stopped"
                                assert len(result["worker_nodes"]) == 2
                                mock_stop_workers.assert_called_once()

    @pytest.mark.asyncio
    async def test_worker_config_validation(self):
        """Test worker configuration validation."""
        ray_manager = RayManager()

        # Test with invalid worker configuration
        invalid_worker_config = [
            {"num_cpus": -1, "node_name": "invalid-worker"},  # Negative CPUs
            {"num_cpus": 0, "node_name": "invalid-worker"},  # Zero CPUs
            {
                "invalid_param": "value",
                "node_name": "invalid-worker",
            },  # Invalid parameter
        ]

        # Mock Ray availability and initialization
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = False
                mock_ray.init.return_value = Mock(
                    address_info={"address": "ray://127.0.0.1:10001"},
                    dashboard_url="http://127.0.0.1:8265",
                )

                # Mock subprocess for head node startup
                with patch("subprocess.Popen") as mock_popen:
                    mock_process = Mock()
                    mock_process.communicate.return_value = (
                        "Ray runtime started\n--address='127.0.0.1:10001'\nView the Ray dashboard at http://127.0.0.1:8265",
                        "",
                    )
                    mock_process.poll.return_value = 0
                    mock_popen.return_value = mock_process

                    # Test with invalid worker configuration
                    result = await ray_manager.init_cluster(
                        num_cpus=4, worker_nodes=invalid_worker_config
                    )

                    # Should still succeed but with warnings or filtered config
                    assert result["status"] == "started"

    @pytest.mark.asyncio
    async def test_worker_node_scaling(self):
        """Test worker node scaling functionality."""
        ray_manager = RayManager()

        # Mock Ray availability and initialization
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = False
                mock_ray.init.return_value = Mock(
                    address_info={"address": "ray://127.0.0.1:10001"},
                    dashboard_url="http://127.0.0.1:8265",
                )

                # Mock subprocess for head node startup
                with patch("subprocess.Popen") as mock_popen:
                    mock_process = Mock()
                    mock_process.communicate.return_value = (
                        "Ray runtime started\n--address='127.0.0.1:10001'\nView the Ray dashboard at http://127.0.0.1:8265",
                        "",
                    )
                    mock_process.poll.return_value = 0
                    mock_popen.return_value = mock_process

                    # Mock worker manager for scaling
                    with patch.object(
                        ray_manager._worker_manager, "start_worker_nodes"
                    ) as mock_start_workers:
                        mock_start_workers.return_value = [
                            {"status": "started", "node_name": "worker-1"},
                        ]

                        # Test initial cluster with 1 worker
                        result = await ray_manager.init_cluster(
                            num_cpus=4,
                            worker_nodes=[{"num_cpus": 2, "node_name": "worker-1"}],
                        )

                        assert result["status"] == "started"
                        assert len(result["worker_nodes"]) == 1

                        # Test adding more workers (simulated by re-initializing)
                        mock_start_workers.return_value = [
                            {"status": "started", "node_name": "worker-1"},
                            {"status": "started", "node_name": "worker-2"},
                            {"status": "started", "node_name": "worker-3"},
                        ]

                        result = await ray_manager.init_cluster(
                            num_cpus=4,
                            worker_nodes=[
                                {"num_cpus": 2, "node_name": "worker-1"},
                                {"num_cpus": 2, "node_name": "worker-2"},
                                {"num_cpus": 2, "node_name": "worker-3"},
                            ],
                        )

                        assert result["status"] == "started"
                        assert len(result["worker_nodes"]) == 3

    @pytest.mark.asyncio
    async def test_worker_node_failure_handling(self):
        """Test handling of worker node failures."""
        ray_manager = RayManager()

        # Mock Ray availability and initialization
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = False
                mock_ray.init.return_value = Mock(
                    address_info={"address": "ray://127.0.0.1:10001"},
                    dashboard_url="http://127.0.0.1:8265",
                )

                # Mock subprocess for head node startup
                with patch("subprocess.Popen") as mock_popen:
                    mock_process = Mock()
                    mock_process.communicate.return_value = (
                        "Ray runtime started\n--address='127.0.0.1:10001'\nView the Ray dashboard at http://127.0.0.1:8265",
                        "",
                    )
                    mock_process.poll.return_value = 0
                    mock_popen.return_value = mock_process

                    # Mock worker manager with mixed success/failure
                    with patch.object(
                        ray_manager._worker_manager, "start_worker_nodes"
                    ) as mock_start_workers:
                        mock_start_workers.return_value = [
                            {"status": "started", "node_name": "worker-1"},
                            {
                                "status": "failed",
                                "node_name": "worker-2",
                                "error": "Connection timeout",
                            },
                            {"status": "started", "node_name": "worker-3"},
                        ]

                        result = await ray_manager.init_cluster(
                            num_cpus=4,
                            worker_nodes=[
                                {"num_cpus": 2, "node_name": "worker-1"},
                                {"num_cpus": 2, "node_name": "worker-2"},
                                {"num_cpus": 2, "node_name": "worker-3"},
                            ],
                        )

                        # Should still succeed but with partial worker failures
                        assert result["status"] == "started"
                        assert len(result["worker_nodes"]) == 3
                        assert any(
                            w["status"] == "failed" for w in result["worker_nodes"]
                        )

    @pytest.mark.asyncio
    async def test_worker_node_resource_allocation(self):
        """Test worker node resource allocation."""
        ray_manager = RayManager()

        # Mock Ray availability and initialization
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = False
                mock_ray.init.return_value = Mock(
                    address_info={"address": "ray://127.0.0.1:10001"},
                    dashboard_url="http://127.0.0.1:8265",
                )

                # Mock subprocess for head node startup
                with patch("subprocess.Popen") as mock_popen:
                    mock_process = Mock()
                    mock_process.communicate.return_value = (
                        "Ray runtime started\n--address='127.0.0.1:10001'\nView the Ray dashboard at http://127.0.0.1:8265",
                        "",
                    )
                    mock_process.poll.return_value = 0
                    mock_popen.return_value = mock_process

                    # Mock worker manager
                    with patch.object(
                        ray_manager._worker_manager, "start_worker_nodes"
                    ) as mock_start_workers:
                        mock_start_workers.return_value = [
                            {"status": "started", "node_name": "cpu-worker"},
                            {"status": "started", "node_name": "gpu-worker"},
                        ]

                        # Test with different resource configurations
                        worker_config = [
                            {
                                "num_cpus": 4,
                                "num_gpus": 0,
                                "node_name": "cpu-worker",
                                "memory": 8000000000,  # 8GB
                            },
                            {
                                "num_cpus": 2,
                                "num_gpus": 1,
                                "node_name": "gpu-worker",
                                "memory": 16000000000,  # 16GB
                            },
                        ]

                        result = await ray_manager.init_cluster(
                            num_cpus=4, worker_nodes=worker_config
                        )

                        assert result["status"] == "started"
                        assert len(result["worker_nodes"]) == 2

                        # Verify worker manager was called with correct config
                        mock_start_workers.assert_called_once()
                        call_args = mock_start_workers.call_args[0][0]
                        assert len(call_args) == 2
                        assert call_args[0]["num_cpus"] == 4
                        assert call_args[0]["num_gpus"] == 0
                        assert call_args[1]["num_cpus"] == 2
                        assert call_args[1]["num_gpus"] == 1


if __name__ == "__main__":
    pytest.main([__file__])
