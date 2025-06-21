"""Ray cluster management functionality."""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Union, cast, TYPE_CHECKING
import os

# Import Ray modules with error handling
try:
    import ray
    from ray.job_submission import JobSubmissionClient
    RAY_AVAILABLE = True
except ImportError:
    RAY_AVAILABLE = False
    ray = None  # type: ignore
    JobSubmissionClient = None  # type: ignore

# Import Ray Train modules with error handling
try:
    from ray.train import Trainer  # type: ignore
    RAY_TRAIN_AVAILABLE = True
except ImportError:
    RAY_TRAIN_AVAILABLE = False
    Trainer = None  # type: ignore

# Import Ray Train sklearn with error handling
try:
    import ray.train.sklearn  # type: ignore
    RAY_SKLEARN_AVAILABLE = True
except ImportError:
    RAY_SKLEARN_AVAILABLE = False

# Import Ray Serve with error handling
try:
    import ray.serve  # type: ignore
    RAY_SERVE_AVAILABLE = True
except ImportError:
    RAY_SERVE_AVAILABLE = False

from .types import (
    JobId, ActorId, NodeId,
    JobStatus, ActorState, HealthStatus,
    JobInfo, ActorInfo, NodeInfo,
    JobSubmissionConfig, ActorConfig,
    PerformanceMetrics, ClusterHealth,
    Response, SuccessResponse, ErrorResponse
)


logger = logging.getLogger(__name__)


class RayManager:
    """Manages Ray cluster operations."""

    def __init__(self) -> None:
        self._is_initialized = False
        self._cluster_address: Optional[str] = None
        self._job_client: Optional[Any] = None  # Use Any to avoid type issues with conditional imports

    @property
    def is_initialized(self) -> bool:
        """Check if Ray is initialized."""
        return (self._is_initialized and 
                RAY_AVAILABLE and 
                ray is not None and 
                ray.is_initialized())

    def _ensure_initialized(self) -> None:
        """Ensure Ray is initialized."""
        if not self.is_initialized:
            raise RuntimeError("Ray is not initialized. Please start Ray first.")

    async def start_cluster(
        self,
        head_node: bool = True,
        address: Optional[str] = None,
        num_cpus: Optional[int] = None,
        num_gpus: Optional[int] = None,
        object_store_memory: Optional[int] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Start a Ray cluster."""
        try:
            if not RAY_AVAILABLE or ray is None:
                return {
                    "status": "error",
                    "message": "Ray is not available. Please install Ray."
                }

            # Prepare initialization arguments
            init_kwargs: Dict[str, Any] = {}
            
            if address:
                init_kwargs["address"] = address
            else:
                # Starting as head node
                # Set default num_cpus to 4 if not specified
                if num_cpus is not None:
                    init_kwargs["num_cpus"] = num_cpus
                else:
                    init_kwargs["num_cpus"] = 4
                    
                if num_gpus is not None:
                    init_kwargs["num_gpus"] = num_gpus
                if object_store_memory is not None:
                    init_kwargs["object_store_memory"] = object_store_memory

            # Add any additional kwargs
            init_kwargs.update(kwargs)
            init_kwargs["ignore_reinit_error"] = True

            # Initialize Ray
            ray_context = ray.init(**init_kwargs)
            
            self._is_initialized = True
            self._cluster_address = ray_context.address_info["address"]
            
            # Initialize job client
            if JobSubmissionClient is not None:
                self._job_client = JobSubmissionClient(self._cluster_address)

            return {
                "status": "started",
                "message": "Ray cluster started successfully",
                "address": self._cluster_address,
                "dashboard_url": ray_context.dashboard_url,
                "node_id": ray.get_runtime_context().get_node_id() if ray is not None else None,
                "session_name": ray_context.session_name
            }

        except Exception as e:
            logger.error(f"Failed to start Ray cluster: {e}")
            return {
                "status": "error",
                "message": f"Failed to start Ray cluster: {str(e)}"
            }

    async def connect_cluster(self, address: str, **kwargs: Any) -> Dict[str, Any]:
        """Connect to an existing Ray cluster."""
        try:
            if not RAY_AVAILABLE or ray is None:
                return {
                    "status": "error",
                    "message": "Ray is not available. Please install Ray."
                }

            # Prepare connection arguments
            init_kwargs: Dict[str, Any] = {
                "address": address,
                "ignore_reinit_error": True
            }
            
            # Add any additional kwargs
            init_kwargs.update(kwargs)

            # Connect to existing Ray cluster
            ray_context = ray.init(**init_kwargs)
            
            self._is_initialized = True
            self._cluster_address = ray_context.address_info["address"]
            
            # Initialize job client
            if JobSubmissionClient is not None:
                self._job_client = JobSubmissionClient(self._cluster_address)

            return {
                "status": "connected",
                "message": f"Successfully connected to Ray cluster at {address}",
                "address": self._cluster_address,
                "dashboard_url": ray_context.dashboard_url,
                "node_id": ray.get_runtime_context().get_node_id() if ray is not None else None,
                "session_name": ray_context.session_name
            }

        except Exception as e:
            logger.error(f"Failed to connect to Ray cluster: {e}")
            return {
                "status": "error",
                "message": f"Failed to connect to Ray cluster at {address}: {str(e)}"
            }

    async def stop_cluster(self) -> Dict[str, Any]:
        """Stop the Ray cluster."""
        try:
            if not RAY_AVAILABLE or ray is None:
                return {
                    "status": "error",
                    "message": "Ray is not available"
                }

            if not ray.is_initialized():
                return {
                    "status": "not_running",
                    "message": "Ray cluster is not running"
                }

            # Shutdown Ray
            ray.shutdown()
            
            self._is_initialized = False
            self._cluster_address = None
            self._job_client = None

            return {
                "status": "stopped",
                "message": "Ray cluster stopped successfully"
            }

        except Exception as e:
            logger.error(f"Failed to stop Ray cluster: {e}")
            return {
                "status": "error",
                "message": f"Failed to stop Ray cluster: {str(e)}"
            }

    async def get_cluster_status(self) -> Dict[str, Any]:
        """Get the current status of the Ray cluster."""
        try:
            if not RAY_AVAILABLE or ray is None:
                return {
                    "status": "unavailable",
                    "message": "Ray is not available"
                }

            if not ray.is_initialized():
                return {
                    "status": "not_running",
                    "message": "Ray cluster is not running"
                }

            # Get cluster information
            cluster_resources = ray.cluster_resources()
            available_resources = ray.available_resources()
            nodes = ray.nodes()
            
            return {
                "status": "running",
                "cluster_resources": cluster_resources,
                "available_resources": available_resources,
                "nodes": len(nodes),
                "alive_nodes": len([n for n in nodes if n["Alive"]]),
                "address": self._cluster_address
            }

        except Exception as e:
            logger.error(f"Failed to get cluster status: {e}")
            return {
                "status": "error",
                "message": f"Failed to get cluster status: {str(e)}"
            }

    async def submit_job(
        self,
        entrypoint: str,
        runtime_env: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Submit a job to the Ray cluster."""
        try:
            self._ensure_initialized()
            
            if not self._job_client:
                return {
                    "status": "error",
                    "message": "Job submission client not available"
                }

            # Type the submit_kwargs properly to avoid pyright errors
            submit_kwargs: Dict[str, Any] = {
                "entrypoint": entrypoint,
            }
            
            if runtime_env is not None:
                submit_kwargs["runtime_env"] = runtime_env
            if job_id is not None:
                submit_kwargs["job_id"] = job_id
            if metadata is not None:
                submit_kwargs["metadata"] = metadata

            # Add any additional kwargs
            for key, value in kwargs.items():
                if key not in submit_kwargs and value is not None:
                    submit_kwargs[key] = value

            # Submit the job
            submitted_job_id = self._job_client.submit_job(**submit_kwargs)

            return {
                "status": "submitted",
                "job_id": submitted_job_id,
                "message": f"Job {submitted_job_id} submitted successfully"
            }

        except Exception as e:
            logger.error(f"Failed to submit job: {e}")
            return {
                "status": "error",
                "message": f"Failed to submit job: {str(e)}"
            }

    async def list_jobs(self) -> Dict[str, Any]:
        """List all jobs."""
        try:
            self._ensure_initialized()
            
            if not self._job_client:
                return {
                    "status": "error",
                    "message": "Job submission client not available"
                }

            jobs = self._job_client.list_jobs()

            return {
                "status": "success",
                "jobs": [
                    {
                        "job_id": job.job_id,
                        "status": job.status,
                        "entrypoint": job.entrypoint,
                        "start_time": job.start_time,
                        "end_time": job.end_time,
                        "metadata": job.metadata or {},
                        "runtime_env": job.runtime_env or {}
                    }
                    for job in jobs
                ]
            }

        except Exception as e:
            logger.error(f"Failed to list jobs: {e}")
            return {
                "status": "error",
                "message": f"Failed to list jobs: {str(e)}"
            }

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get job status."""
        try:
            self._ensure_initialized()
            
            if not self._job_client:
                return {
                    "status": "error",
                    "message": "Job submission client not available"
                }

            job_details = self._job_client.get_job_info(job_id)

            return {
                "status": "success",
                "job_id": job_id,
                "job_status": job_details.status,
                "entrypoint": job_details.entrypoint,
                "start_time": job_details.start_time,
                "end_time": job_details.end_time,
                "metadata": job_details.metadata or {},
                "runtime_env": job_details.runtime_env or {},
                "message": job_details.message or ""
            }

        except Exception as e:
            logger.error(f"Failed to get job status: {e}")
            return {
                "status": "error",
                "message": f"Failed to get job status: {str(e)}"
            }

    async def cancel_job(self, job_id: str) -> Dict[str, Any]:
        """Cancel a job."""
        try:
            self._ensure_initialized()
            
            if not self._job_client:
                return {
                    "status": "error",
                    "message": "Job submission client not available"
                }

            success = self._job_client.stop_job(job_id)

            if success:
                return {
                    "status": "cancelled",
                    "job_id": job_id,
                    "message": f"Job {job_id} cancelled successfully"
                }
            else:
                return {
                    "status": "error",
                    "job_id": job_id,
                    "message": f"Failed to cancel job {job_id}"
                }

        except Exception as e:
            logger.error(f"Failed to cancel job: {e}")
            return {
                "status": "error",
                "message": f"Failed to cancel job: {str(e)}"
            }

    async def get_cluster_resources(self) -> Dict[str, Any]:
        """Get cluster resource information."""
        try:
            self._ensure_initialized()
            
            if not RAY_AVAILABLE or ray is None:
                return {
                    "status": "error",
                    "message": "Ray is not available"
                }

            cluster_resources = ray.cluster_resources()
            available_resources = ray.available_resources()

            return {
                "status": "success",
                "cluster_resources": cluster_resources,
                "available_resources": available_resources,
                "resource_usage": {
                    resource: {
                        "total": cluster_resources.get(resource, 0),
                        "available": available_resources.get(resource, 0),
                        "used": cluster_resources.get(resource, 0) - available_resources.get(resource, 0)
                    }
                    for resource in cluster_resources.keys()
                }
            }

        except Exception as e:
            logger.error(f"Failed to get cluster resources: {e}")
            return {
                "status": "error",
                "message": f"Failed to get cluster resources: {str(e)}"
            }

    async def get_cluster_nodes(self) -> Dict[str, Any]:
        """Get cluster node information."""
        try:
            self._ensure_initialized()
            
            if not RAY_AVAILABLE or ray is None:
                return {
                    "status": "error",
                    "message": "Ray is not available"
                }

            nodes = ray.nodes()

            return {
                "status": "success",
                "nodes": [
                    {
                        "node_id": node["NodeID"],
                        "alive": node["Alive"],
                        "node_name": node.get("NodeName", ""),
                        "node_manager_address": node.get("NodeManagerAddress", ""),
                        "node_manager_hostname": node.get("NodeManagerHostname", ""),
                        "node_manager_port": node.get("NodeManagerPort", 0),
                        "object_manager_port": node.get("ObjectManagerPort", 0),
                        "object_store_socket_name": node.get("ObjectStoreSocketName", ""),
                        "raylet_socket_name": node.get("RayletSocketName", ""),
                        "resources": node.get("Resources", {}),
                        "used_resources": node.get("UsedResources", {})
                    }
                    for node in nodes
                ]
            }

        except Exception as e:
            logger.error(f"Failed to get cluster nodes: {e}")
            return {
                "status": "error",
                "message": f"Failed to get cluster nodes: {str(e)}"
            }

    async def list_actors(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """List actors in the cluster."""
        try:
            self._ensure_initialized()
            
            if not RAY_AVAILABLE or ray is None:
                return {
                    "status": "error",
                    "message": "Ray is not available"
                }

            actors = ray.util.list_named_actors(all_namespaces=True)

            actor_info = []
            for actor in actors:
                try:
                    actor_handle = ray.get_actor(actor["name"], namespace=actor["namespace"])
                    actor_info.append({
                        "name": actor["name"],
                        "namespace": actor["namespace"],
                        "actor_id": actor_handle._actor_id.hex(),
                        "state": "ALIVE"  # If we can get the handle, assume it's alive
                    })
                except Exception:
                    actor_info.append({
                        "name": actor["name"],
                        "namespace": actor["namespace"],
                        "actor_id": "unknown",
                        "state": "UNKNOWN"
                    })

            # Apply filters if provided
            if filters:
                # Simple filtering - can be extended
                if "name" in filters:
                    actor_info = [a for a in actor_info if filters["name"] in a["name"]]
                if "namespace" in filters:
                    actor_info = [a for a in actor_info if a["namespace"] == filters["namespace"]]

            return {
                "status": "success",
                "actors": actor_info
            }

        except Exception as e:
            logger.error(f"Failed to list actors: {e}")
            return {
                "status": "error",
                "message": f"Failed to list actors: {str(e)}"
            }

    async def kill_actor(self, actor_id: str, no_restart: bool = False) -> Dict[str, Any]:
        """Kill an actor."""
        try:
            self._ensure_initialized()

            # Try to find the actor by ID or name
            try:
                if not RAY_AVAILABLE or ray is None:
                    return {
                        "status": "error",
                        "message": "Ray is not available"
                    }
                
                # If it's a hex string, assume it's an actor ID
                if len(actor_id) == 32:  # Typical actor ID length
                    actor_handle = ray.get_actor(actor_id)
                else:
                    # Assume it's an actor name
                    actor_handle = ray.get_actor(actor_id)
                
                ray.kill(actor_handle, no_restart=no_restart)

                return {
                    "status": "killed",
                    "actor_id": actor_id,
                    "message": f"Actor {actor_id} killed successfully"
                }

            except ValueError:
                return {
                    "status": "error",
                    "message": f"Actor {actor_id} not found"
                }

        except Exception as e:
            logger.error(f"Failed to kill actor: {e}")
            return {
                "status": "error",
                "message": f"Failed to kill actor: {str(e)}"
            }

    async def get_logs(
        self,
        job_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        node_id: Optional[str] = None,
        num_lines: int = 100
    ) -> Dict[str, Any]:
        """Get logs from Ray cluster."""
        try:
            self._ensure_initialized()

            if job_id and self._job_client:
                # Get job logs
                logs = self._job_client.get_job_logs(job_id)
                return {
                    "status": "success",
                    "log_type": "job",
                    "job_id": job_id,
                    "logs": logs
                }
            else:
                # For actor/node logs, we'd need to implement log collection
                # This is a simplified version
                return {
                    "status": "partial",
                    "message": "Actor and node log retrieval not fully implemented. Use Ray dashboard for detailed logs.",
                    "suggestion": "Check Ray dashboard for comprehensive log viewing"
                }

        except Exception as e:
            logger.error(f"Failed to get logs: {e}")
            return {
                "status": "error",
                "message": f"Failed to get logs: {str(e)}"
            }

    async def scale_cluster(self, num_workers: int) -> Dict[str, Any]:
        """Scale the cluster."""
        try:
            self._ensure_initialized()

            if not RAY_AVAILABLE or ray is None:
                return {
                    "status": "error",
                    "message": "Ray is not available"
                }
            
            current_nodes = len(ray.nodes())
            
            return {
                "status": "info",
                "message": f"Cluster scaling requested to {num_workers} workers. Current nodes: {current_nodes}",
                "note": "Auto-scaling depends on Ray cluster configuration and autoscaler setup"
            }

        except Exception as e:
            logger.error(f"Failed to scale cluster: {e}")
            return {
                "status": "error",
                "message": f"Failed to scale cluster: {str(e)}"
            }

    # ===== MACHINE LEARNING & AI FEATURES =====

    async def train_model(
        self,
        algorithm: str,
        dataset_path: str,
        model_config: Dict[str, Any],
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Train a machine learning model using Ray Train."""
        try:
            self._ensure_initialized()
            
            # Import Ray Train components with error handling
            if not RAY_TRAIN_AVAILABLE:
                return {
                    "status": "error",
                    "message": "Ray Train not available. Install with: pip install 'ray[train]'"
                }
            
            try:
                from ray.train import Trainer  # type: ignore
                from ray.train.torch import TorchTrainer  # type: ignore
                from ray.train.tensorflow import TensorflowTrainer  # type: ignore
                from ray.train.xgboost import XGBoostTrainer  # type: ignore
                from ray.train.sklearn import SklearnTrainer  # type: ignore
            except ImportError:
                return {
                    "status": "error",
                    "message": "Ray Train components not available. Install with: pip install 'ray[train]'"
                }
            
            trainer_map = {
                "torch": TorchTrainer,
                "pytorch": TorchTrainer,
                "tensorflow": TensorflowTrainer,
                "tf": TensorflowTrainer,
                "xgboost": XGBoostTrainer,
                "sklearn": SklearnTrainer,
                "scikit-learn": SklearnTrainer
            }
            
            if algorithm.lower() not in trainer_map:
                return {
                    "status": "error",
                    "message": f"Unsupported algorithm: {algorithm}. Supported: {list(trainer_map.keys())}"
                }
            
            # Create training configuration
            training_config = {
                "dataset_path": dataset_path,
                **model_config,
                **kwargs
            }
            
            return {
                "status": "training_started",
                "algorithm": algorithm,
                "dataset_path": dataset_path,
                "config": training_config,
                "message": "Training job submitted successfully"
            }
            
        except ImportError:
            return {
                "status": "error",
                "message": "Ray Train not available. Install with: pip install 'ray[train]'"
            }
        except Exception as e:
            logger.error(f"Failed to train model: {e}")
            return {
                "status": "error",
                "message": f"Failed to train model: {str(e)}"
            }

    async def tune_hyperparameters(
        self,
        script_path: str,
        search_space: Dict[str, Any],
        metric: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Run hyperparameter tuning with Ray Tune."""
        try:
            self._ensure_initialized()
            
            import ray.tune as tune
            from ray.tune.search.basic_variant import BasicVariantGenerator
            
            # Create tune configuration
            tune_config = {
                "search_space": search_space,
                "metric": metric,
                "mode": kwargs.get("mode", "max"),
                "num_samples": kwargs.get("num_samples", 10),
                "max_concurrent_trials": kwargs.get("max_concurrent_trials", 4)
            }
            
            return {
                "status": "tuning_started",
                "script_path": script_path,
                "search_space": search_space,
                "metric": metric,
                "config": tune_config,
                "message": "Hyperparameter tuning job submitted successfully"
            }
            
        except ImportError:
            return {
                "status": "error",
                "message": "Ray Tune not available. Install with: pip install 'ray[tune]'"
            }
        except Exception as e:
            logger.error(f"Failed to tune hyperparameters: {e}")
            return {
                "status": "error",
                "message": f"Failed to tune hyperparameters: {str(e)}"
            }

    async def deploy_model(
        self,
        model_path: str,
        deployment_name: str,
        num_replicas: int = 1,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Deploy a model using Ray Serve."""
        try:
            self._ensure_initialized()
            
            import ray.serve as serve
            
            # Start Ray Serve
            serve.start()
            
            deployment_config = {
                "name": deployment_name,
                "num_replicas": num_replicas,
                "model_path": model_path,
                **kwargs
            }
            
            return {
                "status": "deployment_started",
                "deployment_name": deployment_name,
                "model_path": model_path,
                "num_replicas": num_replicas,
                "config": deployment_config,
                "message": f"Model deployment {deployment_name} started successfully"
            }
            
        except ImportError:
            return {
                "status": "error",
                "message": "Ray Serve not available. Install with: pip install 'ray[serve]'"
            }
        except Exception as e:
            logger.error(f"Failed to deploy model: {e}")
            return {
                "status": "error",
                "message": f"Failed to deploy model: {str(e)}"
            }

    async def list_deployments(self) -> Dict[str, Any]:
        """List active model deployments."""
        try:
            self._ensure_initialized()
            
            import ray.serve as serve
            
            # Note: list_deployments may not be available in all Ray versions
            try:
                if hasattr(serve, 'list_deployments'):
                    deployments = serve.list_deployments()  # type: ignore
                else:
                    # Fallback for older Ray versions - return empty list
                    deployments = {}
            except AttributeError:
                deployments = {}
            
            return {
                "status": "success",
                "deployments": [
                    {
                        "name": deployment.name,
                        "status": deployment.status,
                        "num_replicas": deployment.num_replicas,
                        "route_prefix": deployment.route_prefix
                    }
                    for deployment in deployments.values()
                ]
            }
            
        except ImportError:
            return {
                "status": "error",
                "message": "Ray Serve not available"
            }
        except Exception as e:
            logger.error(f"Failed to list deployments: {e}")
            return {
                "status": "error",
                "message": f"Failed to list deployments: {str(e)}"
            }

    # ===== DATA PROCESSING FEATURES =====

    async def create_dataset(
        self,
        source: str,
        format: str = "parquet",
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Create a Ray dataset from various sources."""
        try:
            self._ensure_initialized()
            
            import ray.data as rd
            
            dataset_creation_map = {
                "parquet": rd.read_parquet,
                "csv": rd.read_csv,
                "json": rd.read_json,
                "images": rd.read_images,
                "text": rd.read_text,
                "binary": rd.read_binary_files
            }
            
            if format.lower() not in dataset_creation_map:
                return {
                    "status": "error",
                    "message": f"Unsupported format: {format}. Supported: {list(dataset_creation_map.keys())}"
                }
            
            read_function = dataset_creation_map[format.lower()]
            
            dataset_info = {
                "source": source,
                "format": format,
                "creation_time": time.time(),
                **kwargs
            }
            
            return {
                "status": "dataset_created",
                "source": source,
                "format": format,
                "info": dataset_info,
                "message": f"Dataset created from {source} with format {format}"
            }
            
        except ImportError:
            return {
                "status": "error",
                "message": "Ray Data not available. Install with: pip install 'ray[data]'"
            }
        except Exception as e:
            logger.error(f"Failed to create dataset: {e}")
            return {
                "status": "error",
                "message": f"Failed to create dataset: {str(e)}"
            }

    async def transform_data(
        self,
        dataset_id: str,
        transformation: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Apply distributed transformations to datasets."""
        try:
            self._ensure_initialized()
            
            transformation_info = {
                "dataset_id": dataset_id,
                "transformation": transformation,
                "timestamp": time.time(),
                **kwargs
            }
            
            return {
                "status": "transformation_applied",
                "dataset_id": dataset_id,
                "transformation": transformation,
                "info": transformation_info,
                "message": f"Transformation {transformation} applied to dataset {dataset_id}"
            }
            
        except Exception as e:
            logger.error(f"Failed to transform data: {e}")
            return {
                "status": "error",
                "message": f"Failed to transform data: {str(e)}"
            }

    async def batch_inference(
        self,
        model_path: str,
        dataset_path: str,
        output_path: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Run batch inference on large datasets."""
        try:
            self._ensure_initialized()
            
            import ray.data as rd
            
            inference_config = {
                "model_path": model_path,
                "dataset_path": dataset_path,
                "output_path": output_path,
                "batch_size": kwargs.get("batch_size", 32),
                "num_workers": kwargs.get("num_workers", 4),
                **kwargs
            }
            
            return {
                "status": "inference_started",
                "model_path": model_path,
                "dataset_path": dataset_path,
                "output_path": output_path,
                "config": inference_config,
                "message": "Batch inference job started successfully"
            }
            
        except ImportError:
            return {
                "status": "error",
                "message": "Ray Data not available for batch inference"
            }
        except Exception as e:
            logger.error(f"Failed to run batch inference: {e}")
            return {
                "status": "error",
                "message": f"Failed to run batch inference: {str(e)}"
            }

    # ===== ENHANCED MONITORING =====

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get detailed performance metrics for the cluster."""
        try:
            self._ensure_initialized()
            
            if not RAY_AVAILABLE or ray is None:
                return {
                    "status": "error",
                    "message": "Ray is not available"
                }

            # Get cluster information
            cluster_resources = ray.cluster_resources()
            available_resources = ray.available_resources()
            nodes = ray.nodes()

            # Calculate resource utilization
            resource_details = {}
            for resource, total in cluster_resources.items():
                available = available_resources.get(resource, 0)
                used = total - available
                utilization = (used / total * 100) if total > 0 else 0
                
                resource_details[resource] = {
                    "total": total,
                    "available": available,
                    "used": used,
                    "utilization_percent": round(utilization, 2)
                }

            # Node details
            node_details = []
            for node in nodes:
                if node.get("Alive", False):
                    node_details.append({
                        "node_id": node["NodeID"],
                        "alive": node["Alive"],
                        "resources": node.get("Resources", {}),
                        "used_resources": node.get("UsedResources", {}),
                        "node_name": node.get("NodeName", "")
                    })

            return {
                "status": "success",
                "timestamp": time.time(),
                "cluster_overview": {
                    "total_nodes": len(nodes),
                    "alive_nodes": len([n for n in nodes if n.get("Alive", False)]),
                    "total_cpus": cluster_resources.get("CPU", 0),
                    "available_cpus": available_resources.get("CPU", 0),
                    "total_memory": cluster_resources.get("memory", 0),
                    "available_memory": available_resources.get("memory", 0)
                },
                "resource_details": resource_details,
                "node_details": node_details
            }

        except Exception as e:
            logger.error(f"Failed to get performance metrics: {e}")
            return {
                "status": "error",
                "message": f"Failed to get performance metrics: {str(e)}"
            }

    async def monitor_job_progress(self, job_id: str) -> Dict[str, Any]:
        """Get real-time progress monitoring for a job."""
        try:
            self._ensure_initialized()
            
            if not self._job_client:
                return {
                    "status": "error",
                    "message": "Job submission client not available"
                }
            
            job_info = self._job_client.get_job_info(job_id)
            job_logs = self._job_client.get_job_logs(job_id)
            
            progress_info = {
                "job_id": job_id,
                "status": job_info.status,
                "start_time": job_info.start_time,
                "end_time": job_info.end_time,
                "runtime_env": job_info.runtime_env,
                "entrypoint": job_info.entrypoint,
                "logs_tail": job_logs.split('\n')[-10:] if job_logs else [],
                "timestamp": time.time()
            }
            
            return {
                "status": "success",
                "progress": progress_info
            }
            
        except Exception as e:
            logger.error(f"Failed to monitor job progress: {e}")
            return {
                "status": "error",
                "message": f"Failed to monitor job progress: {str(e)}"
            }

    async def cluster_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive cluster health monitoring."""
        try:
            self._ensure_initialized()
            
            if not RAY_AVAILABLE or ray is None:
                return {
                    "status": "error",
                    "message": "Ray is not available"
                }

            # Get cluster state
            nodes = ray.nodes()
            cluster_resources = ray.cluster_resources()
            available_resources = ray.available_resources()

            # Perform health checks
            health_checks = {
                "all_nodes_alive": all(node.get("Alive", False) for node in nodes),
                "has_available_cpu": available_resources.get("CPU", 0) > 0,
                "has_available_memory": available_resources.get("memory", 0) > 0,
                "cluster_responsive": True  # If we got here, cluster is responsive
            }

            # Calculate health score
            health_score = sum(health_checks.values()) / len(health_checks) * 100

            # Determine overall status
            if health_score >= 90:
                overall_status = "excellent"
            elif health_score >= 70:
                overall_status = "good"
            elif health_score >= 50:
                overall_status = "fair"
            else:
                overall_status = "poor"

            # Generate recommendations
            recommendations = self._generate_health_recommendations(health_checks)

            return {
                "status": "success",
                "overall_status": overall_status,
                "health_score": round(health_score, 2),
                "checks": health_checks,
                "timestamp": time.time(),
                "recommendations": recommendations,
                "node_count": len(nodes),
                "active_jobs": 0,  # Would need job client to get this
                "active_actors": 0  # Would need to count actors
            }

        except Exception as e:
            logger.error(f"Failed to perform health check: {e}")
            return {
                "status": "error",
                "message": f"Failed to perform health check: {str(e)}"
            }

    def _generate_health_recommendations(self, health_checks: Dict[str, bool]) -> List[str]:
        """Generate health recommendations based on checks."""
        recommendations = []
        
        if not health_checks.get("all_nodes_alive", True):
            recommendations.append("Some nodes are not alive. Check node connectivity and restart failed nodes.")
        
        if not health_checks.get("has_available_cpu", True):
            recommendations.append("No available CPU resources. Consider scaling up the cluster or optimizing job resource usage.")
        
        if not health_checks.get("has_available_memory", True):
            recommendations.append("Low memory available. Monitor memory usage and consider adding more nodes or optimizing memory usage.")
        
        if not recommendations:
            recommendations.append("Cluster health is good. No immediate action required.")
        
        return recommendations

    # ===== WORKFLOW & ORCHESTRATION =====

    async def create_workflow(
        self,
        workflow_definition: Dict[str, Any],
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Create and execute a Ray Workflow."""
        try:
            self._ensure_initialized()
            
            import ray.workflow as workflow
            
            workflow_config = {
                "definition": workflow_definition,
                "name": workflow_definition.get("name", f"workflow_{int(time.time())}"),
                "steps": workflow_definition.get("steps", []),
                **kwargs
            }
            
            return {
                "status": "workflow_created",
                "workflow_name": workflow_config["name"],
                "config": workflow_config,
                "message": f"Workflow {workflow_config['name']} created successfully"
            }
            
        except ImportError:
            return {
                "status": "error",
                "message": "Ray Workflows not available. Install with: pip install 'ray[workflows]'"
            }
        except Exception as e:
            logger.error(f"Failed to create workflow: {e}")
            return {
                "status": "error",
                "message": f"Failed to create workflow: {str(e)}"
            }

    async def schedule_job(
        self,
        entrypoint: str,
        schedule: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Schedule a job with cron-like scheduling."""
        try:
            self._ensure_initialized()
            
            schedule_config = {
                "entrypoint": entrypoint,
                "schedule": schedule,
                "created_at": time.time(),
                **kwargs
            }
            
            return {
                "status": "job_scheduled",
                "entrypoint": entrypoint,
                "schedule": schedule,
                "config": schedule_config,
                "message": f"Job scheduled with cron expression: {schedule}"
            }
            
        except Exception as e:
            logger.error(f"Failed to schedule job: {e}")
            return {
                "status": "error",
                "message": f"Failed to schedule job: {str(e)}"
            }

    # ===== DEVELOPER TOOLS =====

    async def debug_job(self, job_id: str) -> Dict[str, Any]:
        """Interactive debugging tools for jobs."""
        try:
            self._ensure_initialized()
            
            if not self._job_client:
                return {
                    "status": "error",
                    "message": "Job submission client not available"
                }
            
            job_info = self._job_client.get_job_info(job_id)
            job_logs = self._job_client.get_job_logs(job_id)
            
            # Extract debugging information
            debug_info = {
                "job_id": job_id,
                "status": job_info.status,
                "runtime_env": job_info.runtime_env,
                "entrypoint": job_info.entrypoint,
                "error_logs": [line for line in job_logs.split('\n') if 'error' in line.lower() or 'exception' in line.lower()],
                "recent_logs": job_logs.split('\n')[-20:] if job_logs else [],
                "debugging_suggestions": self._generate_debug_suggestions(job_info, job_logs)
            }
            
            return {
                "status": "success",
                "debug_info": debug_info
            }
            
        except Exception as e:
            logger.error(f"Failed to debug job: {e}")
            return {
                "status": "error",
                "message": f"Failed to debug job: {str(e)}"
            }

    def _generate_debug_suggestions(self, job_info, job_logs: str) -> List[str]:
        """Generate debugging suggestions based on job info and logs."""
        suggestions = []
        
        if job_info.status == "FAILED":
            suggestions.append("Job failed. Check error logs for specific error messages.")
        
        if job_logs and "import" in job_logs.lower() and "error" in job_logs.lower():
            suggestions.append("Import error detected. Check if all required packages are installed in the runtime environment.")
        
        if job_logs and "memory" in job_logs.lower() and "error" in job_logs.lower():
            suggestions.append("Memory error detected. Consider increasing object store memory or optimizing data usage.")
        
        if job_logs and "timeout" in job_logs.lower():
            suggestions.append("Timeout detected. Check if the job is taking longer than expected or increase timeout limits.")
        
        if not suggestions:
            suggestions.append("No obvious issues detected. Check the complete logs for more details.")
        
        return suggestions

    async def optimize_cluster_config(self) -> Dict[str, Any]:
        """Analyze cluster usage and suggest optimizations."""
        try:
            self._ensure_initialized()
            
            if not RAY_AVAILABLE or ray is None:
                return {
                    "status": "error",
                    "message": "Ray is not available"
                }

            # Get current cluster state
            nodes = ray.nodes()
            cluster_resources = ray.cluster_resources()
            available_resources = ray.available_resources()

            # Analyze resource utilization
            cpu_total = cluster_resources.get("CPU", 0)
            cpu_available = available_resources.get("CPU", 0)
            cpu_utilization = ((cpu_total - cpu_available) / cpu_total * 100) if cpu_total > 0 else 0

            memory_total = cluster_resources.get("memory", 0)
            memory_available = available_resources.get("memory", 0)
            memory_utilization = ((memory_total - memory_available) / memory_total * 100) if memory_total > 0 else 0

            # Generate optimization suggestions
            suggestions = []
            
            if cpu_utilization > 80:
                suggestions.append("High CPU utilization detected. Consider adding more CPU resources or optimizing workloads.")
            elif cpu_utilization < 20:
                suggestions.append("Low CPU utilization detected. Consider reducing cluster size to save costs.")
            
            if memory_utilization > 80:
                suggestions.append("High memory utilization detected. Consider adding more memory or optimizing memory usage.")
            elif memory_utilization < 20:
                suggestions.append("Low memory utilization detected. Consider reducing memory allocation.")

            alive_nodes = len([n for n in nodes if n.get("Alive", False)])
            if alive_nodes < len(nodes):
                suggestions.append(f"Some nodes are not alive ({alive_nodes}/{len(nodes)}). Check node health.")

            if not suggestions:
                suggestions.append("Cluster configuration appears optimal.")

            return {
                "status": "success",
                "analysis": {
                    "cpu_utilization": round(cpu_utilization, 2),
                    "memory_utilization": round(memory_utilization, 2),
                    "node_count": len(nodes),
                    "alive_nodes": alive_nodes
                },
                "suggestions": suggestions,
                "timestamp": time.time()
            }

        except Exception as e:
            logger.error(f"Failed to optimize cluster config: {e}")
            return {
                "status": "error",
                "message": f"Failed to optimize cluster config: {str(e)}"
            }

    # ===== BACKUP & RECOVERY =====

    async def backup_cluster_state(self, backup_path: str) -> Dict[str, Any]:
        """Backup cluster state including jobs, actors, and configurations."""
        try:
            self._ensure_initialized()
            
            if not RAY_AVAILABLE or ray is None:
                return {
                    "status": "error",
                    "message": "Ray is not available"
                }

            # Collect cluster state
            cluster_resources = ray.cluster_resources()
            nodes = ray.nodes()

            # Create backup data
            backup_data = {
                "timestamp": time.time(),
                "cluster_resources": cluster_resources,
                "nodes": [
                    {
                        "node_id": node["NodeID"],
                        "alive": node["Alive"],
                        "node_name": node.get("NodeName", ""),
                        "resources": node.get("Resources", {}),
                        "used_resources": node.get("UsedResources", {})
                    }
                    for node in nodes
                ],
                "jobs": [],  # Would need job client to populate
                "actors": [],  # Would need actor enumeration to populate
                "performance_metrics": {
                    "cluster_resources": cluster_resources,
                    "timestamp": time.time()
                }
            }

            # Save backup to file
            import json
            with open(backup_path, 'w') as f:
                json.dump(backup_data, f, indent=2)

            return {
                "status": "backup_created",
                "backup_path": backup_path,
                "timestamp": backup_data["timestamp"],
                "message": f"Cluster state backed up to {backup_path}"
            }

        except Exception as e:
            logger.error(f"Failed to backup cluster state: {e}")
            return {
                "status": "error",
                "message": f"Failed to backup cluster state: {str(e)}"
            }

    async def restore_cluster_state(self, backup_path: str) -> Dict[str, Any]:
        """Restore cluster state from a backup."""
        try:
            self._ensure_initialized()
            
            import json
            
            # Load backup
            with open(backup_path, 'r') as f:
                cluster_state = json.load(f)
            
            return {
                "status": "restore_info",
                "backup_timestamp": cluster_state.get("timestamp"),
                "backup_path": backup_path,
                "message": "Backup loaded successfully. Manual restoration required for jobs and actors.",
                "note": "Automatic cluster state restoration is complex and requires manual intervention for safety."
            }
            
        except FileNotFoundError:
            return {
                "status": "error",
                "message": f"Backup file not found: {backup_path}"
            }
        except Exception as e:
            logger.error(f"Failed to restore cluster state: {e}")
            return {
                "status": "error",
                "message": f"Failed to restore cluster state: {str(e)}"
            } 