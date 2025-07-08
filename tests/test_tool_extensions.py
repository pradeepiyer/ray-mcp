"""Tests for Phase 3 tool extensions."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from ray_mcp.core.unified_manager import RayUnifiedManager
from ray_mcp.tool_registry import ToolRegistry


class TestToolExtensions:
    """Test Phase 3 tool extensions for KubeRay support."""

    @pytest.fixture
    def mock_ray_manager(self):
        """Create a mock ray manager."""
        manager = MagicMock(spec=RayUnifiedManager)

        # Set up properties using PropertyMock
        type(manager).is_initialized = PropertyMock(return_value=False)
        type(manager).is_kubernetes_connected = PropertyMock(return_value=False)
        type(manager).kuberay_clusters = PropertyMock(return_value={})
        type(manager).kuberay_jobs = PropertyMock(return_value={})

        # Set up async methods
        manager.init_cluster = AsyncMock(return_value={"status": "success"})
        manager.list_jobs = AsyncMock(return_value={"status": "success"})
        manager.list_kuberay_jobs = AsyncMock(return_value={"status": "success"})
        manager.create_kuberay_cluster = AsyncMock(return_value={"status": "success"})
        manager.create_kuberay_job = AsyncMock(return_value={"status": "success"})

        # Create a proper submit_job mock with correct signature
        async def mock_submit_job(
            entrypoint, runtime_env=None, job_id=None, metadata=None, **kwargs
        ):
            return {"status": "success"}

        manager.submit_job = AsyncMock(side_effect=mock_submit_job)

        return manager

    @pytest.fixture
    def tool_registry(self, mock_ray_manager):
        """Create tool registry with mocked manager."""
        return ToolRegistry(mock_ray_manager)

    def test_tool_registry_has_new_tools(self, tool_registry):
        """Test that new tools are registered."""
        tool_names = tool_registry.list_tool_names()

        # Check that new KubeRay tools are present
        assert "list_kuberay_clusters" in tool_names
        assert "inspect_kuberay_cluster" in tool_names
        assert "scale_kuberay_cluster" in tool_names
        assert "delete_kuberay_cluster" in tool_names
        assert "list_kuberay_jobs" in tool_names
        assert "inspect_kuberay_job" in tool_names
        assert "delete_kuberay_job" in tool_names
        assert "get_kuberay_job_logs" in tool_names

    def test_init_ray_tool_schema_extensions(self, tool_registry):
        """Test that init_ray tool has new parameters."""
        tools = tool_registry.get_tool_list()
        init_ray_tool = next(tool for tool in tools if tool.name == "init_ray")

        schema = init_ray_tool.inputSchema
        properties = schema["properties"]

        # Check new parameters are present
        assert "cluster_type" in properties
        assert "kubernetes_config" in properties
        assert "resources" in properties

        # Check cluster_type enum values
        cluster_type = properties["cluster_type"]
        assert cluster_type["enum"] == ["local", "kubernetes", "k8s"]
        assert cluster_type["default"] == "local"

    def test_submit_job_tool_schema_extensions(self, tool_registry):
        """Test that submit_job tool has new parameters."""
        tools = tool_registry.get_tool_list()
        submit_job_tool = next(tool for tool in tools if tool.name == "submit_job")

        schema = submit_job_tool.inputSchema
        properties = schema["properties"]

        # Check new parameters are present
        assert "job_type" in properties
        assert "kubernetes_config" in properties
        assert "image" in properties
        assert "resources" in properties
        assert "tolerations" in properties
        assert "node_selector" in properties
        assert "service_account" in properties
        assert "environment" in properties
        assert "working_dir" in properties

        # Check job_type enum values
        job_type = properties["job_type"]
        assert job_type["enum"] == ["local", "kubernetes", "k8s", "auto"]
        assert job_type["default"] == "auto"

    def test_list_jobs_tool_schema_extensions(self, tool_registry):
        """Test that list_jobs tool has new parameters."""
        tools = tool_registry.get_tool_list()
        list_jobs_tool = next(tool for tool in tools if tool.name == "list_jobs")

        schema = list_jobs_tool.inputSchema
        properties = schema["properties"]

        # Check new parameters are present
        assert "job_type" in properties
        assert "namespace" in properties

        # Check job_type enum values
        job_type = properties["job_type"]
        assert job_type["enum"] == ["local", "kubernetes", "k8s", "auto", "all"]
        assert job_type["default"] == "auto"

    @pytest.mark.asyncio
    async def test_init_ray_local_cluster_type(self, tool_registry, mock_ray_manager):
        """Test init_ray with local cluster type."""
        result = await tool_registry.execute_tool(
            "init_ray", {"cluster_type": "local", "num_cpus": 4}
        )

        # Should call init_cluster on manager with filtered args
        mock_ray_manager.init_cluster.assert_called_once_with(num_cpus=4)
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_init_ray_kubernetes_cluster_type(
        self, tool_registry, mock_ray_manager
    ):
        """Test init_ray with kubernetes cluster type."""
        result = await tool_registry.execute_tool(
            "init_ray",
            {
                "cluster_type": "kubernetes",
                "kubernetes_config": {
                    "namespace": "ray-system",
                    "cluster_name": "test-cluster",
                },
                "num_cpus": 4,
            },
        )

        # Should call create_kuberay_cluster
        mock_ray_manager.create_kuberay_cluster.assert_called_once()
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_init_ray_address_provided(self, tool_registry, mock_ray_manager):
        """Test init_ray with address provided (existing cluster)."""
        result = await tool_registry.execute_tool(
            "init_ray",
            {
                "address": "127.0.0.1:10001",
                "cluster_type": "kubernetes",  # Should be ignored when address is provided
            },
        )

        # Should call init_cluster directly regardless of cluster_type
        mock_ray_manager.init_cluster.assert_called_once_with(
            address="127.0.0.1:10001", cluster_type="kubernetes"
        )
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_submit_job_local_type(self, tool_registry, mock_ray_manager):
        """Test submit_job with local job type."""
        # Mock inspect.signature to return a signature with the expected parameters
        with patch("ray_mcp.tool_registry.inspect.signature") as mock_signature:
            # Create a mock signature that has the parameters we expect
            from inspect import Parameter, Signature

            mock_sig = Signature(
                [
                    Parameter("entrypoint", Parameter.POSITIONAL_OR_KEYWORD),
                    Parameter(
                        "runtime_env", Parameter.POSITIONAL_OR_KEYWORD, default=None
                    ),
                    Parameter("job_id", Parameter.POSITIONAL_OR_KEYWORD, default=None),
                    Parameter(
                        "metadata", Parameter.POSITIONAL_OR_KEYWORD, default=None
                    ),
                ]
            )
            mock_signature.return_value = mock_sig

            result = await tool_registry.execute_tool(
                "submit_job", {"entrypoint": "python script.py", "job_type": "local"}
            )

            # Should call submit_job on manager
            mock_ray_manager.submit_job.assert_called_once_with(
                entrypoint="python script.py"
            )
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_submit_job_kubernetes_type(self, tool_registry, mock_ray_manager):
        """Test submit_job with kubernetes job type."""
        result = await tool_registry.execute_tool(
            "submit_job",
            {
                "entrypoint": "python script.py",
                "job_type": "kubernetes",
                "kubernetes_config": {"namespace": "ray-system"},
            },
        )

        # Should call create_kuberay_job
        mock_ray_manager.create_kuberay_job.assert_called_once()
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_job_type_auto_detection_local(self, tool_registry, mock_ray_manager):
        """Test job type auto-detection for local clusters."""
        # Setup manager state using PropertyMock
        type(mock_ray_manager).kuberay_clusters = PropertyMock(return_value={})
        type(mock_ray_manager).is_kubernetes_connected = PropertyMock(
            return_value=False
        )
        type(mock_ray_manager).is_initialized = PropertyMock(return_value=True)
        
        # Mock state_manager.get_state() to return a state indicating local cluster
        mock_state_manager = MagicMock()
        mock_state_manager.get_state.return_value = {
            "cloud_provider_connections": {},
            "kubernetes_connected": False
        }
        mock_ray_manager.state_manager = mock_state_manager

        # Mock inspect.signature to return a signature with the expected parameters
        with patch("ray_mcp.tool_registry.inspect.signature") as mock_signature:
            from inspect import Parameter, Signature

            mock_sig = Signature(
                [
                    Parameter("entrypoint", Parameter.POSITIONAL_OR_KEYWORD),
                    Parameter(
                        "runtime_env", Parameter.POSITIONAL_OR_KEYWORD, default=None
                    ),
                    Parameter("job_id", Parameter.POSITIONAL_OR_KEYWORD, default=None),
                    Parameter(
                        "metadata", Parameter.POSITIONAL_OR_KEYWORD, default=None
                    ),
                ]
            )
            mock_signature.return_value = mock_sig

            result = await tool_registry.execute_tool(
                "submit_job", {"entrypoint": "python script.py", "job_type": "auto"}
            )

            # Should detect local and call submit_job
            mock_ray_manager.submit_job.assert_called_once()
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_job_type_auto_detection_kubernetes(
        self, tool_registry, mock_ray_manager
    ):
        """Test job type auto-detection for kubernetes clusters."""
        # Setup manager state using PropertyMock
        type(mock_ray_manager).kuberay_clusters = PropertyMock(
            return_value={"default/test-cluster": {}}
        )
        type(mock_ray_manager).is_kubernetes_connected = PropertyMock(return_value=True)
        
        # Mock state_manager.get_state() to return a state indicating kubernetes cluster
        mock_state_manager = MagicMock()
        mock_state_manager.get_state.return_value = {
            "cloud_provider_connections": {},
            "kubernetes_connected": True
        }
        mock_ray_manager.state_manager = mock_state_manager

        result = await tool_registry.execute_tool(
            "submit_job", {"entrypoint": "python script.py", "job_type": "auto"}
        )

        # Should detect kubernetes and call create_kuberay_job
        mock_ray_manager.create_kuberay_job.assert_called_once()
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_list_jobs_local_type(self, tool_registry, mock_ray_manager):
        """Test list_jobs with local job type."""
        result = await tool_registry.execute_tool("list_jobs", {"job_type": "local"})

        # Should call list_jobs on manager
        mock_ray_manager.list_jobs.assert_called_once()
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_list_jobs_kubernetes_type(self, tool_registry, mock_ray_manager):
        """Test list_jobs with kubernetes job type."""
        result = await tool_registry.execute_tool(
            "list_jobs", {"job_type": "kubernetes", "namespace": "ray-system"}
        )

        # Should call list_kuberay_jobs on manager
        mock_ray_manager.list_kuberay_jobs.assert_called_once_with(
            namespace="ray-system"
        )
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_kuberay_cluster_tools(self, tool_registry, mock_ray_manager):
        """Test KubeRay cluster management tools."""
        # Test list_kuberay_clusters
        result = await tool_registry.execute_tool(
            "list_kuberay_clusters", {"namespace": "ray-system"}
        )
        mock_ray_manager.list_kuberay_clusters.assert_called_once_with(
            namespace="ray-system"
        )

        # Test inspect_kuberay_cluster
        mock_ray_manager.get_kuberay_cluster = AsyncMock(
            return_value={"status": "success"}
        )
        result = await tool_registry.execute_tool(
            "inspect_kuberay_cluster",
            {"cluster_name": "test-cluster", "namespace": "ray-system"},
        )
        mock_ray_manager.get_kuberay_cluster.assert_called_once_with(
            "test-cluster", "ray-system"
        )

    @pytest.mark.asyncio
    async def test_kuberay_job_tools(self, tool_registry, mock_ray_manager):
        """Test KubeRay job management tools."""
        # Test list_kuberay_jobs
        result = await tool_registry.execute_tool(
            "list_kuberay_jobs", {"namespace": "ray-system"}
        )
        mock_ray_manager.list_kuberay_jobs.assert_called_once_with(
            namespace="ray-system"
        )

        # Test inspect_kuberay_job
        mock_ray_manager.get_kuberay_job = AsyncMock(return_value={"status": "success"})
        result = await tool_registry.execute_tool(
            "inspect_kuberay_job", {"job_name": "test-job", "namespace": "ray-system"}
        )
        mock_ray_manager.get_kuberay_job.assert_called_once_with(
            "test-job", "ray-system"
        )

    @pytest.mark.asyncio
    async def test_invalid_cluster_type(self, tool_registry, mock_ray_manager):
        """Test init_ray with invalid cluster type."""
        result = await tool_registry.execute_tool(
            "init_ray", {"cluster_type": "invalid"}
        )

        # Should return validation error
        assert result["status"] == "error"
        assert "Invalid cluster_type" in result["message"]

    @pytest.mark.asyncio
    async def test_invalid_job_type(self, tool_registry, mock_ray_manager):
        """Test submit_job with invalid job type."""
        result = await tool_registry.execute_tool(
            "submit_job", {"entrypoint": "python script.py", "job_type": "invalid"}
        )

        # Should return validation error
        assert result["status"] == "error"
        assert "Invalid job_type" in result["message"]

    def test_backward_compatibility_init_ray(self, tool_registry):
        """Test that init_ray maintains backward compatibility."""
        tools = tool_registry.get_tool_list()
        init_ray_tool = next(tool for tool in tools if tool.name == "init_ray")

        schema = init_ray_tool.inputSchema
        properties = schema["properties"]

        # Check that all original parameters are still present
        assert "address" in properties
        assert "num_cpus" in properties
        assert "num_gpus" in properties
        assert "object_store_memory" in properties
        assert "worker_nodes" in properties
        assert "head_node_port" in properties
        assert "dashboard_port" in properties
        assert "head_node_host" in properties

    def test_backward_compatibility_submit_job(self, tool_registry):
        """Test that submit_job maintains backward compatibility."""
        tools = tool_registry.get_tool_list()
        submit_job_tool = next(tool for tool in tools if tool.name == "submit_job")

        schema = submit_job_tool.inputSchema
        properties = schema["properties"]
        required = schema["required"]

        # Check that all original parameters are still present
        assert "entrypoint" in properties
        assert "runtime_env" in properties
        assert "job_id" in properties
        assert "metadata" in properties

        # Check that entrypoint is still the only required parameter
        assert required == ["entrypoint"]
