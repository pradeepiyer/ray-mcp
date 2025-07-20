"""Amazon Elastic Kubernetes Service (EKS) cluster management for Ray MCP."""

import asyncio
import base64
from contextlib import contextmanager
import json
import os
import tempfile
from typing import TYPE_CHECKING, Any, Optional

from ..config import config
from ..foundation.enums import CloudProvider

# AWS and Kubernetes imports
from ..foundation.import_utils import (
    AWS_AVAILABLE,
    KUBERNETES_AVAILABLE,
    BotoCoreError,
    ClientError,
    NoCredentialsError,
    boto3,
    client,
    config as k8s_config,
)
from ..foundation.logging_utils import error_response, success_response
from ..foundation.resource_manager import ResourceManager
from ..llm_parser import get_parser


class EKSManager(ResourceManager):
    """Pure prompt-driven Amazon Elastic Kubernetes Service management - no traditional APIs."""

    # EKS-specific constants
    DEFAULT_NODE_GROUP_NAME = "default-nodegroup"
    DEFAULT_KUBERNETES_VERSION = "1.28"
    DEFAULT_INSTANCE_TYPE = "m5.large"
    DEFAULT_DISK_SIZE = 20
    DEFAULT_DESIRED_SIZE = 3
    DEFAULT_MIN_SIZE = 1
    DEFAULT_MAX_SIZE = 10

    def __init__(self):
        super().__init__(
            enable_ray=False,
            enable_kubernetes=True,
            enable_cloud=True,
        )

        self._eks_client = None
        self._ec2_client = None
        self._iam_client = None
        self._k8s_client = None
        # Initialize missing instance variables
        self._is_authenticated = False
        self._region = None
        self._aws_session = None
        self._ca_cert_file = None  # Track the CA certificate file for cleanup

    async def execute_request(self, prompt: str) -> dict[str, Any]:
        """Execute EKS operations using natural language prompts.

        Examples:
            - "authenticate with AWS region us-west-2"
            - "list all EKS clusters in us-east-1"
            - "connect to EKS cluster training-cluster in region us-west-2"
            - "create EKS cluster ml-cluster with 3 nodes"
            - "get info for cluster production-cluster"
        """
        try:
            action = await get_parser().parse_cloud_action(prompt)
            operation = action["operation"]

            if operation == "authenticate":
                region = action.get(
                    "zone"
                )  # LLM parser uses "zone" for AWS regions too
                return await self._authenticate_from_prompt(region)
            elif operation == "list_clusters":
                region = action.get("zone")
                return await self._discover_clusters(region)
            elif operation == "connect_cluster":
                cluster_name = action.get("cluster_name")
                region = action.get("zone")  # parse_cloud_action uses "zone"
                if not cluster_name or not region:
                    return error_response("cluster name and region required")
                return await self._connect_cluster(cluster_name, region)
            elif operation == "create_cluster":
                cluster_name = action.get("cluster_name")
                region = action.get("zone")  # parse_cloud_action uses "zone"
                cluster_spec = {"name": cluster_name, "region": region}
                return await self._create_cluster(cluster_spec, region)
            elif operation == "get_cluster_info":
                cluster_name = action.get("cluster_name")
                region = action.get("zone")  # parse_cloud_action uses "zone"
                if not cluster_name or not region:
                    return error_response("cluster name and region required")
                return await self._get_cluster_info(cluster_name, region)
            elif operation == "check_environment":
                return await self._check_environment()
            else:
                return error_response(f"Unknown operation: {operation}")

        except ValueError as e:
            return error_response(f"Could not parse request: {str(e)}")
        except Exception as e:
            return self._handle_error("execute_request", e)

    # =================================================================
    # INTERNAL IMPLEMENTATION: All methods are now private
    # =================================================================

    @contextmanager
    def _temporary_ca_cert_file(self, ca_cert_data: bytes):
        """Context manager for temporary CA certificate file with guaranteed cleanup."""
        ca_cert_file = None
        try:
            # Create a temporary file for the CA certificate
            ca_cert_file = tempfile.NamedTemporaryFile(
                mode="w+b", delete=False, suffix=".crt"
            )
            ca_cert_file.write(ca_cert_data)
            ca_cert_file.close()

            # Store the file path for cleanup
            self._ca_cert_file = ca_cert_file.name
            yield ca_cert_file.name
        finally:
            # Always clean up the temporary file
            if ca_cert_file and ca_cert_file.name and os.path.exists(ca_cert_file.name):
                try:
                    os.unlink(ca_cert_file.name)
                except OSError:
                    pass  # File might already be cleaned up
            # Reset the instance variable
            self._ca_cert_file = None

    def _cleanup_ca_cert_file(self):
        """Clean up the CA certificate file."""
        if self._ca_cert_file and os.path.exists(self._ca_cert_file):
            try:
                os.unlink(self._ca_cert_file)
                self._ca_cert_file = None
            except OSError:
                pass  # File might already be cleaned up

    async def _authenticate_from_prompt(
        self, region: Optional[str] = None
    ) -> dict[str, Any]:
        """Authenticate with EKS from prompt action."""
        return await self._authenticate_eks(region)

    async def _authenticate_eks(self, region: Optional[str] = None) -> dict[str, Any]:
        """Authenticate with EKS using AWS credentials."""
        try:
            return await self._authenticate_eks_operation(region)
        except Exception as e:
            return self._handle_error("eks authentication", e)

    async def _authenticate_eks_operation(
        self, region: Optional[str] = None
    ) -> dict[str, Any]:
        """Execute EKS authentication operation."""
        self._ensure_aws_available()

        # Default region if not provided
        region = region or "us-west-2"

        # Try to create AWS session
        try:
            # Create session (will use default credential chain)
            self._aws_session = boto3.Session(region_name=region)

            # Test credentials by calling STS to get caller identity
            sts_client = self._aws_session.client("sts")
            identity = await asyncio.to_thread(sts_client.get_caller_identity)

            # Store region
            self._region = region

            # Initialize EKS client
            self._ensure_clients()
            self._is_authenticated = True

            # Simple state tracking
            self._is_authenticated = True

            return {
                "provider": "eks",
                "authenticated": True,
                "region": region,
                "account_id": identity.get("Account"),
                "user_arn": identity.get("Arn"),
            }

        except NoCredentialsError:
            raise ValueError(
                "AWS credentials not found. Please configure AWS credentials using one of: "
                "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables, "
                "AWS credentials file (~/.aws/credentials), "
                "IAM role, or EC2 instance profile"
            )
        except ClientError as e:
            raise ValueError(f"AWS authentication failed: {str(e)}")

    async def _discover_clusters(self, region: Optional[str] = None) -> dict[str, Any]:
        """Discover EKS clusters."""
        try:
            return await self._discover_clusters_operation(region)
        except Exception as e:
            return self._handle_error("eks cluster discovery", e)

    async def _discover_clusters_operation(
        self, region: Optional[str] = None
    ) -> dict[str, Any]:
        """Execute EKS cluster discovery operation."""
        self._ensure_aws_available()

        # Use ManagedComponent validation method
        await self._ensure_eks_authenticated()

        region = self._resolve_region(region)
        if not region:
            raise ValueError(
                "Region is required for cluster discovery. Please authenticate with AWS first or specify a region."
            )

        # List clusters
        clusters_response = await asyncio.to_thread(self._eks_client.list_clusters)

        discovered_clusters = []
        cluster_names = clusters_response.get("clusters", [])

        # Get detailed information for each cluster
        for cluster_name in cluster_names:
            try:
                cluster_response = await asyncio.to_thread(
                    self._eks_client.describe_cluster, name=cluster_name
                )
                cluster = cluster_response["cluster"]

                cluster_info = {
                    "name": cluster.get("name", "unknown"),
                    "region": region,
                    "status": cluster.get("status", "unknown"),
                    "version": cluster.get("version", "unknown"),
                    "endpoint": cluster.get("endpoint", ""),
                    "created_at": self._format_timestamp(cluster.get("createdAt")),
                    "arn": cluster.get("arn", ""),
                    "role_arn": cluster.get("roleArn", ""),
                    "vpc_config": cluster.get("resourcesVpcConfig", {}),
                    "platform_version": cluster.get("platformVersion", ""),
                }
                discovered_clusters.append(cluster_info)
            except Exception as e:
                # Include cluster in list even if we can't get details
                discovered_clusters.append(
                    {
                        "name": cluster_name,
                        "region": region,
                        "status": "unknown",
                        "error": str(e),
                    }
                )

        return {
            "clusters": discovered_clusters,
            "total_count": len(discovered_clusters),
            "region": region,
        }

    def _ensure_clients(self) -> None:
        """Ensure EKS clients are initialized."""
        self._ensure_aws_available()

        if not self._aws_session:
            raise RuntimeError("Not authenticated with AWS")

        if self._eks_client is None:
            self._eks_client = self._aws_session.client("eks")

        if self._ec2_client is None:
            self._ec2_client = self._aws_session.client("ec2")

        if self._iam_client is None:
            self._iam_client = self._aws_session.client("iam")

    async def _verify_eks_credentials(self) -> None:
        """Verify that EKS credentials are valid by making a simple API call."""
        if not self._eks_client:
            raise RuntimeError("EKS client not initialized")

        # Make a simple API call to verify credentials
        await asyncio.to_thread(self._eks_client.list_clusters)

    def _format_timestamp(self, timestamp) -> str:
        """Format timestamp safely handling both string and datetime objects."""
        if timestamp is None:
            return ""

        try:
            # If it's already a string, return it
            if isinstance(timestamp, str):
                return timestamp
            # If it's a datetime-like object, format it
            elif hasattr(timestamp, "isoformat"):
                return timestamp.isoformat()
            else:
                return str(timestamp)
        except Exception:
            return str(timestamp)

    async def _connect_cluster(self, cluster_name: str, region: str) -> dict[str, Any]:
        """Connect to an EKS cluster and establish Kubernetes connection."""
        if not AWS_AVAILABLE:
            return error_response(
                "AWS SDK is not available. Please install boto3: pip install boto3"
            )

        if not KUBERNETES_AVAILABLE:
            return error_response(
                "Kubernetes client library is not available. Please install kubernetes package: pip install kubernetes"
            )

        # Use ManagedComponent validation method
        try:
            await self._ensure_eks_authenticated()
        except RuntimeError as e:
            return self._handle_error("eks cluster connection", e)

        try:
            resolved_region = self._resolve_region(region)
            if not resolved_region:
                return error_response(
                    "Region is required for cluster connection. Please authenticate with AWS first or specify a region."
                )
            region = resolved_region

            # Get cluster details from EKS API
            cluster_response = await asyncio.to_thread(
                self._eks_client.describe_cluster, name=cluster_name
            )
            cluster = cluster_response["cluster"]

            # Establish actual Kubernetes connection using API
            k8s_connection_result = await self._establish_kubernetes_connection(
                cluster, region
            )

            if k8s_connection_result.get("status") != "success":
                return k8s_connection_result

            # Create context name following EKS convention
            context_name = f"arn:aws:eks:{region}:{cluster.get('arn', '').split(':')[4]}:cluster/{cluster_name}"

            # Simple state tracking
            self._last_operation = "connect_cluster"

            return success_response(
                connected=True,
                cluster_name=cluster_name,
                region=region,
                endpoint=cluster.get("endpoint"),
                kubernetes_connected=True,
                context=context_name,
                server_version=k8s_connection_result.get("server_version"),
            )

        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                return error_response(
                    f"EKS cluster '{cluster_name}' not found in region '{region}'"
                )
            else:
                return self._handle_error("eks cluster connection", e)
        except Exception as e:
            return self._handle_error("eks cluster connection", e)

    async def _establish_kubernetes_connection(
        self, cluster: dict[str, Any], region: str
    ) -> dict[str, Any]:
        """Establish Kubernetes connection using EKS cluster details and AWS credentials."""
        try:
            if not AWS_AVAILABLE:
                return error_response("AWS SDK not available")

            # Create Kubernetes client configuration
            configuration = client.Configuration()
            endpoint = cluster.get("endpoint")
            if endpoint:
                configuration.host = endpoint
            else:
                return error_response("Cluster endpoint not found")

            # Get EKS token for authentication
            token = await self._get_eks_token(cluster["name"], region)
            if not token:
                return error_response("Failed to get EKS authentication token")

            # Set up bearer token authentication
            configuration.api_key_prefix["authorization"] = "Bearer"
            configuration.api_key["authorization"] = token

            # Handle cluster CA certificate
            ca_data = cluster.get("certificateAuthority", {}).get("data")
            if ca_data:
                # Decode the base64-encoded CA certificate
                ca_cert_data = base64.b64decode(ca_data)

                # Use context manager to ensure cleanup of temporary CA certificate file
                with self._temporary_ca_cert_file(ca_cert_data) as ca_cert_file_path:
                    # Set SSL CA certificate path
                    if hasattr(configuration, "ssl_ca_cert"):
                        setattr(configuration, "ssl_ca_cert", ca_cert_file_path)
                    configuration.verify_ssl = True

                    # Test the connection by creating a client and making an API call
                    with client.ApiClient(configuration) as api_client:
                        v1 = client.CoreV1Api(api_client)
                        version_api = client.VersionApi(api_client)

                        # Test connection by getting server version
                        version_info = await asyncio.to_thread(version_api.get_code)

                        # Also test basic functionality by listing namespaces
                        namespaces = await asyncio.to_thread(v1.list_namespace)

                    # Store the configuration for future use
                    self._k8s_client = configuration

                    # Safe access to git_version attribute
                    git_version = getattr(version_info, "git_version", "unknown")
                    return success_response(
                        connected=True,
                        server_version=git_version,
                        namespaces_count=len(namespaces.items) if namespaces else 0,
                    )
            else:
                # No CA certificate data provided
                configuration.verify_ssl = True

                # Test the connection by creating a client and making an API call
                with client.ApiClient(configuration) as api_client:
                    v1 = client.CoreV1Api(api_client)
                    version_api = client.VersionApi(api_client)

                    # Test connection by getting server version
                    version_info = await asyncio.to_thread(version_api.get_code)

                    # Also test basic functionality by listing namespaces
                    namespaces = await asyncio.to_thread(v1.list_namespace)

                # Store the configuration for future use
                self._k8s_client = configuration

                # Safe access to git_version attribute
                git_version = getattr(version_info, "git_version", "unknown")
                return success_response(
                    connected=True,
                    server_version=git_version,
                    namespaces_count=len(namespaces.items) if namespaces else 0,
                )

        except Exception as e:
            return self._handle_error("establish kubernetes connection", e)

    async def _get_eks_token(self, cluster_name: str, region: str) -> Optional[str]:
        """Get EKS authentication token using AWS STS."""
        try:
            # Use the AWS CLI approach to get token
            sts_client = self._aws_session.client("sts", region_name=region)

            # Generate presigned URL for GetCallerIdentity with cluster name header
            presigned_url = await asyncio.to_thread(
                sts_client.generate_presigned_url,
                "get_caller_identity",
                Params={},
                ExpiresIn=60,
                HttpMethod="GET",
            )

            # Generate a new presigned URL with proper headers for EKS
            import urllib.parse
            import botocore.awsrequest
            from botocore.auth import SigV4Auth
            
            # Create a proper request for EKS token
            endpoint = f"https://sts.{region}.amazonaws.com/"
            headers = {
                'x-k8s-aws-id': cluster_name,
                'Host': f"sts.{region}.amazonaws.com"
            }
            
            # Create signed request
            request = botocore.awsrequest.AWSRequest(
                method='GET',
                url=endpoint,
                params={
                    'Action': 'GetCallerIdentity',
                    'Version': '2011-06-15'
                },
                headers=headers
            )
            
            # Sign the request
            credentials = self._aws_session.get_credentials()
            SigV4Auth(credentials, 'sts', region).add_auth(request)
            
            # Create the EKS token from the signed URL
            signed_url = request.url
            token_string = f"k8s-aws-v1.{base64.urlsafe_b64encode(signed_url.encode()).decode().rstrip('=')}"

            return token_string
        except Exception as e:
            self.logger.log_error("get eks token", e)
            return None

    def _get_kubernetes_client(self) -> Optional[Any]:
        """Get the current Kubernetes client configuration."""
        return self._k8s_client

    def _get_connection_status(self) -> dict[str, Any]:
        """Get EKS connection status."""
        return success_response(
            authenticated=self._is_authenticated,
            region=self._region,
            provider="eks",
        )

    def _disconnect(self) -> dict[str, Any]:
        """Disconnect from EKS and clean up resources."""
        try:
            # Clean up certificate file
            self._cleanup_ca_cert_file()

            # Reset connection state
            self._k8s_client = None
            self._is_authenticated = False
            self._region = None
            self._aws_session = None
            self._eks_client = None
            self._ec2_client = None
            self._iam_client = None

            # Simple state tracking
            self._last_operation = "disconnect_cluster"

            return success_response(disconnected=True, provider="eks")

        except Exception as e:
            return self._handle_error("eks disconnect", e)

    async def _create_cluster(
        self, cluster_spec: dict[str, Any], region: Optional[str] = None
    ) -> dict[str, Any]:
        """Create an EKS cluster."""
        if not AWS_AVAILABLE:
            return error_response(
                "AWS SDK is not available. Please install boto3: pip install boto3"
            )

        if not self._is_authenticated:
            return error_response(
                "Not authenticated with AWS. Please authenticate first."
            )

        try:
            region = self._resolve_region(region)
            if not region:
                return error_response(
                    "Region is required for cluster creation. Please authenticate with AWS first or specify a region."
                )

            # Build cluster configuration
            cluster_config = self._build_cluster_config(cluster_spec, region)

            # Create the cluster
            cluster_name = cluster_spec.get("name", "ray-cluster")

            # Create cluster
            operation = await asyncio.to_thread(
                self._eks_client.create_cluster, **cluster_config
            )

            return success_response(
                created=True,
                cluster_name=cluster_name,
                region=region,
                status="CREATING",
                arn=operation.get("cluster", {}).get("arn"),
            )

        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceInUseException":
                return error_response(
                    f"EKS cluster '{cluster_spec.get('name')}' already exists"
                )
            else:
                return self._handle_error("eks cluster creation", e)
        except Exception as e:
            return self._handle_error("eks cluster creation", e)

    async def _get_cluster_info(self, cluster_name: str, region: str) -> dict[str, Any]:
        """Get information about an EKS cluster."""
        if not AWS_AVAILABLE:
            return error_response(
                "AWS SDK is not available. Please install boto3: pip install boto3"
            )

        if not self._is_authenticated:
            return error_response(
                "Not authenticated with AWS. Please authenticate first."
            )

        try:
            resolved_region = self._resolve_region(region)
            if not resolved_region:
                return error_response(
                    "Region is required for cluster info. Please authenticate with AWS first or specify a region."
                )
            region = resolved_region

            # Get cluster details
            cluster_response = await asyncio.to_thread(
                self._eks_client.describe_cluster, name=cluster_name
            )
            cluster = cluster_response["cluster"]

            # Get node groups
            nodegroups_response = await asyncio.to_thread(
                self._eks_client.list_nodegroups, clusterName=cluster_name
            )
            nodegroup_names = nodegroups_response.get("nodegroups", [])

            # Get details for each node group
            nodegroups = []
            for ng_name in nodegroup_names:
                try:
                    ng_response = await asyncio.to_thread(
                        self._eks_client.describe_nodegroup,
                        clusterName=cluster_name,
                        nodegroupName=ng_name,
                    )
                    ng = ng_response["nodegroup"]
                    nodegroups.append(
                        {
                            "name": ng.get("nodegroupName", "unknown"),
                            "status": ng.get("status", "unknown"),
                            "instance_types": ng.get("instanceTypes", []),
                            "scaling_config": ng.get("scalingConfig", {}),
                            "disk_size": ng.get("diskSize", 0),
                            "ami_type": ng.get("amiType", "unknown"),
                            "capacity_type": ng.get("capacityType", "unknown"),
                        }
                    )
                except Exception:
                    nodegroups.append(
                        {
                            "name": ng_name,
                            "status": "unknown",
                            "error": "Failed to get details",
                        }
                    )

            # Format detailed cluster information
            cluster_info = {
                "name": cluster.get("name", "unknown"),
                "region": region,
                "status": cluster.get("status", "unknown"),
                "endpoint": cluster.get("endpoint", ""),
                "version": cluster.get("version", "unknown"),
                "platform_version": cluster.get("platformVersion", "unknown"),
                "created_at": self._format_timestamp(cluster.get("createdAt")),
                "arn": cluster.get("arn", ""),
                "role_arn": cluster.get("roleArn", ""),
                "vpc_config": cluster.get("resourcesVpcConfig", {}),
                "logging": cluster.get("logging", {}),
                "identity": cluster.get("identity", {}),
                "nodegroups": nodegroups,
                "nodegroups_count": len(nodegroups),
            }

            return success_response(cluster=cluster_info)

        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                return error_response(
                    f"EKS cluster '{cluster_name}' not found in region '{region}'"
                )
            else:
                return self._handle_error("eks cluster info", e)
        except Exception as e:
            return self._handle_error("eks cluster info", e)

    def _build_cluster_config(
        self, cluster_spec: dict[str, Any], region: str
    ) -> dict[str, Any]:
        """Build EKS cluster configuration from specification."""
        cluster_name = cluster_spec.get("name", "ray-cluster")

        # Basic cluster config - minimal required fields
        cluster_config = {
            "name": cluster_name,
            "version": cluster_spec.get("version", self.DEFAULT_KUBERNETES_VERSION),
            "roleArn": cluster_spec.get("role_arn")
            or self._get_or_create_cluster_role(),
            "resourcesVpcConfig": {
                "subnetIds": cluster_spec.get("subnet_ids")
                or self._get_default_subnets(region),
            },
        }

        # Optional configuration
        if cluster_spec.get("logging"):
            cluster_config["logging"] = cluster_spec["logging"]

        if cluster_spec.get("encryption_config"):
            cluster_config["encryptionConfig"] = cluster_spec["encryption_config"]

        if cluster_spec.get("tags"):
            cluster_config["tags"] = cluster_spec["tags"]

        return cluster_config

    def _get_or_create_cluster_role(self) -> str:
        """Get or create IAM role for EKS cluster."""
        # This is a simplified implementation
        # In production, you'd want proper role management
        role_name = "ray-mcp-eks-cluster-role"

        try:
            # Try to get existing role
            response = self._iam_client.get_role(RoleName=role_name)
            return response["Role"]["Arn"]
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchEntity":
                # Role doesn't exist, would need to create it
                # For now, return a placeholder - user should provide role_arn
                raise ValueError(
                    f"IAM role '{role_name}' not found. Please provide role_arn in cluster_spec or create the role manually."
                )
            else:
                raise

    def _get_default_subnets(self, region: str) -> list[str]:
        """Get default VPC subnets."""
        # This is a simplified implementation
        # In production, you'd want proper VPC/subnet management
        try:
            # Get default VPC
            vpcs_response = self._ec2_client.describe_vpcs(
                Filters=[{"Name": "isDefault", "Values": ["true"]}]
            )

            if not vpcs_response["Vpcs"]:
                raise ValueError(
                    "No default VPC found. Please provide subnet_ids in cluster_spec."
                )

            vpc_id = vpcs_response["Vpcs"][0]["VpcId"]

            # Get subnets in default VPC
            subnets_response = self._ec2_client.describe_subnets(
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
            )

            subnet_ids = [subnet["SubnetId"] for subnet in subnets_response["Subnets"]]

            if not subnet_ids:
                raise ValueError(
                    "No subnets found in default VPC. Please provide subnet_ids in cluster_spec."
                )

            return subnet_ids

        except Exception as e:
            raise ValueError(
                f"Failed to get default subnets: {str(e)}. Please provide subnet_ids in cluster_spec."
            )

    def _get_current_time(self) -> str:
        """Get current time as ISO string."""
        from datetime import datetime

        return datetime.now().isoformat()

    async def _ensure_eks_authenticated(self) -> dict[str, Any]:
        """Ensure EKS authentication is configured and credentials are valid."""
        try:
            if self._is_authenticated and self._aws_session and self._eks_client:
                # Verify existing credentials are still valid
                try:
                    # Test credentials with a simple API call
                    await self._verify_eks_credentials()
                    return success_response(
                        message="Already authenticated with EKS",
                        region=self._region,
                    )
                except Exception:
                    # Credentials are invalid, need to re-authenticate
                    self._is_authenticated = False
                    self._aws_session = None
                    self._eks_client = None

            # Try to authenticate
            self._ensure_aws_available()

            # Get region from config or use default
            region = getattr(config, "aws_region", None) or "us-west-2"

            # Perform actual authentication with credential verification
            auth_result = await self._authenticate_eks_operation(region)

            # Check if authentication was successful
            if auth_result.get("authenticated"):
                return success_response(
                    message="EKS authentication configured and verified",
                    region=region,
                )
            else:
                return error_response(
                    f"EKS authentication failed: {auth_result.get('error', 'Unknown error')}"
                )

        except Exception as e:
            return self._handle_error("ensure eks authenticated", e)

    def _resolve_region(self, region: Optional[str] = None) -> Optional[str]:
        """Resolve region from multiple sources with fallback."""
        # Try provided region first
        if region:
            return region

        # Try instance region
        if self._region:
            return self._region

        # Try to get from config as fallback
        try:
            return getattr(config, "aws_region", None)
        except Exception:
            return None

    async def _check_environment(self) -> dict[str, Any]:
        """Check EKS environment and authentication status."""
        try:
            environment_status = {
                "provider": "eks",
                "aws_available": AWS_AVAILABLE,
                "kubernetes_available": KUBERNETES_AVAILABLE,
                "authenticated": self._is_authenticated,
                "region": self._region,
                "credentials_configured": bool(self._aws_session),
            }

            # Additional checks
            if AWS_AVAILABLE:
                environment_status["aws_status"] = "available"
            else:
                environment_status["aws_status"] = "missing - install boto3"

            if KUBERNETES_AVAILABLE:
                environment_status["kubernetes_status"] = "available"
            else:
                environment_status["kubernetes_status"] = (
                    "missing - install kubernetes package"
                )

            # Check authentication
            if self._is_authenticated:
                environment_status["authentication_status"] = "authenticated"
                if self._region:
                    environment_status["active_region"] = self._region
            else:
                environment_status["authentication_status"] = "not authenticated"
                environment_status["suggestion"] = (
                    "Run 'authenticate with AWS region us-west-2'"
                )

            return success_response(**environment_status)

        except Exception as e:
            return self._handle_error("check environment", e)

    def _ensure_aws_available(self) -> None:
        """Ensure AWS SDK is available."""
        if not AWS_AVAILABLE:
            raise RuntimeError(
                "AWS SDK (boto3) is not available. Please install boto3: pip install boto3"
            )

    def __del__(self):
        """Cleanup resources when object is destroyed."""
        try:
            self._cleanup_ca_cert_file()
        except Exception:
            pass  # Ignore errors during cleanup
