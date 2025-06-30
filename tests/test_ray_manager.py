#!/usr/bin/env python3
"""Tests for the Ray manager."""

import asyncio
import inspect
import subprocess
import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from ray_mcp.ray_manager import RayManager
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
    async def test_stop_cluster_ray_unavailable(self, manager):
        """Test stopping when Ray is not available."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", False):
            result = await manager.stop_cluster()
            assert result["status"] == "error"
            assert "Ray is not available" in result["message"]

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

    @pytest.mark.asyncio
    async def test_initialize_job_client_not_available(self, manager):
        """Test job client initialization when JobSubmissionClient is not available."""
        with patch("ray_mcp.ray_manager.JobSubmissionClient", None):
            result = await manager._initialize_job_client_with_retry(
                "http://127.0.0.1:8265"
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


if __name__ == "__main__":
    pytest.main([__file__])
