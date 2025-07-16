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

        # Ray settings
        assert config.ray_address is None
        assert config.ray_dashboard_port == 8265
        assert config.ray_num_cpus is None
        assert config.ray_num_gpus is None

        # Kubernetes settings
        assert config.kubernetes_namespace == "default"
        assert config.kubernetes_context is None

        # GCP settings
        assert config.gcp_project_id is None
        assert config.gke_region == "us-central1"
        assert config.gke_zone == "us-central1-a"

        # General settings
        assert config.log_level == "INFO"
        assert config.timeout_seconds == 300
        assert config.enhanced_output is False

    def test_config_from_env_with_valid_values(self):
        """Test configuration loading from environment variables."""
        env_vars = {
            "RAY_ADDRESS": "ray://localhost:10001",
            "RAY_DASHBOARD_PORT": "9999",
            "RAY_NUM_CPUS": "8",
            "RAY_NUM_GPUS": "2",
            "KUBERNETES_NAMESPACE": "production",
            "KUBERNETES_CONTEXT": "my-context",
            "GOOGLE_CLOUD_PROJECT": "my-project",
            "GKE_REGION": "us-west1",
            "GKE_ZONE": "us-west1-b",
            "RAY_MCP_LOG_LEVEL": "DEBUG",
            "RAY_MCP_TIMEOUT": "600",
            "RAY_MCP_ENHANCED_OUTPUT": "true",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            config = Config.from_env()

            # Verify all values were loaded correctly
            assert config.ray_address == "ray://localhost:10001"
            assert config.ray_dashboard_port == 9999
            assert config.ray_num_cpus == 8
            assert config.ray_num_gpus == 2
            assert config.kubernetes_namespace == "production"
            assert config.kubernetes_context == "my-context"
            assert config.gcp_project_id == "my-project"
            assert config.gke_region == "us-west1"
            assert config.gke_zone == "us-west1-b"
            assert config.log_level == "DEBUG"
            assert config.timeout_seconds == 600
            assert config.enhanced_output is True

    def test_config_from_env_with_defaults(self):
        """Test configuration loading with default values when env vars are missing."""
        # Clear relevant environment variables by setting them to empty or unsetting them
        env_vars = {}

        # Use patch to temporarily clear the environment
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config.from_env()

            # Verify defaults are used
            assert config.ray_address is None
            assert config.ray_dashboard_port == 8265  # default
            assert config.ray_num_cpus is None
            assert config.ray_num_gpus is None
            assert config.kubernetes_namespace == "default"
            assert config.kubernetes_context is None
            assert config.gcp_project_id is None
            assert config.gke_region == "us-central1"
            assert config.gke_zone == "us-central1-a"
            assert config.log_level == "INFO"
            assert config.timeout_seconds == 300
            assert config.enhanced_output is False

    def test_config_boolean_parsing(self):
        """Test boolean environment variable parsing."""
        test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("", False),
            ("invalid", False),
        ]

        for value, expected in test_cases:
            with patch.dict(
                os.environ, {"RAY_MCP_ENHANCED_OUTPUT": value}, clear=False
            ):
                config = Config.from_env()
                assert config.enhanced_output == expected

    def test_config_integer_parsing(self):
        """Test integer environment variable parsing."""
        # Test valid integer values
        env_vars = {
            "RAY_DASHBOARD_PORT": "8080",
            "RAY_NUM_CPUS": "16",
            "RAY_NUM_GPUS": "4",
            "RAY_MCP_TIMEOUT": "900",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            config = Config.from_env()
            assert config.ray_dashboard_port == 8080
            assert config.ray_num_cpus == 16
            assert config.ray_num_gpus == 4
            assert config.timeout_seconds == 900

    def test_config_invalid_integer_handling(self):
        """Test handling of invalid integer values - they should fall back to defaults."""
        # Test that empty string uses default
        with patch.dict(os.environ, {"RAY_DASHBOARD_PORT": ""}, clear=False):
            config = Config.from_env()
            assert config.ray_dashboard_port == 8265

        # Test that invalid values fall back to default
        invalid_values = ["not_a_number", "abc", "12.5"]

        for invalid_value in invalid_values:
            with patch.dict(
                os.environ, {"RAY_DASHBOARD_PORT": invalid_value}, clear=False
            ):
                # Invalid values should fall back to default
                config = Config.from_env()
                assert config.ray_dashboard_port == 8265

    def test_config_optional_cpu_gpu_parsing(self):
        """Test optional CPU and GPU parsing."""
        # Test empty values result in None
        env_vars = {
            "RAY_NUM_CPUS": "",
            "RAY_NUM_GPUS": "",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            config = Config.from_env()
            assert config.ray_num_cpus is None
            assert config.ray_num_gpus is None

        # Test valid values are parsed
        env_vars = {
            "RAY_NUM_CPUS": "8",
            "RAY_NUM_GPUS": "2",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            config = Config.from_env()
            assert config.ray_num_cpus == 8
            assert config.ray_num_gpus == 2

    def test_config_dataclass_properties(self):
        """Test that Config is a proper dataclass."""
        config = Config()

        # Test that we can modify values
        config.ray_dashboard_port = 9000
        assert config.ray_dashboard_port == 9000

        # Test that we can create with parameters
        config2 = Config(
            ray_address="ray://test:10001",
            ray_dashboard_port=8080,
            enhanced_output=True,
        )
        assert config2.ray_address == "ray://test:10001"
        assert config2.ray_dashboard_port == 8080
        assert config2.enhanced_output is True

    def test_config_walrus_operator_usage(self):
        """Test that walrus operator works correctly in from_env."""
        # Test with values present
        env_vars = {
            "RAY_NUM_CPUS": "4",
            "RAY_NUM_GPUS": "1",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            config = Config.from_env()
            assert config.ray_num_cpus == 4
            assert config.ray_num_gpus == 1

        # Test with values absent
        env_vars = {}

        with patch.dict(os.environ, env_vars, clear=True):
            config = Config.from_env()
            assert config.ray_num_cpus is None
            assert config.ray_num_gpus is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
