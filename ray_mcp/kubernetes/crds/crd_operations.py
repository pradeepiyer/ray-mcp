"""Custom Resource Definition operations for Ray MCP."""

import asyncio
from typing import Any, Dict, List, Optional

from ...foundation.base_managers import ResourceManager
from ...foundation.import_utils import get_kubernetes_imports, get_logging_utils
from ...foundation.interfaces import ManagedComponent
from ..config.kubernetes_config import KubernetesConfig


class CRDOperationsClient(ResourceManager, ManagedComponent):
    """Manages Custom Resource Definition operations for Kubernetes."""

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
        state_manager,
        config_manager: Optional[KubernetesConfig] = None,
    ):
        # Initialize both parent classes
        ResourceManager.__init__(
            self,
            state_manager,
            enable_ray=False,
            enable_kubernetes=True,
            enable_cloud=False,
        )
        ManagedComponent.__init__(self, state_manager)

        # Get imports
        logging_utils = get_logging_utils()
        self._LoggingUtility = logging_utils["LoggingUtility"]
        self._ResponseFormatter = logging_utils["ResponseFormatter"]

        k8s_imports = get_kubernetes_imports()
        self._client = k8s_imports["client"]
        self._config = k8s_imports["config"]
        self._ApiException = k8s_imports["ApiException"]
        self._KUBERNETES_AVAILABLE = k8s_imports["KUBERNETES_AVAILABLE"]

        self._config_manager = config_manager or KubernetesConfig()
        self._kubernetes_config = None  # Pre-configured Kubernetes client
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
        self._cleanup_api_client()

        self._kubernetes_config = kubernetes_config
        # Reset the clients so they get recreated with the new config
        self._custom_objects_api = None
        self._api_client = None

        self._LoggingUtility.log_info(
            "crd_operations_set_k8s_config",
            "Successfully reset CRD operations client configuration",
        )

    def _cleanup_api_client(self) -> None:
        """Clean up the API client with proper error handling."""
        if self._api_client:
            try:
                self._api_client.close()
                self._LoggingUtility.log_info(
                    "crd_operations_cleanup",
                    "Successfully closed API client",
                )
            except Exception as e:
                self._LoggingUtility.log_warning(
                    "crd_operations_cleanup",
                    f"Failed to close API client: {str(e)}",
                )

    def __del__(self) -> None:
        """Destructor to ensure proper cleanup of API client."""
        try:
            self._cleanup_api_client()
        except Exception:
            # Suppress exceptions in destructor to avoid issues during shutdown
            pass

    async def _ensure_client(self) -> None:
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
                try:
                    # Create a persistent API client that won't be closed
                    api_client = self._client.ApiClient(self._kubernetes_config)
                    custom_objects_api = self._client.CustomObjectsApi(api_client)

                    # Only assign if both are successfully created
                    self._api_client = api_client
                    self._custom_objects_api = custom_objects_api
                except Exception as e:
                    # Clean up partially created client if necessary
                    if "api_client" in locals():
                        try:
                            api_client.close()
                        except Exception:
                            pass
                    self._LoggingUtility.log_error(
                        "crd_operations_ensure_client",
                        f"Failed to create pre-configured Kubernetes client: {str(e)}",
                    )
                    raise
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
                        await asyncio.to_thread(self._config.load_kube_config)
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

    async def _validate_resource_spec(
        self,
        resource_type: str,
        resource_spec: Dict[str, Any],
        namespace: str,
    ) -> Optional[Dict[str, Any]]:
        """Comprehensive validation of resource specification to prevent cluster failures.

        Validates resource structure, security requirements, and limits before creation.

        Args:
            resource_type: Type of resource (raycluster, rayjob)
            resource_spec: Resource specification to validate
            namespace: Target namespace

        Returns:
            None if validation passes, error response dict if validation fails
        """
        try:
            # 1. Basic structure validation
            structure_error = self._validate_basic_structure(resource_spec)
            if structure_error:
                return structure_error

            # 2. Namespace validation
            namespace_error = self._validate_namespace(namespace)
            if namespace_error:
                return namespace_error

            # 3. Resource size validation (prevent overwhelming API server)
            size_error = self._validate_resource_size(resource_spec)
            if size_error:
                return size_error

            # 4. Resource-specific validation
            resource_error = await self._validate_resource_specific(
                resource_type, resource_spec
            )
            if resource_error:
                return resource_error

            # 5. Security validation
            security_error = self._validate_security_requirements(resource_spec)
            if security_error:
                return security_error

            # 6. Resource limits validation
            limits_error = self._validate_resource_limits(resource_spec)
            if limits_error:
                return limits_error

            return None  # Validation passed

        except Exception as e:
            self._LoggingUtility.log_error("validate resource spec", e)
            return self._ResponseFormatter.format_error_response(
                "validate resource spec",
                Exception(f"Validation failed due to internal error: {str(e)}"),
            )

    def _validate_basic_structure(
        self, resource_spec: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Validate basic Kubernetes resource structure."""
        # Check if resource_spec is valid dict
        if not isinstance(resource_spec, dict):
            return self._ResponseFormatter.format_validation_error(
                "Resource specification must be a dictionary"
            )

        # Check for required top-level fields
        required_fields = ["apiVersion", "kind", "metadata", "spec"]
        for field in required_fields:
            if field not in resource_spec:
                return self._ResponseFormatter.format_validation_error(
                    f"Missing required field: {field}"
                )

        # Validate metadata structure
        metadata = resource_spec.get("metadata", {})
        if not isinstance(metadata, dict):
            return self._ResponseFormatter.format_validation_error(
                "metadata must be a dictionary"
            )

        # Validate required metadata fields
        if "name" not in metadata:
            return self._ResponseFormatter.format_validation_error(
                "metadata.name is required"
            )

        # Validate resource name format (Kubernetes naming requirements)
        name = metadata["name"]
        if not self._is_valid_kubernetes_name(name):
            return self._ResponseFormatter.format_validation_error(
                f"Invalid resource name '{name}': must be a valid DNS-1123 subdomain"
            )

        return None

    def _validate_namespace(self, namespace: str) -> Optional[Dict[str, Any]]:
        """Validate namespace safety and format."""
        if not namespace or not isinstance(namespace, str):
            return self._ResponseFormatter.format_validation_error(
                "Namespace must be a non-empty string"
            )

        # Validate namespace name format
        if not self._is_valid_kubernetes_name(namespace):
            return self._ResponseFormatter.format_validation_error(
                f"Invalid namespace '{namespace}': must be a valid DNS-1123 label"
            )

        # Check for potentially dangerous namespaces
        dangerous_namespaces = {
            "kube-system",
            "kube-public",
            "kube-node-lease",
            "kubernetes-dashboard",
            "cert-manager",
            "istio-system",
        }
        if namespace in dangerous_namespaces:
            return self._ResponseFormatter.format_validation_error(
                f"Cannot create resources in system namespace '{namespace}'"
            )

        return None

    def _validate_resource_size(
        self, resource_spec: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Validate resource specification size to prevent API server overload."""
        import json

        try:
            # Calculate serialized size
            serialized = json.dumps(resource_spec, default=str)
            size_bytes = len(serialized.encode("utf-8"))

            # Kubernetes etcd default limit is ~1.5MB, we use 1MB as safe limit
            max_size_bytes = 1024 * 1024  # 1MB

            if size_bytes > max_size_bytes:
                return self._ResponseFormatter.format_validation_error(
                    f"Resource specification too large: {size_bytes} bytes (max: {max_size_bytes} bytes)"
                )

            return None

        except Exception as e:
            return self._ResponseFormatter.format_validation_error(
                f"Failed to validate resource size: {str(e)}"
            )

    async def _validate_resource_specific(
        self, resource_type: str, resource_spec: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Validate resource-specific requirements for Ray CRDs."""
        resource_type_lower = resource_type.lower()

        if resource_type_lower == "raycluster":
            return self._validate_ray_cluster_spec(resource_spec)
        elif resource_type_lower == "rayjob":
            return self._validate_ray_job_spec(resource_spec)

        return None

    def _validate_ray_cluster_spec(
        self, resource_spec: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Validate RayCluster-specific requirements."""
        spec = resource_spec.get("spec", {})

        # Validate head group
        head_group_spec = spec.get("headGroupSpec", {})
        if not head_group_spec:
            return self._ResponseFormatter.format_validation_error(
                "RayCluster requires headGroupSpec"
            )

        # Validate head group has required fields
        if "rayStartParams" not in head_group_spec:
            return self._ResponseFormatter.format_validation_error(
                "headGroupSpec requires rayStartParams"
            )

        # Validate worker groups if present
        worker_group_specs = spec.get("workerGroupSpecs", [])
        for i, worker_spec in enumerate(worker_group_specs):
            if "groupName" not in worker_spec:
                return self._ResponseFormatter.format_validation_error(
                    f"workerGroupSpecs[{i}] requires groupName"
                )

        return None

    def _validate_ray_job_spec(
        self, resource_spec: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Validate RayJob-specific requirements."""
        spec = resource_spec.get("spec", {})

        # Validate entrypoint
        if "entrypoint" not in spec:
            return self._ResponseFormatter.format_validation_error(
                "RayJob requires entrypoint in spec"
            )

        entrypoint = spec["entrypoint"]
        if not isinstance(entrypoint, str) or not entrypoint.strip():
            return self._ResponseFormatter.format_validation_error(
                "RayJob entrypoint must be a non-empty string"
            )

        return None

    def _validate_security_requirements(
        self, resource_spec: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Validate security-related requirements to prevent privilege escalation."""
        # Check for potentially dangerous security contexts
        dangerous_patterns = [
            ("spec.headGroupSpec.template.spec.securityContext.runAsUser", 0),
            (
                "spec.headGroupSpec.template.spec.containers[*].securityContext.privileged",
                True,
            ),
            ("spec.headGroupSpec.template.spec.hostNetwork", True),
            ("spec.headGroupSpec.template.spec.hostPID", True),
        ]

        for pattern_path, dangerous_value in dangerous_patterns:
            if self._check_nested_value(resource_spec, pattern_path, dangerous_value):
                return self._ResponseFormatter.format_validation_error(
                    f"Security violation: {pattern_path} cannot be set to {dangerous_value}"
                )

        return None

    def _validate_resource_limits(
        self, resource_spec: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Validate resource requests and limits for sanity."""
        # Define reasonable limits to prevent cluster resource exhaustion
        max_cpu_cores = 32  # Max CPU cores per container
        max_memory_gi = 64  # Max memory in GiB per container

        # Check head group resources
        head_spec = resource_spec.get("spec", {}).get("headGroupSpec", {})
        head_error = self._validate_container_resources(
            head_spec, max_cpu_cores, max_memory_gi, "headGroup"
        )
        if head_error:
            return head_error

        # Check worker group resources
        worker_specs = resource_spec.get("spec", {}).get("workerGroupSpecs", [])
        for i, worker_spec in enumerate(worker_specs):
            worker_error = self._validate_container_resources(
                worker_spec, max_cpu_cores, max_memory_gi, f"workerGroup[{i}]"
            )
            if worker_error:
                return worker_error

        return None

    def _validate_container_resources(
        self, group_spec: Dict[str, Any], max_cpu: int, max_memory: int, context: str
    ) -> Optional[Dict[str, Any]]:
        """Validate container resource requests and limits."""
        template = group_spec.get("template", {})
        pod_spec = template.get("spec", {})
        containers = pod_spec.get("containers", [])

        for i, container in enumerate(containers):
            resources = container.get("resources", {})

            # Check resource requests and limits
            for resource_type in ["requests", "limits"]:
                resource_values = resources.get(resource_type, {})

                # Validate CPU
                cpu = resource_values.get("cpu")
                if cpu and self._parse_cpu_value(cpu) > max_cpu:
                    return self._ResponseFormatter.format_validation_error(
                        f"{context}.container[{i}].resources.{resource_type}.cpu exceeds maximum {max_cpu} cores"
                    )

                # Validate memory
                memory = resource_values.get("memory")
                if (
                    memory and self._parse_memory_value(memory) > max_memory * 1024**3
                ):  # Convert GiB to bytes
                    return self._ResponseFormatter.format_validation_error(
                        f"{context}.container[{i}].resources.{resource_type}.memory exceeds maximum {max_memory}Gi"
                    )

        return None

    def _is_valid_kubernetes_name(self, name: str) -> bool:
        """Validate Kubernetes resource name format."""
        import re

        # DNS-1123 subdomain format: lowercase alphanumeric, '-', and '.'
        # Must start and end with alphanumeric character
        pattern = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$"
        return bool(re.match(pattern, name)) and len(name) <= 253

    def _check_nested_value(
        self, obj: Dict[str, Any], path: str, target_value: Any
    ) -> bool:
        """Check if a nested path contains a dangerous value."""
        try:
            # Simple path traversal for security checks
            current = obj
            parts = path.split(".")

            for part in parts:
                if "[*]" in part:
                    # Handle array notation for containers
                    field = part.replace("[*]", "")
                    if field in current and isinstance(current[field], list):
                        for item in current[field]:
                            if isinstance(item, dict) and self._check_nested_value(
                                item,
                                ".".join(parts[parts.index(part) + 1 :]),
                                target_value,
                            ):
                                return True
                    return False
                elif part in current:
                    current = current[part]
                else:
                    return False

            return current == target_value
        except Exception:
            return False

    def _parse_cpu_value(self, cpu_str: str) -> float:
        """Parse Kubernetes CPU value to number of cores."""
        try:
            if cpu_str.endswith("m"):
                return float(cpu_str[:-1]) / 1000  # millicores to cores
            else:
                return float(cpu_str)
        except (ValueError, TypeError):
            return 0

    def _parse_memory_value(self, memory_str: str) -> int:
        """Parse Kubernetes memory value to bytes."""
        try:
            memory_str = memory_str.upper()
            multipliers = {
                "KI": 1024,
                "MI": 1024**2,
                "GI": 1024**3,
                "TI": 1024**4,
                "K": 1000,
                "M": 1000**2,
                "G": 1000**3,
                "T": 1000**4,
            }

            for suffix, multiplier in multipliers.items():
                if memory_str.endswith(suffix):
                    return int(float(memory_str[: -len(suffix)]) * multiplier)

            return int(memory_str)  # Assume bytes if no suffix
        except (ValueError, TypeError):
            return 0

    async def create_resource(
        self,
        resource_type: str,
        resource_spec: Dict[str, Any],
        namespace: str = "default",
    ) -> Dict[str, Any]:
        """Create a custom resource with comprehensive validation and retry logic.

        Validates resource specification against security and structural requirements
        before sending to Kubernetes to prevent cluster failures or invalid resources.
        """
        try:
            if not self._KUBERNETES_AVAILABLE:
                return self._ResponseFormatter.format_error_response(
                    "create custom resource",
                    Exception("Kubernetes client library is not available"),
                )

            # Comprehensive resource validation before creation
            validation_result = await self._validate_resource_spec(
                resource_type, resource_spec, namespace
            )
            if validation_result is not None:
                return validation_result  # Return validation error

            resource_info = self._get_resource_info(resource_type)

            # Retry loop for handling transient failures
            for attempt in range(self._retry_attempts):
                try:
                    await self._ensure_client()

                    # Create the resource (only after successful validation)
                    result = await asyncio.to_thread(
                        self._custom_objects_api.create_namespaced_custom_object,
                        group=resource_info["group"],
                        version=resource_info["version"],
                        namespace=namespace,
                        plural=resource_info["plural"],
                        body=resource_spec,
                    )

                    return self._ResponseFormatter.format_success_response(
                        resource=result,
                        name=result.get("metadata", {}).get("name"),
                        namespace=namespace,
                        resource_type=resource_type,
                    )

                except self._ApiException as e:
                    if attempt == self._retry_attempts - 1:  # Last attempt
                        status = getattr(e, "status", "unknown")
                        reason = getattr(e, "reason", "unknown")
                        return self._ResponseFormatter.format_error_response(
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
                    return self._ResponseFormatter.format_error_response(
                        "create custom resource", e
                    )

            # Fallback return in case all retries are exhausted without explicit return
            return self._ResponseFormatter.format_error_response(
                "create custom resource",
                Exception("All retry attempts exhausted without successful completion"),
            )

        except Exception as e:
            self._LoggingUtility.log_error("create custom resource", e)
            return self._ResponseFormatter.format_error_response(
                "create custom resource", e
            )

    async def get_resource(
        self, resource_type: str, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Get a custom resource by name."""
        if not self._KUBERNETES_AVAILABLE:
            return self._ResponseFormatter.format_error_response(
                "get custom resource",
                Exception("Kubernetes client library is not available"),
            )

        resource_info = self._get_resource_info(resource_type)

        try:
            await self._ensure_client()

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

            return self._ResponseFormatter.format_success_response(
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
                return self._ResponseFormatter.format_error_response(
                    "get custom resource",
                    Exception(
                        f"Resource '{name}' not found in namespace '{namespace}'"
                    ),
                )
            else:
                return self._ResponseFormatter.format_error_response(
                    "get custom resource",
                    Exception(f"API Error: {status} - {reason}"),
                )
        except Exception as e:
            return self._ResponseFormatter.format_error_response(
                "get custom resource", e
            )

    async def list_resources(
        self, resource_type: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """List custom resources in a namespace."""
        if not self._KUBERNETES_AVAILABLE:
            return self._ResponseFormatter.format_error_response(
                "list custom resources",
                Exception("Kubernetes client library is not available"),
            )

        resource_info = self._get_resource_info(resource_type)

        try:
            self._LoggingUtility.log_info(
                "crd_operations_list_resources",
                f"Listing {resource_type} resources in namespace {namespace} - k8s config available: {self._kubernetes_config is not None}",
            )
            await self._ensure_client()

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

            return self._ResponseFormatter.format_success_response(
                resources=resources,
                total_count=len(resources),
                namespace=namespace,
                resource_type=resource_type,
            )

        except self._ApiException as e:
            status = getattr(e, "status", "unknown")
            reason = getattr(e, "reason", "unknown")
            return self._ResponseFormatter.format_error_response(
                "list custom resources",
                Exception(f"API Error: {status} - {reason}"),
            )
        except Exception as e:
            return self._ResponseFormatter.format_error_response(
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
            return self._ResponseFormatter.format_error_response(
                "update custom resource",
                Exception("Kubernetes client library is not available"),
            )

        resource_info = self._get_resource_info(resource_type)

        # Retry loop for handling conflicts
        for attempt in range(self._retry_attempts):
            try:
                await self._ensure_client()

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

                return self._ResponseFormatter.format_success_response(
                    resource=result,
                    name=name,
                    namespace=namespace,
                    resource_type=resource_type,
                )

            except self._ApiException as e:
                status = getattr(e, "status", "unknown")
                reason = getattr(e, "reason", "unknown")
                if status == 404:
                    return self._ResponseFormatter.format_error_response(
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
                    return self._ResponseFormatter.format_error_response(
                        "update custom resource",
                        Exception(f"API Error: {status} - {reason}"),
                    )
            except Exception as e:
                return self._ResponseFormatter.format_error_response(
                    "update custom resource", e
                )

        # Fallback return in case all retries are exhausted without explicit return
        return self._ResponseFormatter.format_error_response(
            "update custom resource",
            Exception("All retry attempts exhausted without successful completion"),
        )

    async def delete_resource(
        self, resource_type: str, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Delete a custom resource with cleanup."""
        if not self._KUBERNETES_AVAILABLE:
            return self._ResponseFormatter.format_error_response(
                "delete custom resource",
                Exception("Kubernetes client library is not available"),
            )

        resource_info = self._get_resource_info(resource_type)

        try:
            await self._ensure_client()

            # Delete the resource
            result = await asyncio.to_thread(
                self._custom_objects_api.delete_namespaced_custom_object,
                group=resource_info["group"],
                version=resource_info["version"],
                namespace=namespace,
                plural=resource_info["plural"],
                name=name,
            )

            return self._ResponseFormatter.format_success_response(
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
                return self._ResponseFormatter.format_error_response(
                    "delete custom resource",
                    Exception(
                        f"Resource '{name}' not found in namespace '{namespace}'"
                    ),
                )
            else:
                return self._ResponseFormatter.format_error_response(
                    "delete custom resource",
                    Exception(f"API Error: {status} - {reason}"),
                )
        except Exception as e:
            return self._ResponseFormatter.format_error_response(
                "delete custom resource", e
            )

    async def watch_resource(
        self, resource_type: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Watch custom resource changes."""
        if not self._KUBERNETES_AVAILABLE:
            return self._ResponseFormatter.format_error_response(
                "watch custom resource",
                Exception("Kubernetes client library is not available"),
            )

        # This is a simplified watch implementation
        # In a real implementation, you'd use kubernetes.watch.Watch for streaming events
        resource_info = self._get_resource_info(resource_type)

        try:
            await self._ensure_client()

            # For now, just return the current list of resources
            # A full implementation would stream events
            result = await self.list_resources(resource_type, namespace)

            if result.get("status") == "success":
                return self._ResponseFormatter.format_success_response(
                    watch_enabled=True,
                    resource_type=resource_type,
                    namespace=namespace,
                    current_resources=result.get("resources", []),
                    message="Watch functionality would stream events in a full implementation",
                )
            else:
                return result

        except Exception as e:
            return self._ResponseFormatter.format_error_response(
                "watch custom resource", e
            )
