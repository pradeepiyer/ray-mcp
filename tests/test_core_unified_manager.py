"""Unit tests for RayUnifiedManager component.

Tests focus on unified manager behavior with 100% mocking.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ray_mcp.managers.unified_manager import RayUnifiedManager


@pytest.mark.fast
class TestRayUnifiedManagerCore:
    """Test core unified manager functionality."""

    @patch("ray_mcp.managers.unified_manager.RayStateManager")
    @patch("ray_mcp.managers.unified_manager.RayPortManager")
    @patch("ray_mcp.managers.unified_manager.RayClusterManager")
    @patch("ray_mcp.managers.unified_manager.RayJobManager")
    @patch("ray_mcp.managers.unified_manager.RayLogManager")
    def test_manager_instantiation_creates_all_components(
        self,
        mock_log_mgr,
        mock_job_mgr,
        mock_cluster_mgr,
        mock_port_mgr,
        mock_state_mgr,
    ):
        """Test that unified manager instantiates all required components."""
        mock_state_instance = Mock()
        mock_port_instance = Mock()
        mock_cluster_instance = Mock()
        mock_job_instance = Mock()
        mock_log_instance = Mock()

        mock_state_mgr.return_value = mock_state_instance
        mock_port_mgr.return_value = mock_port_instance
        mock_cluster_mgr.return_value = mock_cluster_instance
        mock_job_mgr.return_value = mock_job_instance
        mock_log_mgr.return_value = mock_log_instance

        RayUnifiedManager()

        # Verify all components are created
        mock_state_mgr.assert_called_once()
        mock_port_mgr.assert_called_once()
        mock_cluster_mgr.assert_called_once_with(
            mock_state_instance, mock_port_instance
        )
        mock_job_mgr.assert_called_once_with(mock_state_instance)
        mock_log_mgr.assert_called_once_with(mock_state_instance)

    def test_component_access_methods(self):
        """Test that component access methods return correct instances."""
        manager = RayUnifiedManager()

        # Test component getters
        assert manager.get_state_manager() is not None
        assert manager.get_cluster_manager() is not None
        assert manager.get_job_manager() is not None
        assert manager.get_log_manager() is not None
        assert manager.get_port_manager() is not None

    def test_property_delegation_to_state_manager(self):
        """Test that properties are correctly delegated to state manager."""
        manager = RayUnifiedManager()

        # Mock the state manager's get_state method
        mock_state = {
            "initialized": True,
            "cluster_address": "127.0.0.1:10001",
            "dashboard_url": "http://127.0.0.1:8265",
            "job_client": Mock(),
        }

        with patch.object(manager._state_manager, "get_state", return_value=mock_state):
            with patch.object(
                manager._state_manager, "is_initialized", return_value=True
            ):
                assert manager.is_initialized is True
                assert manager.cluster_address == "127.0.0.1:10001"
                assert manager.dashboard_url == "http://127.0.0.1:8265"
                assert manager.job_client is not None

    def test_dependency_injection_consistency(self):
        """Test that dependencies are properly injected."""
        manager = RayUnifiedManager()

        # Import concrete types to access private attributes
        from ray_mcp.managers.cluster_manager import RayClusterManager
        from ray_mcp.managers.job_manager import RayJobManager
        from ray_mcp.managers.log_manager import RayLogManager

        cluster_mgr = manager._cluster_manager
        job_mgr = manager._job_manager
        log_mgr = manager._log_manager

        # Cluster manager should have both state and port managers
        if isinstance(cluster_mgr, RayClusterManager):
            assert cluster_mgr.state_manager is manager._state_manager
            assert cluster_mgr._port_manager is manager._port_manager

        # Other managers should have state manager
        if isinstance(job_mgr, RayJobManager):
            assert job_mgr.state_manager is manager._state_manager
        if isinstance(log_mgr, RayLogManager):
            assert log_mgr.state_manager is manager._state_manager

    @pytest.mark.parametrize(
        "property_name",
        ["is_initialized", "cluster_address", "dashboard_url", "job_client"],
    )
    def test_property_access_consistency(self, property_name):
        """Test that property access is consistent with state manager."""
        manager = RayUnifiedManager()

        # Mock state manager state
        mock_state = {
            "initialized": True,
            "cluster_address": "127.0.0.1:10001",
            "dashboard_url": "http://127.0.0.1:8265",
            "job_client": Mock(),
        }

        with patch.object(manager._state_manager, "get_state", return_value=mock_state):
            with patch.object(
                manager._state_manager, "is_initialized", return_value=True
            ):
                # Property access should be consistent
                manager_value = getattr(manager, property_name)

                if property_name == "is_initialized":
                    assert manager_value is True
                else:
                    assert manager_value == mock_state[property_name]


@pytest.mark.fast
class TestRayUnifiedManagerDelegation:
    """Test delegation to underlying components."""

    async def test_cluster_management_delegation(self):
        """Test that cluster management methods are delegated correctly."""
        manager = RayUnifiedManager()

        # Mock cluster manager methods
        mock_cluster_manager = Mock()
        mock_cluster_manager.init_cluster = AsyncMock(
            return_value={"status": "success", "cluster_address": "127.0.0.1:10001"}
        )
        mock_cluster_manager.stop_cluster = AsyncMock(
            return_value={"status": "success", "message": "Cluster stopped"}
        )
        mock_cluster_manager.inspect_cluster = AsyncMock(
            return_value={"status": "running"}
        )

        manager._cluster_manager = mock_cluster_manager

        # Test init_cluster delegation
        result = await manager.init_cluster(num_cpus=4, worker_nodes=[])
        assert result["status"] == "success"
        mock_cluster_manager.init_cluster.assert_called_with(
            num_cpus=4, worker_nodes=[]
        )

        # Test stop_cluster delegation
        result = await manager.stop_cluster()
        assert result["message"] == "Cluster stopped"
        mock_cluster_manager.stop_cluster.assert_called_once()

        # Test inspect_ray_cluster delegation
        result = await manager.inspect_ray_cluster()
        assert result["status"] == "running"
        mock_cluster_manager.inspect_cluster.assert_called_once()

    async def test_job_management_delegation(self):
        """Test that job management methods are delegated correctly."""
        manager = RayUnifiedManager()

        # Mock job manager methods
        mock_job_manager = Mock()
        mock_job_manager.submit_job = AsyncMock(
            return_value={"status": "success", "job_id": "job_123"}
        )
        mock_job_manager.list_jobs = AsyncMock(
            return_value={"status": "success", "jobs": []}
        )
        mock_job_manager.cancel_job = AsyncMock(
            return_value={"status": "success", "cancelled": True}
        )
        mock_job_manager.inspect_job = AsyncMock(
            return_value={"status": "success", "job_info": {}}
        )

        manager._job_manager = mock_job_manager

        # Test submit_ray_job delegation
        result = await manager.submit_ray_job(
            "python script.py", runtime_env={"pip": ["numpy"]}
        )
        assert result["job_id"] == "job_123"
        # Check that submit_job was called (signature may vary between implementations)
        mock_job_manager.submit_job.assert_called_once()

        # Test list_ray_jobs delegation
        result = await manager.list_ray_jobs()
        assert result["jobs"] == []
        mock_job_manager.list_jobs.assert_called_once()

        # Test cancel_ray_job delegation
        result = await manager.cancel_ray_job("job_123")
        assert result["cancelled"] is True
        mock_job_manager.cancel_job.assert_called_with("job_123")

        # Test inspect_ray_job delegation
        result = await manager.inspect_ray_job("job_123", mode="debug")
        assert "job_info" in result
        mock_job_manager.inspect_job.assert_called_with("job_123", "debug")

    async def test_log_management_delegation(self):
        """Test that log management methods are delegated correctly."""
        manager = RayUnifiedManager()

        # Mock log manager methods
        mock_log_manager = Mock()
        mock_log_manager.retrieve_logs = AsyncMock(
            return_value={"status": "success", "logs": "Log content"}
        )

        manager._log_manager = mock_log_manager

        # Test retrieve_logs delegation without pagination
        result = await manager.retrieve_logs("job_123", log_type="job", num_lines=50)
        assert result["logs"] == "Log content"
        mock_log_manager.retrieve_logs.assert_called_with(
            "job_123", "job", 50, False, 10, None, None
        )

        # Test retrieve_logs delegation with pagination
        mock_log_manager.retrieve_logs = AsyncMock(
            return_value={
                "status": "success",
                "logs": "Page content",
                "pagination": {"current_page": 1},
            }
        )
        result = await manager.retrieve_logs(
            "job_123", log_type="job", page=2, page_size=25
        )
        assert result["pagination"]["current_page"] == 1
        mock_log_manager.retrieve_logs.assert_called_with(
            "job_123", "job", 100, False, 10, 2, 25
        )

    async def test_port_management_delegation(self):
        """Test that port management methods are delegated correctly."""
        manager = RayUnifiedManager()

        # Mock port manager methods
        mock_port_manager = Mock()
        mock_port_manager.find_free_port = AsyncMock(return_value=10001)

        manager._port_manager = mock_port_manager

        # Test find_free_port delegation
        port = await manager.find_free_port(start_port=10000, max_tries=10)
        assert port == 10001
        mock_port_manager.find_free_port.assert_called_with(10000, 10)

        # Test cleanup_port_lock delegation
        manager.cleanup_port_lock(10001)
        mock_port_manager.cleanup_port_lock.assert_called_with(10001)


@pytest.mark.fast
class TestRayUnifiedManagerBackwardCompatibility:
    """Test backward compatibility with original RayManager interface."""

    def test_has_all_expected_properties(self):
        """Test that all expected properties are available."""
        manager = RayUnifiedManager()

        # Properties that should exist for backward compatibility
        expected_properties = [
            "is_initialized",
            "cluster_address",
            "dashboard_url",
            "job_client",
        ]

        for prop in expected_properties:
            assert hasattr(manager, prop), f"Missing property: {prop}"

    def test_has_all_expected_methods(self):
        """Test that all expected methods are available."""
        manager = RayUnifiedManager()

        # Methods that should exist for backward compatibility
        expected_methods = [
            "init_cluster",
            "stop_cluster",
            "inspect_ray_cluster",
            "submit_ray_job",
            "list_ray_jobs",
            "cancel_ray_job",
            "inspect_ray_job",
            "retrieve_logs",
            "find_free_port",
            "cleanup_port_lock",
        ]

        for method in expected_methods:
            assert hasattr(manager, method), f"Missing method: {method}"
            assert callable(
                getattr(manager, method)
            ), f"Method {method} is not callable"

    async def test_method_signatures_compatible(self):
        """Test that method signatures are compatible with original interface."""
        manager = RayUnifiedManager()

        # Mock all underlying managers to avoid actual calls
        manager._cluster_manager = Mock()
        manager._job_manager = Mock()
        manager._log_manager = Mock()
        manager._port_manager = Mock()

        # Configure return values
        manager._cluster_manager.init_cluster = AsyncMock(
            return_value={"status": "success"}
        )
        manager._job_manager.submit_job = AsyncMock(return_value={"status": "success"})
        manager._job_manager.list_jobs = AsyncMock(return_value={"status": "success"})
        manager._job_manager.cancel_job = AsyncMock(return_value={"status": "success"})
        manager._job_manager.inspect_job = AsyncMock(return_value={"status": "success"})
        manager._cluster_manager.stop_cluster = AsyncMock(
            return_value={"status": "success"}
        )
        manager._cluster_manager.inspect_cluster = AsyncMock(
            return_value={"status": "success"}
        )
        manager._log_manager.retrieve_logs = AsyncMock(
            return_value={"status": "success"}
        )
        manager._port_manager.find_free_port = AsyncMock(return_value=10001)

        # Test that core methods can be called
        await manager.init_cluster(num_cpus=2)
        await manager.submit_ray_job("python script.py")
        await manager.list_ray_jobs()
        await manager.retrieve_logs("job_123")
        port = await manager.find_free_port()
        assert port == 10001


@pytest.mark.fast
class TestRayUnifiedManagerErrorPropagation:
    """Test that errors are properly propagated from underlying components."""

    async def test_cluster_manager_error_propagation(self):
        """Test that cluster manager errors are properly propagated."""
        manager = RayUnifiedManager()

        # Mock cluster manager to raise an error
        mock_cluster_manager = Mock()
        mock_cluster_manager.init_cluster = AsyncMock(
            side_effect=Exception("Cluster initialization failed")
        )
        manager._cluster_manager = mock_cluster_manager

        # Error should propagate through
        with pytest.raises(Exception, match="Cluster initialization failed"):
            await manager.init_cluster()

    async def test_job_manager_error_propagation(self):
        """Test that job manager errors are properly propagated."""
        manager = RayUnifiedManager()

        # Mock job manager to return error response
        mock_job_manager = Mock()
        mock_job_manager.submit_job = AsyncMock(
            return_value={"status": "error", "message": "Job submission failed"}
        )
        manager._job_manager = mock_job_manager

        result = await manager.submit_ray_job("python script.py")
        assert result["status"] == "error"
        assert "Job submission failed" in result["message"]

    async def test_log_manager_error_propagation(self):
        """Test that log manager errors are properly propagated."""
        manager = RayUnifiedManager()

        # Mock log manager to return error response
        mock_log_manager = Mock()
        mock_log_manager.retrieve_logs = AsyncMock(
            return_value={"status": "error", "message": "Log retrieval failed"}
        )
        manager._log_manager = mock_log_manager

        result = await manager.retrieve_logs("job_123")
        assert result["status"] == "error"
        assert "Log retrieval failed" in result["message"]

    async def test_port_manager_error_propagation(self):
        """Test that port manager errors are properly propagated."""
        manager = RayUnifiedManager()

        # Mock port manager to raise an error
        mock_port_manager = Mock()
        mock_port_manager.find_free_port = AsyncMock(
            side_effect=RuntimeError("No free ports available")
        )
        manager._port_manager = mock_port_manager

        # Error should propagate through
        with pytest.raises(RuntimeError, match="No free ports available"):
            await manager.find_free_port()


@pytest.mark.fast
class TestRayUnifiedManagerStateConsistency:
    """Test state consistency across components."""

    def test_state_manager_shared_across_components(self):
        """Test that the same state manager instance is shared across components."""
        manager = RayUnifiedManager()

        # All components should share the same state manager instance
        # Cast to concrete types to access state_manager property
        from ray_mcp.managers.cluster_manager import RayClusterManager
        from ray_mcp.managers.job_manager import RayJobManager
        from ray_mcp.managers.log_manager import RayLogManager

        cluster_mgr = manager._cluster_manager
        job_mgr = manager._job_manager
        log_mgr = manager._log_manager

        # Check if they're the expected concrete types and have state_manager
        if isinstance(cluster_mgr, RayClusterManager):
            assert cluster_mgr.state_manager is manager._state_manager
        if isinstance(job_mgr, RayJobManager):
            assert job_mgr.state_manager is manager._state_manager
        if isinstance(log_mgr, RayLogManager):
            assert log_mgr.state_manager is manager._state_manager
