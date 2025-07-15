"""Tests for unified configuration management."""

import logging
import os
import pytest
from unittest.mock import patch

from ray_mcp.config.unified_config import UnifiedConfigManager


@pytest.mark.unit
class TestUnifiedConfigManager:
    """Test unified configuration manager."""

    @pytest.fixture
    def config_manager(self):
        """Create a config manager for testing."""
        return UnifiedConfigManager()

    @pytest.mark.asyncio
    async def test_environment_variable_invalid_integer_warning(
        self, config_manager, caplog
    ):
        """Test that invalid integer environment variables generate warnings."""
        # Mock environment variables with invalid integer values
        env_vars = {
            "RAY_DASHBOARD_PORT": "invalid_port",
            "RAY_NUM_CPUS": "not_a_number",
            "RAY_NUM_GPUS": "abc",
            "RAY_OBJECT_STORE_MEMORY": "xyz",
            "RAY_MCP_TIMEOUT": "bad_timeout",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            with caplog.at_level(logging.WARNING):
                await config_manager._load_environment_variables()

        # Check that warnings were logged for each invalid value
        warning_messages = [record.message for record in caplog.records if record.levelname == "WARNING"]
        
        expected_warnings = [
            "RAY_DASHBOARD_PORT",
            "RAY_NUM_CPUS", 
            "RAY_NUM_GPUS",
            "RAY_OBJECT_STORE_MEMORY",
            "RAY_MCP_TIMEOUT"
        ]
        
        for env_var in expected_warnings:
            assert any(env_var in warning for warning in warning_messages), f"Expected warning for {env_var}"
        
        # Verify configuration keeps default values
        assert config_manager._config.ray_dashboard_port == 8265  # default
        assert config_manager._config.ray_num_cpus is None  # default
        assert config_manager._config.ray_num_gpus is None  # default
        assert config_manager._config.ray_object_store_memory is None  # default
        assert config_manager._config.timeout_seconds == 300  # default

    @pytest.mark.asyncio
    async def test_environment_variable_valid_integer_parsing(self, config_manager):
        """Test that valid integer environment variables are parsed correctly."""
        env_vars = {
            "RAY_DASHBOARD_PORT": "9999",
            "RAY_NUM_CPUS": "8",
            "RAY_NUM_GPUS": "2",
            "RAY_OBJECT_STORE_MEMORY": "1073741824",
            "RAY_MCP_TIMEOUT": "600",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            await config_manager._load_environment_variables()

        # Verify values were parsed correctly
        assert config_manager._config.ray_dashboard_port == 9999
        assert config_manager._config.ray_num_cpus == 8
        assert config_manager._config.ray_num_gpus == 2
        assert config_manager._config.ray_object_store_memory == 1073741824
        assert config_manager._config.timeout_seconds == 600

    @pytest.mark.asyncio
    async def test_environment_variable_boolean_parsing(self, config_manager):
        """Test that boolean environment variables are parsed correctly."""
        test_cases = [
            ("true", True),
            ("1", True),
            ("yes", True),
            ("on", True),
            ("false", False),
            ("0", False),
            ("no", False),
            ("off", False),
            ("invalid", False),
        ]

        for value, expected in test_cases:
            with patch.dict(os.environ, {"RAY_MCP_ENHANCED_OUTPUT": value}, clear=False):
                await config_manager._load_environment_variables()
                assert config_manager._config.enhanced_output == expected