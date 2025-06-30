#!/usr/bin/env python3
"""Tests for the worker manager."""

import asyncio
import subprocess
import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from ray_mcp.ray_manager import RayManager
from ray_mcp.worker_manager import WorkerManager
from tests.conftest import mock_cluster_startup


@pytest.mark.fast
class TestWorkerManager:
    """Test cases for WorkerManager."""

    @pytest.fixture
    def worker_manager(self):
        """Create a WorkerManager instance for testing."""
        return WorkerManager()

    def test_worker_manager_initialization(self, worker_manager):
        """Test WorkerManager initialization."""
        assert worker_manager is not None
        assert hasattr(worker_manager, "start_worker_nodes")
        assert hasattr(worker_manager, "stop_all_workers")
        assert worker_manager.worker_processes == []
        assert worker_manager.worker_configs == []

    def test_build_worker_command_comprehensive(self, worker_manager):
        """Test worker command building with various configurations."""
        # Test basic configuration
        config = {"num_cpus": 4, "node_name": "worker-1"}
        head_node_address = "127.0.0.1:10001"
        command = worker_manager._build_worker_command(config, head_node_address)

        assert "ray" in command
        assert "start" in command
        assert "--address" in command
        assert head_node_address in command
        assert "--num-cpus" in command
        assert "4" in command
        assert "--node-name" in command
        assert "worker-1" in command

        # Test with GPU configuration
        config = {"num_cpus": 4, "num_gpus": 2, "node_name": "gpu-worker"}
        command = worker_manager._build_worker_command(config, head_node_address)
        assert "--num-gpus" in command
        assert "2" in command

        # Test with custom resources
        config = {
            "num_cpus": 4,
            "node_name": "custom-worker",
            "resources": {"custom_resource": 2, "memory": 8000000000},
        }
        command = worker_manager._build_worker_command(config, head_node_address)
        assert "--resources" in command

    @pytest.mark.asyncio
    async def test_start_worker_nodes_success(
        self, worker_manager, mock_cluster_startup
    ):
        """Test successful worker node startup."""
        worker_configs = [
            {"num_cpus": 2, "node_name": "worker-1"},
            {"num_cpus": 4, "num_gpus": 1, "node_name": "worker-2"},
        ]
        head_node_address = "127.0.0.1:10001"

        # Mock subprocess.Popen for worker processes
        with patch("subprocess.Popen") as mock_popen:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None  # Process still running
            mock_popen.return_value = mock_process

            result = await worker_manager.start_worker_nodes(
                worker_configs, head_node_address
            )

            assert len(result) == 2
            assert result[0]["status"] == "started"
            assert result[0]["node_name"] == "worker-1"
            assert result[0]["process_id"] == 12345
            assert result[1]["status"] == "started"
            assert result[1]["node_name"] == "worker-2"
            assert result[1]["process_id"] == 12345

            # Verify subprocess.Popen was called twice
            assert mock_popen.call_count == 2

    @pytest.mark.asyncio
    async def test_start_worker_nodes_failure(self, worker_manager):
        """Test worker node startup failure."""
        worker_configs = [{"num_cpus": 2, "node_name": "worker-1"}]
        head_node_address = "127.0.0.1:10001"

        # Mock subprocess.Popen to simulate failure
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.side_effect = subprocess.SubprocessError(
                "Failed to start worker"
            )

            result = await worker_manager.start_worker_nodes(
                worker_configs, head_node_address
            )

            assert len(result) == 1
            assert result[0]["status"] == "error"
            assert result[0]["node_name"] == "worker-1"
            # Accept either the generic or specific error message
            assert (
                "Failed to spawn worker process" in result[0]["message"]
                or "Failed to start worker" in result[0]["message"]
            )

    @pytest.mark.asyncio
    async def test_stop_all_workers_success(self, worker_manager):
        """Test successful stopping of all worker nodes."""
        # Mock worker processes
        mock_process1 = Mock()
        mock_process1.pid = 12345
        mock_process1.poll.return_value = None  # Process is running
        mock_process1.terminate.return_value = None
        mock_process1.wait.return_value = None  # Process stops gracefully

        mock_process2 = Mock()
        mock_process2.pid = 12346
        mock_process2.poll.return_value = None  # Process is running
        mock_process2.terminate.return_value = None
        mock_process2.wait.return_value = None  # Process stops gracefully

        worker_manager.worker_processes = [mock_process1, mock_process2]
        worker_manager.worker_configs = [
            {"node_name": "worker-1"},
            {"node_name": "worker-2"},
        ]

        result = await worker_manager.stop_all_workers()

        assert len(result) == 2
        assert result[0]["status"] == "stopped"
        assert result[0]["node_name"] == "worker-1"
        assert result[1]["status"] == "stopped"
        assert result[1]["node_name"] == "worker-2"

        # Verify processes were terminated
        mock_process1.terminate.assert_called_once()
        mock_process2.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_all_workers_timeout_and_force_kill(self, worker_manager):
        """Test worker stop with timeout and force kill."""
        # Mock worker process that times out during graceful shutdown
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None  # Process is running
        mock_process.terminate.return_value = None
        # First wait call times out, second wait call succeeds
        mock_process.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="ray start", timeout=5),
            None,  # Force kill wait succeeds
        ]

        worker_manager.worker_processes = [mock_process]
        worker_manager.worker_configs = [{"node_name": "worker-1"}]

        result = await worker_manager.stop_all_workers()

        assert len(result) == 1
        assert result[0]["status"] == "force_stopped"
        assert result[0]["node_name"] == "worker-1"
        assert "force stopped" in result[0]["message"]
        assert result[0]["process_id"] == 12345

        # Verify terminate was called, then kill was called
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
        # Verify wait was called twice (once for graceful, once for force kill)
        assert mock_process.wait.call_count == 2

    @pytest.mark.asyncio
    async def test_stop_all_workers_error_handling(self, worker_manager):
        """Test error handling during worker stop."""
        # Mock worker process that raises an exception during termination
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None  # Process is running
        mock_process.terminate.side_effect = Exception("Termination failed")

        worker_manager.worker_processes = [mock_process]
        worker_manager.worker_configs = [{"node_name": "worker-1"}]

        result = await worker_manager.stop_all_workers()

        assert len(result) == 1
        assert result[0]["status"] == "error"
        assert result[0]["node_name"] == "worker-1"
        assert "Failed to stop worker" in result[0]["message"]

        # Verify failing worker is still tracked for retry
        assert worker_manager.worker_processes == [mock_process]
        assert worker_manager.worker_configs == [{"node_name": "worker-1"}]


@pytest.mark.fast
class TestMultiNodeIntegration:
    """Test multi-node cluster integration between RayManager and WorkerManager."""

    @pytest.fixture
    def ray_manager(self):
        """Create a RayManager instance for testing."""
        return RayManager()

    @pytest.mark.asyncio
    async def test_cluster_stop_with_workers(self, ray_manager):
        """Test stopping cluster with worker nodes."""
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
                        ray_manager._worker_manager,
                        "stop_all_workers",
                        new_callable=AsyncMock,
                    ) as mock_stop_workers:
                        mock_stop_workers.return_value = [
                            {"status": "stopped", "node_name": "worker-1"},
                            {"status": "stopped", "node_name": "worker-2"},
                        ]

                        result = await ray_manager.stop_cluster()

                        assert result["status"] == "success"
                        assert result["result_type"] == "stopped"
                        assert "Ray cluster stopped successfully" in result["message"]
                        assert result["worker_nodes"] == [
                            {"status": "stopped", "node_name": "worker-1"},
                            {"status": "stopped", "node_name": "worker-2"},
                        ]

                        # Verify worker manager was called
                        mock_stop_workers.assert_called_once()

    @pytest.mark.asyncio
    async def test_worker_manager_integration(self, ray_manager, mock_cluster_startup):
        """Test complete integration between RayManager and WorkerManager."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = False
                mock_ray.init.return_value = Mock(
                    address_info={"address": "127.0.0.1:10001"},
                    dashboard_url="http://127.0.0.1:8265",
                )
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "node_123"
                )
                with patch("subprocess.Popen") as mock_popen:
                    mock_process = Mock()
                    mock_process.communicate.return_value = (
                        "Ray runtime started\n--address='127.0.0.1:10001'\nView the Ray dashboard at http://127.0.0.1:8265",
                        "",
                    )
                    mock_process.poll.return_value = 0
                    mock_popen.return_value = mock_process
                    with patch.object(
                        RayManager,
                        "_initialize_job_client_with_retry",
                        new_callable=AsyncMock,
                    ) as mock_init_job_client:
                        mock_init_job_client.return_value = None
                        with patch.object(
                            RayManager,
                            "_communicate_with_timeout",
                            new_callable=AsyncMock,
                        ) as mock_communicate:
                            mock_communicate.return_value = (
                                "Ray runtime started\n--address='127.0.0.1:20000'\nView the Ray dashboard at http://127.0.0.1:8265",
                                "",
                            )
                            with patch.object(
                                ray_manager._worker_manager,
                                "start_worker_nodes",
                                new_callable=AsyncMock,
                            ) as mock_start_workers:
                                with patch.object(
                                    ray_manager._worker_manager,
                                    "stop_all_workers",
                                    new_callable=AsyncMock,
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
                                        head_node_port=20000,
                                        dashboard_port=8265,
                                        worker_nodes=[
                                            {"num_cpus": 2, "node_name": "worker-1"},
                                            {"num_cpus": 2, "node_name": "worker-2"},
                                        ],
                                    )
                                    assert result["status"] == "success"
                                    assert result.get("result_type") == "started"
                                    assert len(result["worker_nodes"]) == 2
                                    mock_start_workers.assert_called_once()

                                    # Test cluster shutdown with workers
                                    mock_ray.is_initialized.return_value = True
                                    mock_ray.shutdown.return_value = None
                                    with patch("subprocess.run") as mock_run:
                                        mock_run.return_value.returncode = 0
                                        mock_run.return_value.stderr = ""

                                        result = await ray_manager.stop_cluster()
                                        assert result["status"] == "success"
                                        assert result["result_type"] == "stopped"
                                        assert len(result["worker_nodes"]) == 2
                                        mock_stop_workers.assert_called_once()

    @pytest.mark.asyncio
    async def test_worker_config_validation_integration(
        self, ray_manager, mock_cluster_startup
    ):
        """Test worker configuration validation during cluster initialization."""
        # Test with both valid and invalid worker configs
        mixed_worker_config = [
            {"num_cpus": 2, "node_name": "valid-worker"},
            {"num_cpus": -1, "node_name": "invalid-worker-1"},  # Invalid negative CPUs
            {"num_cpus": 4, "node_name": "valid-worker-2"},
            {
                "invalid_param": "value",
                "node_name": "invalid-worker-2",
            },  # Invalid param
        ]

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = False
                mock_ray.init.return_value = Mock(
                    address_info={"address": "127.0.0.1:10001"},
                    dashboard_url="http://127.0.0.1:8265",
                )
                with patch("subprocess.Popen") as mock_popen:
                    mock_process = Mock()
                    mock_process.communicate.return_value = (
                        "Ray runtime started\n--address='127.0.0.1:10001'\nView the Ray dashboard at http://127.0.0.1:8265",
                        "",
                    )
                    mock_process.poll.return_value = 0
                    mock_popen.return_value = mock_process
                    with patch.object(
                        RayManager,
                        "_initialize_job_client_with_retry",
                        new_callable=AsyncMock,
                    ) as mock_init_job_client:
                        mock_init_job_client.return_value = None
                        with patch.object(
                            RayManager,
                            "_communicate_with_timeout",
                            new_callable=AsyncMock,
                        ) as mock_communicate:
                            mock_communicate.return_value = (
                                "Ray runtime started\n--address='127.0.0.1:20000'\nView the Ray dashboard at http://127.0.0.1:8265",
                                "",
                            )
                            with patch.object(
                                ray_manager._worker_manager,
                                "start_worker_nodes",
                                new_callable=AsyncMock,
                            ) as mock_start_workers:
                                # Even with invalid configs, cluster should still start (validation is lenient)
                                result = await ray_manager.init_cluster(
                                    num_cpus=4,
                                    head_node_port=20000,
                                    dashboard_port=8265,
                                    worker_nodes=mixed_worker_config,
                                )
                                assert result["status"] == "success"
                                assert result.get("result_type") == "started"

    @pytest.mark.asyncio
    async def test_worker_node_scaling(self, ray_manager):
        """Test worker node scaling functionality."""
        # Mock Ray availability and initialization
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = False
                mock_ray.init.return_value = Mock(
                    address_info={"address": "127.0.0.1:10001"},
                    dashboard_url="http://127.0.0.1:8265",
                )
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "node_123"
                )

                with patch("subprocess.Popen") as mock_popen:
                    mock_process = Mock()
                    mock_process.communicate.return_value = (
                        "Ray runtime started\n--address='127.0.0.1:10001'\nView the Ray dashboard at http://127.0.0.1:8265",
                        "",
                    )
                    mock_process.poll.return_value = 0
                    mock_popen.return_value = mock_process

                    # Mock asyncio.sleep to avoid actual delays
                    with patch("asyncio.sleep"):
                        # Mock _initialize_job_client_with_retry to avoid retry delays
                        with patch.object(
                            RayManager,
                            "_initialize_job_client_with_retry",
                            new_callable=AsyncMock,
                        ) as mock_init_job_client:
                            mock_init_job_client.return_value = None
                            with patch.object(
                                RayManager,
                                "_communicate_with_timeout",
                                new_callable=AsyncMock,
                            ) as mock_communicate:
                                mock_communicate.return_value = (
                                    "Ray runtime started\n--address='127.0.0.1:20000'\nView the Ray dashboard at http://127.0.0.1:8265",
                                    "",
                                )
                                # Mock worker manager for scaling
                                with patch.object(
                                    ray_manager._worker_manager,
                                    "start_worker_nodes",
                                    new_callable=AsyncMock,
                                ) as mock_start_workers:
                                    # Test initial cluster with 1 worker
                                    mock_start_workers.return_value = [
                                        {"status": "started", "node_name": "worker-1"},
                                    ]

                                    result = await ray_manager.init_cluster(
                                        num_cpus=4,
                                        head_node_port=20000,
                                        dashboard_port=8265,
                                        worker_nodes=[
                                            {"num_cpus": 2, "node_name": "worker-1"}
                                        ],
                                    )

                                    assert result["status"] == "success"
                                    assert result.get("result_type") == "started"
                                    assert len(result["worker_nodes"]) == 1

                                    # Test scaling up to 3 workers
                                    mock_start_workers.return_value = [
                                        {"status": "started", "node_name": "worker-1"},
                                        {"status": "started", "node_name": "worker-2"},
                                        {"status": "started", "node_name": "worker-3"},
                                    ]

                                    result = await ray_manager.init_cluster(
                                        num_cpus=4,
                                        head_node_port=20000,
                                        dashboard_port=8265,
                                        worker_nodes=[
                                            {"num_cpus": 2, "node_name": "worker-1"},
                                            {"num_cpus": 2, "node_name": "worker-2"},
                                            {"num_cpus": 2, "node_name": "worker-3"},
                                        ],
                                    )

                                    assert result["status"] == "success"
                                    assert result.get("result_type") == "started"
                                    assert len(result["worker_nodes"]) == 3


if __name__ == "__main__":
    pytest.main([__file__])
