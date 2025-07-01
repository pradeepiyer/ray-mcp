"""Ray cluster state management."""

import threading
import time
from typing import Any, Dict

try:
    from ..logging_utils import LoggingUtility
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from logging_utils import LoggingUtility
from .interfaces import StateManager

# Import Ray modules with error handling
try:
    import ray
    RAY_AVAILABLE = True
except ImportError:
    RAY_AVAILABLE = False
    ray = None


class RayStateManager(StateManager):
    """Manages Ray cluster state with thread-safe operations and validation."""
    
    def __init__(self, validation_interval: float = 1.0):
        self._state = {
            "initialized": False,
            "cluster_address": None,
            "gcs_address": None,
            "dashboard_url": None,
            "job_client": None,
            "last_validated": 0.0,
        }
        self._lock = threading.Lock()
        self._validation_interval = validation_interval
        self._validating = False  # Prevent concurrent validations
    
    def get_state(self) -> Dict[str, Any]:
        """Get current state with validation."""
        with self._lock:
            current_time = time.time()
            # Only validate if not currently validating and enough time has passed
            if (
                not self._validating
                and (current_time - self._state["last_validated"]) > self._validation_interval
                and (self._state["cluster_address"] is not None or self._state["initialized"])
            ):
                self._validating = True
                try:
                    self._validate_and_update_state()
                finally:
                    self._validating = False
            return self._state.copy()
    
    def update_state(self, **kwargs) -> None:
        """Update state atomically."""
        with self._lock:
            self._state.update(kwargs)
            # Only update last_validated if we're not resetting
            if "initialized" not in kwargs or kwargs["initialized"]:
                self._state["last_validated"] = time.time()
    
    def reset_state(self) -> None:
        """Reset state to initial values."""
        with self._lock:
            self._state = {
                "initialized": False,
                "cluster_address": None,
                "gcs_address": None,
                "dashboard_url": None,
                "job_client": None,
                "last_validated": 0.0,
            }
    
    def is_initialized(self) -> bool:
        """Check if Ray is initialized with proper state validation."""
        return self.get_state()["initialized"]
    
    def _validate_and_update_state(self) -> None:
        """Validate and update state atomically."""
        try:
            is_valid = self._validate_ray_state()
            self._state["initialized"] = is_valid
            self._state["last_validated"] = time.time()
            
            if not is_valid:
                # Clear invalid state
                self._state.update({
                    "cluster_address": None,
                    "gcs_address": None,
                    "dashboard_url": None,
                    "job_client": None,
                })
        except Exception as e:
            LoggingUtility.log_error("state_validation", Exception(f"State validation failed: {e}"))
            self._state["initialized"] = False
    
    def _validate_ray_state(self) -> bool:
        """Validate the actual Ray state against internal state."""
        try:
            if not RAY_AVAILABLE or ray is None:
                return False
            
            if not ray.is_initialized():
                return False
            
            if not self._state.get("cluster_address"):
                return False
            
            # Verify cluster is still accessible
            try:
                runtime_context = ray.get_runtime_context()
                if not runtime_context:
                    return False
                
                node_id = runtime_context.get_node_id()
                if not node_id:
                    return False
            except Exception as e:
                LoggingUtility.log_warning("ray_state", f"Failed to validate Ray runtime context: {e}")
                return False
            
            return True
        except Exception as e:
            LoggingUtility.log_error("ray_state", Exception(f"Error validating Ray state: {e}"))
            return False 