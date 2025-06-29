"""Tests for streaming log retrieval functionality."""

import asyncio
import sys
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Add the parent directory to the path to import ray_mcp
sys.path.insert(0, "..")

from ray_mcp.ray_manager import RayManager


class TestStreamingLogs:
    """Test cases for streaming log retrieval functionality."""

    @pytest.fixture
    def ray_manager(self):
        """Create a RayManager instance for testing."""
        manager = RayManager()
        # Mock the initialization to avoid actual Ray initialization
        manager._is_initialized = True
        manager.__is_initialized = True  # Set both flags
        manager._job_client = Mock()

        # Mock the _ensure_initialized method to avoid Ray dependency
        def mock_ensure_initialized():
            pass

        manager._ensure_initialized = mock_ensure_initialized
        return manager

    def test_validate_log_parameters_valid(self, ray_manager):
        """Test parameter validation with valid parameters."""
        result = ray_manager._validate_log_parameters(100, 10)
        assert result is None

    def test_validate_log_parameters_invalid_num_lines(self, ray_manager):
        """Test parameter validation with invalid num_lines."""
        result = ray_manager._validate_log_parameters(0, 10)
        assert result["status"] == "error"
        assert "num_lines must be positive" in result["message"]

        result = ray_manager._validate_log_parameters(15000, 10)
        assert result["status"] == "error"
        assert "num_lines cannot exceed 10000" in result["message"]

    def test_validate_log_parameters_invalid_max_size(self, ray_manager):
        """Test parameter validation with invalid max_size_mb."""
        result = ray_manager._validate_log_parameters(100, 0)
        assert result["status"] == "error"
        assert "max_size_mb must be between 1 and 100" in result["message"]

        result = ray_manager._validate_log_parameters(100, 150)
        assert result["status"] == "error"
        assert "max_size_mb must be between 1 and 100" in result["message"]

    def test_truncate_logs_to_size_within_limit(self, ray_manager):
        """Test log truncation when logs are within size limit."""
        logs = "This is a test log\nwith multiple lines\nbut small size"
        result = ray_manager._truncate_logs_to_size(logs, 10)
        assert result == logs

    def test_truncate_logs_to_size_exceeds_limit(self, ray_manager):
        """Test log truncation when logs exceed size limit."""
        # Create a large log that exceeds 1MB
        large_log = "x" * (2 * 1024 * 1024)  # 2MB of data
        result = ray_manager._truncate_logs_to_size(large_log, 1)

        max_allowed = 1024 * 1024 + 1024  # 1MB + 1KB buffer for truncation message
        assert len(result.encode("utf-8")) <= max_allowed
        assert "... (truncated at 1MB limit)" in result

    def test_stream_logs_with_limits_string_input(self, ray_manager):
        """Test streaming logs with string input."""
        logs = "line1\nline2\nline3\nline4\nline5"
        result = ray_manager._stream_logs_with_limits(logs, max_lines=3, max_size_mb=1)

        lines = result.split("\n")
        # Should have 3 lines plus the truncation message
        assert len(lines) == 4
        assert lines[0] == "line1"
        assert lines[1] == "line2"
        assert lines[2] == "line3"
        assert "... (truncated at 3 lines)" in lines[3]

    def test_stream_logs_with_limits_list_input(self, ray_manager):
        """Test streaming logs with list input."""
        logs = ["line1", "line2", "line3", "line4", "line5"]
        result = ray_manager._stream_logs_with_limits(logs, max_lines=3, max_size_mb=1)

        lines = result.split("\n")
        # Should have 3 lines plus the truncation message
        assert len(lines) == 4
        assert lines[0] == "line1"
        assert lines[1] == "line2"
        assert lines[2] == "line3"
        assert "... (truncated at 3 lines)" in lines[3]

    def test_stream_logs_with_limits_size_exceeded(self, ray_manager):
        """Test streaming logs when size limit is exceeded."""
        # Create lines that will exceed the size limit
        large_line = "x" * 1024  # 1KB per line
        logs = [large_line] * 2000  # 2000 lines of 1KB each = ~2MB

        result = ray_manager._stream_logs_with_limits(
            logs, max_lines=3000, max_size_mb=1
        )

        # Should be truncated due to size limit
        if "... (truncated at 1MB limit)" not in result:
            print(f"Result length: {len(result)}")
            print(f"Result snippet: {result[-200:]}")
        assert "... (truncated at 1MB limit)" in result

    def test_stream_logs_with_limits_line_limit_exceeded(self, ray_manager):
        """Test streaming logs when line limit is exceeded."""
        logs = ["line" + str(i) for i in range(100)]
        result = ray_manager._stream_logs_with_limits(
            logs, max_lines=10, max_size_mb=10
        )

        lines = result.split("\n")
        # Should have 10 lines plus the truncation message
        assert len(lines) == 11
        assert "... (truncated at 10 lines)" in lines[10]

    @pytest.mark.asyncio
    async def test_stream_logs_async(self, ray_manager):
        """Test async streaming logs."""
        logs = "line1\nline2\nline3"
        result = await ray_manager._stream_logs_async(logs, max_lines=2, max_size_mb=1)

        lines = result.split("\n")
        # Should have 2 lines plus the truncation message
        assert len(lines) == 3
        assert lines[0] == "line1"
        assert lines[1] == "line2"
        assert "... (truncated at 2 lines)" in lines[2]

    @pytest.mark.asyncio
    async def test_stream_logs_with_pagination(self, ray_manager):
        """Test paginated log streaming."""
        logs = ["line" + str(i) for i in range(1, 101)]  # 100 lines

        # Test first page
        result = await ray_manager._stream_logs_with_pagination(
            logs, page=1, page_size=20, max_size_mb=1
        )
        assert result["status"] == "success"
        assert result["pagination"]["current_page"] == 1
        assert result["pagination"]["total_pages"] == 5
        assert result["pagination"]["total_lines"] == 100
        assert result["pagination"]["lines_in_page"] == 20
        assert result["pagination"]["has_next"] is True
        assert result["pagination"]["has_previous"] is False

        # Test last page
        result = await ray_manager._stream_logs_with_pagination(
            logs, page=5, page_size=20, max_size_mb=1
        )
        assert result["status"] == "success"
        assert result["pagination"]["current_page"] == 5
        assert result["pagination"]["has_next"] is False
        assert result["pagination"]["has_previous"] is True

    @pytest.mark.asyncio
    async def test_stream_logs_with_pagination_invalid_page(self, ray_manager):
        """Test paginated log streaming with invalid page number."""
        logs = ["line" + str(i) for i in range(1, 101)]  # 100 lines

        result = await ray_manager._stream_logs_with_pagination(
            logs, page=10, page_size=20, max_size_mb=1
        )
        assert result["status"] == "error"
        assert "Invalid page number" in result["message"]

    @pytest.mark.asyncio
    async def test_retrieve_logs_with_streaming(self, ray_manager):
        """Test retrieve_logs with streaming approach."""
        # Mock job client
        mock_logs = "line1\nline2\nline3\nline4\nline5"
        ray_manager._job_client.get_job_logs.return_value = mock_logs

        result = await ray_manager.retrieve_logs(
            identifier="test_job", log_type="job", num_lines=3, max_size_mb=10
        )

        assert result["status"] == "success"
        assert result["log_type"] == "job"
        assert result["identifier"] == "test_job"

        # Should have 3 lines plus truncation message = 4 lines total
        lines = result["logs"].split("\n")
        assert len(lines) == 4
        assert lines[0] == "line1"
        assert lines[1] == "line2"
        assert lines[2] == "line3"
        assert "... (truncated at 3 lines)" in lines[3]

    @pytest.mark.asyncio
    async def test_retrieve_logs_with_size_truncation(self, ray_manager):
        """Test retrieve_logs with size truncation."""
        # Mock job client with large logs
        large_logs = "x" * (20 * 1024 * 1024)  # 20MB of data
        ray_manager._job_client.get_job_logs.return_value = large_logs

        result = await ray_manager.retrieve_logs(
            identifier="test_job",
            log_type="job",
            num_lines=100,
            max_size_mb=5,  # 5MB limit
        )

        assert result["status"] == "success"
        assert "warning" in result
        assert "truncated to 5MB limit" in result["warning"]
        assert result["original_size_mb"] == 20.0

        # Check that the logs are actually truncated
        max_allowed = 5 * 1024 * 1024 + 1024  # 5MB + 1KB buffer for truncation message
        assert len(result["logs"].encode("utf-8")) <= max_allowed

    @pytest.mark.asyncio
    async def test_retrieve_logs_paginated(self, ray_manager):
        """Test retrieve_logs_paginated functionality."""
        # Mock job client
        mock_logs = "\n".join([f"line{i}" for i in range(1, 101)])  # 100 lines
        ray_manager._job_client.get_job_logs.return_value = mock_logs

        result = await ray_manager.retrieve_logs_paginated(
            identifier="test_job", log_type="job", page=2, page_size=20, max_size_mb=10
        )

        assert result["status"] == "success"
        assert result["log_type"] == "job"
        assert result["identifier"] == "test_job"
        assert "pagination" in result
        assert result["pagination"]["current_page"] == 2
        assert result["pagination"]["total_pages"] == 5

    def test_analyze_job_logs_with_streaming(self, ray_manager):
        """Test log analysis with streaming approach."""
        logs = "This is a normal log\nThis is an error log\nThis is an exception\nNormal log again"
        result = ray_manager._analyze_job_logs(logs)

        assert result["error_count"] == 2
        assert len(result["errors"]) == 2
        assert "error" in result["errors"][0].lower()
        assert "exception" in result["errors"][1].lower()
        assert len(result["suggestions"]) > 0


if __name__ == "__main__":
    pytest.main([__file__])
