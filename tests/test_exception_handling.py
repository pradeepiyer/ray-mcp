"""Test exception handling improvements for job submission methods."""

from unittest.mock import Mock, patch

import pytest

from ray_mcp.ray_manager import (
    JobClientError,
    JobConnectionError,
    JobRuntimeError,
    JobSubmissionError,
    JobValidationError,
    RayManager,
)


class TestExceptionHandling:
    """Test that exception handling properly re-raises shutdown signals."""

    @pytest.fixture
    def ray_manager(self):
        """Create a RayManager instance for testing."""
        manager = RayManager()
        # Set internal state to avoid actual Ray setup
        manager._update_state(initialized=True)
        manager._job_client = Mock()
        return manager

    def _patch_is_initialized(self, manager):
        """Helper method to patch is_initialized property for this test class only."""
        original_property = type(manager).is_initialized
        type(manager).is_initialized = property(lambda self: True)
        return original_property

    def _restore_is_initialized(self, manager, original_property):
        """Helper method to restore the original is_initialized property."""
        type(manager).is_initialized = original_property

    @pytest.mark.asyncio
    async def test_submit_job_handles_validation_error(self, ray_manager):
        """Test that submit_job properly handles validation errors."""
        original_property = self._patch_is_initialized(ray_manager)
        try:
            # Test with empty entrypoint
            result = await ray_manager.submit_job("")
            assert result["status"] == "error"
            assert "Entrypoint cannot be empty" in result["message"]

            # Test with whitespace-only entrypoint
            result = await ray_manager.submit_job("   ")
            assert result["status"] == "error"
            assert "Entrypoint cannot be empty" in result["message"]
        finally:
            self._restore_is_initialized(ray_manager, original_property)

    @pytest.mark.asyncio
    async def test_cancel_job_handles_validation_error(self, ray_manager):
        """Test that cancel_job properly handles validation errors."""
        original_property = self._patch_is_initialized(ray_manager)
        try:
            # Test with empty job_id
            result = await ray_manager.cancel_job("")
            assert result["status"] == "error"
            assert "Job ID cannot be empty" in result["message"]

            # Test with whitespace-only job_id
            result = await ray_manager.cancel_job("   ")
            assert result["status"] == "error"
            assert "Job ID cannot be empty" in result["message"]
        finally:
            self._restore_is_initialized(ray_manager, original_property)

    def test_custom_exception_hierarchy(self):
        """Test that custom exception hierarchy is properly defined."""
        # Test that JobSubmissionError is the base class
        assert issubclass(JobConnectionError, JobSubmissionError)
        assert issubclass(JobValidationError, JobSubmissionError)
        assert issubclass(JobRuntimeError, JobSubmissionError)
        assert issubclass(JobClientError, JobSubmissionError)

        # Test that exceptions can be instantiated
        connection_error = JobConnectionError("Connection failed")
        validation_error = JobValidationError("Invalid parameters")
        runtime_error = JobRuntimeError("Runtime error")
        client_error = JobClientError("Client not initialized")

        assert str(connection_error) == "Connection failed"
        assert str(validation_error) == "Invalid parameters"
        assert str(runtime_error) == "Runtime error"
        assert str(client_error) == "Client not initialized"
