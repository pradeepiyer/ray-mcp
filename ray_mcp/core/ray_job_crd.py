"""RayJob Custom Resource Definition management."""

import json
import uuid
from typing import Any, Dict, List, Optional

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    yaml = None

try:
    from ..logging_utils import LoggingUtility, ResponseFormatter
except ImportError:
    # Fallback for direct execution
    import os
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from logging_utils import LoggingUtility, ResponseFormatter

from .interfaces import RayJobCRD


class RayJobCRDManager(RayJobCRD):
    """Manages RayJob Custom Resource Definition with schema validation and serialization."""

    def __init__(self):
        self._response_formatter = ResponseFormatter()

    @ResponseFormatter.handle_exceptions("create ray job spec")
    def create_spec(
        self, 
        entrypoint: str, 
        runtime_env: Optional[Dict[str, Any]] = None,
        job_name: Optional[str] = None,
        namespace: str = "default",
        cluster_selector: Optional[Dict[str, str]] = None,
        suspend: bool = False,
        ttl_seconds_after_finished: int = 86400,  # 24 hours
        active_deadline_seconds: Optional[int] = None,
        backoff_limit: int = 0,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Create RayJob specification with validation."""
        
        # Generate job name if not provided
        if not job_name:
            job_name = f"ray-job-{uuid.uuid4().hex[:8]}"

        # Validate entrypoint
        if not entrypoint or not isinstance(entrypoint, str):
            return self._response_formatter.format_error_response(
                "create ray job spec",
                Exception("entrypoint must be a non-empty string")
            )

        # Validate runtime environment
        if runtime_env is not None:
            runtime_validation = self._validate_runtime_env(runtime_env)
            if not runtime_validation["valid"]:
                return self._response_formatter.format_error_response(
                    "create ray job spec",
                    Exception(f"Invalid runtime_env: {runtime_validation['errors']}")
                )

        # Build the RayJob specification
        ray_job_spec = {
            "apiVersion": "ray.io/v1",
            "kind": "RayJob",
            "metadata": {
                "name": job_name,
                "namespace": namespace,
                "labels": {
                    "app.kubernetes.io/name": "rayjob",
                    "app.kubernetes.io/component": "ray-job",
                    "app.kubernetes.io/managed-by": "ray-mcp"
                }
            },
            "spec": {
                "entrypoint": entrypoint,
                "ttlSecondsAfterFinished": ttl_seconds_after_finished,
                "runtimeEnvYAML": self._format_runtime_env(runtime_env) if runtime_env else "",
                "rayClusterSpec": self._build_default_cluster_spec(),
                "backoffLimit": backoff_limit,
                "suspend": suspend
            }
        }

        # Add cluster selector if provided
        if cluster_selector:
            ray_job_spec["spec"]["clusterSelector"] = cluster_selector
        
        # Add active deadline if provided
        if active_deadline_seconds:
            ray_job_spec["spec"]["activeDeadlineSeconds"] = active_deadline_seconds

        # Add any additional kwargs to metadata labels
        if kwargs:
            ray_job_spec["metadata"]["labels"].update({
                f"ray-mcp.{k}": str(v) for k, v in kwargs.items() 
                if isinstance(v, (str, int, bool))
            })

        return self._response_formatter.format_success_response(
            job_spec=ray_job_spec,
            job_name=job_name
        )

    @ResponseFormatter.handle_exceptions("validate ray job spec")
    def validate_spec(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Validate RayJob specification."""
        errors = []
        
        # Check required top-level fields
        required_fields = ["apiVersion", "kind", "metadata", "spec"]
        for field in required_fields:
            if field not in spec:
                errors.append(f"Missing required field: {field}")

        if spec.get("apiVersion") != "ray.io/v1":
            errors.append(f"Invalid apiVersion: expected 'ray.io/v1', got '{spec.get('apiVersion')}'")

        if spec.get("kind") != "RayJob":
            errors.append(f"Invalid kind: expected 'RayJob', got '{spec.get('kind')}'")

        # Validate metadata
        metadata = spec.get("metadata", {})
        if not metadata.get("name"):
            errors.append("Missing metadata.name")

        # Validate spec
        ray_spec = spec.get("spec", {})
        if not ray_spec.get("entrypoint"):
            errors.append("Missing spec.entrypoint")

        # Validate entrypoint is a string
        entrypoint = ray_spec.get("entrypoint")
        if entrypoint and not isinstance(entrypoint, str):
            errors.append("spec.entrypoint must be a string")

        # Validate TTL if present
        ttl = ray_spec.get("ttlSecondsAfterFinished")
        if ttl is not None:
            if not isinstance(ttl, int) or ttl < 0:
                errors.append("spec.ttlSecondsAfterFinished must be a non-negative integer")

        # Validate backoff limit if present
        backoff_limit = ray_spec.get("backoffLimit")
        if backoff_limit is not None:
            if not isinstance(backoff_limit, int) or backoff_limit < 0:
                errors.append("spec.backoffLimit must be a non-negative integer")

        # Validate active deadline if present
        deadline = ray_spec.get("activeDeadlineSeconds")
        if deadline is not None:
            if not isinstance(deadline, int) or deadline <= 0:
                errors.append("spec.activeDeadlineSeconds must be a positive integer")

        # Validate cluster selector if present
        selector = ray_spec.get("clusterSelector")
        if selector is not None:
            if not isinstance(selector, dict):
                errors.append("spec.clusterSelector must be a dictionary")

        return self._response_formatter.format_success_response(
            valid=len(errors) == 0,
            errors=errors
        )

    def to_yaml(self, spec: Dict[str, Any]) -> str:
        """Convert specification to YAML."""
        if not YAML_AVAILABLE:
            raise RuntimeError("PyYAML is not available. Please install pyyaml package.")
        
        return yaml.dump(spec, default_flow_style=False, sort_keys=False)

    def to_json(self, spec: Dict[str, Any]) -> str:
        """Convert specification to JSON."""
        return json.dumps(spec, indent=2)

    def _validate_runtime_env(self, runtime_env: Dict[str, Any]) -> Dict[str, Any]:
        """Validate runtime environment specification."""
        errors = []

        if not isinstance(runtime_env, dict):
            return {"valid": False, "errors": ["runtime_env must be a dictionary"]}

        # Validate working directory
        working_dir = runtime_env.get("working_dir")
        if working_dir is not None:
            if not isinstance(working_dir, str):
                errors.append("runtime_env.working_dir must be a string")

        # Validate pip packages
        pip = runtime_env.get("pip")
        if pip is not None:
            if isinstance(pip, list):
                for i, package in enumerate(pip):
                    if not isinstance(package, str):
                        errors.append(f"runtime_env.pip[{i}] must be a string")
            elif isinstance(pip, dict):
                # Allow pip configuration as dict
                pass
            else:
                errors.append("runtime_env.pip must be a list or dictionary")

        # Validate conda packages
        conda = runtime_env.get("conda")
        if conda is not None:
            if isinstance(conda, list):
                for i, package in enumerate(conda):
                    if not isinstance(package, str):
                        errors.append(f"runtime_env.conda[{i}] must be a string")
            elif isinstance(conda, (str, dict)):
                # Allow conda environment file or configuration as string/dict
                pass
            else:
                errors.append("runtime_env.conda must be a list, string, or dictionary")

        # Validate environment variables
        env_vars = runtime_env.get("env_vars")
        if env_vars is not None:
            if not isinstance(env_vars, dict):
                errors.append("runtime_env.env_vars must be a dictionary")
            else:
                for key, value in env_vars.items():
                    if not isinstance(key, str):
                        errors.append(f"runtime_env.env_vars key '{key}' must be a string")
                    if not isinstance(value, str):
                        errors.append(f"runtime_env.env_vars['{key}'] must be a string")

        return {"valid": len(errors) == 0, "errors": errors}

    def _format_runtime_env(self, runtime_env: Dict[str, Any]) -> str:
        """Format runtime environment as YAML string."""
        if not YAML_AVAILABLE:
            # Fallback to JSON if YAML not available
            return json.dumps(runtime_env)
        
        return yaml.dump(runtime_env, default_flow_style=False)

    def _build_default_cluster_spec(self) -> Dict[str, Any]:
        """Build default RayCluster specification for the job."""
        return {
            "rayVersion": "2.9.0",
            "enableInClusterService": True,
            "headGroupSpec": {
                "serviceType": "ClusterIP",
                "replicas": 1,
                "rayStartParams": {
                    "dashboard-host": "0.0.0.0",
                    "num-cpus": "2",
                    "block": "true"
                },
                "template": {
                    "spec": {
                        "containers": [{
                            "name": "ray-head",
                            "image": "rayproject/ray:2.9.0",
                            "ports": [
                                {"containerPort": 6379, "name": "gcs-server"},
                                {"containerPort": 8265, "name": "dashboard"},
                                {"containerPort": 10001, "name": "client"}
                            ],
                            "resources": {
                                "requests": {"cpu": "2", "memory": "4Gi"},
                                "limits": {"cpu": "2", "memory": "4Gi"}
                            }
                        }]
                    }
                }
            },
            "workerGroupSpecs": [{
                "groupName": "worker-group",
                "replicas": 2,
                "minReplicas": 0,
                "maxReplicas": 4,
                "rayStartParams": {
                    "num-cpus": "2",
                    "block": "true"
                },
                "template": {
                    "spec": {
                        "containers": [{
                            "name": "ray-worker",
                            "image": "rayproject/ray:2.9.0",
                            "resources": {
                                "requests": {"cpu": "2", "memory": "4Gi"},
                                "limits": {"cpu": "2", "memory": "4Gi"}
                            }
                        }]
                    }
                }
            }]
        } 