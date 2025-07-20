"""Pytest configuration and fixtures for Ray MCP tests."""

import os

import pytest

# Import test utilities from helpers for backward compatibility
# This allows existing tests to continue importing from conftest
from tests.helpers import (
    E2EConfig,
    TempScriptManager,
    TestScripts,
    call_tool,
    e2e_ray_manager,
    get_text_content,
    parse_tool_result,
    run_ray_cleanup,
    submit_and_wait_for_job,
    wait_for_job_completion,
    wait_for_ray_shutdown,
)


def pytest_configure(config):
    """Configure pytest with custom markers."""
    # Disable Ray usage reporting to avoid network calls during tests
    os.environ.setdefault("RAY_USAGE_STATS_ENABLED", "0")
    config.addinivalue_line("markers", "e2e: mark test as end-to-end integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "fast: mark test as fast running")
    config.addinivalue_line("markers", "gke: mark test as requiring GKE cluster access")
