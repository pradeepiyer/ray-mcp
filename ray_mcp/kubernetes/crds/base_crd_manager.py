"""Base CRD manager class to eliminate duplication between Ray resource managers."""

from abc import ABC, abstractmethod
import json
from typing import Any, Dict

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    yaml = None

from ...foundation.import_utils import get_logging_utils


class BaseCRDManager(ABC):
    """Base class for Ray Custom Resource Definition managers."""

    def __init__(self):
        """Initialize the base CRD manager."""
        # Get utilities from import system
        logging_utils = get_logging_utils()
        self._LoggingUtility = logging_utils["LoggingUtility"]
        self._ResponseFormatter = logging_utils["ResponseFormatter"]

    @abstractmethod
    def create_spec(self, **kwargs) -> Dict[str, Any]:
        """Create resource specification. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def validate_spec(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Validate resource specification. Must be implemented by subclasses."""
        pass

    def to_yaml(self, spec: Dict[str, Any]) -> str:
        """Convert specification to YAML."""
        if not YAML_AVAILABLE:
            raise RuntimeError(
                "PyYAML is not available. Please install pyyaml package."
            )
        return yaml.dump(spec, default_flow_style=False, sort_keys=False)

    def to_json(self, spec: Dict[str, Any]) -> str:
        """Convert specification to JSON."""
        return json.dumps(spec, indent=2)

    def _validate_required_fields(
        self,
        spec: Dict[str, Any],
        required_fields: list,
        expected_api_version: str,
        expected_kind: str,
    ) -> list:
        """Validate common required fields for Ray resources."""
        errors = []

        # Check required top-level fields
        for field in required_fields:
            if field not in spec:
                errors.append(f"Missing required field: {field}")

        if spec.get("apiVersion") != expected_api_version:
            errors.append(
                f"Invalid apiVersion: expected '{expected_api_version}', got '{spec.get('apiVersion')}'"
            )

        if spec.get("kind") != expected_kind:
            errors.append(
                f"Invalid kind: expected '{expected_kind}', got '{spec.get('kind')}'"
            )

        # Validate metadata
        metadata = spec.get("metadata", {})
        if not metadata.get("name"):
            errors.append("Missing metadata.name")

        return errors

    def _build_base_metadata(
        self, name: str, namespace: str, resource_type: str, **kwargs
    ) -> Dict[str, Any]:
        """Build base metadata for Ray resources."""
        metadata = {
            "name": name,
            "namespace": namespace,
            "labels": {
                "app.kubernetes.io/name": f"ray{resource_type}",
                "app.kubernetes.io/component": f"ray-{resource_type}",
                "app.kubernetes.io/managed-by": "ray-mcp",
            },
        }

        # Add any additional kwargs to metadata labels
        if kwargs:
            metadata["labels"].update(
                {
                    f"ray-mcp.{k}": str(v)
                    for k, v in kwargs.items()
                    if isinstance(v, (str, int, bool))
                }
            )

        return metadata

    def _validate_positive_integer(
        self, value: Any, field_name: str, allow_zero: bool = False
    ) -> str:
        """Validate that a value is a positive integer."""
        if value is None:
            return ""

        min_value = 0 if allow_zero else 1
        if not isinstance(value, int) or value < min_value:
            operator = "non-negative" if allow_zero else "positive"
            return f"{field_name} must be a {operator} integer"

        return ""

    def _validate_non_empty_string(self, value: Any, field_name: str) -> str:
        """Validate that a value is a non-empty string."""
        if value is None:
            return ""

        if not isinstance(value, str) or not value.strip():
            return f"{field_name} must be a non-empty string"

        return ""
