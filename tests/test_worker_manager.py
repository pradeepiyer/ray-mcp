#!/usr/bin/env python3
"""Tests for WorkerManager functionality."""

import asyncio
import json
import subprocess
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ray_mcp.worker_manager import WorkerManager


@pytest.mark.fast
class TestWorkerManager:
    """Test cases for WorkerManager functionality."""

    @pytest.fixture
    def worker_manager(self):
        return WorkerManager()

    def test_worker_manager_initialization(self, worker_manager):
        """Test WorkerManager initialization."""
        assert worker_manager.worker_processes == []
        assert worker_manager.worker_configs == []

    def test_build_worker_command_basic(self, worker_manager):
        """Test building basic worker command."""
        config = {"num_cpus": 4}
        head_node_address = "127.0.0.1:10001"  # GCS address without ray://
        cmd = worker_manager._build_worker_command(config, head_node_address)

        assert cmd[0] == "ray"
        assert cmd[1] == "start"
        assert "--address" in cmd
        assert head_node_address in cmd
        assert "--num-cpus" in cmd
        assert "4" in cmd
        assert "--block" in cmd
        assert "--disable-usage-stats" in cmd

    def test_build_worker_command_with_gpu(self, worker_manager):
        """Test building worker command with GPU configuration."""
        config = {"num_cpus": 4, "num_gpus": 2}
        head_node_address = "127.0.0.1:10001"  # GCS address without ray://
        cmd = worker_manager._build_worker_command(config, head_node_address)

        assert "--num-cpus" in cmd
        assert "4" in cmd
        assert "--num-gpus" in cmd
        assert "2" in cmd

    def test_build_worker_command_with_memory(self, worker_manager):
        """Test building worker command with memory configuration."""
        config = {"num_cpus": 4, "object_store_memory": 1000000000}  # 1GB
        head_node_address = "127.0.0.1:10001"  # GCS address without ray://
        cmd = worker_manager._build_worker_command(config, head_node_address)

        assert "--object-store-memory" in cmd
        assert "1000000000" in cmd  # Bytes are passed directly

    def test_build_worker_command_with_resources(self, worker_manager):
        """Test building worker command with custom resources."""
        config = {
            "num_cpus": 4,
            "resources": {"custom_resource": 2, "another_resource": 1},
        }
        head_node_address = "127.0.0.1:10001"  # GCS address without ray://
        cmd = worker_manager._build_worker_command(config, head_node_address)

        assert "--resources" in cmd
        # Check that resources are passed as a single JSON string
        resources_index = cmd.index("--resources")
        resources_value = cmd[resources_index + 1]

        # Parse the JSON string and verify contents
        resources_dict = json.loads(resources_value)
        assert resources_dict == {"custom_resource": 2, "another_resource": 1}

    def test_build_worker_command_with_node_name(self, worker_manager):
        """Test building worker command with node name."""
        config = {"num_cpus": 4, "node_name": "test-worker"}
        head_node_address = "127.0.0.1:10001"  # GCS address without ray://
        cmd = worker_manager._build_worker_command(config, head_node_address)

        assert "--node-name" in cmd
        assert "test-worker" in cmd

    @pytest.mark.asyncio
    async def test_start_worker_nodes_success(self, worker_manager):
        """Test starting worker nodes successfully."""
        worker_configs = [
            {"num_cpus": 2, "node_name": "worker-1"},
            {"num_cpus": 4, "node_name": "worker-2"},
        ]
        head_node_address = "127.0.0.1:10001"  # GCS address without ray://

        with patch("subprocess.Popen") as mock_popen:
            # Mock successful process creation
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None  # Process is running
            mock_process.communicate.return_value = ("", "")  # Mock communicate method
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

            # Verify subprocess was called twice
            assert mock_popen.call_count == 2

    @pytest.mark.asyncio
    async def test_start_worker_nodes_failure(self, worker_manager):
        """Test starting worker nodes with failure."""
        worker_configs = [{"num_cpus": 2, "node_name": "worker-1"}]
        head_node_address = "127.0.0.1:10001"  # GCS address without ray://

        with patch("subprocess.Popen") as mock_popen:
            # Mock process creation failure
            mock_popen.side_effect = Exception("Process creation failed")

            result = await worker_manager.start_worker_nodes(
                worker_configs, head_node_address
            )

            assert len(result) == 1
            assert result[0]["status"] == "error"
            assert result[0]["node_name"] == "worker-1"
            assert "Failed to spawn worker process" in result[0]["message"]

    @pytest.mark.asyncio
    async def test_stop_all_workers_success(self, worker_manager):
        """Test stopping all worker nodes successfully."""
        # Mock existing worker processes
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
    async def test_stop_all_workers_already_stopped(self, worker_manager):
        """Test stopping worker nodes that are already stopped."""
        # Mock stopped worker processes
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.poll.return_value = 0  # Process already terminated
        mock_process.terminate.return_value = None
        mock_process.wait.return_value = None  # Process stops gracefully

        worker_manager.worker_processes = [mock_process]
        worker_manager.worker_configs = [{"node_name": "worker-1"}]

        result = await worker_manager.stop_all_workers()

        assert len(result) == 1
        assert result[0]["status"] == "stopped"
        assert result[0]["node_name"] == "worker-1"
        assert "stopped gracefully" in result[0]["message"]

    @pytest.mark.asyncio
    async def test_stop_all_workers_timeout_and_force_kill(self, worker_manager):
        """Test stopping worker nodes with timeout and force kill."""
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
        """Test that stop_all_workers uses async wait and doesn't block the event loop."""
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
        """Test error handling in stop_all_workers."""
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

        # Verify lists are still cleared even on error
        assert len(worker_manager.worker_processes) == 0
        assert len(worker_manager.worker_configs) == 0
