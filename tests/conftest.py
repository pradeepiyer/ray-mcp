"""Pytest configuration and fixtures for Ray MCP tests."""

import os
from unittest.mock import Mock, patch

import pytest

from tests.test_utils import run_ray_cleanup, wait_for_ray_shutdown


def pytest_configure(config):
    """Configure pytest with custom markers."""
    # Disable Ray usage reporting to avoid network calls during tests
    os.environ.setdefault("RAY_USAGE_STATS_ENABLED", "0")
    config.addinivalue_line("markers", "e2e: mark test as end-to-end integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "fast: mark test as fast running")
    config.addinivalue_line("markers", "smoke: mark test as smoke test")


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
