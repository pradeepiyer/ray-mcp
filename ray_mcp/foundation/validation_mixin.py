"""Validation mixin for Ray MCP server."""

import re
from typing import Any, Dict, List, Optional, Union

from .logging_utils import ResponseFormatter


class ValidationResult:
    """Result of a validation operation."""

    def __init__(self, is_valid: bool, error_message: Optional[str] = None):
        self.is_valid = is_valid
        self.error_message = error_message

    def __bool__(self):
        return self.is_valid


class ValidationMixin:
    """Mixin class providing common validation methods for Ray MCP components."""

    @staticmethod
    def validate_job_id(job_id: str) -> ValidationResult:
        """Validate a job ID format.

        Args:
            job_id: The job ID to validate

        Returns:
            ValidationResult: Validation result with success/failure and error message
        """
        if not job_id:
            return ValidationResult(False, "job_id cannot be empty")

        if not isinstance(job_id, str):
            return ValidationResult(False, "job_id must be a string")

        # Check for valid patterns: UUID format, raysubmit format, or Kubernetes resource name
        uuid_pattern = r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$"
        raysubmit_pattern = r"^raysubmit_.*"
        k8s_name_pattern = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"

        if (
            re.match(uuid_pattern, job_id)
            or re.match(raysubmit_pattern, job_id)
            or (re.match(k8s_name_pattern, job_id) and len(job_id) <= 63)
        ):
            return ValidationResult(True)

        return ValidationResult(
            False,
            "job_id must be a valid UUID, raysubmit format, or Kubernetes resource name",
        )

    @staticmethod
    def validate_cluster_name(cluster_name: str) -> ValidationResult:
        """Validate a cluster name format.

        Args:
            cluster_name: The cluster name to validate

        Returns:
            ValidationResult: Validation result with success/failure and error message
        """
        if not cluster_name:
            return ValidationResult(False, "cluster_name cannot be empty")

        if not isinstance(cluster_name, str):
            return ValidationResult(False, "cluster_name must be a string")

        # For Kubernetes clusters, validate resource name format
        k8s_name_pattern = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"
        if re.match(k8s_name_pattern, cluster_name) and len(cluster_name) <= 63:
            return ValidationResult(True)

        # For local clusters, allow more flexible naming
        if len(cluster_name) <= 100 and not cluster_name.isspace():
            return ValidationResult(True)

        return ValidationResult(
            False,
            "cluster_name must be a valid identifier (alphanumeric with hyphens for Kubernetes, or any non-whitespace string for local)",
        )

    @staticmethod
    def validate_namespace(namespace: str) -> ValidationResult:
        """Validate a Kubernetes namespace.

        Args:
            namespace: The namespace to validate

        Returns:
            ValidationResult: Validation result with success/failure and error message
        """
        if not namespace:
            return ValidationResult(False, "namespace cannot be empty")

        if not isinstance(namespace, str):
            return ValidationResult(False, "namespace must be a string")

        # Kubernetes namespace validation
        if len(namespace) > 63:
            return ValidationResult(
                False, "namespace cannot be longer than 63 characters"
            )

        # DNS label format
        dns_pattern = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"
        if not re.match(dns_pattern, namespace):
            return ValidationResult(
                False,
                "namespace must be a valid DNS label (lowercase alphanumeric with hyphens)",
            )

        return ValidationResult(True)

    @staticmethod
    def validate_kubernetes_resource(resource_dict: Dict[str, Any]) -> ValidationResult:
        """Validate a Kubernetes resource specification.

        Args:
            resource_dict: Dictionary containing Kubernetes resource spec

        Returns:
            ValidationResult: Validation result with success/failure and error message
        """
        if not isinstance(resource_dict, dict):
            return ValidationResult(False, "resource must be a dictionary")

        # Check for required fields
        if "apiVersion" not in resource_dict:
            return ValidationResult(False, "resource must have 'apiVersion' field")

        if "kind" not in resource_dict:
            return ValidationResult(False, "resource must have 'kind' field")

        if "metadata" not in resource_dict:
            return ValidationResult(False, "resource must have 'metadata' field")

        metadata = resource_dict["metadata"]
        if not isinstance(metadata, dict):
            return ValidationResult(False, "metadata must be a dictionary")

        if "name" not in metadata:
            return ValidationResult(False, "metadata must have 'name' field")

        # Validate name format
        name_validation = ValidationMixin.validate_cluster_name(metadata["name"])
        if not name_validation:
            return ValidationResult(
                False, f"Invalid resource name: {name_validation.error_message}"
            )

        # Validate namespace if present
        if "namespace" in metadata:
            namespace_validation = ValidationMixin.validate_namespace(
                metadata["namespace"]
            )
            if not namespace_validation:
                return ValidationResult(
                    False, f"Invalid namespace: {namespace_validation.error_message}"
                )

        return ValidationResult(True)

    @staticmethod
    def validate_port_number(port: Union[int, str]) -> ValidationResult:
        """Validate a port number.

        Args:
            port: The port number to validate (int or string)

        Returns:
            ValidationResult: Validation result with success/failure and error message
        """
        try:
            port_int = int(port)
        except (ValueError, TypeError):
            return ValidationResult(False, "port must be a valid integer")

        if port_int < 1 or port_int > 65535:
            return ValidationResult(False, "port must be between 1 and 65535")

        return ValidationResult(True)

    @staticmethod
    def validate_resource_limits(resources: Dict[str, Any]) -> ValidationResult:
        """Validate resource limits specification.

        Args:
            resources: Dictionary containing resource specifications

        Returns:
            ValidationResult: Validation result with success/failure and error message
        """
        if not isinstance(resources, dict):
            return ValidationResult(False, "resources must be a dictionary")

        # Validate CPU specification
        if "num_cpus" in resources:
            cpu = resources["num_cpus"]
            if not isinstance(cpu, (int, float)) or cpu <= 0:
                return ValidationResult(False, "num_cpus must be a positive number")

        # Validate GPU specification
        if "num_gpus" in resources:
            gpu = resources["num_gpus"]
            if not isinstance(gpu, (int, float)) or gpu < 0:
                return ValidationResult(False, "num_gpus must be a non-negative number")

        # Validate memory specification
        if "memory" in resources:
            memory = resources["memory"]
            if isinstance(memory, str):
                # Validate memory string format (e.g., "8Gi", "512Mi")
                memory_pattern = r"^\d+(\.\d+)?(Ki|Mi|Gi|Ti|K|M|G|T)?$"
                if not re.match(memory_pattern, memory):
                    return ValidationResult(
                        False, "memory must be a valid size (e.g., '8Gi', '512Mi')"
                    )
            elif isinstance(memory, (int, float)):
                if memory <= 0:
                    return ValidationResult(False, "memory must be a positive number")
            else:
                return ValidationResult(False, "memory must be a string or number")

        return ValidationResult(True)

    @staticmethod
    def validate_entrypoint(entrypoint: str) -> ValidationResult:
        """Validate a job entrypoint.

        Args:
            entrypoint: The job entrypoint command to validate

        Returns:
            ValidationResult: Validation result with success/failure and error message
        """
        if not entrypoint:
            return ValidationResult(False, "entrypoint cannot be empty")

        if not isinstance(entrypoint, str):
            return ValidationResult(False, "entrypoint must be a string")

        # Basic validation - check it's not just whitespace
        if entrypoint.isspace():
            return ValidationResult(False, "entrypoint cannot be only whitespace")

        return ValidationResult(True)

    @staticmethod
    def validate_required_params(
        params: Dict[str, Any], required: List[str]
    ) -> ValidationResult:
        """Validate that required parameters are present.

        Args:
            params: Dictionary of parameters to validate
            required: List of required parameter names

        Returns:
            ValidationResult: Validation result with success/failure and error message
        """
        missing_params = [param for param in required if param not in params]
        if missing_params:
            return ValidationResult(
                False, f"Missing required parameters: {', '.join(missing_params)}"
            )

        return ValidationResult(True)

    @staticmethod
    def validate_enum_value(
        value: str, valid_values: List[str], param_name: str = "value"
    ) -> ValidationResult:
        """Validate that a value is in a list of valid options.

        Args:
            value: The value to validate
            valid_values: List of valid values
            param_name: Name of the parameter for error messages

        Returns:
            ValidationResult: Validation result with success/failure and error message
        """
        if value not in valid_values:
            return ValidationResult(
                False, f"{param_name} must be one of: {', '.join(valid_values)}"
            )

        return ValidationResult(True)

    # Helper methods for standardized error responses
    @staticmethod
    def validate_and_format_error(
        validation_result: ValidationResult, param_name: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Validate and return formatted error response if validation fails.

        Args:
            validation_result: Result from validation method
            param_name: Parameter name for context

        Returns:
            Dict with error response if validation fails, None if validation passes
        """
        if not validation_result.is_valid:
            context = f" for {param_name}" if param_name else ""
            return ResponseFormatter.format_validation_error(
                f"Validation failed{context}: {validation_result.error_message}"
            )
        return None

    @staticmethod
    def validate_job_id_with_response(job_id: str) -> Optional[Dict[str, Any]]:
        """Validate job ID and return error response if invalid."""
        result = ValidationMixin.validate_job_id(job_id)
        return ValidationMixin.validate_and_format_error(result, "job_id")

    @staticmethod
    def validate_cluster_name_with_response(
        cluster_name: str,
    ) -> Optional[Dict[str, Any]]:
        """Validate cluster name and return error response if invalid."""
        result = ValidationMixin.validate_cluster_name(cluster_name)
        return ValidationMixin.validate_and_format_error(result, "cluster_name")

    @staticmethod
    def validate_required_params_with_response(
        params: Dict[str, Any], required: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Validate required parameters and return error response if missing."""
        result = ValidationMixin.validate_required_params(params, required)
        return ValidationMixin.validate_and_format_error(result)
