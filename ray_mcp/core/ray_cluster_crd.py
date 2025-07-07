"""RayCluster Custom Resource Definition management."""

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

from .interfaces import RayClusterCRD


class RayClusterCRDManager(RayClusterCRD):
    """Manages RayCluster Custom Resource Definition with schema validation and serialization."""

    def __init__(self):
        self._response_formatter = ResponseFormatter()

    @ResponseFormatter.handle_exceptions("create ray cluster spec")
    def create_spec(
        self, 
        head_node_spec: Dict[str, Any], 
        worker_node_specs: List[Dict[str, Any]], 
        cluster_name: Optional[str] = None,
        namespace: str = "default",
        ray_version: str = "2.9.0",
        enable_ingress: bool = False,
        suspend: bool = False,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Create RayCluster specification with validation."""
        
        # Generate cluster name if not provided
        if not cluster_name:
            cluster_name = f"ray-cluster-{uuid.uuid4().hex[:8]}"

        # Validate head node spec
        head_validation = self._validate_node_spec(head_node_spec, "head")
        if not head_validation["valid"]:
            return self._response_formatter.format_error_response(
                "create ray cluster spec",
                Exception(f"Invalid head node spec: {head_validation['errors']}")
            )

        # Validate worker node specs
        for i, worker_spec in enumerate(worker_node_specs):
            worker_validation = self._validate_node_spec(worker_spec, f"worker-{i}")
            if not worker_validation["valid"]:
                return self._response_formatter.format_error_response(
                    "create ray cluster spec",
                    Exception(f"Invalid worker node spec {i}: {worker_validation['errors']}")
                )

        # Build the RayCluster specification
        ray_cluster_spec = {
            "apiVersion": "ray.io/v1",
            "kind": "RayCluster",
            "metadata": {
                "name": cluster_name,
                "namespace": namespace,
                "labels": {
                    "app.kubernetes.io/name": "raycluster",
                    "app.kubernetes.io/component": "ray-cluster",
                    "app.kubernetes.io/managed-by": "ray-mcp"
                }
            },
            "spec": {
                "rayVersion": ray_version,
                "enableInClusterService": True,
                "headGroupSpec": self._build_head_group_spec(head_node_spec),
                "workerGroupSpecs": [
                    self._build_worker_group_spec(worker_spec, i) 
                    for i, worker_spec in enumerate(worker_node_specs)
                ]
            }
        }

        # Add optional fields
        if enable_ingress:
            ray_cluster_spec["spec"]["headServiceAnnotations"] = {
                "nginx.ingress.kubernetes.io/rewrite-target": "/$1"
            }

        if suspend:
            ray_cluster_spec["spec"]["suspend"] = True

        # Add any additional kwargs to metadata labels
        if kwargs:
            ray_cluster_spec["metadata"]["labels"].update({
                f"ray-mcp.{k}": str(v) for k, v in kwargs.items() 
                if isinstance(v, (str, int, bool))
            })

        return self._response_formatter.format_success_response(
            cluster_spec=ray_cluster_spec,
            cluster_name=cluster_name
        )

    @ResponseFormatter.handle_exceptions("validate ray cluster spec")
    def validate_spec(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Validate RayCluster specification."""
        errors = []
        
        # Check required top-level fields
        required_fields = ["apiVersion", "kind", "metadata", "spec"]
        for field in required_fields:
            if field not in spec:
                errors.append(f"Missing required field: {field}")

        if spec.get("apiVersion") != "ray.io/v1":
            errors.append(f"Invalid apiVersion: expected 'ray.io/v1', got '{spec.get('apiVersion')}'")

        if spec.get("kind") != "RayCluster":
            errors.append(f"Invalid kind: expected 'RayCluster', got '{spec.get('kind')}'")

        # Validate metadata
        metadata = spec.get("metadata", {})
        if not metadata.get("name"):
            errors.append("Missing metadata.name")

        # Validate spec
        ray_spec = spec.get("spec", {})
        if not ray_spec.get("rayVersion"):
            errors.append("Missing spec.rayVersion")

        if "headGroupSpec" not in ray_spec:
            errors.append("Missing spec.headGroupSpec")

        if "workerGroupSpecs" not in ray_spec:
            errors.append("Missing spec.workerGroupSpecs")

        # Validate head group spec
        head_spec = ray_spec.get("headGroupSpec", {})
        head_validation = self._validate_group_spec(head_spec, "head")
        errors.extend(head_validation.get("errors", []))

        # Validate worker group specs
        worker_specs = ray_spec.get("workerGroupSpecs", [])
        if not isinstance(worker_specs, list):
            errors.append("spec.workerGroupSpecs must be a list")
        else:
            for i, worker_spec in enumerate(worker_specs):
                worker_validation = self._validate_group_spec(worker_spec, f"worker-{i}")
                errors.extend(worker_validation.get("errors", []))

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

    def _build_head_group_spec(self, head_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Build head group specification."""
        group_spec = {
            "serviceType": head_spec.get("service_type", "ClusterIP"),
            "replicas": 1,  # Head node is always single replica
            "rayStartParams": {
                "dashboard-host": "0.0.0.0",
                "metrics-export-port": "8080",
                "num-cpus": str(head_spec.get("num_cpus", 2)),
                "block": "true"
            },
            "template": {
                "spec": {
                    "containers": [{
                        "name": "ray-head",
                        "image": head_spec.get("image", "rayproject/ray:2.9.0"),
                        "ports": [
                            {"containerPort": 6379, "name": "gcs-server"},
                            {"containerPort": 8265, "name": "dashboard"},
                            {"containerPort": 10001, "name": "client"},
                            {"containerPort": 8080, "name": "metrics"}
                        ],
                        "resources": self._build_resource_spec(head_spec),
                        "env": head_spec.get("env", [])
                    }]
                }
            }
        }

        # Add node selector if provided
        if "node_selector" in head_spec:
            group_spec["template"]["spec"]["nodeSelector"] = head_spec["node_selector"]

        # Add tolerations if provided
        if "tolerations" in head_spec:
            group_spec["template"]["spec"]["tolerations"] = head_spec["tolerations"]

        return group_spec

    def _build_worker_group_spec(self, worker_spec: Dict[str, Any], index: int) -> Dict[str, Any]:
        """Build worker group specification."""
        group_name = worker_spec.get("group_name", f"worker-group-{index}")
        
        group_spec = {
            "groupName": group_name,
            "replicas": worker_spec.get("replicas", 2),
            "minReplicas": worker_spec.get("min_replicas", 0),
            "maxReplicas": worker_spec.get("max_replicas", worker_spec.get("replicas", 2) * 2),
            "rayStartParams": {
                "num-cpus": str(worker_spec.get("num_cpus", 2)),
                "block": "true"
            },
            "template": {
                "spec": {
                    "containers": [{
                        "name": "ray-worker",
                        "image": worker_spec.get("image", "rayproject/ray:2.9.0"),
                        "resources": self._build_resource_spec(worker_spec),
                        "env": worker_spec.get("env", [])
                    }]
                }
            }
        }

        # Add GPU support if requested
        if worker_spec.get("num_gpus", 0) > 0:
            group_spec["rayStartParams"]["num-gpus"] = str(worker_spec["num_gpus"])

        # Add node selector if provided
        if "node_selector" in worker_spec:
            group_spec["template"]["spec"]["nodeSelector"] = worker_spec["node_selector"]

        # Add tolerations if provided
        if "tolerations" in worker_spec:
            group_spec["template"]["spec"]["tolerations"] = worker_spec["tolerations"]

        return group_spec

    def _build_resource_spec(self, node_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Build Kubernetes resource specification."""
        resources = {"requests": {}, "limits": {}}

        # CPU resources
        cpu_request = node_spec.get("cpu_request", node_spec.get("num_cpus", 2))
        cpu_limit = node_spec.get("cpu_limit", cpu_request)
        resources["requests"]["cpu"] = f"{cpu_request}"
        resources["limits"]["cpu"] = f"{cpu_limit}"

        # Memory resources
        memory_request = node_spec.get("memory_request", "4Gi")
        memory_limit = node_spec.get("memory_limit", memory_request)
        resources["requests"]["memory"] = memory_request
        resources["limits"]["memory"] = memory_limit

        # GPU resources
        if node_spec.get("num_gpus", 0) > 0:
            gpu_count = str(node_spec["num_gpus"])
            gpu_type = node_spec.get("gpu_type", "nvidia.com/gpu")
            resources["requests"][gpu_type] = gpu_count
            resources["limits"][gpu_type] = gpu_count

        return resources

    def _validate_node_spec(self, node_spec: Dict[str, Any], node_type: str) -> Dict[str, Any]:
        """Validate individual node specification."""
        errors = []

        # Check for required fields
        if not isinstance(node_spec, dict):
            return {"valid": False, "errors": [f"{node_type} spec must be a dictionary"]}

        # Validate CPU requirements
        num_cpus = node_spec.get("num_cpus")
        if num_cpus is not None:
            if not isinstance(num_cpus, (int, float)) or num_cpus <= 0:
                errors.append(f"{node_type}: num_cpus must be a positive number")

        # Validate GPU requirements
        num_gpus = node_spec.get("num_gpus")
        if num_gpus is not None:
            if not isinstance(num_gpus, int) or num_gpus < 0:
                errors.append(f"{node_type}: num_gpus must be a non-negative integer")

        # Validate replica count for workers
        if node_type.startswith("worker"):
            replicas = node_spec.get("replicas")
            if replicas is not None:
                if not isinstance(replicas, int) or replicas < 0:
                    errors.append(f"{node_type}: replicas must be a non-negative integer")

        # Validate image format
        image = node_spec.get("image")
        if image is not None:
            if not isinstance(image, str) or not image.strip():
                errors.append(f"{node_type}: image must be a non-empty string")

        return {"valid": len(errors) == 0, "errors": errors}

    def _validate_group_spec(self, group_spec: Dict[str, Any], group_type: str) -> Dict[str, Any]:
        """Validate group specification."""
        errors = []

        if not isinstance(group_spec, dict):
            return {"errors": [f"{group_type} group spec must be a dictionary"]}

        # Validate template
        if "template" not in group_spec:
            errors.append(f"{group_type}: missing template specification")
        else:
            template = group_spec["template"]
            if not isinstance(template, dict):
                errors.append(f"{group_type}: template must be a dictionary")
            elif "spec" not in template:
                errors.append(f"{group_type}: missing template.spec")

        return {"errors": errors} 