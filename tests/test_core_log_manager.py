"""Unit tests for RayLogManager component.

Tests focus on log management behavior with 100% mocking.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ray_mcp.managers.log_manager import RayLogManager


@pytest.mark.fast
class TestRayLogManagerCore:
    """Test core log management functionality."""

    def test_manager_instantiation(self):
        """Test that log manager can be instantiated with state manager."""
        state_manager = Mock()
        manager = RayLogManager(state_manager)
        assert manager is not None
        assert manager.state_manager == state_manager
        # Test that the new base functionality is available
        assert hasattr(manager, "_log_info")
        assert hasattr(manager, "_format_success_response")
        assert hasattr(manager, "_execute_operation")

    async def test_retrieve_logs_validation_success_job(self):
        """Test log retrieval with valid job parameters."""
        state_manager = Mock()
        state_manager.is_initialized.return_value = True
        manager = RayLogManager(state_manager)

        # Mock the job retrieval method
        with patch.object(manager, "_retrieve_job_logs_unified") as mock_method:
            mock_method.return_value = {"status": "success", "logs": "test logs"}

            result = await manager.retrieve_logs(
                "test_id", log_type="job", num_lines=50
            )

            assert result["status"] == "success"
            mock_method.assert_called_once()

    @pytest.mark.parametrize("identifier", ["", None, "   ", 123])
    async def test_retrieve_logs_invalid_identifier(self, identifier):
        """Test log retrieval with invalid identifier."""
        state_manager = Mock()
        manager = RayLogManager(state_manager)

        result = await manager.retrieve_logs(identifier, log_type="job")

        assert result["status"] == "error"
        assert "Identifier must be a non-empty string" in result["message"]

    @pytest.mark.parametrize("log_type", ["invalid", "JOB"])
    async def test_retrieve_logs_invalid_log_type_validation(self, log_type):
        """Test log retrieval with various invalid log types."""
        state_manager = Mock()
        manager = RayLogManager(state_manager)

        result = await manager.retrieve_logs("test_id", log_type=log_type)

        assert result["status"] == "error"
        if log_type.lower() != "job":
            assert "Only 'job' is supported" in result["message"]

    @pytest.mark.parametrize("num_lines", [0, -1, 10001])
    async def test_retrieve_logs_invalid_num_lines(self, num_lines):
        """Test log retrieval with invalid num_lines."""
        state_manager = Mock()
        manager = RayLogManager(state_manager)

        result = await manager.retrieve_logs(
            "test_id", log_type="job", num_lines=num_lines
        )

        assert result["status"] == "error"
        assert "num_lines must be between 1 and 10000" in result["message"]

    @pytest.mark.parametrize("max_size_mb", [0, -1, 101])
    async def test_retrieve_logs_invalid_max_size(self, max_size_mb):
        """Test log retrieval with invalid max_size_mb."""
        state_manager = Mock()
        manager = RayLogManager(state_manager)

        result = await manager.retrieve_logs(
            "test_id", log_type="job", max_size_mb=max_size_mb
        )

        assert result["status"] == "error"
        assert "max_size_mb must be between 1 and 100" in result["message"]


@pytest.mark.fast
class TestRayLogManagerJobLogs:
    """Test job log retrieval functionality."""

    async def test_retrieve_job_logs_success(self):
        """Test successful job log retrieval."""
        state_manager = Mock()
        state_manager.is_initialized.return_value = True

        # Mock job client
        mock_client = Mock()
        mock_client.get_job_logs.return_value = "Job log content\nLine 2\nLine 3"

        manager = RayLogManager(state_manager)
        manager._RAY_AVAILABLE = True
        manager._JobSubmissionClient = Mock(return_value=mock_client)

        with patch.object(manager, "_get_job_client", return_value=mock_client):
            result = await manager._retrieve_job_logs_unified("job_123", num_lines=100)

        assert result["status"] == "success"
        assert result["log_type"] == "job"
        assert result["identifier"] == "job_123"
        assert "Job log content" in result["logs"]
        mock_client.get_job_logs.assert_called_with("job_123")

    async def test_retrieve_job_logs_no_client(self):
        """Test job log retrieval when no client is available."""
        state_manager = Mock()
        state_manager.is_initialized.return_value = True
        manager = RayLogManager(state_manager)

        with patch.object(manager, "_get_job_client", return_value=None):
            result = await manager._retrieve_job_logs_unified("job_123")

        assert result["status"] == "error"
        assert result["log_type"] == "job"
        assert "Job client not available" in result["error"]

    async def test_retrieve_job_logs_with_error_analysis(self):
        """Test job log retrieval with error analysis."""
        state_manager = Mock()
        state_manager.is_initialized.return_value = True

        mock_client = Mock()
        mock_client.get_job_logs.return_value = (
            "INFO: Starting job\nERROR: Something failed\nINFO: Continuing"
        )

        manager = RayLogManager(state_manager)

        with patch.object(manager, "_get_job_client", return_value=mock_client):
            result = await manager._retrieve_job_logs_unified(
                "job_123", include_errors=True
            )

        assert result["status"] == "success"
        assert "error_analysis" in result
        assert result["error_analysis"]["errors_found"] is True
        assert result["error_analysis"]["error_count"] == 1

    async def test_retrieve_job_logs_paginated(self):
        """Test job log retrieval with pagination."""
        state_manager = Mock()
        state_manager.is_initialized.return_value = True

        mock_client = Mock()
        mock_client.get_job_logs.return_value = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"

        manager = RayLogManager(state_manager)

        with patch.object(manager, "_get_job_client", return_value=mock_client):
            with patch.object(
                manager._log_processor, "stream_logs_with_pagination"
            ) as mock_paginate:
                mock_paginate.return_value = {
                    "status": "success",
                    "logs": "Line 3\nLine 4",
                    "pagination": {"current_page": 2, "total_pages": 3},
                }

                result = await manager._retrieve_job_logs_paginated(
                    "job_123", page=2, page_size=2
                )

        assert result["status"] == "success"
        assert result["log_type"] == "job"
        assert result["pagination"]["current_page"] == 2


@pytest.mark.fast
class TestRayLogManagerErrorAnalysis:
    """Test log error analysis functionality."""

    def test_analyze_job_logs_with_errors(self):
        """Test log analysis with various error patterns."""
        manager = RayLogManager(Mock())

        logs = """INFO: Job started successfully
ERROR: Database connection failed
WARNING: Retrying connection
Exception: ValueError occurred
INFO: Processing data
CRITICAL: System failure
Traceback (most recent call last):
FAILED: Operation unsuccessful"""

        analysis = manager._analyze_job_logs(logs)

        assert analysis["errors_found"] is True
        assert (
            analysis["error_count"] == 5
        )  # ERROR, Exception, CRITICAL, Traceback, FAILED
        assert len(analysis["errors"]) == 5
        assert analysis["total_lines_analyzed"] == 8  # Split by newlines

    def test_analyze_job_logs_no_errors(self):
        """Test log analysis with no errors."""
        manager = RayLogManager(Mock())

        logs = """
        INFO: Job started successfully
        INFO: Processing data
        INFO: Job completed successfully
        """

        analysis = manager._analyze_job_logs(logs)

        assert analysis["errors_found"] is False
        assert analysis["error_count"] == 0
        assert len(analysis["errors"]) == 0

    def test_analyze_job_logs_empty(self):
        """Test log analysis with empty logs."""
        manager = RayLogManager(Mock())

        analysis = manager._analyze_job_logs("")

        assert analysis["errors_found"] is False
        assert "No logs to analyze" in analysis["analysis"]

    def test_analyze_job_logs_limits_errors(self):
        """Test that error analysis limits to first 10 errors."""
        manager = RayLogManager(Mock())

        # Create logs with more than 10 errors
        error_lines = [f"ERROR: Error {i}" for i in range(15)]
        logs = "\n".join(error_lines)

        analysis = manager._analyze_job_logs(logs)

        assert analysis["errors_found"] is True
        assert analysis["error_count"] == 15
        assert len(analysis["errors"]) == 10  # Limited to 10


@pytest.mark.fast
class TestRayLogManagerClientHandling:
    """Test job client handling functionality."""

    async def test_get_job_client_from_state(self):
        """Test getting job client from state."""
        existing_client = Mock()
        state_manager = Mock()
        state_manager.get_state.return_value = {"job_client": existing_client}

        manager = RayLogManager(state_manager)
        manager._RAY_AVAILABLE = True

        client = await manager._get_job_client()

        assert client == existing_client

    async def test_get_job_client_create_new(self):
        """Test creating new job client when none exists."""
        mock_client = Mock()
        mock_client.list_jobs.return_value = []

        state_manager = Mock()
        state_manager.get_state.return_value = {
            "job_client": None,
            "dashboard_url": "http://127.0.0.1:8265",
        }

        manager = RayLogManager(state_manager)
        manager._RAY_AVAILABLE = True
        manager._JobSubmissionClient = Mock(return_value=mock_client)

        client = await manager._get_job_client()

        assert client == mock_client
        manager._JobSubmissionClient.assert_called_with("http://127.0.0.1:8265")
        state_manager.update_state.assert_called_with(job_client=mock_client)

    async def test_get_job_client_ray_not_available(self):
        """Test getting job client when Ray is not available."""
        state_manager = Mock()
        manager = RayLogManager(state_manager)
        manager._RAY_AVAILABLE = False

        # The _get_job_client method calls _ensure_ray_available which raises an exception
        # when Ray is not available, so we need to handle that
        with pytest.raises(RuntimeError, match="Ray is not available"):
            await manager._get_job_client()


@pytest.mark.fast
class TestLogProcessorMemoryEfficiency:
    """Test memory efficiency of log processing."""

    def test_stream_logs_with_limits_memory_efficient_processing(self):
        """Test that large logs are processed memory-efficiently."""
        from ray_mcp.foundation.logging_utils import LogProcessor

        # Create a large log string (5MB)
        large_log = "INFO: Processing data\n" * 100000

        # Process with small limits
        result = LogProcessor.stream_logs_with_limits(
            large_log, max_lines=10, max_size_mb=1
        )

        # Should only return first 10 lines
        lines = result.split("\n")
        assert len(lines) <= 11  # 10 lines + truncation message
        assert "INFO: Processing data" in result
        assert "truncated" in result

    def test_stream_logs_with_limits_per_line_size_protection(self):
        """Test protection against individual large lines."""
        from ray_mcp.foundation.logging_utils import LogProcessor

        # Create log with one very large line
        large_line = "ERROR: " + "A" * 50000  # 50KB line
        logs = f"INFO: Start\n{large_line}\nINFO: End"

        result = LogProcessor.stream_logs_with_limits(
            logs, max_lines=10, max_size_mb=1, max_line_size_kb=1
        )

        lines = result.split("\n")
        assert "INFO: Start" in result
        assert "INFO: End" in result
        # Large line should be truncated
        large_line_found = any("truncated" in line for line in lines)
        assert large_line_found

    async def test_stream_logs_with_pagination_large_logs_estimation(self):
        """Test that pagination handles large logs efficiently with estimation."""
        from ray_mcp.foundation.logging_utils import LogProcessor

        # Create a large log string (15MB)
        large_log = "INFO: Processing data\n" * 300000

        result = await LogProcessor.stream_logs_with_pagination(
            large_log, page=1, page_size=10, max_size_mb=1
        )

        assert result["status"] == "success"
        assert result["pagination"]["current_page"] == 1
        assert result["pagination"]["page_size"] == 10
        # Should have estimated total lines
        assert result["pagination"]["total_lines"] > 0
