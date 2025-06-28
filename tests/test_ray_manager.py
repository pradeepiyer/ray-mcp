#!/usr/bin/env python3
"""Tests for the Ray manager."""

import asyncio
import inspect
import subprocess
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from ray_mcp.ray_manager import RayManager


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
        manager._cluster_address = "ray://127.0.0.1:10001"
        manager._job_client = Mock()
        return manager

    def test_init(self):
        """Test RayManager initialization."""
        manager = RayManager()
        assert not manager.is_initialized
        assert manager._job_client is None
        assert manager._cluster_address is None

    @pytest.mark.asyncio
    async def test_init_cluster_success(self, manager):
        """Test successful cluster initialization."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = False
                mock_ray.init.return_value = Mock(
                    address_info={"address": "ray://127.0.0.1:10001"},
                    dashboard_url="http://127.0.0.1:8265",
                    session_name="test_session",
                )
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "node_123"
                )

                # Patch subprocess.Popen to provide expected stdout for dashboard_url parsing
                with patch("subprocess.Popen") as mock_popen:
                    mock_process = Mock()
                    mock_process.communicate.return_value = (
                        "Ray runtime started\n--address='127.0.0.1:10001'\nView the Ray dashboard at http://127.0.0.1:8265",
                        "",
                    )
                    mock_process.poll.return_value = 0
                    mock_popen.return_value = mock_process

                    result = await manager.init_cluster(worker_nodes=[])

                    assert result["status"] == "started"
                    assert "cluster_address" in result
                    assert result["dashboard_url"] == "http://127.0.0.1:8265"
                    assert result["node_id"] == "node_123"
                    assert result["session_name"] == "test_session"

    @pytest.mark.asyncio
    async def test_init_cluster_already_running(self, manager):
        """Test cluster initialization when Ray is already running."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.init.return_value = Mock(
                    address_info={"address": "ray://127.0.0.1:10001"},
                    dashboard_url="http://127.0.0.1:8265",
                    session_name="test_session",
                )
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "node_123"
                )

                result = await manager.init_cluster(worker_nodes=[])
                assert result["status"] == "started"

    @pytest.mark.asyncio
    async def test_init_cluster_connect_to_existing(self):
        """Test connecting to existing cluster."""
        ray_manager = RayManager()

        # Mock Ray availability and initialization
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = False
                mock_ray.init.return_value = Mock(
                    address_info={"address": "ray://127.0.0.1:10001"},
                    dashboard_url="http://127.0.0.1:8265",
                    session_name="test_session",
                )
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "node_123"
                )

                result = await ray_manager.init_cluster(address="ray://127.0.0.1:10001")

                assert result["status"] == "connected"
                assert "address" in result
                assert result["dashboard_url"] == "http://127.0.0.1:8265"
                assert result["node_id"] == "node_123"
                assert result["session_name"] == "test_session"

    @pytest.mark.asyncio
    async def test_init_cluster_ray_unavailable(self, manager):
        """Test cluster initialization when Ray is not available."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", False):
            result = await manager.init_cluster(address="ray://remote:10001")
            assert result["status"] == "error"
            assert "Ray is not available" in result["message"]

    @pytest.mark.asyncio
    async def test_init_cluster_gcs_address_extraction(self):
        """Test GCS address extraction from different address formats."""
        manager1 = RayManager()
        manager2 = RayManager()

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = False
                mock_ray.init.return_value = Mock(
                    address_info={"address": "ray://127.0.0.1:10001"},
                    dashboard_url="http://127.0.0.1:8265",
                )

                # Test ray:// format
                result1 = await manager1.init_cluster(address="ray://127.0.0.1:10001")
                assert result1["status"] == "connected"
                assert manager1._gcs_address == "127.0.0.1:10001"

                # Test direct IP:PORT format
                result2 = await manager2.init_cluster(address="127.0.0.1:10003")
                assert result2["status"] == "connected"
                assert manager2._gcs_address == "127.0.0.1:10003"

    @pytest.mark.asyncio
    async def test_stop_cluster(self):
        """Test stopping cluster."""
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
                        ray_manager._worker_manager, "stop_all_workers"
                    ) as mock_stop_workers:
                        mock_stop_workers.return_value = []

                        result = await ray_manager.stop_cluster()

                        assert result["status"] == "stopped"
                        assert "Ray cluster stopped successfully" in result["message"]

    @pytest.mark.asyncio
    async def test_stop_cluster_not_running(self, manager):
        """Test cluster stop when not running."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = False

                result = await manager.stop_cluster()

                assert result["status"] == "not_running"
                assert "Ray cluster is not running" in result["message"]

    @pytest.mark.asyncio
    async def test_stop_cluster_ray_unavailable(self, manager):
        """Test cluster stop when Ray is not available."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", False):
            result = await manager.stop_cluster()
            assert result["status"] == "error"
            assert "Ray is not available" in result["message"]

    @pytest.mark.asyncio
    async def test_stop_cluster_exception(self, manager):
        """Test cluster stop with exception."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.shutdown.side_effect = Exception("Shutdown failed")

                result = await manager.stop_cluster()
                assert result["status"] == "error"
                assert "Shutdown failed" in result["message"]

    def test_ensure_initialized_not_initialized(self):
        """Test _ensure_initialized when not initialized."""
        manager = RayManager()

        with pytest.raises(
            RuntimeError, match="Ray is not initialized. Please start Ray first."
        ):
            manager._ensure_initialized()

    def test_ensure_initialized_initialized(self):
        """Test _ensure_initialized when initialized."""
        manager = RayManager()
        manager._is_initialized = True

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                # Should not raise
                manager._ensure_initialized()

    @pytest.mark.asyncio
    async def test_submit_job_success(self, initialized_manager):
        """Test successful job submission."""
        mock_job_client = initialized_manager._job_client
        mock_job_client.submit_job.return_value = "submitted_job_123"

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True

                result = await initialized_manager.submit_job(
                    entrypoint="python train.py",
                    runtime_env={"pip": ["requests"]},
                    job_id="custom_job",
                    metadata={"owner": "test"},
                )

                assert result["status"] == "submitted"
                assert result["job_id"] == "submitted_job_123"

    @pytest.mark.asyncio
    async def test_submit_job_not_initialized(self):
        """Test job submission when not initialized."""
        manager = RayManager()
        result = await manager.submit_job("python test.py")
        assert result["status"] == "error"
        assert "Ray is not initialized" in result["message"]

    @pytest.mark.asyncio
    async def test_retrieve_logs_job_success(self, initialized_manager):
        """Test successful job logs retrieval with retrieve_logs."""
        mock_logs = "Job started\nProcessing data\nJob completed"

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True

                initialized_manager._job_client.get_job_logs.return_value = mock_logs

                result = await initialized_manager.retrieve_logs(
                    "job_123", "job", 100, False
                )

                assert result["status"] == "success"
                assert result["log_type"] == "job"
                assert result["identifier"] == "job_123"
                assert result["logs"] == mock_logs
                assert "error_analysis" not in result
                initialized_manager._job_client.get_job_logs.assert_called_once_with(
                    "job_123"
                )

    @pytest.mark.asyncio
    async def test_retrieve_logs_job_with_errors(self, initialized_manager):
        """Test job logs retrieval with error analysis."""
        mock_logs = "Job started\nError: Import failed\nTraceback..."

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True

                initialized_manager._job_client.get_job_logs.return_value = mock_logs

                result = await initialized_manager.retrieve_logs(
                    "job_123", "job", 100, True
                )

                assert result["status"] == "success"
                assert result["log_type"] == "job"
                assert result["identifier"] == "job_123"
                assert result["logs"] == mock_logs
                assert "error_analysis" in result
                assert result["error_analysis"]["error_count"] > 0
                assert "suggestions" in result["error_analysis"]

    @pytest.mark.asyncio
    async def test_retrieve_logs_actor_limited(self, initialized_manager):
        """Test actor logs retrieval (limited support)."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_actor = MagicMock()
                mock_actor._actor_id.hex.return_value = "abc123"
                mock_ray.get_actor.return_value = mock_actor

                result = await initialized_manager.retrieve_logs(
                    "my_actor", "actor", 100
                )

                assert result["status"] == "partial"
                assert result["log_type"] == "actor"
                assert result["identifier"] == "my_actor"
                assert "Actor logs are not directly accessible" in result["message"]
                assert "suggestions" in result

    @pytest.mark.asyncio
    async def test_retrieve_logs_actor_by_id(self, initialized_manager):
        """Actor log retrieval should use ID lookup without namespace."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_actor = MagicMock()
                mock_actor._actor_id.hex.return_value = "abc123"
                mock_ray.get_actor.return_value = mock_actor

                actor_id = "b" * 32
                await initialized_manager.retrieve_logs(actor_id, "actor", 100)

                mock_ray.get_actor.assert_called_once_with(actor_id)

    @pytest.mark.asyncio
    async def test_retrieve_logs_actor_by_name(self, initialized_manager):
        """Actor log retrieval should search across namespaces for names."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_actor = MagicMock()
                mock_actor._actor_id.hex.return_value = "abc123"
                mock_ray.get_actor.return_value = mock_actor

                await initialized_manager.retrieve_logs("actor_name", "actor", 100)

                mock_ray.get_actor.assert_called_once_with("actor_name", namespace="*")

    @pytest.mark.asyncio
    async def test_retrieve_logs_node_limited(self, initialized_manager):
        """Test node logs retrieval (limited support)."""
        mock_nodes = [
            {
                "NodeID": "node_123",
                "Alive": True,
                "NodeName": "worker-1",
                "NodeManagerAddress": "127.0.0.1:12345",
            }
        ]

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.nodes.return_value = mock_nodes

                result = await initialized_manager.retrieve_logs(
                    "node_123", "node", 100
                )

                assert result["status"] == "partial"
                assert result["log_type"] == "node"
                assert result["identifier"] == "node_123"
                assert "Node logs are not directly accessible" in result["message"]
                assert "node_info" in result
                assert "suggestions" in result

    @pytest.mark.asyncio
    async def test_retrieve_logs_unsupported_type(self, initialized_manager):
        """Test retrieve_logs with unsupported log type."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True

                result = await initialized_manager.retrieve_logs(
                    "test", "unsupported", 100
                )

                assert result["status"] == "error"
                assert "Unsupported log type" in result["message"]

    def test_generate_health_recommendations(self, manager):
        """Test health recommendation generation."""
        # Test with all checks passing
        health_checks = {
            "all_nodes_alive": True,
            "has_available_cpu": True,
            "has_available_memory": True,
            "cluster_responsive": True,
        }
        recommendations = manager._generate_health_recommendations(health_checks)
        assert len(recommendations) == 1
        assert "good" in recommendations[0].lower()

        # Test with failing checks
        health_checks = {
            "all_nodes_alive": False,
            "has_available_cpu": False,
            "has_available_memory": False,
            "cluster_responsive": True,
        }
        recommendations = manager._generate_health_recommendations(health_checks)
        assert len(recommendations) == 3
        assert any("nodes" in rec.lower() for rec in recommendations)
        assert any("cpu" in rec.lower() for rec in recommendations)
        assert any("memory" in rec.lower() for rec in recommendations)

    @pytest.mark.asyncio
    async def test_inspect_ray_not_running(self):
        """Test inspect_ray when Ray is not running."""
        manager = RayManager()
        result = await manager.inspect_ray()
        assert result["status"] == "not_running"
        assert "Ray cluster is not running" in result["message"]

    @pytest.mark.asyncio
    async def test_inspect_ray_running(self):
        """Test inspect_ray when Ray is running."""
        manager = RayManager()

        # Mock Ray as initialized
        with patch("ray_mcp.ray_manager.ray") as mock_ray:
            mock_ray.is_initialized.return_value = True
            mock_ray.cluster_resources.return_value = {"CPU": 4, "memory": 1000000000}
            mock_ray.available_resources.return_value = {"CPU": 2, "memory": 500000000}
            mock_ray.nodes.return_value = [
                {
                    "NodeID": "node_1",
                    "Alive": True,
                    "NodeName": "head_node",
                    "Resources": {"CPU": 4, "memory": 1000000000},
                    "UsedResources": {"CPU": 2, "memory": 500000000},
                }
            ]

            result = await manager.inspect_ray()

        assert result["status"] == "success"
        assert "cluster_overview" in result
        assert "resources" in result
        assert "nodes" in result

    @pytest.mark.asyncio
    async def test_inspect_ray_ray_unavailable(self, manager):
        """Test inspect_ray when Ray is not available."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", False):
            result = await manager.inspect_ray()
        assert result["status"] == "unavailable"

    @pytest.mark.asyncio
    async def test_inspect_ray_with_exception(self, manager):
        """Test inspect_ray when an exception occurs."""
        with patch("ray_mcp.ray_manager.ray") as mock_ray:
            mock_ray.is_initialized.return_value = True
            mock_ray.cluster_resources.side_effect = Exception("Ray error")

            result = await manager.inspect_ray()

        assert result["status"] == "error"
        assert "Ray error" in result["message"]

    @pytest.mark.asyncio
    async def test_init_cluster_filters_none_values(self):
        """Ensure None values and invalid params are removed before ray.init."""
        manager = RayManager()

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = False

                def dummy_init(
                    *, address=None, ignore_reinit_error=True, namespace=None
                ):
                    return Mock(
                        address_info={"address": address or "ray://127.0.0.1:10001"},
                        dashboard_url="http://127.0.0.1:8265",
                    )

                mock_ray.init.side_effect = dummy_init
                mock_ray.init.__signature__ = inspect.signature(dummy_init)
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "node_123"
                )

                await manager.init_cluster(
                    address="ray://127.0.0.1:10001", namespace=None, invalid_param=1
                )

                call_kwargs = mock_ray.init.call_args.kwargs
                assert "namespace" not in call_kwargs
                assert "invalid_param" not in call_kwargs

    @pytest.mark.asyncio
    async def test_filter_cluster_starting_parameters_method(self):
        """Test the _filter_cluster_starting_parameters method."""
        manager = RayManager()

        # Test with cluster-starting parameters
        kwargs = {
            "address": "ray://127.0.0.1:10001",
            "num_cpus": 4,
            "num_gpus": 1,
            "object_store_memory": 1000000000,
            "head_node_port": 10001,
            "dashboard_port": 8265,
            "head_node_host": "127.0.0.1",
            "worker_nodes": [{"num_cpus": 2}],
            "custom_param": "should_be_passed",
        }

        filtered = manager._filter_cluster_starting_parameters(kwargs)

        # Check that cluster-starting parameters were filtered out
        assert "num_cpus" not in filtered
        assert "num_gpus" not in filtered
        assert "object_store_memory" not in filtered
        assert "head_node_port" not in filtered
        assert "dashboard_port" not in filtered
        assert "head_node_host" not in filtered
        assert "worker_nodes" not in filtered

        # Check that other parameters were passed through
        assert "address" in filtered
        assert "custom_param" in filtered
        assert filtered["address"] == "ray://127.0.0.1:10001"
        assert filtered["custom_param"] == "should_be_passed"

    @pytest.mark.asyncio
    async def test_inspect_job_with_non_string_logs(self, initialized_manager):
        """Ensure inspect_job handles non-string log data in debug mode."""
        job_info = MagicMock()
        job_info.status = "RUNNING"
        job_info.entrypoint = "python app.py"
        job_info.start_time = 0.0
        job_info.end_time = None
        job_info.metadata = {}
        job_info.runtime_env = {}
        job_info.message = ""

        initialized_manager._job_client.get_job_info.return_value = job_info
        initialized_manager._job_client.get_job_logs.return_value = [
            "log line 1",
            "error line",
        ]

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True

                result = await initialized_manager.inspect_job("job_123", mode="debug")

        assert result["status"] == "success"
        assert result["inspection_mode"] == "debug"
        assert "debug_info" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
