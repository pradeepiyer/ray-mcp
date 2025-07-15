"""ResourceManager base class for prompt-driven Ray MCP managers."""

from abc import ABC, abstractmethod
from typing import Any, Dict

from .import_utils import get_logging_utils


class ResourceManager(ABC):
    """Enhanced base for prompt-driven managers with import management."""

    def __init__(
        self,
        enable_ray: bool = False,
        enable_kubernetes: bool = False,
        enable_cloud: bool = False,
    ):
        # Import logging utilities (moved from PromptManager)
        logging_utils = get_logging_utils()
        self._ResponseFormatter = logging_utils["ResponseFormatter"]
        self._LoggingUtility = logging_utils["LoggingUtility"]

        # Import enabled services
        if enable_ray:
            self._setup_ray_imports()
        if enable_kubernetes:
            self._setup_kubernetes_imports()
        if enable_cloud:
            self._setup_cloud_imports()

    @abstractmethod
    async def execute_request(self, prompt: str) -> Dict[str, Any]:
        """Process natural language prompt and return response."""
        pass

    def _setup_ray_imports(self) -> None:
        """Set up Ray imports."""
        from .import_utils import get_ray_imports

        ray_imports = get_ray_imports()
        self._ray = ray_imports.get("ray")
        self._RAY_AVAILABLE = ray_imports.get("RAY_AVAILABLE", False)

    def _setup_kubernetes_imports(self) -> None:
        """Set up Kubernetes imports."""
        from .import_utils import get_kubernetes_imports

        k8s_imports = get_kubernetes_imports()
        self._client = k8s_imports.get("client")
        self._config = k8s_imports.get("config")
        self._ApiException = k8s_imports.get("ApiException", Exception)
        self._ConfigException = k8s_imports.get("ConfigException", Exception)
        self._KUBERNETES_AVAILABLE = k8s_imports.get("KUBERNETES_AVAILABLE", False)

    def _setup_cloud_imports(self) -> None:
        """Set up cloud provider imports."""
        from .import_utils import get_google_cloud_imports

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

    # Simple direct checks instead of complex state management
    def _is_ray_ready(self) -> bool:
        """Check if Ray is ready."""
        return bool(self._RAY_AVAILABLE and self._ray and self._ray.is_initialized())

    def _is_kubernetes_ready(self) -> bool:
        """Check if Kubernetes is ready."""
        if not self._KUBERNETES_AVAILABLE:
            return False
        try:
            # Simple check - try to load config
            if self._config:
                self._config.load_kube_config()
                return True
            return False
        except Exception:
            return False

    async def _execute_operation(
        self, operation_name: str, operation_func, *args, **kwargs
    ) -> Dict[str, Any]:
        """Execute an operation with error handling."""
        try:
            result = await operation_func(*args, **kwargs)
            if not isinstance(result, dict):
                result = {"result": result}
            if "status" not in result:
                result["status"] = "success"
            return result
        except Exception as e:
            self._LoggingUtility.log_error(operation_name, e)
            return self._ResponseFormatter.format_error_response(operation_name, e)
