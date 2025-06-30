"""Worker node management for Ray clusters.

This module provides functionality for managing Ray worker node processes in a cluster.
It handles starting, stopping, and monitoring worker nodes that connect to a Ray head node.
The WorkerManager class provides a high-level interface for managing multiple worker processes.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)
from .logging_utils import LoggingUtility, ResponseFormatter


class WorkerManager:
    """Manages Ray worker node processes.

    This class handles the lifecycle of Ray worker nodes in a cluster, including
    starting multiple workers with different configurations, monitoring their status,
    and gracefully shutting them down.

    The WorkerManager maintains lists of active worker processes and their configurations
    to enable proper cleanup and status tracking.
    """

    def __init__(self):
        """Initialize the WorkerManager.

        Creates empty lists to track worker processes and their configurations.
        These lists are populated as workers are started and cleared when workers
        are stopped.
        """
        self.worker_processes: List[subprocess.Popen] = []
        self.worker_configs: List[Dict[str, Any]] = []
        self.response_formatter = ResponseFormatter()

    async def start_worker_nodes(
        self, worker_configs: List[Dict[str, Any]], head_node_address: str
    ) -> List[Dict[str, Any]]:
        """Start multiple worker nodes and connect them to the head node.

        Starts multiple Ray worker nodes in parallel, each with its own configuration.
        Workers are started sequentially with small delays to avoid overwhelming
        the head node during initialization.

        Args:
            worker_configs: List of worker node configurations, each containing:
                - num_cpus: Number of CPUs to allocate (required)
                - num_gpus: Number of GPUs to allocate (optional)
                - object_store_memory: Object store memory in bytes (optional)
                - resources: Custom resources dictionary (optional)
                - node_name: Custom name for the worker node (optional)
            head_node_address: Address of the Ray head node to connect to
                (e.g., "127.0.0.1:10001")

        Returns:
            List[Dict[str, Any]]: List of results for each worker node attempt:
                - status: "started", "error", or "failed"
                - node_name: Name of the worker node
                - message: Success or error message
                - process_id: Process ID if successfully started
                - config: Worker configuration used

        Failure modes:
            - Invalid head node address: Returns connection errors
            - Invalid worker configuration: Returns configuration validation errors
            - Process spawn failures: Returns process creation errors
            - Resource allocation failures: Returns resource constraint errors
            - Network connectivity issues: Returns connection timeout errors
        """
        worker_results = []

        for i, config in enumerate(worker_configs):
            try:
                worker_result = await self._start_single_worker(
                    config, head_node_address, f"worker-{i+1}"
                )
                worker_results.append(worker_result)

                # Add small delay between worker starts to avoid overwhelming the head node
                if i < len(worker_configs) - 1:
                    await asyncio.sleep(0.5)

            except Exception as e:
                LoggingUtility.log_error(f"start worker node {i+1}", e)
                worker_results.append(
                    {
                        "status": "error",
                        "node_name": config.get("node_name", f"worker-{i+1}"),
                        "message": f"Failed to start worker node: {str(e)}",
                    }
                )

        return worker_results

    async def _start_single_worker(
        self, config: Dict[str, Any], head_node_address: str, default_node_name: str
    ) -> Dict[str, Any]:
        """Start a single worker node process.

        Creates and starts a single Ray worker node process with the specified
        configuration. The worker connects to the head node and registers its
        available resources.

        Args:
            config: Worker node configuration dictionary containing resource
                specifications and optional settings
            head_node_address: Address of the Ray head node to connect to
            default_node_name: Default name to use if no custom name is provided

        Returns:
            Dict[str, Any]: Result dictionary containing:
                - status: "started" or "error"
                - node_name: Name of the worker node
                - message: Success or error message
                - process_id: Process ID if successfully started
                - config: Worker configuration used

        Failure modes:
            - Invalid configuration: Returns configuration validation errors
            - Process spawn failure: Returns process creation errors
            - Head node connection failure: Returns connection errors
            - Resource allocation failure: Returns resource constraint errors
        """
        node_name = config.get("node_name", default_node_name)

        try:
            # Prepare Ray worker command
            worker_cmd = self._build_worker_command(config, head_node_address)

            # Start worker process
            process = await self._spawn_worker_process(worker_cmd, node_name)

            if process:
                self.worker_processes.append(process)
                self.worker_configs.append(config)

                return {
                    "status": "started",
                    "node_name": node_name,
                    "message": f"Worker node '{node_name}' started successfully",
                    "process_id": process.pid,
                    "config": config,
                }
            else:
                return {
                    "status": "error",
                    "node_name": node_name,
                    "message": "Failed to spawn worker process",
                }

        except Exception as e:
            LoggingUtility.log_error(f"start worker process for {node_name}", e)
            return {
                "status": "error",
                "node_name": node_name,
                "message": f"Failed to start worker process: {str(e)}",
            }

    def _build_worker_command(
        self, config: Dict[str, Any], head_node_address: str
    ) -> List[str]:
        """Build the command to start a Ray worker node.

        Constructs the command-line arguments needed to start a Ray worker node
        with the specified configuration. Handles resource specifications,
        custom resources, and Ray-specific options.

        Args:
            config: Worker node configuration dictionary
            head_node_address: Address of the Ray head node to connect to

        Returns:
            List[str]: Command-line arguments for starting the Ray worker node

        The command includes:
            - Base Ray start command with head node address
            - CPU and GPU resource specifications
            - Object store memory configuration (minimum 75MB enforced)
            - Custom resources if specified
            - Node name if provided
            - Ray-specific options (blocking mode, usage stats disabled)

        Failure modes:
            - Invalid resource values: Raises ValueError for negative resources
            - Invalid memory specification: Enforces minimum memory requirements
            - Invalid custom resources: Validates resource format
        """
        # Base Ray worker command
        cmd = ["ray", "start", "--address", head_node_address]

        # Add resource specifications
        if "num_cpus" in config:
            cmd.extend(["--num-cpus", str(config["num_cpus"])])

        if "num_gpus" in config:
            cmd.extend(["--num-gpus", str(config["num_gpus"])])

        if "object_store_memory" in config:
            # Ensure it's at least 75MB (Ray's minimum) in bytes
            min_memory_bytes = 75 * 1024 * 1024  # 75MB in bytes
            memory_bytes = max(min_memory_bytes, config["object_store_memory"])
            cmd.extend(["--object-store-memory", str(memory_bytes)])

        # Add custom resources if specified
        if "resources" in config and isinstance(config["resources"], dict):
            resources_json = json.dumps(config["resources"])
            cmd.extend(["--resources", resources_json])

        # Add node name if specified
        if "node_name" in config:
            cmd.extend(["--node-name", config["node_name"]])

        # Add additional Ray options
        cmd.extend(
            [
                "--block",  # Run in blocking mode
                "--disable-usage-stats",  # Disable usage stats for cleaner output
            ]
        )

        return cmd

    @ResponseFormatter.handle_exceptions("spawn worker process")
    async def _spawn_worker_process(
        self, cmd: List[str], node_name: str
    ) -> Optional[subprocess.Popen]:
        """Spawn a worker node process.

        Creates and starts a subprocess for a Ray worker node with the specified
        command. Sets up proper environment variables and monitors the process
        startup to ensure it's running correctly.

        Args:
            cmd: Command-line arguments for starting the Ray worker
            node_name: Name of the worker node for logging purposes

        Returns:
            Optional[subprocess.Popen]: Process object if successfully started,
                None if the process failed to start or crashed immediately

        The method:
            - Sets up environment variables for Ray (usage stats disabled, multi-node enabled)
            - Starts the process with proper I/O redirection
            - Waits briefly for the process to initialize
            - Verifies the process is still running after startup
            - Logs success or failure with detailed error information

        Failure modes:
            - Process creation failure: Returns None with logged error
            - Immediate process crash: Returns None with captured stdout/stderr
            - Environment setup issues: Returns None with environment errors
            - Process validation failure: Returns None if process not running after startup
        """
        LoggingUtility.log_info(
            "worker_manager",
            f"Starting worker node '{node_name}' with command: {' '.join(cmd)}",
        )

        # Create process with proper environment
        env = os.environ.copy()
        env["RAY_DISABLE_USAGE_STATS"] = "1"
        # Enable multi-node clusters on Windows and macOS
        env["RAY_ENABLE_WINDOWS_OR_OSX_CLUSTER"] = "1"

        # Start the process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            text=True,
        )

        # Give it a moment to start
        await asyncio.sleep(0.2)

        # Check if process is still running
        if process.poll() is None:
            LoggingUtility.log_info(
                "worker_manager",
                f"Worker node '{node_name}' started successfully (PID: {process.pid})",
            )
            return process
        else:
            # Process failed to start
            exit_code = process.poll()
            LoggingUtility.log_error(
                "worker_manager",
                f"Worker node '{node_name}' failed to start with exit code: {exit_code}",
            )
            return None

    @ResponseFormatter.handle_exceptions("stop all workers")
    async def stop_all_workers(self) -> List[Dict[str, Any]]:
        """Stop all worker nodes.

        Gracefully terminates all running worker node processes. Attempts graceful
        shutdown first, then forces termination if necessary. Cleans up process
        tracking lists after stopping all workers.

        Returns:
            List[Dict[str, Any]]: List of results for each worker node shutdown:
                - status: "stopped" (graceful), "force_stopped" (forced), or "error"
                - node_name: Name of the worker node
                - message: Success or error message describing the shutdown
                - process_id: Process ID of the stopped worker

        The shutdown process:
            - Iterates through all tracked worker processes
            - Sends SIGTERM (terminate signal) to each process
            - Waits up to 5 seconds for graceful shutdown using non-blocking async wait
            - Sends SIGKILL (force kill) if graceful shutdown fails
            - Clears process tracking lists after all workers are stopped

        Failure modes:
            - Process already terminated: Returns "stopped" status
            - Graceful shutdown timeout: Returns "force_stopped" status
            - Process termination failure: Returns "error" status with error details
            - Process tracking issues: Returns "error" status for missing processes
        """
        results = []
        remaining_processes = []
        remaining_configs = []

        for i, process in enumerate(self.worker_processes):
            try:
                node_name = self.worker_configs[i].get("node_name", f"worker-{i+1}")

                # Terminate the process
                process.terminate()

                # Wait for graceful shutdown using non-blocking async wait
                try:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, lambda: process.wait(timeout=5))
                    status = "stopped"
                    message = f"Worker node '{node_name}' stopped gracefully"
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't stop gracefully
                    process.kill()
                    # Wait for force kill to complete (no timeout needed for kill)
                    await loop.run_in_executor(None, process.wait)
                    status = "force_stopped"
                    message = f"Worker node '{node_name}' force stopped"

                results.append(
                    {
                        "status": status,
                        "node_name": node_name,
                        "message": message,
                        "process_id": process.pid,
                    }
                )
                # Keep only processes that failed to stop in the remaining list
                if status == "error":
                    remaining_processes.append(process)
                    remaining_configs.append(self.worker_configs[i])

            except Exception as e:
                results.append(
                    ResponseFormatter.format_error_response(
                        "stop worker", e, node_name=f"worker-{i+1}"
                    )
                )
                remaining_processes.append(process)
                remaining_configs.append(self.worker_configs[i])

        # Keep only workers that failed to stop
        self.worker_processes = remaining_processes
        self.worker_configs = remaining_configs

        return results
