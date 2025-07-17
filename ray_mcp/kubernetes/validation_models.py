"""Pydantic models for Ray cluster and job validation."""

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, validator


class ValidationSeverity(str, Enum):
    """Validation message severity levels."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationMessage(BaseModel):
    """Represents a single validation message."""

    model_config = ConfigDict(frozen=True)

    severity: ValidationSeverity
    message: str
    field_path: Optional[str] = None
    suggestion: Optional[str] = None
    code: Optional[str] = None


class ValidationResult(BaseModel):
    """Represents the result of a validation operation."""

    model_config = ConfigDict(frozen=True)

    valid: bool
    messages: List[ValidationMessage] = Field(default_factory=list)
    corrected_yaml: Optional[str] = None

    @property
    def errors(self) -> List[ValidationMessage]:
        """Get only error messages."""
        return [
            msg for msg in self.messages if msg.severity == ValidationSeverity.ERROR
        ]

    @property
    def warnings(self) -> List[ValidationMessage]:
        """Get only warning messages."""
        return [
            msg for msg in self.messages if msg.severity == ValidationSeverity.WARNING
        ]

    def add_error(
        self,
        message: str,
        field_path: Optional[str] = None,
        suggestion: Optional[str] = None,
        code: Optional[str] = None,
    ) -> None:
        """Add an error message."""
        validation_msg = ValidationMessage(
            severity=ValidationSeverity.ERROR,
            message=message,
            field_path=field_path,
            suggestion=suggestion,
            code=code,
        )
        # Create new list to maintain immutability
        new_messages = list(self.messages) + [validation_msg]
        object.__setattr__(self, "messages", new_messages)
        object.__setattr__(self, "valid", False)

    def add_warning(
        self,
        message: str,
        field_path: Optional[str] = None,
        suggestion: Optional[str] = None,
        code: Optional[str] = None,
    ) -> None:
        """Add a warning message."""
        validation_msg = ValidationMessage(
            severity=ValidationSeverity.WARNING,
            message=message,
            field_path=field_path,
            suggestion=suggestion,
            code=code,
        )
        # Create new list to maintain immutability
        new_messages = list(self.messages) + [validation_msg]
        object.__setattr__(self, "messages", new_messages)


class ResourceSpec(BaseModel):
    """Resource specification for containers."""

    model_config = ConfigDict(str_strip_whitespace=True)

    cpu: str = Field(default="1", pattern=r"^\d+(\.\d+)?m?$")
    memory: str = Field(default="2Gi", pattern=r"^\d+(\.\d+)?(Mi|Gi|Ti|Ki|M|G|T|K)?$")
    nvidia_gpu: Optional[int] = Field(default=None, alias="nvidia.com/gpu", ge=0)

    @validator("cpu")
    def validate_cpu(cls, v):
        """Validate CPU format."""
        if v.endswith("m"):
            # Millicpu format
            try:
                int(v[:-1])
            except ValueError:
                raise ValueError(f"Invalid CPU format: {v}")
        else:
            try:
                float(v)
            except ValueError:
                raise ValueError(f"Invalid CPU format: {v}")
        return v

    @validator("memory")
    def validate_memory(cls, v):
        """Validate memory format."""
        import re

        if not re.match(r"^\d+(\.\d+)?(Mi|Gi|Ti|Ki|M|G|T|K)?$", v):
            raise ValueError(
                f"Invalid memory format: {v}. Expected format like '2Gi', '512Mi', etc."
            )
        return v


class ContainerSpec(BaseModel):
    """Container specification."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str
    image: str = "rayproject/ray:2.47.0"
    resources: Optional[Dict[str, ResourceSpec]] = None
    ports: Optional[List[Dict[str, Union[int, str]]]] = None
    lifecycle: Optional[Dict[str, Any]] = None

    @validator("image")
    def validate_image(cls, v):
        """Validate image format."""
        if not v or ":" not in v:
            raise ValueError("Image must include a tag (e.g., 'rayproject/ray:2.47.0')")
        return v


class PodTemplateSpec(BaseModel):
    """Pod template specification."""

    containers: List[ContainerSpec]
    restartPolicy: Optional[str] = "Always"

    @validator("containers")
    def validate_containers(cls, v):
        """Ensure at least one container is specified."""
        if not v:
            raise ValueError("At least one container must be specified")
        return v


class HeadGroupSpec(BaseModel):
    """Ray head group specification."""

    rayStartParams: Optional[Dict[str, str]] = Field(
        default_factory=lambda: {"dashboard-host": "0.0.0.0"}
    )
    template: Dict[str, PodTemplateSpec]

    @validator("template")
    def validate_template(cls, v):
        """Ensure template has spec."""
        if "spec" not in v:
            raise ValueError("Template must have 'spec' field")
        return v


class WorkerGroupSpec(BaseModel):
    """Ray worker group specification."""

    replicas: int = Field(default=1, ge=0, le=1000)
    minReplicas: int = Field(default=1, ge=0)
    maxReplicas: int = Field(default=10, ge=1)
    groupName: str = "worker-group"
    rayStartParams: Optional[Dict[str, str]] = Field(default_factory=dict)
    template: Dict[str, PodTemplateSpec]

    @validator("maxReplicas")
    def validate_max_replicas(cls, v, values):
        """Ensure maxReplicas >= minReplicas."""
        min_replicas = values.get("minReplicas", 1)
        if v < min_replicas:
            raise ValueError(
                f"maxReplicas ({v}) must be >= minReplicas ({min_replicas})"
            )
        return v

    @validator("replicas")
    def validate_replicas(cls, v, values):
        """Ensure replicas is within bounds."""
        min_replicas = values.get("minReplicas", 1)
        max_replicas = values.get("maxReplicas", 10)
        if v < min_replicas or v > max_replicas:
            raise ValueError(
                f"replicas ({v}) must be between minReplicas ({min_replicas}) and maxReplicas ({max_replicas})"
            )
        return v


class RayClusterSpec(BaseModel):
    """Ray cluster specification."""

    rayVersion: str = "2.47.0"
    enableInTreeAutoscaling: bool = True
    headGroupSpec: HeadGroupSpec
    workerGroupSpecs: List[WorkerGroupSpec] = Field(default_factory=list)

    @validator("rayVersion")
    def validate_ray_version(cls, v):
        """Validate Ray version format."""
        import re

        if not re.match(r"^\d+\.\d+\.\d+$", v):
            raise ValueError(
                f"Invalid Ray version format: {v}. Expected format: 'X.Y.Z'"
            )
        return v


class RuntimeEnv(BaseModel):
    """Runtime environment configuration."""

    pip: Optional[List[str]] = None
    conda: Optional[Union[str, Dict[str, Any]]] = None
    working_dir: Optional[str] = None
    git: Optional[Dict[str, str]] = None
    env_vars: Optional[Dict[str, str]] = None

    @validator("pip")
    def validate_pip(cls, v):
        """Validate pip packages."""
        if v is not None and not isinstance(v, list):
            raise ValueError("pip must be a list of package names")
        return v

    @validator("working_dir")
    def validate_working_dir(cls, v):
        """Validate working directory path."""
        if v is not None and not v.startswith("/"):
            raise ValueError("working_dir must be an absolute path starting with '/'")
        return v


class RayJobSpec(BaseModel):
    """Ray job specification."""

    entrypoint: str
    runtimeEnvYAML: Optional[str] = None
    rayClusterSpec: RayClusterSpec
    shutdownAfterJobFinishes: bool = True
    ttlSecondsAfterFinished: int = Field(default=300, ge=0, le=86400)  # Max 24 hours

    @validator("entrypoint")
    def validate_entrypoint(cls, v):
        """Validate entrypoint is not empty."""
        if not v.strip():
            raise ValueError("entrypoint cannot be empty")
        return v


class KubernetesMetadata(BaseModel):
    """Kubernetes resource metadata."""

    name: str = Field(min_length=1, max_length=63)
    namespace: str = Field(default="default", min_length=1, max_length=63)
    labels: Optional[Dict[str, str]] = None
    annotations: Optional[Dict[str, str]] = None

    @validator("name")
    def validate_name(cls, v):
        """Validate Kubernetes resource name."""
        import re

        if not re.match(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", v):
            raise ValueError(
                f"Invalid resource name: {v}. Must be lowercase alphanumeric with hyphens, "
                "start and end with alphanumeric character"
            )
        return v

    @validator("namespace")
    def validate_namespace(cls, v):
        """Validate Kubernetes namespace."""
        import re

        if not re.match(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", v):
            raise ValueError(
                f"Invalid namespace: {v}. Must be lowercase alphanumeric with hyphens, "
                "start and end with alphanumeric character"
            )
        return v


class RayCluster(BaseModel):
    """Complete Ray cluster manifest."""

    apiVersion: str = "ray.io/v1"
    kind: str = "RayCluster"
    metadata: KubernetesMetadata
    spec: RayClusterSpec

    @validator("apiVersion")
    def validate_api_version(cls, v):
        """Validate API version."""
        if v != "ray.io/v1":
            raise ValueError(f"Invalid apiVersion: {v}. Expected 'ray.io/v1'")
        return v

    @validator("kind")
    def validate_kind(cls, v):
        """Validate resource kind."""
        if v != "RayCluster":
            raise ValueError(f"Invalid kind: {v}. Expected 'RayCluster'")
        return v


class RayJob(BaseModel):
    """Complete Ray job manifest."""

    apiVersion: str = "ray.io/v1"
    kind: str = "RayJob"
    metadata: KubernetesMetadata
    spec: RayJobSpec

    @validator("apiVersion")
    def validate_api_version(cls, v):
        """Validate API version."""
        if v != "ray.io/v1":
            raise ValueError(f"Invalid apiVersion: {v}. Expected 'ray.io/v1'")
        return v

    @validator("kind")
    def validate_kind(cls, v):
        """Validate resource kind."""
        if v != "RayJob":
            raise ValueError(f"Invalid kind: {v}. Expected 'RayJob'")
        return v


class ServiceSpec(BaseModel):
    """Kubernetes service specification."""

    selector: Dict[str, str]
    ports: List[Dict[str, Union[int, str]]]
    type: str = Field(default="ClusterIP")

    @validator("type")
    def validate_service_type(cls, v):
        """Validate service type."""
        valid_types = ["ClusterIP", "NodePort", "LoadBalancer", "ExternalName"]
        if v not in valid_types:
            raise ValueError(f"Invalid service type: {v}. Valid types: {valid_types}")
        return v

    @validator("ports")
    def validate_ports(cls, v):
        """Validate service ports."""
        if not v:
            raise ValueError("At least one port must be specified")

        for port in v:
            if "port" not in port:
                raise ValueError("Each port must have 'port' field")
            if (
                not isinstance(port["port"], int)
                or port["port"] < 1
                or port["port"] > 65535
            ):
                raise ValueError(f"Invalid port number: {port['port']}")
        return v


class Service(BaseModel):
    """Complete Kubernetes service manifest."""

    apiVersion: str = "v1"
    kind: str = "Service"
    metadata: KubernetesMetadata
    spec: ServiceSpec

    @validator("apiVersion")
    def validate_api_version(cls, v):
        """Validate API version."""
        if v != "v1":
            raise ValueError(f"Invalid apiVersion: {v}. Expected 'v1'")
        return v

    @validator("kind")
    def validate_kind(cls, v):
        """Validate resource kind."""
        if v != "Service":
            raise ValueError(f"Invalid kind: {v}. Expected 'Service'")
        return v
