"""Kubernetes CRD operations client for Ray resources."""

import asyncio
from typing import Any, Dict, List, Optional

from ...foundation.import_utils import get_kubernetes_imports, get_logging_utils
from ...foundation.interfaces import CRDOperations
from ..config.kubernetes_config import KubernetesConfigManager


class CRDOperationsClient(CRDOperations):
    """Client for Custom Resource Definition operations with comprehensive CRUD support."""

    # Resource type mappings
    RESOURCE_MAPPINGS = {
        "raycluster": {
            "group": "ray.io",
            "version": "v1",
            "plural": "rayclusters",
            "kind": "RayCluster",
        },
        "rayjob": {
            "group": "ray.io",
            "version": "v1",
            "plural": "rayjobs",
            "kind": "RayJob",
        },
    }

    def __init__(
        self,
        config_manager: Optional[KubernetesConfigManager] = None,
        kubernetes_config: Optional[Any] = None,
    ):
        # Get imports
        logging_utils = get_logging_utils()
        self._LoggingUtility = logging_utils["LoggingUtility"]
        self._ResponseFormatter = logging_utils["ResponseFormatter"]

        k8s_imports = get_kubernetes_imports()
        self._client = k8s_imports["client"]
        self._config = k8s_imports["config"]
        self._ApiException = k8s_imports["ApiException"]
        self._KUBERNETES_AVAILABLE = k8s_imports["KUBERNETES_AVAILABLE"]

        self._config_manager = config_manager or KubernetesConfigManager()
        self._kubernetes_config = kubernetes_config  # Pre-configured Kubernetes client
        self._response_formatter = self._ResponseFormatter()
        self._custom_objects_api = None
        self._api_client = None  # Persistent API client
        self._retry_attempts = 3
        self._retry_delay = 1.0

    def set_kubernetes_config(self, kubernetes_config: Any) -> None:
        """Set the Kubernetes configuration to use for API calls."""
        self._LoggingUtility.log_info(
            "crd_operations_set_k8s_config",
            f"Setting Kubernetes configuration - config provided: {kubernetes_config is not None}, host: {getattr(kubernetes_config, 'host', 'N/A') if kubernetes_config else 'N/A'}",
        )

        # Clean up existing API client if it exists
        if self._api_client:
            try:
                self._api_client.close()
            except Exception:
                pass  # Ignore cleanup errors

        self._kubernetes_config = kubernetes_config
        # Reset the clients so they get recreated with the new config
        self._custom_objects_api = None
        self._api_client = None

        self._LoggingUtility.log_info(
            "crd_operations_set_k8s_config",
            "Successfully reset CRD operations client configuration",
        )

    def _ensure_client(self) -> None:
        """Ensure custom objects API client is initialized."""
        if not self._KUBERNETES_AVAILABLE:
            raise RuntimeError("Kubernetes client library is not available")

        # Always recreate if we have a pre-configured client to ensure fresh configuration
        if self._custom_objects_api is None or (
            self._kubernetes_config and self._api_client is None
        ):
            if self._kubernetes_config:
                # Use the pre-configured Kubernetes client (e.g., from GKE)
                self._LoggingUtility.log_info(
                    "crd_operations_ensure_client",
                    f"Using pre-configured Kubernetes client (host: {getattr(self._kubernetes_config, 'host', 'unknown')})",
                )
                # Create a persistent API client that won't be closed
                self._api_client = self._client.ApiClient(self._kubernetes_config)
                self._custom_objects_api = self._client.CustomObjectsApi(
                    self._api_client
                )
            else:
                # Fall back to default Kubernetes configuration
                self._LoggingUtility.log_warning(
                    "crd_operations_ensure_client",
                    "No pre-configured Kubernetes client found, falling back to default configuration",
                )
                # Try to load default configuration first
                try:
                    self._config.load_incluster_config()
                    self._LoggingUtility.log_info(
                        "crd_operations_ensure_client",
                        "Loaded in-cluster configuration",
                    )
                except Exception:
                    try:
                        self._config.load_kube_config()
                        self._LoggingUtility.log_info(
                            "crd_operations_ensure_client",
                            "Loaded kubeconfig configuration",
                        )
                    except Exception as e:
                        self._LoggingUtility.log_warning(
                            "crd_operations_ensure_client",
                            f"Failed to load any Kubernetes configuration: {str(e)}",
                        )

                self._custom_objects_api = self._client.CustomObjectsApi()

    def _get_resource_info(self, resource_type: str) -> Dict[str, str]:
        """Get resource information from type mapping."""
        resource_type_lower = resource_type.lower()
        if resource_type_lower not in self.RESOURCE_MAPPINGS:
            raise ValueError(
                f"Unsupported resource type: {resource_type}. Supported types: {list(self.RESOURCE_MAPPINGS.keys())}"
            )

        return self.RESOURCE_MAPPINGS[resource_type_lower]

    async def create_resource(
        self,
        resource_type: str,
        resource_spec: Dict[str, Any],
        namespace: str = "default",
    ) -> Dict[str, Any]:
        """Create a custom resource with retry logic."""
        try:
            if not self._KUBERNETES_AVAILABLE:
                return self._response_formatter.format_error_response(
                    "create custom resource",
                    Exception("Kubernetes client library is not available"),
                )

            resource_info = self._get_resource_info(resource_type)

            # Retry loop for handling transient failures
            for attempt in range(self._retry_attempts):
                try:
                    self._ensure_client()

                    # Create the resource
                    result = await asyncio.to_thread(
                        self._custom_objects_api.create_namespaced_custom_object,
                        group=resource_info["group"],
                        version=resource_info["version"],
                        namespace=namespace,
                        plural=resource_info["plural"],
                        body=resource_spec,
                    )

                    return self._response_formatter.format_success_response(
                        resource=result,
                        name=result.get("metadata", {}).get("name"),
                        namespace=namespace,
                        resource_type=resource_type,
                    )

                except self._ApiException as e:
                    if attempt == self._retry_attempts - 1:  # Last attempt
                        status = getattr(e, "status", "unknown")
                        reason = getattr(e, "reason", "unknown")
                        return self._response_formatter.format_error_response(
                            "create custom resource",
                            Exception(f"API Error: {status} - {reason}"),
                        )
                    else:
                        reason = getattr(e, "reason", "unknown")
                        self._LoggingUtility.log_warning(
                            "create custom resource",
                            f"Attempt {attempt + 1} failed: {reason}, retrying...",
                        )
                        await asyncio.sleep(self._retry_delay * (attempt + 1))

                except Exception as e:
                    self._LoggingUtility.log_error("create custom resource", e)
                    return self._response_formatter.format_error_response(
                        "create custom resource", e
                    )

            # Fallback return in case all retries are exhausted without explicit return
            return self._response_formatter.format_error_response(
                "create custom resource",
                Exception("All retry attempts exhausted without successful completion"),
            )

        except Exception as e:
            self._LoggingUtility.log_error("create custom resource", e)
            return self._response_formatter.format_error_response(
                "create custom resource", e
            )

    async def get_resource(
        self, resource_type: str, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Get a custom resource by name."""
        if not self._KUBERNETES_AVAILABLE:
            return self._response_formatter.format_error_response(
                "get custom resource",
                Exception("Kubernetes client library is not available"),
            )

        resource_info = self._get_resource_info(resource_type)

        try:
            self._ensure_client()

            result = await asyncio.to_thread(
                self._custom_objects_api.get_namespaced_custom_object,
                group=resource_info["group"],
                version=resource_info["version"],
                namespace=namespace,
                plural=resource_info["plural"],
                name=name,
            )

            # Safe dictionary access with type checking
            status = result.get("status", {}) if isinstance(result, dict) else {}
            phase = (
                status.get("phase", "Unknown")
                if isinstance(status, dict)
                else "Unknown"
            )

            return self._response_formatter.format_success_response(
                resource=result,
                name=name,
                namespace=namespace,
                resource_type=resource_type,
                status=status,
                phase=phase,
            )

        except self._ApiException as e:
            status = getattr(e, "status", "unknown")
            reason = getattr(e, "reason", "unknown")
            if status == 404:
                return self._response_formatter.format_error_response(
                    "get custom resource",
                    Exception(
                        f"Resource '{name}' not found in namespace '{namespace}'"
                    ),
                )
            else:
                return self._response_formatter.format_error_response(
                    "get custom resource",
                    Exception(f"API Error: {status} - {reason}"),
                )
        except Exception as e:
            return self._response_formatter.format_error_response(
                "get custom resource", e
            )

    async def list_resources(
        self, resource_type: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """List custom resources in a namespace."""
        if not self._KUBERNETES_AVAILABLE:
            return self._response_formatter.format_error_response(
                "list custom resources",
                Exception("Kubernetes client library is not available"),
            )

        resource_info = self._get_resource_info(resource_type)

        try:
            self._LoggingUtility.log_info(
                "crd_operations_list_resources",
                f"Listing {resource_type} resources in namespace {namespace} - k8s config available: {self._kubernetes_config is not None}",
            )
            self._ensure_client()

            result = await asyncio.to_thread(
                self._custom_objects_api.list_namespaced_custom_object,
                group=resource_info["group"],
                version=resource_info["version"],
                namespace=namespace,
                plural=resource_info["plural"],
            )

            # Extract and format resource information with safe dictionary access
            resources = []
            items = result.get("items", []) if isinstance(result, dict) else []
            for item in items:
                if not isinstance(item, dict):
                    continue

                metadata = item.get("metadata", {}) if isinstance(item, dict) else {}
                status = item.get("status", {}) if isinstance(item, dict) else {}

                resource_summary = {
                    "name": (
                        metadata.get("name") if isinstance(metadata, dict) else None
                    ),
                    "namespace": (
                        metadata.get("namespace")
                        if isinstance(metadata, dict)
                        else None
                    ),
                    "creation_timestamp": (
                        metadata.get("creationTimestamp")
                        if isinstance(metadata, dict)
                        else None
                    ),
                    "status": status,
                    "phase": (
                        status.get("phase", "Unknown")
                        if isinstance(status, dict)
                        else "Unknown"
                    ),
                    "labels": (
                        metadata.get("labels", {}) if isinstance(metadata, dict) else {}
                    ),
                }
                resources.append(resource_summary)

            return self._response_formatter.format_success_response(
                resources=resources,
                total_count=len(resources),
                namespace=namespace,
                resource_type=resource_type,
            )

        except self._ApiException as e:
            status = getattr(e, "status", "unknown")
            reason = getattr(e, "reason", "unknown")
            return self._response_formatter.format_error_response(
                "list custom resources",
                Exception(f"API Error: {status} - {reason}"),
            )
        except Exception as e:
            return self._response_formatter.format_error_response(
                "list custom resources", e
            )

    async def update_resource(
        self,
        resource_type: str,
        name: str,
        resource_spec: Dict[str, Any],
        namespace: str = "default",
    ) -> Dict[str, Any]:
        """Update a custom resource with retry logic."""
        if not self._KUBERNETES_AVAILABLE:
            return self._response_formatter.format_error_response(
                "update custom resource",
                Exception("Kubernetes client library is not available"),
            )

        resource_info = self._get_resource_info(resource_type)

        # Retry loop for handling conflicts
        for attempt in range(self._retry_attempts):
            try:
                self._ensure_client()

                # First get the current resource to get the resourceVersion
                current = await asyncio.to_thread(
                    self._custom_objects_api.get_namespaced_custom_object,
                    group=resource_info["group"],
                    version=resource_info["version"],
                    namespace=namespace,
                    plural=resource_info["plural"],
                    name=name,
                )

                # Update the resource spec while preserving metadata with safe copy
                if isinstance(current, dict):
                    updated_spec = current.copy()
                    updated_spec["spec"] = (
                        resource_spec.get("spec", resource_spec)
                        if isinstance(resource_spec, dict)
                        else resource_spec
                    )
                else:
                    # Fallback if current is not a dict
                    updated_spec = {
                        "spec": (
                            resource_spec.get("spec", resource_spec)
                            if isinstance(resource_spec, dict)
                            else resource_spec
                        )
                    }

                # Perform the update
                result = await asyncio.to_thread(
                    self._custom_objects_api.replace_namespaced_custom_object,
                    group=resource_info["group"],
                    version=resource_info["version"],
                    namespace=namespace,
                    plural=resource_info["plural"],
                    name=name,
                    body=updated_spec,
                )

                return self._response_formatter.format_success_response(
                    resource=result,
                    name=name,
                    namespace=namespace,
                    resource_type=resource_type,
                )

            except self._ApiException as e:
                status = getattr(e, "status", "unknown")
                reason = getattr(e, "reason", "unknown")
                if status == 404:
                    return self._response_formatter.format_error_response(
                        "update custom resource",
                        Exception(
                            f"Resource '{name}' not found in namespace '{namespace}'"
                        ),
                    )
                elif (
                    status == 409 and attempt < self._retry_attempts - 1
                ):  # Conflict, retry
                    self._LoggingUtility.log_warning(
                        "update custom resource",
                        f"Conflict updating resource, attempt {attempt + 1}, retrying...",
                    )
                    await asyncio.sleep(self._retry_delay * (attempt + 1))
                    continue
                else:
                    return self._response_formatter.format_error_response(
                        "update custom resource",
                        Exception(f"API Error: {status} - {reason}"),
                    )
            except Exception as e:
                return self._response_formatter.format_error_response(
                    "update custom resource", e
                )

        # Fallback return in case all retries are exhausted without explicit return
        return self._response_formatter.format_error_response(
            "update custom resource",
            Exception("All retry attempts exhausted without successful completion"),
        )

    async def delete_resource(
        self, resource_type: str, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Delete a custom resource with cleanup."""
        if not self._KUBERNETES_AVAILABLE:
            return self._response_formatter.format_error_response(
                "delete custom resource",
                Exception("Kubernetes client library is not available"),
            )

        resource_info = self._get_resource_info(resource_type)

        try:
            self._ensure_client()

            # Delete the resource
            result = await asyncio.to_thread(
                self._custom_objects_api.delete_namespaced_custom_object,
                group=resource_info["group"],
                version=resource_info["version"],
                namespace=namespace,
                plural=resource_info["plural"],
                name=name,
            )

            return self._response_formatter.format_success_response(
                deleted=True,
                name=name,
                namespace=namespace,
                resource_type=resource_type,
                deletion_timestamp=result.get("metadata", {}).get("deletionTimestamp"),
            )

        except self._ApiException as e:
            status = getattr(e, "status", "unknown")
            reason = getattr(e, "reason", "unknown")
            if status == 404:
                return self._response_formatter.format_error_response(
                    "delete custom resource",
                    Exception(
                        f"Resource '{name}' not found in namespace '{namespace}'"
                    ),
                )
            else:
                return self._response_formatter.format_error_response(
                    "delete custom resource",
                    Exception(f"API Error: {status} - {reason}"),
                )
        except Exception as e:
            return self._response_formatter.format_error_response(
                "delete custom resource", e
            )

    async def watch_resource(
        self, resource_type: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Watch custom resource changes."""
        if not self._KUBERNETES_AVAILABLE:
            return self._response_formatter.format_error_response(
                "watch custom resource",
                Exception("Kubernetes client library is not available"),
            )

        # This is a simplified watch implementation
        # In a real implementation, you'd use kubernetes.watch.Watch for streaming events
        resource_info = self._get_resource_info(resource_type)

        try:
            self._ensure_client()

            # For now, just return the current list of resources
            # A full implementation would stream events
            result = await self.list_resources(resource_type, namespace)

            if result.get("status") == "success":
                return self._response_formatter.format_success_response(
                    watch_enabled=True,
                    resource_type=resource_type,
                    namespace=namespace,
                    current_resources=result.get("resources", []),
                    message="Watch functionality would stream events in a full implementation",
                )
            else:
                return result

        except Exception as e:
            return self._response_formatter.format_error_response(
                "watch custom resource", e
            )
