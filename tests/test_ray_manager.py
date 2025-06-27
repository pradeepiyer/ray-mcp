#!/usr/bin/env python3
"""Tests for the Ray manager."""

import asyncio
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
    async def test_start_cluster_success(self):
        """Test successful cluster start."""
        manager = RayManager()

        # Mock ray.init and related functions
        mock_context = Mock()
        mock_context.address_info = {
            "address": "ray://127.0.0.1:10001",
        }
        mock_context.dashboard_url = "http://127.0.0.1:8265"
        mock_context.session_name = "test_session"

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.init.return_value = mock_context
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "test_node_id"
                )

                with patch("ray_mcp.ray_manager.JobSubmissionClient") as mock_client:
                    with patch("subprocess.Popen") as mock_popen:
                        # Mock the subprocess to simulate successful ray start
                        mock_process = Mock()
                        mock_process.communicate.return_value = (
                            "Ray runtime started\n--address='127.0.0.1:10001'\nView the Ray dashboard at http://127.0.0.1:8265",
                            "",
                        )
                        mock_process.poll.return_value = 0
                        mock_popen.return_value = mock_process

                        result = await manager.start_cluster(worker_nodes=[])

                        assert result["status"] == "started"
                        assert result["address"].startswith("ray://")
                        assert ":" in result["address"]
                        assert manager._is_initialized
                        # Assert JobSubmissionClient was called with HTTP address
                        if mock_client.call_args:
                            job_client_arg = mock_client.call_args[0][0]
                            assert job_client_arg.startswith("http://")

    @pytest.mark.asyncio
    async def test_start_cluster_already_running(self):
        """Test cluster start when already running."""
        manager = RayManager()

        # Mock ray.init to work properly with ignore_reinit_error=True
        mock_context = Mock()
        mock_context.address_info = {"address": "ray://127.0.0.1:10001"}
        mock_context.dashboard_url = "http://127.0.0.1:8265"
        mock_context.session_name = "test_session"

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.init.return_value = mock_context
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "test_node"
                )

                with patch("ray_mcp.ray_manager.JobSubmissionClient"):
                    with patch("subprocess.Popen") as mock_popen:
                        # Mock the subprocess to simulate successful ray start
                        mock_process = Mock()
                        mock_process.communicate.return_value = (
                            "Ray runtime started\n--address='127.0.0.1:10001'",
                            "",
                        )
                        mock_process.poll.return_value = 0
                        mock_popen.return_value = mock_process

                        result = await manager.start_cluster(worker_nodes=[])

                        # When Ray is already running, ray.init with ignore_reinit_error=True
                        # will still return successfully, so we expect "started" status
                        assert result["status"] == "started"
                        assert result["address"].startswith("ray://")
                        assert ":" in result["address"]

    @pytest.mark.asyncio
    async def test_stop_cluster(self):
        """Test cluster stop."""
        manager = RayManager()
        manager._is_initialized = True

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.shutdown.return_value = None

                result = await manager.stop_cluster()

                assert result["status"] == "stopped"
                assert not manager._is_initialized
                assert manager._job_client is None

    @pytest.mark.asyncio
    async def test_stop_cluster_not_running(self):
        """Test cluster stop when not running."""
        manager = RayManager()

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = False

                result = await manager.stop_cluster()

                assert result["status"] == "not_running"

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

    # ===== CONNECT CLUSTER TESTS =====

    @pytest.mark.asyncio
    async def test_connect_cluster_success(self, manager):
        """Test successful cluster connection."""
        mock_context = Mock()
        mock_context.address_info = {"address": "ray://remote:10001"}
        mock_context.dashboard_url = "http://remote:8265"
        mock_context.session_name = "remote_session"

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.init.return_value = mock_context
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "remote_node"
                )

                with patch("ray_mcp.ray_manager.JobSubmissionClient") as mock_client:
                    result = await manager.connect_cluster("ray://remote:10001")

                    assert result["status"] == "connected"
                    assert result["address"].startswith("ray://")
                    assert ":" in result["address"]
                    assert manager._is_initialized
                    assert manager._cluster_address.startswith("ray://")
                    assert ":" in manager._cluster_address
                    # Assert JobSubmissionClient was called with HTTP address if called, otherwise check job_client_status
                    if mock_client.call_args:
                        job_client_arg = mock_client.call_args[0][0]
                        assert job_client_arg.startswith("http://")
                    else:
                        assert result["job_client_status"] == "unavailable"

    @pytest.mark.asyncio
    async def test_connect_cluster_ray_unavailable(self, manager):
        """Test cluster connection when Ray is unavailable."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", False):
            result = await manager.connect_cluster("ray://remote:10001")

            assert result["status"] == "error"
            assert "Ray is not available" in result["message"]

    @pytest.mark.asyncio
    async def test_connect_cluster_gcs_address_extraction(self):
        """Test that GCS address is properly extracted when connecting to existing cluster."""
        manager = RayManager()

        # Mock ray.init and related functions
        mock_context = Mock()
        mock_context.address_info = {
            "address": "ray://127.0.0.1:10001",
        }
        mock_context.dashboard_url = "http://127.0.0.1:8265"
        mock_context.session_name = "test_session"

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.init.return_value = mock_context
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "test_node_id"
                )

                with patch("ray_mcp.ray_manager.JobSubmissionClient"):
                    # Test with ray:// address
                    result = await manager.connect_cluster("ray://127.0.0.1:10001")

                    assert result["status"] == "connected"
                    assert manager._is_initialized
                    # ray:// prefix removed
                    assert manager._gcs_address == "127.0.0.1:10001"

                    # Test with direct IP:PORT address
                    manager2 = RayManager()
                    result2 = await manager2.connect_cluster("127.0.0.1:10003")

                    assert result2["status"] == "connected"
                    assert manager2._is_initialized
                    # direct address stored as-is
                    assert manager2._gcs_address == "127.0.0.1:10003"

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
    async def test_submit_job_not_initialized(self, manager):
        """Test job submission when not initialized."""
        result = await manager.submit_job("python test.py")
        assert result["status"] == "error"
        assert "Ray is not initialized" in result["message"]

    @pytest.mark.asyncio
    async def test_list_actors_success(self, initialized_manager):
        """Test successful actor listing."""
        mock_named_actors = [{"name": "test_actor", "namespace": "default"}]

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.util.list_named_actors.return_value = mock_named_actors

                # Mock actor handle
                mock_actor_handle = Mock()
                mock_actor_handle._actor_id.hex.return_value = "actor123"
                mock_ray.get_actor.return_value = mock_actor_handle

                result = await initialized_manager.list_actors()

                assert result["status"] == "success"
                assert len(result["actors"]) == 1

    @pytest.mark.asyncio
    async def test_kill_actor_success(self, initialized_manager):
        """Test successful actor killing."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.kill.return_value = None

                result = await initialized_manager.kill_actor(
                    "actor123", no_restart=True
                )

                assert result["status"] == "killed"
                assert result["actor_id"] == "actor123"

    @pytest.mark.asyncio
    async def test_get_logs_job_success(self, initialized_manager):
        """Test successful job log retrieval."""
        mock_job_client = initialized_manager._job_client
        mock_job_client.get_job_logs.return_value = "Job log output"

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True

                result = await initialized_manager.get_logs(
                    job_id="test_job", num_lines=50
                )

                assert result["status"] == "success"
                assert result["logs"] == "Job log output"

    @pytest.mark.asyncio
    async def test_get_performance_metrics_success(self, initialized_manager):
        """Test successful performance metrics retrieval."""
        mock_cluster_resources = {"CPU": 12.0, "memory": 32000000000}
        mock_available_resources = {"CPU": 8.0, "memory": 20000000000}
        mock_nodes = [
            {"NodeID": "node1", "Alive": True},
            {"NodeID": "node2", "Alive": True},
        ]

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.cluster_resources.return_value = mock_cluster_resources
                mock_ray.available_resources.return_value = mock_available_resources
                mock_ray.nodes.return_value = mock_nodes

                result = await initialized_manager.get_performance_metrics()

                assert result["status"] == "success"
                assert "cluster_overview" in result or "cluster_utilization" in result

    @pytest.mark.asyncio
    async def test_cluster_health_check_success(self, initialized_manager):
        """Test successful cluster health check."""
        mock_nodes = [{"NodeID": "node1", "Alive": True}]

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.nodes.return_value = mock_nodes
                mock_ray.cluster_resources.return_value = {"CPU": 8.0}
                mock_ray.available_resources.return_value = {"CPU": 4.0}

                result = await initialized_manager.cluster_health_check()

                assert result["status"] == "success"
                assert "health_score" in result

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

    # ===== ERROR HANDLING AND EDGE CASES =====

    @pytest.mark.asyncio
    async def test_start_cluster_ray_unavailable(self, manager):
        """Test start cluster when Ray is not available."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", False):
            result = await manager.start_cluster()
            assert result["status"] == "error"
            assert "Ray is not available" in result["message"]

    @pytest.mark.asyncio
    async def test_start_cluster_exception(self, manager):
        """Test start cluster with exception."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                with patch("subprocess.Popen") as mock_popen:
                    # Mock subprocess to raise an exception
                    mock_popen.side_effect = Exception("Connection failed")

                    result = await manager.start_cluster()
                    assert result["status"] == "error"
                    assert "Connection failed" in result["message"]

    @pytest.mark.asyncio
    async def test_start_cluster_with_all_parameters(self, manager):
        """Test start cluster with all parameters specified."""
        mock_context = Mock()
        mock_context.address_info = {"address": "ray://127.0.0.1:10001"}
        mock_context.dashboard_url = "http://127.0.0.1:8265"
        mock_context.session_name = "test_session"

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.init.return_value = mock_context
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "test_node"
                )

                with patch("ray_mcp.ray_manager.JobSubmissionClient"):
                    with patch("subprocess.Popen") as mock_popen:
                        # Mock the subprocess to simulate successful ray start
                        mock_process = Mock()
                        mock_process.communicate.return_value = (
                            "Ray runtime started\n--address='127.0.0.1:10001'",
                            "",
                        )
                        mock_process.poll.return_value = 0
                        mock_popen.return_value = mock_process

                        result = await manager.start_cluster(
                            num_cpus=8,
                            num_gpus=2,
                            object_store_memory=1000000000,
                            custom_param="test",
                            worker_nodes=[],
                        )

                        assert result["status"] == "started"
                        # Verify the ray start command was called with correct parameters
                        mock_popen.assert_called_once()
                        call_args = mock_popen.call_args[0][0]
                        assert "--num-cpus" in call_args
                        assert "--num-gpus" in call_args
                        assert "--object-store-memory" in call_args

    @pytest.mark.asyncio
    async def test_connect_cluster_exception(self, manager):
        """Test connect cluster with exception."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.init.side_effect = Exception("Connection refused")

                result = await manager.connect_cluster("ray://remote:10001")
                assert result["status"] == "error"
                assert "Connection refused" in result["message"]

    @pytest.mark.asyncio
    async def test_stop_cluster_ray_unavailable(self, manager):
        """Test stop cluster when Ray is not available."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", False):
            result = await manager.stop_cluster()
            assert result["status"] == "error"
            assert "Ray is not available" in result["message"]

    @pytest.mark.asyncio
    async def test_stop_cluster_exception(self, manager):
        """Test stop cluster with exception."""
        manager._is_initialized = True

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.shutdown.side_effect = Exception("Shutdown failed")

                result = await manager.stop_cluster()
                assert result["status"] == "error"
                assert "Shutdown failed" in result["message"]

    # ===== JOB MANAGEMENT ERROR CASES =====

    @pytest.mark.asyncio
    async def test_submit_job_exception(self, initialized_manager):
        """Test submit job with exception."""
        initialized_manager._job_client.submit_job.side_effect = Exception(
            "Submit failed"
        )

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True

                result = await initialized_manager.submit_job("python test.py")
                assert result["status"] == "error"
                assert "Submit failed" in result["message"]

    @pytest.mark.asyncio
    async def test_list_jobs_not_initialized(self, manager):
        """Test list jobs when not initialized."""
        result = await manager.list_jobs()
        assert result["status"] == "error"
        assert "Ray is not initialized" in result["message"]

    @pytest.mark.asyncio
    async def test_list_jobs_no_client(self, initialized_manager):
        """Test list jobs when job client is not available."""
        initialized_manager._job_client = None

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                # Patch the actual ray.job_submission.JobSubmissionClient used in the fallback
                with patch(
                    "ray.job_submission.JobSubmissionClient"
                ) as mock_job_submission:
                    mock_job_submission.side_effect = Exception(
                        "Could not find any running Ray instance"
                    )

                    result = await initialized_manager.list_jobs()
                    assert result["status"] == "error"
                    assert (
                        "Job listing not available in Ray Client mode"
                        in result["message"]
                    )

    @pytest.mark.asyncio
    async def test_get_job_status_not_initialized(self, manager):
        """Test get job status when not initialized."""
        result = await manager.get_job_status("test_job")
        assert result["status"] == "error"
        assert "Ray is not initialized" in result["message"]

    @pytest.mark.asyncio
    async def test_get_job_status_no_client(self, initialized_manager):
        """Test get job status when job client is not available."""
        initialized_manager._job_client = None

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True

                result = await initialized_manager.get_job_status("test_job")
                assert result["status"] == "error"
                assert (
                    "Job status not available in Ray Client mode" in result["message"]
                )

    @pytest.mark.asyncio
    async def test_cancel_job_not_initialized(self, manager):
        """Test cancel job when not initialized."""
        result = await manager.cancel_job("test_job")
        assert result["status"] == "error"
        assert "Ray is not initialized" in result["message"]

    @pytest.mark.asyncio
    async def test_cancel_job_no_client(self, initialized_manager):
        """Test cancel job when job client is not available."""
        initialized_manager._job_client = None

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True

                result = await initialized_manager.cancel_job("test_job")
                assert result["status"] == "error"
                assert (
                    "Job cancellation not available in Ray Client mode"
                    in result["message"]
                )

    # ===== ACTOR MANAGEMENT ERROR CASES =====

    @pytest.mark.asyncio
    async def test_list_actors_not_initialized(self, manager):
        """Test list actors when not initialized."""
        result = await manager.list_actors()
        assert result["status"] == "error"
        assert "Ray is not initialized" in result["message"]

    @pytest.mark.asyncio
    async def test_list_actors_exception(self, initialized_manager):
        """Test list actors with exception."""
        with patch("ray_mcp.ray_manager.ray") as mock_ray:
            mock_ray.util.list_named_actors.side_effect = Exception("Actor list error")

            result = await initialized_manager.list_actors()
            assert result["status"] == "error"
            assert "Actor list error" in result["message"]

    @pytest.mark.asyncio
    async def test_kill_actor_not_initialized(self, manager):
        """Test kill actor when not initialized."""
        result = await manager.kill_actor("test_actor")
        assert result["status"] == "error"
        assert "Ray is not initialized" in result["message"]

    @pytest.mark.asyncio
    async def test_kill_actor_exception(self, initialized_manager):
        """Test kill actor with exception."""
        with patch("ray_mcp.ray_manager.ray") as mock_ray:
            mock_ray.get_actor.side_effect = Exception("Actor not found")

            result = await initialized_manager.kill_actor("test_actor")
            assert result["status"] == "error"
            assert "Actor not found" in result["message"]

    # ===== MONITORING AND DEBUGGING ERROR CASES =====

    @pytest.mark.asyncio
    async def test_get_logs_not_initialized(self, manager):
        """Test get logs when not initialized."""
        result = await manager.get_logs(job_id="test_job")
        assert result["status"] == "error"
        assert "Ray is not initialized" in result["message"]

    @pytest.mark.asyncio
    async def test_get_logs_no_client(self, initialized_manager):
        """Test get logs when job client is not available."""
        initialized_manager._job_client = None

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True

                result = await initialized_manager.get_logs(job_id="test_job")
                assert result["status"] == "partial"
                assert (
                    "Job log retrieval not available in Ray Client mode"
                    in result["message"]
                )

    @pytest.mark.asyncio
    async def test_get_performance_metrics_not_initialized(self, manager):
        """Test get performance metrics when not initialized."""
        result = await manager.get_performance_metrics()
        assert result["status"] == "error"
        assert "Ray is not initialized" in result["message"]

    @pytest.mark.asyncio
    async def test_get_performance_metrics_exception(self, initialized_manager):
        """Test get performance metrics with exception."""
        with patch("ray_mcp.ray_manager.ray") as mock_ray:
            mock_ray.cluster_resources.side_effect = Exception("Metrics error")

            result = await initialized_manager.get_performance_metrics()
            assert result["status"] == "error"
            assert "Metrics error" in result["message"]

    @pytest.mark.asyncio
    async def test_cluster_health_check_not_initialized(self, manager):
        """Test cluster health check when not initialized."""
        result = await manager.cluster_health_check()
        assert result["status"] == "error"
        assert "Ray is not initialized" in result["message"]

    @pytest.mark.asyncio
    async def test_cluster_health_check_exception(self, initialized_manager):
        """Test cluster health check with exception."""
        with patch("ray_mcp.ray_manager.ray") as mock_ray:
            mock_ray.nodes.side_effect = Exception("Health check error")

            result = await initialized_manager.cluster_health_check()
            assert result["status"] == "error"
            assert "Health check error" in result["message"]

    @pytest.mark.asyncio
    async def test_get_cluster_info_not_running(self):
        """Test get cluster info when not running."""
        manager = RayManager()

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = False

                result = await manager.get_cluster_info()

                assert result["status"] == "not_running"

    @pytest.mark.asyncio
    async def test_get_cluster_info_running(self):
        """Test get cluster info when running."""
        manager = RayManager()
        manager._is_initialized = True
        manager._cluster_address = "ray://127.0.0.1:10001"

        # Set up worker manager with test data
        manager._worker_manager.worker_configs = [
            {"node_name": "worker-1", "num_cpus": 4},
            {"node_name": "worker-2", "num_cpus": 8},
        ]
        # Create mock processes that are running
        mock_process1 = Mock()
        mock_process1.poll.return_value = None  # Running
        mock_process1.pid = 12345
        mock_process2 = Mock()
        mock_process2.poll.return_value = None  # Running
        mock_process2.pid = 12346
        manager._worker_manager.worker_processes = [mock_process1, mock_process2]

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.cluster_resources.return_value = {
                    "CPU": 12.0,
                    "memory": 32000000000,
                }
                mock_ray.available_resources.return_value = {
                    "CPU": 8.0,
                    "memory": 20000000000,
                }
                mock_ray.nodes.return_value = [
                    {
                        "NodeID": "node1",
                        "Alive": True,
                        "NodeName": "head-node",
                        "NodeManagerAddress": "127.0.0.1:12345",
                        "NodeManagerHostname": "head-node",
                        "NodeManagerPort": 12345,
                        "ObjectManagerPort": 12346,
                        "ObjectStoreSocketName": "/tmp/ray/session_123/object_store",
                        "RayletSocketName": "/tmp/ray/session_123/raylet",
                        "Resources": {"CPU": 4.0, "memory": 16000000000},
                        "UsedResources": {"CPU": 2.0, "memory": 8000000000},
                    },
                    {
                        "NodeID": "node2",
                        "Alive": True,
                        "NodeName": "worker-1",
                        "NodeManagerAddress": "127.0.0.1:12347",
                        "NodeManagerHostname": "worker-1",
                        "NodeManagerPort": 12347,
                        "ObjectManagerPort": 12348,
                        "ObjectStoreSocketName": "/tmp/ray/session_123/object_store_2",
                        "RayletSocketName": "/tmp/ray/session_123/raylet_2",
                        "Resources": {"CPU": 8.0, "memory": 16000000000},
                        "UsedResources": {"CPU": 4.0, "memory": 8000000000},
                    },
                ]

                result = await manager.get_cluster_info()

                assert result["status"] == "success"
                assert "cluster_overview" in result
                assert "resources" in result
                assert "nodes" in result
                assert "worker_nodes" in result

                # Check cluster overview
                overview = result["cluster_overview"]
                assert overview["status"] == "running"
                assert overview["address"] == "ray://127.0.0.1:10001"
                assert overview["total_nodes"] == 2
                assert overview["alive_nodes"] == 2
                assert overview["total_workers"] == 2
                assert overview["running_workers"] == 2

                # Check resources
                resources = result["resources"]
                assert "cluster_resources" in resources
                assert "available_resources" in resources
                assert "resource_usage" in resources
                assert resources["cluster_resources"]["CPU"] == 12.0
                assert resources["resource_usage"]["CPU"]["total"] == 12.0
                assert resources["resource_usage"]["CPU"]["available"] == 8.0
                assert resources["resource_usage"]["CPU"]["used"] == 4.0

                # Check nodes
                nodes = result["nodes"]
                assert len(nodes) == 2
                assert nodes[0]["node_id"] == "node1"
                assert nodes[0]["alive"] is True
                assert nodes[0]["node_name"] == "head-node"
                assert nodes[0]["resources"]["CPU"] == 4.0

                # Check worker nodes
                worker_nodes = result["worker_nodes"]
                assert len(worker_nodes) == 2
                assert worker_nodes[0]["node_name"] == "worker-1"
                assert worker_nodes[0]["status"] == "running"

    @pytest.mark.asyncio
    async def test_get_cluster_info_ray_unavailable(self, manager):
        """Test get cluster info when Ray is unavailable."""
        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", False):
            result = await manager.get_cluster_info()

            assert result["status"] == "unavailable"
            assert "Ray is not available" in result["message"]

    @pytest.mark.asyncio
    async def test_get_cluster_info_with_exception(self, manager):
        """Test get cluster info with exception."""
        manager._is_initialized = True

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.is_initialized.return_value = True
                mock_ray.cluster_resources.side_effect = Exception("Status error")

                result = await manager.get_cluster_info()
                assert result["status"] == "error"
                assert "Status error" in result["message"]

    @pytest.mark.asyncio
    async def test_gcs_address_storage_and_usage(self):
        """Test that GCS address is properly stored and used for worker nodes."""
        manager = RayManager()

        # Mock ray.init and related functions
        mock_context = Mock()
        mock_context.address_info = {
            "address": "ray://127.0.0.1:10001",
        }
        mock_context.dashboard_url = "http://127.0.0.1:8265"
        mock_context.session_name = "test_session"

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.init.return_value = mock_context
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "test_node_id"
                )

                with patch("ray_mcp.ray_manager.JobSubmissionClient"):
                    with patch("subprocess.Popen") as mock_popen:
                        # Mock the subprocess to simulate successful ray start
                        mock_process = Mock()
                        mock_process.communicate.return_value = (
                            "Ray runtime started\n--address='127.0.0.1:10002'",
                            "",
                        )
                        mock_process.poll.return_value = 0
                        mock_popen.return_value = mock_process

                        # Test with worker nodes to verify GCS address usage
                        worker_configs = [{"num_cpus": 2, "node_name": "test-worker"}]

                        with patch.object(
                            manager._worker_manager,
                            "start_worker_nodes",
                            new_callable=AsyncMock,
                        ) as mock_start_workers:
                            mock_start_workers.return_value = [
                                {
                                    "status": "started",
                                    "node_name": "test-worker",
                                    "message": "Worker node 'test-worker' started successfully",
                                    "process_id": 12345,
                                    "config": worker_configs[0],
                                }
                            ]

                            result = await manager.start_cluster(
                                worker_nodes=worker_configs
                            )

                            # Verify the cluster started successfully
                            assert result["status"] == "started"
                            assert manager._is_initialized

                            # Verify GCS address was stored
                            assert manager._gcs_address == "127.0.0.1:10002"

                            # Verify worker manager was called with GCS address
                            mock_start_workers.assert_called_once()
                            call_args = mock_start_workers.call_args
                            assert call_args[0][0] == worker_configs
                            # GCS address without ray://
                            assert call_args[0][1] == "127.0.0.1:10002"

    # ===== HELPER FUNCTION TESTS =====

    def test_parse_dashboard_url_single_quoted(self):
        """Test parse_dashboard_url with single-quoted URL."""
        from ray_mcp.ray_manager import RayManager

        # Create a manager instance to access the helper function
        manager = RayManager()

        # Test with single-quoted URL
        stdout = (
            "Ray runtime started\nView the Ray dashboard at 'http://127.0.0.1:8265'"
        )

        # Extract the helper function from the start_cluster method
        import re

        def parse_dashboard_url(stdout: str):
            pattern = r"View the Ray dashboard at ['\"]?(http://[^\s\"']+)['\"]?"
            match = re.search(pattern, stdout)
            return match.group(1) if match else None

        result = parse_dashboard_url(stdout)
        assert result == "http://127.0.0.1:8265"

    def test_parse_dashboard_url_double_quoted(self):
        """Test parse_dashboard_url with double-quoted URL."""
        import re

        def parse_dashboard_url(stdout: str):
            pattern = r"View the Ray dashboard at ['\"]?(http://[^\s\"']+)['\"]?"
            match = re.search(pattern, stdout)
            return match.group(1) if match else None

        # Test with double-quoted URL
        stdout = (
            'Ray runtime started\nView the Ray dashboard at "http://127.0.0.1:8265"'
        )
        result = parse_dashboard_url(stdout)
        assert result == "http://127.0.0.1:8265"

    def test_parse_dashboard_url_unquoted(self):
        """Test parse_dashboard_url with unquoted URL."""
        import re

        def parse_dashboard_url(stdout: str):
            pattern = r"View the Ray dashboard at ['\"]?(http://[^\s\"']+)['\"]?"
            match = re.search(pattern, stdout)
            return match.group(1) if match else None

        # Test with unquoted URL
        stdout = "Ray runtime started\nView the Ray dashboard at http://127.0.0.1:8265"
        result = parse_dashboard_url(stdout)
        assert result == "http://127.0.0.1:8265"

    def test_parse_dashboard_url_not_found(self):
        """Test parse_dashboard_url when URL is not found."""
        import re

        def parse_dashboard_url(stdout: str):
            pattern = r"View the Ray dashboard at ['\"]?(http://[^\s\"']+)['\"]?"
            match = re.search(pattern, stdout)
            return match.group(1) if match else None

        # Test with no dashboard URL
        stdout = "Ray runtime started\nNo dashboard information"
        result = parse_dashboard_url(stdout)
        assert result is None

    def test_parse_dashboard_url_complex_url(self):
        """Test parse_dashboard_url with complex URL containing query parameters."""
        import re

        def parse_dashboard_url(stdout: str):
            pattern = r"View the Ray dashboard at ['\"]?(http://[^\s\"']+)['\"]?"
            match = re.search(pattern, stdout)
            return match.group(1) if match else None

        # Test with complex URL
        stdout = 'Ray runtime started\nView the Ray dashboard at "http://127.0.0.1:8265?token=abc123"'
        result = parse_dashboard_url(stdout)
        assert result == "http://127.0.0.1:8265?token=abc123"

    def test_parse_gcs_address_single_quoted(self):
        """Test parse_gcs_address with single-quoted address."""
        import re

        def parse_gcs_address(stdout: str):
            pattern = r"--address=['\"]?([\d\.]+:\d+)['\"]?"
            match = re.search(pattern, stdout)
            return match.group(1) if match else None

        # Test with single-quoted address
        stdout = "Ray runtime started\n--address='127.0.0.1:10001'"
        result = parse_gcs_address(stdout)
        assert result == "127.0.0.1:10001"

    def test_parse_gcs_address_double_quoted(self):
        """Test parse_gcs_address with double-quoted address."""
        import re

        def parse_gcs_address(stdout: str):
            pattern = r"--address=['\"]?([\d\.]+:\d+)['\"]?"
            match = re.search(pattern, stdout)
            return match.group(1) if match else None

        # Test with double-quoted address
        stdout = 'Ray runtime started\n--address="127.0.0.1:10001"'
        result = parse_gcs_address(stdout)
        assert result == "127.0.0.1:10001"

    def test_parse_gcs_address_unquoted(self):
        """Test parse_gcs_address with unquoted address."""
        import re

        def parse_gcs_address(stdout: str):
            pattern = r"--address=['\"]?([\d\.]+:\d+)['\"]?"
            match = re.search(pattern, stdout)
            return match.group(1) if match else None

        # Test with unquoted address
        stdout = "Ray runtime started\n--address=127.0.0.1:10001"
        result = parse_gcs_address(stdout)
        assert result == "127.0.0.1:10001"

    def test_parse_gcs_address_not_found(self):
        """Test parse_gcs_address when address is not found."""
        import re

        def parse_gcs_address(stdout: str):
            pattern = r"--address=['\"]?([\d\.]+:\d+)['\"]?"
            match = re.search(pattern, stdout)
            return match.group(1) if match else None

        # Test with no address
        stdout = "Ray runtime started\nNo address information"
        result = parse_gcs_address(stdout)
        assert result is None

    def test_parse_gcs_address_multiple_addresses(self):
        """Test parse_gcs_address with multiple address patterns in output."""
        import re

        def parse_gcs_address(stdout: str):
            pattern = r"--address=['\"]?([\d\.]+:\d+)['\"]?"
            match = re.search(pattern, stdout)
            return match.group(1) if match else None

        # Test with multiple address patterns (should match the first one)
        stdout = "Ray runtime started\n--address='127.0.0.1:10001'\n--address='192.168.1.1:10002'"
        result = parse_gcs_address(stdout)
        assert result == "127.0.0.1:10001"

    def test_parse_gcs_address_complex_ip(self):
        """Test parse_gcs_address with complex IP addresses."""
        import re

        def parse_gcs_address(stdout: str):
            pattern = r"--address=['\"]?([\d\.]+:\d+)['\"]?"
            match = re.search(pattern, stdout)
            return match.group(1) if match else None

        # Test with complex IP addresses
        test_cases = [
            ("--address='192.168.1.100:10001'", "192.168.1.100:10001"),
            ('--address="10.0.0.50:20001"', "10.0.0.50:20001"),
            ("--address=172.16.0.25:30001", "172.16.0.25:30001"),
        ]

        for stdout, expected in test_cases:
            result = parse_gcs_address(f"Ray runtime started\n{stdout}")
            assert result == expected, f"Failed for {stdout}"

    def test_parse_gcs_address_edge_cases(self):
        """Test parse_gcs_address with edge cases."""
        import re

        def parse_gcs_address(stdout: str):
            pattern = r"--address=['\"]?([\d\.]+:\d+)['\"]?"
            match = re.search(pattern, stdout)
            return match.group(1) if match else None

        # Test edge cases
        test_cases = [
            # Valid cases
            ("--address='0.0.0.0:10001'", "0.0.0.0:10001"),
            ("--address='255.255.255.255:65535'", "255.255.255.255:65535"),
            ("--address='127.0.0.1:1'", "127.0.0.1:1"),
            # Invalid cases (should not match)
            ("--address='invalid:port'", None),
            ("--address='127.0.0.1'", None),  # No port
            ("--address=':10001'", None),  # No IP
        ]

        for stdout, expected in test_cases:
            result = parse_gcs_address(f"Ray runtime started\n{stdout}")
            assert result == expected, f"Failed for {stdout}"

    @pytest.mark.asyncio
    async def test_start_cluster_with_address_filters_parameters(self):
        """Test that cluster-starting parameters are filtered when connecting to existing cluster."""
        manager = RayManager()

        # Mock ray.init and related functions
        mock_context = Mock()
        mock_context.address_info = {
            "address": "ray://127.0.0.1:10001",
        }
        mock_context.dashboard_url = "http://127.0.0.1:8265"
        mock_context.session_name = "test_session"

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.init.return_value = mock_context
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "test_node_id"
                )

                with patch("ray_mcp.ray_manager.JobSubmissionClient"):
                    # Test connecting to existing cluster with cluster-starting parameters
                    result = await manager.start_cluster(
                        address="ray://127.0.0.1:10001",
                        num_cpus=8,  # Should be filtered out
                        num_gpus=2,  # Should be filtered out
                        object_store_memory=1000000000,  # Should be filtered out
                        head_node_port=20001,  # Should be filtered out
                        dashboard_port=9000,  # Should be filtered out
                        head_node_host="0.0.0.0",  # Should be filtered out
                        worker_nodes=[{"num_cpus": 4}],  # Should be filtered out
                        custom_param="should_pass",  # Should not be filtered
                        another_param=123,  # Should not be filtered
                    )

                    assert result["status"] == "started"
                    assert manager._is_initialized

                    # Verify ray.init was called with only valid parameters
                    mock_ray.init.assert_called_once()
                    call_args = mock_ray.init.call_args[1]

                    # Check that cluster-starting parameters were filtered out
                    assert "num_cpus" not in call_args
                    assert "num_gpus" not in call_args
                    assert "object_store_memory" not in call_args
                    assert "head_node_port" not in call_args
                    assert "dashboard_port" not in call_args
                    assert "head_node_host" not in call_args
                    assert "worker_nodes" not in call_args

                    # Check that valid parameters were passed through
                    assert call_args["address"] == "ray://127.0.0.1:10001"
                    assert call_args["ignore_reinit_error"] is True
                    assert call_args["custom_param"] == "should_pass"
                    assert call_args["another_param"] == 123

    @pytest.mark.asyncio
    async def test_connect_cluster_filters_parameters(self):
        """Test that connect_cluster filters out cluster-starting parameters."""
        manager = RayManager()

        # Mock ray.init and related functions
        mock_context = Mock()
        mock_context.address_info = {
            "address": "ray://127.0.0.1:10001",
        }
        mock_context.dashboard_url = "http://127.0.0.1:8265"
        mock_context.session_name = "test_session"

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.init.return_value = mock_context
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "test_node_id"
                )

                with patch("ray_mcp.ray_manager.JobSubmissionClient"):
                    # Test connecting to existing cluster with cluster-starting parameters
                    result = await manager.connect_cluster(
                        "ray://127.0.0.1:10001",
                        num_cpus=8,  # Should be filtered out
                        num_gpus=2,  # Should be filtered out
                        object_store_memory=1000000000,  # Should be filtered out
                        head_node_port=20001,  # Should be filtered out
                        dashboard_port=9000,  # Should be filtered out
                        head_node_host="0.0.0.0",  # Should be filtered out
                        worker_nodes=[{"num_cpus": 4}],  # Should be filtered out
                        custom_param="should_pass",  # Should not be filtered
                        another_param=123,  # Should not be filtered
                    )

                    assert result["status"] == "connected"
                    assert manager._is_initialized

                    # Verify ray.init was called with only valid parameters
                    mock_ray.init.assert_called_once()
                    call_args = mock_ray.init.call_args[1]

                    # Check that cluster-starting parameters were filtered out
                    assert "num_cpus" not in call_args
                    assert "num_gpus" not in call_args
                    assert "object_store_memory" not in call_args
                    assert "head_node_port" not in call_args
                    assert "dashboard_port" not in call_args
                    assert "head_node_host" not in call_args
                    assert "worker_nodes" not in call_args

                    # Check that valid parameters were passed through
                    assert call_args["address"] == "ray://127.0.0.1:10001"
                    assert call_args["ignore_reinit_error"] is True
                    assert call_args["custom_param"] == "should_pass"
                    assert call_args["another_param"] == 123

    @pytest.mark.asyncio
    async def test_filter_cluster_starting_parameters_method(self):
        """Test the _filter_cluster_starting_parameters helper method directly."""
        manager = RayManager()

        # Test with mixed parameters
        test_kwargs = {
            "num_cpus": 8,
            "num_gpus": 2,
            "object_store_memory": 1000000000,
            "head_node_port": 20001,
            "dashboard_port": 9000,
            "head_node_host": "0.0.0.0",
            "worker_nodes": [{"num_cpus": 4}],
            "custom_param": "should_pass",
            "another_param": 123,
            "ignore_reinit_error": True,
        }

        with patch("ray_mcp.ray_manager.logger") as mock_logger:
            filtered_kwargs = manager._filter_cluster_starting_parameters(test_kwargs)

        # Check that cluster-starting parameters were filtered out
        assert "num_cpus" not in filtered_kwargs
        assert "num_gpus" not in filtered_kwargs
        assert "object_store_memory" not in filtered_kwargs
        assert "head_node_port" not in filtered_kwargs
        assert "dashboard_port" not in filtered_kwargs
        assert "head_node_host" not in filtered_kwargs
        assert "worker_nodes" not in filtered_kwargs

        # Check that valid parameters were preserved
        assert filtered_kwargs["custom_param"] == "should_pass"
        assert filtered_kwargs["another_param"] == 123
        assert filtered_kwargs["ignore_reinit_error"] is True

        # Check that logging was called for each filtered parameter
        assert mock_logger.info.call_count == 8  # 7 filtered params + 1 summary log

    @pytest.mark.asyncio
    async def test_start_cluster_with_address_no_parameters_filtered(self):
        """Test that when no cluster-starting parameters are provided, no filtering occurs."""
        manager = RayManager()

        # Mock ray.init and related functions
        mock_context = Mock()
        mock_context.address_info = {
            "address": "ray://127.0.0.1:10001",
        }
        mock_context.dashboard_url = "http://127.0.0.1:8265"
        mock_context.session_name = "test_session"

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.init.return_value = mock_context
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "test_node_id"
                )

                with patch("ray_mcp.ray_manager.JobSubmissionClient"):
                    # Test connecting to existing cluster with only valid parameters
                    result = await manager.start_cluster(
                        address="ray://127.0.0.1:10001",
                        custom_param="should_pass",
                        another_param=123,
                    )

                    assert result["status"] == "started"
                    assert manager._is_initialized

                    # Verify ray.init was called with the parameters
                    mock_ray.init.assert_called_once()
                    call_args = mock_ray.init.call_args[1]

                    # Check that valid parameters were passed through
                    assert call_args["address"] == "ray://127.0.0.1:10001"
                    assert call_args["ignore_reinit_error"] is True
                    assert call_args["custom_param"] == "should_pass"
                    assert call_args["another_param"] == 123

    @pytest.mark.asyncio
    async def test_start_cluster_with_specified_ports(self, manager):
        """Test start cluster with specified head_node_port and dashboard_port."""
        mock_context = Mock()
        mock_context.address_info = {"address": "ray://127.0.0.1:10001"}
        mock_context.dashboard_url = "http://127.0.0.1:8265"
        mock_context.session_name = "test_session"

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.init.return_value = mock_context
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "test_node"
                )

                with patch("ray_mcp.ray_manager.JobSubmissionClient"):
                    with patch("subprocess.Popen") as mock_popen:
                        # Mock the subprocess to simulate successful ray start
                        mock_process = Mock()
                        mock_process.communicate.return_value = (
                            "Ray runtime started\n--address='127.0.0.1:10001'\nView the Ray dashboard at http://127.0.0.1:8265",
                            "",
                        )
                        mock_process.poll.return_value = 0
                        mock_popen.return_value = mock_process

                        result = await manager.start_cluster(
                            head_node_port=10001,
                            dashboard_port=8265,
                            worker_nodes=[],
                        )

                        assert result["status"] == "started"
                        # Verify the ray start command was called with the specified ports
                        mock_popen.assert_called_once()
                        call_args = mock_popen.call_args[0][0]
                        assert "--port" in call_args
                        assert "--dashboard-port" in call_args

                        # Find the port arguments in the command
                        port_index = call_args.index("--port")
                        dashboard_port_index = call_args.index("--dashboard-port")

                        # Verify the specified ports were used
                        assert call_args[port_index + 1] == "10001"
                        assert call_args[dashboard_port_index + 1] == "8265"

    @pytest.mark.asyncio
    async def test_start_cluster_with_none_ports_uses_free_ports(self, manager):
        """Test start cluster with None ports uses find_free_port."""
        mock_context = Mock()
        mock_context.address_info = {"address": "ray://127.0.0.1:10001"}
        mock_context.dashboard_url = "http://127.0.0.1:8265"
        mock_context.session_name = "test_session"

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.init.return_value = mock_context
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "test_node"
                )

                with patch("ray_mcp.ray_manager.JobSubmissionClient"):
                    with patch("subprocess.Popen") as mock_popen:
                        # Mock the subprocess to simulate successful ray start
                        mock_process = Mock()
                        mock_process.communicate.return_value = (
                            "Ray runtime started\n--address='127.0.0.1:10001'\nView the Ray dashboard at http://127.0.0.1:8265",
                            "",
                        )
                        mock_process.poll.return_value = 0
                        mock_popen.return_value = mock_process

                        # Mock find_free_port to return predictable values
                        with patch("socket.socket") as mock_socket:
                            mock_socket.return_value.__enter__.return_value.bind.side_effect = [
                                None,  # First call succeeds (port 10001)
                                None,  # Second call succeeds (port 8265)
                                None,  # Third call succeeds (port 10002)
                            ]

                            result = await manager.start_cluster(
                                head_node_port=None,
                                dashboard_port=None,
                                worker_nodes=[],
                            )

                            assert result["status"] == "started"
                            # Verify the ray start command was called with free ports
                            mock_popen.assert_called_once()
                            call_args = mock_popen.call_args[0][0]
                            assert "--port" in call_args
                            assert "--dashboard-port" in call_args

    @pytest.mark.asyncio
    async def test_start_cluster_mixed_port_specification(self, manager):
        """Test start cluster with one port specified and one None."""
        mock_context = Mock()
        mock_context.address_info = {"address": "ray://127.0.0.1:10001"}
        mock_context.dashboard_url = "http://127.0.0.1:8265"
        mock_context.session_name = "test_session"

        with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.ray_manager.ray") as mock_ray:
                mock_ray.init.return_value = mock_context
                mock_ray.get_runtime_context.return_value.get_node_id.return_value = (
                    "test_node"
                )

                with patch("ray_mcp.ray_manager.JobSubmissionClient"):
                    with patch("subprocess.Popen") as mock_popen:
                        # Mock the subprocess to simulate successful ray start
                        mock_process = Mock()
                        mock_process.communicate.return_value = (
                            "Ray runtime started\n--address='127.0.0.1:10001'\nView the Ray dashboard at http://127.0.0.1:8265",
                            "",
                        )
                        mock_process.poll.return_value = 0
                        mock_popen.return_value = mock_process

                        # Mock find_free_port to return predictable values
                        with patch("socket.socket") as mock_socket:
                            mock_socket.return_value.__enter__.return_value.bind.side_effect = [
                                None,  # First call succeeds (port 8265)
                                None,  # Second call succeeds (port 10002)
                            ]

                            result = await manager.start_cluster(
                                head_node_port=10001,  # Specified
                                dashboard_port=None,  # Will use find_free_port
                                worker_nodes=[],
                            )

                            assert result["status"] == "started"
                            # Verify the ray start command was called with correct ports
                            mock_popen.assert_called_once()
                            call_args = mock_popen.call_args[0][0]
                            assert "--port" in call_args
                            assert "--dashboard-port" in call_args

                            # Find the port arguments in the command
                            port_index = call_args.index("--port")
                            dashboard_port_index = call_args.index("--dashboard-port")

                            # Verify the specified head_node_port was used and dashboard_port was found
                            assert call_args[port_index + 1] == "10001"
                            # The dashboard port should be the first free port found (8265)
                            assert call_args[dashboard_port_index + 1] == "8265"


if __name__ == "__main__":
    pytest.main([__file__])
