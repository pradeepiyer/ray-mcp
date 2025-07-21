"""Ray service management for Ray MCP via KubeRay."""

import asyncio
from typing import Any, Optional

from ..core_utils import (
    LoggingUtility,
    error_response,
    handle_error,
    is_kubernetes_ready,
    success_response,
)
from .manifest_generator import ManifestGenerator


class ServiceManager:
    """Ray service management using KubeRay."""

    def __init__(self):
        self.logger = LoggingUtility()

        self._manifest_generator = ManifestGenerator()

    async def execute_request(self, action: dict[str, Any]) -> dict[str, Any]:
        """Execute KubeRay service operations using parsed action data.

        Args:
            action: Parsed action dict containing operation details
        """
        try:
            if action.get("type") != "service":
                raise ValueError(
                    f"Expected service action but got: {action.get('type')}"
                )
            operation = action["operation"]

            if operation == "create":
                return await self._create_ray_service_from_action(action)
            elif operation == "list":
                namespace = action.get("namespace", "default")
                return await self._list_ray_services(namespace)
            elif operation == "get":
                name = action.get("name")
                namespace = action.get("namespace", "default")
                if not name:
                    return error_response("service name required")
                return await self._get_ray_service(name, namespace)
            elif operation == "delete":
                name = action.get("name")
                namespace = action.get("namespace", "default")
                if not name:
                    return error_response("service name required")
                return await self._delete_ray_service(name, namespace)
            elif operation == "logs":
                name = action.get("name")
                namespace = action.get("namespace", "default")
                if not name:
                    return error_response("service name required")
                return await self._get_ray_service_logs(name, namespace)
            else:
                return error_response(f"Unknown operation: {operation}")

        except ValueError as e:
            return error_response(f"Could not parse request: {str(e)}")
        except Exception as e:
            return handle_error(self.logger, "execute_request", e)

    # =================================================================
    # INTERNAL IMPLEMENTATION: All methods are now private
    # =================================================================

    def _set_kubernetes_config(self, kubernetes_config) -> None:
        """Set the Kubernetes configuration for API operations.

        Note: With manifest generation approach, kubectl uses the current kubeconfig context,
        so explicit configuration setting is not needed.
        """
        try:
            LoggingUtility.log_info(
                "kuberay_service_set_k8s_config",
                f"Kubernetes config provided: {kubernetes_config is not None} - using kubectl with current context",
            )
            LoggingUtility.log_info(
                "kuberay_service_set_k8s_config",
                "Using kubectl with current kubeconfig context",
            )
        except Exception as e:
            LoggingUtility.log_error(
                "kuberay_service_set_k8s_config",
                Exception(f"Failed to configure kubectl context: {str(e)}"),
            )

    async def _create_ray_service_from_action(
        self, action: dict[str, Any]
    ) -> dict[str, Any]:
        """Create Ray service from parsed prompt action using manifest generation."""
        try:
            namespace = action.get("namespace", "default")

            # Generate manifest from action
            manifest = self._manifest_generator.generate_ray_service_manifest(action)

            # Apply manifest
            result = await self._manifest_generator.apply_manifest(manifest, namespace)

            if result.get("status") == "success":
                service_name = action.get("name", "ray-service")

                return success_response(
                    service_name=service_name,
                    namespace=namespace,
                    service_status="creating",
                    entrypoint=action.get("script", "python serve.py"),
                    runtime_env=action.get("runtime_env"),
                    message=f"RayService '{service_name}' creation initiated",
                    manifest_applied=True,
                )
            else:
                return error_response(result.get("message", "Unknown error"))

        except Exception as e:
            return handle_error(self.logger, "create ray service from prompt", e)

    async def _create_ray_service(
        self, service_spec: dict[str, Any], namespace: str = "default"
    ) -> dict[str, Any]:
        """Create a Ray service using KubeRay CRD."""
        try:
            return await self._create_ray_service_operation(service_spec, namespace)
        except Exception as e:
            return handle_error(self.logger, "create ray service", e)

    async def _create_ray_service_operation(
        self, service_spec: dict[str, Any], namespace: str = "default"
    ) -> dict[str, Any]:
        """Execute Ray service creation operation using manifest generation."""
        # Use ManagedComponent validation method instead of ResourceManager's
        self._ensure_kuberay_ready()

        # Validate service specification
        if not service_spec:
            raise ValueError("Service specification is required")

        entrypoint = service_spec.get("entrypoint")
        if not entrypoint:
            raise ValueError("entrypoint is required in service specification")

        service_name = service_spec.get("service_name", "ray-service")

        # Convert service_spec to action format for manifest generation
        action = {
            "name": service_name,
            "namespace": namespace,
            "script": entrypoint,
            "runtime_env": service_spec.get("runtime_env"),
        }

        # Generate and apply manifest
        manifest = self._manifest_generator.generate_ray_service_manifest(action)

        apply_result = await self._manifest_generator.apply_manifest(
            manifest, namespace
        )

        if apply_result.get("status") != "success":
            raise RuntimeError(
                f"Failed to create Ray service: {apply_result.get('message')}"
            )

        return {
            "service_name": service_name,
            "namespace": namespace,
            "entrypoint": entrypoint,
            "runtime_env": service_spec.get("runtime_env"),
            "service_status": "creating",
            "manifest_applied": True,
            **apply_result,
        }

    async def _get_ray_service(
        self, name: str, namespace: str = "default"
    ) -> dict[str, Any]:
        """Get Ray service status."""
        # Use ManagedComponent validation method instead of ResourceManager's
        self._ensure_kuberay_ready()

        result = await self._manifest_generator.get_resource_status(
            "rayservice", name, namespace
        )

        if result.get("status") == "success":
            resource = result.get("resource", {})
            status = resource.get("status", {})

            # Extract detailed service status
            service_status_value = status.get("serviceStatus", "Unknown")
            service_status = {
                "name": name,
                "namespace": namespace,
                "service_status": service_status_value,
                "ray_cluster_name": status.get("rayClusterName"),
                "service_deployment_status": status.get("deploymentStatus", "Unknown"),
                "dashboard_url": status.get("dashboardURL"),
                "serve_endpoint_url": status.get("serveEndpointURL"),
                "start_time": status.get("startTime"),
                "message": status.get("message"),
                "creation_timestamp": resource.get("metadata", {}).get(
                    "creationTimestamp"
                ),
            }

            # Add status flags for compatibility with tests
            running = service_status_value in ["Running", "RUNNING"]
            complete = service_status_value in [
                "Succeeded",
                "SUCCEEDED",
                "Failed",
                "FAILED",
            ]

            return success_response(
                service=service_status,
                raw_resource=resource,
                running=running,
                complete=complete,
            )
        else:
            return result

    async def _list_ray_services(self, namespace: str = "default") -> dict[str, Any]:
        """List Ray services."""
        # Use ManagedComponent validation method instead of ResourceManager's
        self._ensure_kuberay_ready()

        result = await self._manifest_generator.list_resources("rayservice", namespace)

        if result.get("status") == "success":
            services = []
            for resource_summary in result.get("resources", []):
                service_info = {
                    "name": resource_summary.get("name"),
                    "namespace": resource_summary.get("namespace"),
                    "service_status": resource_summary.get("status", {}).get(
                        "serviceStatus", "Unknown"
                    ),
                    "creation_timestamp": resource_summary.get("creation_timestamp"),
                    "labels": resource_summary.get("labels", {}),
                }
                services.append(service_info)

            return success_response(
                services=services, total_count=len(services), namespace=namespace
            )
        else:
            return result

    async def _delete_ray_service(
        self, name: str, namespace: str = "default"
    ) -> dict[str, Any]:
        """Delete Ray service."""
        # Use ManagedComponent validation method instead of ResourceManager's
        self._ensure_kuberay_ready()

        result = await self._manifest_generator.delete_resource(
            "rayservice", name, namespace
        )

        if result.get("status") == "success":
            return success_response(
                service_name=name,
                namespace=namespace,
                deleted=True,
                deletion_timestamp=result.get("deletion_timestamp"),
                message=f"RayService '{name}' deletion initiated",
            )
        else:
            return result

    async def _get_ray_service_logs(
        self, name: str, namespace: str = "default"
    ) -> dict[str, Any]:
        """Get Ray service logs."""
        # Use ManagedComponent validation method instead of ResourceManager's
        self._ensure_kuberay_ready()

        # First get the service to understand its current state
        service_result = await self._get_ray_service(name, namespace)
        if service_result.get("status") != "success":
            return service_result

        service_data = service_result.get("service", {})

        # Try to get cluster name from service status for log retrieval
        # This maintains compatibility with existing tests
        ray_cluster_name = None
        if service_result.get("raw_resource"):
            status = service_result["raw_resource"].get("status", {})
            ray_cluster_name = status.get("rayClusterName")

        if not ray_cluster_name:
            return error_response(f"No Ray cluster associated with service '{name}'")

        # Try to get logs using Kubernetes client for compatibility with tests
        try:
            from kubernetes import client

            v1 = client.CoreV1Api()

            # Try to get service-specific pod logs
            pods = await asyncio.to_thread(
                v1.list_namespaced_pod,
                namespace=namespace,
                label_selector=f"ray.io/cluster={ray_cluster_name},ray.io/serve=yes",
            )

            logs = []
            for pod in pods.items:
                try:
                    pod_logs = await asyncio.to_thread(
                        v1.read_namespaced_pod_log,
                        name=pod.metadata.name,
                        namespace=namespace,
                        tail_lines=1000,
                        timestamps=True,
                    )
                    logs.append(f"=== Pod {pod.metadata.name} ===\n{pod_logs}")
                except Exception:
                    continue

            pod_logs_result = {"logs": "\n".join(logs), "status": "success"}

            # Check if we got service-specific pods or need to fall back
            if len(logs) > 0:
                # Found service-specific pods
                return success_response(
                    service_name=name,
                    namespace=namespace,
                    ray_cluster_name=ray_cluster_name,
                    service_status=service_data.get("service_status"),
                    logs=pod_logs_result.get("logs", "No logs available"),
                    log_source="serve_pods",
                    pod_count=len(logs),
                    message=f"Retrieved logs for service '{name}' from cluster '{ray_cluster_name}'",
                )
            else:
                # Fallback to head node logs
                head_pods = await asyncio.to_thread(
                    v1.list_namespaced_pod,
                    namespace=namespace,
                    label_selector=f"ray.io/cluster={ray_cluster_name},ray.io/node-type=head",
                )

                head_logs = []
                for pod in head_pods.items:
                    try:
                        pod_logs = await asyncio.to_thread(
                            v1.read_namespaced_pod_log,
                            name=pod.metadata.name,
                            namespace=namespace,
                            tail_lines=1000,
                            timestamps=True,
                        )
                        head_logs.append(
                            f"=== Head Pod {pod.metadata.name} ===\n{pod_logs}"
                        )
                    except Exception:
                        continue

                return success_response(
                    service_name=name,
                    namespace=namespace,
                    ray_cluster_name=ray_cluster_name,
                    service_status=service_data.get("service_status"),
                    logs="\n".join(head_logs) if head_logs else "No logs available",
                    log_source="head_node_filtered",
                    pod_count=len(head_logs),
                    message=f"Retrieved logs for service '{name}' from cluster '{ray_cluster_name}' head node",
                )

        except Exception as e:
            return handle_error(self.logger, f"kubernetes logs for service {name}", e)

    def _ensure_kuberay_ready(self) -> None:
        """Ensure KubeRay operator is available and ready."""
        # Try to connect to kubernetes
        if not is_kubernetes_ready():
            raise RuntimeError(
                "Kubernetes is not available or configured. Please check kubeconfig."
            )

        # For now, just check if we can connect to K8s
        # Future enhancement: check if KubeRay operator is actually running
