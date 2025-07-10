#!/usr/bin/env python3
"""Tests for Kubernetes and KubeRay integration.

This file consolidates tests for:
- Kubernetes cluster management and connectivity  
- KubeRay cluster and job operations
- CRD management and validation
- Cross-component Kubernetes integration

Focus: Behavior-driven tests for Kubernetes functionality.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ray_mcp.kubernetes.crds.ray_cluster_crd import RayClusterCRDManager
from ray_mcp.kubernetes.crds.ray_job_crd import RayJobCRDManager
from ray_mcp.kubernetes.managers.kuberay_cluster_manager import KubeRayClusterManagerImpl
from ray_mcp.kubernetes.managers.kuberay_job_manager import KubeRayJobManagerImpl
from ray_mcp.kubernetes.managers.kubernetes_manager import KubernetesClusterManager
from ray_mcp.managers.state_manager import RayStateManager
from ray_mcp.managers.unified_manager import RayUnifiedManager


@pytest.mark.fast
class TestKubernetesCRDOperations:
    """Test Kubernetes CRD operations for RayCluster and RayJob."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cluster_crd = RayClusterCRDManager()
        self.job_crd = RayJobCRDManager()

    def test_ray_cluster_crd_spec_creation(self):
        """Test RayCluster CRD specification creation and validation."""
        head_spec = {"num_cpus": 4, "memory_request": "8Gi"}
        worker_specs = [{"num_cpus": 2, "replicas": 3}]

        result = self.cluster_crd.create_spec(head_spec, worker_specs)

        assert result["status"] == "success"
        assert "cluster_spec" in result
        assert "cluster_name" in result

        spec = result["cluster_spec"]
        assert spec["apiVersion"] == "ray.io/v1"
        assert spec["kind"] == "RayCluster"
        assert "headGroupSpec" in spec["spec"]
        assert "workerGroupSpecs" in spec["spec"]

    def test_ray_cluster_crd_validation(self):
        """Test RayCluster CRD validation workflows."""
        # Test valid spec
        valid_spec = {
            "apiVersion": "ray.io/v1",
            "kind": "RayCluster",
            "metadata": {"name": "test-cluster"},
            "spec": {
                "rayVersion": "2.47.0",
                "headGroupSpec": {"template": {"spec": {}}},
                "workerGroupSpecs": [{"template": {"spec": {}}}],
            },
        }

        result = self.cluster_crd.validate_spec(valid_spec)
        assert result["status"] == "success"
        assert result["valid"] is True
        assert result["errors"] == []

        # Test invalid spec
        invalid_spec = {
            "apiVersion": "v1",  # Wrong API version
            "kind": "RayCluster",
            "metadata": {},  # Missing name
            "spec": {},  # Missing required fields
        }

        result = self.cluster_crd.validate_spec(invalid_spec)
        assert result["status"] == "success"
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_ray_job_crd_spec_creation(self):
        """Test RayJob CRD specification creation and validation."""
        entrypoint = "python my_script.py"
        runtime_env = {"pip": ["numpy", "pandas"], "env_vars": {"MY_VAR": "value"}}

        result = self.job_crd.create_spec(entrypoint, runtime_env=runtime_env)

        assert result["status"] == "success"
        assert "job_spec" in result
        assert "job_name" in result

        spec = result["job_spec"]
        assert spec["apiVersion"] == "ray.io/v1"
        assert spec["kind"] == "RayJob"
        assert spec["spec"]["entrypoint"] == entrypoint
        assert spec["spec"]["runtimeEnvYAML"]  # Should contain serialized runtime env

    def test_ray_job_crd_validation_patterns(self):
        """Test RayJob CRD validation patterns and error handling."""
        # Test invalid entrypoint
        result = self.job_crd.create_spec("")  # Empty entrypoint
        assert result["status"] == "error"
        assert "entrypoint" in result["message"].lower()

        # Test runtime environment validation
        valid_env = {
            "pip": ["numpy"],
            "env_vars": {"KEY": "value"},
            "working_dir": "/tmp",
        }
        result = self.job_crd._validate_runtime_env(valid_env)
        assert result["valid"] is True
        assert result["errors"] == []

        invalid_env = {
            "pip": [123],  # Should be strings
            "env_vars": {"key": 456},  # Values should be strings
        }
        result = self.job_crd._validate_runtime_env(invalid_env)
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_crd_serialization_formats(self):
        """Test CRD serialization to different formats."""
        spec = {"test": "data", "nested": {"key": "value"}}
        
        # Test JSON serialization
        json_output = self.cluster_crd.to_json(spec)
        assert isinstance(json_output, str)
        assert '"test": "data"' in json_output
        assert '"nested"' in json_output

        # Test YAML serialization (if available)
        with patch("ray_mcp.kubernetes.crds.ray_cluster_crd.YAML_AVAILABLE", True):
            yaml_output = self.cluster_crd.to_yaml(spec)
            assert isinstance(yaml_output, str)
            assert "test: data" in yaml_output


@pytest.mark.fast
class TestKubeRayClusterOperations:
    """Test KubeRay cluster management operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.state_manager = RayStateManager()
        self.state_manager.update_state(kubernetes_connected=True)

        self.mock_crd_operations = Mock()
        self.mock_cluster_crd = Mock()

        self.cluster_manager = KubeRayClusterManagerImpl(
            self.state_manager,
            crd_operations=self.mock_crd_operations,
            cluster_crd=self.mock_cluster_crd,
        )

    @pytest.mark.asyncio
    async def test_kuberay_cluster_lifecycle_workflow(self):
        """Test complete KubeRay cluster lifecycle workflow."""
        cluster_spec = {
            "head_node_spec": {"num_cpus": 4},
            "worker_node_specs": [{"num_cpus": 2, "replicas": 3}],
        }

        # Mock cluster creation
        self.mock_cluster_crd.create_spec.return_value = {
            "status": "success",
            "cluster_spec": {"apiVersion": "ray.io/v1", "kind": "RayCluster"},
            "cluster_name": "test-cluster",
        }
        self.mock_crd_operations.create_resource = AsyncMock(
            return_value={
                "status": "success",
                "resource": {"metadata": {"name": "test-cluster"}},
            }
        )

        # Test cluster creation
        create_result = await self.cluster_manager.create_ray_cluster(cluster_spec)
        assert create_result["status"] == "success"
        assert create_result["cluster_name"] == "test-cluster"

        # Mock cluster retrieval
        self.mock_crd_operations.get_resource = AsyncMock(
            return_value={
                "status": "success",
                "resource": {
                    "metadata": {"name": "test-cluster"},
                    "spec": {"rayVersion": "2.47.0"},
                    "status": {
                        "phase": "running",
                        "state": "ready",
                        "readyWorkerReplicas": 2,
                        "desiredWorkerReplicas": 2,
                    },
                },
            }
        )

        # Test cluster status retrieval
        get_result = await self.cluster_manager.get_ray_cluster("test-cluster")
        assert get_result["status"] == "success"
        cluster = get_result["cluster"]
        assert cluster["name"] == "test-cluster"
        assert cluster["phase"] == "running"
        assert cluster["ray_version"] == "2.47.0"

    @pytest.mark.asyncio
    async def test_kuberay_cluster_scaling_operations(self):
        """Test KubeRay cluster scaling operations."""
        # Mock current cluster state
        self.mock_crd_operations.get_resource = AsyncMock(
            return_value={
                "status": "success",
                "resource": {
                    "spec": {"workerGroupSpecs": [{"replicas": 2, "maxReplicas": 4}]},
                    "status": {},
                },
            }
        )

        # Mock update operation
        self.mock_crd_operations.update_resource = AsyncMock(
            return_value={"status": "success"}
        )

        # Test successful scaling
        result = await self.cluster_manager.scale_ray_cluster("test-cluster", 5)
        assert result["status"] == "success"
        assert result["worker_replicas"] == 5
        assert result["cluster_status"] == "scaling"

        # Test invalid scaling parameters
        result = await self.cluster_manager.scale_ray_cluster("test-cluster", -1)
        assert result["status"] == "error"
        assert "non-negative" in result["message"]

    def test_kuberay_readiness_requirements(self):
        """Test KubeRay readiness checks and requirements."""
        # Create a disconnected state manager and cluster manager
        disconnected_state_manager = RayStateManager()
        disconnected_state_manager.reset_state()  # Ensure kubernetes_connected=False
        
        disconnected_cluster_manager = KubeRayClusterManagerImpl(
            disconnected_state_manager,
            crd_operations=self.mock_crd_operations,
            cluster_crd=self.mock_cluster_crd,
        )
        
        # Test not connected to Kubernetes - should raise RuntimeError
        with pytest.raises(RuntimeError, match="not connected"):
            disconnected_cluster_manager._ensure_kuberay_ready()

        # Test again with another disconnected manager
        another_disconnected_state_manager = RayStateManager()
        another_disconnected_state_manager.reset_state()
        another_disconnected_cluster_manager = KubeRayClusterManagerImpl(
            another_disconnected_state_manager,
            crd_operations=self.mock_crd_operations,
            cluster_crd=self.mock_cluster_crd,
        )
        
        with pytest.raises(RuntimeError, match="not connected"):
            another_disconnected_cluster_manager._ensure_kuberay_ready()

    @pytest.mark.asyncio
    async def test_kuberay_cluster_error_handling(self):
        """Test error handling in KubeRay cluster operations."""
        # Test missing head node spec
        invalid_spec = {"worker_node_specs": []}
        result = await self.cluster_manager.create_ray_cluster(invalid_spec)
        assert result["status"] == "error"
        assert "head_node_spec" in result["message"]

        # Test CRD creation failure
        self.mock_cluster_crd.create_spec.return_value = {
            "status": "error",
            "message": "CRD validation failed"
        }
        valid_spec = {
            "head_node_spec": {"num_cpus": 4},
            "worker_node_specs": [{"num_cpus": 2, "replicas": 3}],
        }
        result = await self.cluster_manager.create_ray_cluster(valid_spec)
        assert result["status"] == "error"


@pytest.mark.fast
class TestKubeRayJobOperations:
    """Test KubeRay job management operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.state_manager = RayStateManager()
        self.state_manager.update_state(kubernetes_connected=True)

        self.mock_crd_operations = Mock()
        self.mock_job_crd = Mock()

        self.job_manager = KubeRayJobManagerImpl(
            self.state_manager,
            crd_operations=self.mock_crd_operations,
            job_crd=self.mock_job_crd,
        )

    @pytest.mark.asyncio
    async def test_kuberay_job_lifecycle_workflow(self):
        """Test complete KubeRay job lifecycle workflow."""
        job_spec = {
            "entrypoint": "python my_script.py",
            "runtime_env": {"pip": ["numpy"]},
        }

        # Mock job creation
        self.mock_job_crd.create_spec.return_value = {
            "status": "success",
            "job_spec": {"apiVersion": "ray.io/v1", "kind": "RayJob"},
            "job_name": "test-job",
        }
        self.mock_crd_operations.create_resource = AsyncMock(
            return_value={
                "status": "success",
                "resource": {"metadata": {"name": "test-job"}},
            }
        )

        # Test job creation
        create_result = await self.job_manager.create_ray_job(job_spec)
        assert create_result["status"] == "success"
        assert create_result["job_name"] == "test-job"
        assert create_result["entrypoint"] == "python my_script.py"
        assert create_result["job_status"] == "creating"

        # Mock job status retrieval
        self.mock_crd_operations.get_resource = AsyncMock(
            return_value={
                "status": "success",
                "resource": {
                    "metadata": {"name": "test-job"},
                    "spec": {"entrypoint": "python script.py"},
                    "status": {
                        "phase": "running",
                        "jobStatus": "RUNNING",
                        "rayClusterName": "test-cluster",
                    },
                },
            }
        )

        # Test job status retrieval
        get_result = await self.job_manager.get_ray_job("test-job")
        assert get_result["status"] == "success"
        job = get_result["job"]
        assert job["name"] == "test-job"
        assert job["job_status"] == "RUNNING"
        assert job["ray_cluster_name"] == "test-cluster"
        assert get_result["running"] is True
        assert get_result["complete"] is False

    @pytest.mark.asyncio
    async def test_kuberay_job_log_retrieval(self):
        """Test KubeRay job log retrieval from Kubernetes pods."""
        # Mock job retrieval for log context
        self.mock_crd_operations.get_resource = AsyncMock(
            return_value={
                "status": "success",
                "resource": {"status": {"rayClusterName": "test-cluster"}},
            }
        )

        # Mock Kubernetes client for pod logs
        with patch(
            "ray_mcp.kubernetes.config.kubernetes_client.KubernetesApiClient"
        ) as mock_k8s_client_class:
            mock_k8s_client = Mock()
            mock_k8s_client_class.return_value = mock_k8s_client

            # Test successful log retrieval
            mock_k8s_client.get_pod_logs = AsyncMock(
                return_value={
                    "status": "success",
                    "logs": "INFO: Job started successfully\nINFO: Processing data\nINFO: Job completed",
                    "pod_count": 1,
                }
            )

            result = await self.job_manager.get_ray_job_logs("test-job")

            assert result["status"] == "success"
            assert result["ray_cluster_name"] == "test-cluster"
            assert result["job_name"] == "test-job"
            assert result["log_source"] == "job_runner_pods"
            assert result["pod_count"] == 1
            assert "Job started successfully" in result["logs"]

            # Verify Kubernetes client was called correctly
            mock_k8s_client.get_pod_logs.assert_called_once_with(
                namespace="default",
                label_selector="ray.io/cluster=test-cluster,ray.io/job-name=test-job",
                lines=1000,
                timestamps=True,
            )

    @pytest.mark.asyncio
    async def test_kuberay_job_log_fallback_strategies(self):
        """Test KubeRay job log retrieval fallback strategies."""
        # Mock job retrieval
        self.mock_crd_operations.get_resource = AsyncMock(
            return_value={
                "status": "success",
                "resource": {"status": {"rayClusterName": "test-cluster"}},
            }
        )

        with patch(
            "ray_mcp.kubernetes.config.kubernetes_client.KubernetesApiClient"
        ) as mock_k8s_client_class:
            mock_k8s_client = Mock()
            mock_k8s_client_class.return_value = mock_k8s_client

            # Mock fallback scenario: no job-specific pods, but head node logs available
            mock_k8s_client.get_pod_logs = AsyncMock(
                side_effect=[
                    # First call: no job-specific pods
                    {
                        "status": "success",
                        "logs": "No pods found matching the label selector",
                        "pod_count": 0,
                    },
                    # Second call: head node logs
                    {
                        "status": "success",
                        "logs": "INFO: Ray head node started\nINFO: Job test-job submitted\nINFO: Job test-job completed",
                        "pod_count": 1,
                    },
                ]
            )

            result = await self.job_manager.get_ray_job_logs("test-job")

            assert result["status"] == "success"
            assert result["log_source"] == "head_node_filtered"
            assert result["pod_count"] == 1
            assert "Job test-job" in result["logs"]

    @pytest.mark.asyncio
    async def test_kuberay_job_error_handling(self):
        """Test error handling in KubeRay job operations."""
        # Test missing entrypoint
        invalid_spec = {"runtime_env": {"pip": ["numpy"]}}
        result = await self.job_manager.create_ray_job(invalid_spec)
        assert result["status"] == "error"
        assert "entrypoint" in result["message"]

        # Test CRD creation failure
        self.mock_job_crd.create_spec.return_value = {
            "status": "error",
            "message": "Invalid job specification"
        }
        valid_spec = {"entrypoint": "python script.py"}
        result = await self.job_manager.create_ray_job(valid_spec)
        assert result["status"] == "error"


@pytest.mark.fast
class TestKubernetesClusterManager:
    """Test Kubernetes cluster management functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.state_manager = RayStateManager()
        self.k8s_manager = KubernetesClusterManager(self.state_manager)

    def test_kubernetes_manager_initialization(self):
        """Test Kubernetes manager initialization and structure."""
        assert self.k8s_manager is not None
        assert self.k8s_manager.state_manager is self.state_manager
        assert self.k8s_manager.get_config_manager() is not None
        assert self.k8s_manager.get_client() is not None

    @pytest.mark.asyncio
    async def test_kubernetes_connectivity_workflows(self):
        """Test Kubernetes connectivity and disconnection workflows."""
        # Test connection without Kubernetes library available
        manager = KubernetesClusterManager(self.state_manager)
        manager._config_manager._KUBERNETES_AVAILABLE = False

        result = await manager.connect()
        assert result["status"] == "error"
        assert "kubernetes" in result["message"].lower()

        # Test disconnection workflow
        self.state_manager.update_state(
            kubernetes_connected=True, kubernetes_context="test-context"
        )

        result = await self.k8s_manager.disconnect_cluster()
        assert result["status"] == "success"
        assert not self.state_manager.get_state().get("kubernetes_connected", True)
        assert self.state_manager.get_state().get("kubernetes_context") is None

    @pytest.mark.asyncio
    async def test_kubernetes_cluster_operations_require_connection(self):
        """Test that Kubernetes operations require active connection."""
        # Test health check when not connected
        result = await self.k8s_manager.health_check()
        assert result["status"] == "error"
        assert "not connected" in result["message"].lower()

        # Test inspect cluster when not connected
        result = await self.k8s_manager.inspect_cluster()
        assert result["status"] == "error"
        assert "not connected" in result["message"].lower()

        # Test operations that raise exceptions when not connected
        operations_requiring_connection = [
            "get_namespaces",
            "get_nodes", 
            "get_pods"
        ]

        for operation in operations_requiring_connection:
            with pytest.raises(RuntimeError, match="not connected"):
                await getattr(self.k8s_manager, operation)()

    @pytest.mark.asyncio
    async def test_kubernetes_configuration_validation(self):
        """Test Kubernetes configuration validation."""
        result = await self.k8s_manager.validate_config()
        assert result is not None
        # Should not raise exceptions and should return a valid result


@pytest.mark.fast
class TestKubernetesUnifiedIntegration:
    """Test Kubernetes integration with unified manager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.unified_manager = RayUnifiedManager()

    def test_kubernetes_components_integration(self):
        """Test that Kubernetes components are properly integrated."""
        # Test Kubernetes manager availability
        k8s_manager = self.unified_manager.get_kubernetes_manager()
        assert k8s_manager is not None
        assert hasattr(k8s_manager, "connect")
        assert hasattr(k8s_manager, "disconnect_cluster")
        assert hasattr(k8s_manager, "inspect_cluster")

        # Test KubeRay managers availability
        assert hasattr(self.unified_manager, "_kuberay_cluster_manager")
        assert hasattr(self.unified_manager, "_kuberay_job_manager")

    def test_kubernetes_properties_and_state(self):
        """Test Kubernetes properties and state management in unified manager."""
        # Test properties are available
        assert hasattr(self.unified_manager, "is_kubernetes_connected")
        assert hasattr(self.unified_manager, "kubernetes_context")
        assert hasattr(self.unified_manager, "kubernetes_server_version")
        assert hasattr(self.unified_manager, "kuberay_clusters")
        assert hasattr(self.unified_manager, "kuberay_jobs")

        # Test initial state
        assert self.unified_manager.is_kubernetes_connected is False
        assert self.unified_manager.kubernetes_context is None
        assert self.unified_manager.kubernetes_server_version is None
        assert isinstance(self.unified_manager.kuberay_clusters, dict)
        assert isinstance(self.unified_manager.kuberay_jobs, dict)

    @pytest.mark.asyncio
    async def test_kubernetes_workflow_integration(self):
        """Test integrated Kubernetes workflow through unified manager."""
        methods_to_test = [
            "connect_kubernetes_cluster",
            "disconnect_kubernetes_cluster", 
            "inspect_kubernetes_cluster",
            "kubernetes_health_check",
            "list_kubernetes_contexts",
            "get_kubernetes_namespaces",
            "get_kubernetes_nodes",
            "get_kubernetes_pods",
            "validate_kubernetes_config",
        ]

        for method_name in methods_to_test:
            assert hasattr(self.unified_manager, method_name)
            method = getattr(self.unified_manager, method_name)
            assert callable(method)

        # Test disconnection workflow
        result = await self.unified_manager.disconnect_kubernetes_cluster()
        assert result["status"] == "success"
        assert not self.unified_manager.is_kubernetes_connected

    @pytest.mark.asyncio
    async def test_kuberay_workflow_integration(self):
        """Test KubeRay workflow integration through unified manager."""
        kuberay_methods = [
            "create_kuberay_cluster",
            "get_kuberay_cluster",
            "list_ray_clusters",
            "update_kuberay_cluster", 
            "delete_kuberay_cluster",
            "scale_ray_cluster",
            "create_kuberay_job",
            "get_kuberay_job",
            "list_kuberay_jobs",
            "delete_kuberay_job",
            "get_kuberay_job_logs",
        ]

        for method_name in kuberay_methods:
            assert hasattr(self.unified_manager, method_name)
            method = getattr(self.unified_manager, method_name)
            assert callable(method)

    @pytest.mark.asyncio
    async def test_cloud_provider_coordination(self):
        """Test cloud provider coordination with Kubernetes."""
        # Test that cloud provider methods are available
        cloud_methods = [
            "detect_cloud_provider",
            "connect_kubernetes_cluster",  # Use actual method name
            "disconnect_kubernetes_cluster",  # Use actual method name
        ]

        for method_name in cloud_methods:
            assert hasattr(self.unified_manager, method_name)
            method = getattr(self.unified_manager, method_name)
            assert callable(method)

        # Test that cloud provider manager is accessible
        assert hasattr(self.unified_manager, "_cloud_provider_manager")
        # Test that cloud provider manager has cloud provider functionality
        cloud_provider_manager = self.unified_manager._cloud_provider_manager
        assert hasattr(cloud_provider_manager, "detect_cloud_provider")
        assert callable(cloud_provider_manager.detect_cloud_provider)


@pytest.mark.fast
class TestKubernetesErrorHandlingPatterns:
    """Test error handling patterns across Kubernetes components."""

    def test_kubernetes_availability_error_patterns(self):
        """Test error patterns when Kubernetes libraries are unavailable."""
        state_manager = RayStateManager()
        k8s_manager = KubernetesClusterManager(state_manager)

        # Simulate Kubernetes library unavailable
        k8s_manager._config_manager._KUBERNETES_AVAILABLE = False

        # Test async operations
        async def test_connect():
            result = await k8s_manager.connect()
            assert result["status"] == "error"
            assert "kubernetes" in result["message"].lower()

        import asyncio
        asyncio.run(test_connect())

    def test_kuberay_connection_requirement_patterns(self):
        """Test error patterns when KubeRay operations require Kubernetes connection."""
        state_manager = RayStateManager()
        # Ensure state shows not connected
        state_manager.reset_state()

        cluster_manager = KubeRayClusterManagerImpl(
            state_manager,
            crd_operations=Mock(),
            cluster_crd=Mock(),
        )

        # Test readiness check
        with pytest.raises(RuntimeError, match="not connected"):
            cluster_manager._ensure_kuberay_ready()

    @pytest.mark.asyncio
    async def test_crd_operation_error_patterns(self):
        """Test error handling patterns in CRD operations."""
        state_manager = RayStateManager()
        state_manager.update_state(kubernetes_connected=True)

        mock_crd_operations = Mock()
        mock_cluster_crd = Mock()

        cluster_manager = KubeRayClusterManagerImpl(
            state_manager,
            crd_operations=mock_crd_operations,
            cluster_crd=mock_cluster_crd,
        )

        # Test CRD creation failure
        mock_cluster_crd.create_spec.return_value = {
            "status": "error",
            "message": "Validation failed"
        }

        cluster_spec = {
            "head_node_spec": {"num_cpus": 4},
            "worker_node_specs": [{"num_cpus": 2, "replicas": 3}],
        }

        result = await cluster_manager.create_ray_cluster(cluster_spec)
        assert result["status"] == "error"

    def test_validation_error_propagation_patterns(self):
        """Test how validation errors propagate through the system."""
        cluster_crd = RayClusterCRDManager()
        job_crd = RayJobCRDManager()

        # Test cluster validation error
        invalid_cluster_spec = {"num_cpus": -1}  # Invalid
        result = cluster_crd.create_spec(invalid_cluster_spec, [])
        assert result["status"] == "error"
        assert "invalid" in result["message"].lower()

        # Test job validation error
        result = job_crd.create_spec("")  # Empty entrypoint
        assert result["status"] == "error"
        assert "entrypoint" in result["message"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 