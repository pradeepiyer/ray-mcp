#!/usr/bin/env python3
"""Tests for the Ray manager - Consolidated and optimized for maintainability."""

import asyncio
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
class TestRayManagerCore:
    """Core Ray manager functionality - cluster lifecycle, state management, validation."""

    @pytest.fixture
    def manager(self):
        """Create a RayManager instance for testing."""
        return RayManager()

    @pytest.fixture
    def initialized_manager(self):
        """Create an initialized RayManager for testing job operations."""
        manager = RayManager()
        manager._update_state(initialized=True)
        mock_client = Mock()
        manager._update_state(job_client=mock_client)
        return manager

    # Core Lifecycle Tests
    def test_initialization_properties(self):
        """Test RayManager initialization and core properties."""
        manager = RayManager()
        assert not manager.is_initialized
        
        # Test _ensure_initialized raises when not initialized
        with pytest.raises(RuntimeError, match="Ray is not initialized"):
            manager._ensure_initialized()

        # Test proper initialization state
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                manager._update_state(initialized=True)
                assert manager.is_initialized

    @pytest.mark.asyncio
    async def test_cluster_lifecycle(self, manager, mock_cluster_startup):
        """Test complete cluster start/stop lifecycle."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = False
                
                # Test Ray unavailable scenario
                with patch("ray_mcp.ray_manager.RAY_AVAILABLE", False):
                    result = await manager.init_cluster(address="127.0.0.1:10001")
                    assert result and result["status"] == "error"
                    assert "Ray is not available" in result["message"]
                
                # Test successful stop
                mock_ray.is_initialized.return_value = True
                mock_ray.shutdown.return_value = None
                mock_process = Mock()
                manager._head_node_process = mock_process

                with patch.object(manager, "_cleanup_head_node_process") as mock_cleanup:
                    mock_cleanup.return_value = None
                    result = await manager.stop_cluster()
                    assert result and result["status"] == "success"
                    assert result.get("result_type") == "stopped"
                    mock_cleanup.assert_called_once_with(timeout=10)

                # Test stop when not running
                mock_ray.is_initialized.return_value = False
                result = await manager.stop_cluster()
                assert result and result["status"] == "not_running"

    @pytest.mark.asyncio
    async def test_job_client_initialization(self, manager):
        """Test job client initialization with retry logic."""
        with patch("ray_mcp.ray_manager.JobSubmissionClient") as mock_job_client_class:
            # Test successful initialization
            mock_job_client = Mock()
            mock_job_client_class.return_value = mock_job_client
            result = await manager._initialize_job_client_with_retry("http://127.0.0.1:8265")
            assert result == mock_job_client

            # Test failure after retries
            mock_job_client_class.side_effect = Exception("Connection failed")
            with patch("asyncio.sleep"):
                result = await manager._initialize_job_client_with_retry(
                    "http://127.0.0.1:8265", max_retries=2
                )
                assert result is None

    @pytest.mark.parametrize("job_input,expected_error", [
        ("", "Entrypoint cannot be empty"),
        ("   ", "Entrypoint cannot be empty"),
        (None, "Entrypoint cannot be empty"),
    ])
    @pytest.mark.asyncio
    async def test_job_validation_errors(self, initialized_manager, job_input, expected_error):
        """Test job validation error handling."""
        result = await initialized_manager.submit_job(job_input)
        assert result and result["status"] == "error"
        assert expected_error in result["message"]

    @pytest.mark.parametrize("job_id_input,expected_error", [
        ("", "Job ID cannot be empty"),
        ("   ", "Job ID cannot be empty"),
        (None, "Job ID cannot be empty"),
    ])
    @pytest.mark.asyncio
    async def test_cancel_job_validation_errors(self, initialized_manager, job_id_input, expected_error):
        """Test cancel job validation error handling."""
        result = await initialized_manager.cancel_job(job_id_input)
        assert result and result["status"] == "error"
        assert expected_error in result["message"]

    def test_exception_hierarchy(self):
        """Test custom exception hierarchy structure."""
        # Verify inheritance
        assert issubclass(JobConnectionError, JobSubmissionError)
        assert issubclass(JobValidationError, JobSubmissionError)
        assert issubclass(JobRuntimeError, JobSubmissionError)
        assert issubclass(JobClientError, JobSubmissionError)

        # Test instantiation
        errors = [
            JobConnectionError("Connection failed"),
            JobValidationError("Invalid parameters"),
            JobRuntimeError("Runtime error"),
            JobClientError("Client not initialized")
        ]
        assert all(str(error) in ["Connection failed", "Invalid parameters", "Runtime error", "Client not initialized"] for error in errors)

    # State Management Tests
    def test_state_management_lifecycle(self):
        """Test complete state management lifecycle."""
        state_manager = RayStateManager()
        
        # Test initial state
        state = state_manager.get_state()
        assert state["initialized"] is False
        assert state["cluster_address"] is None
        assert state["dashboard_url"] is None
        assert state["job_client"] is None

        # Test state updates
        state_manager.update_state(
            initialized=True,
            cluster_address="ray://localhost:10001",
            dashboard_url="http://localhost:8265",
        )
        state = state_manager.get_state()
        assert state["initialized"] is True
        assert state["cluster_address"] == "ray://localhost:10001"
        assert state["dashboard_url"] == "http://localhost:8265"

        # Test state reset
        state_manager.reset_state()
        state = state_manager.get_state()
        assert state["initialized"] is False
        assert state["cluster_address"] is None

    def test_ray_manager_state_integration(self):
        """Test RayManager state integration."""
        manager = RayManager()
        
        # Test initial state
        assert manager.is_initialized is False
        assert manager.cluster_address is None
        assert manager.dashboard_url is None

        # Test state update integration
        manager._update_state(
            initialized=True,
            cluster_address="ray://localhost:10001",
            dashboard_url="http://localhost:8265",
        )
        assert manager.is_initialized is True
        assert manager.cluster_address == "ray://localhost:10001"
        assert manager.dashboard_url == "http://localhost:8265"

    def test_state_thread_safety(self):
        """Test thread safety of state management."""
        state_manager = RayStateManager()
        results = []

        def update_state_thread(thread_id):
            for i in range(20):  # Reduced from 50 for efficiency
                state_manager.update_state(
                    initialized=True,
                    cluster_address=f"ray://localhost:{10001 + thread_id}",
                )
                state = state_manager.get_state()
                results.append((thread_id, state["initialized"]))
                time.sleep(0.001)

        # Test with fewer threads for efficiency
        threads = []
        for i in range(3):
            thread = threading.Thread(target=update_state_thread, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(results) == 60  # 3 threads * 20 updates each

    # Worker Node Logic Tests
    @pytest.mark.parametrize("worker_nodes,expected_result", [
        (None, "default_workers"),  # Should create default workers
        ([], None),  # Should return None for head-only
        ([{"num_cpus": 2, "node_name": "test-worker"}], "custom_config"),  # Valid custom config
    ])
    def test_worker_node_processing(self, manager, worker_nodes, expected_result):
        """Test worker node validation and processing scenarios."""
        result = manager._validate_and_process_worker_nodes(worker_nodes)
        
        if expected_result == "default_workers":
            assert result is not None and len(result) == 2
            assert result[0]["node_name"] == "default-worker-1"
        elif expected_result is None:
            assert result is None
        elif expected_result == "custom_config":
            assert result is not None and len(result) == 1
            assert result[0]["num_cpus"] == 2

    @pytest.mark.asyncio
    async def test_cleanup_process_handling(self, manager):
        """Test process cleanup functionality."""
        # Start a real subprocess for testing
        proc = subprocess.Popen(["sleep", "1"])
        manager._head_node_process = proc

        await manager._cleanup_head_node_process(timeout=5)
        
        # Process should be cleaned up
        assert manager._head_node_process is None
        assert proc.poll() is not None


@pytest.mark.fast
class TestProcessCommunication:
    """Process communication, port allocation, and streaming functionality."""

    @pytest.fixture
    def manager(self):
        """Create a RayManager instance for testing."""
        return RayManager()

    @pytest.mark.asyncio
    async def test_find_free_port_functionality(self, manager):
        """Test port allocation with basic locking mechanism."""
        flock_call_count = 0

        def mock_flock_side_effect(*args):
            nonlocal flock_call_count
            flock_call_count += 1
            if flock_call_count == 2:  # Second attempt fails
                raise OSError("Resource temporarily unavailable")
            return None

        with patch("fcntl.flock", side_effect=mock_flock_side_effect):
            with patch("socket.socket") as mock_socket:
                mock_sock = Mock()
                mock_socket.return_value.__enter__.return_value = mock_sock
                mock_sock.bind.return_value = None
                
                port = await manager.find_free_port(start_port=20000)
                assert isinstance(port, int)
                assert port >= 20000

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario,mock_config,expected", [
        ("normal_operation", {
            "stdout_lines": ["line1", "line2", ""],
            "stderr_lines": ["error1", ""],
            "poll_sequence": [None, None, 0]
        }, "success"),
        ("memory_limits", {
            "stdout_lines": ["x" * 1000] * 10 + [""],
            "stderr_lines": [""],
            "poll_sequence": [None, 0]
        }, "memory_handled"),
        ("timeout_handling", {
            "stdout_lines": ["line1"] * 100,  # Never ends
            "stderr_lines": [""],
            "poll_sequence": [None] * 100
        }, "timeout"),
    ])
    async def test_stream_process_scenarios(self, manager, scenario, mock_config, expected):
        """Test various stream processing scenarios."""
        stdout_iter = iter(mock_config["stdout_lines"])
        stderr_iter = iter(mock_config["stderr_lines"])
        poll_iter = iter(mock_config["poll_sequence"])

        def mock_stdout_readline():
            try:
                return next(stdout_iter).encode() + b"\n"
            except StopIteration:
                return b""

        def mock_stderr_readline():
            try:
                return next(stderr_iter).encode() + b"\n"
            except StopIteration:
                return b""

        def mock_poll():
            try:
                return next(poll_iter)
            except StopIteration:
                return 0

        mock_process = Mock()
        mock_process.stdout.readline = mock_stdout_readline
        mock_process.stderr.readline = mock_stderr_readline
        mock_process.poll = mock_poll

        if scenario == "timeout_handling":
            # Test timeout handling - should raise RuntimeError
            with pytest.raises(RuntimeError, match="Process startup timed out"):
                await manager._stream_process_output(mock_process, timeout=0.1)
        else:
            stdout, stderr = await manager._stream_process_output(mock_process, timeout=5)
            
            if scenario == "normal_operation":
                assert "line1" in stdout and "line2" in stdout
                assert "error1" in stderr
            elif scenario == "memory_limits":
                # Should handle large output without memory issues
                assert isinstance(stdout, str)
                assert len(stdout) > 0

    @pytest.mark.asyncio
    async def test_communicate_with_timeout_scenarios(self, manager):
        """Test process communication timeout handling."""
        # Test timeout scenario - process never finishes
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process still running
        mock_process.stdout = Mock()
        mock_process.stderr = Mock()
        mock_process.stdout.read.return_value = "partial output"
        mock_process.stderr.read.return_value = "partial error"
        
        # Should timeout and raise RuntimeError
        with pytest.raises(RuntimeError, match="Process communication timed out"):
            await manager._communicate_with_timeout(mock_process, timeout=0.1)


@pytest.mark.fast  
class TestLogProcessing:
    """Log processing, validation, and streaming functionality."""

    @pytest.fixture
    def manager(self):
        """Create RayManager for log testing."""
        manager = RayManager()
        manager._update_state(initialized=True)
        mock_client = Mock()
        manager._update_state(job_client=mock_client)
        manager._ensure_initialized = lambda: None
        return manager

    @pytest.mark.parametrize("num_lines,max_size_mb,expected_error", [
        (100, 10, None),  # Valid parameters
        (0, 10, "num_lines must be positive"),  # Invalid num_lines
        (15000, 10, "num_lines cannot exceed 10000"),  # Excessive num_lines
        (100, 0, "max_size_mb must be between 1 and 100"),  # Invalid max_size low
        (100, 150, "max_size_mb must be between 1 and 100"),  # Invalid max_size high
    ])
    def test_log_parameter_validation(self, num_lines, max_size_mb, expected_error):
        """Test log parameter validation scenarios."""
        result = LogProcessor.validate_log_parameters(num_lines, max_size_mb)
        
        if expected_error is None:
            assert result is None
        else:
            assert result and result["status"] == "error"
            assert expected_error in result["message"]

    @pytest.mark.parametrize("log_input,max_size_mb,should_truncate", [
        ("Small log content", 10, False),
        ("x" * (2 * 1024 * 1024), 1, True),  # 2MB content, 1MB limit
    ])
    def test_log_size_handling(self, log_input, max_size_mb, should_truncate):
        """Test log size truncation functionality."""
        result = LogProcessor.truncate_logs_to_size(log_input, max_size_mb)
        
        if should_truncate:
            max_allowed = max_size_mb * 1024 * 1024 + 1024
            assert len(result.encode("utf-8")) <= max_allowed
            assert "... (truncated at" in result
        else:
            assert result == log_input

    def test_log_streaming_with_limits(self):
        """Test log streaming with various limits and constraints."""
        # Test line limits
        logs = "line1\nline2\nline3\nline4\nline5"
        result = LogProcessor.stream_logs_with_limits(logs, max_lines=3, max_size_mb=1)
        lines = result.split("\n")
        assert len(lines) == 4  # 3 lines + truncation message
        assert "... (truncated at 3 lines)" in lines[3]

        # Test per-line size limits
        large_line = "x" * (2 * 1024)  # 2KB line
        logs_with_large = f"normal\n{large_line}\nend"
        result = LogProcessor.stream_logs_with_limits(
            logs_with_large, max_lines=10, max_size_mb=1, max_line_size_kb=1
        )
        lines = result.split("\n")
        assert "normal" in lines[0]
        assert "... (line truncated at 1KB)" in lines[1]
        assert "end" in lines[2]

    def test_memory_exhaustion_protection(self):
        """Test memory exhaustion protection in log processing."""
        # Test multiple large lines
        large_line = "y" * (300 * 1024)  # 300KB each
        logs = [large_line, large_line, "small_line"]
        result = LogProcessor.stream_logs_with_limits(
            logs, max_lines=10, max_size_mb=1, max_line_size_kb=200
        )
        lines = result.split("\n")
        assert "... (line truncated at 200KB)" in lines[0]
        assert "... (line truncated at 200KB)" in lines[1]
        assert "small_line" in lines[2]

        # Test line limit precedence
        mixed_logs = ["normal"] * 3 + ["z" * (1024 * 1024)]
        result = LogProcessor.stream_logs_with_limits(
            mixed_logs, max_lines=2, max_size_mb=10, max_line_size_kb=512
        )
        lines = result.split("\n")
        assert len(lines) == 3  # 2 lines + truncation message
        assert lines[2] == "... (truncated at 2 lines)"

    def test_log_analysis_functionality(self, manager):
        """Test log analysis and streaming capabilities."""
        logs = "This is a normal log\nThis is an error log\nThis is an exception\nNormal log again"
        result = manager._analyze_job_logs(logs)

        assert result and result["error_count"] == 2
        assert len(result["errors"]) == 2
        assert "error" in result["errors"][0].lower()


if __name__ == "__main__":
    pytest.main([__file__])
