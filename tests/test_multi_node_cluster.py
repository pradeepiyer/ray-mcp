#!/usr/bin/env python3
"""Tests for multi-node Ray cluster functionality."""

print("[DEBUG] Loading test_multi_node_cluster.py")

import asyncio
import json
import pytest
from unittest.mock import Mock, patch, AsyncMock
import subprocess

print("[DEBUG] Imports completed")

from ray_mcp.ray_manager import RayManager
from ray_mcp.worker_manager import WorkerManager

print("[DEBUG] Ray imports completed")


@pytest.mark.fast
class TestMultiNodeCluster:
    """Test cases for multi-node cluster functionality."""
    
    print("[DEBUG] TestMultiNodeCluster class defined")

    @pytest.fixture
    def ray_manager(self):
        """Create a RayManager instance for testing."""
        print("[DEBUG] Creating ray_manager fixture")
        return RayManager()

    @pytest.fixture
    def worker_manager(self):
        """Create a WorkerManager instance for testing."""
        print("[DEBUG] Creating worker_manager fixture")
        return WorkerManager()

    @pytest.mark.asyncio
    async def test_start_cluster_with_worker_nodes(self):
        """Test starting a cluster with worker nodes."""
        worker_configs = [
            {"num_cpus": 2, "num_gpus": 0},
            {"num_cpus": 2, "num_gpus": 0}
        ]
        expected_worker_count = len(worker_configs)
        expected_total_nodes = 1 + expected_worker_count  # 1 head + workers
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray.is_initialized', return_value=True):
                with patch('ray_mcp.ray_manager.ray.init') as mock_init:
                    with patch('ray_mcp.ray_manager.ray.get_runtime_context') as mock_get_runtime_context:
                        mock_context = Mock()
                        mock_context.address_info = {"address": "ray://127.0.0.1:10001"}
                        mock_context.dashboard_url = "http://127.0.0.1:8265"
                        mock_context.session_name = "test_session"
                        mock_init.return_value = mock_context
                        mock_get_runtime_context.return_value.get_node_id.return_value = "test_node"
                        ray_manager = RayManager()
                        with patch.object(ray_manager._worker_manager, 'start_worker_nodes', new_callable=AsyncMock) as mock_start_workers:
                            mock_start_workers.return_value = [
                                {
                                    "status": "started",
                                    "node_name": f"worker-{i}",
                                    "message": f"Worker node 'worker-{i}' started successfully",
                                    "process_id": 1000 + i,
                                    "config": config
                                }
                                for i, config in enumerate(worker_configs)
                            ]
                            result = await ray_manager.start_cluster(
                                num_cpus=4,
                                worker_nodes=worker_configs,
                                head_node_port=10001,
                                dashboard_port=8265
                            )
                            print("[DEBUG] start_cluster returned")
                            # Verify result
                            assert result["status"] == "started"
                            assert result["total_nodes"] == expected_total_nodes
                            assert "worker_nodes" in result
                            assert len(result["worker_nodes"]) == expected_worker_count
                            # Verify worker manager was called
                            mock_start_workers.assert_called_once_with(
                                worker_configs,
                                "ray://127.0.0.1:10001"
                            )
        print("[DEBUG] test_start_cluster_with_worker_nodes completed")

    @pytest.mark.asyncio
    async def test_start_cluster_without_worker_nodes(self):
        """Test starting a cluster without worker nodes (backward compatibility)."""
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray.is_initialized', return_value=True):
                with patch('ray_mcp.ray_manager.ray.init') as mock_init:
                    with patch('ray_mcp.ray_manager.ray.get_runtime_context') as mock_get_runtime_context:
                        mock_context = Mock()
                        mock_context.address_info = {"address": "ray://127.0.0.1:10001"}
                        mock_context.dashboard_url = "http://127.0.0.1:8265"
                        mock_context.session_name = "test_session"
                        mock_init.return_value = mock_context
                        mock_get_runtime_context.return_value.get_node_id.return_value = "test_node"
                        ray_manager = RayManager()
                        result = await ray_manager.start_cluster(num_cpus=4)
                        assert result["status"] == "started"
                        assert result["total_nodes"] == 1  # Only head node
                        assert "worker_nodes" in result
                        assert len(result["worker_nodes"]) == 0  # No workers

    @pytest.mark.asyncio
    async def test_stop_cluster_with_workers(self):
        """Test stopping a cluster with worker nodes."""
        mock_worker_results = [
            {
                "status": "stopped",
                "node_name": "worker-1",
                "message": "Worker node 'worker-1' stopped gracefully"
            }
        ]
        expected_worker_count = len(mock_worker_results)
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray.is_initialized', return_value=True):
                with patch('ray_mcp.ray_manager.ray.shutdown') as mock_shutdown:
                    ray_manager = RayManager()
                    with patch.object(ray_manager._worker_manager, 'stop_all_workers', new_callable=AsyncMock) as mock_stop_workers:
                        mock_stop_workers.return_value = mock_worker_results
                        result = await ray_manager.stop_cluster()
                        assert result["status"] == "stopped"
                        assert "worker_nodes" in result
                        assert len(result["worker_nodes"]) == expected_worker_count
                        mock_stop_workers.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_worker_status(self):
        """Test getting worker node status."""
        mock_worker_status = [
            {
                "status": "running",
                "node_name": "worker-1",
                "process_id": 12345,
                "message": "Worker node 'worker-1' is running"
            }
        ]
        expected_total_workers = len(mock_worker_status)
        expected_running_workers = len([w for w in mock_worker_status if w["status"] == "running"])
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray.is_initialized', return_value=True):
                ray_manager = RayManager()
                ray_manager._is_initialized = True
                with patch.object(ray_manager._worker_manager, 'get_worker_status') as mock_get_status:
                    mock_get_status.return_value = mock_worker_status
                    result = await ray_manager.get_worker_status()
                    assert result["status"] == "success"
                    assert "worker_nodes" in result
                    assert result["total_workers"] == expected_total_workers
                    assert result["running_workers"] == expected_running_workers

    @pytest.mark.asyncio
    async def test_cluster_status_with_workers(self):
        """Test getting cluster status with worker information."""
        mock_ray_nodes = [{"NodeID": "node1", "Alive": True}, {"NodeID": "node2", "Alive": True}]
        mock_worker_status = [
            {
                "status": "running",
                "node_name": "worker-1",
                "process_id": 12345
            }
        ]
        expected_total_nodes = len(mock_ray_nodes)
        expected_alive_nodes = len([n for n in mock_ray_nodes if n["Alive"]])
        expected_total_worker_nodes = len(mock_worker_status)
        
        with patch('ray_mcp.ray_manager.RAY_AVAILABLE', True):
            with patch('ray_mcp.ray_manager.ray.is_initialized', return_value=True):
                with patch('ray_mcp.ray_manager.ray.cluster_resources', return_value={"CPU": 8, "memory": 16000000000}):
                    with patch('ray_mcp.ray_manager.ray.available_resources', return_value={"CPU": 4, "memory": 8000000000}):
                        with patch('ray_mcp.ray_manager.ray.nodes', return_value=mock_ray_nodes):
                            ray_manager = RayManager()
                            ray_manager._is_initialized = True
                            ray_manager._cluster_address = "ray://127.0.0.1:10001"
                            with patch.object(ray_manager._worker_manager, 'get_worker_status') as mock_get_status:
                                mock_get_status.return_value = mock_worker_status
                                result = await ray_manager.get_cluster_status()
                                assert result["status"] == "running"
                                assert "worker_nodes" in result
                                assert result["total_worker_nodes"] == expected_total_worker_nodes
                                assert result["nodes"] == expected_total_nodes
                                assert result["alive_nodes"] == expected_alive_nodes


@pytest.mark.fast
class TestWorkerManager:
    """Test cases for WorkerManager functionality."""

    @pytest.fixture
    def worker_manager(self):
        return WorkerManager()

    def test_worker_manager_initialization(self, worker_manager):
        """Test WorkerManager initialization."""
        assert worker_manager.worker_processes == []
        assert worker_manager.worker_configs == []

    def test_build_worker_command_basic(self, worker_manager):
        """Test building basic worker command."""
        config = {"num_cpus": 4}
        head_node_address = "ray://127.0.0.1:10001"
        cmd = worker_manager._build_worker_command(config, head_node_address)
        
        assert cmd[0] == "ray"
        assert cmd[1] == "start"
        assert "--address" in cmd
        assert head_node_address in cmd
        assert "--num-cpus" in cmd
        assert "4" in cmd
        assert "--block" in cmd
        assert "--disable-usage-stats" in cmd

    def test_build_worker_command_full_config(self, worker_manager):
        """Test building worker command with full configuration."""
        config = {
            "num_cpus": 4,
            "num_gpus": 0,
            "object_store_memory": 1000000000,
            "node_name": "test-worker",
            "resources": {"custom_resource": 2}
        }
        head_node_address = "ray://127.0.0.1:10001"
        cmd = worker_manager._build_worker_command(config, head_node_address)
        
        assert cmd[0] == "ray"
        assert cmd[1] == "start"
        assert "--address" in cmd
        assert head_node_address in cmd
        assert "--num-cpus" in cmd
        assert "4" in cmd
        assert "--num-gpus" in cmd
        assert "0" in cmd
        assert "--object-store-memory" in cmd
        assert "953" in cmd  # Converted to MB
        assert "--node-name" in cmd
        assert "test-worker" in cmd
        assert "--resources" in cmd
        assert "custom_resource=2" in cmd

    def test_build_worker_command_minimal_config(self, worker_manager):
        """Test building worker command with minimal configuration."""
        config = {}
        head_node_address = "ray://127.0.0.1:10001"
        cmd = worker_manager._build_worker_command(config, head_node_address)
        
        # Should have basic command without resource specs
        assert cmd[0] == "ray"
        assert cmd[1] == "start"
        assert "--address" in cmd
        assert head_node_address in cmd
        assert "--block" in cmd
        assert "--disable-usage-stats" in cmd
        
        # Should not have resource specs
        assert "--num-cpus" not in cmd
        assert "--num-gpus" not in cmd
        assert "--object-store-memory" not in cmd
        assert "--node-name" not in cmd
        assert "--resources" not in cmd

    def test_build_worker_command_memory_conversion(self, worker_manager):
        """Test memory conversion from bytes to MB."""
        config = {"object_store_memory": 2147483648}  # 2GB in bytes
        head_node_address = "ray://127.0.0.1:10001"
        cmd = worker_manager._build_worker_command(config, head_node_address)
        
        assert "--object-store-memory" in cmd
        assert "2048" in cmd  # 2GB = 2048MB

    def test_build_worker_command_multiple_resources(self, worker_manager):
        """Test building command with multiple custom resources."""
        config = {
            "resources": {
                "custom_resource": 2,
                "gpu_memory": 8192,
                "fast_network": 1
            }
        }
        head_node_address = "ray://127.0.0.1:10001"
        cmd = worker_manager._build_worker_command(config, head_node_address)
        
        # Check that all resources are included
        resource_args = [arg for i, arg in enumerate(cmd) if arg == "--resources"]
        assert len(resource_args) == 3
        
        # Check specific resource values
        assert "custom_resource=2" in cmd
        assert "gpu_memory=8192" in cmd
        assert "fast_network=1" in cmd

    @pytest.mark.asyncio
    async def test_start_worker_nodes_empty_list(self, worker_manager):
        """Test starting worker nodes with empty configuration list."""
        results = await worker_manager.start_worker_nodes([], "ray://127.0.0.1:10001")
        assert results == []

    @pytest.mark.asyncio
    async def test_start_worker_nodes_single_success(self, worker_manager):
        """Test starting a single worker node successfully."""
        configs = [{"num_cpus": 2, "node_name": "test-worker"}]
        
        with patch.object(worker_manager, '_start_single_worker', new_callable=AsyncMock) as mock_start:
            mock_start.return_value = {
                "status": "started",
                "node_name": "test-worker",
                "message": "Worker node 'test-worker' started successfully",
                "process_id": 12345,
                "config": configs[0]
            }
            
            results = await worker_manager.start_worker_nodes(configs, "ray://127.0.0.1:10001")
            
            assert len(results) == 1
            assert results[0]["status"] == "started"
            assert results[0]["node_name"] == "test-worker"
            assert results[0]["process_id"] == 12345
            mock_start.assert_called_once_with(configs[0], "ray://127.0.0.1:10001", "worker-1")

    @pytest.mark.asyncio
    async def test_start_worker_nodes_multiple_success(self, worker_manager):
        """Test starting multiple worker nodes successfully."""
        configs = [
            {"num_cpus": 2, "node_name": "worker-1"},
            {"num_cpus": 4, "node_name": "worker-2"},
            {"num_cpus": 1, "node_name": "worker-3"}
        ]
        
        with patch.object(worker_manager, '_start_single_worker', new_callable=AsyncMock) as mock_start:
            mock_start.side_effect = [
                {
                    "status": "started",
                    "node_name": "worker-1",
                    "process_id": 12345,
                    "config": configs[0]
                },
                {
                    "status": "started",
                    "node_name": "worker-2",
                    "process_id": 12346,
                    "config": configs[1]
                },
                {
                    "status": "started",
                    "node_name": "worker-3",
                    "process_id": 12347,
                    "config": configs[2]
                }
            ]
            
            results = await worker_manager.start_worker_nodes(configs, "ray://127.0.0.1:10001")
            
            assert len(results) == 3
            for i, result in enumerate(results):
                assert result["status"] == "started"
                assert result["node_name"] == f"worker-{i+1}"
                assert result["process_id"] == 12345 + i
            
            assert mock_start.call_count == 3

    @pytest.mark.asyncio
    async def test_start_worker_nodes_mixed_success_error(self, worker_manager):
        """Test starting worker nodes with mixed success and error results."""
        configs = [
            {"num_cpus": 2, "node_name": "worker-1"},
            {"num_cpus": 4, "node_name": "worker-2"},
            {"num_cpus": 1, "node_name": "worker-3"}
        ]
        
        with patch.object(worker_manager, '_start_single_worker', new_callable=AsyncMock) as mock_start:
            mock_start.side_effect = [
                {
                    "status": "started",
                    "node_name": "worker-1",
                    "process_id": 12345,
                    "config": configs[0]
                },
                Exception("Failed to start worker-2"),
                {
                    "status": "started",
                    "node_name": "worker-3",
                    "process_id": 12347,
                    "config": configs[2]
                }
            ]
            
            results = await worker_manager.start_worker_nodes(configs, "ray://127.0.0.1:10001")
            
            assert len(results) == 3
            assert results[0]["status"] == "started"
            assert results[1]["status"] == "error"
            assert results[1]["message"] == "Failed to start worker node: Failed to start worker-2"
            assert results[2]["status"] == "started"

    @pytest.mark.asyncio
    async def test_start_worker_nodes_all_errors(self, worker_manager):
        """Test starting worker nodes when all fail."""
        configs = [
            {"num_cpus": 2, "node_name": "worker-1"},
            {"num_cpus": 4, "node_name": "worker-2"}
        ]
        
        with patch.object(worker_manager, '_start_single_worker', new_callable=AsyncMock) as mock_start:
            mock_start.side_effect = [
                Exception("Connection failed"),
                Exception("Resource unavailable")
            ]
            
            results = await worker_manager.start_worker_nodes(configs, "ray://127.0.0.1:10001")
            
            assert len(results) == 2
            assert results[0]["status"] == "error"
            assert results[0]["message"] == "Failed to start worker node: Connection failed"
            assert results[1]["status"] == "error"
            assert results[1]["message"] == "Failed to start worker node: Resource unavailable"

    @pytest.mark.asyncio
    async def test_start_worker_nodes_delay_between_starts(self, worker_manager):
        """Test that there's a delay between worker starts."""
        configs = [
            {"num_cpus": 2, "node_name": "worker-1"},
            {"num_cpus": 4, "node_name": "worker-2"}
        ]
        
        with patch.object(worker_manager, '_start_single_worker', new_callable=AsyncMock) as mock_start:
            mock_start.return_value = {
                "status": "started",
                "node_name": "worker-1",
                "process_id": 12345
            }
            
            with patch('asyncio.sleep') as mock_sleep:
                await worker_manager.start_worker_nodes(configs, "ray://127.0.0.1:10001")
                
                # Should have one sleep call between the two workers
                mock_sleep.assert_called_once_with(0.5)

    @pytest.mark.asyncio
    async def test__start_single_worker_success(self, worker_manager):
        """Test starting a single worker successfully."""
        config = {"num_cpus": 2, "node_name": "test-worker"}
        head_node_address = "ray://127.0.0.1:10001"
        
        class MockProcess:
            def __init__(self):
                self.pid = 12345
                self._running = True
            
            def poll(self):
                return None if self._running else 1
            
            def communicate(self):
                return ("stdout", "stderr")
        
        with patch('subprocess.Popen', return_value=MockProcess()) as mock_popen:
            with patch('asyncio.sleep'):
                result = await worker_manager._start_single_worker(config, head_node_address, "test-worker")
                
                assert result["status"] == "started"
                assert result["node_name"] == "test-worker"
                assert result["process_id"] == 12345
                assert result["config"] == config
                assert "started successfully" in result["message"]
                
                # Check that process was added to manager
                assert len(worker_manager.worker_processes) == 1
                assert len(worker_manager.worker_configs) == 1
                assert worker_manager.worker_configs[0] == config

    @pytest.mark.asyncio
    async def test__start_single_worker_process_fails_to_start(self, worker_manager):
        """Test when worker process fails to start."""
        config = {"num_cpus": 2, "node_name": "test-worker"}
        head_node_address = "ray://127.0.0.1:10001"
        
        class MockProcess:
            def __init__(self):
                self.pid = 12345
                self._running = False
            
            def poll(self):
                return 1  # Process has exited
            
            def communicate(self):
                return ("stdout", "stderr")
        
        with patch('subprocess.Popen', return_value=MockProcess()) as mock_popen:
            with patch('asyncio.sleep'):
                result = await worker_manager._start_single_worker(config, head_node_address, "test-worker")
                
                assert result["status"] == "error"
                assert result["node_name"] == "test-worker"
                assert "Failed to spawn worker process" in result["message"]
                
                # Check that process was not added to manager
                assert len(worker_manager.worker_processes) == 0
                assert len(worker_manager.worker_configs) == 0

    @pytest.mark.asyncio
    async def test__start_single_worker_subprocess_exception(self, worker_manager):
        """Test when subprocess.Popen raises an exception."""
        config = {"num_cpus": 2, "node_name": "test-worker"}
        head_node_address = "ray://127.0.0.1:10001"
        
        with patch('subprocess.Popen', side_effect=OSError("Command not found")) as mock_popen:
            result = await worker_manager._start_single_worker(config, head_node_address, "test-worker")
            
            assert result["status"] == "error"
            assert result["node_name"] == "test-worker"
            assert "Failed to spawn worker process" in result["message"]
            # The original exception message is not included in the final result

    @pytest.mark.asyncio
    async def test__start_single_worker_with_default_node_name(self, worker_manager):
        """Test starting worker with default node name when not specified in config."""
        config = {"num_cpus": 2}  # No node_name specified
        head_node_address = "ray://127.0.0.1:10001"
        default_name = "worker-1"
        
        class MockProcess:
            def __init__(self):
                self.pid = 12345
                self._running = True
            
            def poll(self):
                return None
            
            def communicate(self):
                return ("stdout", "stderr")
        
        with patch('subprocess.Popen', return_value=MockProcess()):
            with patch('asyncio.sleep'):
                result = await worker_manager._start_single_worker(config, head_node_address, default_name)
                
                assert result["status"] == "started"
                assert result["node_name"] == default_name

    @pytest.mark.asyncio
    async def test__spawn_worker_process_success(self, worker_manager):
        """Test spawning worker process successfully."""
        cmd = ["ray", "start", "--address", "ray://127.0.0.1:10001"]
        node_name = "test-worker"
        
        class MockProcess:
            def __init__(self):
                self.pid = 12345
                self._running = True
            
            def poll(self):
                return None if self._running else 1
        
        with patch('subprocess.Popen', return_value=MockProcess()) as mock_popen:
            with patch('asyncio.sleep'):
                with patch('os.environ.copy', return_value={"RAY_DISABLE_USAGE_STATS": "1"}):
                    process = await worker_manager._spawn_worker_process(cmd, node_name)
                    
                    assert process is not None
                    assert process.pid == 12345
                    mock_popen.assert_called_once()

    @pytest.mark.asyncio
    async def test__spawn_worker_process_failure(self, worker_manager):
        """Test spawning worker process when it fails to start."""
        cmd = ["ray", "start", "--address", "ray://127.0.0.1:10001"]
        node_name = "test-worker"
        
        class MockProcess:
            def __init__(self):
                self.pid = 12345
                self._running = False
            
            def poll(self):
                return 1  # Process has exited
            
            def communicate(self):
                return ("stdout", "stderr")
        
        with patch('subprocess.Popen', return_value=MockProcess()) as mock_popen:
            with patch('asyncio.sleep'):
                process = await worker_manager._spawn_worker_process(cmd, node_name)
                
                assert process is None

    @pytest.mark.asyncio
    async def test__spawn_worker_process_exception(self, worker_manager):
        """Test spawning worker process when subprocess.Popen raises an exception."""
        cmd = ["ray", "start", "--address", "ray://127.0.0.1:10001"]
        node_name = "test-worker"
        
        with patch('subprocess.Popen', side_effect=FileNotFoundError("ray command not found")):
            process = await worker_manager._spawn_worker_process(cmd, node_name)
            
            assert process is None

    @pytest.mark.asyncio
    async def test_stop_all_workers_empty(self, worker_manager):
        """Test stopping all workers when no workers are running."""
        results = await worker_manager.stop_all_workers()
        assert results == []

    @pytest.mark.asyncio
    async def test_stop_all_workers_graceful(self, worker_manager):
        """Test stopping all workers gracefully."""
        class MockProcess:
            def __init__(self):
                self.pid = 12345
                self._running = True
                self._terminated = False
                self._killed = False
            
            def poll(self):
                return None if self._running else 1
            
            def terminate(self):
                self._terminated = True
            
            def wait(self, timeout=None):
                if self._terminated:
                    self._running = False
                return None
            
            def kill(self):
                self._killed = True
                self._running = False
        
        worker_manager.worker_processes = [MockProcess()]
        worker_manager.worker_configs = [{"node_name": "test-worker"}]
        
        results = await worker_manager.stop_all_workers()
        
        assert len(results) == 1
        assert results[0]["status"] == "stopped"
        assert results[0]["node_name"] == "test-worker"
        assert results[0]["process_id"] == 12345
        assert "stopped gracefully" in results[0]["message"]
        
        # Check that lists were cleared
        assert len(worker_manager.worker_processes) == 0
        assert len(worker_manager.worker_configs) == 0

    @pytest.mark.asyncio
    async def test_stop_all_workers_force_kill(self, worker_manager):
        """Test stopping all workers with force kill when graceful termination fails."""
        class MockProcess:
            def __init__(self):
                self.pid = 12345
                self._running = True
                self._terminated = False
                self._killed = False
                self._wait_count = 0
            
            def poll(self):
                return None if self._running else 1
            
            def terminate(self):
                self._terminated = True
            
            def wait(self, timeout=None):
                self._wait_count += 1
                if self._terminated and self._wait_count == 1:
                    # First wait after terminate raises TimeoutExpired
                    raise subprocess.TimeoutExpired(cmd="ray", timeout=5)
                elif self._killed:
                    # Second wait after kill succeeds
                    self._running = False
                    return None
                else:
                    # Other cases
                    self._running = False
                    return None
            
            def kill(self):
                self._killed = True
                self._running = False
        
        worker_manager.worker_processes = [MockProcess()]
        worker_manager.worker_configs = [{"node_name": "test-worker"}]
        
        results = await worker_manager.stop_all_workers()
        
        assert len(results) == 1
        assert results[0]["status"] == "force_stopped"
        assert results[0]["node_name"] == "test-worker"
        assert results[0]["process_id"] == 12345
        assert "force stopped" in results[0]["message"]

    @pytest.mark.asyncio
    async def test_stop_all_workers_error(self, worker_manager):
        """Test stopping all workers when an error occurs."""
        class MockProcess:
            def __init__(self):
                self.pid = 12345
                self._running = True
            
            def poll(self):
                return None
            
            def terminate(self):
                raise Exception("Termination failed")
            
            def wait(self, timeout=None):
                pass
            
            def kill(self):
                pass
        
        worker_manager.worker_processes = [MockProcess()]
        worker_manager.worker_configs = [{"node_name": "test-worker"}]
        
        results = await worker_manager.stop_all_workers()
        
        assert len(results) == 1
        assert results[0]["status"] == "error"
        assert results[0]["node_name"] == "worker-1"  # Uses index-based name when exception occurs
        assert "Failed to stop worker" in results[0]["message"]

    @pytest.mark.asyncio
    async def test_stop_all_workers_multiple_mixed(self, worker_manager):
        """Test stopping multiple workers with mixed results."""
        class MockProcessGraceful:
            def __init__(self):
                self.pid = 12345
                self._running = True
            
            def poll(self):
                return None
            
            def terminate(self):
                pass
            
            def wait(self, timeout=None):
                self._running = False
                return None
            
            def kill(self):
                pass
        
        class MockProcessForce:
            def __init__(self):
                self.pid = 12346
                self._running = True
                self._terminated = False
                self._killed = False
                self._wait_count = 0
            
            def poll(self):
                return None
            
            def terminate(self):
                self._terminated = True
            
            def wait(self, timeout=None):
                self._wait_count += 1
                if self._terminated and self._wait_count == 1:
                    # First wait after terminate raises TimeoutExpired
                    raise subprocess.TimeoutExpired(cmd="ray", timeout=5)
                elif self._killed:
                    # Second wait after kill succeeds
                    self._running = False
                    return None
                else:
                    # Other cases
                    self._running = False
                    return None
            
            def kill(self):
                self._killed = True
                self._running = False
        
        class MockProcessError:
            def __init__(self):
                self.pid = 12347
                self._running = True
            
            def poll(self):
                return None
            
            def terminate(self):
                raise Exception("Termination failed")
            
            def wait(self, timeout=None):
                pass
            
            def kill(self):
                pass
        
        worker_manager.worker_processes = [
            MockProcessGraceful(),
            MockProcessForce(),
            MockProcessError()
        ]
        worker_manager.worker_configs = [
            {"node_name": "worker-1"},
            {"node_name": "worker-2"},
            {"node_name": "worker-3"}
        ]
        
        results = await worker_manager.stop_all_workers()
        
        assert len(results) == 3
        assert results[0]["status"] == "stopped"
        assert results[1]["status"] == "force_stopped"
        assert results[2]["status"] == "error"
        assert results[2]["node_name"] == "worker-3"  # Uses index-based name when exception occurs

    def test_get_worker_status_empty(self, worker_manager):
        """Test getting worker status when no workers are running."""
        status = worker_manager.get_worker_status()
        assert status == []

    def test_get_worker_status_running(self, worker_manager):
        """Test getting worker status for running workers."""
        class MockProcess:
            def __init__(self):
                self.pid = 12345
                self._running = True
            
            def poll(self):
                return None  # None means running
        
        worker_manager.worker_processes = [MockProcess()]
        worker_manager.worker_configs = [{"node_name": "test-worker"}]
        
        status = worker_manager.get_worker_status()
        
        assert len(status) == 1
        assert status[0]["status"] == "running"
        assert status[0]["node_name"] == "test-worker"
        assert status[0]["process_id"] == 12345
        assert "is running" in status[0]["message"]

    def test_get_worker_status_stopped(self, worker_manager):
        """Test getting worker status for stopped workers."""
        class MockProcess:
            def __init__(self):
                self.pid = 12345
                self._running = False
            
            def poll(self):
                return 1  # Non-None means stopped
        
        worker_manager.worker_processes = [MockProcess()]
        worker_manager.worker_configs = [{"node_name": "test-worker"}]
        
        status = worker_manager.get_worker_status()
        
        assert len(status) == 1
        assert status[0]["status"] == "stopped"
        assert status[0]["node_name"] == "test-worker"
        assert status[0]["process_id"] == 12345
        assert "has stopped" in status[0]["message"]

    def test_get_worker_status_mixed(self, worker_manager):
        """Test getting worker status for mixed running and stopped workers."""
        class MockProcessRunning:
            def __init__(self):
                self.pid = 12345
                self._running = True
            
            def poll(self):
                return None
        
        class MockProcessStopped:
            def __init__(self):
                self.pid = 12346
                self._running = False
            
            def poll(self):
                return 1
        
        worker_manager.worker_processes = [MockProcessRunning(), MockProcessStopped()]
        worker_manager.worker_configs = [
            {"node_name": "worker-1"},
            {"node_name": "worker-2"}
        ]
        
        status = worker_manager.get_worker_status()
        
        assert len(status) == 2
        assert status[0]["status"] == "running"
        assert status[1]["status"] == "stopped"

    def test_get_worker_status_with_default_names(self, worker_manager):
        """Test getting worker status when node names are not specified in config."""
        class MockProcess:
            def __init__(self):
                self.pid = 12345
                self._running = True
            
            def poll(self):
                return None
        
        worker_manager.worker_processes = [MockProcess()]
        worker_manager.worker_configs = [{}]  # No node_name specified
        
        status = worker_manager.get_worker_status()
        
        assert len(status) == 1
        assert status[0]["status"] == "running"
        assert status[0]["node_name"] == "worker-1"  # Default name
        assert status[0]["process_id"] == 12345

    def test_worker_manager_state_management(self, worker_manager):
        """Test that worker manager properly manages its internal state."""
        # Test initial state
        assert worker_manager.worker_processes == []
        assert worker_manager.worker_configs == []
        
        # Test adding workers
        class MockProcess:
            def __init__(self, pid):
                self.pid = pid
                self._running = True
            
            def poll(self):
                return None
        
        # Simulate adding workers
        worker_manager.worker_processes = [MockProcess(12345), MockProcess(12346)]
        worker_manager.worker_configs = [
            {"node_name": "worker-1", "num_cpus": 2},
            {"node_name": "worker-2", "num_cpus": 4}
        ]
        
        assert len(worker_manager.worker_processes) == 2
        assert len(worker_manager.worker_configs) == 2
        assert worker_manager.worker_processes[0].pid == 12345
        assert worker_manager.worker_processes[1].pid == 12346
        assert worker_manager.worker_configs[0]["num_cpus"] == 2
        assert worker_manager.worker_configs[1]["num_cpus"] == 4

    @pytest.mark.asyncio
    async def test_worker_manager_integration_workflow(self, worker_manager):
        """Test a complete workflow: start workers, check status, stop workers."""
        # Mock successful worker start
        class MockProcess:
            def __init__(self, pid):
                self.pid = pid
                self._running = True
            
            def poll(self):
                return None
            
            def terminate(self):
                pass
            
            def wait(self, timeout=None):
                self._running = False
                return None
            
            def kill(self):
                pass
        
        configs = [
            {"num_cpus": 2, "node_name": "worker-1"},
            {"num_cpus": 4, "node_name": "worker-2"}
        ]
        
        # Start workers
        with patch.object(worker_manager, '_start_single_worker', new_callable=AsyncMock) as mock_start:
            mock_start.side_effect = [
                {
                    "status": "started",
                    "node_name": "worker-1",
                    "process_id": 12345,
                    "config": configs[0]
                },
                {
                    "status": "started",
                    "node_name": "worker-2",
                    "process_id": 12346,
                    "config": configs[1]
                }
            ]
            
            results = await worker_manager.start_worker_nodes(configs, "ray://127.0.0.1:10001")
            assert len(results) == 2
            assert all(r["status"] == "started" for r in results)
        
        # Simulate workers being added to manager
        worker_manager.worker_processes = [MockProcess(12345), MockProcess(12346)]
        worker_manager.worker_configs = configs
        
        # Check status
        status = worker_manager.get_worker_status()
        assert len(status) == 2
        assert all(s["status"] == "running" for s in status)
        
        # Stop workers
        results = await worker_manager.stop_all_workers()
        assert len(results) == 2
        assert all(r["status"] == "stopped" for r in results)
        
        # Verify lists were cleared
        assert len(worker_manager.worker_processes) == 0
        assert len(worker_manager.worker_configs) == 0 