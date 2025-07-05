"""Unit tests for RayClusterManager component.

Tests focus on cluster management behavior with 100% mocking.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ray_mcp.core.unified_manager import RayUnifiedManager


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


@pytest.mark.fast
class TestRayClusterManagerConnectionType:
    """Test connection type handling and stop_cluster behavior."""

    @pytest.fixture
    def cluster_manager(self):
        """Create a RayClusterManager instance for testing."""
        from ray_mcp.core.cluster_manager import RayClusterManager
        from ray_mcp.core.port_manager import RayPortManager
        from ray_mcp.core.state_manager import RayStateManager

        state_manager = RayStateManager()
        port_manager = RayPortManager()
        return RayClusterManager(state_manager, port_manager)

    @patch("ray_mcp.core.cluster_manager.RAY_AVAILABLE", True)
    @patch("ray_mcp.core.cluster_manager.ray")
    async def test_stop_cluster_connection_type_routing(
        self, mock_ray, cluster_manager
    ):
        """Test stop_cluster routes to appropriate cleanup based on connection type."""
        mock_ray.is_initialized.return_value = True
        mock_ray.shutdown = Mock()

        # Test 1: Existing cluster - should disconnect only
        cluster_manager.state_manager.update_state(connection_type="existing")
        result = await cluster_manager.stop_cluster()
        assert result["status"] == "success"
        assert result["action"] == "disconnected"
        mock_ray.shutdown.assert_called_once()

        # Test 2: New cluster - should do full cleanup
        mock_ray.reset_mock()
        mock_worker_manager = Mock()
        mock_worker_manager.worker_processes = [Mock()]
        mock_worker_manager.stop_all_workers = AsyncMock(
            return_value=[{"status": "stopped"}]
        )
        cluster_manager._worker_manager = mock_worker_manager
        cluster_manager._head_node_process = Mock()

        cluster_manager.state_manager.update_state(connection_type="new")
        result = await cluster_manager.stop_cluster()
        assert result["status"] == "success"
        assert result["action"] == "stopped"
        mock_worker_manager.stop_all_workers.assert_called_once()
        mock_ray.shutdown.assert_called_once()
        assert cluster_manager._head_node_process is None

        # Test 3: No connection type (backward compatibility) - should default to local cleanup
        mock_ray.reset_mock()
        mock_worker_manager.reset_mock()
        cluster_manager.state_manager.update_state(connection_type=None)
        await cluster_manager.stop_cluster()
        mock_worker_manager.stop_all_workers.assert_called_once()

    @patch("ray_mcp.core.cluster_manager.RAY_AVAILABLE", True)
    @patch("ray_mcp.core.cluster_manager.ray")
    async def test_connection_type_tracking_during_init(
        self, mock_ray, cluster_manager
    ):
        """Test that connection type is tracked correctly during cluster initialization."""
        # Test 1: Starting new cluster sets connection_type to "new"
        mock_ray.is_initialized.return_value = False
        mock_ray.init = Mock()
        mock_ray.get_runtime_context.return_value = Mock(gcs_address="127.0.0.1:10001")
        cluster_manager._port_manager.find_free_port = AsyncMock(return_value=8265)

        # Mock subprocess for head node - configure the Mock properly
        with patch("ray_mcp.core.cluster_manager.subprocess") as mock_subprocess:
            mock_process = Mock()
            mock_process.communicate.return_value = (
                "stdout output",
                "",
            )  # (stdout, stderr)
            mock_process.returncode = 0  # Success
            mock_subprocess.Popen.return_value = mock_process

            # Mock the _wait_for_head_node_ready method to avoid dashboard connection
            with patch.object(
                cluster_manager, "_wait_for_head_node_ready", return_value=None
            ):
                await cluster_manager.init_cluster(num_cpus=2, worker_nodes=[])

        state = cluster_manager.state_manager.get_state()
        assert state["connection_type"] == "new"

        # Test 2: Connecting to existing cluster sets connection_type to "existing"
        mock_ray.reset_mock()
        mock_ray.is_initialized.return_value = False
        cluster_manager.state_manager.reset_state()

        # Mock _connect_to_existing_cluster and simulate state update
        def mock_connect_to_existing(address):
            # Simulate what the real method does - update state with connection_type
            cluster_manager.state_manager.update_state(
                initialized=True, cluster_address=address, connection_type="existing"
            )
            return {"status": "success", "connection_type": "existing"}

        with patch.object(
            cluster_manager,
            "_connect_to_existing_cluster",
            side_effect=mock_connect_to_existing,
        ):
            result = await cluster_manager.init_cluster(address="127.0.0.1:10001")

        state = cluster_manager.state_manager.get_state()
        assert state["connection_type"] == "existing"


@pytest.mark.fast
class TestRayClusterManagerAddressParsing:
    """Test address parsing and validation functionality."""

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
        """Test cluster address validation."""
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
        """Test successful cluster address parsing."""
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
        """Test cluster address parsing failure."""
        with pytest.raises(ValueError):
            cluster_manager._parse_cluster_address(address)

    @patch("ray_mcp.core.cluster_manager.RAY_AVAILABLE", True)
    @patch("ray_mcp.core.cluster_manager.ray")
    async def test_connect_to_existing_cluster_ipv4_url_formatting(
        self, mock_ray, cluster_manager
    ):
        """Test that connect_to_existing_cluster correctly formats IPv4 URLs."""
        mock_ray.is_initialized.return_value = False
        mock_ray.init = Mock()
        mock_ray.get_runtime_context.return_value = Mock(gcs_address="127.0.0.1:10001")

        mock_job_client = Mock()

        with patch.object(
            cluster_manager, "_test_dashboard_connection", return_value=mock_job_client
        ):
            result = await cluster_manager._connect_to_existing_cluster(
                "127.0.0.1:10001"
            )

        assert result["status"] == "success"

        # Verify the state was updated with proper URLs
        state = cluster_manager.state_manager.get_state()
        assert state["cluster_address"] == "127.0.0.1:10001"
        assert state["dashboard_url"] == "http://127.0.0.1:8265"

    async def test_connect_to_existing_cluster_invalid_address(self, cluster_manager):
        """Test connecting to existing cluster with invalid address."""
        result = await cluster_manager._connect_to_existing_cluster("invalid:address")
        assert result["status"] == "error"
        assert "Invalid cluster address" in result["message"]
