"""Tests for robust state management implementation."""

import asyncio
import threading
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from ray_mcp.ray_manager import RayManager, RayStateManager


class TestRayStateManager:
    """Test the RayStateManager class for robust state management."""

    def test_initial_state(self):
        """Test initial state is properly set."""
        state_manager = RayStateManager()
        state = state_manager.get_state()

        assert state["initialized"] is False
        assert state["cluster_address"] is None
        assert state["gcs_address"] is None
        assert state["dashboard_url"] is None
        assert state["job_client"] is None
        assert state["last_validated"] == 0.0

    def test_update_state(self):
        """Test state updates are atomic."""
        state_manager = RayStateManager()

        # Update state
        state_manager.update_state(
            initialized=True,
            cluster_address="ray://localhost:10001",
            dashboard_url="http://localhost:8265",
        )

        state = state_manager.get_state()
        assert state["initialized"] is True
        assert state["cluster_address"] == "ray://localhost:10001"
        assert state["dashboard_url"] == "http://localhost:8265"

    def test_reset_state(self):
        """Test state reset functionality."""
        state_manager = RayStateManager()

        # Set some state
        state_manager.update_state(
            initialized=True, cluster_address="ray://localhost:10001"
        )

        # Reset state
        state_manager.reset_state()

        state = state_manager.get_state()
        assert state["initialized"] is False
        assert state["cluster_address"] is None
        assert state["gcs_address"] is None
        assert state["dashboard_url"] is None
        assert state["job_client"] is None

    def test_thread_safety(self):
        """Test that state updates are thread-safe."""
        state_manager = RayStateManager()
        results = []

        def update_state_thread(thread_id):
            for i in range(100):
                state_manager.update_state(
                    initialized=True,
                    cluster_address=f"ray://localhost:{10001 + thread_id}",
                    dashboard_url=f"http://localhost:{8265 + thread_id}",
                )
                state = state_manager.get_state()
                results.append((thread_id, state["cluster_address"]))
                time.sleep(0.001)  # Small delay to increase race condition chance

        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=update_state_thread, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify no exceptions occurred and state is consistent
        assert len(results) == 500  # 5 threads * 100 updates each
        final_state = state_manager.get_state()
        assert final_state["initialized"] is True

    @patch("ray_mcp.ray_manager.RAY_AVAILABLE", True)
    @patch("ray_mcp.ray_manager.ray")
    def test_validate_ray_state_success(self, mock_ray):
        """Test successful Ray state validation."""
        state_manager = RayStateManager()

        # Mock Ray to be available and initialized
        mock_ray.is_initialized.return_value = True
        mock_runtime_context = Mock()
        mock_runtime_context.get_node_id.return_value = "test_node_id"
        mock_ray.get_runtime_context.return_value = mock_runtime_context

        # Set cluster address
        state_manager.update_state(cluster_address="ray://localhost:10001")

        # Validate state
        state_manager._validate_and_update_state()

        state = state_manager.get_state()
        assert state["initialized"] is True

    @patch("ray_mcp.ray_manager.RAY_AVAILABLE", False)
    def test_validate_ray_state_ray_unavailable(self):
        """Test Ray state validation when Ray is unavailable."""
        state_manager = RayStateManager()

        # Set some state
        state_manager.update_state(
            initialized=True, cluster_address="ray://localhost:10001"
        )

        # Validate state
        state_manager._validate_and_update_state()

        state = state_manager.get_state()
        assert state["initialized"] is False
        # State should be cleared when validation fails
        assert state["cluster_address"] is None

    @patch("ray_mcp.ray_manager.RAY_AVAILABLE", True)
    @patch("ray_mcp.ray_manager.ray")
    def test_validate_ray_state_not_initialized(self, mock_ray):
        """Test Ray state validation when Ray is not initialized."""
        state_manager = RayStateManager()

        # Mock Ray to be available but not initialized
        mock_ray.is_initialized.return_value = False

        # Set some state
        state_manager.update_state(
            initialized=True, cluster_address="ray://localhost:10001"
        )

        # Validate state
        state_manager._validate_and_update_state()

        state = state_manager.get_state()
        assert state["initialized"] is False

    @patch("ray_mcp.ray_manager.RAY_AVAILABLE", True)
    @patch("ray_mcp.ray_manager.ray")
    def test_validate_ray_state_no_cluster_address(self, mock_ray):
        """Test Ray state validation when no cluster address is set."""
        state_manager = RayStateManager()

        # Mock Ray to be available and initialized
        mock_ray.is_initialized.return_value = True

        # Don't set cluster address
        state_manager.update_state(initialized=True)

        # Validate state
        state_manager._validate_and_update_state()

        state = state_manager.get_state()
        assert state["initialized"] is False

    @patch("ray_mcp.ray_manager.RAY_AVAILABLE", True)
    @patch("ray_mcp.ray_manager.ray")
    def test_validate_ray_state_runtime_context_failure(self, mock_ray):
        """Test Ray state validation when runtime context fails."""
        state_manager = RayStateManager()

        # Mock Ray to be available and initialized
        mock_ray.is_initialized.return_value = True
        mock_ray.get_runtime_context.side_effect = Exception("Runtime context error")

        # Set cluster address
        state_manager.update_state(cluster_address="ray://localhost:10001")

        # Validate state
        state_manager._validate_and_update_state()

        state = state_manager.get_state()
        assert state["initialized"] is False


class TestRayManagerStateManagement:
    """Test the RayManager class with robust state management."""

    def test_initialization(self):
        """Test RayManager initialization with state manager."""
        manager = RayManager()

        assert hasattr(manager, "_state_manager")
        assert isinstance(manager._state_manager, RayStateManager)
        assert manager.is_initialized is False

    def test_is_initialized_property(self):
        """Test the is_initialized property."""
        manager = RayManager()

        # Initially should be False
        assert manager.is_initialized is False

        # Update state
        manager._state_manager.update_state(initialized=True)
        assert manager.is_initialized is True

    def test_backward_compatibility_properties(self):
        """Test backward compatibility with _is_initialized property."""
        manager = RayManager()

        # Test getter
        assert manager._is_initialized is False

        # Test setter
        manager._is_initialized = True
        assert manager._is_initialized is True
        assert manager.is_initialized is True

    def test_update_state_method(self):
        """Test the _update_state method."""
        manager = RayManager()

        manager._update_state(
            initialized=True,
            cluster_address="ray://localhost:10001",
            dashboard_url="http://localhost:8265",
        )

        state = manager._state_manager.get_state()
        assert state["initialized"] is True
        assert state["cluster_address"] == "ray://localhost:10001"
        assert state["dashboard_url"] == "http://localhost:8265"

    @patch("ray_mcp.ray_manager.RAY_AVAILABLE", True)
    @patch("ray_mcp.ray_manager.ray")
    def test_ensure_initialized_success(self, mock_ray):
        """Test _ensure_initialized when Ray is properly initialized."""
        manager = RayManager()

        # Mock Ray to be available and initialized
        mock_ray.is_initialized.return_value = True
        mock_runtime_context = Mock()
        mock_runtime_context.get_node_id.return_value = "test_node_id"
        mock_ray.get_runtime_context.return_value = mock_runtime_context

        # Set state
        manager._state_manager.update_state(
            initialized=True, cluster_address="ray://localhost:10001"
        )

        # Should not raise exception
        manager._ensure_initialized()

    @patch("ray_mcp.ray_manager.RAY_AVAILABLE", False)
    def test_ensure_initialized_failure(self):
        """Test _ensure_initialized when Ray is not initialized."""
        manager = RayManager()

        # Should raise RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            manager._ensure_initialized()

        assert "Ray is not initialized" in str(exc_info.value)
        assert "RAY_AVAILABLE: False" in str(exc_info.value)

    def test_thread_safety_integration(self):
        """Test thread safety of the integrated state management."""
        manager = RayManager()
        results = []

        def check_initialized_thread(thread_id):
            for i in range(50):
                is_init = manager.is_initialized
                results.append((thread_id, is_init))
                time.sleep(0.001)

        def update_state_thread(thread_id):
            for i in range(50):
                manager._update_state(
                    initialized=(i % 2 == 0),
                    cluster_address=f"ray://localhost:{10001 + thread_id}",
                )
                time.sleep(0.001)

        # Start multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=check_initialized_thread, args=(i,))
            threads.append(thread)
            thread.start()

        for i in range(2):
            thread = threading.Thread(target=update_state_thread, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify no exceptions occurred
        assert len(results) == 150  # 3 threads * 50 checks each

    @patch("ray_mcp.ray_manager.RAY_AVAILABLE", True)
    @patch("ray_mcp.ray_manager.ray")
    def test_state_validation_caching(self, mock_ray):
        """Test that state validation is cached appropriately."""
        manager = RayManager()

        # Mock Ray
        mock_ray.is_initialized.return_value = True
        mock_runtime_context = Mock()
        mock_runtime_context.get_node_id.return_value = "test_node_id"
        mock_ray.get_runtime_context.return_value = mock_runtime_context

        # Set initial state
        manager._state_manager.update_state(
            initialized=True, cluster_address="ray://localhost:10001"
        )

        # First call should validate
        assert manager.is_initialized is True

        # Change Ray state to invalid
        mock_ray.is_initialized.return_value = False

        # Should still return cached result (within cache duration)
        assert manager.is_initialized is True

        # Wait for cache to expire and validate again
        manager._state_manager._validation_interval = 0.1
        time.sleep(0.2)

        # Now should reflect the new invalid state
        assert manager.is_initialized is False


class TestStateManagementRecovery:
    """Test state management recovery mechanisms."""

    @patch("ray_mcp.ray_manager.RAY_AVAILABLE", True)
    @patch("ray_mcp.ray_manager.ray")
    def test_state_recovery_after_failure(self, mock_ray):
        """Test state recovery after Ray becomes unavailable and then available again."""
        manager = RayManager()

        # Mock Ray to be available and initialized
        mock_ray.is_initialized.return_value = True
        mock_runtime_context = Mock()
        mock_runtime_context.get_node_id.return_value = "test_node_id"
        mock_ray.get_runtime_context.return_value = mock_runtime_context

        # Set initial state with cluster address
        manager._state_manager.update_state(
            initialized=True, cluster_address="ray://localhost:10001"
        )

        # Force validation to run
        manager._state_manager._validation_interval = 0.1
        time.sleep(0.2)

        assert manager.is_initialized is True

        # Simulate Ray becoming unavailable
        mock_ray.is_initialized.return_value = False
        time.sleep(0.2)
        assert manager.is_initialized is False

        # Simulate Ray becoming available again
        mock_ray.is_initialized.return_value = True
        # Re-set cluster address to simulate re-initialization
        manager._state_manager.update_state(cluster_address="ray://localhost:10001")
        time.sleep(0.2)
        assert manager.is_initialized is True

    def test_state_consistency_under_load(self):
        """Test state consistency under concurrent load."""
        manager = RayManager()

        def concurrent_operations():
            for i in range(100):
                # Read state
                is_init = manager.is_initialized

                # Update state
                manager._update_state(
                    initialized=(i % 2 == 0),
                    cluster_address=f"ray://localhost:{10001 + i}",
                )

                # Read state again
                is_init_after = manager.is_initialized

                # State should be consistent within the same operation
                assert (i % 2 == 0) == is_init_after

                time.sleep(0.001)

        # Run multiple concurrent operations
        threads = []
        for i in range(5):
            thread = threading.Thread(target=concurrent_operations)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()


if __name__ == "__main__":
    pytest.main([__file__])
