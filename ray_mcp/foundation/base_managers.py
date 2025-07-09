"""Consolidated base manager classes - 2 classes instead of 8."""

from abc import ABC, abstractmethod
import asyncio
from typing import Any, Dict, Optional

from .import_utils import (
    get_google_cloud_imports,
    get_kubernetes_imports,
    get_logging_utils,
    get_ray_imports,
)
from .interfaces import StateManager


class BaseManager(ABC):
    """Unified base class with common functionality and all former mixin capabilities.

    This replaces the old BaseManager + 3 mixins (ValidationMixin, StateManagementMixin, AsyncOperationMixin).
    """

    def __init__(self, state_manager: StateManager):
        self._state_manager = state_manager

        # Get imports
        logging_utils = get_logging_utils()
        self._LoggingUtility = logging_utils["LoggingUtility"]
        self._ResponseFormatter = logging_utils["ResponseFormatter"]

        # Backward compatibility: keep instance for managers that still use it
        self._response_formatter = self._ResponseFormatter()

    @property
    def state_manager(self) -> StateManager:
        """Get the state manager."""
        return self._state_manager

    # === Logging Methods ===
    def _log_info(self, operation: str, message: str) -> None:
        """Log info message."""
        self._LoggingUtility.log_info(operation, message)

    def _log_warning(self, operation: str, message: str) -> None:
        """Log warning message."""
        self._LoggingUtility.log_warning(operation, message)

    def _log_error(self, operation: str, error: Exception) -> None:
        """Log error message."""
        self._LoggingUtility.log_error(operation, error)

    # === Response Formatting Methods ===
    def _format_success_response(self, **kwargs) -> Dict[str, Any]:
        """Format success response."""
        return self._response_formatter.format_success_response(**kwargs)

    def _format_error_response(
        self, operation: str, error: Exception, **kwargs
    ) -> Dict[str, Any]:
        """Format error response."""
        return self._response_formatter.format_error_response(
            operation, error, **kwargs
        )

    def _format_validation_error(self, message: str, **kwargs) -> Dict[str, Any]:
        """Format validation error response."""
        return self._response_formatter.format_validation_error(message, **kwargs)

    def _handle_exceptions(self, operation: str):
        """Decorator for handling exceptions in manager methods."""
        return self._ResponseFormatter.handle_exceptions(operation)

    async def _execute_operation(
        self, operation_name: str, operation_func, *args, **kwargs
    ) -> Dict[str, Any]:
        """Execute an operation with standardized error handling."""
        try:
            result = await operation_func(*args, **kwargs)
            if isinstance(result, dict) and "status" in result:
                return result
            return self._format_success_response(**result)
        except Exception as e:
            self._log_error(operation_name, e)
            return self._format_error_response(operation_name, e)

    # === Validation Methods (former ValidationMixin) ===
    def _validate_job_id(
        self, job_id: str, operation_name: str
    ) -> Optional[Dict[str, Any]]:
        """Validate job ID format."""
        if not job_id or not isinstance(job_id, str) or not job_id.strip():
            return self._format_validation_error(
                f"Invalid job_id for {operation_name}: must be a non-empty string"
            )
        return None

    def _validate_entrypoint(self, entrypoint: str) -> Optional[Dict[str, Any]]:
        """Validate job entrypoint."""
        if not entrypoint or not isinstance(entrypoint, str) or not entrypoint.strip():
            return self._format_validation_error(
                "Entrypoint must be a non-empty string"
            )
        return None

    def _validate_cluster_name(self, cluster_name: str) -> Optional[Dict[str, Any]]:
        """Validate cluster name."""
        if (
            not cluster_name
            or not isinstance(cluster_name, str)
            or not cluster_name.strip()
        ):
            return self._format_validation_error(
                "Cluster name must be a non-empty string"
            )
        return None

    # === State Management Methods (former StateManagementMixin) ===
    def _get_state(self) -> Dict[str, Any]:
        """Get current state."""
        return self._state_manager.get_state()

    def _update_state(self, **kwargs) -> None:
        """Update state with validation."""
        self._state_manager.update_state(**kwargs)

    def _reset_state(self) -> None:
        """Reset state to initial values."""
        self._state_manager.reset_state()

    def _get_state_value(self, key: str, default: Any = None) -> Any:
        """Get a specific value from state."""
        return self._get_state().get(key, default)

    def _is_state_initialized(self) -> bool:
        """Check if state is initialized."""
        return self._state_manager.is_initialized()

    # === Async Operation Methods (former AsyncOperationMixin) ===
    async def _retry_operation(
        self,
        operation_func,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        operation_name: str = "operation",
    ) -> Any:
        """Retry an operation with exponential backoff."""
        for attempt in range(max_retries):
            try:
                self._log_info(operation_name, f"Attempt {attempt + 1}/{max_retries}")
                return await operation_func()
            except Exception as e:
                self._log_warning(operation_name, f"Attempt {attempt + 1} failed: {e}")

                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    raise

    async def _test_connection(
        self,
        connection_func,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        operation_name: str = "connection test",
    ) -> bool:
        """Test a connection with retry logic."""
        try:
            await self._retry_operation(
                connection_func, max_retries, retry_delay, operation_name
            )
            return True
        except Exception as e:
            self._log_error(operation_name, e)
            return False


class ResourceManager(BaseManager):
    """Unified resource manager with optional Ray, Kubernetes, and Cloud capabilities.

    This replaces the old RayBaseManager, KubernetesBaseManager, CloudProviderBaseManager,
    and KubeRayBaseManager with a single configurable class.
    """

    def __init__(
        self,
        state_manager: StateManager,
        enable_ray: bool = True,
        enable_kubernetes: bool = True,
        enable_cloud: bool = True,
    ):
        super().__init__(state_manager)

        # Ray capabilities (optional)
        if enable_ray:
            ray_imports = get_ray_imports()
            self._ray = ray_imports["ray"]
            self._JobSubmissionClient = ray_imports["JobSubmissionClient"]
            self._RAY_AVAILABLE = ray_imports["RAY_AVAILABLE"]
        else:
            self._ray = None
            self._JobSubmissionClient = None
            self._RAY_AVAILABLE = False

        # Kubernetes capabilities (optional)
        if enable_kubernetes:
            k8s_imports = get_kubernetes_imports()
            self._client = k8s_imports["client"]
            self._config = k8s_imports["config"]
            self._ApiException = k8s_imports["ApiException"]
            self._ConfigException = k8s_imports["ConfigException"]
            self._KUBERNETES_AVAILABLE = k8s_imports["KUBERNETES_AVAILABLE"]
        else:
            self._client = None
            self._config = None
            self._ApiException = Exception
            self._ConfigException = Exception
            self._KUBERNETES_AVAILABLE = False

        # Cloud capabilities (optional)
        if enable_cloud:
            gcp_imports = get_google_cloud_imports()
            self._gcp_default = gcp_imports["default"]
            self._DefaultCredentialsError = gcp_imports["DefaultCredentialsError"]
            self._container_v1 = gcp_imports["container_v1"]
            self._service_account = gcp_imports["service_account"]
            self._google_auth_transport = gcp_imports["google_auth_transport"]
            self._GOOGLE_CLOUD_AVAILABLE = gcp_imports["GOOGLE_CLOUD_AVAILABLE"]
            self._GOOGLE_AUTH_AVAILABLE = gcp_imports["GOOGLE_AUTH_AVAILABLE"]
        else:
            self._gcp_default = None
            self._DefaultCredentialsError = Exception
            self._container_v1 = None
            self._service_account = None
            self._google_auth_transport = None
            self._GOOGLE_CLOUD_AVAILABLE = False
            self._GOOGLE_AUTH_AVAILABLE = False

    # === Ray Methods ===
    def _ensure_ray_available(self) -> None:
        """Ensure Ray is available."""
        if not self._RAY_AVAILABLE:
            raise RuntimeError(
                "Ray is not available. Please install Ray to use this feature."
            )

    def _ensure_initialized(self) -> None:
        """Ensure Ray is initialized."""
        if not self._state_manager.is_initialized():
            raise RuntimeError("Ray is not initialized. Please start Ray first.")

    def _is_ray_initialized(self) -> bool:
        """Check if Ray is initialized."""
        if not self._RAY_AVAILABLE or not self._ray:
            return False
        try:
            return bool(self._ray.is_initialized())
        except Exception:
            return False

    # === Kubernetes Methods ===
    def _ensure_kubernetes_available(self) -> None:
        """Ensure Kubernetes is available."""
        if not self._KUBERNETES_AVAILABLE:
            raise RuntimeError(
                "Kubernetes client library is not available. Please install kubernetes package."
            )

    def _ensure_connected(self) -> None:
        """Ensure Kubernetes is connected."""
        state = self._state_manager.get_state()
        if not state.get("kubernetes_connected", False):
            raise RuntimeError(
                "Kubernetes is not connected. Please connect to a cluster first."
            )

    def _ensure_kuberay_ready(self) -> None:
        """Ensure Kubernetes is connected and KubeRay is available."""
        self._ensure_connected()

    # === Cloud Methods ===
    def _ensure_google_cloud_available(self) -> None:
        """Ensure Google Cloud SDK is available."""
        if not self._GOOGLE_CLOUD_AVAILABLE:
            raise RuntimeError(
                "Google Cloud SDK is not available. Please install google-cloud-container."
            )

    def _ensure_google_auth_available(self) -> None:
        """Ensure Google Auth is available."""
        if not self._GOOGLE_AUTH_AVAILABLE:
            raise RuntimeError("Google auth transport is not available.")

    def _get_current_time(self) -> str:
        """Get current time as ISO string."""
        from datetime import datetime

        return datetime.utcnow().isoformat() + "Z"
