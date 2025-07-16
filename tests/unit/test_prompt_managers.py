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

    @pytest.mark.asyncio
    async def test_create_cluster_prompt(self):
        """Test cluster creation through natural language prompt."""
        prompt = "create a local cluster with 4 CPUs"

        # Mock the entire Ray import and ensure RAY_AVAILABLE is True
        with patch("ray_mcp.foundation.import_utils.RAY_AVAILABLE", True):
            with patch("ray_mcp.foundation.import_utils.ray") as ray_mock:
                ray_mock.is_initialized.return_value = False
                ray_mock.init.return_value = None

                # Mock get_parser
                with patch(
                    "ray_mcp.managers.cluster_manager.get_parser"
                ) as parser_mock:
                    mock_llm_parser = Mock()
                    mock_llm_parser.parse_cluster_action.return_value = {
                        "operation": "create",
                        "cpus": 4,
                        "gpus": 0,
                        "dashboard_port": 8265,
                    }
                    parser_mock.return_value = mock_llm_parser

                    result = await self.manager.execute_request(prompt)

                    # Verify successful response
                    assert result["status"] == "success"
                    assert "cluster_address" in result
                    assert "Ray cluster created successfully" in result["message"]

    @pytest.mark.asyncio
    async def test_invalid_prompt_handling(self):
        """Test handling of invalid/unparseable prompts."""
        prompt = "this is not a valid cluster command"

        with patch("ray_mcp.managers.cluster_manager.get_parser") as parser_mock:
            mock_llm_parser = Mock()
            mock_llm_parser.parse_cluster_action.side_effect = ValueError(
                "Could not parse prompt"
            )
            parser_mock.return_value = mock_llm_parser

            result = await self.manager.execute_request(prompt)

            assert result["status"] == "error"
            assert "Could not parse request" in result["message"]


@pytest.mark.unit
class TestJobManager:
    """Test JobManager prompt-driven interface."""

    def setup_method(self):
        """Set up test fixtures."""
        # Mock the unified manager parameter
        with patch(
            "ray_mcp.managers.unified_manager.RayUnifiedManager"
        ) as unified_mock:
            self.manager = JobManager(unified_manager=unified_mock)

    @pytest.mark.asyncio
    async def test_invalid_prompt_handling(self):
        """Test handling of invalid/unparseable prompts."""
        prompt = "this is not a valid job command"

        with patch("ray_mcp.managers.job_manager.get_parser") as parser_mock:
            mock_llm_parser = Mock()
            mock_llm_parser.parse_job_action.side_effect = ValueError(
                "Could not parse prompt"
            )
            parser_mock.return_value = mock_llm_parser

            result = await self.manager.execute_request(prompt)

            assert result["status"] == "error"
            assert "Could not parse request" in result["message"]


@pytest.mark.unit
class TestCloudProviderManager:
    """Test CloudProviderManager prompt-driven interface."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = CloudProviderManager()

    @pytest.mark.asyncio
    async def test_invalid_prompt_handling(self):
        """Test handling of invalid/unparseable prompts."""
        prompt = "this is not a valid cloud command"

        with patch("ray_mcp.cloud.cloud_provider_manager.get_parser") as parser_mock:
            mock_llm_parser = Mock()
            mock_llm_parser.parse_cloud_action.side_effect = ValueError(
                "Could not parse prompt"
            )
            parser_mock.return_value = mock_llm_parser

            result = await self.manager.execute_request(prompt)

            assert result["status"] == "error"
            assert "Could not parse request" in result["message"]


@pytest.mark.unit
class TestRayUnifiedManager:
    """Test RayUnifiedManager as the central orchestrator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = RayUnifiedManager()

    @pytest.mark.asyncio
    async def test_cluster_operation_delegation(self):
        """Test that cluster operations are delegated to appropriate manager."""
        # Mock the cluster manager's execute_request method
        expected_response = {
            "status": "success",
            "message": "Cluster created",
        }

        with patch.object(self.manager, "_cluster_manager") as cluster_mock:
            cluster_mock.execute_request = AsyncMock(return_value=expected_response)

            # Mock the Kubernetes connectivity check to ensure it returns False
            with patch.object(
                self.manager, "_is_kubernetes_connected", return_value=False
            ):
                result = await self.manager.handle_cluster_request("create cluster")

                cluster_mock.execute_request.assert_called_once_with("create cluster")
                assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_job_operation_delegation(self):
        """Test that job operations are delegated to appropriate manager."""
        expected_response = {
            "status": "success",
            "message": "Job submitted",
        }

        with patch.object(self.manager, "_job_manager") as job_mock:
            job_mock.execute_request = AsyncMock(return_value=expected_response)

            # Mock the Kubernetes connectivity check to ensure it returns False
            with patch.object(
                self.manager, "_is_kubernetes_connected", return_value=False
            ):
                result = await self.manager.handle_job_request("submit job")

                job_mock.execute_request.assert_called_once_with("submit job")
                assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_cloud_operation_delegation(self):
        """Test that cloud operations are delegated to appropriate manager."""
        expected_response = {
            "status": "success",
            "message": "Authentication successful",
        }

        with patch.object(self.manager, "_cloud_provider_manager") as cloud_mock:
            cloud_mock.execute_request = AsyncMock(return_value=expected_response)

            result = await self.manager.handle_cloud_request("authenticate with GCP")

            cloud_mock.execute_request.assert_called_once_with("authenticate with GCP")
            assert result["status"] == "success"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
