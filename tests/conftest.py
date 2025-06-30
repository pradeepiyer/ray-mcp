"""Pytest configuration and fixtures for Ray MCP tests."""

import os
from pathlib import Path
import subprocess
import time
from typing import Optional
from unittest.mock import Mock, patch

import pytest


def pytest_configure(config):
    """Configure pytest with custom markers."""
    # Disable Ray usage reporting to avoid network calls during tests
    os.environ.setdefault("RAY_USAGE_STATS_ENABLED", "0")
    config.addinivalue_line("markers", "e2e: mark test as end-to-end integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "fast: mark test as fast running")
    config.addinivalue_line("markers", "smoke: mark test as smoke test")


def run_ray_cleanup(verbose: bool = True) -> bool:
    """
    Run the ray_cleanup.sh script.

    Args:
        verbose: Whether to print cleanup messages

    Returns:
        True if cleanup was successful, False otherwise
    """
    cleanup_script = Path(__file__).parent.parent / "scripts" / "ray_cleanup.sh"

    if not cleanup_script.exists():
        if verbose:
            print("⚠️  Ray cleanup script not found")
        return False

    try:
        if verbose:
            print("🧹 Running ray_cleanup.sh...")

        result = subprocess.run(
            [str(cleanup_script)], check=True, capture_output=True, text=True
        )

        if verbose:
            print("✅ Ray cleanup completed successfully")
            if result.stdout:
                print(f"Cleanup output: {result.stdout}")

        return True

    except subprocess.CalledProcessError as e:
        if verbose:
            print(f"⚠️  Ray cleanup failed: {e}")
            if e.stdout:
                print(f"stdout: {e.stdout}")
            if e.stderr:
                print(f"stderr: {e.stderr}")
        return False


def wait_for_ray_shutdown(timeout: int = 30) -> bool:
    """
    Wait for Ray to fully shutdown.

    Args:
        timeout: Maximum time to wait in seconds

    Returns:
        True if Ray shutdown successfully, False if timeout
    """
    try:
        import ray
    except ImportError:
        # Ray not available, consider it shutdown
        return True

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            if not ray.is_initialized():
                return True
            time.sleep(1)
        except Exception:
            # Ray might be in an inconsistent state, continue waiting
            time.sleep(1)

    return False


def ensure_clean_ray_state():
    """
    Ensure Ray is in a clean state by running cleanup and waiting for shutdown.
    """
    run_ray_cleanup()
    wait_for_ray_shutdown()


@pytest.fixture(scope="function", autouse=True)
def cleanup_ray_between_e2e_tests(request):
    """Automatically run ray_cleanup.sh between e2e tests."""
    # Only run cleanup for e2e tests
    if "e2e" in request.keywords:
        print(f"\n🧹 Running cleanup before e2e test: {request.node.name}")

        # Run cleanup before the test
        cleanup_success = run_ray_cleanup(verbose=True)
        if not cleanup_success:
            print("⚠️  Warning: Ray cleanup failed before test")

        # Wait for Ray to fully shutdown
        if wait_for_ray_shutdown(timeout=10):
            print("✅ Ray shutdown confirmed")
        else:
            print("⚠️  Warning: Ray may not have fully shutdown")

        yield

        print(f"\n🧹 Running cleanup after e2e test: {request.node.name}")

        # Run cleanup after the test
        cleanup_success = run_ray_cleanup(verbose=True)
        if not cleanup_success:
            print("⚠️  Warning: Ray cleanup failed after test")

        # Wait for Ray to fully shutdown
        if wait_for_ray_shutdown(timeout=10):
            print("✅ Ray shutdown confirmed")
        else:
            print("⚠️  Warning: Ray may not have fully shutdown")
    else:
        yield


@pytest.fixture
def mock_cluster_startup():
    """Mock cluster startup operations to speed up tests."""
    with patch("asyncio.sleep") as mock_sleep:
        with patch("subprocess.Popen.communicate") as mock_communicate:
            mock_communicate.return_value = (
                "Ray runtime started\n--address='127.0.0.1:10001'\nView the Ray dashboard at http://127.0.0.1:8265",
                "",
            )
            yield


@pytest.fixture
def mock_ray_available():
    """Mock Ray as available for tests."""
    with patch("ray_mcp.ray_manager.RAY_AVAILABLE", True):
        yield


@pytest.fixture
def mock_ray_module():
    """Mock the ray module with common behaviors."""
    with patch("ray_mcp.ray_manager.ray") as mock_ray:
        mock_ray.is_initialized.return_value = False
        mock_ray.init.return_value = Mock(
            address_info={"address": "127.0.0.1:10001"},
            dashboard_url="http://127.0.0.1:8265",
        )
        mock_ray.get_runtime_context.return_value.get_node_id.return_value = "node_123"
        yield mock_ray
