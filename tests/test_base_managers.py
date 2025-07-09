"""Tests for base managers and mixins."""

from unittest.mock import Mock, patch

import pytest

from ray_mcp.foundation.base_managers import BaseManager, ResourceManager
from ray_mcp.foundation.import_utils import (
    get_logging_utils,
    get_ray_imports,
    is_google_cloud_available,
    is_kubernetes_available,
    is_ray_available,
)


@pytest.mark.fast
class TestImportUtils:
    """Test import utilities functionality."""

    def test_get_logging_utils(self):
        """Test that logging utilities can be imported."""
        utils = get_logging_utils()
        assert "LoggingUtility" in utils
        assert "ResponseFormatter" in utils
        assert callable(utils["LoggingUtility"].log_info)
        assert callable(utils["ResponseFormatter"])

    def test_get_ray_imports(self):
        """Test Ray imports with mocking."""
        imports = get_ray_imports()
        assert "ray" in imports
        assert "JobSubmissionClient" in imports
        assert "RAY_AVAILABLE" in imports
        assert isinstance(imports["RAY_AVAILABLE"], bool)

    def test_availability_functions(self):
        """Test availability check functions."""
        ray_available = is_ray_available()
        k8s_available = is_kubernetes_available()
        gcp_available = is_google_cloud_available()

        assert isinstance(ray_available, bool)
        assert isinstance(k8s_available, bool)
        assert isinstance(gcp_available, bool)


@pytest.mark.fast
class TestBaseManager:
    """Test base manager functionality."""

    def test_base_manager_initialization(self):
        """Test that BaseManager can be initialized with state manager."""
        state_manager = Mock()

        # Create a concrete implementation for testing
        class TestManager(BaseManager):
            pass

        manager = TestManager(state_manager)
        assert manager.state_manager == state_manager
        assert hasattr(manager, "_log_info")
        assert hasattr(manager, "_log_error")
        assert hasattr(manager, "_format_success_response")
        assert hasattr(manager, "_format_error_response")

    def test_logging_methods(self):
        """Test that logging methods work correctly."""
        state_manager = Mock()

        class TestManager(BaseManager):
            pass

        manager = TestManager(state_manager)

        # Test logging methods don't raise exceptions
        manager._log_info("test", "message")
        manager._log_warning("test", "warning")

        # Test response formatting
        success_response = manager._format_success_response(result="test")
        assert isinstance(success_response, dict)

        error_response = manager._format_error_response(
            "operation", RuntimeError("test")
        )
        assert isinstance(error_response, dict)


@pytest.mark.fast
class TestResourceManager:
    """Test Resource manager functionality."""

    def test_resource_manager_initialization(self):
        """Test ResourceManager initialization."""
        state_manager = Mock()

        class TestResourceManager(ResourceManager):
            pass

        manager = TestResourceManager(
            state_manager, enable_ray=True, enable_kubernetes=False, enable_cloud=False
        )
        assert manager.state_manager == state_manager
        assert hasattr(manager, "_ray")
        assert hasattr(manager, "_JobSubmissionClient")
        assert hasattr(manager, "_RAY_AVAILABLE")
        assert hasattr(manager, "_ensure_ray_available")
        assert hasattr(manager, "_ensure_initialized")

    def test_ray_availability_check(self):
        """Test Ray availability checking."""
        state_manager = Mock()

        class TestResourceManager(ResourceManager):
            pass

        manager = TestResourceManager(
            state_manager, enable_ray=True, enable_kubernetes=False, enable_cloud=False
        )

        # Mock Ray as unavailable
        with patch.object(manager, "_RAY_AVAILABLE", False):
            with pytest.raises(RuntimeError, match="Ray is not available"):
                manager._ensure_ray_available()

        # Mock Ray as available
        with patch.object(manager, "_RAY_AVAILABLE", True):
            # Should not raise
            manager._ensure_ray_available()

    def test_ray_initialization_check(self):
        """Test Ray initialization checking."""
        state_manager = Mock()
        state_manager.is_initialized.return_value = False

        class TestResourceManager(ResourceManager):
            pass

        manager = TestResourceManager(
            state_manager, enable_ray=True, enable_kubernetes=False, enable_cloud=False
        )

        with pytest.raises(RuntimeError, match="Ray is not initialized"):
            manager._ensure_initialized()


@pytest.mark.fast
class TestConsolidatedFunctionality:
    """Test consolidated functionality in BaseManager."""

    def test_validation_functionality(self):
        """Test validation functionality built into BaseManager."""

        class TestValidationManager(BaseManager):
            pass

        state_manager = Mock()
        manager = TestValidationManager(state_manager)

        # Test job ID validation
        assert manager._validate_job_id("valid_job_id", "test") is None
        error_response = manager._validate_job_id("", "test")
        assert error_response is not None
        assert "job_id" in error_response.get("message", "")

    def test_state_management_functionality(self):
        """Test state management functionality built into BaseManager."""

        class TestStateManager(BaseManager):
            pass

        state_manager = Mock()
        state_manager.get_state.return_value = {"test_key": "test_value"}
        state_manager.is_initialized.return_value = True

        manager = TestStateManager(state_manager)

        # Test state access methods
        state = manager._get_state()
        assert state == {"test_key": "test_value"}

        assert manager._get_state_value("test_key") == "test_value"
        assert manager._get_state_value("missing_key", "default") == "default"

        assert manager._is_state_initialized() is True

    @pytest.mark.asyncio
    async def test_async_operation_functionality(self):
        """Test async operation functionality built into BaseManager."""

        class TestAsyncManager(BaseManager):
            async def test_operation(self):
                return "success"

        state_manager = Mock()
        manager = TestAsyncManager(state_manager)

        # Test retry operation
        result = await manager._retry_operation(
            manager.test_operation,
            max_retries=3,
            retry_delay=0.1,
            operation_name="test",
        )
        assert result == "success"


@pytest.mark.fast
class TestFullManagerIntegration:
    """Test full manager with consolidated functionality."""

    def test_comprehensive_manager(self):
        """Test a manager that uses ResourceManager with all capabilities."""

        class ComprehensiveManager(ResourceManager):
            async def test_operation(self, job_id: str):
                # Validate input
                validation_error = self._validate_job_id(job_id, "test")
                if validation_error:
                    return validation_error

                # Check state
                if not self._is_state_initialized():
                    raise RuntimeError("Not initialized")

                # Return success
                return {"result": "success", "job_id": job_id}

        state_manager = Mock()
        state_manager.is_initialized.return_value = True

        manager = ComprehensiveManager(
            state_manager, enable_ray=True, enable_kubernetes=True, enable_cloud=True
        )

        # Test that all functionality is available
        assert hasattr(manager, "_validate_job_id")
        assert hasattr(manager, "_get_state")
        assert hasattr(manager, "_retry_operation")
        assert hasattr(manager, "_ensure_ray_available")
        assert hasattr(manager, "_log_info")
        assert hasattr(manager, "_format_success_response")
