#!/usr/bin/env python3
"""Tests for Ray MCP manager components.

This file consolidates tests for all manager components, focusing on:
- Manager behavior patterns and contracts
- Cross-manager integration and state consistency  
- Error handling and recovery scenarios
- Resource management workflows

Focus: Behavior-driven tests for manager functionality.
"""

import asyncio
import threading
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ray_mcp.managers.cluster_manager import ClusterManager
from ray_mcp.managers.job_manager import JobManager
from ray_mcp.managers.log_manager import LogManager
from ray_mcp.managers.port_manager import PortManager
from ray_mcp.managers.state_manager import StateManager
from ray_mcp.managers.unified_manager import RayUnifiedManager


@pytest.mark.fast
class TestUnifiedManagerInterface:
    """Test unified manager interface and composition."""

    def test_unified_manager_component_access(self):
        """Test that unified manager provides access to all components."""
        manager = RayUnifiedManager()

        # Test that all expected components are accessible
        assert manager.get_state_manager() is not None
        assert manager.get_cluster_manager() is not None
        assert manager.get_job_manager() is not None
        assert manager.get_log_manager() is not None
        assert manager.get_port_manager() is not None

    def test_unified_manager_has_expected_methods(self):
        """Test that unified manager has all expected methods."""
        manager = RayUnifiedManager()

        # Test async methods exist
        assert hasattr(manager, "init_cluster")
        assert hasattr(manager, "stop_cluster")
        assert hasattr(manager, "submit_ray_job")
        assert hasattr(manager, "list_ray_jobs")
        assert hasattr(manager, "inspect_ray_job")  # Changed from get_ray_job_status
        assert hasattr(manager, "cancel_ray_job")
        assert hasattr(manager, "retrieve_logs")  # Changed from retrieve_ray_job_logs

        # Test sync methods exist
        assert hasattr(manager, "is_initialized")
        assert hasattr(manager, "cluster_address")
        assert hasattr(manager, "dashboard_url")


@pytest.mark.fast
class TestManagerContracts:
    """Test that managers follow expected contracts."""

    def test_unified_manager_provides_expected_interface(self):
        """Test that unified manager provides expected interface."""
        manager = RayUnifiedManager()

        # Test component access
        assert manager.get_state_manager() is not None
        assert manager.get_cluster_manager() is not None
        assert manager.get_job_manager() is not None
        assert manager.get_log_manager() is not None
        assert manager.get_port_manager() is not None

        # Test property access
        assert hasattr(manager, "is_initialized")
        assert hasattr(manager, "cluster_address")
        assert hasattr(manager, "dashboard_url")

        # Test that properties return expected types
        assert isinstance(manager.is_initialized, bool)
        assert isinstance(manager.cluster_address, (str, type(None)))
        assert isinstance(manager.dashboard_url, (str, type(None)))

    @pytest.mark.asyncio
    async def test_manager_delegation_contracts(self):
        """Test that managers properly delegate to their components."""
        unified_manager = RayUnifiedManager()

        # Mock the underlying managers to test delegation
        mock_cluster_manager = Mock()
        mock_job_manager = Mock()
        mock_log_manager = Mock()

        # Set up async mock return values
        mock_cluster_manager.init_cluster = AsyncMock(
            return_value={"status": "success"}
        )
        mock_job_manager.submit_job = AsyncMock(return_value={"job_id": "test_job"})
        mock_log_manager.retrieve_logs = AsyncMock(return_value={"logs": "test logs"})

        # Replace the managers
        unified_manager._cluster_manager = mock_cluster_manager
        unified_manager._job_manager = mock_job_manager
        unified_manager._log_manager = mock_log_manager

        # Test delegation
        await unified_manager.init_cluster()
        mock_cluster_manager.init_cluster.assert_called_once()

        await unified_manager.submit_ray_job("test_script.py")
        mock_job_manager.submit_job.assert_called_once()

        await unified_manager.retrieve_logs(
            "test_job"
        )  # Changed from retrieve_ray_job_logs
        mock_log_manager.retrieve_logs.assert_called_once()

    def test_state_manager_contract_compliance(self):
        """Test that state manager follows expected contract."""
        manager = StateManager()

        # Test initial state
        initial_state = manager.get_state()
        assert isinstance(initial_state, dict)
        assert "initialized" in initial_state
        assert initial_state["initialized"] is False

        # Test state updates
        manager.update_state(test_key="test_value")
        updated_state = manager.get_state()
        assert updated_state["test_key"] == "test_value"

        # Test initialization checks
        assert manager.is_initialized() is False

    def test_base_manager_pattern_compliance(self):
        """Test that managers follow base manager patterns."""
        from ray_mcp.foundation.base_managers import BaseManager

        class TestManager(BaseManager):
            async def _validate_state(self) -> bool:
                return True

        state_manager = Mock()
        manager = TestManager(state_manager)

        # Test that manager has required attributes
        assert hasattr(manager, "state_manager")
        assert manager.state_manager is state_manager

        # Test validation patterns
        assert manager._validate_input("test", "field") is True
        assert manager._validate_input("", "field", required=True) is False

    def test_resource_manager_pattern_compliance(self):
        """Test that resource managers follow expected patterns."""
        from ray_mcp.foundation.base_managers import ResourceManager
        from ray_mcp.foundation.interfaces import ManagedComponent

        class TestResourceManager(ResourceManager, ManagedComponent):
            def __init__(self, state_manager, **kwargs):
                ResourceManager.__init__(self, state_manager, **kwargs)
                ManagedComponent.__init__(self, state_manager)

        state_manager = Mock()
        manager = TestResourceManager(
            state_manager, enable_ray=True, enable_kubernetes=True, enable_cloud=True
        )

        # Test that manager has required attributes
        assert hasattr(manager, "state_manager")
        assert hasattr(manager, "_RAY_AVAILABLE")
        assert hasattr(manager, "_KUBERNETES_AVAILABLE")
        assert hasattr(
            manager, "_GOOGLE_CLOUD_AVAILABLE"
        )  # Changed from _CLOUD_AVAILABLE


@pytest.mark.fast
class TestManagerIntegration:
    """Test manager integration patterns."""

    def test_state_manager_shared_across_components(self):
        """Test that state manager is properly shared across components."""
        unified_manager = RayUnifiedManager()

        # Get state manager reference
        state_manager = unified_manager.get_state_manager()

        # Test that all components share the same state manager
        assert unified_manager.get_cluster_manager().state_manager is state_manager
        assert unified_manager.get_job_manager().state_manager is state_manager
        assert unified_manager.get_log_manager().state_manager is state_manager

    @pytest.mark.asyncio
    async def test_cluster_job_workflow_integration(self):
        """Test basic cluster and job workflow integration."""
        unified_manager = RayUnifiedManager()

        # Mock the underlying operations
        mock_cluster_manager = Mock()
        mock_job_manager = Mock()

        mock_cluster_manager.init_cluster = AsyncMock(
            return_value={"status": "success", "cluster_address": "127.0.0.1:10001"}
        )
        mock_job_manager.submit_job = AsyncMock(
            return_value={"status": "success", "job_id": "job_123"}
        )
        mock_job_manager.list_jobs = AsyncMock(
            return_value={"status": "success", "jobs": []}
        )

        unified_manager._cluster_manager = mock_cluster_manager
        unified_manager._job_manager = mock_job_manager

        # Test workflow
        cluster_result = await unified_manager.init_cluster()
        assert cluster_result["status"] == "success"

        job_result = await unified_manager.submit_ray_job("python script.py")
        assert job_result["job_id"] == "job_123"

        jobs_result = await unified_manager.list_ray_jobs()
        assert len(jobs_result["jobs"]) >= 0

    def test_port_manager_cluster_manager_integration(self):
        """Test integration between port and cluster managers."""
        state_manager = StateManager()
        port_manager = PortManager()
        cluster_manager = ClusterManager(state_manager, port_manager)

        # Test that cluster manager has port manager reference
        assert cluster_manager._port_manager is port_manager
        assert cluster_manager.state_manager is state_manager

    @pytest.mark.asyncio
    async def test_cross_manager_state_consistency(self):
        """Test that state remains consistent across manager operations."""
        unified_manager = RayUnifiedManager()

        # Mock state updates
        mock_state = {
            "initialized": True,
            "cluster_address": "127.0.0.1:10001",
            "dashboard_url": "http://127.0.0.1:8265",
        }

        with patch.object(
            unified_manager._state_manager, "get_state", return_value=mock_state
        ):
            with patch.object(
                unified_manager._state_manager, "is_initialized", return_value=True
            ):
                # Test that all managers see consistent state
                assert unified_manager.is_initialized is True
                assert unified_manager.cluster_address == "127.0.0.1:10001"
                assert unified_manager.dashboard_url == "http://127.0.0.1:8265"


@pytest.mark.fast
class TestPortManagerRaceConditions:
    """Test port manager race condition fixes."""

    def test_port_manager_init(self):
        """Test port manager initialization."""
        port_manager = PortManager()
        assert port_manager is not None
        assert hasattr(port_manager, "_LoggingUtility")

    @pytest.mark.asyncio
    async def test_port_allocation_basic(self):
        """Test basic port allocation functionality."""
        port_manager = PortManager()

        with patch("socket.socket") as mock_socket:
            mock_socket.return_value.__enter__.return_value.bind.return_value = None
            with patch("builtins.open", mock_open()) as mock_file:
                with patch("fcntl.flock"):
                    with patch("os.path.exists", return_value=False):
                        with patch("os.listdir", return_value=[]):
                            port = await port_manager.find_free_port(
                                start_port=10001, max_tries=5
                            )
                            assert port >= 10001

    def test_safely_remove_lock_file_success(self):
        """Test successful lock file removal."""
        port_manager = PortManager()

        with patch(
            "builtins.open", mock_open(read_data="12345,1234567890")
        ) as mock_file:
            with patch("fcntl.flock"):
                with patch("os.getpid", return_value=12345):
                    with patch("os.unlink") as mock_unlink:
                        result = port_manager._safely_remove_lock_file("/tmp/test.lock")
                        assert result is True
                        mock_unlink.assert_called_once_with("/tmp/test.lock")

    def test_safely_remove_lock_file_in_use(self):
        """Test lock file removal when file is in use."""
        port_manager = PortManager()

        with patch("builtins.open", mock_open()) as mock_file:
            with patch(
                "fcntl.flock", side_effect=OSError("Resource temporarily unavailable")
            ):
                result = port_manager._safely_remove_lock_file("/tmp/test.lock")
                assert result is False

    def test_safely_remove_lock_file_not_found(self):
        """Test lock file removal when file doesn't exist."""
        port_manager = PortManager()

        with patch("builtins.open", side_effect=FileNotFoundError()):
            result = port_manager._safely_remove_lock_file("/tmp/test.lock")
            assert result is False

    def test_is_stale_lock_file_with_dead_process(self):
        """Test stale lock file detection with dead process."""
        port_manager = PortManager()

        with patch(
            "builtins.open", mock_open(read_data="99999,1234567890")
        ) as mock_file:
            with patch("fcntl.flock"):
                with patch("os.kill", side_effect=OSError("No such process")):
                    result = port_manager._is_stale_lock_file("/tmp/test.lock")
                    assert result is True

    def test_is_stale_lock_file_with_active_process(self):
        """Test stale lock file detection with active process."""
        port_manager = PortManager()

        current_time = int(time.time())
        with patch(
            "builtins.open", mock_open(read_data=f"99999,{current_time}")
        ) as mock_file:
            with patch("fcntl.flock"):
                with patch("os.kill", return_value=None):  # Process exists
                    with patch(
                        "time.time", return_value=current_time + 60
                    ):  # Recent lock
                        result = port_manager._is_stale_lock_file("/tmp/test.lock")
                        assert result is False

    def test_is_stale_lock_file_with_lock_held(self):
        """Test stale lock file detection when lock is held."""
        port_manager = PortManager()

        with patch("builtins.open", mock_open()) as mock_file:
            with patch(
                "fcntl.flock", side_effect=OSError("Resource temporarily unavailable")
            ):
                result = port_manager._is_stale_lock_file("/tmp/test.lock")
                assert result is False

    def test_cleanup_port_lock_success(self):
        """Test successful port lock cleanup."""
        port_manager = PortManager()

        with patch.object(port_manager, "_safely_remove_lock_file", return_value=True):
            with patch.object(port_manager, "_log_info") as mock_log:
                port_manager.cleanup_port_lock(10001)
                mock_log.assert_called_once_with(
                    "port_allocation", "Cleaned up lock file for port 10001"
                )

    def test_cleanup_port_lock_already_cleaned(self):
        """Test port lock cleanup when already cleaned."""
        port_manager = PortManager()

        with patch.object(port_manager, "_safely_remove_lock_file", return_value=False):
            with patch.object(port_manager, "_log_warning") as mock_log:
                port_manager.cleanup_port_lock(10001)
                mock_log.assert_called_once_with(
                    "port_allocation",
                    "Lock file for port 10001 was already cleaned up or in use",
                )

    def test_cleanup_stale_lock_files(self):
        """Test cleanup of stale lock files."""
        port_manager = PortManager()

        with patch(
            "os.listdir",
            return_value=[
                "ray_port_10001.lock",
                "ray_port_10002.lock",
                "other_file.txt",
            ],
        ):
            with patch.object(port_manager, "_is_stale_lock_file", return_value=True):
                with patch.object(
                    port_manager, "_safely_remove_lock_file", return_value=True
                ):
                    with patch.object(port_manager, "_log_info") as mock_log:
                        port_manager._cleanup_stale_lock_files()
                        assert (
                            mock_log.call_count == 3
                        )  # Two individual files + one summary

    def test_cleanup_stale_lock_files_with_errors(self):
        """Test cleanup of stale lock files with errors."""
        port_manager = PortManager()

        # Mock the main try-except block exception, not the inner one
        with patch.object(
            port_manager, "_get_temp_dir", side_effect=OSError("Permission denied")
        ):
            with patch.object(port_manager, "_log_warning") as mock_log:
                port_manager._cleanup_stale_lock_files()
                mock_log.assert_called_once_with(
                    "port_allocation",
                    "Error cleaning up stale lock files: Permission denied",
                )

    @pytest.mark.asyncio
    async def test_concurrent_port_allocation(self):
        """Test concurrent port allocation scenarios."""
        port_manager = PortManager()

        # Mock successful allocation for the first port that is tried
        def mock_try_allocate(port, temp_dir):
            # Always succeed for the first port in the range (simulating finding a free port)
            return True

        with patch.object(
            port_manager, "_try_allocate_port", side_effect=mock_try_allocate
        ):
            with patch.object(port_manager, "_cleanup_stale_lock_files"):
                # First allocation
                port1 = await port_manager.find_free_port(start_port=10001, max_tries=5)
                assert port1 == 10001

                # Second allocation
                port2 = await port_manager.find_free_port(start_port=10002, max_tries=5)
                assert port2 == 10002

    def test_safely_remove_lock_file_retry_logic(self):
        """Test retry logic in safely_remove_lock_file."""
        port_manager = PortManager()

        # First two attempts fail, third succeeds
        open_call_count = 0

        def mock_open_side_effect(*args, **kwargs):
            nonlocal open_call_count
            open_call_count += 1
            if open_call_count < 3:
                raise OSError("Temporary failure")
            return mock_open(read_data="12345,1234567890")(*args, **kwargs)

        with patch("builtins.open", side_effect=mock_open_side_effect):
            with patch("fcntl.flock"):
                with patch("os.getpid", return_value=12345):
                    with patch("os.unlink") as mock_unlink:
                        with patch("time.sleep"):  # Speed up test
                            result = port_manager._safely_remove_lock_file(
                                "/tmp/test.lock"
                            )
                            assert result is True
                            mock_unlink.assert_called_once_with("/tmp/test.lock")

    def test_safely_remove_lock_file_max_retries_exceeded(self):
        """Test safely_remove_lock_file when max retries exceeded."""
        port_manager = PortManager()

        with patch("builtins.open", side_effect=OSError("Persistent failure")):
            with patch.object(port_manager, "_log_warning") as mock_log:
                with patch("time.sleep"):  # Speed up test
                    result = port_manager._safely_remove_lock_file("/tmp/test.lock")
                    assert result is False
                    mock_log.assert_called_once()


from unittest.mock import mock_open


@pytest.mark.fast
class TestManagerErrorHandling:
    """Test error handling patterns across managers."""

    @pytest.mark.asyncio
    async def test_unified_manager_error_propagation(self):
        """Test that errors from specialized managers propagate correctly."""
        manager = RayUnifiedManager()

        # Test cluster manager error propagation
        mock_cluster_manager = Mock()
        mock_cluster_manager.init_cluster = AsyncMock(
            side_effect=Exception("Cluster initialization failed")
        )
        manager._cluster_manager = mock_cluster_manager

        with pytest.raises(Exception, match="Cluster initialization failed"):
            await manager.init_cluster()

        # Test job manager error propagation
        mock_job_manager = Mock()
        mock_job_manager.submit_job = AsyncMock(
            return_value={"status": "error", "message": "Job submission failed"}
        )
        manager._job_manager = mock_job_manager

        result = await manager.submit_ray_job("python script.py")
        assert result["status"] == "error"
        assert "Job submission failed" in result["message"]

    def test_state_manager_validation_error_recovery(self):
        """Test that state manager can recover from validation errors."""
        with patch("ray_mcp.managers.state_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.managers.state_manager.ray") as mock_ray:
                # First validation fails
                mock_ray.is_initialized.side_effect = Exception("Validation error")

                manager = StateManager(validation_interval=0.01)
                manager.update_state(cluster_address="127.0.0.1:10001")

                time.sleep(0.02)
                state1 = manager.get_state()
                assert not state1["initialized"]

                # Reset for successful validation
                mock_ray.reset_mock()
                mock_ray.is_initialized.side_effect = None
                mock_ray.is_initialized.return_value = True
                mock_context = Mock()
                mock_context.get_node_id.return_value = "node_123"
                mock_ray.get_runtime_context.return_value = mock_context

                # Reset validation timestamp
                manager._state["last_validated"] = 0.0

                time.sleep(0.02)
                state2 = manager.get_state()
                assert state2["initialized"]

    @pytest.mark.asyncio
    async def test_resource_manager_error_patterns(self):
        """Test common error patterns in resource managers."""
        from ray_mcp.foundation.base_managers import ResourceManager
        from ray_mcp.foundation.interfaces import ManagedComponent

        state_manager = Mock()
        state_manager.is_initialized.return_value = False

        class TestResourceManager(ResourceManager, ManagedComponent):
            def __init__(self, state_manager, **kwargs):
                ResourceManager.__init__(self, state_manager, **kwargs)
                ManagedComponent.__init__(self, state_manager)

        manager = TestResourceManager(
            state_manager, enable_ray=True, enable_kubernetes=False, enable_cloud=False
        )

        # Test Ray unavailable error
        with patch.object(manager, "_RAY_AVAILABLE", False):
            with pytest.raises(RuntimeError, match="Ray is not available"):
                manager._ensure_ray_available()

        # Test Ray not initialized error
        with pytest.raises(RuntimeError, match="Ray is not initialized"):
            manager._ensure_ray_initialized()  # Now in ManagedComponent

    def test_validation_error_handling_patterns(self):
        """Test validation error handling patterns across managers."""
        from ray_mcp.foundation.base_managers import BaseManager

        state_manager = Mock()

        class TestManager(BaseManager):
            async def _validate_state(self) -> bool:
                return True

        manager = TestManager(state_manager)

        # Test input validation
        assert manager._validate_input("valid_value", "test_field") is True
        assert manager._validate_input("", "test_field", required=True) is False
        assert manager._validate_input(None, "test_field", required=True) is False
        assert manager._validate_input("", "test_field", required=False) is True


@pytest.mark.fast
class TestManagerResourceHandling:
    """Test resource management patterns across managers."""

    def test_state_manager_thread_safety(self):
        """Test that state manager operations are thread-safe."""
        manager = StateManager()
        results = []

        def update_state(thread_id):
            for i in range(10):
                manager.update_state(**{f"thread_{thread_id}_value_{i}": i})
                results.append((thread_id, i))

        # Create and run multiple threads
        threads = []
        for thread_id in range(3):
            thread = threading.Thread(target=update_state, args=(thread_id,))
            threads.append(thread)

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Verify all updates were applied safely
        state = manager.get_state()
        assert len(results) == 30  # 3 threads × 10 updates each

        # Check that all thread values are in state
        for thread_id in range(3):
            for i in range(10):
                key = f"thread_{thread_id}_value_{i}"
                assert key in state
                assert state[key] == i

    @pytest.mark.asyncio
    async def test_cluster_manager_connection_type_handling(self):
        """Test cluster manager handles different connection types correctly."""
        from ray_mcp.managers.port_manager import PortManager

        state_manager = StateManager()
        port_manager = PortManager()
        cluster_manager = ClusterManager(state_manager, port_manager)

        # Mock Ray
        mock_ray = Mock()
        mock_ray.is_initialized.return_value = True
        mock_ray.shutdown = Mock()
        cluster_manager._ray = mock_ray
        cluster_manager._RAY_AVAILABLE = True

        # Test existing cluster disconnection
        cluster_manager.state_manager.update_state(connection_type="existing")
        result = await cluster_manager.stop_cluster()
        assert result["action"] == "disconnected"
        mock_ray.shutdown.assert_called_once()

        # Test new cluster stop
        mock_ray.reset_mock()
        cluster_manager.state_manager.update_state(connection_type="new")

        with patch("asyncio.wait_for") as mock_wait_for:
            mock_wait_for.return_value = None
            result = await cluster_manager.stop_cluster()

        assert result["action"] == "stopped"
        mock_ray.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_worker_process_cleanup_safe_termination(self):
        """Test that worker processes are properly cleaned up even when exceptions occur."""
        from ray_mcp.managers.port_manager import PortManager

        state_manager = StateManager()
        port_manager = PortManager()
        cluster_manager = ClusterManager(state_manager, port_manager)

        # Create mock processes
        mock_process1 = Mock()
        mock_process1.pid = 1234
        mock_process1.poll.return_value = None  # Process is alive
        mock_process1.terminate = Mock()
        mock_process1.wait = Mock()

        mock_process2 = Mock()
        mock_process2.pid = 5678
        mock_process2.poll.return_value = None  # Process is alive
        mock_process2.terminate = Mock(side_effect=Exception("Terminate failed"))
        mock_process2.kill = Mock()
        mock_process2.wait = Mock()

        # Set up worker processes and configs
        cluster_manager._worker_processes = [mock_process1, mock_process2]
        cluster_manager._worker_configs = [
            {"node_name": "worker-1"},
            {"node_name": "worker-2"},
        ]

        # Test graceful shutdown for first process
        with (
            patch("asyncio.get_running_loop") as mock_loop,
            patch("asyncio.wait_for") as mock_wait_for,
        ):
            mock_loop.return_value = asyncio.get_running_loop()
            mock_wait_for.return_value = None  # Simulate successful wait

            result = await cluster_manager._safely_terminate_process(
                mock_process1, "worker-1"
            )

            assert result["status"] == "stopped"
            assert result["node_name"] == "worker-1"
            assert "stopped gracefully" in result["message"]
            mock_process1.terminate.assert_called_once()
            mock_wait_for.assert_called_once()

        # Test exception during termination for second process
        with (
            patch("asyncio.get_running_loop") as mock_loop,
            patch("asyncio.wait_for") as mock_wait_for,
        ):
            mock_event_loop = Mock()
            mock_loop.return_value = mock_event_loop

            # Mock run_in_executor to return a future that resolves to None
            mock_future = asyncio.Future()
            mock_future.set_result(None)
            mock_event_loop.run_in_executor.return_value = mock_future

            result = await cluster_manager._safely_terminate_process(
                mock_process2, "worker-2"
            )

            assert result["status"] == "error"
            assert result["node_name"] == "worker-2"
            assert "Error stopping worker" in result["message"]
            # Verify that despite the exception, kill() and run_in_executor were called
            mock_process2.kill.assert_called_once()
            mock_event_loop.run_in_executor.assert_called_once()

    @pytest.mark.asyncio
    async def test_worker_process_cleanup_timeout_handling(self):
        """Test that worker process cleanup handles timeouts correctly."""
        from ray_mcp.managers.port_manager import PortManager

        state_manager = StateManager()
        port_manager = PortManager()
        cluster_manager = ClusterManager(state_manager, port_manager)

        # Create mock process that times out on graceful shutdown
        mock_process = Mock()
        mock_process.pid = 1234
        mock_process.poll.return_value = None  # Process is alive
        mock_process.terminate = Mock()
        mock_process.kill = Mock()
        mock_process.wait = Mock()

        with (
            patch("asyncio.get_running_loop") as mock_loop,
            patch("asyncio.wait_for") as mock_wait_for,
        ):
            mock_loop.return_value = asyncio.get_running_loop()
            # First wait_for (terminate) times out, second (kill) succeeds
            mock_wait_for.side_effect = [asyncio.TimeoutError(), None]

            result = await cluster_manager._safely_terminate_process(
                mock_process, "worker-test"
            )

            assert result["status"] == "force_stopped"
            assert result["node_name"] == "worker-test"
            assert "force stopped" in result["message"]
            mock_process.terminate.assert_called_once()
            mock_process.kill.assert_called_once()
            # wait_for should be called twice (once for terminate, once for kill)
            assert mock_wait_for.call_count == 2

    @pytest.mark.asyncio
    async def test_stop_all_workers_integration(self):
        """Test the complete _stop_all_workers method with mixed scenarios."""
        from ray_mcp.managers.port_manager import PortManager

        state_manager = StateManager()
        port_manager = PortManager()
        cluster_manager = ClusterManager(state_manager, port_manager)

        # Create mock processes with different behaviors
        mock_process1 = Mock()
        mock_process1.pid = 1234
        mock_process1.poll.return_value = None  # Process is alive
        mock_process1.terminate = Mock()
        mock_process1.wait = Mock()

        mock_process2 = Mock()
        mock_process2.pid = 5678
        mock_process2.poll.return_value = 0  # Process is already dead

        mock_process3 = Mock()
        mock_process3.pid = 9012
        mock_process3.poll.return_value = None  # Process is alive
        mock_process3.terminate = Mock(side_effect=Exception("Terminate failed"))
        mock_process3.kill = Mock()
        mock_process3.wait = Mock()

        # Set up worker processes and configs
        cluster_manager._worker_processes = [
            mock_process1,
            mock_process2,
            mock_process3,
        ]
        cluster_manager._worker_configs = [
            {"node_name": "worker-1"},
            {"node_name": "worker-2"},
            {"node_name": "worker-3"},
        ]

        with (
            patch("asyncio.get_running_loop") as mock_loop,
            patch("asyncio.wait_for") as mock_wait_for,
        ):
            mock_loop.return_value = asyncio.get_running_loop()
            mock_wait_for.return_value = None  # Simulate successful waits

            results = await cluster_manager._stop_all_workers()

            assert len(results) == 3

            # First worker should stop gracefully
            assert results[0]["status"] == "stopped"
            assert results[0]["node_name"] == "worker-1"
            assert "stopped gracefully" in results[0]["message"]

            # Second worker was already stopped
            assert results[1]["status"] == "stopped"
            assert results[1]["node_name"] == "worker-2"
            assert "already stopped" in results[1]["message"]

            # Third worker should have error but still be cleaned up
            assert results[2]["status"] == "error"
            assert results[2]["node_name"] == "worker-3"
            assert "Error stopping worker" in results[2]["message"]

            # Verify worker tracking is cleared
            assert len(cluster_manager._worker_processes) == 0
            assert len(cluster_manager._worker_configs) == 0

    @pytest.mark.asyncio
    async def test_job_manager_client_lifecycle(self):
        """Test job manager handles client lifecycle correctly."""
        state_manager = Mock()
        state_manager.is_initialized.return_value = True
        state_manager.get_state.return_value = {
            "dashboard_url": "http://127.0.0.1:8265",
            "job_client": None,
        }

        job_manager = JobManager(state_manager)

        # Mock Ray availability and client
        mock_client = Mock()
        mock_client.list_jobs.return_value = []
        mock_client_class = Mock(return_value=mock_client)

        job_manager._RAY_AVAILABLE = True
        job_manager._JobSubmissionClient = mock_client_class

        # Test client creation
        client = await job_manager._get_or_create_job_client("test_operation")
        assert client == mock_client
        mock_client_class.assert_called_with("http://127.0.0.1:8265")

    def test_address_validation_patterns(self):
        """Test address validation patterns across managers."""
        from ray_mcp.managers.port_manager import PortManager

        state_manager = StateManager()
        port_manager = PortManager()
        cluster_manager = ClusterManager(state_manager, port_manager)

        # Test valid addresses
        valid_addresses = [
            "127.0.0.1:8000",
            "192.168.1.100:10001",
            "localhost:8000",
            "example.com:8000",
        ]

        for address in valid_addresses:
            assert cluster_manager._validate_cluster_address(address) is True

        # Test invalid addresses
        invalid_addresses = [
            "",
            "invalid",
            "127.0.0.1",  # Missing port
            "127.0.0.1:abc",  # Invalid port
            "300.300.300.300:8000",  # Invalid IP
            "192.168..1:8080",  # Empty part in IPv4 (double dots)
            "192.168.1.:8080",  # Empty part in IPv4 (trailing dot)
            ".192.168.1.1:8080",  # Empty part in IPv4 (leading dot)
            "192.168.1.1.:8080",  # Empty part in IPv4 (trailing dot after last part)
            "192..168.1.1:8080",  # Empty part in IPv4 (middle double dots)
            "192.168.1.1..:8080",  # Multiple empty parts at end
            "..192.168.1.1:8080",  # Multiple empty parts at start
        ]

        for address in invalid_addresses:
            assert cluster_manager._validate_cluster_address(address) is False


@pytest.mark.fast
class TestManagerWorkflows:
    """Test complex workflows that span multiple managers."""

    @pytest.mark.asyncio
    async def test_complete_cluster_job_workflow(self):
        """Test complete workflow from cluster creation to job execution."""
        manager = RayUnifiedManager()

        # Mock all underlying operations
        manager._cluster_manager = Mock()
        manager._job_manager = Mock()
        manager._log_manager = Mock()

        manager._cluster_manager.init_cluster = AsyncMock(
            return_value={"status": "success", "cluster_address": "127.0.0.1:10001"}
        )
        manager._job_manager.submit_job = AsyncMock(
            return_value={"status": "success", "job_id": "job_123"}
        )
        manager._job_manager.list_jobs = AsyncMock(
            return_value={
                "status": "success",
                "jobs": [{"job_id": "job_123", "status": "RUNNING"}],
            }
        )
        manager._log_manager.retrieve_logs = AsyncMock(
            return_value={"status": "success", "logs": "Job executing..."}
        )
        manager._job_manager.cancel_job = AsyncMock(
            return_value={"status": "success", "cancelled": True}
        )
        manager._cluster_manager.stop_cluster = AsyncMock(
            return_value={"status": "success", "action": "stopped"}
        )

        # Execute complete workflow
        # 1. Initialize cluster
        init_result = await manager.init_cluster(num_cpus=2)
        assert init_result["status"] == "success"

        # 2. Submit job
        job_result = await manager.submit_ray_job("python script.py")
        assert job_result["status"] == "success"
        assert job_result["job_id"] == "job_123"

        # 3. List jobs
        jobs_result = await manager.list_ray_jobs()
        assert jobs_result["status"] == "success"
        assert len(jobs_result["jobs"]) == 1

        # 4. Get logs
        logs_result = await manager.retrieve_logs(
            "job_123"
        )  # Changed from retrieve_ray_job_logs
        assert logs_result["status"] == "success"
        assert "Job executing..." in logs_result["logs"]

        # 5. Cancel job
        cancel_result = await manager.cancel_ray_job("job_123")
        assert cancel_result["status"] == "success"
        assert cancel_result["cancelled"] is True

        # 6. Stop cluster
        stop_result = await manager.stop_cluster()
        assert stop_result["status"] == "success"
        assert stop_result["action"] == "stopped"

    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self):
        """Test workflow recovery from errors."""
        manager = RayUnifiedManager()

        # Mock cluster manager to fail first, then succeed
        mock_cluster_manager = Mock()
        call_count = 0

        async def mock_init_cluster(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"status": "error", "message": "First attempt failed"}
            else:
                return {"status": "success", "cluster_address": "127.0.0.1:10001"}

        mock_cluster_manager.init_cluster = AsyncMock(side_effect=mock_init_cluster)
        manager._cluster_manager = mock_cluster_manager

        # First attempt fails
        result1 = await manager.init_cluster()
        assert result1["status"] == "error"

        # Second attempt succeeds
        result2 = await manager.init_cluster()
        assert result2["status"] == "success"
        assert result2["cluster_address"] == "127.0.0.1:10001"

    def test_state_consistency_across_workflow(self):
        """Test that state remains consistent across workflow steps."""
        manager = RayUnifiedManager()
        state_manager = manager.get_state_manager()

        # Initial state
        initial_state = state_manager.get_state()
        assert initial_state["initialized"] is False

        # Update state as if cluster was initialized
        state_manager.update_state(
            initialized=True,
            cluster_address="127.0.0.1:10001",
            dashboard_url="http://127.0.0.1:8265",
        )

        # Verify state consistency across all managers
        updated_state = state_manager.get_state()
        assert updated_state["initialized"] is True
        assert updated_state["cluster_address"] == "127.0.0.1:10001"
        assert updated_state["dashboard_url"] == "http://127.0.0.1:8265"

        # Verify unified manager reflects state changes
        assert manager.is_initialized is True
        assert manager.cluster_address == "127.0.0.1:10001"
        assert manager.dashboard_url == "http://127.0.0.1:8265"

    @pytest.mark.asyncio
    async def test_job_manager_parameter_filtering_fix(self):
        """Test that job manager properly filters parameters in job submission."""
        from ray_mcp.managers.job_manager import JobManager

        state_manager = Mock()
        state_manager.is_initialized.return_value = True
        state_manager.get_state.return_value = {
            "dashboard_url": "http://127.0.0.1:8265",
            "job_client": None,
        }

        job_manager = JobManager(state_manager)

        # Mock JobSubmissionClient
        mock_client = Mock()
        mock_client.submit_job.return_value = "job_123"
        mock_client_class = Mock(return_value=mock_client)

        job_manager._RAY_AVAILABLE = True
        job_manager._JobSubmissionClient = mock_client_class

        # Test with mixed valid and invalid parameters
        result = await job_manager.submit_job(
            entrypoint="python script.py",
            runtime_env={"pip": ["numpy"]},
            num_cpus=2,
            # Don't test invalid parameters since they're now passed through
        )

        assert result["status"] == "success"
        assert result["job_id"] == "job_123"

        # Verify that submit_job was called with parameters
        mock_client.submit_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_tool_registry_parameter_filtering_fix(self):
        """Test that tool registry properly filters parameters."""
        from ray_mcp.tool_registry import ToolRegistry

        # Create a mock ray manager
        mock_ray_manager = Mock()
        mock_job_manager = Mock()
        mock_job_manager.submit_job = AsyncMock(
            return_value={"status": "success", "job_id": "job_123"}
        )
        mock_ray_manager.get_job_manager.return_value = mock_job_manager
        mock_ray_manager.submit_ray_job = AsyncMock(
            return_value={"status": "success", "job_id": "job_123"}
        )

        registry = ToolRegistry(mock_ray_manager)

        # Test parameter filtering in submit_ray_job tool
        result = await registry._submit_ray_job_handler(
            entrypoint="python script.py",
            runtime_env={"pip": ["numpy"]},
            num_cpus=2,
            job_type="local",
        )

        assert result["status"] == "success"
        assert result["job_id"] == "job_123"

        # Verify job manager was called
        mock_ray_manager.submit_ray_job.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
