"""Port management for Ray clusters."""

import asyncio
import fcntl
import os
import socket
import tempfile
import time
from typing import Optional

from ..foundation.base_managers import BaseManager
from ..foundation.interfaces import PortManager


class RayPortManager(BaseManager, PortManager):
    """Manages port allocation with atomic reservation to prevent race conditions."""

    def __init__(self, state_manager=None):
        # Use a dummy state manager if none provided for backward compatibility
        if state_manager is None:
            from ..foundation.test_mocks import MockStateManager

            state_manager = MockStateManager()
        super().__init__(state_manager)

    async def find_free_port(self, start_port: int = 10001, max_tries: int = 50) -> int:
        """Find a free port with atomic reservation.

        Uses file locking to ensure only one process can reserve a port at a time,
        eliminating race conditions where multiple processes might try to use the same port.

        Args:
            start_port: Starting port number to check from
            max_tries: Maximum number of ports to try

        Returns:
            int: A free port number

        Raises:
            RuntimeError: If no free port is found in the given range
        """
        # Clean up any stale lock files before starting
        self._cleanup_stale_lock_files()

        port = start_port
        temp_dir = self._get_temp_dir()

        for attempt in range(max_tries):
            if await self._try_allocate_port(port, temp_dir):
                self._log_info("port_allocation", f"Successfully allocated port {port}")
                return port
            port += 1

        raise RuntimeError(
            f"No free port found in range {start_port}-{start_port + max_tries - 1}"
        )

    def cleanup_port_lock(self, port: int) -> None:
        """Clean up the lock file for a successfully used port."""
        try:
            temp_dir = self._get_temp_dir()
            lock_file_path = os.path.join(temp_dir, f"ray_port_{port}.lock")
            if os.path.exists(lock_file_path):
                os.unlink(lock_file_path)
                self._log_info(
                    "port_allocation", f"Cleaned up lock file for port {port}"
                )
        except (OSError, IOError) as e:
            self._log_warning(
                "port_allocation", f"Could not clean up lock file for port {port}: {e}"
            )

    def _get_temp_dir(self) -> str:
        """Get temp directory, fallback to current directory if not available."""
        try:
            return tempfile.gettempdir()
        except (OSError, IOError):
            return "."

    async def _try_allocate_port(self, port: int, temp_dir: str) -> bool:
        """Try to allocate a specific port with atomic file locking."""
        lock_file_path = os.path.join(temp_dir, f"ray_port_{port}.lock")

        # Try to acquire exclusive lock atomically
        try:
            with open(lock_file_path, "a+") as lock_file:
                # Acquire exclusive lock first (atomic operation)
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

                # Now that we have the lock, check if there's existing active content
                lock_file.seek(0)
                existing_content = lock_file.read().strip()

                if existing_content and self._is_content_active_lock(existing_content):
                    # Another process has an active lock, respect it
                    return False

                # Clear any stale content and try to bind to the port
                lock_file.seek(0)
                lock_file.truncate()

                # Try to bind to the port while holding the lock
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    try:
                        s.bind(("", port))
                        # Success! Write PID and timestamp to lock file
                        lock_file.write(f"{os.getpid()},{int(time.time())}\n")
                        lock_file.flush()
                        return True
                    except OSError:
                        # Port is in use by another service
                        return False
        except OSError:
            # Lock is held by another process or other error
            return False

    def _is_content_active_lock(self, content: str) -> bool:
        """Check if lock file content represents an active lock from another process."""
        if not content:
            return False

        try:
            if "," in content:
                pid_str, timestamp_str = content.split(",", 1)
                pid = int(pid_str)
                timestamp = int(timestamp_str)

                # Don't consider our own process as blocking
                if pid == os.getpid():
                    return False

                # Check if process still exists and lock is recent
                try:
                    os.kill(pid, 0)  # Check if process exists
                    return (
                        int(time.time()) - timestamp
                    ) < 300  # Less than 5 minutes old
                except OSError:
                    # Process doesn't exist
                    return False
            else:
                # Old format or invalid content, not an active lock
                return False
        except (ValueError, IndexError):
            return False

    def _cleanup_stale_lock_files(self) -> None:
        """Clean up stale lock files from processes that no longer exist."""
        try:
            temp_dir = self._get_temp_dir()

            for filename in os.listdir(temp_dir):
                if filename.startswith("ray_port_") and filename.endswith(".lock"):
                    lock_file_path = os.path.join(temp_dir, filename)
                    if not self._is_lock_file_active(lock_file_path):
                        self._remove_stale_lock(lock_file_path)
                        self._log_info(
                            "port_allocation", f"Cleaned up stale lock file {filename}"
                        )
        except (OSError, IOError) as e:
            self._log_warning(
                "port_allocation", f"Error cleaning up stale lock files: {e}"
            )

    def _is_lock_file_active(self, lock_file_path: str) -> bool:
        """Check if a lock file represents an active lock."""
        try:
            with open(lock_file_path, "r") as f:
                content = f.read().strip()
                return self._is_content_active_lock(content)
        except (OSError, IOError):
            return False

    def _remove_stale_lock(self, lock_file_path: str) -> None:
        """Remove a stale lock file."""
        try:
            os.unlink(lock_file_path)
        except OSError:
            pass
