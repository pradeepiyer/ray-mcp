"""Test fixtures for Ray MCP tests."""

import pytest


@pytest.fixture
def e2e_ray_manager():
    """Fixture to manage Ray cluster lifecycle for e2e testing."""
    # Use the same RayManager instance that the MCP tools use
    from ray_mcp.main import ray_manager

    # Ensure Ray is not already running
    try:
        import ray

        if ray.is_initialized():
            ray.shutdown()
    except ImportError:
        pass  # Ray not available

    yield ray_manager

    # Cleanup: Stop Ray if it's running
    try:
        import ray

        if ray.is_initialized():
            ray.shutdown()
    except Exception:
        pass  # Ignore cleanup errors
