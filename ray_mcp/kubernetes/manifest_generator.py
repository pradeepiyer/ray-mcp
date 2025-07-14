"""Prompt-to-manifest generation for Ray clusters and jobs - replaces entire CRD system."""

import re
import tempfile
from typing import Any, Dict, Optional


class ManifestGenerator:
    """Generates Kubernetes manifests from natural language prompts.

    Replaces the entire CRD system (1,861 lines) with simple prompt-to-YAML generation.
    """

    @staticmethod
    def generate_ray_cluster_manifest(prompt: str, action: Dict[str, Any]) -> str:
        """Generate RayCluster manifest from prompt and parsed action."""
        # Extract parameters from action
        name = action.get("name", "ray-cluster")
        namespace = action.get("namespace", "default")
        workers = action.get("workers", 1)
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
        return manifest

    @staticmethod
    def generate_ray_job_manifest(prompt: str, action: Dict[str, Any]) -> str:
        """Generate RayJob manifest from prompt and parsed action."""
        # Extract parameters from action
        name = action.get("name", "ray-job")
        namespace = action.get("namespace", "default")
        script = action.get("script", "python main.py")
        runtime_env = action.get("runtime_env", {})

        # Handle runtime environment
        runtime_env_yaml = ""
        if runtime_env:
            if runtime_env.get("pip"):
                runtime_env_yaml = f"""
        runtimeEnvYAML: |
          pip:
            - {runtime_env["pip"][0]}"""
            elif runtime_env.get("working_dir"):
                runtime_env_yaml = f"""
        runtimeEnvYAML: |
          working_dir: "{runtime_env["working_dir"]}" """

        # Generate manifest YAML
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
        return manifest

    @staticmethod
    async def apply_manifest(
        manifest: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Apply Kubernetes manifest using kubectl."""
        import asyncio

        try:
            # Write manifest to temporary file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            ) as f:
                f.write(manifest)
                manifest_file = f.name

            # Apply using kubectl
            process = await asyncio.create_subprocess_exec(
                "kubectl",
                "apply",
                "-f",
                manifest_file,
                "-n",
                namespace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            # Clean up temp file
            import os

            os.unlink(manifest_file)

            if process.returncode == 0:
                return {
                    "status": "success",
                    "message": "Manifest applied successfully",
                    "output": stdout.decode().strip(),
                    "namespace": namespace,
                }
            else:
                return {
                    "status": "error",
                    "message": f"kubectl apply failed: {stderr.decode().strip()}",
                    "namespace": namespace,
                }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to apply manifest: {str(e)}",
                "namespace": namespace,
            }

    @staticmethod
    async def delete_resource(
        resource_type: str, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Delete Kubernetes resource using kubectl."""
        import asyncio

        try:
            # Delete using kubectl
            process = await asyncio.create_subprocess_exec(
                "kubectl",
                "delete",
                resource_type,
                name,
                "-n",
                namespace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return {
                    "status": "success",
                    "message": f"{resource_type} {name} deleted successfully",
                    "output": stdout.decode().strip(),
                    "namespace": namespace,
                }
            else:
                # Check if resource doesn't exist (not an error in this context)
                error_msg = stderr.decode().strip()
                if "not found" in error_msg.lower():
                    return {
                        "status": "success",
                        "message": f"{resource_type} {name} not found (already deleted)",
                        "namespace": namespace,
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"kubectl delete failed: {error_msg}",
                        "namespace": namespace,
                    }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to delete {resource_type}: {str(e)}",
                "namespace": namespace,
            }

    @staticmethod
    async def get_resource_status(
        resource_type: str, name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """Get Kubernetes resource status using kubectl."""
        import asyncio
        import json

        try:
            # Get resource info using kubectl
            process = await asyncio.create_subprocess_exec(
                "kubectl",
                "get",
                resource_type,
                name,
                "-n",
                namespace,
                "-o",
                "json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                resource_data = json.loads(stdout.decode())

                # Extract common status information
                status_info = {
                    "name": name,
                    "namespace": namespace,
                    "kind": resource_data.get("kind"),
                    "creation_timestamp": resource_data.get("metadata", {}).get(
                        "creationTimestamp"
                    ),
                    "labels": resource_data.get("metadata", {}).get("labels", {}),
                    "status": resource_data.get("status", {}),
                    "spec": resource_data.get("spec", {}),
                }

                return {
                    "status": "success",
                    "resource": status_info,
                    "raw_resource": resource_data,
                }
            else:
                error_msg = stderr.decode().strip()
                if "not found" in error_msg.lower():
                    return {
                        "status": "error",
                        "message": f"{resource_type} {name} not found",
                        "namespace": namespace,
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"kubectl get failed: {error_msg}",
                        "namespace": namespace,
                    }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to get {resource_type} status: {str(e)}",
                "namespace": namespace,
            }

    @staticmethod
    async def list_resources(
        resource_type: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """List Kubernetes resources using kubectl."""
        import asyncio
        import json

        try:
            # List resources using kubectl
            process = await asyncio.create_subprocess_exec(
                "kubectl",
                "get",
                resource_type,
                "-n",
                namespace,
                "-o",
                "json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                resources_data = json.loads(stdout.decode())
                items = resources_data.get("items", [])

                # Extract summary information for each resource
                resources = []
                for item in items:
                    resource_summary = {
                        "name": item.get("metadata", {}).get("name"),
                        "namespace": item.get("metadata", {}).get("namespace"),
                        "creation_timestamp": item.get("metadata", {}).get(
                            "creationTimestamp"
                        ),
                        "labels": item.get("metadata", {}).get("labels", {}),
                        "status": item.get("status", {}),
                    }
                    resources.append(resource_summary)

                return {
                    "status": "success",
                    "resources": resources,
                    "total_count": len(resources),
                    "namespace": namespace,
                }
            else:
                return {
                    "status": "error",
                    "message": f"kubectl get failed: {stderr.decode().strip()}",
                    "namespace": namespace,
                }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to list {resource_type}: {str(e)}",
                "namespace": namespace,
            }

    @staticmethod
    def extract_gpu_resources(prompt: str) -> Dict[str, str]:
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
