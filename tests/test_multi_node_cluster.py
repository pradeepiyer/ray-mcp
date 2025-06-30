#!/usr/bin/env python3
"""Tests for multi-node cluster functionality."""

import asyncio
import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from ray_mcp.ray_manager import RayManager
from tests.conftest import mock_cluster_startup


@pytest.mark.fast
class TestMultiNodeCluster:
    """Essential multi-node cluster functionality tests."""

    @pytest.fixture
    def ray_manager(self):
        """Create a RayManager instance for testing."""
        return RayManager()

    @pytest.mark.asyncio
    async def test_multi_node_error_handling(self, ray_manager):
        """Test error handling in multi-node scenarios."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.shutdown.side_effect = Exception("Shutdown failed")

                # Mock worker manager failure
                with patch.object(
                    ray_manager._worker_manager,
                    "stop_all_workers",
                    new_callable=AsyncMock,
                ) as mock_stop_workers:
                    mock_stop_workers.side_effect = Exception("Worker stop failed")

                    result = await ray_manager.stop_cluster()

                    assert result["status"] == "error"
                    # The error message may be wrapped, check for either the original or wrapper message
                    assert (
                        "Shutdown failed" in result["message"]
                        or "Worker stop failed" in result["message"]
                    )

    @pytest.mark.asyncio
    async def test_worker_node_resource_allocation(
        self, ray_manager, mock_cluster_startup
    ):
        """Test worker node resource allocation in multi-node setup."""
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

                            with patch.object(
                                ray_manager._worker_manager,
                                "start_worker_nodes",
                                new_callable=AsyncMock,
                            ) as mock_start_workers:
                                # Test resource allocation across nodes
                                worker_configs = [
                                    {
                                        "num_cpus": 8,
                                        "num_gpus": 2,
                                        "node_name": "high-resource-worker",
                                        "resources": {"custom_gpu": 1},
                                    },
                                    {
                                        "num_cpus": 4,
                                        "num_gpus": 0,
                                        "node_name": "cpu-worker",
                                        "resources": {"memory": 16000000000},
                                    },
                                ]

                                mock_start_workers.return_value = [
                                    {
                                        "status": "started",
                                        "node_name": "high-resource-worker",
                                    },
                                    {"status": "started", "node_name": "cpu-worker"},
                                ]

                                result = await ray_manager.init_cluster(
                                    num_cpus=4,
                                    head_node_port=20000,
                                    dashboard_port=8265,
                                    worker_nodes=worker_configs,
                                )

                                assert result["status"] == "success"
                                assert result.get("result_type") == "started"
                                assert len(result["worker_nodes"]) == 2
                                mock_start_workers.assert_called_once_with(
                                    worker_configs, "127.0.0.1:20000"
                                )

    @pytest.mark.asyncio
    async def test_large_scale_worker_deployment(self, ray_manager):
        """Test deployment of many worker nodes."""
        # Test with a larger number of workers to verify scalability
        num_workers = 10
        worker_configs = []
        expected_results = []

        for i in range(num_workers):
            worker_configs.append(
                {
                    "num_cpus": 2,
                    "node_name": f"worker-{i+1}",
                }
            )
            expected_results.append(
                {
                    "status": "started",
                    "node_name": f"worker-{i+1}",
                }
            )

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

                    # Mock asyncio.sleep to avoid delays
                    with patch("asyncio.sleep"):
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

                                with patch.object(
                                    ray_manager._worker_manager,
                                    "start_worker_nodes",
                                    new_callable=AsyncMock,
                                ) as mock_start_workers:
                                    mock_start_workers.return_value = expected_results

                                    result = await ray_manager.init_cluster(
                                        num_cpus=4,
                                        head_node_port=20000,
                                        dashboard_port=8265,
                                        worker_nodes=worker_configs,
                                    )

                                    assert result["status"] == "success"
                                    assert result.get("result_type") == "started"
                                    assert len(result["worker_nodes"]) == num_workers

                                    # Verify all workers were started
                                    for i, worker_result in enumerate(
                                        result["worker_nodes"]
                                    ):
                                        assert worker_result["status"] == "started"
                                        assert (
                                            worker_result["node_name"]
                                            == f"worker-{i+1}"
                                        )


if __name__ == "__main__":
    pytest.main([__file__])
