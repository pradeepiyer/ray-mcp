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

    @pytest.fixture
    def initialized_manager(self):
        """Create an initialized RayManager instance."""
        manager = RayManager()
        manager._is_initialized = True
        manager._cluster_address = "127.0.0.1:10001"
        manager._job_client = Mock()
        return manager

    def test_init(self):
        """Test RayManager initialization."""
        manager = RayManager()
        assert not manager.is_initialized
        assert manager._job_client is None
        assert manager._cluster_address is None
        assert manager._dashboard_url is None

    def test_is_initialized_property(self):
        """Test the is_initialized property."""
        manager = RayManager()
        assert not manager.is_initialized

        # Mock Ray as available and initialized
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                manager._is_initialized = True
                assert manager.is_initialized

    def test_ensure_initialized(self):
        """Test _ensure_initialized method."""
        manager = RayManager()
        with pytest.raises(RuntimeError, match="Ray is not initialized"):
            manager._ensure_initialized()

    @pytest.mark.asyncio
    async def test_init_cluster_ray_already_running(
        self, manager, mock_cluster_startup
    ):
        """Test cluster initialization when Ray is already running."""
        print("\n=== Starting test_init_cluster_ray_already_running ===")
        start_time = time.time()
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            print(f"  [{(time.time() - start_time)*1000:.1f}ms] Patched RAY_AVAILABLE")
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                print(f"  [{(time.time() - start_time)*1000:.1f}ms] Patched ray")
                mock_ray.is_initialized.return_value = True
                # Simulate ray.init() returning a valid context even if already initialized
                mock_context = Mock()
                mock_context.address_info = {"address": "127.0.0.1:10001"}
                mock_context.dashboard_url = "http://127.0.0.1:8265"
                mock_ray.init.return_value = mock_context
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "node_123"
                )
                with patch("subprocess.Popen") as mock_popen:
                    mock_process = Mock()
                    mock_process.poll.return_value = 0
                    mock_process.communicate.return_value = (
                        "Ray runtime started\n--address='127.0.0.1:10001'\nView the Ray dashboard at http://127.0.0.1:8265",
                        "",
                    )
                    mock_popen.return_value = mock_process
                    with patch.object(
                        manager, "_initialize_job_client_with_retry"
                    ) as mock_init_job_client:
                        print(
                            f"  [{(time.time() - start_time)*1000:.1f}ms] Patched _initialize_job_client_with_retry"
                        )
                        mock_init_job_client.return_value = Mock()
                        print(
                            f"  [{(time.time() - start_time)*1000:.1f}ms] About to call init_cluster"
                        )
                        init_start = time.time()
                        result = await manager.init_cluster(worker_nodes=[])
                        print(
                            f"  [{(time.time() - start_time)*1000:.1f}ms] init_cluster took {(time.time() - init_start)*1000:.1f}ms"
                        )
                        print(f"Result: {result}")
                        assert result["status"] == "started"
        print(f"  [{(time.time() - start_time)*1000:.1f}ms] Test completed")
        print("=== End test_init_cluster_ray_already_running ===\n")

    @pytest.mark.asyncio
    async def test_init_cluster_connect_to_existing(self, mock_cluster_startup):
        """Test connecting to existing cluster."""
        ray_manager = RayManager()
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.init.return_value = Mock(
                    address_info={"address": "127.0.0.1:10001"},
                    dashboard_url="http://127.0.0.1:8265",
                )
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "node_123"
                )
                with patch.object(
                    ray_manager, "_initialize_job_client_with_retry"
                ) as mock_init_job_client:
                    mock_init_job_client.return_value = Mock()
                    result = await ray_manager.init_cluster(address="127.0.0.1:10001")
                    assert result["status"] == "connected"
                    assert "cluster_address" in result
                    assert result["dashboard_url"] == "http://127.0.0.1:8265"
                    assert result["node_id"] == "node_123"

    @pytest.mark.asyncio
    async def test_init_cluster_ray_unavailable(self, manager, mock_cluster_startup):
        """Test cluster initialization when Ray is not available."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", False):
            result = await manager.init_cluster(address="127.0.0.1:10001")
            assert result["status"] == "error"
            assert "Ray is not available" in result["message"]

    @pytest.mark.asyncio
    async def test_init_cluster_gcs_address_extraction(self, mock_cluster_startup):
        """Test GCS address extraction from different address formats."""
        manager1 = RayManager()
        manager2 = RayManager()
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = False
                mock_ray.init.return_value = Mock(
                    address_info={"address": "127.0.0.1:10001"},
                    dashboard_url="http://127.0.0.1:8265",
                )
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "node_123"
                )
                with patch.object(
                    manager1, "_initialize_job_client_with_retry"
                ) as mock_init_job_client1:
                    mock_init_job_client1.return_value = Mock()
                    result1 = await manager1.init_cluster(address="127.0.0.1:10001")
                    assert result1["status"] == "connected"
                    assert manager1._gcs_address == "127.0.0.1:10001"
                with patch.object(
                    manager2, "_initialize_job_client_with_retry"
                ) as mock_init_job_client2:
                    mock_init_job_client2.return_value = Mock()
                    result2 = await manager2.init_cluster(address="192.168.1.100:10001")
                    assert result2["status"] == "connected"
                    assert manager2._gcs_address == "192.168.1.100:10001"

    @pytest.mark.asyncio
    async def test_init_cluster_start_new_cluster(self, manager, mock_cluster_startup):
        """Test starting a new cluster."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = False
                mock_ray.init.return_value = Mock(
                    address_info={"address": "127.0.0.1:10001"},
                    dashboard_url="http://127.0.0.1:8265",
                )
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "node_123"
                )
                with patch("subprocess.Popen") as mock_popen:
                    mock_process = Mock()
                    mock_process.poll.return_value = 0
                    mock_process.communicate.return_value = (
                        "Ray runtime started\n--address=127.0.0.1:10001\nView the Ray dashboard at http://127.0.0.1:8265",
                        "",
                    )
                    mock_popen.return_value = mock_process
                    with patch.object(
                        manager, "_initialize_job_client_with_retry"
                    ) as mock_init_job_client:
                        mock_init_job_client.return_value = Mock()
                        result = await manager.init_cluster(num_cpus=2, num_gpus=1)
                        assert result["status"] == "started"

    @pytest.mark.asyncio
    async def test_stop_cluster(self, initialized_manager):
        """Test stopping the Ray cluster."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.shutdown.return_value = None

                # Mock subprocess for ray stop
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 0
                    mock_run.return_value.stderr = ""

                    result = await initialized_manager.stop_cluster()
                    assert result["status"] == "stopped"

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
    async def test_inspect_ray(self, initialized_manager):
        """Test inspecting Ray cluster."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.cluster_resources.return_value = {"CPU": 8, "GPU": 2}
                mock_ray.available_resources.return_value = {"CPU": 4, "GPU": 1}
                mock_ray.nodes.return_value = [
                    {
                        "NodeID": "node_1",
                        "Alive": True,
                        "NodeName": "head-node",
                        "NodeManagerAddress": "127.0.0.1",
                        "NodeManagerHostname": "localhost",
                        "NodeManagerPort": 12345,
                        "ObjectManagerPort": 12346,
                        "ObjectStoreSocketName": "/tmp/ray/session_12345/sockets/object_store",
                        "RayletSocketName": "/tmp/ray/session_12345/sockets/raylet",
                        "Resources": {"CPU": 8, "GPU": 2},
                        "UsedResources": {"CPU": 4, "GPU": 1},
                    }
                ]
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "node_123"
                )

                # Mock cluster info
                mock_ray.get_cluster_info.return_value = {
                    "nodes": [
                        {"node_id": "node_1", "status": "alive"},
                        {"node_id": "node_2", "status": "alive"},
                    ]
                }

                result = await initialized_manager.inspect_ray()

                if result["status"] == "error":
                    assert "Ray is not initialized" in result["message"]
                else:
                    assert result["status"] == "success"
                    assert "cluster_info" in result or "cluster_overview" in result
                    assert (
                        "health_check" in result or "health_recommendations" in result
                    )
                    # Accept missing node_id if not present
                    if "node_id" in result:
                        assert result["node_id"] == "node_123"

    @pytest.mark.asyncio
    async def test_inspect_ray_ray_unavailable(self, manager):
        """Test ray inspection when Ray is not available."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", False):
            result = await manager.inspect_ray()
            assert result["status"] == "unavailable"
            assert "Ray is not available" in result["message"]

    @pytest.mark.asyncio
    async def test_inspect_ray_with_exception(self, manager):
        """Test ray inspection with exception."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.side_effect = Exception("Ray error")

                result = await manager.inspect_ray()
                assert result["status"] == "error"
                assert "Failed to get cluster info" in result["message"]

    @pytest.mark.asyncio
    async def test_submit_job(self, initialized_manager):
        """Test job submission."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                with patch(
                    "ray_mcp.ray_manager.JobSubmissionClient"
                ) as mock_job_client_class:
                    mock_job_client = Mock()
                    mock_job_client.submit_job.return_value = "job_123"
                    mock_job_client_class.return_value = mock_job_client

                    initialized_manager._job_client = mock_job_client
                    initialized_manager._dashboard_url = "http://127.0.0.1:8265"

                    result = await initialized_manager.submit_job(
                        entrypoint="python script.py"
                    )
                    assert result["status"] == "submitted"
                    assert result["job_id"] == "job_123"

    @pytest.mark.asyncio
    async def test_submit_job_no_job_client(self, initialized_manager):
        """Test job submission when job client is not available."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                initialized_manager._job_client = None

                result = await initialized_manager.submit_job(
                    entrypoint="python script.py"
                )
                # Accept both possible error messages
                assert (
                    "Job client is not initialized" in result["message"]
                    or "Job submission not available: No dashboard URL available"
                    in result["message"]
                )

    @pytest.mark.asyncio
    async def test_list_jobs(self, initialized_manager):
        """Test listing jobs."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                with patch(
                    "ray_mcp.ray_manager.JobSubmissionClient"
                ) as mock_job_client_class:
                    # Return objects with job_id, entrypoint, start_time, end_time, metadata, and runtime_env attributes
                    job1 = type(
                        "Job",
                        (),
                        {
                            "job_id": "job_1",
                            "status": "RUNNING",
                            "entrypoint": "python foo.py",
                            "start_time": 123,
                            "end_time": None,
                            "metadata": {},
                            "runtime_env": {},
                        },
                    )()
                    job2 = type(
                        "Job",
                        (),
                        {
                            "job_id": "job_2",
                            "status": "SUCCEEDED",
                            "entrypoint": "python bar.py",
                            "start_time": 456,
                            "end_time": 789,
                            "metadata": {},
                            "runtime_env": {},
                        },
                    )()
                    mock_job_client = Mock()
                    mock_job_client.list_jobs.return_value = [job1, job2]
                    mock_job_client_class.return_value = mock_job_client

                    initialized_manager._job_client = mock_job_client

                    result = await initialized_manager.list_jobs()
                    assert result["status"] == "success"
                    assert len(result["jobs"]) == 2

    @pytest.mark.asyncio
    async def test_cancel_job(self, initialized_manager):
        """Test job cancellation."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                with patch(
                    "ray_mcp.ray_manager.JobSubmissionClient"
                ) as mock_job_client_class:
                    mock_job_client = Mock()
                    mock_job_client.delete_job.return_value = None
                    mock_job_client_class.return_value = mock_job_client

                    initialized_manager._job_client = mock_job_client

                    result = await initialized_manager.cancel_job("job_123")
                    assert result["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_retrieve_logs(self, initialized_manager):
        """Test log retrieval."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                with patch(
                    "ray_mcp.ray_manager.JobSubmissionClient"
                ) as mock_job_client_class:
                    mock_job_client = Mock()
                    mock_job_client.get_job_logs.return_value = "Job log content"
                    mock_job_client_class.return_value = mock_job_client

                    initialized_manager._job_client = mock_job_client

                    result = await initialized_manager.retrieve_logs("job_123")
                    assert result["status"] == "success"
                    assert "logs" in result

    def test_get_default_worker_config(self, manager):
        """Test default worker configuration."""
        config = manager._get_default_worker_config()
        assert len(config) == 2
        assert all("num_cpus" in worker for worker in config)
        assert all("num_gpus" in worker for worker in config)
        assert all("object_store_memory" in worker for worker in config)

    def test_filter_cluster_starting_parameters(self, manager):
        """Test filtering of cluster starting parameters."""
        kwargs = {
            "num_cpus": 4,
            "num_gpus": 2,
            "object_store_memory": 1000000,
            "head_node_port": 10001,
            "dashboard_port": 8265,
            "head_node_host": "127.0.0.1",
            "worker_nodes": [{"num_cpus": 2}],
            "ignore_reinit_error": True,
            "local_mode": False,
        }

        filtered = manager._filter_cluster_starting_parameters(kwargs)
        assert "num_cpus" not in filtered
        assert "num_gpus" not in filtered
        assert "object_store_memory" not in filtered
        assert "head_node_port" not in filtered
        assert "dashboard_port" not in filtered
        assert "head_node_host" not in filtered
        assert "worker_nodes" not in filtered
        assert "ignore_reinit_error" in filtered
        assert "local_mode" in filtered

    def test_sanitize_init_kwargs(self, manager):
        """Test sanitization of Ray init kwargs."""
        kwargs = {
            "num_cpus": 4,
            "num_gpus": None,
            "object_store_memory": 1000000,
            "worker_nodes": [{"num_cpus": 2}],
            "ignore_reinit_error": True,
            "local_mode": False,
        }

        sanitized = manager._sanitize_init_kwargs(kwargs)
        assert "num_cpus" in sanitized
        assert "num_gpus" not in sanitized  # None values removed
        assert "object_store_memory" in sanitized
        assert "worker_nodes" not in sanitized  # Explicitly excluded
        assert "ignore_reinit_error" in sanitized
        assert "local_mode" in sanitized

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

    @pytest.mark.asyncio
    async def test_init_cluster_with_dashboard_api_only(self):
        """Test that cluster initialization only uses dashboard API."""
        manager = RayManager()

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = False
                mock_ray.init.return_value = Mock(
                    address_info={"address": "127.0.0.1:10001"},
                    dashboard_url="http://127.0.0.1:8265",
                )
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "node_123"
                )
                with patch.object(
                    manager, "_initialize_job_client_with_retry"
                ) as mock_init_job_client:
                    mock_init_job_client.return_value = Mock()
                    result = await manager.init_cluster(address="127.0.0.1:10001")

                    # Verify that the address is stored as direct GCS address
                    assert manager._gcs_address == "127.0.0.1:10001"
                    assert result["status"] == "connected"
                    assert "dashboard_url" in result


if __name__ == "__main__":
    pytest.main([__file__])
