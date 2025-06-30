#!/usr/bin/env python3
"""Tests for multi-node cluster functionality."""

import asyncio
import json
import subprocess
import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from ray_mcp.ray_manager import RayManager
from ray_mcp.worker_manager import WorkerManager
from tests.conftest import mock_cluster_startup


@pytest.mark.fast
class TestMultiNodeCluster:
    """Test cases for multi-node cluster functionality."""

    @pytest.fixture
    def ray_manager(self):
        """Create a RayManager instance for testing."""
        return RayManager()

    @pytest.fixture
    def worker_manager(self):
        """Create a WorkerManager instance for testing."""
        return WorkerManager()

    @pytest.mark.asyncio
    async def test_stop_cluster_with_worker_nodes(self):
        """Test stopping cluster with worker nodes."""
        ray_manager = RayManager()

        # Mock Ray availability and shutdown
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.shutdown.return_value = None

                # Mock subprocess for head node stop
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 0
                    mock_run.return_value.stderr = ""

                    # Mock worker manager
                    with patch.object(
                        ray_manager._worker_manager,
                        "stop_all_workers",
                        new_callable=AsyncMock,
                    ) as mock_stop_workers:
                        mock_stop_workers.return_value = [
                            {"status": "stopped", "node_name": "worker-1"},
                            {"status": "stopped", "node_name": "worker-2"},
                        ]

                        result = await ray_manager.stop_cluster()

                        assert result["status"] == "success"
                        assert result["result_type"] == "stopped"
                        assert "Ray cluster stopped successfully" in result["message"]
                        assert result["worker_nodes"] == [
                            {"status": "stopped", "node_name": "worker-1"},
                            {"status": "stopped", "node_name": "worker-2"},
                        ]

                        # Verify worker manager was called
                        mock_stop_workers.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_cluster_without_worker_nodes(self):
        """Test stopping cluster without worker nodes."""
        ray_manager = RayManager()

        # Mock Ray availability and shutdown
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.shutdown.return_value = None

                # Mock subprocess for head node stop
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 0
                    mock_run.return_value.stderr = ""

                    # Mock worker manager
                    with patch.object(
                        ray_manager._worker_manager,
                        "stop_all_workers",
                        new_callable=AsyncMock,
                    ) as mock_stop_workers:
                        mock_stop_workers.return_value = []

                        result = await ray_manager.stop_cluster()

                        assert result["status"] == "success"
                        assert result["result_type"] == "stopped"
                        assert "Ray cluster stopped successfully" in result["message"]
                        assert result["worker_nodes"] == []

                        # Verify worker manager was called
                        mock_stop_workers.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_cluster_not_running(self):
        """Test stopping cluster when not running."""
        ray_manager = RayManager()

        # Mock Ray availability
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = False

                result = await ray_manager.stop_cluster()

                assert result["status"] == "not_running"
                assert "Ray cluster is not running" in result["message"]

    @pytest.mark.asyncio
    async def test_stop_cluster_ray_unavailable(self):
        """Test stopping cluster when Ray is not available."""
        ray_manager = RayManager()

        # Mock Ray unavailability
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", False):
            result = await ray_manager.stop_cluster()

            assert result["status"] == "error"
            assert "Ray is not available" in result["message"]

    @pytest.mark.asyncio
    async def test_stop_cluster_exception(self):
        """Test stopping cluster with exception."""
        ray_manager = RayManager()

        # Mock Ray availability and shutdown exception
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.shutdown.side_effect = Exception("Shutdown failed")

                result = await ray_manager.stop_cluster()

                assert result["status"] == "error"
                assert "Shutdown failed" in result["message"]

    @pytest.mark.asyncio
    async def test_worker_manager_integration(self, mock_cluster_startup):
        """Test integration between RayManager and WorkerManager."""
        ray_manager = RayManager()
        print("\n=== Starting test_worker_manager_integration ===")
        start_time = time.time()
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            print(f"  [{(time.time() - start_time)*1000:.1f}ms] Patched RAY_AVAILABLE")
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                print(f"  [{(time.time() - start_time)*1000:.1f}ms] Patched ray")
                mock_ray.is_initialized.return_value = False
                mock_ray.init.return_value = Mock(
                    address_info={"address": "127.0.0.1:10001"},
                    dashboard_url="http://127.0.0.1:8265",
                )
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "node_123"
                )
                with patch("subprocess.Popen") as mock_popen:
                    print(
                        f"  [{(time.time() - start_time)*1000:.1f}ms] Patched subprocess.Popen"
                    )
                    mock_process = Mock()
                    mock_process.communicate.return_value = (
                        "Ray runtime started\n--address='127.0.0.1:10001'\nView the Ray dashboard at http://127.0.0.1:8265",
                        "",
                    )
                    mock_process.poll.return_value = 0
                    mock_popen.return_value = mock_process
                    with patch.object(
                        RayManager,
                        "_initialize_job_client_with_retry",
                        new_callable=AsyncMock,
                    ) as mock_init_job_client:
                        print(
                            f"  [{(time.time() - start_time)*1000:.1f}ms] Patched _initialize_job_client_with_retry"
                        )
                        mock_init_job_client.return_value = None
                        with patch.object(
                            RayManager,
                            "_communicate_with_timeout",
                            new_callable=AsyncMock,
                        ) as mock_communicate:
                            mock_communicate.return_value = (
                                "Ray runtime started\n--address='127.0.0.1:20000'\nView the Ray dashboard at http://127.0.0.1:8265",
                                "",
                            )
                            with patch.object(
                                ray_manager._worker_manager,
                                "start_worker_nodes",
                                new_callable=AsyncMock,
                            ) as mock_start_workers:
                                print(
                                    f"  [{(time.time() - start_time)*1000:.1f}ms] Patched start_worker_nodes"
                                )
                                with patch.object(
                                    ray_manager._worker_manager,
                                    "stop_all_workers",
                                    new_callable=AsyncMock,
                                ) as mock_stop_workers:
                                    print(
                                        f"  [{(time.time() - start_time)*1000:.1f}ms] Patched stop_all_workers"
                                    )
                                    mock_start_workers.return_value = [
                                        {"status": "started", "node_name": "worker-1"},
                                        {"status": "started", "node_name": "worker-2"},
                                    ]
                                    mock_stop_workers.return_value = [
                                        {"status": "stopped", "node_name": "worker-1"},
                                        {"status": "stopped", "node_name": "worker-2"},
                                    ]
                                    print(
                                        f"  [{(time.time() - start_time)*1000:.1f}ms] About to call init_cluster"
                                    )
                                    init_start = time.time()
                                    result = await ray_manager.init_cluster(
                                        num_cpus=4,
                                        head_node_port=20000,
                                        dashboard_port=8265,
                                        worker_nodes=[
                                            {"num_cpus": 2, "node_name": "worker-1"},
                                            {"num_cpus": 2, "node_name": "worker-2"},
                                        ],
                                    )
                                    print(
                                        f"  [{(time.time() - start_time)*1000:.1f}ms] init_cluster took {(time.time() - init_start)*1000:.1f}ms"
                                    )
                                    assert result["status"] == "success"
                                    assert result.get("result_type") == "started"
                                    assert len(result["worker_nodes"]) == 2
                                    mock_start_workers.assert_called_once()
                                    mock_ray.is_initialized.return_value = True
                                    mock_ray.shutdown.return_value = None
                                    with patch("subprocess.run") as mock_run:
                                        print(
                                            f"  [{(time.time() - start_time)*1000:.1f}ms] Patched subprocess.run"
                                        )
                                        mock_run.return_value.returncode = 0
                                        mock_run.return_value.stderr = ""
                                        print(
                                            f"  [{(time.time() - start_time)*1000:.1f}ms] About to call stop_cluster"
                                        )
                                        stop_start = time.time()
                                        result = await ray_manager.stop_cluster()
                                        print(
                                            f"  [{(time.time() - start_time)*1000:.1f}ms] stop_cluster took {(time.time() - stop_start)*1000:.1f}ms"
                                        )
                                        assert result["status"] == "success"
                                        assert result["result_type"] == "stopped"
                                        assert len(result["worker_nodes"]) == 2
                                        mock_stop_workers.assert_called_once()
        print(f"  [{(time.time() - start_time)*1000:.1f}ms] Test completed")
        print("=== End test_worker_manager_integration ===\n")

    @pytest.mark.asyncio
    async def test_worker_config_validation(self, mock_cluster_startup):
        """Test worker configuration validation."""
        ray_manager = RayManager()
        print("\n=== Starting test_worker_config_validation ===")
        start_time = time.time()
        invalid_worker_config = [
            {"num_cpus": -1, "node_name": "invalid-worker"},
            {"num_cpus": 0, "node_name": "invalid-worker"},
            {"invalid_param": "value", "node_name": "invalid-worker"},
        ]
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            print(f"  [{(time.time() - start_time)*1000:.1f}ms] Patched RAY_AVAILABLE")
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                print(f"  [{(time.time() - start_time)*1000:.1f}ms] Patched ray")
                mock_ray.is_initialized.return_value = False
                mock_ray.init.return_value = Mock(
                    address_info={"address": "127.0.0.1:10001"},
                    dashboard_url="http://127.0.0.1:8265",
                )
                with patch("subprocess.Popen") as mock_popen:
                    print(
                        f"  [{(time.time() - start_time)*1000:.1f}ms] Patched subprocess.Popen"
                    )
                    mock_process = Mock()
                    mock_process.communicate.return_value = (
                        "Ray runtime started\n--address='127.0.0.1:10001'\nView the Ray dashboard at http://127.0.0.1:8265",
                        "",
                    )
                    mock_process.poll.return_value = 0
                    mock_popen.return_value = mock_process
                    with patch.object(
                        RayManager,
                        "_initialize_job_client_with_retry",
                        new_callable=AsyncMock,
                    ) as mock_init_job_client:
                        print(
                            f"  [{(time.time() - start_time)*1000:.1f}ms] Patched _initialize_job_client_with_retry"
                        )
                        mock_init_job_client.return_value = None
                        with patch.object(
                            RayManager,
                            "_communicate_with_timeout",
                            new_callable=AsyncMock,
                        ) as mock_communicate:
                            mock_communicate.return_value = (
                                "Ray runtime started\n--address='127.0.0.1:20000'\nView the Ray dashboard at http://127.0.0.1:8265",
                                "",
                            )
                            with patch.object(
                                ray_manager._worker_manager,
                                "start_worker_nodes",
                                new_callable=AsyncMock,
                            ) as mock_start_workers:
                                print(
                                    f"  [{(time.time() - start_time)*1000:.1f}ms] About to call init_cluster"
                                )
                                init_start = time.time()
                                result = await ray_manager.init_cluster(
                                    num_cpus=4,
                                    head_node_port=20000,
                                    dashboard_port=8265,
                                    worker_nodes=invalid_worker_config,
                                )
                                print(
                                    f"  [{(time.time() - start_time)*1000:.1f}ms] init_cluster took {(time.time() - init_start)*1000:.1f}ms"
                                )
                                assert result["status"] == "success"
                                assert result.get("result_type") == "started"
        print(f"  [{(time.time() - start_time)*1000:.1f}ms] Test completed")
        print("=== End test_worker_config_validation ===\n")

    @pytest.mark.asyncio
    async def test_worker_node_scaling(self):
        """Test worker node scaling functionality."""
        ray_manager = RayManager()

        # Mock Ray availability and initialization
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
                    mock_process.communicate.return_value = (
                        "Ray runtime started\n--address='127.0.0.1:10001'\nView the Ray dashboard at http://127.0.0.1:8265",
                        "",
                    )
                    mock_process.poll.return_value = 0
                    mock_popen.return_value = mock_process

                    # Mock asyncio.sleep to avoid actual delays
                    with patch("asyncio.sleep") as mock_sleep:
                        # Mock asyncio.get_event_loop().run_in_executor to avoid blocking
                        with patch("asyncio.get_event_loop") as mock_get_loop:
                            mock_loop = Mock()

                            # Create a mock coroutine for run_in_executor
                            async def mock_run_in_executor(*args, **kwargs):
                                return (
                                    "Ray runtime started\n--address='127.0.0.1:10001'\nView the Ray dashboard at http://127.0.0.1:8265",
                                    "",
                                )

                            mock_loop.run_in_executor = mock_run_in_executor
                            mock_get_loop.return_value = mock_loop

                            # Mock _initialize_job_client_with_retry to avoid retry delays
                            with patch.object(
                                RayManager,
                                "_initialize_job_client_with_retry",
                                new_callable=AsyncMock,
                            ) as mock_init_job_client:
                                mock_init_job_client.return_value = None
                                with patch.object(
                                    RayManager,
                                    "_communicate_with_timeout",
                                    new_callable=AsyncMock,
                                ) as mock_communicate:
                                    mock_communicate.return_value = (
                                        "Ray runtime started\n--address='127.0.0.1:20000'\nView the Ray dashboard at http://127.0.0.1:8265",
                                        "",
                                    )
                                    # Mock worker manager for scaling
                                    with patch.object(
                                        ray_manager._worker_manager,
                                        "start_worker_nodes",
                                        new_callable=AsyncMock,
                                    ) as mock_start_workers:
                                        mock_start_workers.return_value = [
                                            {
                                                "status": "started",
                                                "node_name": "worker-1",
                                            },
                                        ]

                                        # Test initial cluster with 1 worker
                                        result = await ray_manager.init_cluster(
                                            num_cpus=4,
                                            head_node_port=20000,
                                            dashboard_port=8265,
                                            worker_nodes=[
                                                {"num_cpus": 2, "node_name": "worker-1"}
                                            ],
                                        )

                                        assert result["status"] == "success"
                                        assert result.get("result_type") == "started"
                                        assert len(result["worker_nodes"]) == 1

                                        # Test adding more workers (simulated by re-initializing)
                                        mock_start_workers.return_value = [
                                            {
                                                "status": "started",
                                                "node_name": "worker-1",
                                            },
                                            {
                                                "status": "started",
                                                "node_name": "worker-2",
                                            },
                                            {
                                                "status": "started",
                                                "node_name": "worker-3",
                                            },
                                        ]

                                        result = await ray_manager.init_cluster(
                                            num_cpus=4,
                                            head_node_port=20000,
                                            dashboard_port=8265,
                                            worker_nodes=[
                                                {
                                                    "num_cpus": 2,
                                                    "node_name": "worker-1",
                                                },
                                                {
                                                    "num_cpus": 2,
                                                    "node_name": "worker-2",
                                                },
                                                {
                                                    "num_cpus": 2,
                                                    "node_name": "worker-3",
                                                },
                                            ],
                                        )

                                        assert result["status"] == "success"
                                        assert result.get("result_type") == "started"
                                        assert len(result["worker_nodes"]) == 3

    @pytest.mark.asyncio
    async def test_worker_node_failure_handling(self, mock_cluster_startup):
        """Test handling of worker node failures."""
        ray_manager = RayManager()
        print("\n=== Starting test_worker_node_failure_handling ===")
        start_time = time.time()
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            print(f"  [{(time.time() - start_time)*1000:.1f}ms] Patched RAY_AVAILABLE")
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                print(f"  [{(time.time() - start_time)*1000:.1f}ms] Patched ray")
                mock_ray.is_initialized.return_value = False
                mock_ray.init.return_value = Mock(
                    address_info={"address": "127.0.0.1:10001"},
                    dashboard_url="http://127.0.0.1:8265",
                )
                with patch("subprocess.Popen") as mock_popen:
                    mock_process = Mock()
                    mock_process.communicate.return_value = (
                        "Ray runtime started\n--address='127.0.0.1:10001'\nView the Ray dashboard at http://127.0.0.1:8265",
                        "",
                    )
                    mock_process.poll.return_value = 0
                    mock_popen.return_value = mock_process
                    with patch.object(
                        RayManager,
                        "_initialize_job_client_with_retry",
                        new_callable=AsyncMock,
                    ) as mock_init_job_client:
                        print(
                            f"  [{(time.time() - start_time)*1000:.1f}ms] Patched _initialize_job_client_with_retry"
                        )
                        mock_init_job_client.return_value = None
                        with patch.object(
                            RayManager,
                            "_communicate_with_timeout",
                            new_callable=AsyncMock,
                        ) as mock_communicate:
                            mock_communicate.return_value = (
                                "Ray runtime started\n--address='127.0.0.1:20000'\nView the Ray dashboard at http://127.0.0.1:8265",
                                "",
                            )
                            with patch.object(
                                ray_manager._worker_manager,
                                "start_worker_nodes",
                                new_callable=AsyncMock,
                            ) as mock_start_workers:
                                print(
                                    f"  [{(time.time() - start_time)*1000:.1f}ms] Patched start_worker_nodes"
                                )
                                mock_start_workers.return_value = [
                                    {"status": "started", "node_name": "worker-1"},
                                    {
                                        "status": "failed",
                                        "node_name": "worker-2",
                                        "error": "Connection timeout",
                                    },
                                    {"status": "started", "node_name": "worker-3"},
                                ]
                                print(
                                    f"  [{(time.time() - start_time)*1000:.1f}ms] About to call init_cluster"
                                )
                                init_start = time.time()
                                result = await ray_manager.init_cluster(
                                    num_cpus=4,
                                    head_node_port=20000,
                                    dashboard_port=8265,
                                    worker_nodes=[
                                        {"num_cpus": 2, "node_name": "worker-1"},
                                        {"num_cpus": 2, "node_name": "worker-2"},
                                        {"num_cpus": 2, "node_name": "worker-3"},
                                    ],
                                )
                                print(
                                    f"  [{(time.time() - start_time)*1000:.1f}ms] init_cluster took {(time.time() - init_start)*1000:.1f}ms"
                                )
                                assert result["status"] == "success"
                                assert result.get("result_type") == "started"
                                assert len(result["worker_nodes"]) == 3
                                assert any(
                                    w["status"] == "failed"
                                    for w in result["worker_nodes"]
                                )
        print(f"  [{(time.time() - start_time)*1000:.1f}ms] Test completed")
        print("=== End test_worker_node_failure_handling ===\n")

    @pytest.mark.asyncio
    async def test_worker_node_resource_allocation(self, mock_cluster_startup):
        """Test worker node resource allocation."""
        ray_manager = RayManager()
        print("\n=== Starting test_worker_node_resource_allocation ===")
        start_time = time.time()
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            print(f"  [{(time.time() - start_time)*1000:.1f}ms] Patched RAY_AVAILABLE")
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                print(f"  [{(time.time() - start_time)*1000:.1f}ms] Patched ray")
                mock_ray.is_initialized.return_value = False
                mock_ray.init.return_value = Mock(
                    address_info={"address": "127.0.0.1:10001"},
                    dashboard_url="http://127.0.0.1:8265",
                )
                with patch("subprocess.Popen") as mock_popen:
                    mock_process = Mock()
                    mock_process.communicate.return_value = (
                        "Ray runtime started\n--address='127.0.0.1:10001'\nView the Ray dashboard at http://127.0.0.1:8265",
                        "",
                    )
                    mock_process.poll.return_value = 0
                    mock_popen.return_value = mock_process
                    with patch.object(
                        RayManager,
                        "_initialize_job_client_with_retry",
                        new_callable=AsyncMock,
                    ) as mock_init_job_client:
                        print(
                            f"  [{(time.time() - start_time)*1000:.1f}ms] Patched _initialize_job_client_with_retry"
                        )
                        mock_init_job_client.return_value = None
                        with patch.object(
                            RayManager,
                            "_communicate_with_timeout",
                            new_callable=AsyncMock,
                        ) as mock_communicate:
                            mock_communicate.return_value = (
                                "Ray runtime started\n--address='127.0.0.1:20000'\nView the Ray dashboard at http://127.0.0.1:8265",
                                "",
                            )
                            with patch.object(
                                ray_manager._worker_manager,
                                "start_worker_nodes",
                                new_callable=AsyncMock,
                            ) as mock_start_workers:
                                print(
                                    f"  [{(time.time() - start_time)*1000:.1f}ms] Patched start_worker_nodes"
                                )
                                mock_start_workers.return_value = [
                                    {"status": "started", "node_name": "cpu-worker"},
                                    {"status": "started", "node_name": "gpu-worker"},
                                ]
                                worker_config = [
                                    {
                                        "num_cpus": 4,
                                        "num_gpus": 0,
                                        "node_name": "cpu-worker",
                                        "memory": 8000000000,
                                    },
                                    {
                                        "num_cpus": 2,
                                        "num_gpus": 1,
                                        "node_name": "gpu-worker",
                                        "memory": 16000000000,
                                    },
                                ]
                                print(
                                    f"  [{(time.time() - start_time)*1000:.1f}ms] About to call init_cluster"
                                )
                                init_start = time.time()
                                result = await ray_manager.init_cluster(
                                    num_cpus=4,
                                    head_node_port=20000,
                                    dashboard_port=8265,
                                    worker_nodes=worker_config,
                                )
                                print(
                                    f"  [{(time.time() - start_time)*1000:.1f}ms] init_cluster took {(time.time() - init_start)*1000:.1f}ms"
                                )
                                assert result["status"] == "success"
                                assert result.get("result_type") == "started"
                                assert len(result["worker_nodes"]) == 2
                                mock_start_workers.assert_called_once()
                                call_args = mock_start_workers.call_args[0][0]
                                assert len(call_args) == 2
                                assert call_args[0]["num_cpus"] == 4
                                assert call_args[0]["num_gpus"] == 0
                                assert call_args[1]["num_cpus"] == 2
                                assert call_args[1]["num_gpus"] == 1
        print(f"  [{(time.time() - start_time)*1000:.1f}ms] Test completed")
        print("=== End test_worker_node_resource_allocation ===\n")


if __name__ == "__main__":
    pytest.main([__file__])
