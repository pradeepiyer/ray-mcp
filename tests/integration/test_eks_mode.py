#!/usr/bin/env python3
"""
Comprehensive EKS mode testing for Ray MCP server without Claude Desktop.
This script tests AWS cloud integration and Kubernetes functionality.
"""

import asyncio
import json
import os
from pathlib import Path
import sys

# Add the ray_mcp package to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.helpers.utils import call_tool, parse_tool_result


class EKSTestConfig:
    """Configuration for EKS testing."""

    @staticmethod
    def is_eks_configured():
        """Check if EKS is properly configured."""
        # Check for AWS credentials
        aws_credentials_available = (
            (os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"))
            or os.getenv("AWS_PROFILE")
            or os.path.exists(os.path.expanduser("~/.aws/credentials"))
        )
        return aws_credentials_available

    @staticmethod
    def get_region():
        """Get AWS region from environment."""
        return os.getenv("AWS_DEFAULT_REGION", "us-west-2")


async def test_eks_environment_setup():
    """Test EKS environment setup and configuration."""
    print("🔧 Testing EKS environment setup...")

    # Check environment variables
    if not EKSTestConfig.is_eks_configured():
        print(
            "❌ EKS not configured. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY, "
            "or AWS_PROFILE, or configure ~/.aws/credentials"
        )
        return False

    # Test cloud environment check
    result = await call_tool("cloud", {"prompt": "check environment"})
    response = parse_tool_result(result)
    print(f"✅ Environment check: {response['status']}")

    if response["status"] == "success":
        # Check if EKS is detected
        providers = response.get("providers", {})
        if "eks" in providers:
            eks_status = providers["eks"]
            if eks_status.get("available", False):
                print("✅ EKS provider available")
                return True
            else:
                print(f"❌ EKS not available: {eks_status.get('reason', 'Unknown')}")
        else:
            print("❌ EKS provider not detected")

    return False


async def test_aws_authentication():
    """Test AWS authentication functionality."""
    print("🔐 Testing AWS authentication...")

    region = EKSTestConfig.get_region()
    result = await call_tool(
        "cloud", {"prompt": f"authenticate with AWS region {region}"}
    )
    response = parse_tool_result(result)

    if response["status"] == "success":
        print(f"✅ AWS authentication successful for region {region}")
        if "account_id" in response:
            print(f"   Account ID: {response['account_id']}")
        if "user_arn" in response:
            print(f"   User ARN: {response['user_arn']}")
        return True
    else:
        print(f"❌ AWS authentication failed: {response.get('error', 'Unknown error')}")
        return False


async def test_eks_cluster_discovery():
    """Test EKS cluster discovery functionality."""
    print("🔍 Testing EKS cluster discovery...")

    region = EKSTestConfig.get_region()
    result = await call_tool(
        "cloud", {"prompt": f"list EKS clusters in region {region}"}
    )
    response = parse_tool_result(result)

    if response["status"] == "success":
        clusters = response.get("clusters", [])
        print(f"✅ Found {len(clusters)} EKS clusters in region {region}")

        for cluster in clusters:
            print(
                f"   - {cluster.get('name', 'Unknown')}: {cluster.get('status', 'Unknown')}"
            )

        return True
    else:
        print(
            f"❌ EKS cluster discovery failed: {response.get('error', 'Unknown error')}"
        )
        return False


async def test_eks_cluster_info():
    """Test EKS cluster info functionality."""
    print("ℹ️  Testing EKS cluster info...")

    # First, discover clusters to get a cluster name
    region = EKSTestConfig.get_region()
    result = await call_tool(
        "cloud", {"prompt": f"list EKS clusters in region {region}"}
    )
    response = parse_tool_result(result)

    if response["status"] != "success":
        print("❌ Cannot test cluster info - cluster discovery failed")
        return False

    clusters = response.get("clusters", [])
    if not clusters:
        print("ℹ️  No clusters found - skipping cluster info test")
        return True

    # Test info for the first cluster
    cluster_name = clusters[0].get("name")
    if not cluster_name:
        print("❌ Cannot test cluster info - no valid cluster name")
        return False

    result = await call_tool(
        "cloud",
        {"prompt": f"get info for EKS cluster {cluster_name} in region {region}"},
    )
    response = parse_tool_result(result)

    if response["status"] == "success":
        cluster_info = response.get("cluster", {})
        print(f"✅ Retrieved info for cluster '{cluster_name}'")
        print(f"   Status: {cluster_info.get('status', 'Unknown')}")
        print(f"   Version: {cluster_info.get('version', 'Unknown')}")
        print(f"   Endpoint: {cluster_info.get('endpoint', 'Unknown')}")

        nodegroups = cluster_info.get("nodegroups", [])
        print(f"   Node groups: {len(nodegroups)}")

        return True
    else:
        print(f"❌ EKS cluster info failed: {response.get('error', 'Unknown error')}")
        return False


async def test_eks_integration_workflow():
    """Test complete EKS integration workflow."""
    print("🔄 Testing complete EKS integration workflow...")

    tests = [
        ("Environment Setup", test_eks_environment_setup),
        ("AWS Authentication", test_aws_authentication),
        ("EKS Cluster Discovery", test_eks_cluster_discovery),
        ("EKS Cluster Info", test_eks_cluster_info),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            success = await test_func()
            if success:
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"❌ {test_name} ERROR: {str(e)}")

    print(f"\n📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All EKS integration tests PASSED!")
        return True
    else:
        print("❌ Some EKS integration tests FAILED")
        return False


async def main():
    """Main test runner."""
    print("🚀 Starting EKS Mode Integration Tests")
    print("=" * 50)

    success = await test_eks_integration_workflow()

    print("\n" + "=" * 50)
    if success:
        print("✅ EKS mode testing completed successfully!")
        sys.exit(0)
    else:
        print("❌ EKS mode testing failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
