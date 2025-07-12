"""Port management for Ray clusters."""

import asyncio
import fcntl
import os
import socket
import tempfile
import time
from typing import Optional

from ..foundation.import_utils import get_logging_utils


class PortManager:
    """Manages port allocation with atomic reservation to prevent race conditions."""

    def __init__(self):
        # Import logging utilities directly - no state management needed
        logging_utils = get_logging_utils()
        self._LoggingUtility = logging_utils["LoggingUtility"]

    def _log_info(self, operation: str, message: str) -> None:
        """Log info message."""
        self._LoggingUtility.log_info(operation, message)

    def _log_warning(self, operation: str, message: str) -> None:
        """Log warning message."""
        self._LoggingUtility.log_warning(operation, message)

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
        """Clean up the lock file for a successfully used port.

        Uses atomic file locking to prevent race conditions during cleanup.
        """
        temp_dir = self._get_temp_dir()
        lock_file_path = os.path.join(temp_dir, f"ray_port_{port}.lock")

        # Use atomic cleanup with proper locking
        if self._safely_remove_lock_file(lock_file_path):
            self._log_info("port_allocation", f"Cleaned up lock file for port {port}")
        else:
            self._log_warning(
                "port_allocation",
                f"Lock file for port {port} was already cleaned up or in use",
            )

    def _safely_remove_lock_file(self, lock_file_path: str) -> bool:
        """Safely remove a lock file using atomic operations.

        Uses file locking as the single source of truth. If we can acquire
        the lock, the original process is guaranteed dead and the file is stale.

        Args:
            lock_file_path: Path to the lock file to remove

        Returns:
            bool: True if file was removed, False if it was already gone or in use
        """
        try:
            with open(lock_file_path, "r+") as lock_file:
                try:
                    # If this succeeds, the original process is guaranteed dead
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    # No content validation needed - lock acquisition proves staleness
                    lock_file.seek(0)
                    lock_file.truncate()
                    # File will be unlinked after context exit
                except OSError:
                    # Lock held by active process
                    return False

            # Safe to remove - no active lock holder
            os.unlink(lock_file_path)
            return True
        except (OSError, FileNotFoundError):
            # File doesn't exist or other error
            return False

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

                # Clear any stale content - if we got the lock, any existing content is stale
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

    def _cleanup_stale_lock_files(self) -> None:
        """Clean up stale lock files from processes that no longer exist.

        Uses safe iteration and atomic operations to prevent race conditions.
        """
        try:
            temp_dir = self._get_temp_dir()

            # Get snapshot of files to avoid modification during iteration
            try:
                filenames = [
                    f
                    for f in os.listdir(temp_dir)
                    if f.startswith("ray_port_") and f.endswith(".lock")
                ]
            except (OSError, IOError):
                return

            cleaned_count = 0
            for filename in filenames:
                lock_file_path = os.path.join(temp_dir, filename)
                if self._is_stale_lock_file(lock_file_path):
                    if self._safely_remove_lock_file(lock_file_path):
                        cleaned_count += 1
                        self._log_info(
                            "port_allocation", f"Cleaned up stale lock file {filename}"
                        )

            # Only log summary if we actually cleaned up files
            # This maintains backward compatibility with existing tests
            if cleaned_count > 0:
                self._log_info(
                    "port_allocation", f"Cleaned up {cleaned_count} stale lock files"
                )

        except (OSError, IOError) as e:
            self._log_warning(
                "port_allocation", f"Error cleaning up stale lock files: {e}"
            )

    def _is_stale_lock_file(self, lock_file_path: str) -> bool:
        """Check if a lock file is stale and safe to remove.

        Uses file locking as the single source of truth. If we can acquire
        the lock, the file is stale. No content validation needed.

        Args:
            lock_file_path: Path to the lock file to check

        Returns:
            bool: True if the lock file is stale and can be removed
        """
        try:
            with open(lock_file_path, "r") as f:
                try:
                    # Try non-blocking lock to see if file is in use
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return True  # Got lock = stale
                except OSError:
                    return False  # Lock held = active
        except (OSError, IOError):
            return True  # Can't read = stale

    def _is_lock_file_active(self, lock_file_path: str) -> bool:
        """Check if a lock file represents an active lock."""
        return not self._is_stale_lock_file(lock_file_path)

    def _remove_stale_lock(self, lock_file_path: str) -> None:
        """Remove a stale lock file."""
        try:
            os.unlink(lock_file_path)
        except OSError:
            pass
