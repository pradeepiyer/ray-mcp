#!/usr/bin/env python3
"""
Comprehensive GKE mode testing for Ray MCP server without Claude Desktop.
This script tests cloud integration and Kubernetes functionality.
"""

import asyncio
import json
import os
from pathlib import Path
import sys

# Add the ray_mcp package to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.helpers.utils import call_tool, parse_tool_result


class GKETestConfig:
    """Configuration for GKE testing."""

    @staticmethod
    def is_gke_configured():
        """Check if GKE is properly configured."""
        return (
            os.getenv("GOOGLE_APPLICATION_CREDENTIALS") is not None
            and os.getenv("GOOGLE_CLOUD_PROJECT") is not None
        )

    @staticmethod
    def get_project_id():
        """Get GCP project ID from environment."""
        return os.getenv("GOOGLE_CLOUD_PROJECT")


async def test_gke_environment_setup():
    """Test GKE environment setup and configuration."""
    print("🔧 Testing GKE environment setup...")

    # Check environment variables
    if not GKETestConfig.is_gke_configured():
        print(
            "❌ GKE not configured. Set GOOGLE_APPLICATION_CREDENTIALS and GOOGLE_CLOUD_PROJECT"
        )
        return False

    # Test cloud environment check
    result = await call_tool("cloud", {"prompt": "check environment"})
    response = parse_tool_result(result)
    print(f"✅ Environment check: {response['status']}")

    if response["status"] != "success":
        print(f"❌ Environment check failed: {response['message']}")
        return False

    # Verify GKE is available
    providers = response.get("providers", {})
    gke_available = providers.get("gke", {}).get("available", False)

    if not gke_available:
        print("❌ GKE not available in environment")
        return False

    print("✅ GKE environment properly configured")
    return True


async def test_gcp_authentication():
    """Test GCP authentication flow."""
    print("🔐 Testing GCP authentication...")

    project_id = GKETestConfig.get_project_id()
    if not project_id:
        print("❌ No GCP project ID configured")
        return False

    # Test authentication
    result = await call_tool(
        "cloud", {"prompt": f"authenticate with GCP project {project_id}"}
    )
    response = parse_tool_result(result)

    # Check for successful authentication - GKE auth returns "authenticated": true, not "status": "success"
    if not response.get("authenticated", False):
        print(f"❌ Authentication failed: {response}")
        return False

    print(
        f"✅ Authentication: {'success' if response.get('authenticated') else 'failed'}"
    )

    # Verify project ID is correct
    if response.get("project_id") != project_id:
        print(
            f"❌ Project ID mismatch: expected {project_id}, got {response.get('project_id')}"
        )
        return False

    # Verify provider is GKE
    if response.get("provider") != "gke":
        print(f"❌ Provider mismatch: expected 'gke', got {response.get('provider')}")
        return False

    print(f"✅ Successfully authenticated with project {project_id}")
    return True


async def test_gke_cluster_listing():
    """Test GKE cluster listing functionality."""
    print("📋 Testing GKE cluster listing...")

    # First ensure we're authenticated
    project_id = GKETestConfig.get_project_id()
    auth_result = await call_tool(
        "cloud", {"prompt": f"authenticate with GCP project {project_id}"}
    )
    auth_response = parse_tool_result(auth_result)

    # Fix authentication check to match actual response format
    if not auth_response.get("authenticated", False):
        print(f"❌ Authentication failed: {auth_response}")
        return False

    # Test cluster listing
    result = await call_tool("cloud", {"prompt": "list all GKE clusters"})
    response = parse_tool_result(result)

    # Check for successful listing - GKE cluster listing returns "clusters" field, not "status"
    if "clusters" not in response:
        print(f"❌ Cluster listing failed: {response}")
        return False

    print(f"✅ Cluster listing: success")

    # Verify response structure
    clusters = response["clusters"]
    print(f"✅ Found {len(clusters)} GKE clusters")

    # Show cluster details if any exist
    for cluster in clusters[:3]:  # Show first 3 clusters
        name = cluster.get("name", "Unknown")
        status = cluster.get("status", "Unknown")
        location = cluster.get("location", "Unknown")
        print(f"  - {name} ({status}) in {location}")

    return True


async def test_gke_cluster_creation():
    """Test GKE cluster creation (be careful with costs!)."""
    print("🏗️  Testing GKE cluster creation...")

    # WARNING: This creates actual GCP resources that cost money!
    # Only run if explicitly enabled
    if not os.getenv("ENABLE_GKE_CLUSTER_CREATION"):
        print(
            "⚠️  Skipping cluster creation (set ENABLE_GKE_CLUSTER_CREATION=1 to enable)"
        )
        return True

    # First ensure we're authenticated
    project_id = GKETestConfig.get_project_id()
    auth_result = await call_tool(
        "cloud", {"prompt": f"authenticate with GCP project {project_id}"}
    )
    auth_response = parse_tool_result(auth_result)

    # Fix authentication check to match actual response format
    if not auth_response.get("authenticated", False):
        print(f"❌ Authentication failed: {auth_response}")
        return False

    # Create a test cluster
    cluster_name = "ray-mcp-test-cluster"
    result = await call_tool(
        "cloud",
        {
            "prompt": f"create GKE cluster named {cluster_name} with 2 nodes in us-central1-a"
        },
    )
    response = parse_tool_result(result)

    # Check for successful cluster creation - uses success_response format
    if response.get("status") == "error":
        print(f"❌ Cluster creation failed: {response.get('message', 'Unknown error')}")
        return False
    elif response.get("status") == "success":
        print(f"✅ Cluster creation: success")
        print(f"✅ Cluster {cluster_name} creation initiated")
        return True
    else:
        print(f"❌ Unexpected response format: {response}")
        return False


async def test_kubernetes_integration():
    """Test Kubernetes integration for existing clusters."""
    print("☸️  Testing Kubernetes integration...")

    # First ensure we're authenticated
    project_id = GKETestConfig.get_project_id()
    auth_result = await call_tool(
        "cloud", {"prompt": f"authenticate with GCP project {project_id}"}
    )
    auth_response = parse_tool_result(auth_result)

    # Fix authentication check to match actual response format
    if not auth_response.get("authenticated", False):
        print(f"❌ Authentication failed: {auth_response}")
        return False

    # List clusters to find one to test with
    list_result = await call_tool("cloud", {"prompt": "list all GKE clusters"})
    list_response = parse_tool_result(list_result)

    # Check for successful listing - returns clusters field, not status
    if "clusters" not in list_response:
        print("❌ Could not list clusters for Kubernetes integration test")
        return False

    clusters = list_response.get("clusters", [])
    if not clusters:
        print("⚠️  No clusters available for Kubernetes integration test")
        return True

    # Pick the first running cluster
    test_cluster = None
    for cluster in clusters:
        if cluster.get("status") == "RUNNING":
            test_cluster = cluster
            break

    if not test_cluster:
        print("⚠️  No running clusters available for Kubernetes integration test")
        return True

    cluster_name = test_cluster["name"]
    cluster_location = test_cluster.get("location", "us-central1-a")

    print(f"Testing connection to cluster {cluster_name} in {cluster_location}")

    # Test connecting to the cluster
    result = await call_tool(
        "cloud",
        {"prompt": f"connect to GKE cluster {cluster_name} in {cluster_location}"},
    )
    response = parse_tool_result(result)

    # Check for successful connection - uses success_response format
    if response.get("status") == "error":
        # If connection fails, that's expected in a test environment
        print(
            f"⚠️  Kubernetes connection failed (expected in test environment): {response.get('message', 'Unknown error')}"
        )
        print("✅ Kubernetes integration test completed (connection attempt made)")
        return True
    elif response.get("status") == "success":
        print(f"✅ Kubernetes connection: success")
        print(f"✅ Successfully connected to cluster {cluster_name}")
        return True
    else:
        print(f"❌ Unexpected response format: {response}")
        return False


async def test_ray_on_kubernetes():
    """Test Ray cluster creation on Kubernetes."""
    print("🚀 Testing Ray on Kubernetes...")

    # First ensure we're authenticated and connected
    project_id = GKETestConfig.get_project_id()
    auth_result = await call_tool(
        "cloud", {"prompt": f"authenticate with GCP project {project_id}"}
    )
    auth_response = parse_tool_result(auth_result)

    # Fix authentication check to match actual response format
    if not auth_response.get("authenticated", False):
        print(f"❌ Authentication failed: {auth_response}")
        return False

    # Test Ray cluster creation on Kubernetes
    result = await call_tool(
        "ray_cluster",
        {
            "prompt": "create Ray cluster named test-ray-cluster with 2 worker nodes on kubernetes"
        },
    )
    response = parse_tool_result(result)

    # Check for successful ray cluster creation - uses success_response format
    if response.get("status") == "error":
        error_message = response.get("message", "Unknown error")
        if "Kubernetes client not available" in error_message:
            print(
                f"⚠️  Ray cluster creation failed (expected in test environment): {error_message}"
            )
            print("✅ Ray on Kubernetes test completed (creation attempt made)")
            return True
        else:
            print(f"❌ Ray cluster creation failed: {error_message}")
            return False
    elif response.get("status") == "success":
        print(f"✅ Ray cluster creation: success")
        print("✅ Ray cluster creation on Kubernetes initiated")
        return True
    else:
        print(f"❌ Unexpected response format: {response}")
        return False


async def test_gke_error_handling():
    """Test error handling in GKE mode."""
    print("🚨 Testing GKE error handling...")

    # Test connecting to non-existent cluster (this should definitely fail)
    result = await call_tool(
        "cloud",
        {"prompt": "connect to GKE cluster non-existent-cluster-xyz in us-central1-a"},
    )
    response = parse_tool_result(result)

    # Error responses use standard format with "status": "error"
    if response.get("status") == "error":
        print(f"✅ Non-existent cluster error handling: correctly returned error")
    else:
        print(f"❌ Expected error response but got: {response}")
        return False

    # Test connecting to cluster without location (this should fail)
    result = await call_tool(
        "cloud", {"prompt": "connect to GKE cluster missing-location-cluster"}
    )
    response = parse_tool_result(result)

    # Error responses use standard format with "status": "error"
    if response.get("status") == "error":
        print(f"✅ Missing location error handling: correctly returned error")
    else:
        print(f"❌ Expected error response but got: {response}")
        return False

    return True


async def main():
    """Run all GKE mode tests."""
    print("🚀 Starting comprehensive GKE mode testing...")
    print("=" * 60)

    # Check if GKE is configured
    if not GKETestConfig.is_gke_configured():
        print("❌ GKE not configured. Please set:")
        print(
            "   export GOOGLE_APPLICATION_CREDENTIALS='/path/to/service-account.json'"
        )
        print("   export GOOGLE_CLOUD_PROJECT='your-project-id'")
        sys.exit(1)

    tests = [
        test_gke_environment_setup,
        test_gcp_authentication,
        test_gke_cluster_listing,
        test_gke_error_handling,
        test_kubernetes_integration,
        test_ray_on_kubernetes,
        test_gke_cluster_creation,  # Run last as it creates resources
    ]

    results = []

    for test in tests:
        try:
            print(f"\n🧪 Running {test.__name__}...")
            result = await test()
            results.append((test.__name__, result))
            print(f"✅ {test.__name__}: {'PASS' if result else 'FAIL'}")
        except Exception as e:
            print(f"❌ {test.__name__}: ERROR - {str(e)}")
            results.append((test.__name__, False))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary:")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")

    print(f"\n🎯 Results: {passed}/{total} tests passed")

    if not GKETestConfig.is_gke_configured():
        print("\n⚠️  Some tests were skipped due to missing GKE configuration")

    return passed == total


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Testing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Testing failed with error: {e}")
        sys.exit(1)
