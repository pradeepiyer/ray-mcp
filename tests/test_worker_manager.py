#!/usr/bin/env python3
"""Tests for the worker manager."""

import asyncio
import subprocess
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from ray_mcp.worker_manager import WorkerManager


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

    def test_build_worker_command_basic(self, worker_manager):
        """Test basic worker command building."""
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

    def test_build_worker_command_with_gpu(self, worker_manager):
        """Test worker command building with GPU configuration."""
        config = {"num_cpus": 4, "num_gpus": 2, "node_name": "gpu-worker"}
        head_node_address = "127.0.0.1:10001"
        command = worker_manager._build_worker_command(config, head_node_address)

        assert "--num-cpus" in command
        assert "4" in command
        assert "--num-gpus" in command
        assert "2" in command
        assert "--node-name" in command
        assert "gpu-worker" in command

    def test_build_worker_command_with_resources(self, worker_manager):
        """Test worker command building with custom resources."""
        config = {
            "num_cpus": 4,
            "node_name": "custom-worker",
            "resources": {"custom_resource": 2, "memory": 8000000000},
        }
        head_node_address = "127.0.0.1:10001"
        command = worker_manager._build_worker_command(config, head_node_address)

        assert "--num-cpus" in command
        assert "4" in command
        assert "--node-name" in command
        assert "custom-worker" in command
        assert "--resources" in command

    def test_build_worker_command_with_node_name(self, worker_manager):
        """Test worker command building with node name."""
        config = {"num_cpus": 2, "node_name": "test-worker"}
        head_node_address = "127.0.0.1:10001"
        command = worker_manager._build_worker_command(config, head_node_address)

        assert "--node-name" in command
        assert "test-worker" in command
        assert "--num-cpus" in command
        assert "2" in command

    @pytest.mark.asyncio
    async def test_start_worker_nodes_success(self, worker_manager):
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
    async def test_stop_all_workers_async_wait_behavior(self, worker_manager):
        """Test async wait behavior during worker stop."""
        # Mock worker process
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None  # Process is running
        mock_process.terminate.return_value = None
        mock_process.wait.return_value = None  # Process stops gracefully

        worker_manager.worker_processes = [mock_process]
        worker_manager.worker_configs = [{"node_name": "worker-1"}]

        # Track when the operation starts and ends to verify it's non-blocking
        start_time = asyncio.get_event_loop().time()

        # Run the stop operation
        result = await worker_manager.stop_all_workers()

        end_time = asyncio.get_event_loop().time()

        # The operation should complete quickly (not block for 5 seconds)
        # Even with the async wait, it should complete in much less than 5 seconds
        assert end_time - start_time < 1.0  # Should complete in under 1 second

        assert len(result) == 1
        assert result[0]["status"] == "stopped"
        assert result[0]["node_name"] == "worker-1"

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


if __name__ == "__main__":
    pytest.main([__file__])
