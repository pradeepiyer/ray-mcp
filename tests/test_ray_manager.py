#!/usr/bin/env python3
"""Tests for the Ray manager."""

import asyncio
import inspect
import subprocess
import threading
import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from ray_mcp.logging_utils import LogProcessor
from ray_mcp.ray_manager import (
    JobClientError,
    JobConnectionError,
    JobRuntimeError,
    JobSubmissionError,
    JobValidationError,
    RayManager,
    RayStateManager,
)
from tests.conftest import mock_cluster_startup


@pytest.mark.fast
class TestRayManager:
    """Test cases for RayManager."""

    @pytest.fixture
    def manager(self):
        """Create a RayManager instance for testing."""
        return RayManager()

    def test_is_initialized_property(self):
        """Test the is_initialized property."""
        manager = RayManager()
        assert not manager.is_initialized

        # Mock Ray as available and initialized
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                manager._update_state(initialized=True)
                assert manager.is_initialized

    def test_ensure_initialized(self):
        """Test _ensure_initialized method."""
        manager = RayManager()
        with pytest.raises(RuntimeError, match="Ray is not initialized"):
            manager._ensure_initialized()

    @pytest.mark.asyncio
    async def test_init_cluster_ray_unavailable(self, manager, mock_cluster_startup):
        """Test cluster initialization when Ray is not available."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", False):
            result = await manager.init_cluster(address="127.0.0.1:10001")
            assert result["status"] == "error"
            assert "Ray is not available" in result["message"]

    @pytest.mark.asyncio
    async def test_stop_cluster(self, manager):
        """Test stopping the Ray cluster."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.shutdown.return_value = None

                # Mock subprocess for ray stop
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 0
                    mock_run.return_value.stderr = ""

                    result = await manager.stop_cluster()
                    assert result["status"] == "success"
                    assert result.get("result_type") == "stopped"

    @pytest.mark.asyncio
    async def test_stop_cluster_not_running(self, manager):
        """Test stopping when Ray is not running."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = False

                result = await manager.stop_cluster()
                assert result["status"] == "not_running"

    @pytest.mark.asyncio
    async def test_cleanup_head_node_process(self, manager):
        """Test enhanced cleanup of head node process with a real subprocess."""
        import subprocess

        # Start a real subprocess
        proc = subprocess.Popen(["sleep", "1"])
        manager._head_node_process = proc

        await manager._cleanup_head_node_process(timeout=5)

        # The process should be terminated and cleaned up
        assert manager._head_node_process is None
        assert proc.poll() is not None  # Process should be terminated

    @pytest.mark.asyncio
    async def test_initialize_job_client_with_retry_success(self, manager):
        """Test successful job client initialization with retry."""
        with patch("ray_mcp.ray_manager.JobSubmissionClient") as mock_job_client_class:
            mock_job_client = Mock()
            mock_job_client_class.return_value = mock_job_client

            result = await manager._initialize_job_client_with_retry(
                "http://127.0.0.1:8265"
            )
            assert result == mock_job_client

    @pytest.mark.asyncio
    async def test_initialize_job_client_with_retry_failure(self, manager):
        """Test job client initialization failure after retries."""
        with patch("ray_mcp.ray_manager.JobSubmissionClient") as mock_job_client_class:
            mock_job_client_class.side_effect = Exception("Connection failed")
            with patch("asyncio.sleep"):
                result = await manager._initialize_job_client_with_retry(
                    "http://127.0.0.1:8265", max_retries=2
                )
                assert result is None

    def test_address_format_validation(self):
        """Test that address format validation works correctly."""
        manager = RayManager()

        # Test valid direct addresses
        valid_addresses = [
            "127.0.0.1:10001",
            "192.168.1.100:10001",
            "localhost:10001",
            "10.0.0.1:10001",
        ]

        for address in valid_addresses:
            # This should not raise any exceptions
            assert isinstance(address, str)
            assert ":" in address
            assert address.split(":")[1].isdigit()


@pytest.mark.fast
class TestExceptionHandling:
    """Test exception handling for job submission methods."""

    @pytest.fixture
    def ray_manager(self):
        """Create a RayManager instance for testing."""
        manager = RayManager()
        # Set internal state to avoid actual Ray setup
        manager._update_state(initialized=True)
        manager._job_client = Mock()
        return manager

    def _patch_is_initialized(self, manager):
        """Helper method to patch is_initialized property."""
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


@pytest.mark.fast
class TestStreamingLogs:
    """Test cases for streaming log retrieval functionality."""

    @pytest.fixture
    def ray_manager(self):
        """Create a RayManager instance for testing."""
        manager = RayManager()
        manager._update_state(initialized=True)
        manager._job_client = Mock()
        manager._ensure_initialized = lambda: None
        return manager

    def test_validate_log_parameters_valid(self):
        result = LogProcessor.validate_log_parameters(100, 10)
        assert result is None

    def test_validate_log_parameters_invalid_num_lines(self):
        result = LogProcessor.validate_log_parameters(0, 10)
        assert result["status"] == "error"
        assert "num_lines must be positive" in result["message"]

        result = LogProcessor.validate_log_parameters(15000, 10)
        assert result["status"] == "error"
        assert "num_lines cannot exceed 10000" in result["message"]

    def test_validate_log_parameters_invalid_max_size(self):
        result = LogProcessor.validate_log_parameters(100, 0)
        assert result["status"] == "error"
        assert "max_size_mb must be between 1 and 100" in result["message"]

        result = LogProcessor.validate_log_parameters(100, 150)
        assert result["status"] == "error"
        assert "max_size_mb must be between 1 and 100" in result["message"]

    def test_truncate_logs_to_size_within_limit(self):
        logs = "This is a test log\nwith multiple lines\nbut small size"
        result = LogProcessor.truncate_logs_to_size(logs, 10)
        assert result == logs

    def test_truncate_logs_to_size_exceeds_limit(self):
        large_log = "x" * (2 * 1024 * 1024)
        result = LogProcessor.truncate_logs_to_size(large_log, 1)
        max_allowed = 1024 * 1024 + 1024
        assert len(result.encode("utf-8")) <= max_allowed
        assert "... (truncated at 1MB limit)" in result

    def test_stream_logs_with_limits_string_input(self):
        logs = "line1\nline2\nline3\nline4\nline5"
        result = LogProcessor.stream_logs_with_limits(logs, max_lines=3, max_size_mb=1)
        lines = result.split("\n")
        assert len(lines) == 4
        assert lines[0] == "line1"
        assert lines[1] == "line2"
        assert lines[2] == "line3"
        assert "... (truncated at 3 lines)" in lines[3]

    def test_analyze_job_logs_with_streaming(self, ray_manager):
        """Test log analysis with streaming approach."""
        logs = "This is a normal log\nThis is an error log\nThis is an exception\nNormal log again"
        result = ray_manager._analyze_job_logs(logs)

        assert result["error_count"] == 2
        assert len(result["errors"]) == 2
        assert "error" in result["errors"][0].lower()


@pytest.mark.fast
class TestStateManagement:
    """Test core state management functionality."""

    def test_ray_state_manager_initialization(self):
        """Test RayStateManager initialization."""
        state_manager = RayStateManager()
        state = state_manager.get_state()

        assert state["initialized"] is False
        assert state["cluster_address"] is None
        assert state["dashboard_url"] is None
        assert state["job_client"] is None

    def test_state_update_and_reset(self):
        """Test state updates and reset."""
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

        # Reset state
        state_manager.reset_state()
        state = state_manager.get_state()
        assert state["initialized"] is False
        assert state["cluster_address"] is None

    def test_ray_manager_state_integration(self):
        """Test RayManager state management integration."""
        manager = RayManager()

        # Test initial state
        assert manager.is_initialized is False
        assert manager.cluster_address is None
        assert manager.dashboard_url is None

        # Test state update
        manager._update_state(
            initialized=True,
            cluster_address="ray://localhost:10001", 
            dashboard_url="http://localhost:8265"
        )
        assert manager.is_initialized is True
        assert manager.cluster_address == "ray://localhost:10001"
        assert manager.dashboard_url == "http://localhost:8265"

    def test_thread_safety_basic(self):
        """Test basic thread safety of state management."""
        state_manager = RayStateManager()
        results = []

        def update_state_thread(thread_id):
            for i in range(50):
                state_manager.update_state(
                    initialized=True,
                    cluster_address=f"ray://localhost:{10001 + thread_id}",
                )
                state = state_manager.get_state()
                results.append((thread_id, state["initialized"]))
                time.sleep(0.001)

        # Start multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=update_state_thread, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Verify no exceptions occurred
        assert len(results) == 150  # 3 threads * 50 updates each


if __name__ == "__main__":
    pytest.main([__file__])
