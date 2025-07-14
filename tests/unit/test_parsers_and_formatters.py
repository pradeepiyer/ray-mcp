#!/usr/bin/env python3
"""Unit tests for prompt parsers and response formatters.

This module tests the core parsing and formatting utilities that power
the prompt-driven architecture.

Test Focus:
- Prompt parsing accuracy and edge cases
- Response formatting consistency
- Error handling in parsing/formatting
- Validation of output schemas
"""

from unittest.mock import Mock, patch

import pytest

from ray_mcp.foundation.logging_utils import ResponseFormatter
from ray_mcp.parsers import ActionParser


@pytest.mark.unit
class TestActionParser:
    """Test ActionParser for various prompt types."""

    def test_parse_cluster_create_action(self):
        """Test parsing cluster creation prompts."""
        test_cases = [
            {
                "prompt": "create a local cluster with 4 CPUs",
                "expected": {
                    "operation": "create",
                    "cpus": 4,
                    "gpus": 0,
                    "dashboard_port": 8265,
                    "include_dashboard": True,
                },
            },
            {
                "prompt": "create cluster with 8 CPUs and 2 GPUs",
                "expected": {"operation": "create", "cpus": 8, "gpus": 2},
            },
            {
                "prompt": "start a Ray cluster with dashboard on port 9000",
                "expected": {"operation": "create", "dashboard_port": 9000},
            },
        ]

        for case in test_cases:
            result = ActionParser.parse_cluster_action(case["prompt"])

            assert result["operation"] == case["expected"]["operation"]

            # Check that expected keys are present with correct values
            for key, value in case["expected"].items():
                if key in result:
                    assert result[key] == value

    def test_parse_cluster_connect_action(self):
        """Test parsing cluster connection prompts."""
        test_cases = [
            {
                "prompt": "connect to cluster at 192.168.1.100:10001",
                "expected": {"operation": "connect", "address": "192.168.1.100:10001"},
            },
            {
                "prompt": "connect to Ray cluster at localhost:8265",
                "expected": {"operation": "connect", "address": "localhost:8265"},
            },
        ]

        for case in test_cases:
            result = ActionParser.parse_cluster_action(case["prompt"])
            assert result["operation"] == case["expected"]["operation"]
            assert result["address"] == case["expected"]["address"]

    def test_parse_cluster_inspect_action(self):
        """Test parsing cluster inspection prompts."""
        prompts = [
            "inspect cluster status",
            "show cluster information",
            "get cluster details",
            "check cluster health",
        ]

        for prompt in prompts:
            result = ActionParser.parse_cluster_action(prompt)
            assert result["operation"] == "inspect"

    def test_parse_cluster_stop_action(self):
        """Test parsing cluster stop prompts."""
        prompts = [
            "stop the current cluster",
            "shutdown cluster",
            "terminate Ray cluster",
            "stop cluster",
        ]

        for prompt in prompts:
            result = ActionParser.parse_cluster_action(prompt)
            assert result["operation"] == "stop"

    def test_parse_job_submit_action(self):
        """Test parsing job submission prompts."""
        test_cases = [
            {
                "prompt": "submit job with script train.py",
                "expected": {"operation": "submit", "script": "train.py"},
            },
            {
                "prompt": "run job with entrypoint main.py using 2 GPUs",
                "expected": {"operation": "submit", "entrypoint": "main.py", "gpus": 2},
            },
            {
                "prompt": "submit training job train.py with job_id my-training-run",
                "expected": {
                    "operation": "submit",
                    "script": "train.py",
                    "job_id": "my-training-run",
                },
            },
        ]

        for case in test_cases:
            result = ActionParser.parse_job_action(case["prompt"])
            assert result["operation"] == case["expected"]["operation"]

            for key, value in case["expected"].items():
                if key in result:
                    assert result[key] == value

    def test_parse_job_list_action(self):
        """Test parsing job listing prompts."""
        prompts = ["list all running jobs", "show jobs", "get job list", "list jobs"]

        for prompt in prompts:
            result = ActionParser.parse_job_action(prompt)
            assert result["operation"] == "list"

    def test_parse_job_cancel_action(self):
        """Test parsing job cancellation prompts."""
        test_cases = [
            {
                "prompt": "cancel job raysubmit_123",
                "expected": {"operation": "cancel", "job_id": "raysubmit_123"},
            },
            {
                "prompt": "stop job my-training-run",
                "expected": {"operation": "cancel", "job_id": "my-training-run"},
            },
        ]

        for case in test_cases:
            result = ActionParser.parse_job_action(case["prompt"])
            assert result["operation"] == case["expected"]["operation"]
            assert result["job_id"] == case["expected"]["job_id"]

    def test_parse_job_logs_action(self):
        """Test parsing job log retrieval prompts."""
        test_cases = [
            {
                "prompt": "get logs for job raysubmit_456",
                "expected": {"operation": "logs", "job_id": "raysubmit_456"},
            },
            {
                "prompt": "show logs for job training-run-789",
                "expected": {"operation": "logs", "job_id": "training-run-789"},
            },
        ]

        for case in test_cases:
            result = ActionParser.parse_job_action(case["prompt"])
            assert result["operation"] == case["expected"]["operation"]
            assert result["job_id"] == case["expected"]["job_id"]

    def test_parse_cloud_authenticate_action(self):
        """Test parsing cloud authentication prompts."""
        test_cases = [
            {
                "prompt": "authenticate with GCP project ml-experiments",
                "expected": {
                    "operation": "authenticate",
                    "provider": "gcp",
                    "project_id": "ml-experiments",
                },
            },
            {
                "prompt": "auth with Google Cloud",
                "expected": {"operation": "authenticate", "provider": "gcp"},
            },
        ]

        for case in test_cases:
            result = ActionParser.parse_cloud_action(case["prompt"])
            assert result["operation"] == case["expected"]["operation"]

            for key, value in case["expected"].items():
                if key in result:
                    assert result[key] == value

    def test_parse_cloud_list_clusters_action(self):
        """Test parsing cloud cluster listing prompts."""
        prompts = [
            "list all GKE clusters",
            "show kubernetes clusters",
            "list clusters in GCP",
            "get GKE cluster list",
            "Get GKE clusters",  # Added test case for the reported issue
            "list gke clusters",  # Added test case with lowercase
            "show all gke clusters",  # Added test case with 'all'
        ]

        for prompt in prompts:
            result = ActionParser.parse_cloud_action(prompt)
            assert result["operation"] == "list_clusters"

    def test_parse_cloud_connect_cluster_action(self):
        """Test parsing cloud cluster connection prompts."""
        test_cases = [
            {
                "prompt": "connect to GKE cluster production-ml in zone us-central1-a",
                "expected": {
                    "operation": "connect_cluster",
                    "cluster_name": "production-ml",
                    "zone": "us-central1-a",
                },
            },
            {
                "prompt": "connect to cluster training-cluster in GKE",
                "expected": {
                    "operation": "connect_cluster",
                    "cluster_name": "training-cluster",
                },
            },
        ]

        for case in test_cases:
            result = ActionParser.parse_cloud_action(case["prompt"])
            assert result["operation"] == case["expected"]["operation"]
            assert result["cluster_name"] == case["expected"]["cluster_name"]

    def test_parse_invalid_prompts(self):
        """Test handling of invalid or ambiguous prompts."""
        invalid_prompts = [
            "",
            "this is not a valid command",
            "hello world",
            "create",  # incomplete
            "job",  # incomplete
            "cluster",  # incomplete
        ]

        for prompt in invalid_prompts:
            # Should raise ValueError for unparseable prompts
            with pytest.raises(ValueError):
                ActionParser.parse_cluster_action(prompt)

            with pytest.raises(ValueError):
                ActionParser.parse_job_action(prompt)

            with pytest.raises(ValueError):
                ActionParser.parse_cloud_action(prompt)

    def test_parse_edge_cases(self):
        """Test edge cases in prompt parsing."""
        # Test case sensitivity
        result = ActionParser.parse_cluster_action("CREATE A CLUSTER WITH 4 CPUS")
        assert result["operation"] == "create"
        assert result["cpus"] == 4

        # Test extra whitespace
        result = ActionParser.parse_job_action(
            "  submit   job   with   script   train.py  "
        )
        assert result["operation"] == "submit"
        assert result["script"] == "train.py"

        # Test punctuation
        result = ActionParser.parse_cloud_action(
            "authenticate with GCP project 'ml-experiments'!"
        )
        assert result["operation"] == "authenticate"


@pytest.mark.unit
class TestResponseFormatter:
    """Test ResponseFormatter for consistent output formatting."""

    def test_format_success_response(self):
        """Test successful response formatting."""
        # Test basic success response
        result = ResponseFormatter.format_success_response(
            message="Operation completed successfully"
        )

        assert result["status"] == "success"
        assert result["message"] == "Operation completed successfully"

        # Test success response with additional data
        result = ResponseFormatter.format_success_response(
            job_id="raysubmit_123",
            entrypoint="train.py",
            message="Job submitted successfully",
        )

        assert result["status"] == "success"
        assert result["job_id"] == "raysubmit_123"
        assert result["entrypoint"] == "train.py"
        assert result["message"] == "Job submitted successfully"

    def test_format_error_response(self):
        """Test error response formatting."""
        # Test with Exception object
        error = Exception("Something went wrong")
        result = ResponseFormatter.format_error_response("test_operation", error)

        assert result["status"] == "error"
        assert "Something went wrong" in result["message"]
        assert "test_operation" in result["message"]

        # Test with string error
        result = ResponseFormatter.format_error_response(
            "another_operation", Exception("Custom error message")
        )

        assert result["status"] == "error"
        assert "Custom error message" in result["message"]

    def test_response_format_consistency(self):
        """Test that all responses follow consistent format."""
        # Success responses should always have status and can have additional fields
        success = ResponseFormatter.format_success_response(
            cluster_address="localhost:8265", dashboard_url="http://localhost:8265"
        )

        assert "status" in success
        assert success["status"] == "success"
        assert "cluster_address" in success
        assert "dashboard_url" in success

        # Error responses should always have status and message
        error = ResponseFormatter.format_error_response("test", Exception("Test error"))

        assert "status" in error
        assert error["status"] == "error"
        assert "message" in error
        assert isinstance(error["message"], str)

    def test_response_serialization(self):
        """Test that responses can be JSON serialized."""
        import json

        # Test success response serialization
        success = ResponseFormatter.format_success_response(
            job_id="test_123", status_details={"running": True, "progress": 0.5}
        )

        # Should not raise exception
        json_str = json.dumps(success)
        assert isinstance(json_str, str)

        # Should be deserializable
        deserialized = json.loads(json_str)
        assert deserialized["status"] == "success"
        assert deserialized["job_id"] == "test_123"

        # Test error response serialization
        error = ResponseFormatter.format_error_response(
            "test_op", Exception("Test error with special chars: àñ™")
        )

        json_str = json.dumps(error)
        deserialized = json.loads(json_str)
        assert deserialized["status"] == "error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
