"""Multi-layer validation pipeline for Ray YAML manifests."""

from abc import ABC, abstractmethod
import asyncio
import json
import re
from typing import Any, Dict, List, Optional, Union

from pydantic import ValidationError
import yaml

from .validation_models import (
    RayCluster,
    RayJob,
    Service,
    ValidationMessage,
    ValidationResult,
    ValidationSeverity,
)

try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException

    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False


class BaseValidator(ABC):
    """Base class for all validators."""

    @abstractmethod
    async def validate(
        self, yaml_str: str, parsed_yaml: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Validate YAML and return validation result."""
        pass

    def _create_result(self, valid: bool = True) -> ValidationResult:
        """Create a new validation result."""
        return ValidationResult(valid=valid, messages=[])


class SyntaxValidator(BaseValidator):
    """Validates YAML syntax and basic structure."""

    async def validate(
        self, yaml_str: str, parsed_yaml: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Validate YAML syntax and basic structure."""
        result = self._create_result()

        try:
            # Parse YAML
            if parsed_yaml is None:
                parsed_yaml = yaml.safe_load(yaml_str)

            if not isinstance(parsed_yaml, dict):
                result.add_error(
                    "YAML must be a dictionary/object at root level",
                    suggestion="Ensure your YAML starts with key-value pairs, not a list or scalar",
                )
                return result

            # Check required top-level fields
            required_fields = ["apiVersion", "kind", "metadata", "spec"]
            for field in required_fields:
                if field not in parsed_yaml:
                    result.add_error(
                        f"Missing required field: {field}",
                        field_path=field,
                        suggestion=f"Add '{field}:' field to the root level of your YAML",
                    )

            # Validate apiVersion format
            if "apiVersion" in parsed_yaml:
                api_version = parsed_yaml["apiVersion"]
                if not isinstance(api_version, str) or not api_version:
                    result.add_error(
                        "apiVersion must be a non-empty string",
                        field_path="apiVersion",
                        suggestion="Use 'apiVersion: ray.io/v1' for Ray resources or 'apiVersion: v1' for core resources",
                    )

            # Validate kind
            if "kind" in parsed_yaml:
                kind = parsed_yaml["kind"]
                valid_kinds = ["RayCluster", "RayJob", "Service"]
                if kind not in valid_kinds:
                    result.add_warning(
                        f"Unknown kind: {kind}. Expected one of {valid_kinds}",
                        field_path="kind",
                        suggestion=f"Use one of the supported kinds: {', '.join(valid_kinds)}",
                    )

            # Validate metadata structure
            if "metadata" in parsed_yaml:
                metadata = parsed_yaml["metadata"]
                if not isinstance(metadata, dict):
                    result.add_error(
                        "metadata must be a dictionary",
                        field_path="metadata",
                        suggestion="Change metadata to a dictionary with 'name' and optionally 'namespace'",
                    )
                elif "name" not in metadata:
                    result.add_error(
                        "metadata.name is required",
                        field_path="metadata.name",
                        suggestion="Add 'name: your-resource-name' under metadata",
                    )

            # Validate spec structure
            if "spec" in parsed_yaml:
                spec = parsed_yaml["spec"]
                if not isinstance(spec, dict):
                    result.add_error(
                        "spec must be a dictionary",
                        field_path="spec",
                        suggestion="Change spec to a dictionary containing the resource specification",
                    )

        except yaml.YAMLError as e:
            result.add_error(
                f"YAML syntax error: {str(e)}",
                suggestion="Check YAML indentation, quotes, and overall syntax",
            )
        except Exception as e:
            result.add_error(
                f"Unexpected error parsing YAML: {str(e)}",
                suggestion="Ensure YAML is properly formatted",
            )

        return result


class SchemaValidator(BaseValidator):
    """JSON Schema validation for RayCluster/RayJob structure using Pydantic."""

    async def validate(
        self, yaml_str: str, parsed_yaml: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Validate against Pydantic schemas."""
        result = self._create_result()

        try:
            if parsed_yaml is None:
                parsed_yaml = yaml.safe_load(yaml_str)

            if not isinstance(parsed_yaml, dict):
                result.add_error("Invalid YAML structure")
                return result

            kind = parsed_yaml.get("kind")

            if kind == "RayCluster":
                try:
                    RayCluster(**parsed_yaml)
                except ValidationError as e:
                    self._process_pydantic_errors(e, result)

            elif kind == "RayJob":
                try:
                    RayJob(**parsed_yaml)
                except ValidationError as e:
                    self._process_pydantic_errors(e, result)

            elif kind == "Service":
                try:
                    Service(**parsed_yaml)
                except ValidationError as e:
                    self._process_pydantic_errors(e, result)

            else:
                result.add_warning(
                    f"Schema validation not available for kind: {kind}",
                    field_path="kind",
                )

        except Exception as e:
            result.add_error(f"Schema validation error: {str(e)}")

        return result

    def _process_pydantic_errors(
        self, error: ValidationError, result: ValidationResult
    ) -> None:
        """Process Pydantic validation errors into ValidationMessages."""
        for err in error.errors():
            field_path = (
                ".".join(str(loc) for loc in err["loc"]) if err["loc"] else None
            )
            message = err["msg"]

            # Generate helpful suggestions based on error type
            suggestion = self._generate_suggestion(
                err["type"], field_path, err.get("input")
            )

            result.add_error(
                message=message,
                field_path=field_path,
                suggestion=suggestion,
                code=err["type"],
            )

    def _generate_suggestion(
        self, error_type: str, field_path: Optional[str], input_value: Any
    ) -> Optional[str]:
        """Generate helpful suggestions based on validation error type."""
        suggestions = {
            "missing": f"Add the required field '{field_path}' to your YAML",
            "string_type": f"Change '{field_path}' to a string value",
            "int_parsing": f"Change '{field_path}' to a valid integer",
            "value_error": f"Fix the value for '{field_path}' - check format requirements",
            "type_error": f"Change '{field_path}' to the correct data type",
            "greater_than_equal": f"Set '{field_path}' to a value >= the minimum allowed",
            "less_than_equal": f"Set '{field_path}' to a value <= the maximum allowed",
        }

        return suggestions.get(
            error_type, f"Check the value and format for '{field_path}'"
        )


class KubernetesValidator(BaseValidator):
    """Validates against Kubernetes API using dry-run."""

    def __init__(self):
        self._custom_objects_api = None
        self._core_v1_api = None
        self._client_initialized = False

    async def validate(
        self, yaml_str: str, parsed_yaml: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Validate using Kubernetes dry-run API."""
        result = self._create_result()

        if not KUBERNETES_AVAILABLE:
            result.add_warning(
                "Kubernetes client not available - skipping API validation",
                suggestion="Install kubernetes package for full validation",
            )
            return result

        try:
            if parsed_yaml is None:
                parsed_yaml = yaml.safe_load(yaml_str)

            if not isinstance(parsed_yaml, dict):
                result.add_error("Invalid YAML structure for Kubernetes validation")
                return result

            # Initialize Kubernetes client
            await self._ensure_kubernetes_client()

            # Perform dry-run validation
            api_version = parsed_yaml.get("apiVersion")
            kind = parsed_yaml.get("kind")
            namespace = parsed_yaml.get("metadata", {}).get("namespace", "default")

            try:
                if api_version == "ray.io/v1":
                    await self._validate_ray_crd(parsed_yaml, result)
                elif api_version == "v1" and kind == "Service":
                    await self._validate_service(parsed_yaml, namespace, result)
                else:
                    result.add_warning(
                        f"Kubernetes validation not supported for {api_version}/{kind}"
                    )

            except ApiException as e:
                self._process_api_exception(e, result)

        except Exception as e:
            result.add_error(f"Kubernetes validation error: {str(e)}")

        return result

    async def _ensure_kubernetes_client(self) -> None:
        """Initialize Kubernetes clients if not already done."""
        if not self._client_initialized:
            try:
                # Try to load in-cluster config first, then kubeconfig
                try:
                    config.load_incluster_config()
                except config.ConfigException:
                    config.load_kube_config()

                self._custom_objects_api = client.CustomObjectsApi()
                self._core_v1_api = client.CoreV1Api()
                self._client_initialized = True
            except Exception as e:
                raise RuntimeError(f"Failed to initialize Kubernetes client: {str(e)}")

    async def _validate_ray_crd(
        self, parsed_yaml: Dict[str, Any], result: ValidationResult
    ) -> None:
        """Validate Ray CRD using dry-run."""
        kind = parsed_yaml.get("kind")
        namespace = parsed_yaml.get("metadata", {}).get("namespace", "default")

        if kind == "RayCluster":
            plural = "rayclusters"
        elif kind == "RayJob":
            plural = "rayjobs"
        else:
            result.add_error(f"Unknown Ray CRD kind: {kind}")
            return

        try:
            # Use dry-run to validate without creating the resource
            await asyncio.to_thread(
                self._custom_objects_api.create_namespaced_custom_object,
                group="ray.io",
                version="v1",
                namespace=namespace,
                plural=plural,
                body=parsed_yaml,
                dry_run=["All"],
            )
        except ApiException as e:
            if e.status != 409:  # Ignore "already exists" errors in dry-run
                raise e

    async def _validate_service(
        self, parsed_yaml: Dict[str, Any], namespace: str, result: ValidationResult
    ) -> None:
        """Validate Service using dry-run."""
        try:
            await asyncio.to_thread(
                self._core_v1_api.create_namespaced_service,
                namespace=namespace,
                body=parsed_yaml,
                dry_run=["All"],
            )
        except ApiException as e:
            if e.status != 409:  # Ignore "already exists" errors in dry-run
                raise e

    def _process_api_exception(
        self, error: ApiException, result: ValidationResult
    ) -> None:
        """Process Kubernetes API exceptions into ValidationMessages."""
        try:
            error_body = json.loads(error.body) if error.body else {}
            message = error_body.get("message", str(error))

            # Extract field-specific errors from Kubernetes API response
            if "details" in error_body and "causes" in error_body["details"]:
                for cause in error_body["details"]["causes"]:
                    field_path = cause.get("field", "unknown")
                    cause_message = cause.get("message", message)

                    result.add_error(
                        message=f"Kubernetes API error: {cause_message}",
                        field_path=field_path,
                        suggestion=self._generate_k8s_suggestion(
                            cause_message, field_path
                        ),
                    )
            else:
                result.add_error(
                    message=f"Kubernetes API error: {message}",
                    suggestion="Check the resource specification against Kubernetes API requirements",
                )
        except:
            result.add_error(f"Kubernetes API validation failed: {str(error)}")

    def _generate_k8s_suggestion(self, message: str, field_path: str) -> str:
        """Generate suggestions based on Kubernetes API error messages."""
        message_lower = message.lower()

        if "invalid value" in message_lower:
            return f"Check the format and allowed values for field '{field_path}'"
        elif "required" in message_lower:
            return f"Add the required field '{field_path}'"
        elif "must be" in message_lower:
            return f"Update '{field_path}' to meet the specified requirements"
        elif "duplicate" in message_lower:
            return f"Remove duplicate values in '{field_path}'"
        else:
            return f"Review the specification for field '{field_path}'"


class SemanticValidator(BaseValidator):
    """Business logic validation for Ray-specific constraints."""

    async def validate(
        self, yaml_str: str, parsed_yaml: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Validate Ray-specific semantic constraints."""
        result = self._create_result()

        try:
            if parsed_yaml is None:
                parsed_yaml = yaml.safe_load(yaml_str)

            if not isinstance(parsed_yaml, dict):
                result.add_error("Invalid YAML structure for semantic validation")
                return result

            kind = parsed_yaml.get("kind")

            if kind == "RayCluster":
                self._validate_ray_cluster_semantics(parsed_yaml, result)
            elif kind == "RayJob":
                self._validate_ray_job_semantics(parsed_yaml, result)

        except Exception as e:
            result.add_error(f"Semantic validation error: {str(e)}")

        return result

    def _validate_ray_cluster_semantics(
        self, parsed_yaml: Dict[str, Any], result: ValidationResult
    ) -> None:
        """Validate Ray cluster semantic constraints."""
        spec = parsed_yaml.get("spec", {})

        # Validate Ray version compatibility
        ray_version = spec.get("rayVersion", "")
        if ray_version and not self._is_compatible_ray_version(ray_version):
            result.add_warning(
                f"Ray version {ray_version} may not be compatible with current KubeRay",
                field_path="spec.rayVersion",
                suggestion="Consider using a supported Ray version like '2.47.0'",
            )

        # Validate resource allocations
        head_group = spec.get("headGroupSpec", {})
        self._validate_resource_limits(head_group, "head", result)

        worker_groups = spec.get("workerGroupSpecs", [])
        for i, worker_group in enumerate(worker_groups):
            self._validate_resource_limits(worker_group, f"worker[{i}]", result)
            self._validate_worker_scaling(worker_group, f"worker[{i}]", result)

    def _validate_ray_job_semantics(
        self, parsed_yaml: Dict[str, Any], result: ValidationResult
    ) -> None:
        """Validate Ray job semantic constraints."""
        spec = parsed_yaml.get("spec", {})

        # Validate entrypoint
        entrypoint = spec.get("entrypoint", "")
        if entrypoint and not self._is_valid_entrypoint(entrypoint):
            result.add_warning(
                "Entrypoint may not be a valid Python command",
                field_path="spec.entrypoint",
                suggestion="Ensure entrypoint is a valid Python command like 'python script.py'",
            )

        # Validate TTL
        ttl = spec.get("ttlSecondsAfterFinished", 300)
        if ttl > 86400:  # 24 hours
            result.add_warning(
                "TTL is very long (>24 hours), which may waste resources",
                field_path="spec.ttlSecondsAfterFinished",
                suggestion="Consider a shorter TTL for automatic cleanup",
            )

        # Validate embedded cluster spec
        cluster_spec = spec.get("rayClusterSpec", {})
        if cluster_spec:
            self._validate_ray_cluster_semantics(
                {"spec": cluster_spec, "kind": "RayCluster"}, result
            )

    def _validate_resource_limits(
        self, group_spec: Dict[str, Any], group_name: str, result: ValidationResult
    ) -> None:
        """Validate resource limits are reasonable."""
        template = group_spec.get("template", {}).get("spec", {})
        containers = template.get("containers", [])

        for i, container in enumerate(containers):
            resources = container.get("resources", {})
            limits = resources.get("limits", {})
            requests = resources.get("requests", {})

            # Check if limits are set
            if not limits:
                result.add_warning(
                    f"No resource limits set for {group_name} container[{i}]",
                    field_path=f"spec.{group_name}GroupSpec.template.spec.containers[{i}].resources.limits",
                    suggestion="Set CPU and memory limits to prevent resource exhaustion",
                )

            # Check if requests match limits (recommended)
            if limits and requests:
                if limits.get("cpu") != requests.get("cpu"):
                    result.add_warning(
                        f"CPU requests don't match limits for {group_name} container[{i}]",
                        suggestion="Consider setting CPU requests equal to limits for guaranteed QoS",
                    )

    def _validate_worker_scaling(
        self, worker_spec: Dict[str, Any], group_name: str, result: ValidationResult
    ) -> None:
        """Validate worker group scaling configuration."""
        replicas = worker_spec.get("replicas", 1)
        min_replicas = worker_spec.get("minReplicas", 1)
        max_replicas = worker_spec.get("maxReplicas", 10)

        # Check scaling ratios
        if max_replicas > min_replicas * 10:
            result.add_warning(
                f"Large scaling ratio ({max_replicas}/{min_replicas}) for {group_name}",
                field_path=f"spec.workerGroupSpecs.maxReplicas",
                suggestion="Consider a smaller scaling ratio for more predictable behavior",
            )

        # Check if autoscaling is enabled but bounds are the same
        if min_replicas == max_replicas and min_replicas > 1:
            result.add_warning(
                f"Autoscaling bounds are equal for {group_name} - no scaling will occur",
                suggestion="Set different minReplicas and maxReplicas to enable autoscaling",
            )

    def _is_compatible_ray_version(self, version: str) -> bool:
        """Check if Ray version is in supported range."""
        try:
            major, minor, patch = map(int, version.split("."))
            # Support Ray 2.40+ (approximate KubeRay compatibility)
            return major >= 2 and minor >= 40
        except ValueError:
            return False

    def _is_valid_entrypoint(self, entrypoint: str) -> bool:
        """Basic validation of entrypoint command."""
        # Should start with python, python3, or contain .py
        entrypoint_lower = entrypoint.lower().strip()
        return (
            entrypoint_lower.startswith("python")
            or ".py" in entrypoint_lower
            or entrypoint_lower.startswith("ray ")
        )


class SecurityValidator(BaseValidator):
    """Security policy validation."""

    async def validate(
        self, yaml_str: str, parsed_yaml: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Validate security policies."""
        result = self._create_result()

        try:
            if parsed_yaml is None:
                parsed_yaml = yaml.safe_load(yaml_str)

            if not isinstance(parsed_yaml, dict):
                result.add_error("Invalid YAML structure for security validation")
                return result

            self._check_privileged_containers(parsed_yaml, result)
            self._check_image_sources(parsed_yaml, result)
            self._check_resource_limits(parsed_yaml, result)
            self._check_host_network(parsed_yaml, result)
            self._check_volume_mounts(parsed_yaml, result)

        except Exception as e:
            result.add_error(f"Security validation error: {str(e)}")

        return result

    def _check_privileged_containers(
        self, parsed_yaml: Dict[str, Any], result: ValidationResult
    ) -> None:
        """Check for privileged containers."""
        containers = self._extract_all_containers(parsed_yaml)

        for container_path, container in containers:
            security_context = container.get("securityContext", {})
            if security_context.get("privileged", False):
                result.add_error(
                    "Privileged containers are not allowed",
                    field_path=f"{container_path}.securityContext.privileged",
                    suggestion="Remove 'privileged: true' or set to 'privileged: false'",
                )

    def _check_image_sources(
        self, parsed_yaml: Dict[str, Any], result: ValidationResult
    ) -> None:
        """Check image sources for security."""
        containers = self._extract_all_containers(parsed_yaml)

        allowed_registries = [
            "rayproject/",
            "docker.io/rayproject/",
            "gcr.io/",
            "registry.k8s.io/",
        ]

        for container_path, container in containers:
            image = container.get("image", "")
            if image and not any(
                image.startswith(registry) for registry in allowed_registries
            ):
                result.add_warning(
                    f"Image from untrusted registry: {image}",
                    field_path=f"{container_path}.image",
                    suggestion="Use images from trusted registries like rayproject/, gcr.io/, or registry.k8s.io/",
                )

            if image and ":latest" in image:
                result.add_warning(
                    "Using ':latest' tag is not recommended for production",
                    field_path=f"{container_path}.image",
                    suggestion="Pin to a specific version tag for reproducible deployments",
                )

    def _check_resource_limits(
        self, parsed_yaml: Dict[str, Any], result: ValidationResult
    ) -> None:
        """Check that resource limits are set for security."""
        containers = self._extract_all_containers(parsed_yaml)

        for container_path, container in containers:
            resources = container.get("resources", {})
            limits = resources.get("limits", {})

            if not limits:
                result.add_warning(
                    "No resource limits set - may cause resource exhaustion",
                    field_path=f"{container_path}.resources.limits",
                    suggestion="Set CPU and memory limits to prevent resource abuse",
                )
            else:
                if "memory" not in limits:
                    result.add_warning(
                        "No memory limit set",
                        field_path=f"{container_path}.resources.limits.memory",
                        suggestion="Set memory limit to prevent OOM issues",
                    )

    def _check_host_network(
        self, parsed_yaml: Dict[str, Any], result: ValidationResult
    ) -> None:
        """Check for host network access."""
        pod_specs = self._extract_pod_specs(parsed_yaml)

        for spec_path, pod_spec in pod_specs:
            if pod_spec.get("hostNetwork", False):
                result.add_error(
                    "Host network access is not allowed",
                    field_path=f"{spec_path}.hostNetwork",
                    suggestion="Remove 'hostNetwork: true' for security",
                )

    def _check_volume_mounts(
        self, parsed_yaml: Dict[str, Any], result: ValidationResult
    ) -> None:
        """Check for potentially dangerous volume mounts."""
        pod_specs = self._extract_pod_specs(parsed_yaml)

        dangerous_paths = ["/var/run/docker.sock", "/proc", "/sys", "/dev"]

        for spec_path, pod_spec in pod_specs:
            volumes = pod_spec.get("volumes", [])

            for i, volume in enumerate(volumes):
                host_path = volume.get("hostPath", {}).get("path", "")
                if any(host_path.startswith(path) for path in dangerous_paths):
                    result.add_error(
                        f"Dangerous host path mount: {host_path}",
                        field_path=f"{spec_path}.volumes[{i}].hostPath.path",
                        suggestion="Avoid mounting sensitive host directories",
                    )

    def _extract_all_containers(
        self, parsed_yaml: Dict[str, Any]
    ) -> List[tuple[str, Dict[str, Any]]]:
        """Extract all containers from the YAML with their paths."""
        containers = []

        # Extract from different locations based on resource type
        spec = parsed_yaml.get("spec", {})

        # RayCluster containers
        if parsed_yaml.get("kind") == "RayCluster":
            # Head group containers
            head_template = (
                spec.get("headGroupSpec", {}).get("template", {}).get("spec", {})
            )
            for i, container in enumerate(head_template.get("containers", [])):
                containers.append(
                    (f"spec.headGroupSpec.template.spec.containers[{i}]", container)
                )

            # Worker group containers
            for wg_i, worker_group in enumerate(spec.get("workerGroupSpecs", [])):
                worker_template = worker_group.get("template", {}).get("spec", {})
                for c_i, container in enumerate(worker_template.get("containers", [])):
                    containers.append(
                        (
                            f"spec.workerGroupSpecs[{wg_i}].template.spec.containers[{c_i}]",
                            container,
                        )
                    )

        # RayJob containers (embedded cluster)
        elif parsed_yaml.get("kind") == "RayJob":
            cluster_spec = spec.get("rayClusterSpec", {})
            if cluster_spec:
                # Recursively extract from embedded cluster
                embedded_cluster = {"kind": "RayCluster", "spec": cluster_spec}
                containers.extend(self._extract_all_containers(embedded_cluster))

        return containers

    def _extract_pod_specs(
        self, parsed_yaml: Dict[str, Any]
    ) -> List[tuple[str, Dict[str, Any]]]:
        """Extract all pod specs from the YAML with their paths."""
        pod_specs = []
        spec = parsed_yaml.get("spec", {})

        if parsed_yaml.get("kind") == "RayCluster":
            # Head group pod spec
            head_spec = (
                spec.get("headGroupSpec", {}).get("template", {}).get("spec", {})
            )
            if head_spec:
                pod_specs.append(("spec.headGroupSpec.template.spec", head_spec))

            # Worker group pod specs
            for i, worker_group in enumerate(spec.get("workerGroupSpecs", [])):
                worker_spec = worker_group.get("template", {}).get("spec", {})
                if worker_spec:
                    pod_specs.append(
                        (f"spec.workerGroupSpecs[{i}].template.spec", worker_spec)
                    )

        elif parsed_yaml.get("kind") == "RayJob":
            # Embedded cluster pod specs
            cluster_spec = spec.get("rayClusterSpec", {})
            if cluster_spec:
                embedded_cluster = {"kind": "RayCluster", "spec": cluster_spec}
                pod_specs.extend(self._extract_pod_specs(embedded_cluster))

        return pod_specs


class CorrectiveValidator(BaseValidator):
    """Attempts to auto-correct common issues."""

    async def validate(
        self, yaml_str: str, parsed_yaml: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Validate and attempt auto-correction."""
        result = self._create_result()
        corrected_yaml = yaml_str

        try:
            if parsed_yaml is None:
                parsed_yaml = yaml.safe_load(yaml_str)

            if not isinstance(parsed_yaml, dict):
                result.add_error("Invalid YAML structure for corrective validation")
                return result

            # Create a copy for modifications
            corrected_data = parsed_yaml.copy()
            corrections_made = False

            # Apply corrections
            if self._add_missing_defaults(corrected_data):
                corrections_made = True

            if self._fix_resource_formats(corrected_data, result):
                corrections_made = True

            if self._normalize_naming(corrected_data, result):
                corrections_made = True

            if self._add_required_labels(corrected_data):
                corrections_made = True

            # Generate corrected YAML if changes were made
            if corrections_made:
                result.corrected_yaml = yaml.dump(
                    corrected_data, default_flow_style=False
                )
                result.add_warning(
                    "Auto-corrections applied to YAML",
                    suggestion="Review the corrected YAML before applying",
                )

        except Exception as e:
            result.add_error(f"Corrective validation error: {str(e)}")

        return result

    def _add_missing_defaults(self, data: Dict[str, Any]) -> bool:
        """Add missing default values."""
        corrections_made = False

        # Add default namespace if missing
        metadata = data.get("metadata", {})
        if "namespace" not in metadata:
            metadata["namespace"] = "default"
            data["metadata"] = metadata
            corrections_made = True

        # Add default resource limits if missing
        containers = self._get_all_containers(data)
        for container in containers:
            if "resources" not in container:
                container["resources"] = {
                    "limits": {"cpu": "1", "memory": "2Gi"},
                    "requests": {"cpu": "1", "memory": "2Gi"},
                }
                corrections_made = True
            elif "limits" not in container["resources"]:
                container["resources"]["limits"] = {"cpu": "1", "memory": "2Gi"}
                corrections_made = True

        return corrections_made

    def _fix_resource_formats(
        self, data: Dict[str, Any], result: ValidationResult
    ) -> bool:
        """Fix common resource format issues."""
        corrections_made = False

        containers = self._get_all_containers(data)
        for container in containers:
            resources = container.get("resources", {})

            for resource_type in ["limits", "requests"]:
                resource_spec = resources.get(resource_type, {})

                # Fix CPU format
                cpu = resource_spec.get("cpu")
                if cpu and isinstance(cpu, (int, float)):
                    resource_spec["cpu"] = str(cpu)
                    corrections_made = True

                # Fix memory format
                memory = resource_spec.get("memory")
                if memory and isinstance(memory, (int, float)):
                    # Assume bytes, convert to appropriate unit
                    if memory >= 1024**3:
                        resource_spec["memory"] = f"{memory // (1024**3)}Gi"
                    elif memory >= 1024**2:
                        resource_spec["memory"] = f"{memory // (1024**2)}Mi"
                    else:
                        resource_spec["memory"] = f"{memory}Ki"
                    corrections_made = True

        return corrections_made

    def _normalize_naming(self, data: Dict[str, Any], result: ValidationResult) -> bool:
        """Normalize naming conventions."""
        corrections_made = False

        # Normalize resource name
        metadata = data.get("metadata", {})
        name = metadata.get("name", "")

        if name:
            # Convert to lowercase and replace invalid characters
            normalized_name = re.sub(r"[^a-z0-9-]", "-", name.lower())
            normalized_name = re.sub(
                r"-+", "-", normalized_name
            )  # Remove multiple consecutive hyphens
            normalized_name = normalized_name.strip(
                "-"
            )  # Remove leading/trailing hyphens

            if normalized_name != name:
                metadata["name"] = normalized_name
                corrections_made = True
                result.add_warning(
                    f"Normalized resource name from '{name}' to '{normalized_name}'",
                    field_path="metadata.name",
                )

        return corrections_made

    def _add_required_labels(self, data: Dict[str, Any]) -> bool:
        """Add required labels."""
        corrections_made = False

        metadata = data.get("metadata", {})
        labels = metadata.get("labels", {})

        # Add common labels if missing
        name = metadata.get("name", "unknown")
        kind = data.get("kind", "unknown").lower()

        required_labels = {
            "app.kubernetes.io/name": name,
            "app.kubernetes.io/component": kind,
            "app.kubernetes.io/managed-by": "ray-mcp",
        }

        for label_key, label_value in required_labels.items():
            if label_key not in labels:
                labels[label_key] = label_value
                corrections_made = True

        if corrections_made:
            metadata["labels"] = labels
            data["metadata"] = metadata

        return corrections_made

    def _get_all_containers(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get all containers from the YAML structure."""
        containers = []
        spec = data.get("spec", {})

        if data.get("kind") == "RayCluster":
            # Head group containers
            head_template = (
                spec.get("headGroupSpec", {}).get("template", {}).get("spec", {})
            )
            containers.extend(head_template.get("containers", []))

            # Worker group containers
            for worker_group in spec.get("workerGroupSpecs", []):
                worker_template = worker_group.get("template", {}).get("spec", {})
                containers.extend(worker_template.get("containers", []))

        elif data.get("kind") == "RayJob":
            # Embedded cluster containers
            cluster_spec = spec.get("rayClusterSpec", {})
            if cluster_spec:
                embedded_data = {"kind": "RayCluster", "spec": cluster_spec}
                containers.extend(self._get_all_containers(embedded_data))

        return containers
