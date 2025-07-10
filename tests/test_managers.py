#!/usr/bin/env python3
"""Tests for Ray MCP manager components.

This file consolidates tests for all manager components, focusing on:
- Manager behavior patterns and contracts
- Cross-manager integration and state consistency  
- Error handling and recovery scenarios
- Resource management workflows

Focus: Behavior-driven tests for manager functionality.
"""

import asyncio
import threading
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ray_mcp.managers.cluster_manager import RayClusterManager
from ray_mcp.managers.job_manager import RayJobManager
from ray_mcp.managers.log_manager import RayLogManager
from ray_mcp.managers.port_manager import RayPortManager
from ray_mcp.managers.state_manager import RayStateManager
from ray_mcp.managers.unified_manager import RayUnifiedManager


@pytest.mark.fast
class TestManagerContracts:
    """Test that managers fulfill their expected contracts and interfaces."""

    def test_unified_manager_provides_expected_interface(self):
        """Test that unified manager provides all expected methods and properties."""
        manager = RayUnifiedManager()

        # Test component access
        assert manager.get_state_manager() is not None
        assert manager.get_cluster_manager() is not None
        assert manager.get_job_manager() is not None
        assert manager.get_log_manager() is not None
        assert manager.get_port_manager() is not None

        # Test properties are available
        expected_properties = [
            "is_initialized",
            "cluster_address",
            "dashboard_url",
            "job_client",
        ]
        for prop in expected_properties:
            assert hasattr(manager, prop), f"Missing property: {prop}"

        # Test core methods are available
        expected_methods = [
            "init_cluster",
            "stop_cluster",
            "inspect_ray_cluster",
            "submit_ray_job",
            "list_ray_jobs",
            "cancel_ray_job",
            "inspect_ray_job",
            "retrieve_logs",
        ]
        for method in expected_methods:
            assert hasattr(manager, method), f"Missing method: {method}"
            assert callable(getattr(manager, method)), f"Method {method} not callable"

    @pytest.mark.asyncio
    async def test_manager_delegation_contracts(self):
        """Test that unified manager properly delegates to specialized managers."""
        manager = RayUnifiedManager()

        # Mock underlying managers
        mock_cluster_manager = Mock()
        mock_job_manager = Mock()
        mock_log_manager = Mock()

        mock_cluster_manager.init_cluster = AsyncMock(
            return_value={"status": "success"}
        )
        mock_job_manager.submit_job = AsyncMock(
            return_value={"status": "success", "job_id": "job_123"}
        )
        mock_log_manager.retrieve_logs = AsyncMock(
            return_value={"status": "success", "logs": "content"}
        )

        manager._cluster_manager = mock_cluster_manager
        manager._job_manager = mock_job_manager
        manager._log_manager = mock_log_manager

        # Test delegation to cluster manager
        await manager.init_cluster(num_cpus=4)
        mock_cluster_manager.init_cluster.assert_called_once()

        # Test delegation to job manager
        result = await manager.submit_ray_job("python script.py")
        assert result["job_id"] == "job_123"
        mock_job_manager.submit_job.assert_called_once()

        # Test delegation to log manager
        result = await manager.retrieve_logs("job_123", log_type="job", num_lines=50)
        assert result["logs"] == "content"
        mock_log_manager.retrieve_logs.assert_called_once()

    def test_state_manager_contract_compliance(self):
        """Test that state manager fulfills expected interface contract."""
        manager = RayStateManager()

        # Test initial state structure
        state = manager.get_state()
        required_fields = [
            "initialized",
            "cluster_address",
            "dashboard_url",
            "job_client",
        ]
        for field in required_fields:
            assert field in state

        # Test state operations
        manager.update_state(test_field="value")
        assert manager.get_state()["test_field"] == "value"

        manager.reset_state()
        assert "test_field" not in manager.get_state()

        # Test initialization check
        assert isinstance(manager.is_initialized(), bool)

    def test_base_manager_pattern_compliance(self):
        """Test that managers follow expected base patterns."""
        from ray_mcp.foundation.base_managers import BaseManager, ResourceManager

        state_manager = Mock()

        # Test BaseManager pattern
        class TestManager(BaseManager):
            pass

        manager = TestManager(state_manager)
        assert hasattr(manager, "_log_info")
        assert hasattr(manager, "_format_success_response")
        assert hasattr(manager, "_format_error_response")

        # Test ResourceManager pattern
        class TestResourceManager(ResourceManager):
            pass

        resource_manager = TestResourceManager(
            state_manager, enable_ray=True, enable_kubernetes=False, enable_cloud=False
        )
        assert hasattr(resource_manager, "_ensure_ray_available")
        assert hasattr(resource_manager, "_ensure_initialized")


@pytest.mark.fast
class TestManagerIntegration:
    """Test integration patterns between managers."""

    def test_state_manager_shared_across_components(self):
        """Test that state manager is properly shared across all components."""
        unified_manager = RayUnifiedManager()

        # All components should reference the same state manager
        state_manager = unified_manager._state_manager
        cluster_manager = unified_manager._cluster_manager
        job_manager = unified_manager._job_manager
        log_manager = unified_manager._log_manager

        assert cluster_manager.state_manager is state_manager
        assert job_manager.state_manager is state_manager
        assert log_manager.state_manager is state_manager

    @pytest.mark.asyncio
    async def test_cluster_job_workflow_integration(self):
        """Test integrated workflow between cluster and job managers."""
        unified_manager = RayUnifiedManager()

        # Mock managers for integration testing
        mock_cluster_manager = Mock()
        mock_job_manager = Mock()

        mock_cluster_manager.init_cluster = AsyncMock(
            return_value={"status": "success", "cluster_address": "127.0.0.1:10001"}
        )
        mock_job_manager.submit_job = AsyncMock(
            return_value={"status": "success", "job_id": "job_123"}
        )
        mock_job_manager.list_jobs = AsyncMock(
            return_value={"status": "success", "jobs": [{"job_id": "job_123"}]}
        )

        unified_manager._cluster_manager = mock_cluster_manager
        unified_manager._job_manager = mock_job_manager

        # Test workflow: cluster init -> job submit -> job list
        cluster_result = await unified_manager.init_cluster(num_cpus=2)
        assert cluster_result["status"] == "success"

        job_result = await unified_manager.submit_ray_job("python script.py")
        assert job_result["job_id"] == "job_123"

        jobs_result = await unified_manager.list_ray_jobs()
        assert len(jobs_result["jobs"]) > 0

    def test_port_manager_cluster_manager_integration(self):
        """Test integration between port and cluster managers."""
        state_manager = RayStateManager()
        port_manager = RayPortManager(state_manager)
        cluster_manager = RayClusterManager(state_manager, port_manager)

        # Test that cluster manager has port manager reference
        assert cluster_manager._port_manager is port_manager
        assert cluster_manager.state_manager is state_manager

    @pytest.mark.asyncio
    async def test_cross_manager_state_consistency(self):
        """Test that state remains consistent across manager operations."""
        unified_manager = RayUnifiedManager()

        # Mock state updates
        mock_state = {
            "initialized": True,
            "cluster_address": "127.0.0.1:10001",
            "dashboard_url": "http://127.0.0.1:8265",
        }

        with patch.object(
            unified_manager._state_manager, "get_state", return_value=mock_state
        ):
            with patch.object(
                unified_manager._state_manager, "is_initialized", return_value=True
            ):
                # Test that all managers see consistent state
                assert unified_manager.is_initialized is True
                assert unified_manager.cluster_address == "127.0.0.1:10001"
                assert unified_manager.dashboard_url == "http://127.0.0.1:8265"


@pytest.mark.fast
class TestManagerErrorHandling:
    """Test error handling patterns across managers."""

    @pytest.mark.asyncio
    async def test_unified_manager_error_propagation(self):
        """Test that errors from specialized managers propagate correctly."""
        manager = RayUnifiedManager()

        # Test cluster manager error propagation
        mock_cluster_manager = Mock()
        mock_cluster_manager.init_cluster = AsyncMock(
            side_effect=Exception("Cluster initialization failed")
        )
        manager._cluster_manager = mock_cluster_manager

        with pytest.raises(Exception, match="Cluster initialization failed"):
            await manager.init_cluster()

        # Test job manager error propagation
        mock_job_manager = Mock()
        mock_job_manager.submit_job = AsyncMock(
            return_value={"status": "error", "message": "Job submission failed"}
        )
        manager._job_manager = mock_job_manager

        result = await manager.submit_ray_job("python script.py")
        assert result["status"] == "error"
        assert "Job submission failed" in result["message"]

    def test_state_manager_validation_error_recovery(self):
        """Test that state manager can recover from validation errors."""
        with patch("ray_mcp.managers.state_manager.RAY_AVAILABLE", True):
            with patch("ray_mcp.managers.state_manager.ray") as mock_ray:
                # First validation fails
                mock_ray.is_initialized.side_effect = Exception("Validation error")

                manager = RayStateManager(validation_interval=0.01)
                manager.update_state(cluster_address="127.0.0.1:10001")

                time.sleep(0.02)
                state1 = manager.get_state()
                assert not state1["initialized"]

                # Reset for successful validation
                mock_ray.reset_mock()
                mock_ray.is_initialized.side_effect = None
                mock_ray.is_initialized.return_value = True
                mock_context = Mock()
                mock_context.get_node_id.return_value = "node_123"
                mock_ray.get_runtime_context.return_value = mock_context

                # Reset validation timestamp
                manager._state["last_validated"] = 0.0

                time.sleep(0.02)
                state2 = manager.get_state()
                assert state2["initialized"]

    @pytest.mark.asyncio
    async def test_resource_manager_error_patterns(self):
        """Test common error patterns in resource managers."""
        from ray_mcp.foundation.base_managers import ResourceManager

        state_manager = Mock()
        state_manager.is_initialized.return_value = False

        class TestResourceManager(ResourceManager):
            pass

        manager = TestResourceManager(
            state_manager, enable_ray=True, enable_kubernetes=False, enable_cloud=False
        )

        # Test Ray unavailable error
        with patch.object(manager, "_RAY_AVAILABLE", False):
            with pytest.raises(RuntimeError, match="Ray is not available"):
                manager._ensure_ray_available()

        # Test Ray not initialized error
        with pytest.raises(RuntimeError, match="Ray is not initialized"):
            manager._ensure_initialized()

    def test_validation_error_handling_patterns(self):
        """Test validation error handling patterns across managers."""
        from ray_mcp.foundation.base_managers import BaseManager

        state_manager = Mock()

        class TestManager(BaseManager):
            pass

        manager = TestManager(state_manager)

        # Test job ID validation
        assert manager._validate_job_id("valid_job_id", "test") is None

        error_response = manager._validate_job_id("", "test")
        assert error_response is not None
        assert error_response["status"] == "error"
        assert "job_id" in error_response["message"]


@pytest.mark.fast
class TestManagerResourceHandling:
    """Test resource management patterns across managers."""

    def test_state_manager_thread_safety(self):
        """Test that state manager operations are thread-safe."""
        manager = RayStateManager()
        results = []

        def update_state(thread_id):
            for i in range(10):
                manager.update_state(**{f"thread_{thread_id}_value_{i}": i})
                results.append((thread_id, i))

        # Create and run multiple threads
        threads = []
        for thread_id in range(3):
            thread = threading.Thread(target=update_state, args=(thread_id,))
            threads.append(thread)

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Verify all updates were applied safely
        state = manager.get_state()
        assert len(results) == 30  # 3 threads × 10 updates each

        # Check that all thread values are in state
        for thread_id in range(3):
            for i in range(10):
                key = f"thread_{thread_id}_value_{i}"
                assert key in state
                assert state[key] == i

    @pytest.mark.asyncio
    async def test_cluster_manager_connection_type_handling(self):
        """Test cluster manager handles different connection types correctly."""
        from ray_mcp.managers.port_manager import RayPortManager

        state_manager = RayStateManager()
        port_manager = RayPortManager(state_manager)
        cluster_manager = RayClusterManager(state_manager, port_manager)

        # Mock Ray
        mock_ray = Mock()
        mock_ray.is_initialized.return_value = True
        mock_ray.shutdown = Mock()
        cluster_manager._ray = mock_ray
        cluster_manager._RAY_AVAILABLE = True

        # Test existing cluster disconnection
        cluster_manager.state_manager.update_state(connection_type="existing")
        result = await cluster_manager.stop_cluster()
        assert result["action"] == "disconnected"
        mock_ray.shutdown.assert_called_once()

        # Test new cluster stop
        mock_ray.reset_mock()
        cluster_manager.state_manager.update_state(connection_type="new")

        with patch("asyncio.wait_for") as mock_wait_for:
            mock_wait_for.return_value = None
            result = await cluster_manager.stop_cluster()

        assert result["action"] == "stopped"
        mock_ray.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_job_manager_client_lifecycle(self):
        """Test job manager handles client lifecycle correctly."""
        state_manager = Mock()
        state_manager.is_initialized.return_value = True
        state_manager.get_state.return_value = {
            "dashboard_url": "http://127.0.0.1:8265",
            "job_client": None,
        }

        job_manager = RayJobManager(state_manager)

        # Mock Ray availability and client
        mock_client = Mock()
        mock_client.list_jobs.return_value = []
        mock_client_class = Mock(return_value=mock_client)

        job_manager._RAY_AVAILABLE = True
        job_manager._JobSubmissionClient = mock_client_class

        # Test client creation
        client = await job_manager._get_or_create_job_client("test_operation")
        assert client == mock_client
        mock_client_class.assert_called_with("http://127.0.0.1:8265")

    def test_address_validation_patterns(self):
        """Test address validation patterns across managers."""
        from ray_mcp.managers.port_manager import RayPortManager

        state_manager = RayStateManager()
        port_manager = RayPortManager(state_manager)
        cluster_manager = RayClusterManager(state_manager, port_manager)

        # Test valid addresses
        valid_addresses = [
            "127.0.0.1:8000",
            "192.168.1.100:10001",
            "localhost:8000",
            "example.com:8000",
        ]

        for address in valid_addresses:
            assert cluster_manager._validate_cluster_address(address) is True

        # Test invalid addresses
        invalid_addresses = [
            "",
            "invalid",
            "127.0.0.1",  # Missing port
            "127.0.0.1:abc",  # Invalid port
            "300.300.300.300:8000",  # Invalid IP
        ]

        for address in invalid_addresses:
            assert cluster_manager._validate_cluster_address(address) is False


@pytest.mark.fast
class TestManagerWorkflows:
    """Test complex workflows that span multiple managers."""

    @pytest.mark.asyncio
    async def test_complete_cluster_job_workflow(self):
        """Test complete workflow from cluster creation to job execution."""
        manager = RayUnifiedManager()

        # Mock all underlying operations
        manager._cluster_manager = Mock()
        manager._job_manager = Mock()
        manager._log_manager = Mock()

        manager._cluster_manager.init_cluster = AsyncMock(
            return_value={"status": "success", "cluster_address": "127.0.0.1:10001"}
        )
        manager._job_manager.submit_job = AsyncMock(
            return_value={"status": "success", "job_id": "job_123"}
        )
        manager._job_manager.list_jobs = AsyncMock(
            return_value={
                "status": "success",
                "jobs": [{"job_id": "job_123", "status": "RUNNING"}],
            }
        )
        manager._log_manager.retrieve_logs = AsyncMock(
            return_value={"status": "success", "logs": "Job executing..."}
        )
        manager._job_manager.cancel_job = AsyncMock(
            return_value={"status": "success", "cancelled": True}
        )
        manager._cluster_manager.stop_cluster = AsyncMock(
            return_value={"status": "success", "action": "stopped"}
        )

        # Execute complete workflow
        # 1. Initialize cluster
        init_result = await manager.init_cluster(num_cpus=2)
        assert init_result["status"] == "success"

        # 2. Submit job
        job_result = await manager.submit_ray_job("python script.py")
        assert job_result["job_id"] == "job_123"

        # 3. List jobs to verify submission
        list_result = await manager.list_ray_jobs()
        assert len(list_result["jobs"]) > 0

        # 4. Retrieve logs
        logs_result = await manager.retrieve_logs("job_123", log_type="job")
        assert "Job executing" in logs_result["logs"]

        # 5. Cancel job
        cancel_result = await manager.cancel_ray_job("job_123")
        assert cancel_result["cancelled"] is True

        # 6. Stop cluster
        stop_result = await manager.stop_cluster()
        assert stop_result["action"] == "stopped"

    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self):
        """Test workflow recovery from various error conditions."""
        manager = RayUnifiedManager()

        # Simulate initial failure followed by success
        mock_cluster_manager = Mock()

        # First call fails, second succeeds
        mock_cluster_manager.init_cluster = AsyncMock(
            side_effect=[
                Exception("Initial failure"),
                {"status": "success", "cluster_address": "127.0.0.1:10001"},
            ]
        )

        manager._cluster_manager = mock_cluster_manager

        # First attempt should fail
        with pytest.raises(Exception, match="Initial failure"):
            await manager.init_cluster(num_cpus=2)

        # Second attempt should succeed
        result = await manager.init_cluster(num_cpus=2)
        assert result["status"] == "success"

        # Verify both calls were made
        assert mock_cluster_manager.init_cluster.call_count == 2

    def test_state_consistency_across_workflow(self):
        """Test that state remains consistent throughout complex workflows."""
        manager = RayUnifiedManager()

        # Simulate state changes through workflow
        initial_state = manager._state_manager.get_state()
        assert not initial_state["initialized"]

        # Simulate cluster initialization
        manager._state_manager.update_state(
            initialized=True,
            cluster_address="127.0.0.1:10001",
            dashboard_url="http://127.0.0.1:8265",
        )

        cluster_state = manager._state_manager.get_state()
        assert cluster_state["initialized"]
        assert cluster_state["cluster_address"] == "127.0.0.1:10001"

        # Simulate cluster shutdown
        manager._state_manager.reset_state()

        final_state = manager._state_manager.get_state()
        assert not final_state["initialized"]
        assert final_state["cluster_address"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
