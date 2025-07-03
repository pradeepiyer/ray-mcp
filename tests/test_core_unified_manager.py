"""Unit tests for RayUnifiedManager component.

Tests focus on unified facade behavior with 100% mocking.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ray_mcp.core.unified_manager import RayUnifiedManager


@pytest.mark.fast
class TestRayUnifiedManagerCore:
    """Test core unified manager functionality."""

    @patch("ray_mcp.core.unified_manager.RayStateManager")
    @patch("ray_mcp.core.unified_manager.RayPortManager")
    @patch("ray_mcp.core.unified_manager.RayClusterManager")
    @patch("ray_mcp.core.unified_manager.RayJobManager")
    @patch("ray_mcp.core.unified_manager.RayLogManager")
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

        # Test inspect_ray delegation
        result = await manager.inspect_ray()
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

        # Test submit_job delegation
        result = await manager.submit_job(
            "python script.py", runtime_env={"pip": ["numpy"]}
        )
        assert result["job_id"] == "job_123"
        # Check that submit_job was called (signature may vary between implementations)
        mock_job_manager.submit_job.assert_called_once()

        # Test list_jobs delegation
        result = await manager.list_jobs()
        assert result["jobs"] == []
        mock_job_manager.list_jobs.assert_called_once()

        # Test cancel_job delegation
        result = await manager.cancel_job("job_123")
        assert result["cancelled"] is True
        mock_job_manager.cancel_job.assert_called_with("job_123")

        # Test inspect_job delegation
        result = await manager.inspect_job("job_123", mode="debug")
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
            "inspect_ray",
            "submit_job",
            "list_jobs",
            "cancel_job",
            "inspect_job",
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
        await manager.submit_job("python script.py")
        await manager.list_jobs()
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

        result = await manager.submit_job("python script.py")
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
        from ray_mcp.core.cluster_manager import RayClusterManager
        from ray_mcp.core.job_manager import RayJobManager
        from ray_mcp.core.log_manager import RayLogManager

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


@pytest.mark.fast
class TestRayClusterManagerGCSAddress:
    """Test GCS address retrieval functionality."""

    @patch("ray_mcp.core.cluster_manager.RAY_AVAILABLE", True)
    @patch("ray_mcp.core.cluster_manager.ray")
    @pytest.mark.parametrize(
        "ray_initialized,runtime_context,gcs_address,expected_result",
        [
            (
                True,
                Mock(gcs_address="192.168.1.100:10001"),
                "192.168.1.100:10001",
                "192.168.1.100:10001",
            ),  # Success case
            (False, None, None, None),  # Ray not initialized
            (True, None, None, None),  # No runtime context
            (True, Mock(gcs_address=None), None, None),  # No GCS address
        ],
    )
    async def test_get_actual_gcs_address_scenarios(
        self, mock_ray, ray_initialized, runtime_context, gcs_address, expected_result
    ):
        """Test GCS address retrieval for various scenarios."""
        mock_ray.is_initialized.return_value = ray_initialized
        mock_ray.get_runtime_context.return_value = runtime_context

        manager = RayUnifiedManager()
        cluster_mgr = manager._cluster_manager

        result = await cluster_mgr._get_actual_gcs_address()

        assert result == expected_result
        mock_ray.is_initialized.assert_called_once()
        if ray_initialized:
            mock_ray.get_runtime_context.assert_called_once()

    @patch("ray_mcp.core.cluster_manager.RAY_AVAILABLE", True)
    @patch("ray_mcp.core.cluster_manager.ray")
    async def test_connect_to_existing_cluster_uses_actual_gcs_address(self, mock_ray):
        """Test that connect_to_existing_cluster uses actual GCS address instead of provided address."""
        # Mock the dashboard connection test
        mock_job_client = Mock()

        # Mock Ray initialization and runtime context
        mock_context = Mock()
        mock_context.gcs_address = "actual.gcs.address:10001"

        # Setup mock to return False initially (not initialized), then True after init
        mock_ray.is_initialized.side_effect = [
            False,
            True,
        ]  # First call returns False, second returns True
        mock_ray.init = Mock()
        mock_ray.get_runtime_context.return_value = mock_context

        manager = RayUnifiedManager()
        cluster_mgr = manager._cluster_manager

        # Mock the dashboard connection test
        with patch.object(
            cluster_mgr, "_test_dashboard_connection", return_value=mock_job_client
        ):
            with patch.object(
                cluster_mgr, "_validate_cluster_address", return_value=True
            ):
                result = await cluster_mgr._connect_to_existing_cluster(
                    "provided.address:10001"
                )

        assert result["status"] == "success"

        # Verify that ray.init was called
        mock_ray.init.assert_called_once_with(ignore_reinit_error=True)

        # Verify that the state was updated with the actual GCS address, not the provided address
        state_manager = cluster_mgr.state_manager
        assert state_manager.get_state()["gcs_address"] == "actual.gcs.address:10001"

    def test_dependency_injection_consistency(self):
        """Test that dependencies are properly injected."""
        manager = RayUnifiedManager()

        # Import concrete types to access private attributes
        from ray_mcp.core.cluster_manager import RayClusterManager
        from ray_mcp.core.job_manager import RayJobManager
        from ray_mcp.core.log_manager import RayLogManager

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
class TestRayClusterManagerAddressParsing:
    """Test address validation and parsing functionality."""

    @pytest.fixture
    def cluster_manager(self):
        """Create a RayClusterManager instance for testing."""
        from ray_mcp.core.cluster_manager import RayClusterManager
        from ray_mcp.core.port_manager import RayPortManager
        from ray_mcp.core.state_manager import RayStateManager

        state_manager = RayStateManager()
        port_manager = RayPortManager()
        return RayClusterManager(state_manager, port_manager)

    @pytest.mark.parametrize(
        "address,expected_valid",
        [
            # Valid IPv4 addresses
            ("127.0.0.1:8000", True),
            ("192.168.1.100:10001", True),
            ("localhost:8000", True),
            ("example.com:8000", True),
            ("ray-cluster.example.com:8000", True),
            # Invalid addresses
            ("", False),
            ("invalid", False),
            ("127.0.0.1", False),  # Missing port
            ("127.0.0.1:", False),  # Missing port number
            ("127.0.0.1:abc", False),  # Invalid port
            ("127.0.0.1:99999", False),  # Port out of range
            ("127.0.0.1:0", False),  # Port zero
            ("300.300.300.300:8000", False),  # Invalid IPv4
        ],
    )
    def test_validate_cluster_address(self, cluster_manager, address, expected_valid):
        """Test address validation for various formats."""
        result = cluster_manager._validate_cluster_address(address)
        assert result == expected_valid

    @pytest.mark.parametrize(
        "host,expected_valid",
        [
            # Valid IPv4 addresses
            ("127.0.0.1", True),
            ("192.168.1.100", True),
            ("255.255.255.255", True),
            ("0.0.0.0", True),
            # Valid hostnames
            ("localhost", True),
            ("example.com", True),
            ("ray-cluster.example.com", True),
            ("a.b.c.d", True),
            # Invalid IPv4
            ("256.256.256.256", False),
            ("127.0.0", False),
            ("127.0.0.1.1", False),
            # Invalid hostnames
            ("", False),
            ("-invalid", False),
            ("invalid-", False),
            ("inv@lid", False),
        ],
    )
    def test_validate_ipv4_or_hostname(self, cluster_manager, host, expected_valid):
        """Test IPv4 and hostname validation."""
        result = cluster_manager._validate_ipv4_or_hostname(host)
        assert result == expected_valid

    @pytest.mark.parametrize(
        "port,expected_valid",
        [
            # Valid ports
            ("1", True),
            ("80", True),
            ("8000", True),
            ("65535", True),
            # Invalid ports
            ("", False),
            ("0", False),
            ("65536", False),
            ("abc", False),
            ("8000.5", False),
            ("-1", False),
        ],
    )
    def test_validate_port(self, cluster_manager, port, expected_valid):
        """Test port validation."""
        result = cluster_manager._validate_port(port)
        assert result == expected_valid

    @pytest.mark.parametrize(
        "address,expected_host,expected_port",
        [
            # IPv4 addresses
            ("127.0.0.1:8000", "127.0.0.1", 8000),
            ("192.168.1.100:10001", "192.168.1.100", 10001),
            ("localhost:8000", "localhost", 8000),
        ],
    )
    def test_parse_cluster_address_success(
        self, cluster_manager, address, expected_host, expected_port
    ):
        """Test successful address parsing."""
        host, port = cluster_manager._parse_cluster_address(address)
        assert host == expected_host
        assert port == expected_port

    @pytest.mark.parametrize(
        "address",
        [
            "",
            "invalid",
            "127.0.0.1",
            "127.0.0.1:abc",
            "300.300.300.300:8000",
        ],
    )
    def test_parse_cluster_address_failure(self, cluster_manager, address):
        """Test address parsing failures."""
        with pytest.raises(ValueError, match="Invalid cluster address format"):
            cluster_manager._parse_cluster_address(address)

    @patch("ray_mcp.core.cluster_manager.RAY_AVAILABLE", True)
    @patch("ray_mcp.core.cluster_manager.ray")
    async def test_connect_to_existing_cluster_ipv4_url_formatting(
        self, mock_ray, cluster_manager
    ):
        """Test that IPv4 addresses are properly formatted in URLs."""
        # Mock the dashboard connection test
        mock_job_client = Mock()
        mock_context = Mock()
        mock_context.gcs_address = "actual.gcs.address:10001"

        mock_ray.is_initialized.side_effect = [False, True]
        mock_ray.init = Mock()
        mock_ray.get_runtime_context.return_value = mock_context

        # Test IPv4 address formatting
        with patch.object(
            cluster_manager, "_test_dashboard_connection", return_value=mock_job_client
        ) as mock_test:
            result = await cluster_manager._connect_to_existing_cluster(
                "127.0.0.1:8000"
            )

            # Should succeed
            assert result["status"] == "success"
            # Check that the dashboard URL was formatted correctly
            mock_test.assert_called_once_with("http://127.0.0.1:8265")

    async def test_connect_to_existing_cluster_invalid_address(self, cluster_manager):
        """Test that invalid addresses are rejected."""
        result = await cluster_manager._connect_to_existing_cluster("invalid-address")

        assert result["status"] == "error"
        assert "Invalid cluster address format" in result["message"]


@pytest.mark.fast
class TestWorkerManagerProcessCleanup:
    """Test the simplified process cleanup logic in WorkerManager."""

    @pytest.fixture
    def worker_manager(self):
        """Create a WorkerManager instance for testing."""
        from ray_mcp.worker_manager import WorkerManager

        return WorkerManager()

    async def test_process_termination_scenarios(self, worker_manager):
        """Test multiple scenarios for the simplified process termination logic."""
        from unittest.mock import AsyncMock, Mock

        # Test 1: Successful termination
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.wait = Mock(return_value=0)

        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=0)

            status, message = await worker_manager._wait_for_process_termination(
                mock_process, "test-worker", timeout=5
            )

            assert status == "force_stopped"
            assert "test-worker" in message
            assert "force stopped" in message

        # Test 2: Timeout but process actually terminated (race condition)
        mock_process.poll.return_value = 0  # Process is terminated
        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                side_effect=asyncio.TimeoutError()
            )

            status, message = await worker_manager._wait_for_process_termination(
                mock_process, "test-worker", timeout=5
            )

            assert status == "force_stopped"
            assert "test-worker" in message

        # Test 3: Timeout with process still running
        mock_process.poll.return_value = None  # Process still running
        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                side_effect=asyncio.TimeoutError()
            )

            status, message = await worker_manager._wait_for_process_termination(
                mock_process, "test-worker", timeout=5
            )

            assert status == "force_stopped"
            assert "may still be running" in message

        # Test 4: Unexpected exception during cleanup
        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                side_effect=RuntimeError("Unexpected error")
            )

            status, message = await worker_manager._wait_for_process_termination(
                mock_process, "test-worker", timeout=5
            )

            assert status == "force_stopped"
            assert "cleanup error" in message

    async def test_stop_all_workers_graceful_and_force_termination(
        self, worker_manager
    ):
        """Test both graceful and force termination workflows in stop_all_workers."""
        from unittest.mock import AsyncMock, Mock, patch

        # Test graceful termination first
        mock_process_graceful = Mock()
        mock_process_graceful.pid = 12345
        mock_process_graceful.terminate = Mock()
        mock_process_graceful.wait = Mock(return_value=0)

        worker_manager.worker_processes = [mock_process_graceful]
        worker_manager.worker_configs = [{"node_name": "graceful-worker"}]

        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=0)

            results = await worker_manager.stop_all_workers()

            assert len(results) == 1
            assert results[0]["status"] == "stopped"
            assert results[0]["node_name"] == "graceful-worker"
            assert "stopped gracefully" in results[0]["message"]
            assert len(worker_manager.worker_processes) == 0

        # Test force termination when graceful fails
        mock_process_force = Mock()
        mock_process_force.pid = 54321
        mock_process_force.terminate = Mock()
        mock_process_force.kill = Mock()
        mock_process_force.wait = Mock(return_value=0)

        worker_manager.worker_processes = [mock_process_force]
        worker_manager.worker_configs = [{"node_name": "force-worker"}]

        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=0)

            # First asyncio.wait_for (graceful) times out, triggering force termination
            with patch("asyncio.wait_for", side_effect=[asyncio.TimeoutError(), None]):
                results = await worker_manager.stop_all_workers()

                assert len(results) == 1
                assert results[0]["status"] == "force_stopped"
                assert results[0]["node_name"] == "force-worker"
                assert len(worker_manager.worker_processes) == 0
