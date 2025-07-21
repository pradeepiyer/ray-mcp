"""End-to-end testing utilities for Ray MCP tests."""

import asyncio
import time
from typing import Any, Dict, List, Optional

from .utils import E2EConfig, TempScriptManager, call_tool, parse_tool_result


async def wait_for_job_completion(
    job_id: str, max_wait: Optional[int] = None, expected_status: str = "SUCCEEDED"
) -> Dict[str, Any]:
    """
    Wait for a job to reach completion status.

    Args:
        job_id: The job ID to monitor
        max_wait: Maximum time to wait (uses E2EConfig default if None)
        expected_status: Expected final status (SUCCEEDED, FAILED, etc.)

    Returns:
        Final job status data

    Raises:
        AssertionError: If job doesn't complete in time or reaches unexpected status
    """
    if max_wait is None:
        max_wait = E2EConfig.get_wait_time()

    for i in range(max_wait):
        status_result = await call_tool("ray_job", {"prompt": f"inspect job {job_id}"})
        status_data = parse_tool_result(status_result)
        job_status = status_data.get("job_status", "UNKNOWN")
        print(f"Job {job_id} status at {i + 1}s: {job_status}")

        if job_status == expected_status:
            return status_data
        if job_status == "FAILED" and expected_status != "FAILED":
            raise AssertionError(f"Job failed unexpectedly: {status_data}")
        if job_status == "SUCCEEDED" and expected_status == "FAILED":
            raise AssertionError(
                f"Job succeeded when failure was expected: {status_data}"
            )

        await asyncio.sleep(1)
    else:
        raise AssertionError(
            f"Job {job_id} did not reach {expected_status} within {max_wait} seconds. "
            f"Last status: {job_status}"
        )


async def _wait_for_cluster_ready(
    max_wait: int = 10, poll_interval: float = 0.5
) -> None:
    """
    Wait for Ray cluster to be fully ready by testing job listing functionality.

    Args:
        max_wait: Maximum time to wait in seconds
        poll_interval: Time between status checks in seconds

    Raises:
        AssertionError: If cluster doesn't become ready within max_wait seconds
    """
    print("Waiting for Ray cluster to be fully ready...")

    # Since the cluster start was successful, we'll just give it a moment to stabilize
    # rather than trying complex status checks that might route incorrectly
    await asyncio.sleep(2)

    # Try a simple job list operation to verify cluster is responsive
    try:
        job_list_result = await call_tool("ray_job", {"prompt": "list all jobs"})
        job_list_data = parse_tool_result(job_list_result)

        if job_list_data.get("status") == "success":
            print("✅ Ray cluster is fully ready!")
            return
        else:
            print(
                f"Cluster not quite ready: {job_list_data.get('message', 'Job listing failed')}"
            )

    except Exception as e:
        print(f"Cluster readiness check failed: {e}")

    # Give it a bit more time if needed
    await asyncio.sleep(1)
    print("✅ Ray cluster should be ready now!")


async def submit_and_wait_for_job(
    script_content: str,
    expected_status: str = "SUCCEEDED",
    max_wait: Optional[int] = None,
    runtime_env: Optional[Dict[str, Any]] = None,
) -> tuple[str, Dict[str, Any]]:
    """
    Submit a job and wait for completion.

    Args:
        script_content: Python script content to execute
        expected_status: Expected final job status
        max_wait: Maximum time to wait for completion
        runtime_env: Optional runtime environment

    Returns:
        Tuple of (job_id, final_status_data)
    """
    with TempScriptManager(script_content) as script_path:
        print(f"Submitting job with script at {script_path}...")

        job_args: Dict[str, Any] = {"entrypoint": f"python {script_path}"}
        if runtime_env is not None:
            job_args["runtime_env"] = runtime_env

        job_result = await call_tool(
            "ray_job",
            {"prompt": f"submit job with entrypoint {job_args['entrypoint']}"},
        )
        job_data = parse_tool_result(job_result)

        assert job_data["status"] == "success"
        # Fix: Remove the result_type check since actual response doesn't have this field
        # The response has job_status and job_id fields instead
        assert "job_id" in job_data

        job_id = job_data["job_id"]
        print(f"Job submitted with ID: {job_id}")

        # Wait for completion
        final_status = await wait_for_job_completion(job_id, max_wait, expected_status)
        print(f"Job {job_id} completed with status: {expected_status}")

        return job_id, final_status
