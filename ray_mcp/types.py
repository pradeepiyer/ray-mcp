"""Type definitions for the Ray MCP server."""

from enum import Enum
import time
from typing import Any, Dict, List, Literal, Optional, Protocol, TypedDict, Union

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
    BackupResponse,
]

# ===== UNION RESPONSE TYPES =====

RayManagerResponse = Union[
    SuccessResponse,
    ErrorResponse,
    ClusterStartResponse,
    JobSubmissionResponse,
    BackupResponse,
    JsonDict,  # For complex responses that don't fit standard patterns
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
