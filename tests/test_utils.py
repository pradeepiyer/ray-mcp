"""Test utilities for Ray MCP tests."""

from pathlib import Path
import subprocess
import time
from typing import Optional


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
    import ray

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
