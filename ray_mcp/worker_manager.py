"""Worker node management for Ray clusters."""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class WorkerManager:
    """Manages Ray worker node processes."""

    def __init__(self):
        self.worker_processes: List[subprocess.Popen] = []
        self.worker_configs: List[Dict[str, Any]] = []

    async def start_worker_nodes(
        self, worker_configs: List[Dict[str, Any]], head_node_address: str
    ) -> List[Dict[str, Any]]:
        """Start multiple worker nodes and connect them to the head node."""
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
                logger.error(f"Failed to start worker node {i+1}: {e}")
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
        """Start a single worker node process."""
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
            logger.error(f"Failed to start worker process for {node_name}: {e}")
            return {
                "status": "error",
                "node_name": node_name,
                "message": f"Failed to start worker process: {str(e)}",
            }

    def _build_worker_command(
        self, config: Dict[str, Any], head_node_address: str
    ) -> List[str]:
        """Build the command to start a Ray worker node."""
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
            for resource, value in config["resources"].items():
                cmd.extend(["--resources", f"{resource}={value}"])

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

    async def _spawn_worker_process(
        self, cmd: List[str], node_name: str
    ) -> Optional[subprocess.Popen]:
        """Spawn a worker node process."""
        try:
            logger.info(
                f"Starting worker node '{node_name}' with command: {' '.join(cmd)}"
            )

            # Create process with proper environment
            env = os.environ.copy()
            env["RAY_DISABLE_USAGE_STATS"] = "1"
            # Enable multi-node clusters on Windows and macOS
            env["RAY_ENABLE_WINDOWS_OR_OSX_CLUSTER"] = "1"

            # Start the process
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True
            )

            # Give it a moment to start
            await asyncio.sleep(0.2)

            # Check if process is still running
            if process.poll() is None:
                logger.info(
                    f"Worker node '{node_name}' started successfully (PID: {process.pid})"
                )
                return process
            else:
                # Process failed to start
                stdout, stderr = process.communicate()
                logger.error(
                    f"Worker node '{node_name}' failed to start. stdout: {stdout}, stderr: {stderr}"
                )
                return None

        except Exception as e:
            logger.error(f"Failed to spawn worker process for {node_name}: {e}")
            return None

    async def stop_all_workers(self) -> List[Dict[str, Any]]:
        """Stop all worker nodes."""
        results = []

        for i, process in enumerate(self.worker_processes):
            try:
                node_name = self.worker_configs[i].get("node_name", f"worker-{i+1}")

                # Terminate the process
                process.terminate()

                # Wait for graceful shutdown
                try:
                    process.wait(timeout=5)
                    status = "stopped"
                    message = f"Worker node '{node_name}' stopped gracefully"
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't stop gracefully
                    process.kill()
                    process.wait()
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

            except Exception as e:
                logger.error(f"Failed to stop worker {i+1}: {e}")
                results.append(
                    {
                        "status": "error",
                        "node_name": f"worker-{i+1}",
                        "message": f"Failed to stop worker: {str(e)}",
                    }
                )

        # Clear the lists
        self.worker_processes.clear()
        self.worker_configs.clear()

        return results

    def get_worker_status(self) -> List[Dict[str, Any]]:
        """Get status of all worker processes."""
        status_list = []

        for i, process in enumerate(self.worker_processes):
            node_name = self.worker_configs[i].get("node_name", f"worker-{i+1}")

            if process.poll() is None:
                status = "running"
                message = f"Worker node '{node_name}' is running"
            else:
                status = "stopped"
                message = f"Worker node '{node_name}' has stopped"

            status_list.append(
                {
                    "status": status,
                    "node_name": node_name,
                    "process_id": process.pid,
                    "message": message,
                }
            )

        return status_list
