"""Kubernetes Custom Resource Definition operations and managers."""

from .base_crd_manager import BaseCRDManager
from .crd_operations import CRDOperationsClient
from .ray_cluster_crd import RayClusterCRDManager
from .ray_job_crd import RayJobCRDManager

# Export the CRDOperations interface from the operations client
CRDOperations = CRDOperationsClient

__all__ = [
    "BaseCRDManager",
    "CRDOperationsClient",
    "CRDOperations",
    "RayClusterCRDManager",
    "RayJobCRDManager",
]
