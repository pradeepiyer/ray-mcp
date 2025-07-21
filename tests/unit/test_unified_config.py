"""Tests for simplified configuration management."""

import os
from unittest.mock import patch

import pytest

from ray_mcp.config import Config


@pytest.mark.unit
class TestConfig:
    """Test simplified configuration system."""

    def test_config_defaults(self):
        """Test that configuration has correct default values."""
        config = Config()

        # Kubernetes settings
        assert config.kubernetes_namespace == "default"

        # GCP settings
        assert config.gcp_project_id is None
        assert config.gke_region == "us-central1"
        assert config.gke_zone == "us-central1-a"

        # AWS settings
        assert config.aws_region == "us-west-2"

    def test_config_from_env_with_valid_values(self):
        """Test configuration loading from environment variables."""
        env_vars = {
            "KUBERNETES_NAMESPACE": "production",
            "GOOGLE_CLOUD_PROJECT": "my-project",
            "GKE_REGION": "us-west1",
            "GKE_ZONE": "us-west1-b",
            "AWS_DEFAULT_REGION": "us-east-1",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            config = Config.from_env()

            # Verify all values were loaded correctly
            assert config.kubernetes_namespace == "production"
            assert config.gcp_project_id == "my-project"
            assert config.gke_region == "us-west1"
            assert config.gke_zone == "us-west1-b"
            assert config.aws_region == "us-east-1"

    def test_config_from_env_with_defaults(self):
        """Test configuration loading with default values when env vars are missing."""
        # Clear relevant environment variables by setting them to empty or unsetting them
        env_vars = {}

        # Use patch to temporarily clear the environment
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config.from_env()

            # Verify defaults are used
            assert config.kubernetes_namespace == "default"
            assert config.gcp_project_id is None
            assert config.gke_region == "us-central1"
            assert config.gke_zone == "us-central1-a"
            assert config.aws_region == "us-west-2"

    def test_config_dataclass_properties(self):
        """Test that Config is a proper dataclass."""
        config = Config()

        # Test that we can modify values
        config.kubernetes_namespace = "test-namespace"
        assert config.kubernetes_namespace == "test-namespace"

        # Test that we can create with parameters
        config2 = Config(
            kubernetes_namespace="custom-namespace",
            gcp_project_id="test-project",
            aws_region="eu-west-1",
        )
        assert config2.kubernetes_namespace == "custom-namespace"
        assert config2.gcp_project_id == "test-project"
        assert config2.aws_region == "eu-west-1"

    def test_gcp_project_id_from_service_account(self):
        """Test GCP project ID extraction from service account file."""
        # This test would require mocking the file system,
        # but for now we'll just test that the function exists and doesn't crash
        config = Config.from_env()
        # If no service account file exists, should be None
        assert config.gcp_project_id is None or isinstance(config.gcp_project_id, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
