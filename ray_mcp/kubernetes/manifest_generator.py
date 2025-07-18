"""Prompt-to-manifest generation for Ray clusters and jobs using native Kubernetes API."""

import asyncio
import json
import re
from typing import Any, Optional

import yaml

from ..foundation.logging_utils import LoggingUtility

try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException

    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False


class ManifestGenerator:
    """Generates and applies Kubernetes manifests using native Kubernetes API."""

    def __init__(self):
        self._custom_objects_api = None
        self._core_v1_api = None
        self._apps_v1_api = None
        self._client_initialized = False

    def _ensure_kubernetes_client(self) -> None:
        """Initialize Kubernetes clients if not already done."""
        if not KUBERNETES_AVAILABLE:
            raise RuntimeError(
                "Kubernetes client not available. Please install kubernetes package."
            )

        if not self._client_initialized:
            try:
                # Try to load in-cluster config first, then kubeconfig
                try:
                    config.load_incluster_config()
                except config.ConfigException:
                    config.load_kube_config()

                self._custom_objects_api = client.CustomObjectsApi()
                self._core_v1_api = client.CoreV1Api()
                self._apps_v1_api = client.AppsV1Api()
                self._client_initialized = True
            except Exception as e:
                raise RuntimeError(f"Failed to initialize Kubernetes client: {str(e)}")

    @staticmethod
    def generate_ray_cluster_manifest(prompt: str, action: dict[str, Any]) -> str:
        """Generate RayCluster manifest from prompt and parsed action."""
        # Extract parameters from action
        name = action.get("name", "ray-cluster")
        namespace = action.get("namespace", "default")
        workers = action.get("workers") or 1  # Handle None workers
        head_resources = action.get("head_resources", {"cpu": "1", "memory": "2Gi"})
        worker_resources = action.get("worker_resources", {"cpu": "1", "memory": "2Gi"})

        # Generate manifest YAML
        manifest = f"""apiVersion: ray.io/v1
kind: RayCluster
metadata:
  name: {name}
  namespace: {namespace}
spec:
  rayVersion: '2.47.0'
  enableInTreeAutoscaling: true
  headGroupSpec:
    rayStartParams:
      dashboard-host: '0.0.0.0'
    template:
      spec:
        containers:
        - name: ray-head
          image: rayproject/ray:2.47.0
          resources:
            limits:
              cpu: {head_resources["cpu"]}
              memory: {head_resources["memory"]}
            requests:
              cpu: {head_resources["cpu"]}
              memory: {head_resources["memory"]}
          ports:
          - containerPort: 6379
            name: gcs-server
          - containerPort: 8265
            name: dashboard
          - containerPort: 10001
            name: client
  workerGroupSpecs:
  - replicas: {workers}
    minReplicas: 1
    maxReplicas: {workers * 2}
    groupName: small-group
    rayStartParams: {{}}
    template:
      spec:
        containers:
        - name: ray-worker
          image: rayproject/ray:2.47.0
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh","-c","ray stop"]
          resources:
            limits:
              cpu: {worker_resources["cpu"]}
              memory: {worker_resources["memory"]}
            requests:
              cpu: {worker_resources["cpu"]}
              memory: {worker_resources["memory"]}
---
apiVersion: v1
kind: Service
metadata:
  name: {name}-head-svc
  namespace: {namespace}
spec:
  selector:
    ray.io/cluster: {name}
    ray.io/node-type: head
  ports:
  - name: dashboard
    port: 8265
    targetPort: 8265
  - name: client
    port: 10001
    targetPort: 10001
  type: ClusterIP
"""
        # Log the generated manifest
        LoggingUtility.log_info(
            "kuberay_cluster_manifest_gen",
            f"Generated RayCluster manifest:\n{manifest}",
        )

        return manifest

    @staticmethod
    def generate_ray_job_manifest(prompt: str, action: dict[str, Any]) -> str:
        """Generate RayJob manifest from prompt and parsed action."""
        # Extract parameters from action
        name = action.get("name", "ray-job")
        namespace = action.get("namespace", "default")
        script = action.get("script") or action.get("source", "python main.py")
        runtime_env = action.get("runtime_env", {})

        # Handle GitHub URL in script - convert to proper git runtime_env + entrypoint
        if script and script.startswith("https://github.com/"):
            # Extract repo and script path from GitHub URL
            # Example: https://github.com/anyscale/rayturbo-benchmarks/blob/main/aggregations-filters/tpch-q1.py
            # -> repo: https://github.com/anyscale/rayturbo-benchmarks.git, script: aggregations-filters/tpch-q1.py
            if "/blob/" in script:
                parts = script.split("/blob/")
                if len(parts) == 2:
                    repo_url = parts[0] + ".git"
                    branch_and_path = parts[1].split("/", 1)
                    if len(branch_and_path) == 2:
                        branch = branch_and_path[0]
                        script_path = branch_and_path[1]

                        # Set up git runtime environment
                        if not runtime_env.get("git"):
                            runtime_env["git"] = {}
                        runtime_env["git"]["url"] = repo_url
                        runtime_env["git"]["branch"] = branch

                        # Set working directory to repository root for git cloned repos
                        runtime_env["working_dir"] = "."

                        # Set entrypoint to run the script from the downloaded repo
                        script = f"python {script_path}"

        # Handle runtime environment
        runtime_env_yaml = ""
        if runtime_env:
            runtime_parts = []

            # Handle pip dependencies
            if runtime_env.get("pip"):
                pip_packages = runtime_env["pip"]
                if isinstance(pip_packages, str):
                    # Single package as string
                    runtime_parts.append(f"pip:\n      - {pip_packages}")
                elif isinstance(pip_packages, list):
                    # Multiple packages as list
                    pip_yaml = "pip:"
                    for package in pip_packages:
                        pip_yaml += f"\n      - {package}"
                    runtime_parts.append(pip_yaml)

            # Handle working directory
            if runtime_env.get("working_dir"):
                runtime_parts.append(f'working_dir: "{runtime_env["working_dir"]}"')

            # Handle conda environment
            if runtime_env.get("conda"):
                conda_config = runtime_env["conda"]
                if isinstance(conda_config, str):
                    runtime_parts.append(f"conda: {conda_config}")
                elif isinstance(conda_config, dict):
                    conda_yaml = "conda:"
                    for key, value in conda_config.items():
                        conda_yaml += f"\n  {key}: {value}"
                    runtime_parts.append(conda_yaml)

            # Handle git repository
            if runtime_env.get("git"):
                git_config = runtime_env["git"]
                if isinstance(git_config, dict):
                    git_yaml = "git:"
                    for key, value in git_config.items():
                        if key == "url":
                            git_yaml += f'\n  {key}: "{value}"'
                        else:
                            git_yaml += f'\n  {key}: "{value}"'
                    runtime_parts.append(git_yaml)

            # Handle environment variables
            if runtime_env.get("env_vars"):
                env_vars = runtime_env["env_vars"]
                env_yaml = "env_vars:"
                for key, value in env_vars.items():
                    env_yaml += f"\n  {key}: {value}"
                runtime_parts.append(env_yaml)

            # Combine all parts
            if runtime_parts:
                # Properly indent each part's content
                indented_parts = []
                for part in runtime_parts:
                    # Replace internal newlines with properly indented newlines
                    indented_part = part.replace("\n", "\n    ")
                    indented_parts.append(indented_part)
                runtime_content = "\n    ".join(indented_parts)
                runtime_env_yaml = f"""
  runtimeEnvYAML: |
    {runtime_content}"""

        # Generate manifest YAML with proper separation
        manifest = f"""apiVersion: ray.io/v1
kind: RayJob
metadata:
  name: {name}
  namespace: {namespace}
spec:
  entrypoint: {script}{runtime_env_yaml}
  rayClusterSpec:
    rayVersion: '2.47.0'
    enableInTreeAutoscaling: true
    headGroupSpec:
      rayStartParams:
        dashboard-host: '0.0.0.0'
      template:
        spec:
          containers:
          - name: ray-head
            image: rayproject/ray:2.47.0
            resources:
              limits:
                cpu: "1"
                memory: "2Gi"
              requests:
                cpu: "1"
                memory: "2Gi"
            ports:
            - containerPort: 6379
              name: gcs-server
            - containerPort: 8265
              name: dashboard
            - containerPort: 10001
              name: client
    workerGroupSpecs:
    - replicas: 1
      minReplicas: 1
      maxReplicas: 3
      groupName: small-group
      rayStartParams: {{}}
      template:
        spec:
          containers:
          - name: ray-worker
            image: rayproject/ray:2.47.0
            lifecycle:
              preStop:
                exec:
                  command: ["/bin/sh","-c","ray stop"]
            resources:
              limits:
                cpu: "1"
                memory: "2Gi"
              requests:
                cpu: "1"
                memory: "2Gi"
  shutdownAfterJobFinishes: true
  ttlSecondsAfterFinished: 300
"""
        # Log the generated manifest
        LoggingUtility.log_info(
            "kuberay_job_manifest_gen", f"Generated RayJob manifest:\n{manifest}"
        )

        return manifest

    async def apply_manifest(
        self, manifest: str, namespace: str = "default"
    ) -> dict[str, Any]:
        """Apply Kubernetes manifest using native Kubernetes API."""
        try:
            self._ensure_kubernetes_client()

            # Parse YAML manifest into documents
            documents = list(yaml.safe_load_all(manifest))
            applied_resources = []

            for doc in documents:
                if not doc or not isinstance(doc, dict):
                    continue

                result = await self._apply_single_resource(doc, namespace)
                applied_resources.append(result)

            # Check if any resources failed
            failed_resources = [
                r for r in applied_resources if r.get("status") == "error"
            ]

            if failed_resources:
                return {
                    "status": "error",
                    "message": f"Failed to apply {len(failed_resources)} of {len(applied_resources)} resources",
                    "applied_resources": applied_resources,
                    "failed_resources": failed_resources,
                    "namespace": namespace,
                }
            else:
                return {
                    "status": "success",
                    "message": "Manifest applied successfully",
                    "applied_resources": applied_resources,
                    "namespace": namespace,
                }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to apply manifest: {str(e)}",
                "namespace": namespace,
            }

    async def _apply_single_resource(
        self, resource: dict[str, Any], namespace: str
    ) -> dict[str, Any]:
        """Apply a single Kubernetes resource."""
        api_version = resource.get("apiVersion", "")
        kind = resource.get("kind", "")
        metadata = resource.get("metadata", {})
        name = metadata.get("name")

        # Ensure namespace is set in metadata
        if "namespace" not in metadata and namespace != "default":
            metadata["namespace"] = namespace
            resource["metadata"] = metadata

        try:
            if api_version == "ray.io/v1":
                # Handle Ray CRDs
                group = "ray.io"
                version = "v1"

                if kind == "RayCluster":
                    plural = "rayclusters"
                elif kind == "RayJob":
                    plural = "rayjobs"
                else:
                    raise ValueError(f"Unsupported Ray CRD kind: {kind}")

                # Log the final CRD before applying
                LoggingUtility.log_info(
                    f"kuberay_crd_apply_{kind.lower()}",
                    f"Applying {kind} CRD '{name}' in namespace '{namespace}'",
                )
                LoggingUtility.log_info(
                    f"kuberay_crd_apply_{kind.lower()}",
                    f"Complete {kind} CRD manifest:\n{yaml.dump(resource, default_flow_style=False)}",
                )

                # Try to get existing resource first
                try:
                    await asyncio.to_thread(
                        self._custom_objects_api.get_namespaced_custom_object,
                        group=group,
                        version=version,
                        namespace=namespace,
                        plural=plural,
                        name=name,
                    )
                    # Resource exists, update it
                    LoggingUtility.log_info(
                        f"kuberay_crd_apply_{kind.lower()}",
                        f"Updating existing {kind} '{name}' in namespace '{namespace}'",
                    )
                    result = await asyncio.to_thread(
                        self._custom_objects_api.patch_namespaced_custom_object,
                        group=group,
                        version=version,
                        namespace=namespace,
                        plural=plural,
                        name=name,
                        body=resource,
                    )
                    action = "updated"
                except ApiException as e:
                    if hasattr(e, "status") and e.status == 404:
                        # Resource doesn't exist, create it
                        LoggingUtility.log_info(
                            f"kuberay_crd_apply_{kind.lower()}",
                            f"Creating new {kind} '{name}' in namespace '{namespace}'",
                        )
                        result = await asyncio.to_thread(
                            self._custom_objects_api.create_namespaced_custom_object,
                            group=group,
                            version=version,
                            namespace=namespace,
                            plural=plural,
                            body=resource,
                        )
                        action = "created"
                    else:
                        raise

                # Log the result of the CRD application
                LoggingUtility.log_info(
                    f"kuberay_crd_result_{kind.lower()}",
                    f"Successfully {action} {kind} '{name}' in namespace '{namespace}'",
                )
                LoggingUtility.log_info(
                    f"kuberay_crd_result_{kind.lower()}",
                    f"Applied {kind} result: {json.dumps(result, default=str, indent=2)}",
                )

            elif api_version == "v1" and kind == "Service":
                # Handle core v1 Service
                try:
                    await asyncio.to_thread(
                        self._core_v1_api.read_namespaced_service,
                        name=name,
                        namespace=namespace,
                    )
                    # Service exists, update it
                    result = await asyncio.to_thread(
                        self._core_v1_api.patch_namespaced_service,
                        name=name,
                        namespace=namespace,
                        body=resource,
                    )
                    action = "updated"
                except ApiException as e:
                    if hasattr(e, "status") and e.status == 404:
                        # Service doesn't exist, create it
                        result = await asyncio.to_thread(
                            self._core_v1_api.create_namespaced_service,
                            namespace=namespace,
                            body=resource,
                        )
                        action = "created"
                    else:
                        raise
            else:
                raise ValueError(f"Unsupported resource type: {api_version}/{kind}")

            return {
                "kind": kind,
                "name": name,
                "namespace": namespace,
                "action": action,
                "status": "success",
            }

        except Exception as e:
            return {
                "kind": kind,
                "name": name,
                "namespace": namespace,
                "action": "failed",
                "status": "error",
                "error": str(e),
            }

    async def delete_resource(
        self, resource_type: str, name: str, namespace: str = "default"
    ) -> dict[str, Any]:
        """Delete Kubernetes resource using native Kubernetes API."""
        try:
            self._ensure_kubernetes_client()

            if resource_type.lower() == "raycluster":
                await asyncio.to_thread(
                    self._custom_objects_api.delete_namespaced_custom_object,
                    group="ray.io",
                    version="v1",
                    namespace=namespace,
                    plural="rayclusters",
                    name=name,
                )
            elif resource_type.lower() == "rayjob":
                await asyncio.to_thread(
                    self._custom_objects_api.delete_namespaced_custom_object,
                    group="ray.io",
                    version="v1",
                    namespace=namespace,
                    plural="rayjobs",
                    name=name,
                )
            elif resource_type.lower() == "service":
                await asyncio.to_thread(
                    self._core_v1_api.delete_namespaced_service,
                    name=name,
                    namespace=namespace,
                )
            else:
                raise ValueError(f"Unsupported resource type: {resource_type}")

            return {
                "status": "success",
                "message": f"{resource_type} {name} deleted successfully",
                "namespace": namespace,
            }

        except ApiException as e:
            if hasattr(e, "status") and e.status == 404:
                return {
                    "status": "success",
                    "message": f"{resource_type} {name} not found (already deleted)",
                    "namespace": namespace,
                }
            else:
                return {
                    "status": "error",
                    "message": f"Failed to delete {resource_type}: {str(e)}",
                    "namespace": namespace,
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to delete {resource_type}: {str(e)}",
                "namespace": namespace,
            }

    async def get_resource_status(
        self, resource_type: str, name: str, namespace: str = "default"
    ) -> dict[str, Any]:
        """Get Kubernetes resource status using native Kubernetes API."""
        try:
            self._ensure_kubernetes_client()

            if resource_type.lower() == "raycluster":
                resource_data = await asyncio.to_thread(
                    self._custom_objects_api.get_namespaced_custom_object,
                    group="ray.io",
                    version="v1",
                    namespace=namespace,
                    plural="rayclusters",
                    name=name,
                )
            elif resource_type.lower() == "rayjob":
                resource_data = await asyncio.to_thread(
                    self._custom_objects_api.get_namespaced_custom_object,
                    group="ray.io",
                    version="v1",
                    namespace=namespace,
                    plural="rayjobs",
                    name=name,
                )
            elif resource_type.lower() == "service":
                service = await asyncio.to_thread(
                    self._core_v1_api.read_namespaced_service,
                    name=name,
                    namespace=namespace,
                )
                # Convert K8s object to dict for consistency
                resource_data = client.ApiClient().sanitize_for_serialization(service)
            else:
                raise ValueError(f"Unsupported resource type: {resource_type}")

            # Extract common status information
            metadata = (
                resource_data.get("metadata", {})
                if isinstance(resource_data, dict)
                else {}
            )
            status_info = {
                "name": name,
                "namespace": namespace,
                "kind": (
                    resource_data.get("kind")
                    if isinstance(resource_data, dict)
                    else None
                ),
                "creation_timestamp": (
                    metadata.get("creationTimestamp")
                    if isinstance(metadata, dict)
                    else None
                ),
                "labels": (
                    metadata.get("labels", {}) if isinstance(metadata, dict) else {}
                ),
                "status": (
                    resource_data.get("status", {})
                    if isinstance(resource_data, dict)
                    else {}
                ),
                "spec": (
                    resource_data.get("spec", {})
                    if isinstance(resource_data, dict)
                    else {}
                ),
            }

            return {
                "status": "success",
                "resource": status_info,
                "raw_resource": resource_data,
            }

        except ApiException as e:
            if hasattr(e, "status") and e.status == 404:
                return {
                    "status": "error",
                    "message": f"{resource_type} {name} not found",
                    "namespace": namespace,
                }
            else:
                return {
                    "status": "error",
                    "message": f"Failed to get {resource_type}: {str(e)}",
                    "namespace": namespace,
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to get {resource_type} status: {str(e)}",
                "namespace": namespace,
            }

    async def list_resources(
        self, resource_type: str, namespace: str = "default"
    ) -> dict[str, Any]:
        """List Kubernetes resources using native Kubernetes API."""
        try:
            self._ensure_kubernetes_client()

            if resource_type.lower() == "raycluster":
                resources_data = await asyncio.to_thread(
                    self._custom_objects_api.list_namespaced_custom_object,
                    group="ray.io",
                    version="v1",
                    namespace=namespace,
                    plural="rayclusters",
                )
            elif resource_type.lower() == "rayjob":
                resources_data = await asyncio.to_thread(
                    self._custom_objects_api.list_namespaced_custom_object,
                    group="ray.io",
                    version="v1",
                    namespace=namespace,
                    plural="rayjobs",
                )
            elif resource_type.lower() == "service":
                service_list = await asyncio.to_thread(
                    self._core_v1_api.list_namespaced_service, namespace=namespace
                )
                # Convert K8s object to dict for consistency
                resources_data = client.ApiClient().sanitize_for_serialization(
                    service_list
                )
            else:
                raise ValueError(f"Unsupported resource type: {resource_type}")

            items = (
                resources_data.get("items", [])
                if isinstance(resources_data, dict)
                else []
            )

            # Extract summary information for each resource
            resources = []
            for item in items:
                if isinstance(item, dict):
                    metadata = (
                        item.get("metadata", {})
                        if isinstance(item.get("metadata"), dict)
                        else {}
                    )
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
                        "labels": (
                            metadata.get("labels", {})
                            if isinstance(metadata, dict)
                            else {}
                        ),
                        "status": (
                            item.get("status", {})
                            if isinstance(item.get("status"), dict)
                            else {}
                        ),
                    }
                    resources.append(resource_summary)

            return {
                "status": "success",
                "resources": resources,
                "total_count": len(resources),
                "namespace": namespace,
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to list {resource_type}: {str(e)}",
                "namespace": namespace,
            }

    @staticmethod
    def extract_gpu_resources(prompt: str) -> dict[str, str]:
        """Extract GPU resource requirements from prompt."""
        resources = {}

        # Look for GPU specifications
        gpu_match = re.search(r"(\d+)\s*(?:gpu|nvidia)", prompt, re.IGNORECASE)
        if gpu_match:
            resources["nvidia.com/gpu"] = gpu_match.group(1)

        return resources

    @staticmethod
    def detect_service_type(prompt: str) -> str:
        """Detect desired service type from prompt."""
        prompt_lower = prompt.lower()

        if "loadbalancer" in prompt_lower or "external" in prompt_lower:
            return "LoadBalancer"
        elif "nodeport" in prompt_lower:
            return "NodePort"
        else:
            return "ClusterIP"
