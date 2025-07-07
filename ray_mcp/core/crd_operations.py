"""Custom Resource Definition operations client."""

import asyncio
from typing import Any, Dict, List, Optional

try:
    from ..logging_utils import LoggingUtility, ResponseFormatter
except ImportError:
    # Fallback for direct execution
    import os
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from logging_utils import LoggingUtility, ResponseFormatter

from .interfaces import CRDOperations
from .kubernetes_config import KubernetesConfigManager

# Import kubernetes modules with error handling
try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException

    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False
    client = None
    ApiException = Exception


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

    def __init__(self, config_manager: Optional[KubernetesConfigManager] = None):
        self._config_manager = config_manager or KubernetesConfigManager()
        self._response_formatter = ResponseFormatter()
        self._custom_objects_api = None
        self._retry_attempts = 3
        self._retry_delay = 1.0

    def _ensure_client(self) -> None:
        """Ensure custom objects API client is initialized."""
        if not KUBERNETES_AVAILABLE:
            raise RuntimeError("Kubernetes client library is not available")

        if self._custom_objects_api is None:
            self._custom_objects_api = client.CustomObjectsApi()

    def _get_resource_info(self, resource_type: str) -> Dict[str, str]:
        """Get resource information from type mapping."""
        resource_type_lower = resource_type.lower()
        if resource_type_lower not in self.RESOURCE_MAPPINGS:
            raise ValueError(
                f"Unsupported resource type: {resource_type}. Supported types: {list(self.RESOURCE_MAPPINGS.keys())}"
            )

        return self.RESOURCE_MAPPINGS[resource_type_lower]

    @ResponseFormatter.handle_exceptions("create custom resource")
    async def create_resource(
        self,
        resource_type: str,
        resource_spec: Dict[str, Any],
        namespace: str = "default",
    ) -> Dict[str, Any]:
        """Create a custom resource with retry logic."""
        if not KUBERNETES_AVAILABLE:
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

            except ApiException as e:
                if attempt == self._retry_attempts - 1:  # Last attempt
                    return self._response_formatter.format_error_response(
                        "create custom resource",
                        Exception(f"API Error: {e.status} - {e.reason}"),
                    )
                else:
                    LoggingUtility.log_warning(
                        "create custom resource",
                        f"Attempt {attempt + 1} failed: {e.reason}, retrying...",
                    )
                    await asyncio.sleep(self._retry_delay * (attempt + 1))

            except Exception as e:
                return self._response_formatter.format_error_response(
                    "create custom resource", e
                )

    @ResponseFormatter.handle_exceptions("get custom resource")
    async def get_resource(
        self, resource_type: str, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Get a custom resource by name."""
        if not KUBERNETES_AVAILABLE:
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

            return self._response_formatter.format_success_response(
                resource=result,
                name=name,
                namespace=namespace,
                resource_type=resource_type,
                status=result.get("status", {}),
                phase=result.get("status", {}).get("phase", "Unknown"),
            )

        except ApiException as e:
            if e.status == 404:
                return self._response_formatter.format_error_response(
                    "get custom resource",
                    Exception(
                        f"Resource '{name}' not found in namespace '{namespace}'"
                    ),
                )
            else:
                return self._response_formatter.format_error_response(
                    "get custom resource",
                    Exception(f"API Error: {e.status} - {e.reason}"),
                )
        except Exception as e:
            return self._response_formatter.format_error_response(
                "get custom resource", e
            )

    @ResponseFormatter.handle_exceptions("list custom resources")
    async def list_resources(
        self, resource_type: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """List custom resources in a namespace."""
        if not KUBERNETES_AVAILABLE:
            return self._response_formatter.format_error_response(
                "list custom resources",
                Exception("Kubernetes client library is not available"),
            )

        resource_info = self._get_resource_info(resource_type)

        try:
            self._ensure_client()

            result = await asyncio.to_thread(
                self._custom_objects_api.list_namespaced_custom_object,
                group=resource_info["group"],
                version=resource_info["version"],
                namespace=namespace,
                plural=resource_info["plural"],
            )

            # Extract and format resource information
            resources = []
            for item in result.get("items", []):
                resource_summary = {
                    "name": item.get("metadata", {}).get("name"),
                    "namespace": item.get("metadata", {}).get("namespace"),
                    "creation_timestamp": item.get("metadata", {}).get(
                        "creationTimestamp"
                    ),
                    "status": item.get("status", {}),
                    "phase": item.get("status", {}).get("phase", "Unknown"),
                    "labels": item.get("metadata", {}).get("labels", {}),
                }
                resources.append(resource_summary)

            return self._response_formatter.format_success_response(
                resources=resources,
                total_count=len(resources),
                namespace=namespace,
                resource_type=resource_type,
            )

        except ApiException as e:
            return self._response_formatter.format_error_response(
                "list custom resources",
                Exception(f"API Error: {e.status} - {e.reason}"),
            )
        except Exception as e:
            return self._response_formatter.format_error_response(
                "list custom resources", e
            )

    @ResponseFormatter.handle_exceptions("update custom resource")
    async def update_resource(
        self,
        resource_type: str,
        name: str,
        resource_spec: Dict[str, Any],
        namespace: str = "default",
    ) -> Dict[str, Any]:
        """Update a custom resource with retry logic."""
        if not KUBERNETES_AVAILABLE:
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

                # Update the resource spec while preserving metadata
                updated_spec = current.copy()
                updated_spec["spec"] = resource_spec.get("spec", resource_spec)

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

            except ApiException as e:
                if e.status == 404:
                    return self._response_formatter.format_error_response(
                        "update custom resource",
                        Exception(
                            f"Resource '{name}' not found in namespace '{namespace}'"
                        ),
                    )
                elif (
                    e.status == 409 and attempt < self._retry_attempts - 1
                ):  # Conflict, retry
                    LoggingUtility.log_warning(
                        "update custom resource",
                        f"Conflict updating resource, attempt {attempt + 1}, retrying...",
                    )
                    await asyncio.sleep(self._retry_delay * (attempt + 1))
                    continue
                else:
                    return self._response_formatter.format_error_response(
                        "update custom resource",
                        Exception(f"API Error: {e.status} - {e.reason}"),
                    )
            except Exception as e:
                return self._response_formatter.format_error_response(
                    "update custom resource", e
                )

    @ResponseFormatter.handle_exceptions("delete custom resource")
    async def delete_resource(
        self, resource_type: str, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Delete a custom resource with cleanup."""
        if not KUBERNETES_AVAILABLE:
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

        except ApiException as e:
            if e.status == 404:
                return self._response_formatter.format_error_response(
                    "delete custom resource",
                    Exception(
                        f"Resource '{name}' not found in namespace '{namespace}'"
                    ),
                )
            else:
                return self._response_formatter.format_error_response(
                    "delete custom resource",
                    Exception(f"API Error: {e.status} - {e.reason}"),
                )
        except Exception as e:
            return self._response_formatter.format_error_response(
                "delete custom resource", e
            )

    @ResponseFormatter.handle_exceptions("watch custom resource")
    async def watch_resource(
        self, resource_type: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Watch custom resource changes."""
        if not KUBERNETES_AVAILABLE:
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
