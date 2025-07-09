"""Unit tests for KubeRay manager components.

Tests focus on KubeRay cluster and job management behavior with 100% mocking.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ray_mcp.kubernetes.crds.ray_cluster_crd import RayClusterCRDManager
from ray_mcp.kubernetes.crds.ray_job_crd import RayJobCRDManager
from ray_mcp.kubernetes.managers.kuberay_cluster_manager import (
    KubeRayClusterManagerImpl,
)
from ray_mcp.kubernetes.managers.kuberay_job_manager import KubeRayJobManagerImpl
from ray_mcp.managers.state_manager import RayStateManager


class TestRayClusterCRD:
    """Test cases for RayClusterCRDManager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cluster_crd = RayClusterCRDManager()

    def test_create_spec_basic(self):
        """Test basic RayCluster spec creation."""
        head_spec = {"num_cpus": 4, "memory_request": "8Gi"}
        worker_specs = [{"num_cpus": 2, "replicas": 3}]

        result = self.cluster_crd.create_spec(head_spec, worker_specs)

        assert result.get("status") == "success"
        assert "cluster_spec" in result
        assert "cluster_name" in result

        spec = result["cluster_spec"]
        assert spec["apiVersion"] == "ray.io/v1"
        assert spec["kind"] == "RayCluster"
        assert "headGroupSpec" in spec["spec"]
        assert "workerGroupSpecs" in spec["spec"]

    def test_create_spec_with_custom_name(self):
        """Test RayCluster spec creation with custom name."""
        head_spec = {"num_cpus": 2}
        worker_specs = [{"num_cpus": 1, "replicas": 2}]

        result = self.cluster_crd.create_spec(
            head_spec, worker_specs, cluster_name="my-cluster"
        )

        assert result.get("status") == "success"
        assert result["cluster_name"] == "my-cluster"

        spec = result["cluster_spec"]
        assert spec["metadata"]["name"] == "my-cluster"

    def test_create_spec_validation_error(self):
        """Test RayCluster spec creation with validation errors."""
        head_spec = {"num_cpus": -1}  # Invalid CPU count
        worker_specs = []

        result = self.cluster_crd.create_spec(head_spec, worker_specs)

        assert result.get("status") == "error"
        assert "invalid" in result.get("message", "").lower()

    def test_validate_spec_valid(self):
        """Test validation of valid RayCluster spec."""
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

        assert result.get("status") == "success"
        assert result.get("valid") is True
        assert result.get("errors") == []

    def test_validate_spec_invalid(self):
        """Test validation of invalid RayCluster spec."""
        invalid_spec = {
            "apiVersion": "v1",  # Wrong API version
            "kind": "RayCluster",
            "metadata": {},  # Missing name
            "spec": {},  # Missing required fields
        }

        result = self.cluster_crd.validate_spec(invalid_spec)

        assert result.get("status") == "success"
        assert result.get("valid") is False
        assert len(result.get("errors", [])) > 0

    @patch("ray_mcp.kubernetes.crds.ray_cluster_crd.YAML_AVAILABLE", True)
    def test_to_yaml(self):
        """Test YAML serialization."""
        spec = {"test": "data"}
        yaml_output = self.cluster_crd.to_yaml(spec)

        assert isinstance(yaml_output, str)
        assert "test: data" in yaml_output

    def test_to_json(self):
        """Test JSON serialization."""
        spec = {"test": "data"}
        json_output = self.cluster_crd.to_json(spec)

        assert isinstance(json_output, str)
        assert '"test": "data"' in json_output


class TestRayJobCRD:
    """Test cases for RayJobCRDManager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.job_crd = RayJobCRDManager()

    def test_create_spec_basic(self):
        """Test basic RayJob spec creation."""
        entrypoint = "python my_script.py"

        result = self.job_crd.create_spec(entrypoint)

        assert result.get("status") == "success"
        assert "job_spec" in result
        assert "job_name" in result

        spec = result["job_spec"]
        assert spec["apiVersion"] == "ray.io/v1"
        assert spec["kind"] == "RayJob"
        assert spec["spec"]["entrypoint"] == entrypoint

    def test_create_spec_with_runtime_env(self):
        """Test RayJob spec creation with runtime environment."""
        entrypoint = "python my_script.py"
        runtime_env = {"pip": ["numpy", "pandas"], "env_vars": {"MY_VAR": "value"}}

        result = self.job_crd.create_spec(entrypoint, runtime_env=runtime_env)

        assert result.get("status") == "success"
        spec = result["job_spec"]
        assert spec["spec"]["runtimeEnvYAML"]  # Should contain serialized runtime env

    def test_create_spec_invalid_entrypoint(self):
        """Test RayJob spec creation with invalid entrypoint."""
        result = self.job_crd.create_spec("")  # Empty entrypoint

        assert result.get("status") == "error"
        assert "entrypoint" in result.get("message", "").lower()

    def test_validate_runtime_env(self):
        """Test runtime environment validation."""
        valid_env = {
            "pip": ["numpy"],
            "env_vars": {"KEY": "value"},
            "working_dir": "/tmp",
        }

        result = self.job_crd._validate_runtime_env(valid_env)

        assert result["valid"] is True
        assert result["errors"] == []

    def test_validate_runtime_env_invalid(self):
        """Test invalid runtime environment validation."""
        invalid_env = {
            "pip": [123],  # Should be strings
            "env_vars": {"key": 456},  # Values should be strings
        }

        result = self.job_crd._validate_runtime_env(invalid_env)

        assert result["valid"] is False
        assert len(result["errors"]) > 0


class TestKubeRayClusterManager:
    """Test cases for KubeRayClusterManagerImpl."""

    def setup_method(self):
        """Set up test fixtures."""
        self.state_manager = RayStateManager()
        # Set Kubernetes as connected to pass the _ensure_kuberay_ready check
        self.state_manager.update_state(kubernetes_connected=True)

        # Mock the CRD operations client
        self.mock_crd_operations = Mock()
        self.mock_cluster_crd = Mock()

        self.cluster_manager = KubeRayClusterManagerImpl(
            self.state_manager,
            crd_operations=self.mock_crd_operations,
            cluster_crd=self.mock_cluster_crd,
        )

    @pytest.mark.asyncio
    async def test_create_ray_cluster_success(self):
        """Test successful Ray cluster creation."""
        cluster_spec = {
            "head_node_spec": {"num_cpus": 4},
            "worker_node_specs": [{"num_cpus": 2, "replicas": 3}],
        }

        # Mock CRD creation success
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

        result = await self.cluster_manager.create_ray_cluster(cluster_spec)

        assert result.get("status") == "success"
        assert result.get("cluster_name") == "test-cluster"
        # The new implementation doesn't set cluster_status to "creating" directly
        # Instead it returns the create_result which has the resource info
        assert "cluster_spec" in result
        assert "resource" in result

    @pytest.mark.asyncio
    async def test_create_ray_cluster_missing_head_spec(self):
        """Test Ray cluster creation with missing head node spec."""
        cluster_spec = {"worker_node_specs": []}

        result = await self.cluster_manager.create_ray_cluster(cluster_spec)

        assert result.get("status") == "error"
        assert "head_node_spec" in result.get("message", "")

    @pytest.mark.asyncio
    async def test_get_ray_cluster_success(self):
        """Test successful Ray cluster retrieval."""
        self.mock_crd_operations.get_resource = AsyncMock(
            return_value={
                "status": "success",
                "resource": {
                    "metadata": {
                        "name": "test-cluster",
                        "creationTimestamp": "2023-01-01T00:00:00Z",
                    },
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

        result = await self.cluster_manager.get_ray_cluster("test-cluster")

        assert result.get("status") == "success"
        cluster = result.get("cluster", {})
        assert cluster["name"] == "test-cluster"
        assert cluster["phase"] == "running"
        assert cluster["ray_version"] == "2.47.0"

    @pytest.mark.asyncio
    async def test_scale_ray_cluster(self):
        """Test Ray cluster scaling."""
        # Mock getting current cluster
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

        result = await self.cluster_manager.scale_ray_cluster("test-cluster", 5)

        assert result.get("status") == "success"
        assert result.get("worker_replicas") == 5
        assert result.get("cluster_status") == "scaling"

    @pytest.mark.asyncio
    async def test_scale_ray_cluster_invalid_replicas(self):
        """Test Ray cluster scaling with invalid replica count."""
        result = await self.cluster_manager.scale_ray_cluster("test-cluster", -1)

        assert result.get("status") == "error"
        assert "non-negative" in result.get("message", "")

    def test_not_connected_to_kubernetes(self):
        """Test operations when not connected to Kubernetes."""
        # Reset state to not connected
        self.state_manager.reset_state()

        with pytest.raises(RuntimeError, match="not connected"):
            self.cluster_manager._ensure_kuberay_ready()


class TestKubeRayJobManager:
    """Test cases for KubeRayJobManagerImpl."""

    def setup_method(self):
        """Set up test fixtures."""
        self.state_manager = RayStateManager()
        # Set Kubernetes as connected
        self.state_manager.update_state(kubernetes_connected=True)

        # Mock the CRD operations client and job CRD
        self.mock_crd_operations = Mock()
        self.mock_job_crd = Mock()

        self.job_manager = KubeRayJobManagerImpl(
            self.state_manager,
            crd_operations=self.mock_crd_operations,
            job_crd=self.mock_job_crd,
        )

    @pytest.mark.asyncio
    async def test_create_ray_job_success(self):
        """Test successful Ray job creation."""
        job_spec = {
            "entrypoint": "python my_script.py",
            "runtime_env": {"pip": ["numpy"]},
        }

        # Mock CRD creation success
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

        result = await self.job_manager.create_ray_job(job_spec)

        assert result.get("status") == "success"
        assert result.get("job_name") == "test-job"
        assert result.get("entrypoint") == "python my_script.py"
        assert result.get("job_status") == "creating"

    @pytest.mark.asyncio
    async def test_create_ray_job_missing_entrypoint(self):
        """Test Ray job creation with missing entrypoint."""
        job_spec = {"runtime_env": {"pip": ["numpy"]}}

        result = await self.job_manager.create_ray_job(job_spec)

        assert result.get("status") == "error"
        assert "entrypoint" in result.get("message", "")

    @pytest.mark.asyncio
    async def test_get_ray_job_success(self):
        """Test successful Ray job retrieval."""
        self.mock_crd_operations.get_resource = AsyncMock(
            return_value={
                "status": "success",
                "resource": {
                    "metadata": {
                        "name": "test-job",
                        "creationTimestamp": "2023-01-01T00:00:00Z",
                    },
                    "spec": {
                        "entrypoint": "python script.py",
                        "ttlSecondsAfterFinished": 86400,
                    },
                    "status": {
                        "phase": "running",
                        "jobStatus": "RUNNING",
                        "rayClusterName": "test-cluster",
                        "startTime": "2023-01-01T00:00:00Z",
                    },
                },
            }
        )

        result = await self.job_manager.get_ray_job("test-job")

        assert result.get("status") == "success"
        job = result.get("job", {})
        assert job["name"] == "test-job"
        assert job["job_status"] == "RUNNING"
        assert job["ray_cluster_name"] == "test-cluster"
        assert result.get("running") is True
        assert result.get("complete") is False

    @pytest.mark.asyncio
    async def test_get_ray_job_logs(self):
        """Test Ray job log retrieval."""
        # Mock getting job first
        self.mock_crd_operations.get_resource = AsyncMock(
            return_value={
                "status": "success",
                "resource": {"status": {"rayClusterName": "test-cluster"}},
            }
        )

        result = await self.job_manager.get_ray_job_logs("test-job")

        assert result.get("status") == "success"
        assert result.get("ray_cluster_name") == "test-cluster"
        assert result.get("logs_available") is True


class TestKubeRayUnifiedManagerIntegration:
    """Integration tests for KubeRay functionality in unified manager."""

    def setup_method(self):
        """Set up test fixtures."""
        from ray_mcp.managers.unified_manager import RayUnifiedManager

        self.unified_manager = RayUnifiedManager()

    def test_kuberay_managers_available(self):
        """Test that KubeRay managers are available in unified manager."""
        cluster_manager = self.unified_manager.get_kuberay_cluster_manager()
        job_manager = self.unified_manager.get_kuberay_job_manager()

        assert cluster_manager is not None
        assert job_manager is not None
        assert hasattr(cluster_manager, "create_ray_cluster")
        assert hasattr(job_manager, "create_ray_job")

    def test_kuberay_properties(self):
        """Test KubeRay properties in unified manager."""
        assert hasattr(self.unified_manager, "kuberay_clusters")
        assert hasattr(self.unified_manager, "kuberay_jobs")

        # Test initial state
        assert isinstance(self.unified_manager.kuberay_clusters, dict)
        assert isinstance(self.unified_manager.kuberay_jobs, dict)

    @pytest.mark.asyncio
    async def test_kuberay_methods_available(self):
        """Test that KubeRay methods are available in unified manager."""
        cluster_methods = [
            "create_kuberay_cluster",
            "get_kuberay_cluster",
            "list_ray_clusters",
            "update_kuberay_cluster",
            "delete_kuberay_cluster",
            "scale_ray_cluster",
        ]

        job_methods = [
            "create_kuberay_job",
            "get_kuberay_job",
            "list_kuberay_jobs",
            "delete_kuberay_job",
            "get_kuberay_job_logs",
        ]

        all_methods = cluster_methods + job_methods

        for method_name in all_methods:
            assert hasattr(self.unified_manager, method_name)
            method = getattr(self.unified_manager, method_name)
            assert callable(method)
