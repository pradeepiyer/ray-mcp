"""Test fixtures for Ray MCP tests."""

import pytest


@pytest.fixture
def e2e_ray_manager():
    """Fixture to manage Kubernetes cluster lifecycle for e2e testing."""
    # Return the individual managers since ray_manager no longer exists
    from ray_mcp.main import cloud_provider_manager, job_manager, service_manager

    return {
        "job_manager": job_manager,
        "service_manager": service_manager,
        "cloud_manager": cloud_provider_manager,
    }
