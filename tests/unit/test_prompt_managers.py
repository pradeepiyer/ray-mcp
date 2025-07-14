#!/usr/bin/env python3
"""Unit tests for prompt-driven managers.

This module tests the core prompt-driven managers in isolation with full mocking
for fast, deterministic test execution.

Test Focus:
- Prompt parsing and response generation
- Manager routing and delegation
- Error handling and validation
- Response formatting consistency
"""

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from ray_mcp.cloud.cloud_provider_manager import CloudProviderManager

# Import the managers we're testing
from ray_mcp.managers.cluster_manager import ClusterManager
from ray_mcp.managers.job_manager import JobManager
from ray_mcp.managers.unified_manager import RayUnifiedManager


@pytest.mark.unit
class TestClusterManager:
    """Test ClusterManager prompt-driven interface."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = ClusterManager()

        # Mock all external dependencies
        self.ray_mock = Mock()
        self.ray_mock.is_initialized.return_value = False
        self.ray_mock.init.return_value = {"redis_address": "test:8265"}
        self.ray_mock.shutdown.return_value = None
        self.ray_mock.nodes.return_value = []
        self.ray_mock.cluster_resources.return_value = {"CPU": 4}
        self.ray_mock.available_resources.return_value = {"CPU": 2}

        # Inject mocks
        self.manager._ray = self.ray_mock
        self.manager._RAY_AVAILABLE = True

    @pytest.mark.asyncio
    async def test_create_cluster_prompt(self):
        """Test cluster creation through natural language prompt."""
        prompt = "create a local cluster with 4 CPUs"

        # Mock ActionParser to return structured action
        with patch("ray_mcp.managers.cluster_manager.ActionParser") as parser_mock:
            parser_mock.parse_cluster_action.return_value = {
                "operation": "create",
                "cpus": 4,
                "gpus": 0,
                "dashboard_port": 8265,
            }

            result = await self.manager.execute_request(prompt)

            # Verify prompt was parsed
            parser_mock.parse_cluster_action.assert_called_once_with(prompt)

            # Verify Ray was initialized
            self.ray_mock.init.assert_called_once()

            # Verify successful response
            assert result["status"] == "success"
            assert "cluster_address" in result
            assert result["message"] == "Ray cluster created successfully"

    @pytest.mark.asyncio
    async def test_connect_cluster_prompt(self):
        """Test connecting to existing cluster."""
        prompt = "connect to cluster at 192.168.1.100:10001"

        with patch("ray_mcp.managers.cluster_manager.ActionParser") as parser_mock:
            parser_mock.parse_cluster_action.return_value = {
                "operation": "connect",
                "address": "192.168.1.100:10001",
            }

            result = await self.manager.execute_request(prompt)

            # Verify connection attempt
            self.ray_mock.init.assert_called_once_with(address="192.168.1.100:10001")
            assert result["status"] == "success"
            assert "Connected to Ray cluster" in result["message"]

    @pytest.mark.asyncio
    async def test_inspect_cluster_prompt(self):
        """Test cluster inspection."""
        # Set up cluster as running
        self.manager._ray.is_initialized.return_value = True
        self.manager._cluster_address = "test:8265"

        prompt = "inspect cluster status"

        with patch("ray_mcp.managers.cluster_manager.ActionParser") as parser_mock:
            parser_mock.parse_cluster_action.return_value = {"operation": "inspect"}

            result = await self.manager.execute_request(prompt)

            assert result["status"] == "success"
            assert result["cluster_status"] == "running"
            assert "nodes" in result
            assert "resources" in result

    @pytest.mark.asyncio
    async def test_stop_cluster_prompt(self):
        """Test cluster shutdown."""
        self.manager._ray.is_initialized.return_value = True

        prompt = "stop the current cluster"

        with patch("ray_mcp.managers.cluster_manager.ActionParser") as parser_mock:
            parser_mock.parse_cluster_action.return_value = {"operation": "stop"}

            result = await self.manager.execute_request(prompt)

            # Verify shutdown was called
            self.ray_mock.shutdown.assert_called_once()
            assert result["status"] == "success"
            assert "stopped successfully" in result["message"]

    @pytest.mark.asyncio
    async def test_invalid_prompt_handling(self):
        """Test handling of invalid/unparseable prompts."""
        prompt = "this is not a valid cluster command"

        with patch("ray_mcp.managers.cluster_manager.ActionParser") as parser_mock:
            parser_mock.parse_cluster_action.side_effect = ValueError(
                "Could not parse prompt"
            )

            result = await self.manager.execute_request(prompt)

            assert result["status"] == "error"
            assert "Could not parse request" in result["message"]

    @pytest.mark.asyncio
    async def test_ray_not_available_error(self):
        """Test error handling when Ray is not available."""
        self.manager._RAY_AVAILABLE = False

        prompt = "create a cluster"

        with patch("ray_mcp.managers.cluster_manager.ActionParser") as parser_mock:
            parser_mock.parse_cluster_action.return_value = {
                "operation": "create",
                "cpus": 4,
            }

            # This should return an error response from _ensure_ray_available()
            result = await self.manager.execute_request(prompt)
            assert result["status"] == "error"
            assert "Ray is not available" in result["message"]


@pytest.mark.unit
class TestJobManager:
    """Test JobManager prompt-driven interface."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = JobManager()

        # Mock Ray dependencies
        self.ray_mock = Mock()
        self.ray_mock.is_initialized.return_value = True
        self.job_client_mock = Mock()

        # Inject mocks
        self.manager._ray = self.ray_mock
        self.manager._RAY_AVAILABLE = True
        self.manager._JobSubmissionClient = Mock(return_value=self.job_client_mock)

    @pytest.mark.asyncio
    async def test_submit_job_prompt(self):
        """Test job submission through natural language."""
        prompt = "submit job with script train.py"

        # Mock job submission
        self.job_client_mock.submit_job.return_value = "raysubmit_123"

        with patch("ray_mcp.managers.job_manager.ActionParser") as parser_mock:
            parser_mock.parse_job_action.return_value = {
                "operation": "submit",
                "script": "train.py",
                "runtime_env": {},
                "metadata": {},
            }

            result = await self.manager.execute_request(prompt)

            # Verify job was submitted
            self.job_client_mock.submit_job.assert_called_once()
            assert result["status"] == "success"
            assert result["job_status"] == "submitted"
            assert result["job_id"] == "raysubmit_123"
            assert "submitted successfully" in result["message"]

    @pytest.mark.asyncio
    async def test_list_jobs_prompt(self):
        """Test listing jobs."""
        prompt = "list all running jobs"

        # Mock job list response
        mock_job_info = Mock()
        mock_job_info.status.value = "RUNNING"
        mock_job_info.entrypoint = "train.py"
        mock_job_info.start_time = "2024-01-01T00:00:00"
        mock_job_info.end_time = None
        mock_job_info.metadata = {}

        self.job_client_mock.list_jobs.return_value = {"job_123": mock_job_info}

        with patch("ray_mcp.managers.job_manager.ActionParser") as parser_mock:
            parser_mock.parse_job_action.return_value = {"operation": "list"}

            result = await self.manager.execute_request(prompt)

            assert result["status"] == "success"
            assert "jobs" in result
            assert len(result["jobs"]) == 1
            assert result["jobs"][0]["job_id"] == "job_123"
            assert result["jobs"][0]["status"] == "RUNNING"

    @pytest.mark.asyncio
    async def test_cancel_job_prompt(self):
        """Test job cancellation."""
        prompt = "cancel job raysubmit_456"

        self.job_client_mock.stop_job.return_value = True

        with patch("ray_mcp.managers.job_manager.ActionParser") as parser_mock:
            parser_mock.parse_job_action.return_value = {
                "operation": "cancel",
                "job_id": "raysubmit_456",
            }

            result = await self.manager.execute_request(prompt)

            self.job_client_mock.stop_job.assert_called_once_with("raysubmit_456")
            assert result["status"] == "success"
            assert "cancelled successfully" in result["message"]

    @pytest.mark.asyncio
    async def test_get_job_logs_prompt(self):
        """Test retrieving job logs."""
        prompt = "get logs for job raysubmit_789"

        self.job_client_mock.get_job_logs.return_value = (
            "Training started\\nEpoch 1 complete"
        )

        with patch("ray_mcp.managers.job_manager.ActionParser") as parser_mock:
            parser_mock.parse_job_action.return_value = {
                "operation": "logs",
                "job_id": "raysubmit_789",
            }

            result = await self.manager.execute_request(prompt)

            assert result["status"] == "success"
            assert result["job_id"] == "raysubmit_789"
            assert "Training started" in result["logs"]

    @pytest.mark.asyncio
    async def test_ray_not_running_error(self):
        """Test error when Ray cluster is not running."""
        self.manager._ray.is_initialized.return_value = False

        prompt = "submit job with script test.py"

        with patch("ray_mcp.managers.job_manager.ActionParser") as parser_mock:
            parser_mock.parse_job_action.return_value = {
                "operation": "submit",
                "script": "test.py",
            }

            result = await self.manager.execute_request(prompt)

            assert result["status"] == "error"
            assert "Ray cluster is not running" in result["message"]


@pytest.mark.unit
class TestUnifiedManager:
    """Test RayUnifiedManager routing and composition."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = RayUnifiedManager()

        # Mock all the specialized managers
        self.cluster_manager_mock = AsyncMock()
        self.job_manager_mock = AsyncMock()
        self.cloud_manager_mock = AsyncMock()
        self.kubernetes_manager_mock = AsyncMock()
        self.kuberay_cluster_mock = AsyncMock()
        self.kuberay_job_mock = AsyncMock()

        # Inject mocks
        self.manager._cluster_manager = self.cluster_manager_mock
        self.manager._job_manager = self.job_manager_mock
        self.manager._cloud_provider_manager = self.cloud_manager_mock
        self.manager._kubernetes_manager = self.kubernetes_manager_mock
        self.manager._kuberay_cluster_manager = self.kuberay_cluster_mock
        self.manager._kuberay_job_manager = self.kuberay_job_mock

    @pytest.mark.asyncio
    async def test_route_local_cluster_request(self):
        """Test routing local cluster requests to ClusterManager."""
        prompt = "create a local cluster with 4 CPUs"

        self.cluster_manager_mock.execute_request.return_value = {
            "status": "success",
            "message": "Cluster created",
        }

        result = await self.manager.handle_cluster_request(prompt)

        # Verify it was routed to cluster manager
        self.cluster_manager_mock.execute_request.assert_called_once_with(prompt)
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_route_kubernetes_cluster_request(self):
        """Test routing Kubernetes cluster requests."""
        prompt = "connect to kubernetes cluster with context my-cluster"

        self.kubernetes_manager_mock.execute_request.return_value = {
            "status": "success",
            "message": "Connected to Kubernetes",
        }

        result = await self.manager.handle_cluster_request(prompt)

        # Should route to kubernetes manager (not kuberay because no "ray" keyword)
        self.kubernetes_manager_mock.execute_request.assert_called_once_with(prompt)
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_route_kuberay_cluster_request(self):
        """Test routing KubeRay cluster requests."""
        prompt = "create Ray cluster named ml-cluster with 3 workers on kubernetes"

        self.kuberay_cluster_mock.execute_request.return_value = {
            "status": "success",
            "message": "KubeRay cluster created",
        }

        result = await self.manager.handle_cluster_request(prompt)

        # Should route to kuberay cluster manager (contains both "kubernetes" and "ray")
        self.kuberay_cluster_mock.execute_request.assert_called_once_with(prompt)
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_route_local_job_request(self):
        """Test routing local job requests to JobManager."""
        prompt = "submit job with script train.py"

        self.job_manager_mock.execute_request.return_value = {
            "status": "success",
            "job_id": "raysubmit_123",
        }

        result = await self.manager.handle_job_request(prompt)

        self.job_manager_mock.execute_request.assert_called_once_with(prompt)
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_route_kuberay_job_request(self):
        """Test routing KubeRay job requests."""
        prompt = "create Ray job with training script train.py on kubernetes"

        self.kuberay_job_mock.execute_request.return_value = {
            "status": "success",
            "job_name": "training-job",
        }

        result = await self.manager.handle_job_request(prompt)

        self.kuberay_job_mock.execute_request.assert_called_once_with(prompt)
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_route_cloud_request(self):
        """Test routing cloud requests to CloudProviderManager."""
        prompt = "authenticate with GCP project ml-experiments"

        self.cloud_manager_mock.execute_request.return_value = {
            "status": "success",
            "message": "Authenticated with GCP",
        }

        result = await self.manager.handle_cloud_request(prompt)

        self.cloud_manager_mock.execute_request.assert_called_once_with(prompt)
        assert result["status"] == "success"

    def test_kubernetes_environment_detection(self):
        """Test the _is_kubernetes_environment helper method."""
        # Test Kubernetes keywords
        assert self.manager._is_kubernetes_environment("connect to kubernetes cluster")
        assert self.manager._is_kubernetes_environment("list namespaces in k8s")
        assert self.manager._is_kubernetes_environment("create kuberay cluster")
        assert self.manager._is_kubernetes_environment("use kubectl to get pods")

        # Test non-Kubernetes prompts
        assert not self.manager._is_kubernetes_environment("create local cluster")
        assert not self.manager._is_kubernetes_environment("submit job to ray")
        assert not self.manager._is_kubernetes_environment("authenticate with GCP")

    @pytest.mark.asyncio
    async def test_error_propagation_from_cluster_manager(self):
        """Test that errors from cluster managers are properly propagated."""
        prompt = "create local cluster"

        # Mock cluster manager returning error
        self.cluster_manager_mock.execute_request.return_value = {
            "status": "error",
            "message": "Ray is not available",
        }

        result = await self.manager.handle_cluster_request(prompt)

        # Error should be propagated
        assert result["status"] == "error"
        assert "Ray is not available" in result["message"]

    @pytest.mark.asyncio
    async def test_error_propagation_from_job_manager(self):
        """Test that errors from job managers are properly propagated."""
        prompt = "submit job with script train.py"

        # Mock job manager returning error
        self.job_manager_mock.execute_request.return_value = {
            "status": "error",
            "message": "Ray cluster is not running",
        }

        result = await self.manager.handle_job_request(prompt)

        # Error should be propagated
        assert result["status"] == "error"
        assert "Ray cluster is not running" in result["message"]

    @pytest.mark.asyncio
    async def test_error_propagation_from_cloud_manager(self):
        """Test that errors from cloud manager are properly propagated."""
        prompt = "authenticate with GCP"

        # Mock cloud manager returning error
        self.cloud_manager_mock.execute_request.return_value = {
            "status": "error",
            "message": "Invalid credentials",
        }

        result = await self.manager.handle_cloud_request(prompt)

        # Error should be propagated
        assert result["status"] == "error"
        assert "Invalid credentials" in result["message"]

    @pytest.mark.asyncio
    async def test_exception_handling_in_cluster_request(self):
        """Test that exceptions in cluster managers are handled gracefully."""
        prompt = "create local cluster"

        # Mock cluster manager raising exception
        self.cluster_manager_mock.execute_request.side_effect = Exception(
            "Unexpected error"
        )

        result = await self.manager.handle_cluster_request(prompt)

        # Should return error response (not raise exception)
        assert result["status"] == "error"
        assert "Unexpected error" in result["message"]

    @pytest.mark.asyncio
    async def test_exception_handling_in_job_request(self):
        """Test that exceptions in job managers are handled gracefully."""
        prompt = "list jobs"

        # Mock job manager raising exception
        self.job_manager_mock.execute_request.side_effect = Exception(
            "Connection error"
        )

        result = await self.manager.handle_job_request(prompt)

        # Should return error response (not raise exception)
        assert result["status"] == "error"
        assert "Connection error" in result["message"]

    @pytest.mark.asyncio
    async def test_exception_handling_in_cloud_request(self):
        """Test that exceptions in cloud manager are handled gracefully."""
        prompt = "list clusters"

        # Mock cloud manager raising exception
        self.cloud_manager_mock.execute_request.side_effect = Exception(
            "Authentication failed"
        )

        result = await self.manager.handle_cloud_request(prompt)

        # Should return error response (not raise exception)
        assert result["status"] == "error"
        assert "Authentication failed" in result["message"]

    def test_kubernetes_environment_detection_edge_cases(self):
        """Test edge cases in Kubernetes environment detection."""
        # Test case sensitivity
        assert self.manager._is_kubernetes_environment("Connect to KUBERNETES cluster")
        assert self.manager._is_kubernetes_environment("Create K8S deployment")

        # Test mixed case
        assert self.manager._is_kubernetes_environment("Deploy to KubeRay")

        # Test partial matches should not match
        assert not self.manager._is_kubernetes_environment("use cubes for analysis")
        assert not self.manager._is_kubernetes_environment("kubernetic is a tool")

        # Test empty/invalid inputs
        assert not self.manager._is_kubernetes_environment("")
        assert not self.manager._is_kubernetes_environment("   ")

    @pytest.mark.asyncio
    async def test_ray_keyword_detection_in_cluster_requests(self):
        """Test that Ray keyword correctly routes to KubeRay cluster manager."""
        # Test Ray + Kubernetes -> KubeRay
        kubernetes_ray_prompts = [
            "create Ray cluster on kubernetes",
            "deploy ray cluster in k8s",
            "scale ray cluster with kuberay",
            "connect to Ray cluster in namespace production",
        ]

        for prompt in kubernetes_ray_prompts:
            self.kuberay_cluster_mock.execute_request.return_value = {
                "status": "success",
                "message": "KubeRay operation",
            }

            result = await self.manager.handle_cluster_request(prompt)

            # Should route to KubeRay cluster manager
            self.kuberay_cluster_mock.execute_request.assert_called_with(prompt)
            assert result["status"] == "success"
            self.kuberay_cluster_mock.reset_mock()

    @pytest.mark.asyncio
    async def test_kubernetes_without_ray_routes_to_kubernetes_manager(self):
        """Test that Kubernetes without Ray routes to kubernetes manager."""
        kubernetes_only_prompts = [
            "connect to kubernetes cluster",
            "list k8s namespaces",
            "check kubectl context",
            "use kubeconfig file",
        ]

        for prompt in kubernetes_only_prompts:
            self.kubernetes_manager_mock.execute_request.return_value = {
                "status": "success",
                "message": "Kubernetes operation",
            }

            result = await self.manager.handle_cluster_request(prompt)

            # Should route to kubernetes manager
            self.kubernetes_manager_mock.execute_request.assert_called_with(prompt)
            assert result["status"] == "success"
            self.kubernetes_manager_mock.reset_mock()

    @pytest.mark.asyncio
    async def test_job_routing_logic(self):
        """Test job request routing logic."""
        # Local job should go to job manager
        local_prompt = "submit job with script train.py"
        self.job_manager_mock.execute_request.return_value = {
            "status": "success",
            "job_id": "local_job_123",
        }

        result = await self.manager.handle_job_request(local_prompt)

        self.job_manager_mock.execute_request.assert_called_once_with(local_prompt)
        assert result["status"] == "success"

        # Kubernetes job should go to kuberay job manager
        k8s_prompt = "create job in kubernetes namespace"
        self.kuberay_job_mock.execute_request.return_value = {
            "status": "success",
            "job_name": "k8s_job_456",
        }

        result = await self.manager.handle_job_request(k8s_prompt)

        self.kuberay_job_mock.execute_request.assert_called_once_with(k8s_prompt)
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_cloud_routing_always_goes_to_cloud_manager(self):
        """Test that cloud requests always go to cloud provider manager."""
        cloud_prompts = [
            "authenticate with GCP",
            "list GKE clusters",
            "connect to cloud cluster",
            "check cloud environment",
        ]

        for prompt in cloud_prompts:
            self.cloud_manager_mock.execute_request.return_value = {
                "status": "success",
                "message": "Cloud operation",
            }

            result = await self.manager.handle_cloud_request(prompt)

            # Should always route to cloud manager
            self.cloud_manager_mock.execute_request.assert_called_with(prompt)
            assert result["status"] == "success"
            self.cloud_manager_mock.reset_mock()

    @pytest.mark.asyncio
    async def test_manager_initialization(self):
        """Test that all managers are properly initialized."""
        # Create a new manager to test initialization
        new_manager = RayUnifiedManager()

        # Check that all managers are initialized
        assert new_manager._cluster_manager is not None
        assert new_manager._job_manager is not None
        assert new_manager._log_manager is not None
        assert new_manager._kubernetes_manager is not None
        assert new_manager._kuberay_cluster_manager is not None
        assert new_manager._kuberay_job_manager is not None
        assert new_manager._cloud_provider_manager is not None

    @pytest.mark.asyncio
    async def test_concurrent_requests_handling(self):
        """Test that unified manager can handle concurrent requests."""
        import asyncio

        # Set up mock responses
        self.cluster_manager_mock.execute_request.return_value = {
            "status": "success",
            "type": "cluster",
        }
        self.job_manager_mock.execute_request.return_value = {
            "status": "success",
            "type": "job",
        }
        self.cloud_manager_mock.execute_request.return_value = {
            "status": "success",
            "type": "cloud",
        }

        # Make concurrent requests
        tasks = [
            self.manager.handle_cluster_request("create local cluster"),
            self.manager.handle_job_request("submit job"),
            self.manager.handle_cloud_request("authenticate with GCP"),
        ]

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert len(results) == 3
        assert all(result["status"] == "success" for result in results)

        # Check that different types were handled
        types = [result["type"] for result in results]
        assert "cluster" in types
        assert "job" in types
        assert "cloud" in types


@pytest.mark.unit
class TestCloudProviderManager:
    """Test CloudProviderManager prompt-driven interface."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = CloudProviderManager()

        # Mock dependencies
        self.gke_manager_mock = AsyncMock()
        self.manager._gke_manager = self.gke_manager_mock

        # Mock config manager
        self.config_mock = Mock()
        self.manager._config_manager = self.config_mock

    @pytest.mark.asyncio
    async def test_authenticate_gcp_prompt(self):
        """Test GCP authentication through prompt."""
        prompt = "authenticate with GCP project ml-experiments"

        self.gke_manager_mock.execute_request.return_value = {
            "status": "success",
            "message": "Authenticated with GCP",
        }

        with patch("ray_mcp.cloud.cloud_provider_manager.ActionParser") as parser_mock:
            parser_mock.parse_cloud_action.return_value = {
                "operation": "authenticate",
                "provider": "gcp",
                "project_id": "ml-experiments",
            }

            result = await self.manager.execute_request(prompt)

            # Should delegate to GKE manager
            self.gke_manager_mock.execute_request.assert_called_once()
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_list_gke_clusters_prompt(self):
        """Test listing GKE clusters."""
        prompt = "list all GKE clusters"

        self.gke_manager_mock.execute_request.return_value = {
            "status": "success",
            "clusters": [{"name": "ml-cluster", "status": "RUNNING"}],
        }

        with patch("ray_mcp.cloud.cloud_provider_manager.ActionParser") as parser_mock:
            parser_mock.parse_cloud_action.return_value = {"operation": "list_clusters"}

            result = await self.manager.execute_request(prompt)

            assert result["status"] == "success"
            assert "clusters" in result

    @pytest.mark.asyncio
    async def test_check_environment_prompt(self):
        """Test environment status checking."""
        prompt = "check cloud environment setup"

        # Mock environment detection
        self.config_mock.detect_environment.return_value = {
            "gke_available": True,
            "kubernetes_available": True,
            "providers": ["gke"],
            "default_provider": "gke",
        }
        self.config_mock.validate_config.return_value = {"valid": True}

        with patch("ray_mcp.cloud.cloud_provider_manager.ActionParser") as parser_mock:
            parser_mock.parse_cloud_action.return_value = {
                "operation": "check_environment"
            }

            result = await self.manager.execute_request(prompt)

            assert result["status"] == "success"
            assert "environment" in result
            assert "providers" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
