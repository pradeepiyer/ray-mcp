"""Unit tests for EKSManager functionality."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from ray_mcp.cloud.eks_manager import EKSManager
from ray_mcp.foundation.enums import CloudProvider


@pytest.mark.unit
class TestEKSManager:
    """Test EKSManager functionality."""

    @pytest.fixture
    def eks_manager(self):
        """Create an EKSManager instance for testing."""
        return EKSManager()

    @pytest.fixture
    def mock_aws_session(self):
        """Mock AWS session."""
        session = Mock()
        session.client.return_value = Mock()
        return session

    def test_eks_manager_initialization(self, eks_manager):
        """Test EKSManager initialization."""
        assert eks_manager._eks_client is None
        assert eks_manager._ec2_client is None
        assert eks_manager._iam_client is None
        assert eks_manager._k8s_client is None
        assert eks_manager._is_authenticated is False
        assert eks_manager._region is None
        assert eks_manager._aws_session is None

    @pytest.mark.asyncio
    @patch("ray_mcp.cloud.eks_manager.get_parser")
    async def test_execute_request_authenticate(self, mock_get_parser, eks_manager):
        """Test execute_request with authenticate operation."""
        # Mock parser
        mock_parser = AsyncMock()
        mock_parser.parse_cloud_action.return_value = {
            "operation": "authenticate",
            "zone": "us-west-2",
        }
        mock_get_parser.return_value = mock_parser

        # Mock authenticate method
        eks_manager._authenticate_from_prompt = AsyncMock(
            return_value={"status": "success"}
        )

        result = await eks_manager.execute_request(
            "authenticate with AWS region us-west-2"
        )

        assert result["status"] == "success"
        mock_parser.parse_cloud_action.assert_called_once_with(
            "authenticate with AWS region us-west-2"
        )
        eks_manager._authenticate_from_prompt.assert_called_once_with("us-west-2")

    @pytest.mark.asyncio
    @patch("ray_mcp.cloud.eks_manager.get_parser")
    async def test_execute_request_list_clusters(self, mock_get_parser, eks_manager):
        """Test execute_request with list_clusters operation."""
        # Mock parser
        mock_parser = AsyncMock()
        mock_parser.parse_cloud_action.return_value = {
            "operation": "list_clusters",
            "zone": "us-west-2",
        }
        mock_get_parser.return_value = mock_parser

        # Mock discover method
        eks_manager._discover_clusters = AsyncMock(
            return_value={"status": "success", "clusters": []}
        )

        result = await eks_manager.execute_request("list EKS clusters in us-west-2")

        assert result["status"] == "success"
        eks_manager._discover_clusters.assert_called_once_with("us-west-2")

    @pytest.mark.asyncio
    @patch("ray_mcp.cloud.eks_manager.get_parser")
    async def test_execute_request_connect_cluster(self, mock_get_parser, eks_manager):
        """Test execute_request with connect_cluster operation."""
        # Mock parser
        mock_parser = AsyncMock()
        mock_parser.parse_cloud_action.return_value = {
            "operation": "connect_cluster",
            "cluster_name": "test-cluster",
            "zone": "us-west-2",
        }
        mock_get_parser.return_value = mock_parser

        # Mock connect method
        eks_manager._connect_cluster = AsyncMock(return_value={"status": "success"})

        result = await eks_manager.execute_request(
            "connect to EKS cluster test-cluster in us-west-2"
        )

        assert result["status"] == "success"
        eks_manager._connect_cluster.assert_called_once_with(
            "test-cluster", "us-west-2"
        )

    @pytest.mark.asyncio
    @patch("ray_mcp.cloud.eks_manager.get_parser")
    async def test_execute_request_missing_required_params(
        self, mock_get_parser, eks_manager
    ):
        """Test execute_request with missing required parameters."""
        # Mock parser
        mock_parser = AsyncMock()
        mock_parser.parse_cloud_action.return_value = {
            "operation": "connect_cluster",
            "cluster_name": None,
            "zone": "us-west-2",
        }
        mock_get_parser.return_value = mock_parser

        result = await eks_manager.execute_request("connect to cluster")

        assert result["status"] == "error"
        assert "cluster name and region required" in result["error"]

    @pytest.mark.asyncio
    @patch("ray_mcp.cloud.eks_manager.boto3")
    @patch("ray_mcp.cloud.eks_manager.asyncio.to_thread")
    async def test_authenticate_eks_operation_success(
        self, mock_to_thread, mock_boto3, eks_manager
    ):
        """Test successful EKS authentication."""
        # Mock AWS session and STS client
        mock_session = Mock()
        mock_sts_client = Mock()
        mock_session.client.return_value = mock_sts_client
        mock_boto3.Session.return_value = mock_session

        # Mock STS get_caller_identity response
        mock_identity = {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/test-user",
        }
        mock_to_thread.return_value = mock_identity

        # Mock ensure_clients
        eks_manager._ensure_clients = Mock()

        result = await eks_manager._authenticate_eks_operation("us-west-2")

        assert result["provider"] == "eks"
        assert result["authenticated"] is True
        assert result["region"] == "us-west-2"
        assert result["account_id"] == "123456789012"
        assert result["user_arn"] == "arn:aws:iam::123456789012:user/test-user"
        assert eks_manager._is_authenticated is True
        assert eks_manager._region == "us-west-2"

    @pytest.mark.asyncio
    @patch("ray_mcp.cloud.eks_manager.boto3")
    async def test_authenticate_eks_operation_no_credentials(
        self, mock_boto3, eks_manager
    ):
        """Test EKS authentication with no credentials."""
        from ray_mcp.foundation.import_utils import NoCredentialsError

        # Mock boto3 to raise NoCredentialsError
        mock_boto3.Session.side_effect = NoCredentialsError("No credentials found")

        with pytest.raises(ValueError, match="AWS credentials not found"):
            await eks_manager._authenticate_eks_operation("us-west-2")

    @pytest.mark.asyncio
    @patch("ray_mcp.cloud.eks_manager.asyncio.to_thread")
    async def test_discover_clusters_operation(self, mock_to_thread, eks_manager):
        """Test EKS cluster discovery operation."""
        # Mock authentication check
        eks_manager._ensure_eks_authenticated = AsyncMock()
        eks_manager._resolve_region = Mock(return_value="us-west-2")

        # Mock EKS client
        mock_eks_client = Mock()
        eks_manager._eks_client = mock_eks_client

        # Mock list_clusters response
        mock_clusters_response = {"clusters": ["cluster1", "cluster2"]}

        # Mock describe_cluster responses
        mock_cluster1_response = {
            "cluster": {
                "name": "cluster1",
                "status": "ACTIVE",
                "version": "1.28",
                "endpoint": "https://test1.eks.us-west-2.amazonaws.com",
                "createdAt": "2023-01-01T00:00:00Z",
                "arn": "arn:aws:eks:us-west-2:123456789012:cluster/cluster1",
                "roleArn": "arn:aws:iam::123456789012:role/eks-role",
                "resourcesVpcConfig": {},
                "platformVersion": "eks.1",
            }
        }

        mock_cluster2_response = {
            "cluster": {
                "name": "cluster2",
                "status": "CREATING",
                "version": "1.27",
                "endpoint": "https://test2.eks.us-west-2.amazonaws.com",
                "createdAt": "2023-01-02T00:00:00Z",
                "arn": "arn:aws:eks:us-west-2:123456789012:cluster/cluster2",
                "roleArn": "arn:aws:iam::123456789012:role/eks-role",
                "resourcesVpcConfig": {},
                "platformVersion": "eks.1",
            }
        }

        # Configure mock_to_thread to return different responses for different calls
        mock_to_thread.side_effect = [
            mock_clusters_response,  # list_clusters call
            mock_cluster1_response,  # describe_cluster for cluster1
            mock_cluster2_response,  # describe_cluster for cluster2
        ]

        result = await eks_manager._discover_clusters_operation("us-west-2")

        assert "clusters" in result
        assert len(result["clusters"]) == 2
        assert result["total_count"] == 2
        assert result["region"] == "us-west-2"

        # Check first cluster details
        cluster1 = result["clusters"][0]
        assert cluster1["name"] == "cluster1"
        assert cluster1["status"] == "ACTIVE"
        assert cluster1["version"] == "1.28"

    def test_resolve_region(self, eks_manager):
        """Test region resolution logic."""
        # Test with provided region
        assert eks_manager._resolve_region("us-east-1") == "us-east-1"

        # Test with instance region
        eks_manager._region = "us-west-1"
        assert eks_manager._resolve_region(None) == "us-west-1"

        # Test with config fallback
        eks_manager._region = None
        with patch("ray_mcp.cloud.eks_manager.config") as mock_config:
            mock_config.aws_region = "us-central-1"
            assert eks_manager._resolve_region(None) == "us-central-1"

    def test_format_timestamp(self, eks_manager):
        """Test timestamp formatting."""
        # Test with string
        assert (
            eks_manager._format_timestamp("2023-01-01T00:00:00Z")
            == "2023-01-01T00:00:00Z"
        )

        # Test with None
        assert eks_manager._format_timestamp(None) == ""

        # Test with object that has isoformat
        from datetime import datetime

        dt = datetime(2023, 1, 1)
        assert eks_manager._format_timestamp(dt) == dt.isoformat()

    def test_ensure_aws_available(self, eks_manager):
        """Test AWS availability check."""
        with patch("ray_mcp.cloud.eks_manager.AWS_AVAILABLE", True):
            # Should not raise when AWS is available
            eks_manager._ensure_aws_available()

        with patch("ray_mcp.cloud.eks_manager.AWS_AVAILABLE", False):
            # Should raise when AWS is not available
            with pytest.raises(
                RuntimeError, match="AWS SDK \\(boto3\\) is not available"
            ):
                eks_manager._ensure_aws_available()

    def test_cleanup_ca_cert_file(self, eks_manager):
        """Test CA certificate file cleanup."""
        with patch("os.path.exists") as mock_exists, patch("os.unlink") as mock_unlink:

            # Test cleanup when file exists
            mock_exists.return_value = True
            eks_manager._ca_cert_file = "/tmp/test.crt"

            eks_manager._cleanup_ca_cert_file()

            mock_exists.assert_called_once_with("/tmp/test.crt")
            mock_unlink.assert_called_once_with("/tmp/test.crt")
            assert eks_manager._ca_cert_file is None

    def test_get_connection_status(self, eks_manager):
        """Test connection status reporting."""
        eks_manager._is_authenticated = True
        eks_manager._region = "us-west-2"

        status = eks_manager._get_connection_status()

        assert status["status"] == "success"
        assert status["authenticated"] is True
        assert status["region"] == "us-west-2"
        assert status["provider"] == "eks"

    def test_disconnect(self, eks_manager):
        """Test disconnection and cleanup."""
        # Set up initial state
        eks_manager._k8s_client = Mock()
        eks_manager._is_authenticated = True
        eks_manager._region = "us-west-2"
        eks_manager._aws_session = Mock()
        eks_manager._eks_client = Mock()
        eks_manager._cleanup_ca_cert_file = Mock()

        result = eks_manager._disconnect()

        assert result["status"] == "success"
        assert result["disconnected"] is True
        assert result["provider"] == "eks"

        # Check that state was reset
        assert eks_manager._k8s_client is None
        assert eks_manager._is_authenticated is False
        assert eks_manager._region is None
        assert eks_manager._aws_session is None
        assert eks_manager._eks_client is None

        # Check that cleanup was called
        eks_manager._cleanup_ca_cert_file.assert_called_once()
