"""Base manager classes for Ray MCP components."""

from abc import ABC, abstractmethod
import asyncio
import time
from typing import Any, Dict, Optional

from .import_utils import (
    get_google_cloud_imports,
    get_kubernetes_imports,
    get_logging_utils,
    get_ray_imports,
)
from .interfaces import ManagedComponent


class BaseManager(ABC):
    """Lightweight base class for simple components that need only logging and validation."""

    def __init__(
        self,
        state_manager,
        enable_validation: bool = True,
        validation_interval: float = 30.0,
    ):
        # Import logging utilities
        logging_utils = get_logging_utils()
        self._LoggingUtility = logging_utils["LoggingUtility"]
        self._ResponseFormatter = logging_utils["ResponseFormatter"]

        # Basic validation properties
        self._enable_validation = enable_validation
        self._validation_interval = validation_interval
        self._last_validation = 0.0

        # Store state manager but don't use it for logging utilities
        self._external_state_manager = state_manager

    @property
    def state_manager(self):
        """Get the state manager."""
        return self._external_state_manager

    def _log_info(self, operation: str, message: str) -> None:
        """Log info message using logging utilities."""
        self._LoggingUtility.log_info(operation, message)

    def _log_warning(self, operation: str, message: str) -> None:
        """Log warning message using logging utilities."""
        self._LoggingUtility.log_warning(operation, message)

    def _log_error(self, operation: str, error: Exception) -> None:
        """Log error message using logging utilities."""
        self._LoggingUtility.log_error(operation, error)

    def _validate_input(self, value: Any, name: str, required: bool = True) -> bool:
        """Basic input validation."""
        if required and (value is None or (isinstance(value, str) and not value)):
            self._log_error(f"validate {name}", ValueError(f"{name} is required"))
            return False
        return True

    def _should_validate(self) -> bool:
        """Check if validation should run based on interval."""
        if not self._enable_validation:
            return False

        current_time = time.time()
        if (current_time - self._last_validation) >= self._validation_interval:
            self._last_validation = current_time
            return True
        return False

    # === State Management Helper Methods ===
    def _get_state(self) -> Dict[str, Any]:
        """Get current state."""
        return self._external_state_manager.get_state()

    def _update_state(self, **kwargs) -> None:
        """Update state with validation."""
        self._external_state_manager.update_state(**kwargs)

    def _reset_state(self) -> None:
        """Reset state to initial values."""
        self._external_state_manager.reset_state()

    def _get_state_value(self, key: str, default: Any = None) -> Any:
        """Get a specific value from state."""
        return self._get_state().get(key, default)

    def _is_state_initialized(self) -> bool:
        """Check if state is initialized."""
        return self._external_state_manager.is_initialized()

    # === Validation Helper Methods ===
    def _validate_job_id(
        self, job_id: str, operation_name: str
    ) -> Optional[Dict[str, Any]]:
        """Validate job ID format."""
        if not job_id or not isinstance(job_id, str) or not job_id.strip():
            return self._ResponseFormatter.format_validation_error(
                f"Invalid job_id for {operation_name}: must be a non-empty string"
            )
        return None

    def _validate_entrypoint(self, entrypoint: str) -> Optional[Dict[str, Any]]:
        """Validate job entrypoint."""
        if not entrypoint or not isinstance(entrypoint, str) or not entrypoint.strip():
            return self._ResponseFormatter.format_validation_error(
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
            return self._ResponseFormatter.format_validation_error(
                "Cluster name must be a non-empty string"
            )
        return None

    # === Async Operation Helper Methods ===
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

    @abstractmethod
    async def _validate_state(self) -> bool:
        """Validate current state. Must be implemented by subclasses."""
        pass


class ResourceManager(BaseManager):
    """Enhanced base class for resource-intensive managers that need import management."""

    def __init__(
        self,
        state_manager,
        enable_ray: bool = False,
        enable_kubernetes: bool = False,
        enable_cloud: bool = False,
        enable_validation: bool = True,
        validation_interval: float = 30.0,
    ):
        super().__init__(state_manager, enable_validation, validation_interval)

        # Import enabled services based on configuration
        if enable_ray:
            self._setup_ray_imports()
        if enable_kubernetes:
            self._setup_kubernetes_imports()
        if enable_cloud:
            self._setup_cloud_imports()

    def _setup_ray_imports(self) -> None:
        """Set up Ray imports with error handling."""
        ray_imports = get_ray_imports()
        self._ray = ray_imports.get("ray")
        self._JobSubmissionClient = ray_imports.get("JobSubmissionClient")
        self._RAY_AVAILABLE = ray_imports.get("RAY_AVAILABLE", False)

    def _setup_kubernetes_imports(self) -> None:
        """Set up Kubernetes imports with error handling."""
        k8s_imports = get_kubernetes_imports()
        self._client = k8s_imports.get("client")
        self._config = k8s_imports.get("config")
        self._ApiException = k8s_imports.get("ApiException", Exception)
        self._ConfigException = k8s_imports.get("ConfigException", Exception)
        self._KUBERNETES_AVAILABLE = k8s_imports.get("KUBERNETES_AVAILABLE", False)

    def _setup_cloud_imports(self) -> None:
        """Set up cloud provider imports with error handling."""
        gcp_imports = get_google_cloud_imports()
        self._default = gcp_imports.get("default")
        self._DefaultCredentialsError = gcp_imports.get(
            "DefaultCredentialsError", Exception
        )
        self._container_v1 = gcp_imports.get("container_v1")
        self._service_account = gcp_imports.get("service_account")
        self._google_auth_transport = gcp_imports.get("google_auth_transport")
        self._GOOGLE_CLOUD_AVAILABLE = gcp_imports.get("GOOGLE_CLOUD_AVAILABLE", False)
        self._GOOGLE_AUTH_AVAILABLE = gcp_imports.get("GOOGLE_AUTH_AVAILABLE", False)

    def _ensure_ray_available(self) -> None:
        """Ensure Ray is available."""
        if not self._RAY_AVAILABLE:
            raise RuntimeError(
                "Ray is not available. Please install Ray: pip install ray[default]"
            )

    def _ensure_kubernetes_available(self) -> None:
        """Ensure Kubernetes client is available."""
        if not self._KUBERNETES_AVAILABLE:
            raise RuntimeError(
                "Kubernetes client is not available. Please install: pip install kubernetes"
            )

    def _ensure_gcp_available(self) -> None:
        """Ensure GCP libraries are available."""
        if not self._GOOGLE_CLOUD_AVAILABLE:
            raise RuntimeError(
                "GCP libraries are not available. Please install: pip install google-cloud-container google-auth"
            )

    async def _execute_operation(
        self, operation_name: str, operation_func, *args, **kwargs
    ) -> Dict[str, Any]:
        """Execute an operation with comprehensive error handling and validation."""
        try:
            # Optional validation before operation
            if self._should_validate():
                await self._validate_state()

            # Execute the operation
            result = await operation_func(*args, **kwargs)

            # Ensure result is a dictionary
            if not isinstance(result, dict):
                result = {"result": result}

            # Add success status if not present
            if "status" not in result:
                result["status"] = "success"

            return result

        except Exception as e:
            self._log_error(operation_name, e)
            return self._ResponseFormatter.format_error_response(operation_name, e)

    async def _validate_state(self) -> bool:
        """Default validation implementation."""
        return True

    def _is_ray_initialized(self) -> bool:
        """Check if Ray is initialized."""
        if not self._RAY_AVAILABLE or not self._ray:
            return False
        try:
            return bool(self._ray.is_initialized())
        except Exception:
            return False
