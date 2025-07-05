"""Unit tests for RayStateManager component.

Tests focus on behavior verification with 100% mocking.
"""

import threading
import time
from unittest.mock import Mock, patch

import pytest

from ray_mcp.core.state_manager import RayStateManager


@pytest.mark.fast
class TestRayStateManagerCore:
    """Test core state management functionality."""

    def test_initial_state_is_correct(self):
        """Test that the initial state contains the expected default values."""
        manager = RayStateManager()
        state = manager.get_state()

        # Check that all expected keys exist with correct initial values
        expected_keys = {
            "initialized",
            "cluster_address",
            "gcs_address",
            "dashboard_url",
            "job_client",
            "connection_type",
            "last_validated",
        }
        assert set(state.keys()) == expected_keys

        # Check initial values
        assert state["initialized"] is False
        assert state["cluster_address"] is None
        assert state["gcs_address"] is None
        assert state["dashboard_url"] is None
        assert state["job_client"] is None
        assert state["connection_type"] is None
        assert state["last_validated"] == 0.0

    def test_update_state_modifies_values(self):
        """Test that update_state correctly modifies state values."""
        manager = RayStateManager()

        manager.update_state(
            initialized=True,
            cluster_address="127.0.0.1:10001",
            custom_field="test_value",
        )

        state = manager.get_state()
        assert state["initialized"] is True
        assert state["cluster_address"] == "127.0.0.1:10001"
        assert state["custom_field"] == "test_value"
        assert state["last_validated"] > 0  # Should be updated

    def test_update_state_updates_timestamp(self):
        """Test that update_state updates the last_validated timestamp."""
        manager = RayStateManager()
        original_time = manager.get_state()["last_validated"]

        # Small delay to ensure timestamp difference
        time.sleep(0.01)
        manager.update_state(test_field="value")

        new_time = manager.get_state()["last_validated"]
        assert new_time > original_time

    def test_reset_state_clears_all_custom_values(self):
        """Test that reset_state clears all custom values and resets to defaults."""
        manager = RayStateManager()

        # Add custom state
        manager.update_state(
            initialized=True,
            cluster_address="127.0.0.1:10001",
            custom_field="test",
            another_field=42,
        )

        # Reset state
        manager.reset_state()

        state = manager.get_state()
        assert not state["initialized"]
        assert state["cluster_address"] is None
        assert state["last_validated"] == 0.0
        assert "custom_field" not in state
        assert "another_field" not in state

    @pytest.mark.parametrize("initialized_value", [True, False])
    def test_is_initialized_reflects_state(self, initialized_value):
        """Test that is_initialized correctly reflects the initialized state."""
        manager = RayStateManager()
        manager.update_state(initialized=initialized_value)

        assert manager.is_initialized() == initialized_value


@pytest.mark.fast
class TestRayStateManagerThreadSafety:
    """Test thread safety of state management operations."""

    def test_concurrent_updates_are_thread_safe(self):
        """Test that concurrent state updates don't cause race conditions."""
        manager = RayStateManager()
        results = []

        def update_state(thread_id):
            """Update state from a specific thread."""
            for i in range(10):
                manager.update_state(**{f"thread_{thread_id}_value_{i}": i})
                results.append((thread_id, i))

        # Create multiple threads
        threads = []
        for thread_id in range(5):
            thread = threading.Thread(target=update_state, args=(thread_id,))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Verify all updates were applied
        state = manager.get_state()
        assert len(results) == 50  # 5 threads × 10 updates each

        # Check that all thread values are in state
        for thread_id in range(5):
            for i in range(10):
                key = f"thread_{thread_id}_value_{i}"
                assert key in state
                assert state[key] == i

    def test_concurrent_reset_and_update_operations(self):
        """Test that reset and update operations work correctly when concurrent."""
        manager = RayStateManager()

        def continuous_updates():
            """Continuously update state."""
            for i in range(20):
                manager.update_state(counter=i)
                time.sleep(0.001)

        def reset_operation():
            """Reset state after delay."""
            time.sleep(0.01)  # Let some updates happen first
            manager.reset_state()

        # Start update thread
        update_thread = threading.Thread(target=continuous_updates)
        reset_thread = threading.Thread(target=reset_operation)

        update_thread.start()
        reset_thread.start()

        update_thread.join()
        reset_thread.join()

        # State should be in a consistent state (either reset or with final update)
        state = manager.get_state()
        assert isinstance(state, dict)
        assert "initialized" in state  # Core field should always exist


@pytest.mark.fast
class TestRayStateManagerValidation:
    """Test state validation functionality."""

    @patch("ray_mcp.core.state_manager.RAY_AVAILABLE", True)
    @patch("ray_mcp.core.state_manager.ray")
    def test_validation_with_ray_not_initialized(self, mock_ray):
        """Test validation when Ray is not initialized."""
        mock_ray.is_initialized.return_value = False

        manager = RayStateManager(validation_interval=0.01)  # Fast validation
        manager.update_state(cluster_address="127.0.0.1:10001")

        # Wait for validation to trigger
        time.sleep(0.02)
        state = manager.get_state()

        assert not state["initialized"]
        mock_ray.is_initialized.assert_called()

    @patch("ray_mcp.core.state_manager.RAY_AVAILABLE", True)
    @patch("ray_mcp.core.state_manager.ray")
    def test_validation_with_ray_initialized_and_valid_cluster(self, mock_ray):
        """Test validation when Ray is initialized with valid cluster."""
        mock_ray.is_initialized.return_value = True
        mock_context = Mock()
        mock_context.get_node_id.return_value = "node_123"
        mock_ray.get_runtime_context.return_value = mock_context

        manager = RayStateManager(validation_interval=0.01)
        manager.update_state(cluster_address="127.0.0.1:10001")

        # Wait for validation to trigger
        time.sleep(0.02)
        state = manager.get_state()

        assert state["initialized"]
        mock_ray.is_initialized.assert_called()
        mock_ray.get_runtime_context.assert_called()

    @patch("ray_mcp.core.state_manager.RAY_AVAILABLE", False)
    def test_validation_with_ray_unavailable(self):
        """Test validation when Ray is not available."""
        manager = RayStateManager(validation_interval=0.01)
        manager.update_state(cluster_address="127.0.0.1:10001")

        # Wait for validation to trigger
        time.sleep(0.02)
        state = manager.get_state()

        assert not state["initialized"]

    @patch("ray_mcp.core.state_manager.RAY_AVAILABLE", True)
    @patch("ray_mcp.core.state_manager.ray")
    def test_validation_clears_invalid_state(self, mock_ray):
        """Test that validation clears invalid state when Ray fails validation."""
        mock_ray.is_initialized.return_value = False

        manager = RayStateManager(validation_interval=0.01)
        manager.update_state(
            cluster_address="127.0.0.1:10001",
            dashboard_url="http://127.0.0.1:8265",
            job_client=Mock(),
        )

        # Wait for validation to trigger
        time.sleep(0.02)
        state = manager.get_state()

        assert not state["initialized"]
        assert state["cluster_address"] is None
        assert state["dashboard_url"] is None
        assert state["job_client"] is None

    def test_validation_interval_prevents_excessive_validation(self):
        """Test that validation interval prevents excessive validation calls."""
        with patch("ray_mcp.core.state_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.core.state_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True

                manager = RayStateManager(validation_interval=1.0)  # 1 second interval
                manager.update_state(cluster_address="127.0.0.1:10001")

                # Multiple rapid calls to get_state
                for _ in range(5):
                    manager.get_state()

                # Should only validate once due to interval
                assert mock_ray.is_initialized.call_count <= 1


@pytest.mark.fast
class TestRayStateManagerErrorHandling:
    """Test error handling in state validation."""

    @patch("ray_mcp.core.state_manager.RAY_AVAILABLE", True)
    @patch("ray_mcp.core.state_manager.ray")
    @patch("ray_mcp.core.state_manager.LoggingUtility")
    def test_validation_error_handling(self, mock_logging, mock_ray):
        """Test that validation errors are properly handled and logged."""
        mock_ray.is_initialized.side_effect = Exception("Ray validation error")

        manager = RayStateManager(validation_interval=0.01)
        manager.update_state(cluster_address="127.0.0.1:10001")

        # Wait for validation to trigger
        time.sleep(0.02)
        state = manager.get_state()

        assert not state["initialized"]
        mock_logging.log_error.assert_called()

    @patch("ray_mcp.core.state_manager.RAY_AVAILABLE", True)
    @patch("ray_mcp.core.state_manager.ray")
    def test_runtime_context_error_handling(self, mock_ray):
        """Test handling of runtime context errors during validation."""
        mock_ray.is_initialized.return_value = True
        mock_ray.get_runtime_context.side_effect = Exception("Context error")

        manager = RayStateManager(validation_interval=0.01)
        manager.update_state(cluster_address="127.0.0.1:10001")

        # Wait for validation to trigger
        time.sleep(0.02)
        state = manager.get_state()

        assert not state["initialized"]

    @patch("ray_mcp.core.state_manager.RAY_AVAILABLE", True)
    @patch("ray_mcp.core.state_manager.ray")
    def test_node_id_error_handling(self, mock_ray):
        """Test handling of node ID errors during validation."""
        mock_ray.is_initialized.return_value = True
        mock_context = Mock()
        mock_context.get_node_id.side_effect = Exception("Node ID error")
        mock_ray.get_runtime_context.return_value = mock_context

        manager = RayStateManager(validation_interval=0.01)
        manager.update_state(cluster_address="127.0.0.1:10001")

        # Wait for validation to trigger
        time.sleep(0.02)
        state = manager.get_state()

        assert not state["initialized"]

    @patch("ray_mcp.core.state_manager.RAY_AVAILABLE", True)
    @patch("ray_mcp.core.state_manager.ray")
    def test_validation_exception_recovery_race_condition_fix(self, mock_ray):
        """Test that validation can recover from exceptions without race condition.

        This test verifies the fix for Issue #105 where validation exceptions
        would prevent future validation attempts, creating a race condition.
        """
        # Setup: cause exception during validation
        mock_ray.is_initialized.side_effect = Exception("Validation error")

        manager = RayStateManager(validation_interval=0.01)
        manager.update_state(cluster_address="127.0.0.1:10001")

        # Reset last_validated to ensure validation will trigger
        manager._state["last_validated"] = 0.0

        # First validation should trigger exception
        time.sleep(0.02)
        state1 = manager.get_state()

        # Verify: exception handled but cluster state preserved for retry
        assert not state1["initialized"]
        assert state1["cluster_address"] == "127.0.0.1:10001"  # Preserved!

        # Setup: successful validation after exception
        mock_ray.reset_mock()
        mock_ray.is_initialized.side_effect = None
        mock_ray.is_initialized.return_value = True
        mock_context = Mock()
        mock_context.get_node_id.return_value = "node_123"
        mock_ray.get_runtime_context.return_value = mock_context

        # Reset last_validated to ensure validation will trigger again
        manager._state["last_validated"] = 0.0

        # Second validation should succeed (race condition fixed)
        time.sleep(0.02)
        state2 = manager.get_state()

        # Verify: validation succeeded after exception recovery
        mock_ray.is_initialized.assert_called()
        assert state2["initialized"]
        assert state2["cluster_address"] == "127.0.0.1:10001"
