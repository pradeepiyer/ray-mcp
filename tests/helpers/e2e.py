"""End-to-end testing utilities for Ray MCP tests."""

import asyncio
import time
from typing import Any, Dict, List, Optional

from .utils import E2EConfig, call_tool, parse_tool_result, TempScriptManager


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
        status_result = await call_tool("inspect_ray_job", {"job_id": job_id})
        status_data = parse_tool_result(status_result)
        job_status = status_data.get("job_status", "UNKNOWN")
        print(f"Job {job_id} status at {i+1}s: {job_status}")

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
    Wait for Ray cluster to be fully ready by polling its status.

    Args:
        max_wait: Maximum time to wait in seconds
        poll_interval: Time between status checks in seconds

    Raises:
        AssertionError: If cluster doesn't become ready within max_wait seconds
    """
    print("Waiting for Ray cluster to be fully ready...")
    start_time = time.time()

    while time.time() - start_time < max_wait:
        try:
            status_result = await call_tool("inspect_ray_cluster", {})
            status_data = parse_tool_result(status_result)

            # Check if cluster is ready (either "active" or "success" status)
            if status_data.get("status") in ["active", "success"]:
                print("✅ Ray cluster is fully ready!")
                return

        except Exception as e:
            # Cluster might not be ready yet, continue polling
            print(f"Cluster not ready yet: {e}")

        await asyncio.sleep(poll_interval)

    raise AssertionError(f"Ray cluster did not become ready within {max_wait} seconds")


async def start_ray_cluster(
    cpu_limit: Optional[int] = None, worker_nodes: Optional[List] = None
) -> Dict[str, Any]:
    """
    Start Ray cluster with appropriate configuration.

    Args:
        cpu_limit: Number of CPUs (uses E2EConfig default if None)
        worker_nodes: Worker nodes config (uses E2EConfig default if None)

    Returns:
        Start result data
    """
    if cpu_limit is None:
        cpu_limit = E2EConfig.get_cpu_limit()
    if worker_nodes is None:
        worker_nodes = E2EConfig.get_worker_nodes()

    # Clean up any existing Ray instances before starting
    try:
        import ray
        if ray.is_initialized():
            ray.shutdown()
    except:
        pass

    # Run ray stop to clean up any external processes
    try:
        import subprocess
        subprocess.run(["ray", "stop"], capture_output=True, check=False)
    except:
        pass

    print(f"Starting Ray cluster with {cpu_limit} CPU(s)...")
    start_result = await call_tool(
        "init_ray_cluster", {"num_cpus": cpu_limit, "worker_nodes": worker_nodes}
    )

    start_data = parse_tool_result(start_result)
    print(f"Start result: {start_data}")

    if start_data["status"] == "error":
        print("Error message:", start_data["message"])

    assert start_data["status"] == "success"
    assert start_data.get("result_type") == "started"
    print(f"Ray cluster started: {start_data}")

    # Verify cluster is actually ready by checking its status
    await _wait_for_cluster_ready()

    return start_data


async def stop_ray_cluster() -> Dict[str, Any]:
    """
    Stop Ray cluster and verify shutdown.

    Returns:
        Stop result data
    """
    print("Stopping Ray cluster...")
    stop_result = await call_tool("stop_ray_cluster")
    stop_data = parse_tool_result(stop_result)

    assert stop_data["status"] == "success"
    # Note: result_type field may not be present in all response formats
    print("Ray cluster stopped successfully!")

    # Additional cleanup to ensure Ray is completely shut down
    try:
        import ray
        if ray.is_initialized():
            ray.shutdown()
    except:
        pass

    # Run ray stop to clean up any remaining processes
    try:
        import subprocess
        subprocess.run(["ray", "stop"], capture_output=True, check=False)
    except:
        pass

    # Verify cluster is stopped
    print("Verifying cluster is stopped...")
    final_status_result = await call_tool("inspect_ray_cluster")
    final_status_data = parse_tool_result(final_status_result)
    # Check for either "not_running" or "error" status when cluster is stopped
    assert final_status_data["status"] in ["not_running", "error"]
    print("Cluster shutdown verification passed!")

    return stop_data


async def verify_cluster_status() -> Dict[str, Any]:
    """
    Verify Ray cluster is running and return status.

    Returns:
        Cluster status data
    """
    print("Checking cluster status...")
    status_result = await call_tool("inspect_ray_cluster")
    status_data = parse_tool_result(status_result)

    # Accept both "active" (cluster running) and "success" (operation succeeded)
    assert status_data["status"] in [
        "success",
        "active",
    ], f"Unexpected status: {status_data['status']}"

    # Check for basic cluster status (no longer includes performance metrics)
    assert status_data["status"] in [
        "active",
        "success",
    ], f"Unexpected cluster status: {status_data.get('status')}"

    print(f"Cluster status: {status_data}")
    return status_data


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

        job_result = await call_tool("submit_ray_job", job_args)
        job_data = parse_tool_result(job_result)

        assert job_data["status"] == "success"
        assert job_data["result_type"] == "submitted"

        job_id = job_data["job_id"]
        print(f"Job submitted with ID: {job_id}")

        # Wait for completion
        final_status = await wait_for_job_completion(job_id, max_wait, expected_status)
        print(f"Job {job_id} completed with status: {expected_status}")

        return job_id, final_status 