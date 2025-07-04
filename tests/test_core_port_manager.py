"""Unit tests for RayPortManager component.

Tests focus on port allocation behavior with 100% mocking.
"""

from unittest.mock import Mock, mock_open, patch

import pytest

from ray_mcp.core.port_manager import RayPortManager


@pytest.mark.fast
class TestRayPortManagerCore:
    """Test core port allocation functionality."""

    def test_manager_instantiation(self):
        """Test that port manager can be instantiated."""
        manager = RayPortManager()
        assert manager is not None

    @patch("ray_mcp.core.port_manager.socket.socket")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ray_mcp.core.port_manager.fcntl.flock")
    async def test_find_free_port_success(self, mock_flock, mock_file, mock_socket):
        """Test successful port allocation."""
        # Mock empty lock file content (no existing lock)
        mock_file.return_value.read.return_value = ""

        # Mock socket binding success
        mock_sock_instance = Mock()
        mock_socket.return_value.__enter__.return_value = mock_sock_instance

        manager = RayPortManager()
        port = await manager.find_free_port(start_port=10001, max_tries=5)

        assert port == 10001
        mock_socket.assert_called()
        mock_sock_instance.bind.assert_called_with(("", 10001))

    @patch("ray_mcp.core.port_manager.socket.socket")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ray_mcp.core.port_manager.fcntl.flock")
    async def test_find_free_port_multiple_attempts(
        self, mock_flock, mock_file, mock_socket
    ):
        """Test port allocation when first ports are occupied by socket binding failures."""
        # Mock empty lock file content (no existing locks)
        mock_file.return_value.read.return_value = ""

        # Mock socket to fail on first two attempts, succeed on third
        mock_sock_instance = Mock()
        mock_socket.return_value.__enter__.return_value = mock_sock_instance
        mock_sock_instance.bind.side_effect = [
            OSError("Port in use"),
            OSError("Port in use"),
            None,
        ]

        manager = RayPortManager()
        port = await manager.find_free_port(start_port=10001, max_tries=5)

        assert port == 10003  # Should succeed on third attempt

    @patch("ray_mcp.core.port_manager.socket.socket")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ray_mcp.core.port_manager.fcntl.flock")
    async def test_find_free_port_exhausted_attempts(
        self, mock_flock, mock_file, mock_socket
    ):
        """Test port allocation failure when all attempts are exhausted."""
        # Mock empty lock file content (no existing locks)
        mock_file.return_value.read.return_value = ""

        # Mock all socket bind attempts to fail
        mock_sock_instance = Mock()
        mock_socket.return_value.__enter__.return_value = mock_sock_instance
        mock_sock_instance.bind.side_effect = OSError("Port in use")

        manager = RayPortManager()

        with pytest.raises(RuntimeError, match="No free port found in range"):
            await manager.find_free_port(start_port=10001, max_tries=3)

    @pytest.mark.parametrize(
        "start_port,max_tries,expected_range",
        [
            (10001, 5, "10001-10005"),
            (8000, 10, "8000-8009"),
            (50000, 2, "50000-50001"),
        ],
    )
    @patch("ray_mcp.core.port_manager.socket.socket")
    async def test_find_free_port_range_parameters(
        self, mock_socket, start_port, max_tries, expected_range
    ):
        """Test port allocation with different range parameters."""
        # Mock all attempts to fail to test the error message
        mock_sock_instance = Mock()
        mock_socket.return_value.__enter__.return_value = mock_sock_instance
        mock_sock_instance.bind.side_effect = OSError("Port in use")

        manager = RayPortManager()

        with pytest.raises(RuntimeError) as exc_info:
            await manager.find_free_port(start_port=start_port, max_tries=max_tries)

        assert expected_range in str(exc_info.value)


@pytest.mark.fast
class TestRayPortManagerLockHandling:
    """Test file locking mechanisms for port allocation."""

    @patch("ray_mcp.core.port_manager.os.kill")
    @patch("builtins.open", new_callable=mock_open)
    async def test_stale_lock_file_removal(self, mock_file, mock_kill):
        """Test that stale lock files are handled correctly during allocation."""
        # Mock lock file content with dead PID
        mock_file.return_value.read.return_value = "99999,1234567890"

        # Mock process doesn't exist (OSError from os.kill)
        mock_kill.side_effect = OSError("No such process")

        manager = RayPortManager()

        # This should detect stale lock content and proceed with allocation
        with patch("ray_mcp.core.port_manager.socket.socket") as mock_socket:
            with patch("ray_mcp.core.port_manager.fcntl.flock"):
                mock_sock_instance = Mock()
                mock_socket.return_value.__enter__.return_value = mock_sock_instance

                # Should proceed to try binding after detecting stale lock
                port = await manager.find_free_port(start_port=10001, max_tries=1)
                assert port == 10001

        # Verify we attempted to bind to the port
        mock_sock_instance.bind.assert_called_with(("", 10001))

    @patch("ray_mcp.core.port_manager.fcntl.flock")
    @patch("builtins.open", new_callable=mock_open)
    async def test_lock_acquisition_failure(self, mock_file, mock_flock):
        """Test handling when lock acquisition fails."""
        # Mock lock acquisition failure
        mock_flock.side_effect = OSError("Resource temporarily unavailable")

        manager = RayPortManager()

        # Should fail to get port due to lock contention
        with pytest.raises(RuntimeError):
            await manager.find_free_port(start_port=10001, max_tries=1)

    @patch("ray_mcp.core.port_manager.os.kill")
    @patch("ray_mcp.core.port_manager.os.getpid")
    @patch("ray_mcp.core.port_manager.time.time")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ray_mcp.core.port_manager.fcntl.flock")
    async def test_race_condition_active_lock_respected(
        self, mock_flock, mock_file, mock_time, mock_getpid, mock_kill
    ):
        """Test race condition fix: active locks from other processes are respected."""
        mock_time.return_value = 1234567890
        mock_getpid.return_value = 12345
        mock_kill.return_value = None  # Process exists

        # Mock lock file with active lock from different process
        mock_file.return_value.read.return_value = "99999,1234567850"

        manager = RayPortManager()

        # Should detect active lock and move to next port
        with patch("ray_mcp.core.port_manager.socket.socket") as mock_socket:
            mock_sock_instance = Mock()
            mock_socket.return_value.__enter__.return_value = mock_sock_instance

            # First call has active lock, second call succeeds
            mock_file.return_value.read.side_effect = ["99999,1234567850", ""]

            port = await manager.find_free_port(start_port=10001, max_tries=2)
            assert port == 10002

    @patch("ray_mcp.core.port_manager.os.getpid")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ray_mcp.core.port_manager.fcntl.flock")
    async def test_race_condition_own_process_ignored(
        self, mock_flock, mock_file, mock_getpid
    ):
        """Test race condition fix: locks from same process are ignored."""
        our_pid = 12345
        mock_getpid.return_value = our_pid

        # Mock lock file with our own PID
        mock_file.return_value.read.return_value = f"{our_pid},1234567850"

        manager = RayPortManager()

        # Should ignore our own lock and proceed
        with patch("ray_mcp.core.port_manager.socket.socket") as mock_socket:
            mock_sock_instance = Mock()
            mock_socket.return_value.__enter__.return_value = mock_sock_instance

            port = await manager.find_free_port(start_port=10001, max_tries=1)
            assert port == 10001
            mock_sock_instance.bind.assert_called_with(("", 10001))


@pytest.mark.fast
class TestRayPortManagerCleanup:
    """Test port cleanup functionality."""

    @patch("ray_mcp.core.port_manager.os.path.exists")
    @patch("ray_mcp.core.port_manager.os.unlink")
    @patch("ray_mcp.core.port_manager.tempfile.gettempdir")
    def test_cleanup_port_lock_success(self, mock_tempdir, mock_unlink, mock_exists):
        """Test successful cleanup of port lock file."""
        mock_tempdir.return_value = "/tmp"
        mock_exists.return_value = True

        manager = RayPortManager()
        manager.cleanup_port_lock(10001)

        mock_unlink.assert_called_with("/tmp/ray_port_10001.lock")

    @patch("ray_mcp.core.port_manager.os.path.exists")
    @patch("ray_mcp.core.port_manager.os.unlink")
    @patch("ray_mcp.core.port_manager.tempfile.gettempdir")
    def test_cleanup_port_lock_file_not_exists(
        self, mock_tempdir, mock_unlink, mock_exists
    ):
        """Test cleanup when lock file doesn't exist."""
        mock_tempdir.return_value = "/tmp"
        mock_exists.return_value = False

        manager = RayPortManager()
        manager.cleanup_port_lock(10001)

        mock_unlink.assert_not_called()

    @patch("ray_mcp.core.port_manager.os.path.exists")
    @patch("ray_mcp.core.port_manager.os.unlink")
    @patch("ray_mcp.core.port_manager.tempfile.gettempdir")
    @patch("ray_mcp.core.port_manager.LoggingUtility")
    def test_cleanup_port_lock_error_handling(
        self, mock_logging, mock_tempdir, mock_unlink, mock_exists
    ):
        """Test error handling during lock file cleanup."""
        mock_tempdir.return_value = "/tmp"
        mock_exists.return_value = True
        mock_unlink.side_effect = OSError("Permission denied")

        manager = RayPortManager()
        manager.cleanup_port_lock(10001)

        mock_logging.log_warning.assert_called()

    @patch("ray_mcp.core.port_manager.tempfile.gettempdir")
    def test_temp_dir_fallback(self, mock_tempdir):
        """Test fallback when temp directory is not accessible."""
        mock_tempdir.side_effect = OSError("Temp dir not accessible")

        manager = RayPortManager()
        temp_dir = manager._get_temp_dir()

        assert temp_dir == "."

    @patch("ray_mcp.core.port_manager.os.listdir")
    @patch("ray_mcp.core.port_manager.os.kill")
    @patch("ray_mcp.core.port_manager.os.unlink")
    @patch("builtins.open", new_callable=mock_open)
    def test_cleanup_stale_lock_files(
        self, mock_file, mock_unlink, mock_kill, mock_listdir
    ):
        """Test cleanup of multiple stale lock files."""
        # Mock directory listing with ray port lock files
        mock_listdir.return_value = [
            "ray_port_10001.lock",
            "ray_port_10002.lock",
            "other_file.txt",
            "ray_port_10003.lock",
        ]

        # Mock lock file contents with dead processes
        mock_file.return_value.read.return_value = "99999,1234567890"
        mock_kill.side_effect = OSError("No such process")

        manager = RayPortManager()
        manager._cleanup_stale_lock_files()

        # Should attempt to remove stale lock files
        assert mock_unlink.call_count == 3  # Three ray_port_*.lock files


@pytest.mark.fast
class TestRayPortManagerErrorScenarios:
    """Test error handling and edge cases."""

    @patch("ray_mcp.core.port_manager.tempfile.gettempdir")
    @patch("ray_mcp.core.port_manager.LoggingUtility")
    def test_temp_dir_error_handling(self, mock_logging, mock_tempdir):
        """Test handling of temp directory errors."""
        mock_tempdir.side_effect = OSError("Temp dir error")

        manager = RayPortManager()

        # Should fallback gracefully
        temp_dir = manager._get_temp_dir()
        assert temp_dir == "."

    @patch("ray_mcp.core.port_manager.os.listdir")
    @patch("ray_mcp.core.port_manager.LoggingUtility")
    def test_cleanup_stale_files_error_handling(self, mock_logging, mock_listdir):
        """Test error handling during stale file cleanup."""
        mock_listdir.side_effect = OSError("Permission denied")

        manager = RayPortManager()
        manager._cleanup_stale_lock_files()

        mock_logging.log_warning.assert_called()

    @patch("ray_mcp.core.port_manager.socket.socket")
    @patch("ray_mcp.core.port_manager.LoggingUtility")
    async def test_socket_error_handling(self, mock_logging, mock_socket):
        """Test handling of socket operation errors."""
        mock_socket.side_effect = OSError("Socket error")

        manager = RayPortManager()

        with pytest.raises(RuntimeError):
            await manager.find_free_port(start_port=10001, max_tries=1)
