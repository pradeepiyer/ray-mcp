"""Type definitions for the Ray MCP server."""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union

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


class HealthReport(TypedDict):
    """Complete health report."""

    overall_status: HealthStatus
    health_score: float
    checks: Dict[str, bool]
    timestamp: float
    recommendations: List[str]


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
