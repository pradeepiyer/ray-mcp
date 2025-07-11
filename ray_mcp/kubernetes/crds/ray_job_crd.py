"""Ray Job Custom Resource Definition management."""

from typing import Any, Dict, Optional
import uuid

from .base_crd_manager import BaseCRDManager


class RayJobCRDManager(BaseCRDManager):
    """Manager for RayJob Custom Resource Definitions."""

    def create_spec(
        self,
        entrypoint: str,
        runtime_env: Optional[Dict[str, Any]] = None,
        job_name: Optional[str] = None,
        namespace: str = "default",
        cluster_selector: Optional[str] = None,
        suspend: bool = False,
        ttl_seconds_after_finished: Optional[int] = 86400,  # 24 hours
        active_deadline_seconds: Optional[int] = None,
        backoff_limit: int = 0,
        shutdown_after_job_finishes: Optional[bool] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Create RayJob specification with validation."""

        # Generate job name if not provided
        if not job_name:
            job_name = f"ray-job-{uuid.uuid4().hex[:8]}"

        # Validate entrypoint
        if not entrypoint or not isinstance(entrypoint, str):
            return self._ResponseFormatter.format_error_response(
                "create ray job spec",
                Exception("entrypoint must be a non-empty string"),
            )

        # Validate runtime environment
        if runtime_env is not None:
            runtime_validation = self._validate_runtime_env(runtime_env)
            if not runtime_validation["valid"]:
                return self._ResponseFormatter.format_error_response(
                    "create ray job spec",
                    Exception(f"Invalid runtime_env: {runtime_validation['errors']}"),
                )

        # Intelligent shutdown_after_job_finishes behavior based on cluster usage
        if shutdown_after_job_finishes is None:
            if cluster_selector:
                # Using existing cluster - CRITICAL: don't shutdown the cluster after job finishes
                shutdown_after_job_finishes = False
                self._LoggingUtility.log_info(
                    "rayjob_cluster_preservation",
                    f"Using existing cluster '{cluster_selector}' - setting shutdownAfterJobFinishes=false to preserve cluster",
                )
            else:
                # Creating new ephemeral cluster - shutdown after job finishes to save resources
                shutdown_after_job_finishes = True
                self._LoggingUtility.log_info(
                    "rayjob_ephemeral_cluster",
                    f"Creating ephemeral cluster - setting shutdownAfterJobFinishes=true for cleanup",
                )

        # CRITICAL SAFETY CHECK: Ensure existing clusters are not accidentally torn down
        if cluster_selector and shutdown_after_job_finishes:
            self._LoggingUtility.log_warning(
                "rayjob_cluster_safety",
                f"WARNING: Job configured to use existing cluster '{cluster_selector}' but shutdownAfterJobFinishes=true. This could destroy the existing cluster!",
            )
            # Override for safety
            shutdown_after_job_finishes = False
            self._LoggingUtility.log_info(
                "rayjob_cluster_safety",
                "Safety override: Setting shutdownAfterJobFinishes=false to protect existing cluster",
            )

        # Handle TTL compatibility with shutdown setting
        if not shutdown_after_job_finishes and ttl_seconds_after_finished is not None:
            # If cluster doesn't shutdown after job finishes, we cannot have TTL
            ttl_seconds_after_finished = None
            self._LoggingUtility.log_info(
                "rayjob_ttl_disable",
                "TTL disabled because shutdownAfterJobFinishes=false (cluster preservation mode)",
            )

        # Build the RayJob specification
        ray_job_spec = {
            "apiVersion": "ray.io/v1",
            "kind": "RayJob",
            "metadata": self._build_base_metadata(job_name, namespace, "job", **kwargs),
            "spec": {
                "entrypoint": entrypoint,
                "runtimeEnvYAML": (
                    self._format_runtime_env(runtime_env) if runtime_env else ""
                ),
                "backoffLimit": backoff_limit,
                "suspend": suspend,
                "shutdownAfterJobFinishes": shutdown_after_job_finishes,
            },
        }

        # Add cluster configuration based on whether we're using existing or creating new cluster
        if cluster_selector:
            # Using existing cluster - add cluster selector
            ray_job_spec["spec"]["clusterSelector"] = cluster_selector
            self._LoggingUtility.log_info(
                "rayjob_existing_cluster",
                f"Job configured to use existing cluster: {cluster_selector}",
            )
        else:
            # Creating new cluster - add ray cluster spec
            ray_job_spec["spec"]["rayClusterSpec"] = self._build_default_cluster_spec()
            self._LoggingUtility.log_info(
                "rayjob_new_cluster", "Job configured to create new ephemeral cluster"
            )

        # Add TTL only if cluster shuts down after job finishes
        if shutdown_after_job_finishes and ttl_seconds_after_finished is not None:
            ray_job_spec["spec"]["ttlSecondsAfterFinished"] = ttl_seconds_after_finished
            self._LoggingUtility.log_info(
                "rayjob_ttl_enabled",
                f"TTL set to {ttl_seconds_after_finished} seconds for ephemeral cluster cleanup",
            )

        # Add active deadline if provided
        if active_deadline_seconds:
            ray_job_spec["spec"]["activeDeadlineSeconds"] = active_deadline_seconds

        return self._ResponseFormatter.format_success_response(
            job_spec=ray_job_spec, job_name=job_name
        )

    def validate_spec(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Validate RayJob specification."""
        required_fields = ["apiVersion", "kind", "metadata", "spec"]
        errors = self._validate_required_fields(
            spec, required_fields, "ray.io/v1", "RayJob"
        )

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
        shutdown_after_job_finishes = ray_spec.get("shutdownAfterJobFinishes", True)

        if ttl is not None:
            if error := self._validate_positive_integer(
                ttl, "spec.ttlSecondsAfterFinished", allow_zero=True
            ):
                errors.append(error)

            # Validate TTL compatibility with shutdown setting
            if not shutdown_after_job_finishes:
                errors.append(
                    "spec.ttlSecondsAfterFinished cannot be set when shutdownAfterJobFinishes is false"
                )

        # Validate shutdownAfterJobFinishes if present
        if "shutdownAfterJobFinishes" in ray_spec:
            if not isinstance(shutdown_after_job_finishes, bool):
                errors.append("spec.shutdownAfterJobFinishes must be a boolean")

        # Validate backoff limit if present
        backoff_limit = ray_spec.get("backoffLimit")
        if error := self._validate_positive_integer(
            backoff_limit, "spec.backoffLimit", allow_zero=True
        ):
            errors.append(error)

        # Validate active deadline if present
        deadline = ray_spec.get("activeDeadlineSeconds")
        if error := self._validate_positive_integer(
            deadline, "spec.activeDeadlineSeconds"
        ):
            errors.append(error)

        # Validate cluster selector if present
        selector = ray_spec.get("clusterSelector")
        if selector is not None:
            if not isinstance(selector, (str, dict)):
                errors.append(
                    "spec.clusterSelector must be a string (cluster name) or dictionary (label selector)"
                )
            elif isinstance(selector, str) and not selector.strip():
                errors.append("spec.clusterSelector string must not be empty")
            elif isinstance(selector, dict) and not selector:
                errors.append("spec.clusterSelector dictionary must not be empty")

        return self._ResponseFormatter.format_success_response(
            valid=len(errors) == 0, errors=errors
        )

    def _validate_runtime_env(self, runtime_env: Dict[str, Any]) -> Dict[str, Any]:
        """Validate runtime environment specification."""
        errors = []

        if not isinstance(runtime_env, dict):
            return {"valid": False, "errors": ["runtime_env must be a dictionary"]}

        # Validate working directory
        working_dir = runtime_env.get("working_dir")
        if error := self._validate_non_empty_string(
            working_dir, "runtime_env.working_dir"
        ):
            errors.append(error)

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
                        errors.append(
                            f"runtime_env.env_vars key '{key}' must be a string"
                        )
                    if not isinstance(value, str):
                        errors.append(f"runtime_env.env_vars['{key}'] must be a string")

        return {"valid": len(errors) == 0, "errors": errors}

    def _format_runtime_env(self, runtime_env: Dict[str, Any]) -> str:
        """Format runtime environment as YAML string."""
        try:
            import yaml

            return yaml.dump(runtime_env, default_flow_style=False)
        except ImportError:
            # Fallback to JSON if YAML not available
            import json

            return json.dumps(runtime_env)

    def _build_default_cluster_spec(self) -> Dict[str, Any]:
        """Build default RayCluster specification for the job."""
        return {
            "rayVersion": "2.47.0",
            "enableInClusterService": True,
            "headGroupSpec": {
                "serviceType": "ClusterIP",
                "replicas": 1,
                "rayStartParams": {
                    "dashboard-host": "0.0.0.0",
                    "num-cpus": "2",
                    "block": "true",
                },
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": "ray-head",
                                "image": "rayproject/ray:2.47.0",
                                "ports": [
                                    {"containerPort": 6379, "name": "gcs-server"},
                                    {"containerPort": 8265, "name": "dashboard"},
                                    {"containerPort": 10001, "name": "client"},
                                ],
                                "resources": {
                                    "requests": {"cpu": "2", "memory": "4Gi"},
                                    "limits": {"cpu": "2", "memory": "4Gi"},
                                },
                            }
                        ]
                    }
                },
            },
            "workerGroupSpecs": [
                {
                    "groupName": "worker-group",
                    "replicas": 2,
                    "minReplicas": 0,
                    "maxReplicas": 4,
                    "rayStartParams": {"num-cpus": "2", "block": "true"},
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "name": "ray-worker",
                                    "image": "rayproject/ray:2.47.0",
                                    "resources": {
                                        "requests": {"cpu": "2", "memory": "4Gi"},
                                        "limits": {"cpu": "2", "memory": "4Gi"},
                                    },
                                }
                            ]
                        }
                    },
                }
            ],
        }
