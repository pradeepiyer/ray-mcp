"""Unit tests for RayJobManager component.

Tests focus on job management behavior with 100% mocking.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ray_mcp.core.managers.job_manager import RayJobManager


@pytest.mark.fast
class TestRayJobManagerCore:
    """Test core job management functionality."""

    def test_manager_instantiation(self):
        """Test that job manager can be instantiated with state manager."""
        state_manager = Mock()
        manager = RayJobManager(state_manager)
        assert manager is not None
        assert manager.state_manager == state_manager
        # Test that the new base functionality is available
        assert hasattr(manager, "_log_info")
        assert hasattr(manager, "_format_success_response")
        assert hasattr(manager, "_execute_operation")

    async def test_submit_job_success(self):
        """Test successful job submission."""
        state_manager = Mock()
        state_manager.is_initialized.return_value = True
        state_manager.get_state.return_value = {
            "dashboard_url": "http://127.0.0.1:8265"
        }

        # Mock job client
        mock_job_client = Mock()
        mock_job_client.submit_job.return_value = "job_12345"

        manager = RayJobManager(state_manager)

        # Mock the Ray availability check and job client
        with (
            patch.object(manager, "_RAY_AVAILABLE", True),
            patch.object(
                manager, "_get_or_create_job_client", return_value=mock_job_client
            ),
        ):
            result = await manager.submit_job("python script.py")

        assert result["status"] == "success"
        assert result["job_id"] == "job_12345"
        assert result["entrypoint"] == "python script.py"
        mock_job_client.submit_job.assert_called_once()

    async def test_submit_job_not_initialized(self):
        """Test job submission when Ray is not initialized."""
        state_manager = Mock()
        state_manager.is_initialized.return_value = False

        manager = RayJobManager(state_manager)

        result = await manager.submit_job("python script.py")
        assert result["status"] == "error"
        assert "Ray is not initialized" in result["message"]

    @pytest.mark.parametrize("entrypoint", ["", None, "   ", 123])
    async def test_submit_job_invalid_entrypoint(self, entrypoint):
        """Test job submission with invalid entrypoint."""
        state_manager = Mock()
        state_manager.is_initialized.return_value = True

        manager = RayJobManager(state_manager)

        result = await manager.submit_job(entrypoint)
        assert result["status"] == "error"
        assert "Entrypoint must be a non-empty string" in result["message"]

    async def test_submit_job_with_runtime_env(self):
        """Test job submission with runtime environment."""
        state_manager = Mock()
        state_manager.is_initialized.return_value = True

        mock_job_client = Mock()
        mock_job_client.submit_job.return_value = "job_67890"

        manager = RayJobManager(state_manager)

        runtime_env = {"pip": ["numpy", "pandas"]}

        with patch.object(
            manager, "_get_or_create_job_client", return_value=mock_job_client
        ):
            result = await manager.submit_job(
                "python script.py",
                runtime_env=runtime_env,
                job_id="custom_job_id",
                metadata={"user": "test"},
            )

        assert result["status"] == "success"
        assert result["runtime_env"] == runtime_env
        mock_job_client.submit_job.assert_called_with(
            entrypoint="python script.py",
            runtime_env=runtime_env,
            job_id="custom_job_id",
            metadata={"user": "test"},
        )

    async def test_list_jobs_success(self):
        """Test successful job listing."""
        state_manager = Mock()
        state_manager.is_initialized.return_value = True

        # Mock job data
        mock_job1 = Mock()
        mock_job1.__dict__ = {
            "job_id": "job_1",
            "status": "SUCCEEDED",
            "entrypoint": "python script1.py",
        }
        mock_job2 = Mock()
        mock_job2.__dict__ = {
            "job_id": "job_2",
            "status": "RUNNING",
            "entrypoint": "python script2.py",
        }

        mock_job_client = Mock()
        mock_job_client.list_jobs.return_value = [mock_job1, mock_job2]

        manager = RayJobManager(state_manager)

        with patch.object(
            manager, "_get_or_create_job_client", return_value=mock_job_client
        ):
            result = await manager.list_jobs()

        assert result["status"] == "success"
        assert result["job_count"] == 2
        assert len(result["jobs"]) == 2
        assert result["jobs"][0]["job_id"] == "job_1"
        assert result["jobs"][1]["job_id"] == "job_2"

    async def test_cancel_job_success(self):
        """Test successful job cancellation."""
        state_manager = Mock()
        state_manager.is_initialized.return_value = True

        mock_job_client = Mock()
        mock_job_client.stop_job.return_value = True

        manager = RayJobManager(state_manager)

        with patch.object(
            manager, "_get_or_create_job_client", return_value=mock_job_client
        ):
            result = await manager.cancel_job("job_12345")

        assert result["status"] == "success"
        assert result["job_id"] == "job_12345"
        assert result["cancelled"] is True
        mock_job_client.stop_job.assert_called_with("job_12345")

    async def test_cancel_job_failure(self):
        """Test job cancellation failure."""
        state_manager = Mock()
        state_manager.is_initialized.return_value = True

        mock_job_client = Mock()
        mock_job_client.stop_job.return_value = False

        manager = RayJobManager(state_manager)

        with patch.object(
            manager, "_get_or_create_job_client", return_value=mock_job_client
        ):
            result = await manager.cancel_job("job_12345")

        assert result["status"] == "error"
        assert "Failed to cancel job job_12345" in result["message"]

    @pytest.mark.parametrize("job_id", ["", None, "   ", 123])
    async def test_cancel_job_invalid_id(self, job_id):
        """Test job cancellation with invalid job ID."""
        state_manager = Mock()
        state_manager.is_initialized.return_value = True

        manager = RayJobManager(state_manager)

        result = await manager.cancel_job(job_id)
        assert result["status"] == "error"
        assert "Invalid job_id" in result["message"]


@pytest.mark.fast
class TestRayJobManagerClientHandling:
    """Test job client initialization and management."""

    async def test_job_client_creation_success(self):
        """Test successful job client creation."""
        state_manager = Mock()
        state_manager.get_state.return_value = {
            "dashboard_url": "http://127.0.0.1:8265",
            "job_client": None,
        }

        # Mock the imports at instance level
        mock_client = Mock()
        mock_client.list_jobs.return_value = []
        mock_client_class = Mock(return_value=mock_client)

        manager = RayJobManager(state_manager)
        manager._RAY_AVAILABLE = True
        manager._JobSubmissionClient = mock_client_class

        client = await manager._get_or_create_job_client("test_operation")

        assert client == mock_client
        mock_client_class.assert_called_with("http://127.0.0.1:8265")
        state_manager.update_state.assert_called_with(job_client=mock_client)

    async def test_job_client_existing_client(self):
        """Test using existing job client."""
        existing_client = Mock()
        state_manager = Mock()
        state_manager.get_state.return_value = {"job_client": existing_client}

        manager = RayJobManager(state_manager)

        client = await manager._get_or_create_job_client("test_operation")

        assert client == existing_client

    async def test_job_client_ray_not_available(self):
        """Test getting job client when Ray is not available."""
        state_manager = Mock()
        manager = RayJobManager(state_manager)
        manager._RAY_AVAILABLE = False

        # The _get_or_create_job_client method calls _ensure_ray_available which raises an exception
        # when Ray is not available, so we need to handle that
        with pytest.raises(RuntimeError, match="Ray is not available"):
            await manager._get_or_create_job_client("test_operation")

    async def test_job_client_creation_with_retry(self):
        """Test job client creation with retry logic."""
        state_manager = Mock()
        state_manager.get_state.return_value = {
            "dashboard_url": "http://127.0.0.1:8265",
            "job_client": None,
        }

        mock_client = Mock()
        # Fail first two attempts, succeed on third
        mock_client.list_jobs.side_effect = [
            Exception("Connection failed"),
            Exception("Still failing"),
            [],  # Success
        ]
        mock_client_class = Mock(return_value=mock_client)

        manager = RayJobManager(state_manager)
        manager._RAY_AVAILABLE = True
        manager._JobSubmissionClient = mock_client_class

        client = await manager._initialize_job_client_with_retry(
            "http://127.0.0.1:8265", max_retries=3, retry_delay=0.01
        )

        assert client == mock_client
        assert mock_client.list_jobs.call_count == 3

    async def test_job_client_creation_all_retries_fail(self):
        """Test job client creation when all retries fail."""
        mock_client = Mock()
        mock_client.list_jobs.side_effect = Exception("Connection failed")
        mock_client_class = Mock(return_value=mock_client)

        manager = RayJobManager(Mock())
        manager._RAY_AVAILABLE = True
        manager._JobSubmissionClient = mock_client_class

        client = await manager._initialize_job_client_with_retry(
            "http://127.0.0.1:8265", max_retries=2, retry_delay=0.01
        )

        assert client is None

    async def test_initialize_job_client_if_available(self):
        """Test initializing job client when Ray cluster is available."""
        mock_context = Mock()
        mock_context.get_node_id.return_value = "node_123"
        mock_context.gcs_address = "192.168.1.100:10001"  # Mock GCS address

        mock_ray = Mock()
        mock_ray.is_initialized.return_value = True
        mock_ray.get_runtime_context.return_value = mock_context

        state_manager = Mock()
        state_manager.get_state.return_value = {}  # No existing dashboard URL
        manager = RayJobManager(state_manager)
        manager._RAY_AVAILABLE = True
        manager._ray = mock_ray

        dashboard_url = await manager._initialize_job_client_if_available()

        assert (
            dashboard_url == "http://192.168.1.100:8265"
        )  # Should extract host from GCS address
        state_manager.update_state.assert_called_with(
            dashboard_url="http://192.168.1.100:8265"
        )

    async def test_initialize_job_client_with_existing_url(self):
        """Test initializing job client when dashboard URL already exists in state."""
        mock_context = Mock()
        mock_ray = Mock()
        mock_ray.is_initialized.return_value = True
        mock_ray.get_runtime_context.return_value = mock_context

        state_manager = Mock()
        state_manager.get_state.return_value = {
            "dashboard_url": "http://existing.host:8265"
        }
        manager = RayJobManager(state_manager)
        manager._RAY_AVAILABLE = True
        manager._ray = mock_ray

        dashboard_url = await manager._initialize_job_client_if_available()

        assert dashboard_url == "http://existing.host:8265"  # Should use existing URL

    async def test_initialize_job_client_fallback_to_localhost(self):
        """Test initializing job client falls back to localhost when no GCS address."""
        mock_context = Mock()
        mock_context.get_node_id.return_value = "node_123"
        mock_context.gcs_address = None  # No GCS address

        mock_ray = Mock()
        mock_ray.is_initialized.return_value = True
        mock_ray.get_runtime_context.return_value = mock_context

        state_manager = Mock()
        state_manager.get_state.return_value = {}  # No existing dashboard URL
        manager = RayJobManager(state_manager)
        manager._RAY_AVAILABLE = True
        manager._ray = mock_ray

        dashboard_url = await manager._initialize_job_client_if_available()

        assert dashboard_url == "http://127.0.0.1:8265"  # Should fall back to localhost
        state_manager.update_state.assert_called_with(
            dashboard_url="http://127.0.0.1:8265"
        )

    async def test_initialize_job_client_ray_not_initialized(self):
        """Test initializing job client when Ray is not initialized."""
        mock_ray = Mock()
        mock_ray.is_initialized.return_value = False

        state_manager = Mock()
        manager = RayJobManager(state_manager)
        manager._RAY_AVAILABLE = True
        manager._ray = mock_ray

        dashboard_url = await manager._initialize_job_client_if_available()

        assert dashboard_url is None


@pytest.mark.fast
class TestRayJobManagerErrorHandling:
    """Test error handling in job operations."""

    async def test_job_operation_client_initialization_failure(self):
        """Test job operation when client initialization fails, including infinite loop prevention."""
        state_manager = Mock()
        state_manager.is_initialized.return_value = True
        state_manager.get_state.return_value = {
            "job_client": None,
            "dashboard_url": None,
        }

        manager = RayJobManager(state_manager)
        manager._RAY_AVAILABLE = True

        # Test 1: Basic client initialization failure
        with patch.object(manager, "_get_or_create_job_client", return_value=None):
            result = await manager.submit_job("python script.py")

        assert result["status"] == "error"
        assert "Failed to initialize job client" in result["message"]

        # Test 2: Infinite loop prevention - Direct recursion prevention when flag is already set
        manager._initializing_job_client = True
        client = await manager._get_or_create_job_client("test_operation")
        assert client is None

        # Test 3: Nested initialization prevention
        dashboard_url = await manager._initialize_job_client_if_available()
        assert dashboard_url is None

        # Test 4: Flag reset after exception
        manager._initializing_job_client = False  # Reset for exception test
        with patch.object(
            manager,
            "_initialize_job_client_if_available",
            side_effect=Exception("Test error"),
        ):
            client = await manager._get_or_create_job_client("test_operation")
            assert client is None
            # Flag should be reset to False after exception
            assert manager._initializing_job_client is False

    async def test_job_operation_execution_error(self):
        """Test error handling during job operation execution."""
        state_manager = Mock()
        state_manager.is_initialized.return_value = True

        mock_job_client = Mock()
        mock_job_client.submit_job.side_effect = Exception("Job submission failed")

        manager = RayJobManager(state_manager)

        with patch.object(
            manager, "_get_or_create_job_client", return_value=mock_job_client
        ):
            result = await manager.submit_job("python script.py")

        assert result["status"] == "error"
        assert "Job submission failed" in result["message"]

    async def test_format_job_info_with_dict(self):
        """Test job info formatting with dictionary input."""
        manager = RayJobManager(Mock())

        job_dict = {
            "job_id": "test_job",
            "status": "RUNNING",
            "entrypoint": "python test.py",
            "metadata": {"user": "test"},
        }

        formatted = manager._format_job_info(job_dict)

        assert formatted["job_id"] == "test_job"
        assert formatted["status"] == "RUNNING"
        assert formatted["entrypoint"] == "python test.py"
        assert formatted["metadata"] == {"user": "test"}

    async def test_format_job_info_with_object(self):
        """Test job info formatting with object input."""
        manager = RayJobManager(Mock())

        job_obj = Mock()
        job_obj.__dict__ = {
            "submission_id": "test_job_obj",
            "status": "SUCCEEDED",
            "entrypoint": "python obj_test.py",
        }

        formatted = manager._format_job_info(job_obj)

        assert formatted["job_id"] == "test_job_obj"  # Uses submission_id as fallback
        assert formatted["status"] == "SUCCEEDED"
        assert formatted["entrypoint"] == "python obj_test.py"

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"invalid_param": "value", "entrypoint": "python script.py"},
            {"entrypoint": "python script.py", "extra_param": 123},
        ],
    )
    async def test_submit_job_filters_invalid_kwargs(self, kwargs):
        """Test that submit_job filters out invalid kwargs."""
        state_manager = Mock()
        state_manager.is_initialized.return_value = True

        mock_job_client = Mock()
        mock_job_client.submit_job.return_value = "job_filtered"

        # Mock inspect.signature to return specific parameters
        with patch(
            "ray_mcp.core.managers.job_manager.inspect.signature"
        ) as mock_signature:
            mock_sig = Mock()
            mock_sig.parameters.keys.return_value = [
                "entrypoint",
                "runtime_env",
                "job_id",
                "metadata",
            ]
            mock_signature.return_value = mock_sig

            manager = RayJobManager(state_manager)

            with patch.object(
                manager, "_get_or_create_job_client", return_value=mock_job_client
            ):
                await manager.submit_job(**kwargs)

        # Should only pass valid parameters to submit_job
        call_args = mock_job_client.submit_job.call_args
        assert "invalid_param" not in call_args.kwargs
        assert "extra_param" not in call_args.kwargs
        assert call_args.kwargs["entrypoint"] == "python script.py"
