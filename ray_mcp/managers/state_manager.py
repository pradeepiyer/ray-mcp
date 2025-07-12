"""Centralized state management for Ray MCP components.

This module provides thread-safe state management for all Ray MCP components,
ensuring consistency across cluster, job, and configuration operations.
"""

import asyncio
import threading
import time
from typing import Any, Dict, Optional, Union

from ..foundation.logging_utils import LoggingUtility

# Import Ray modules with error handling
try:
    import ray

    RAY_AVAILABLE = True
except ImportError:
    RAY_AVAILABLE = False
    ray = None


class StateManager:
    """Manages Ray cluster state with thread-safe operations and validation."""

    def __init__(self, validation_interval: float = 1.0):
        self._state = {
            "initialized": False,
            "cluster_address": None,
            "gcs_address": None,
            "dashboard_url": None,
            "job_client": None,
            "connection_type": None,  # "new" or "existing"
            "last_validated": 0.0,
        }
        self._lock = threading.Lock()
        self._validation_interval = validation_interval
        self._validating = False  # Prevent concurrent validations

    def get_state(self) -> Dict[str, Any]:
        """Get current state with validation."""
        with self._lock:
            if self._should_validate():
                self._validating = True
                try:
                    self._validate_and_update_state()
                finally:
                    self._validating = False
            return self._state.copy()

    def _should_validate(self) -> bool:
        """Check if validation should be performed."""
        if self._validating:
            return False

        current_time = time.time()
        if (current_time - self._state["last_validated"]) <= self._validation_interval:
            return False

        return self._state["cluster_address"] is not None or self._state["initialized"]

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
                "connection_type": None,  # "new" or "existing"
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
            # Only update last_validated if validation completed successfully
            self._state["last_validated"] = time.time()

            if not is_valid:
                # Clear invalid state only when validation succeeds but cluster is invalid
                self._state.update(
                    {
                        "cluster_address": None,
                        "gcs_address": None,
                        "dashboard_url": None,
                        "job_client": None,
                        "connection_type": None,
                    }
                )
        except Exception as e:
            LoggingUtility.log_error(
                "state_validation", Exception(f"State validation failed: {e}")
            )
            self._state["initialized"] = False
            # Don't update last_validated on exception - allow retry on next validation cycle
            # Don't clear cluster_address on exception - keep it for retry attempts

    def _validate_ray_state(self) -> bool:
        """Validate the actual Ray state against internal state."""
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
            LoggingUtility.log_warning(
                "ray_state", f"Failed to validate Ray runtime context: {e}"
            )
            return False

        return True
