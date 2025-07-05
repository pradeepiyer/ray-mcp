"""Unit tests for WorkerManager component.

Tests focus on worker process management behavior with 100% mocking.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.fast
class TestWorkerManagerProcessCleanup:
    """Test the simplified process cleanup logic in WorkerManager."""

    @pytest.fixture
    def worker_manager(self):
        """Create a WorkerManager instance for testing."""
        from ray_mcp.worker_manager import WorkerManager

        return WorkerManager()

    async def test_process_termination_scenarios(self, worker_manager):
        """Test multiple scenarios for the simplified process termination logic."""
        # Test 1: Successful termination
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.wait = Mock(return_value=0)

        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=0)

            status, message = await worker_manager._wait_for_process_termination(
                mock_process, "test-worker", timeout=5
            )

            assert status == "force_stopped"
            assert "test-worker" in message
            assert "force stopped" in message

        # Test 2: Timeout but process actually terminated (race condition)
        mock_process.poll.return_value = 0  # Process is terminated
        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                side_effect=asyncio.TimeoutError()
            )

            status, message = await worker_manager._wait_for_process_termination(
                mock_process, "test-worker", timeout=5
            )

            assert status == "force_stopped"
            assert "test-worker" in message

        # Test 3: Timeout with process still running
        mock_process.poll.return_value = None  # Process still running
        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                side_effect=asyncio.TimeoutError()
            )

            status, message = await worker_manager._wait_for_process_termination(
                mock_process, "test-worker", timeout=5
            )

            assert status == "force_stopped"
            assert "may still be running" in message

        # Test 4: Unexpected exception during cleanup
        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                side_effect=RuntimeError("Unexpected error")
            )

            status, message = await worker_manager._wait_for_process_termination(
                mock_process, "test-worker", timeout=5
            )

            assert status == "force_stopped"
            assert "cleanup error" in message

    async def test_stop_all_workers_graceful_and_force_termination(
        self, worker_manager
    ):
        """Test both graceful and force termination workflows in stop_all_workers."""
        # Test graceful termination first
        mock_process_graceful = Mock()
        mock_process_graceful.pid = 12345
        mock_process_graceful.terminate = Mock()
        mock_process_graceful.wait = Mock(return_value=0)

        worker_manager.worker_processes = [mock_process_graceful]
        worker_manager.worker_configs = [{"node_name": "graceful-worker"}]

        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=0)

            results = await worker_manager.stop_all_workers()

            assert len(results) == 1
            assert results[0]["status"] == "stopped"
            assert results[0]["node_name"] == "graceful-worker"
            assert "stopped gracefully" in results[0]["message"]
            assert len(worker_manager.worker_processes) == 0

        # Test force termination when graceful fails
        mock_process_force = Mock()
        mock_process_force.pid = 54321
        mock_process_force.terminate = Mock()
        mock_process_force.kill = Mock()
        mock_process_force.wait = Mock(return_value=0)

        worker_manager.worker_processes = [mock_process_force]
        worker_manager.worker_configs = [{"node_name": "force-worker"}]

        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=0)

            # First asyncio.wait_for (graceful) times out, triggering force termination
            with patch("asyncio.wait_for", side_effect=[asyncio.TimeoutError(), None]):
                results = await worker_manager.stop_all_workers()

                assert len(results) == 1
                assert results[0]["status"] == "force_stopped"
                assert results[0]["node_name"] == "force-worker"
                assert len(worker_manager.worker_processes) == 0

    async def test_stop_all_workers_no_workers(self, worker_manager):
        """Test stop_all_workers when no workers are running."""
        worker_manager.worker_processes = []
        worker_manager.worker_configs = []

        results = await worker_manager.stop_all_workers()

        assert len(results) == 0

    async def test_stop_all_workers_mixed_results(self, worker_manager):
        """Test stop_all_workers with mixed success and failure scenarios."""
        # Create two mock processes with different outcomes
        mock_process1 = Mock()
        mock_process1.pid = 12345
        mock_process1.terminate = Mock()
        mock_process1.wait = Mock(return_value=0)

        mock_process2 = Mock()
        mock_process2.pid = 54321
        mock_process2.terminate = Mock()
        mock_process2.kill = Mock()
        mock_process2.wait = Mock(return_value=0)

        worker_manager.worker_processes = [mock_process1, mock_process2]
        worker_manager.worker_configs = [
            {"node_name": "worker-1"},
            {"node_name": "worker-2"}
        ]

        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=0)

            # First worker terminates gracefully, second requires force termination
            with patch("asyncio.wait_for", side_effect=[None, asyncio.TimeoutError()]):
                results = await worker_manager.stop_all_workers()

                assert len(results) == 2
                assert results[0]["status"] == "stopped"
                assert results[0]["node_name"] == "worker-1"
                assert results[1]["status"] == "force_stopped"
                assert results[1]["node_name"] == "worker-2"
                assert len(worker_manager.worker_processes) == 0 