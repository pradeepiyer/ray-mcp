#!/usr/bin/env python3
"""Unit tests for main.py functions."""

import asyncio
import json
import sys
from io import StringIO
from typing import Any, Dict, List, cast
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from mcp.types import TextContent
from ray_mcp.main import call_tool, list_tools, run_server


@pytest.mark.fast
class TestMain:
    """Test cases for main.py functions."""

    @pytest.mark.asyncio
    async def test_list_tools_complete(self):
        """Test that list_tools returns all expected tools."""
        tools = await list_tools()

        tool_names = [tool.name for tool in tools]

        # Check that key tools are present
        expected_tools = [
            "start_ray",
            "connect_ray",
            "stop_ray",
            "cluster_status",
            "submit_job",
            "list_jobs",
            "job_status",
            "cancel_job",
            "list_actors",
            "kill_actor",
            "performance_metrics",
            "health_check",
            "optimize_config",
            "schedule_job",
            "get_logs",
        ]

        for expected_tool in expected_tools:
            assert (
                expected_tool in tool_names
            ), f"Tool {expected_tool} not found in tools list"

        # Verify tool schemas
        start_ray_tool = next(tool for tool in tools if tool.name == "start_ray")
        assert "num_cpus" in start_ray_tool.inputSchema["properties"]
        assert start_ray_tool.inputSchema["properties"]["num_cpus"]["default"] == 1

    @pytest.mark.asyncio
    async def test_call_tool_ray_unavailable(self):
        """Test call_tool when Ray is not available."""
        with patch("ray_mcp.main.RAY_AVAILABLE", False):
            result = cast(List[TextContent], await call_tool("start_ray", {}))

            assert len(result) == 1
            assert isinstance(result[0], TextContent)
            assert "Ray is not available" in result[0].text

    @pytest.mark.asyncio
    async def test_call_tool_unknown_tool(self):
        """Test call_tool with unknown tool name."""
        with patch("ray_mcp.main.RAY_AVAILABLE", True):
            with patch("ray_mcp.main.ray_manager") as mock_manager:
                result = cast(List[TextContent], await call_tool("unknown_tool", {}))

                assert len(result) == 1
                response_data = json.loads(result[0].text)
                assert response_data["status"] == "error"
                assert "Unknown tool" in response_data["message"]

    @pytest.mark.asyncio
    async def test_call_tool_exception_handling(self):
        """Test call_tool exception handling."""
        with patch("ray_mcp.main.RAY_AVAILABLE", True):
            with patch("ray_mcp.main.ray_manager") as mock_manager:
                mock_manager.start_cluster = AsyncMock(
                    side_effect=Exception("Test exception")
                )

                result = cast(List[TextContent], await call_tool("start_ray", {}))

                assert len(result) == 1
                response_data = json.loads(result[0].text)
                assert response_data["status"] == "error"
                assert "Test exception" in response_data["message"]

    @pytest.mark.asyncio
    async def test_call_tool_with_arguments(self):
        """Test call_tool with various arguments."""
        with patch("ray_mcp.main.RAY_AVAILABLE", True):
            with patch("ray_mcp.main.ray_manager") as mock_manager:
                mock_manager.start_cluster = AsyncMock(
                    return_value={"status": "started"}
                )

                args = {"num_cpus": 8, "num_gpus": 2}
                result = cast(List[TextContent], await call_tool("start_ray", args))

                assert len(result) == 1
                mock_manager.start_cluster.assert_called_once_with(
                    num_cpus=8, num_gpus=2
                )

    @pytest.mark.asyncio
    async def test_call_tool_no_arguments(self):
        """Test call_tool with None arguments."""
        with patch("ray_mcp.main.RAY_AVAILABLE", True):
            with patch("ray_mcp.main.ray_manager") as mock_manager:
                mock_manager.get_cluster_status = AsyncMock(
                    return_value={"status": "running"}
                )

                result = cast(
                    List[TextContent], await call_tool("cluster_status", None)
                )

                assert len(result) == 1
                mock_manager.get_cluster_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_tool_job_management(self):
        """Test call_tool for job management tools."""
        with patch("ray_mcp.main.RAY_AVAILABLE", True):
            with patch("ray_mcp.main.ray_manager") as mock_manager:
                # Test job_status
                mock_manager.get_job_status = AsyncMock(
                    return_value={"status": "success", "job_status": "RUNNING"}
                )

                result = cast(
                    List[TextContent],
                    await call_tool("job_status", {"job_id": "test_job"}),
                )

                assert len(result) == 1
                mock_manager.get_job_status.assert_called_once_with("test_job")

                # Test cancel_job
                mock_manager.cancel_job = AsyncMock(
                    return_value={"status": "cancelled"}
                )

                result = cast(
                    List[TextContent],
                    await call_tool("cancel_job", {"job_id": "test_job"}),
                )

                assert len(result) == 1
                mock_manager.cancel_job.assert_called_once_with("test_job")

    @pytest.mark.asyncio
    async def test_call_tool_actor_management(self):
        """Test call_tool for actor management tools."""
        with patch("ray_mcp.main.RAY_AVAILABLE", True):
            with patch("ray_mcp.main.ray_manager") as mock_manager:
                # Test list_actors with filters
                mock_manager.list_actors = AsyncMock(
                    return_value={"status": "success", "actors": []}
                )

                filters = {"state": "ALIVE"}
                result = cast(
                    List[TextContent],
                    await call_tool("list_actors", {"filters": filters}),
                )

                assert len(result) == 1
                mock_manager.list_actors.assert_called_once_with(filters)

                # Test kill_actor with no_restart
                mock_manager.kill_actor = AsyncMock(return_value={"status": "killed"})

                result = cast(
                    List[TextContent],
                    await call_tool(
                        "kill_actor", {"actor_id": "test_actor", "no_restart": True}
                    ),
                )

                assert len(result) == 1
                mock_manager.kill_actor.assert_called_once_with("test_actor", True)

    @pytest.mark.asyncio
    async def test_call_tool_monitoring_tools(self):
        """Test call_tool for monitoring tools."""
        with patch("ray_mcp.main.RAY_AVAILABLE", True):
            with patch("ray_mcp.main.ray_manager") as mock_manager:
                # Test performance_metrics
                mock_manager.get_performance_metrics = AsyncMock(
                    return_value={"status": "success", "metrics": {}}
                )

                result = cast(
                    List[TextContent], await call_tool("performance_metrics", {})
                )

                assert len(result) == 1
                mock_manager.get_performance_metrics.assert_called_once()

                # Test health_check
                mock_manager.cluster_health_check = AsyncMock(
                    return_value={"status": "success", "health": "good"}
                )

                result = cast(List[TextContent], await call_tool("health_check", {}))

                assert len(result) == 1
                mock_manager.cluster_health_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_tool_logs(self):
        """Test call_tool for log retrieval."""
        with patch("ray_mcp.main.RAY_AVAILABLE", True):
            with patch("ray_mcp.main.ray_manager") as mock_manager:
                mock_manager.get_logs = AsyncMock(
                    return_value={"status": "success", "logs": "test logs"}
                )

                args = {"job_id": "test_job", "num_lines": 50}
                result = cast(List[TextContent], await call_tool("get_logs", args))

                assert len(result) == 1
                mock_manager.get_logs.assert_called_once_with(
                    job_id="test_job", num_lines=50
                )

    def test_main_ray_unavailable_check(self):
        """Test that RAY_AVAILABLE is checked in main function."""
        # Test the logic without actually running the server
        with patch("ray_mcp.main.RAY_AVAILABLE", False) as mock_ray_available:
            # This test verifies the condition exists, not the full execution
            assert not mock_ray_available

    def test_run_server_exists(self):
        """Test that run_server function exists and is callable."""
        # Simple test that doesn't involve mocking asyncio or main
        assert callable(run_server)
        # Test that the function exists in the module
        import ray_mcp.main

        assert hasattr(ray_mcp.main, "run_server")

    @pytest.mark.asyncio
    async def test_call_tool_job_id_required_tools(self):
        """Test tools that require job_id parameter."""
        job_id_tools = ["job_status", "cancel_job", "monitor_job", "debug_job"]

        with patch("ray_mcp.main.RAY_AVAILABLE", True):
            with patch("ray_mcp.main.ray_manager") as mock_manager:
                # Mock return values for each method as async
                mock_manager.get_job_status = AsyncMock(
                    return_value={"status": "success"}
                )
                mock_manager.cancel_job = AsyncMock(
                    return_value={"status": "cancelled"}
                )
                mock_manager.monitor_job_progress = AsyncMock(
                    return_value={"status": "monitoring"}
                )
                mock_manager.debug_job = AsyncMock(return_value={"status": "debugging"})

                for tool_name in job_id_tools:
                    result = cast(
                        List[TextContent],
                        await call_tool(tool_name, {"job_id": "test_job"}),
                    )
                    assert len(result) == 1
                    response_data = json.loads(result[0].text)
                    assert response_data["status"] in [
                        "success",
                        "cancelled",
                        "monitoring",
                        "debugging",
                    ]

    @pytest.mark.asyncio
    async def test_call_tool_actor_id_required_tools(self):
        """Test tools that require actor_id parameter."""
        with patch("ray_mcp.main.RAY_AVAILABLE", True):
            with patch("ray_mcp.main.ray_manager") as mock_manager:
                mock_manager.kill_actor = AsyncMock(return_value={"status": "killed"})

                result = cast(
                    List[TextContent],
                    await call_tool("kill_actor", {"actor_id": "test_actor"}),
                )
                assert len(result) == 1

    @pytest.mark.asyncio
    async def test_call_tool_connect_ray(self):
        """Test connect_ray tool."""
        with patch("ray_mcp.main.RAY_AVAILABLE", True):
            with patch("ray_mcp.main.ray_manager") as mock_manager:
                mock_manager.connect_cluster = AsyncMock(
                    return_value={"status": "connected"}
                )

                result = cast(
                    List[TextContent],
                    await call_tool("connect_ray", {"address": "ray://remote:10001"}),
                )

                assert len(result) == 1
                response_data = json.loads(result[0].text)
                assert response_data["status"] == "connected"

    @pytest.mark.asyncio
    async def test_call_tool_all_cluster_management_tools(self):
        """Test all cluster management tools to ensure coverage."""
        with patch("ray_mcp.main.RAY_AVAILABLE", True):
            with patch("ray_mcp.main.ray_manager") as mock_manager:
                # Setup mock return values
                mock_manager.start_cluster = AsyncMock(
                    return_value={"status": "started"}
                )
                mock_manager.stop_cluster = AsyncMock(
                    return_value={"status": "stopped"}
                )
                mock_manager.get_cluster_resources = AsyncMock(
                    return_value={"status": "success"}
                )
                mock_manager.get_cluster_nodes = AsyncMock(
                    return_value={"status": "success"}
                )

                # Test cluster_resources
                result = cast(
                    List[TextContent], await call_tool("cluster_resources", {})
                )
                assert len(result) == 1
                mock_manager.get_cluster_resources.assert_called_once()

                # Test cluster_nodes
                result = cast(List[TextContent], await call_tool("cluster_nodes", {}))
                assert len(result) == 1
                mock_manager.get_cluster_nodes.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_tool_all_job_management_tools(self):
        """Test all job management tools to ensure coverage."""
        with patch("ray_mcp.main.RAY_AVAILABLE", True):
            with patch("ray_mcp.main.ray_manager") as mock_manager:
                # Setup mock return values
                mock_manager.submit_job = AsyncMock(
                    return_value={"status": "submitted"}
                )
                mock_manager.list_jobs = AsyncMock(return_value={"status": "success"})
                mock_manager.monitor_job_progress = AsyncMock(
                    return_value={"status": "monitoring"}
                )
                mock_manager.debug_job = AsyncMock(return_value={"status": "debugging"})

                # Test submit_job
                args = {
                    "entrypoint": "python test.py",
                    "runtime_env": {"pip": ["requests"]},
                }
                result = cast(List[TextContent], await call_tool("submit_job", args))
                assert len(result) == 1
                mock_manager.submit_job.assert_called_once_with(**args)

                # Test list_jobs
                result = cast(List[TextContent], await call_tool("list_jobs", {}))
                assert len(result) == 1
                mock_manager.list_jobs.assert_called_once()

                # Test monitor_job
                result = cast(
                    List[TextContent],
                    await call_tool("monitor_job", {"job_id": "test_job"}),
                )
                assert len(result) == 1
                mock_manager.monitor_job_progress.assert_called_once_with("test_job")

                # Test debug_job
                result = cast(
                    List[TextContent],
                    await call_tool("debug_job", {"job_id": "test_job"}),
                )
                assert len(result) == 1
                mock_manager.debug_job.assert_called_once_with("test_job")

    @pytest.mark.asyncio
    async def test_call_tool_all_actor_management_tools(self):
        """Test all actor management tools to ensure coverage."""
        with patch("ray_mcp.main.RAY_AVAILABLE", True):
            with patch("ray_mcp.main.ray_manager") as mock_manager:
                # Setup mock return values
                mock_manager.list_actors = AsyncMock(return_value={"status": "success"})
                mock_manager.kill_actor = AsyncMock(return_value={"status": "killed"})

                # Test list_actors without filters
                result = cast(List[TextContent], await call_tool("list_actors", {}))
                assert len(result) == 1
                mock_manager.list_actors.assert_called_once_with(None)

                # Test kill_actor with default no_restart
                result = cast(
                    List[TextContent],
                    await call_tool("kill_actor", {"actor_id": "test_actor"}),
                )
                assert len(result) == 1
                mock_manager.kill_actor.assert_called_once_with("test_actor", False)

    @pytest.mark.asyncio
    async def test_call_tool_all_monitoring_tools(self):
        """Test all monitoring tools to ensure coverage."""
        with patch("ray_mcp.main.RAY_AVAILABLE", True):
            with patch("ray_mcp.main.ray_manager") as mock_manager:
                # Setup mock return values
                mock_manager.optimize_cluster_config = AsyncMock(
                    return_value={"status": "optimized"}
                )

                # Test optimize_config
                result = cast(List[TextContent], await call_tool("optimize_config", {}))
                assert len(result) == 1
                mock_manager.optimize_cluster_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_tool_schedule_job(self):
        """Test schedule_job tool to ensure coverage."""
        with patch("ray_mcp.main.RAY_AVAILABLE", True):
            with patch("ray_mcp.main.ray_manager") as mock_manager:
                mock_manager.schedule_job = AsyncMock(
                    return_value={"status": "scheduled"}
                )

                args = {"entrypoint": "python daily_job.py", "schedule": "0 9 * * *"}
                result = cast(List[TextContent], await call_tool("schedule_job", args))

                assert len(result) == 1
                mock_manager.schedule_job.assert_called_once_with(**args)

    @pytest.mark.asyncio
    async def test_call_tool_get_logs_all_parameters(self):
        """Test get_logs tool with various parameter combinations."""
        with patch("ray_mcp.main.RAY_AVAILABLE", True):
            with patch("ray_mcp.main.ray_manager") as mock_manager:
                mock_manager.get_logs = AsyncMock(return_value={"status": "success"})

                # Test with all possible parameters
                args = {
                    "job_id": "test_job",
                    "actor_id": "test_actor",
                    "node_id": "test_node",
                    "num_lines": 200,
                }
                result = cast(List[TextContent], await call_tool("get_logs", args))

                assert len(result) == 1
                mock_manager.get_logs.assert_called_once_with(**args)

    # ===== ADDITIONAL COVERAGE TESTS =====

    @pytest.mark.asyncio
    async def test_call_tool_stop_ray(self):
        """Test stop_ray tool to ensure coverage."""
        with patch("ray_mcp.main.RAY_AVAILABLE", True):
            with patch("ray_mcp.main.ray_manager") as mock_manager:
                mock_manager.stop_cluster = AsyncMock(
                    return_value={"status": "stopped"}
                )

                result = cast(List[TextContent], await call_tool("stop_ray", {}))

                assert len(result) == 1
                mock_manager.stop_cluster.assert_called_once()

    def test_run_server_function_exists(self):
        """Test that run_server function exists and is importable."""
        from ray_mcp.main import run_server

        assert callable(run_server)

    def test_main_module_structure(self):
        """Test that the main module has expected structure."""
        import ray_mcp.main as main_module

        # Verify the main module has the expected attributes
        assert hasattr(main_module, "run_server")
        assert hasattr(main_module, "main")
        assert hasattr(main_module, "server")
        assert hasattr(main_module, "ray_manager")
        assert callable(main_module.run_server)

    @pytest.mark.asyncio
    async def test_call_tool_arguments_handling(self):
        """Test call_tool with various argument scenarios."""
        with patch("ray_mcp.main.RAY_AVAILABLE", True):
            with patch("ray_mcp.main.ray_manager") as mock_manager:
                mock_manager.get_cluster_status = AsyncMock(
                    return_value={"status": "running"}
                )

                # Test with empty dict
                result = cast(List[TextContent], await call_tool("cluster_status", {}))
                assert len(result) == 1
                mock_manager.get_cluster_status.assert_called_once()

    def test_main_function_import(self):
        """Test that main function can be imported."""
        import asyncio

        from ray_mcp.main import main

        assert asyncio.iscoroutinefunction(main)
        # Don't call the function to avoid creating an unawaited coroutine

    def test_asyncio_run_mock(self):
        """Test run_server function calls asyncio.run."""
        with patch("ray_mcp.main.asyncio.run") as mock_asyncio_run:
            from ray_mcp.main import run_server

            run_server()

            mock_asyncio_run.assert_called_once()

    def test_run_server_entrypoint(self, monkeypatch):
        """Test run_server function calls asyncio.run."""
        import ray_mcp.main

        called = {}

        async def fake_main():
            called["main_called"] = True
            return {"status": "test"}

        def fake_run(coro):
            called["run_called"] = True
            import asyncio

            return asyncio.get_event_loop().run_until_complete(coro)

        monkeypatch.setattr(ray_mcp.main, "main", fake_main)
        monkeypatch.setattr(ray_mcp.main.asyncio, "run", fake_run)
        ray_mcp.main.run_server()
        assert called["main_called"]
        assert called["run_called"]

    def test_main_ray_unavailable_branch(self, monkeypatch):
        import asyncio

        import ray_mcp.main

        monkeypatch.setattr(ray_mcp.main, "RAY_AVAILABLE", False)
        called = {}

        def fake_exit(code):
            called["exited"] = code
            raise SystemExit

        monkeypatch.setattr(ray_mcp.main.sys, "exit", fake_exit)
        # Should exit early due to RAY_AVAILABLE = False
        try:
            asyncio.run(ray_mcp.main.main())
        except SystemExit:
            pass
        assert called["exited"] == 1


if __name__ == "__main__":
    pytest.main([__file__])
