#!/usr/bin/env python3
"""Tests for prompt parsing functionality in the new architecture.

This file tests the natural language parsing capabilities that replace
the complex schema validation system. Focus on comprehensive coverage
of parsing patterns and edge cases.
"""

import pytest

from ray_mcp.parsers import ActionParser


@pytest.mark.fast
class TestClusterActionParsing:
    """Test cluster operation parsing from natural language prompts."""

    def test_cluster_creation_parsing(self):
        """Test parsing of cluster creation commands."""
        test_cases = [
            (
                "Create a local Ray cluster with 4 CPUs",
                {
                    "operation": "create",
                    "environment": "local",
                    "resources": {"cpu": 4},
                },
            ),
            (
                "Start Ray cluster with head only",
                {"operation": "create", "environment": "local", "head_only": True},
            ),
            (
                "Deploy a Kubernetes Ray cluster",
                {"operation": "create", "environment": "kubernetes"},
            ),
            (
                "Initialize cluster my-cluster with 8 CPUs",
                {"operation": "create", "name": "my-cluster", "resources": {"cpu": 8}},
            ),
        ]

        for prompt, expected in test_cases:
            result = ActionParser.parse_cluster_action(prompt)
            assert result["operation"] == expected["operation"]
            if "environment" in expected:
                assert result["environment"] == expected["environment"]
            if "resources" in expected:
                assert result["resources"] == expected["resources"]
            if "head_only" in expected:
                assert result["head_only"] == expected["head_only"]
            if "name" in expected:
                assert result["name"] == expected["name"]

    def test_cluster_connection_parsing(self):
        """Test parsing of cluster connection commands."""
        test_cases = [
            (
                "Connect to Ray cluster at 127.0.0.1:10001",
                {"operation": "connect", "address": "127.0.0.1:10001"},
            ),
            ("Connect to existing cluster", {"operation": "connect", "address": None}),
        ]

        for prompt, expected in test_cases:
            result = ActionParser.parse_cluster_action(prompt)
            assert result["operation"] == expected["operation"]
            assert result.get("address") == expected["address"]

    def test_cluster_management_parsing(self):
        """Test parsing of cluster management commands."""
        test_cases = [
            ("Stop Ray cluster", {"operation": "stop", "name": None}),
            (
                "Scale cluster to 5 workers",
                {"operation": "scale", "workers": 5, "name": None},
            ),
            (
                "Scale cluster named my-cluster to 3 workers",
                {"operation": "scale", "name": "my-cluster", "workers": 3},
            ),
            ("Inspect cluster status", {"operation": "inspect", "name": None}),
            ("List all clusters", {"operation": "list"}),
        ]

        for prompt, expected in test_cases:
            result = ActionParser.parse_cluster_action(prompt)
            assert result["operation"] == expected["operation"]
            for key, value in expected.items():
                if key != "operation":
                    assert result.get(key) == value

    def test_invalid_cluster_prompts(self):
        """Test handling of invalid or unclear cluster prompts."""
        invalid_prompts = [
            "",
            "hello world",
            "something about databases",
            "delete all files",
        ]

        for prompt in invalid_prompts:
            with pytest.raises(ValueError, match="Cannot understand cluster action"):
                ActionParser.parse_cluster_action(prompt)


@pytest.mark.fast
class TestJobActionParsing:
    """Test job operation parsing from natural language prompts."""

    def test_job_submission_parsing(self):
        """Test parsing of job submission commands."""
        test_cases = [
            (
                "Submit job from GitHub repo https://github.com/user/repo",
                {
                    "operation": "submit",
                    "source": "https://github.com/user/repo",
                    "script": None,  # No .py file in this prompt
                },
            ),
            (
                "Run job with script train.py from repo",
                {"operation": "submit", "script": "train.py", "source": None},
            ),
            (
                "Execute job from https://github.com/rayproject/ray with entrypoint examples/basic.py",
                {
                    "operation": "submit",
                    "source": "https://github.com/rayproject/ray",
                    "script": "examples/basic.py",
                },
            ),
        ]

        for prompt, expected in test_cases:
            result = ActionParser.parse_job_action(prompt)
            assert result["operation"] == expected["operation"]
            for key, value in expected.items():
                if key != "operation":
                    assert result.get(key) == value

    def test_job_management_parsing(self):
        """Test parsing of job management commands."""
        test_cases = [
            ("List all running jobs", {"operation": "list"}),
            (
                "Show job status for job123",
                {"operation": "inspect", "job_id": "123"},  # Extracted from "job123"
            ),
            ("Get logs for job 456", {"operation": "logs", "job_id": "456"}),
            (
                "Cancel job job789",
                {
                    "operation": "cancel",
                    "job_id": "job789",  # Pattern matches "job job789" -> "job789"
                },
            ),
            (
                "Show logs with errors filtered for job my-job",
                {"operation": "logs", "job_id": "my-job", "filter_errors": True},
            ),
        ]

        for prompt, expected in test_cases:
            result = ActionParser.parse_job_action(prompt)
            assert result["operation"] == expected["operation"]
            for key, value in expected.items():
                if key != "operation":
                    assert result.get(key) == value

    def test_invalid_job_prompts(self):
        """Test handling of invalid or unclear job prompts."""
        invalid_prompts = [
            "",
            "cluster operations",
            "authenticate with cloud",
            "random text here",
        ]

        for prompt in invalid_prompts:
            with pytest.raises(ValueError, match="Cannot understand job action"):
                ActionParser.parse_job_action(prompt)


@pytest.mark.fast
class TestCloudActionParsing:
    """Test cloud operation parsing from natural language prompts."""

    def test_cloud_authentication_parsing(self):
        """Test parsing of cloud authentication commands."""
        test_cases = [
            (
                "Authenticate with GCP",
                {"operation": "authenticate", "provider": "gke", "project": None},
            ),
            (
                "Login to Google Cloud project my-project",
                {
                    "operation": "authenticate",
                    "provider": "gke",
                    "project": "my-project",
                },
            ),
            (
                "Connect to GKE",
                {"operation": "authenticate", "provider": "gke", "project": None},
            ),
        ]

        for prompt, expected in test_cases:
            result = ActionParser.parse_cloud_action(prompt)
            assert result["operation"] == expected["operation"]
            for key, value in expected.items():
                if key != "operation":
                    assert result.get(key) == value

    def test_cloud_cluster_operations_parsing(self):
        """Test parsing of cloud cluster operations."""
        test_cases = [
            (
                "List Kubernetes clusters",
                {"operation": "list_clusters", "provider": "gke"},
            ),
            (
                "Connect to GKE cluster named my-gke-cluster",
                {
                    "operation": "connect_cluster",
                    "cluster_name": "my-gke-cluster",
                    "provider": "gke",
                },
            ),
            (
                "Create GKE cluster named test-cluster in zone us-central1-a",
                {
                    "operation": "create_cluster",
                    "cluster_name": "test-cluster",
                    "provider": "gke",
                    "zone": "us-central1-a",
                },
            ),
            ("Check environment status", {"operation": "check_environment"}),
        ]

        for prompt, expected in test_cases:
            result = ActionParser.parse_cloud_action(prompt)
            assert result["operation"] == expected["operation"]
            for key, value in expected.items():
                if key != "operation":
                    assert result.get(key) == value

    def test_invalid_cloud_prompts(self):
        """Test handling of invalid or unclear cloud prompts."""
        invalid_prompts = [
            "",
            "start ray cluster",
            "submit job",
            "meaningless text",
        ]

        for prompt in invalid_prompts:
            with pytest.raises(ValueError, match="Cannot understand cloud action"):
                ActionParser.parse_cloud_action(prompt)


@pytest.mark.fast
class TestParameterExtraction:
    """Test parameter extraction patterns across all parsers."""

    def test_resource_extraction(self):
        """Test extraction of resource specifications."""
        test_cases = [
            ("cluster with 4 CPUs", {"cpu": 4}),
            ("8 CPU cluster", {"cpu": 8}),
            ("cluster using 16 cores", {"cpu": 16}),
            ("2 cpu setup", {"cpu": 2}),
        ]

        for prompt, expected in test_cases:
            result = ActionParser.parse_cluster_action(f"Create {prompt}")
            assert result.get("resources") == expected

    def test_job_id_extraction(self):
        """Test extraction of job identifiers."""
        test_cases = [
            ("job 123", "123"),  # Pattern extracts after "job"
            ("job my-job-name", "my-job-name"),
            ("job job_with_underscores", "job_with_underscores"),
            ("job simple-job", "simple-job"),
        ]

        for prompt_suffix, expected in test_cases:
            result = ActionParser.parse_job_action(f"Show status for {prompt_suffix}")
            assert result.get("job_id") == expected

    def test_url_extraction(self):
        """Test extraction of GitHub URLs and paths."""
        test_cases = [
            ("https://github.com/user/repo", "https://github.com/user/repo"),
            ("github.com/rayproject/ray", None),  # Must have https:// prefix
        ]

        for url, expected in test_cases:
            result = ActionParser.parse_job_action(f"Submit job from {url}")
            assert result.get("source") == expected

    def test_cluster_name_extraction(self):
        """Test extraction of cluster names."""
        test_cases = [
            ("cluster named my-cluster", "my-cluster"),
            ("cluster called test_cluster", "test_cluster"),
            ("cluster named production-ray-cluster", "production-ray-cluster"),
        ]

        for phrase, expected in test_cases:
            result = ActionParser.parse_cluster_action(f"Scale {phrase} to 5 workers")
            assert result.get("name") == expected


@pytest.mark.fast
class TestParsingEdgeCases:
    """Test edge cases and error handling in prompt parsing."""

    def test_case_insensitive_operations(self):
        """Test that operations are case insensitive."""
        test_cases = [
            ("CREATE a cluster", "create"),
            ("List Jobs", "list"),
            ("AUTHENTICATE with gcp", "authenticate"),
        ]

        parsers = [
            (ActionParser.parse_cluster_action, "CREATE a cluster"),
            (ActionParser.parse_job_action, "List Jobs"),
            (ActionParser.parse_cloud_action, "AUTHENTICATE with gcp"),
        ]

        for parser, prompt in parsers:
            result = parser(prompt)
            # Operations should be normalized to lowercase
            assert result["operation"].islower()

    def test_whitespace_handling(self):
        """Test handling of extra whitespace in prompts."""
        test_cases = [
            "  create cluster  ",
            "\tlist jobs\n",
            "   authenticate    with   gcp   ",
        ]

        # Should not raise errors despite extra whitespace
        ActionParser.parse_cluster_action("  create cluster  ")
        ActionParser.parse_job_action("\tlist jobs\n")
        ActionParser.parse_cloud_action("   authenticate    with   gcp   ")

    def test_multiple_matches_priority(self):
        """Test behavior when multiple operation patterns could match."""
        # This tests the precedence in regex patterns (first match wins)
        ambiguous_prompts = [
            "create and list clusters",  # Should prioritize "create"
            "list and submit jobs",  # Should prioritize "list" (due to order)
            "connect and authenticate with gcp",  # Should prioritize "authenticate"
        ]

        # These should parse successfully with the first matched operation
        result1 = ActionParser.parse_cluster_action("create and list clusters")
        assert result1["operation"] == "create"

        result2 = ActionParser.parse_job_action("list and submit jobs")
        assert result2["operation"] == "list"  # List comes first in parsing order

        result3 = ActionParser.parse_cloud_action("connect and authenticate with gcp")
        assert result3["operation"] == "authenticate"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
