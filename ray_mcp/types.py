"""Type definitions for the MCP Ray server."""

from typing import Dict, List, Optional, Union, Literal, TypedDict, Protocol, Any
from enum import Enum
import time

# ===== BASIC TYPE ALIASES =====

# Resource types
ResourceValue = Union[int, float]
ResourceDict = Dict[str, ResourceValue]

# JSON-serializable types
JsonValue = Union[str, int, float, bool, None, Dict[str, Any], List[Any]]
JsonDict = Dict[str, JsonValue]

# Ray-specific types
RayAddress = str
NodeId = str
JobId = str
ActorId = str
ActorName = str

# ===== ENUMS =====

class JobStatus(str, Enum):
    """Ray job status enumeration."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"

class ActorState(str, Enum):
    """Ray actor state enumeration."""
    ALIVE = "ALIVE"
    DEAD = "DEAD"
    UNKNOWN = "UNKNOWN"

class HealthStatus(str, Enum):
    """Cluster health status enumeration."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"

class MLAlgorithm(str, Enum):
    """Supported ML algorithms."""
    TORCH = "torch"
    PYTORCH = "pytorch"
    TENSORFLOW = "tensorflow"
    TF = "tf"
    XGBOOST = "xgboost"
    SKLEARN = "sklearn"
    SCIKIT_LEARN = "scikit-learn"

class DataFormat(str, Enum):
    """Supported data formats."""
    PARQUET = "parquet"
    CSV = "csv"
    JSON = "json"
    IMAGES = "images"
    TEXT = "text"
    BINARY = "binary"

class OptimizationMode(str, Enum):
    """Hyperparameter optimization modes."""
    MAX = "max"
    MIN = "min"

# ===== TYPED DICTIONARIES =====

class NodeInfo(TypedDict):
    """Information about a Ray cluster node."""
    node_id: NodeId
    alive: bool
    node_name: str
    node_manager_address: str
    node_manager_hostname: str
    node_manager_port: int
    object_manager_port: int
    object_store_socket_name: str
    raylet_socket_name: str
    resources: ResourceDict
    used_resources: ResourceDict

class JobInfo(TypedDict):
    """Information about a Ray job."""
    job_id: JobId
    status: JobStatus
    start_time: Optional[float]
    end_time: Optional[float]
    runtime_env: Optional[JsonDict]
    entrypoint: str
    metadata: Optional[Dict[str, str]]

class ActorInfo(TypedDict):
    """Information about a Ray actor."""
    name: ActorName
    namespace: str
    actor_id: ActorId
    state: ActorState

class ClusterResources(TypedDict):
    """Cluster resource information."""
    total: ResourceValue
    available: ResourceValue
    used: ResourceValue

class PerformanceMetrics(TypedDict):
    """Cluster performance metrics."""
    timestamp: float
    cluster_overview: Dict[str, Union[int, float]]
    resource_details: Dict[str, ClusterResources]
    node_details: List[NodeInfo]

class HealthCheck(TypedDict):
    """Cluster health check result."""
    all_nodes_alive: bool
    has_available_cpu: bool
    has_available_memory: bool
    cluster_responsive: bool

class HealthReport(TypedDict):
    """Complete health report."""
    overall_status: HealthStatus
    health_score: float
    checks: HealthCheck
    timestamp: float
    recommendations: List[str]

# ===== ML-SPECIFIC TYPES =====

class ModelConfig(TypedDict, total=False):
    """Model configuration for training."""
    learning_rate: float
    batch_size: int
    epochs: int
    hidden_size: int
    num_layers: int
    dropout: float
    optimizer: str
    loss_function: str

class SearchSpace(TypedDict, total=False):
    """Hyperparameter search space."""
    learning_rate: Union[List[float], Dict[str, Union[float, str]]]
    batch_size: Union[List[int], Dict[str, Union[int, str]]]
    epochs: Union[List[int], Dict[str, Union[int, str]]]
    hidden_size: Union[List[int], Dict[str, Union[int, str]]]

class TuneConfig(TypedDict):
    """Ray Tune configuration."""
    search_space: SearchSpace
    metric: str
    mode: OptimizationMode
    num_samples: int
    max_concurrent_trials: int

class DeploymentConfig(TypedDict):
    """Model deployment configuration."""
    name: str
    num_replicas: int
    model_path: str

class DeploymentInfo(TypedDict):
    """Information about a model deployment."""
    name: str
    status: str
    num_replicas: int
    route_prefix: Optional[str]

# ===== DATA PROCESSING TYPES =====

class DatasetInfo(TypedDict):
    """Dataset information."""
    source: str
    format: DataFormat
    creation_time: float

class TransformationInfo(TypedDict):
    """Data transformation information."""
    dataset_id: str
    transformation: str
    timestamp: float

class InferenceConfig(TypedDict):
    """Batch inference configuration."""
    model_path: str
    dataset_path: str
    output_path: str
    batch_size: int
    num_workers: int

# ===== WORKFLOW TYPES =====

class WorkflowStep(TypedDict):
    """A single workflow step."""
    name: str
    function: str
    dependencies: List[str]
    args: List[JsonValue]
    kwargs: JsonDict

class WorkflowDefinition(TypedDict):
    """Complete workflow definition."""
    name: str
    steps: List[WorkflowStep]
    description: Optional[str]

class ScheduleConfig(TypedDict):
    """Job scheduling configuration."""
    entrypoint: str
    schedule: str
    created_at: float

# ===== BACKUP TYPES =====

class ClusterState(TypedDict):
    """Complete cluster state for backup."""
    timestamp: float
    cluster_resources: ResourceDict
    nodes: List[NodeInfo]
    jobs: List[JobInfo]
    actors: List[ActorInfo]
    performance_metrics: PerformanceMetrics

# ===== CONFIGURATION TYPES =====

class JobSubmissionConfig(TypedDict, total=False):
    """Configuration for job submission."""
    entrypoint: str
    runtime_env: Optional[JsonDict]
    job_id: Optional[JobId]
    metadata: Optional[Dict[str, str]]
    entrypoint_num_cpus: Optional[Union[int, float]]
    entrypoint_num_gpus: Optional[Union[int, float]]
    entrypoint_memory: Optional[int]
    entrypoint_resources: Optional[Dict[str, float]]

class ActorConfig(TypedDict, total=False):
    """Configuration for actor creation."""
    name: Optional[str]
    namespace: Optional[str]
    num_cpus: Optional[Union[int, float]]
    num_gpus: Optional[Union[int, float]]
    memory: Optional[int]
    resources: Optional[Dict[str, float]]

class ClusterHealth(TypedDict):
    """Complete cluster health information."""
    overall_status: HealthStatus
    health_score: float
    checks: HealthCheck
    timestamp: float
    recommendations: List[str]
    node_count: int
    active_jobs: int
    active_actors: int

# ===== RESPONSE TYPES =====

class SuccessResponse(TypedDict):
    """Standard success response."""
    status: Literal["success"]
    message: str

class ErrorResponse(TypedDict):
    """Standard error response."""
    status: Literal["error"]
    message: str

class ClusterStartResponse(TypedDict):
    """Response from starting a cluster."""
    status: Literal["started", "already_running"]
    message: str
    address: Optional[RayAddress]
    dashboard_url: Optional[str]
    node_id: Optional[str]
    session_name: Optional[str]

class JobSubmissionResponse(TypedDict):
    """Response from job submission."""
    status: Literal["submitted"]
    job_id: JobId
    message: str

class TrainingResponse(TypedDict):
    """Response from model training."""
    status: Literal["training_started"]
    algorithm: MLAlgorithm
    dataset_path: str
    config: ModelConfig
    message: str

class TuningResponse(TypedDict):
    """Response from hyperparameter tuning."""
    status: Literal["tuning_started"]
    script_path: str
    search_space: SearchSpace
    metric: str
    config: TuneConfig
    message: str

class DeploymentResponse(TypedDict):
    """Response from model deployment."""
    status: Literal["deployment_started"]
    deployment_name: str
    model_path: str
    num_replicas: int
    config: DeploymentConfig
    message: str

class DatasetResponse(TypedDict):
    """Response from dataset creation."""
    status: Literal["dataset_created"]
    source: str
    format: DataFormat
    info: DatasetInfo
    message: str

class BackupResponse(TypedDict):
    """Response from cluster backup."""
    status: Literal["backup_created"]
    backup_path: str
    timestamp: float
    message: str

# Union type for all possible responses
Response = Union[
    SuccessResponse,
    ErrorResponse,
    ClusterStartResponse,
    JobSubmissionResponse,
    TrainingResponse,
    TuningResponse,
    DeploymentResponse,
    DatasetResponse,
    BackupResponse
]

# ===== UNION RESPONSE TYPES =====

RayManagerResponse = Union[
    SuccessResponse,
    ErrorResponse,
    ClusterStartResponse,
    JobSubmissionResponse,
    TrainingResponse,
    TuningResponse,
    DeploymentResponse,
    DatasetResponse,
    BackupResponse,
    JsonDict  # For complex responses that don't fit standard patterns
]

# ===== PROTOCOL TYPES =====

class JobClient(Protocol):
    """Protocol for Ray job submission client."""
    def submit_job(
        self,
        entrypoint: str,
        runtime_env: Optional[JsonDict] = None,
        job_id: Optional[JobId] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> JobId: ...
    
    def get_job_info(self, job_id: JobId) -> JobInfo: ...
    def get_job_logs(self, job_id: JobId) -> str: ...
    def stop_job(self, job_id: JobId) -> bool: ...
    def list_jobs(self) -> List[JobInfo]: ...

# ===== KWARGS TYPES =====

# Specific kwargs types for different operations
ClusterKwargs = Dict[str, Union[str, int, bool, ResourceDict]]
JobKwargs = Dict[str, Union[str, int, JsonDict, Dict[str, str]]]
MLKwargs = Dict[str, Union[str, int, float, bool, ModelConfig, SearchSpace]]
DataKwargs = Dict[str, Union[str, int, DataFormat, JsonDict]]
WorkflowKwargs = Dict[str, Union[str, WorkflowDefinition, JsonDict]] 