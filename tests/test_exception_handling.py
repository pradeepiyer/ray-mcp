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
        manager._is_initialized = True
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
    async def test_submit_job_re_raises_keyboard_interrupt(self, ray_manager):
        """Test that submit_job re-raises KeyboardInterrupt."""
        original_property = self._patch_is_initialized(ray_manager)
        try:
            # Mock the job client to raise KeyboardInterrupt
            ray_manager._job_client.submit_job.side_effect = KeyboardInterrupt()

            with pytest.raises(KeyboardInterrupt):
                await ray_manager.submit_job("test_script.py")
        finally:
            self._restore_is_initialized(ray_manager, original_property)

    @pytest.mark.asyncio
    async def test_submit_job_re_raises_system_exit(self, ray_manager):
        """Test that submit_job re-raises SystemExit."""
        original_property = self._patch_is_initialized(ray_manager)
        try:
            # Mock the job client to raise SystemExit
            ray_manager._job_client.submit_job.side_effect = SystemExit()

            with pytest.raises(SystemExit):
                await ray_manager.submit_job("test_script.py")
        finally:
            self._restore_is_initialized(ray_manager, original_property)

    @pytest.mark.asyncio
    async def test_list_jobs_re_raises_keyboard_interrupt(self, ray_manager):
        """Test that list_jobs re-raises KeyboardInterrupt."""
        original_property = self._patch_is_initialized(ray_manager)
        try:
            # Mock the job client to raise KeyboardInterrupt
            ray_manager._job_client.list_jobs.side_effect = KeyboardInterrupt()

            with pytest.raises(KeyboardInterrupt):
                await ray_manager.list_jobs()
        finally:
            self._restore_is_initialized(ray_manager, original_property)

    @pytest.mark.asyncio
    async def test_list_jobs_re_raises_system_exit(self, ray_manager):
        """Test that list_jobs re-raises SystemExit."""
        original_property = self._patch_is_initialized(ray_manager)
        try:
            # Mock the job client to raise SystemExit
            ray_manager._job_client.list_jobs.side_effect = SystemExit()

            with pytest.raises(SystemExit):
                await ray_manager.list_jobs()
        finally:
            self._restore_is_initialized(ray_manager, original_property)

    @pytest.mark.asyncio
    async def test_cancel_job_re_raises_keyboard_interrupt(self, ray_manager):
        """Test that cancel_job re-raises KeyboardInterrupt."""
        original_property = self._patch_is_initialized(ray_manager)
        try:
            # Mock the job client to raise KeyboardInterrupt
            ray_manager._job_client.stop_job.side_effect = KeyboardInterrupt()

            with pytest.raises(KeyboardInterrupt):
                await ray_manager.cancel_job("test_job_id")
        finally:
            self._restore_is_initialized(ray_manager, original_property)

    @pytest.mark.asyncio
    async def test_cancel_job_re_raises_system_exit(self, ray_manager):
        """Test that cancel_job re-raises SystemExit."""
        original_property = self._patch_is_initialized(ray_manager)
        try:
            # Mock the job client to raise SystemExit
            ray_manager._job_client.stop_job.side_effect = SystemExit()

            with pytest.raises(SystemExit):
                await ray_manager.cancel_job("test_job_id")
        finally:
            self._restore_is_initialized(ray_manager, original_property)

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

    @pytest.mark.asyncio
    async def test_submit_job_handles_connection_error(self, ray_manager):
        """Test that submit_job properly handles connection errors."""
        original_property = self._patch_is_initialized(ray_manager)
        try:
            # Mock the job client to raise ConnectionError
            ray_manager._job_client.submit_job.side_effect = ConnectionError(
                "Connection failed"
            )

            result = await ray_manager.submit_job("test_script.py")
            assert result["status"] == "error"
            assert "Connection error" in result["message"]
        finally:
            self._restore_is_initialized(ray_manager, original_property)

    @pytest.mark.asyncio
    async def test_list_jobs_handles_connection_error(self, ray_manager):
        """Test that list_jobs properly handles connection errors."""
        original_property = self._patch_is_initialized(ray_manager)
        try:
            # Mock the job client to raise ConnectionError
            ray_manager._job_client.list_jobs.side_effect = ConnectionError(
                "Connection failed"
            )

            result = await ray_manager.list_jobs()
            assert result["status"] == "error"
            assert "Connection error" in result["message"]
        finally:
            self._restore_is_initialized(ray_manager, original_property)

    @pytest.mark.asyncio
    async def test_cancel_job_handles_connection_error(self, ray_manager):
        """Test that cancel_job properly handles connection errors."""
        original_property = self._patch_is_initialized(ray_manager)
        try:
            # Mock the job client to raise ConnectionError
            ray_manager._job_client.stop_job.side_effect = ConnectionError(
                "Connection failed"
            )

            result = await ray_manager.cancel_job("test_job_id")
            assert result["status"] == "error"
            assert "Connection error" in result["message"]
        finally:
            self._restore_is_initialized(ray_manager, original_property)

    @pytest.mark.asyncio
    async def test_submit_job_handles_value_error(self, ray_manager):
        """Test that submit_job properly handles ValueError."""
        original_property = self._patch_is_initialized(ray_manager)
        try:
            # Mock the job client to raise ValueError
            ray_manager._job_client.submit_job.side_effect = ValueError("Invalid value")

            result = await ray_manager.submit_job("test_script.py")
            assert result["status"] == "error"
            assert "Invalid parameters" in result["message"]
        finally:
            self._restore_is_initialized(ray_manager, original_property)

    @pytest.mark.asyncio
    async def test_list_jobs_handles_value_error(self, ray_manager):
        """Test that list_jobs properly handles ValueError."""
        original_property = self._patch_is_initialized(ray_manager)
        try:
            # Mock the job client to raise ValueError
            ray_manager._job_client.list_jobs.side_effect = ValueError("Invalid value")

            result = await ray_manager.list_jobs()
            assert result["status"] == "error"
            assert "Invalid parameters" in result["message"]
        finally:
            self._restore_is_initialized(ray_manager, original_property)

    @pytest.mark.asyncio
    async def test_cancel_job_handles_value_error(self, ray_manager):
        """Test that cancel_job properly handles ValueError."""
        original_property = self._patch_is_initialized(ray_manager)
        try:
            # Mock the job client to raise ValueError
            ray_manager._job_client.stop_job.side_effect = ValueError("Invalid value")

            result = await ray_manager.cancel_job("test_job_id")
            assert result["status"] == "error"
            assert "Invalid parameters" in result["message"]
        finally:
            self._restore_is_initialized(ray_manager, original_property)

    @pytest.mark.asyncio
    async def test_submit_job_handles_runtime_error(self, ray_manager):
        """Test that submit_job properly handles RuntimeError."""
        original_property = self._patch_is_initialized(ray_manager)
        try:
            # Mock the job client to raise RuntimeError
            ray_manager._job_client.submit_job.side_effect = RuntimeError(
                "Runtime error"
            )

            result = await ray_manager.submit_job("test_script.py")
            assert result["status"] == "error"
            assert "Runtime error" in result["message"]
        finally:
            self._restore_is_initialized(ray_manager, original_property)

    @pytest.mark.asyncio
    async def test_list_jobs_handles_runtime_error(self, ray_manager):
        """Test that list_jobs properly handles RuntimeError."""
        original_property = self._patch_is_initialized(ray_manager)
        try:
            # Mock the job client to raise RuntimeError
            ray_manager._job_client.list_jobs.side_effect = RuntimeError(
                "Runtime error"
            )

            result = await ray_manager.list_jobs()
            assert result["status"] == "error"
            assert "Runtime error" in result["message"]
        finally:
            self._restore_is_initialized(ray_manager, original_property)

    @pytest.mark.asyncio
    async def test_cancel_job_handles_runtime_error(self, ray_manager):
        """Test that cancel_job properly handles RuntimeError."""
        original_property = self._patch_is_initialized(ray_manager)
        try:
            # Mock the job client to raise RuntimeError
            ray_manager._job_client.stop_job.side_effect = RuntimeError("Runtime error")

            result = await ray_manager.cancel_job("test_job_id")
            assert result["status"] == "error"
            assert "Runtime error" in result["message"]
        finally:
            self._restore_is_initialized(ray_manager, original_property)

    @pytest.mark.asyncio
    async def test_submit_job_handles_unexpected_error(self, ray_manager):
        """Test that submit_job properly handles unexpected errors."""
        original_property = self._patch_is_initialized(ray_manager)
        try:
            # Mock the job client to raise an unexpected error
            ray_manager._job_client.submit_job.side_effect = Exception(
                "Unexpected error"
            )

            result = await ray_manager.submit_job("test_script.py")
            assert result["status"] == "error"
            assert "Unexpected error" in result["message"]
        finally:
            self._restore_is_initialized(ray_manager, original_property)

    @pytest.mark.asyncio
    async def test_list_jobs_handles_unexpected_error(self, ray_manager):
        """Test that list_jobs properly handles unexpected errors."""
        original_property = self._patch_is_initialized(ray_manager)
        try:
            # Mock the job client to raise an unexpected error
            ray_manager._job_client.list_jobs.side_effect = Exception(
                "Unexpected error"
            )

            result = await ray_manager.list_jobs()
            assert result["status"] == "error"
            assert "Unexpected error" in result["message"]
        finally:
            self._restore_is_initialized(ray_manager, original_property)

    @pytest.mark.asyncio
    async def test_cancel_job_handles_unexpected_error(self, ray_manager):
        """Test that cancel_job properly handles unexpected errors."""
        original_property = self._patch_is_initialized(ray_manager)
        try:
            # Mock the job client to raise an unexpected error
            ray_manager._job_client.stop_job.side_effect = Exception("Unexpected error")

            result = await ray_manager.cancel_job("test_job_id")
            assert result["status"] == "error"
            assert "Unexpected error" in result["message"]
        finally:
            self._restore_is_initialized(ray_manager, original_property)

    @pytest.mark.asyncio
    async def test_job_client_error_handling(self, ray_manager):
        """Test that JobClientError is properly handled."""
        original_property = self._patch_is_initialized(ray_manager)
        try:
            # Set job client to None to trigger JobClientError
            ray_manager._job_client = None

            result = await ray_manager.submit_job("test_script.py")
            assert result["status"] == "error"
            assert (
                "Job client is not initialized" in result["message"]
                or "No dashboard URL available" in result["message"]
            )

            result = await ray_manager.list_jobs()
            assert result["status"] == "error"
            assert (
                "Job client is not initialized" in result["message"]
                or "No dashboard URL available" in result["message"]
            )

            result = await ray_manager.cancel_job("test_job_id")
            assert result["status"] == "error"
            assert (
                "Job client is not initialized" in result["message"]
                or "No dashboard URL available" in result["message"]
            )
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
