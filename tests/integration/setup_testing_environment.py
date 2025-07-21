#!/usr/bin/env python3
"""
Setup script for Ray MCP server testing environment.
Helps configure both local and GKE testing modes.
"""

import os
from pathlib import Path
import subprocess
import sys
from typing import Dict, Optional


class TestingSetup:
    """Helper class for setting up testing environment."""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.config_file = self.project_root / "testing_config.json"

    def check_python_version(self) -> bool:
        """Check if Python version is compatible."""
        version = sys.version_info
        if version.major >= 3 and version.minor >= 11:
            print(f"✅ Python {version.major}.{version.minor} - Compatible")
            return True
        else:
            print(f"❌ Python {version.major}.{version.minor} - Requires Python 3.11+")
            return False

    def check_dependencies(self) -> Dict[str, bool]:
        """Check if required dependencies are installed."""
        results = {}

        # Check UV
        try:
            result = subprocess.run(["uv", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ UV: {result.stdout.strip()}")
                results["uv"] = True
            else:
                print("❌ UV not found")
                results["uv"] = False
        except FileNotFoundError:
            print("❌ UV not found")
            results["uv"] = False

        # Check MCP
        try:
            result = subprocess.run(
                ["uv", "run", "python", "-c", "import mcp; print('MCP available')"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                print("✅ MCP available")
                results["mcp"] = True
            else:
                print("❌ MCP not available")
                results["mcp"] = False
        except Exception:
            print("❌ MCP not available")
            results["mcp"] = False

        return results

    def check_gke_setup(self) -> Dict[str, bool]:
        """Check GKE setup."""
        print("\n☁️  Checking GKE Setup...")

        results = {}

        # Check environment variables
        gcp_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        gcp_project = os.getenv("GOOGLE_CLOUD_PROJECT")

        if gcp_credentials:
            if os.path.exists(gcp_credentials):
                print(f"✅ GCP Credentials found: {gcp_credentials}")
                results["credentials"] = True
            else:
                print(f"❌ GCP Credentials file not found: {gcp_credentials}")
                results["credentials"] = False
        else:
            print("❌ GOOGLE_APPLICATION_CREDENTIALS not set")
            results["credentials"] = False

        if gcp_project:
            print(f"✅ GCP Project: {gcp_project}")
            results["project"] = True
        else:
            print("❌ GOOGLE_CLOUD_PROJECT not set")
            results["project"] = False

        # Check GKE dependencies
        try:
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    "-c",
                    """
try:
    from google.cloud import container_v1
    print("✅ Google Cloud Container API available")
except ImportError as e:
    print(f"❌ Google Cloud Container API not available: {e}")
    exit(1)
""",
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                print("✅ GKE dependencies available")
                results["gke_deps"] = True
            else:
                print("❌ GKE dependencies missing")
                results["gke_deps"] = False
        except Exception:
            print("❌ Error checking GKE dependencies")
            results["gke_deps"] = False

        # Check Kubernetes client
        try:
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    "-c",
                    """
try:
    from kubernetes import client, config
    print("✅ Kubernetes client available")
except ImportError as e:
    print(f"❌ Kubernetes client not available: {e}")
    exit(1)
""",
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                print("✅ Kubernetes client available")
                results["k8s_client"] = True
            else:
                print("❌ Kubernetes client missing")
                results["k8s_client"] = False
        except Exception:
            print("❌ Error checking Kubernetes client")
            results["k8s_client"] = False

        return results

    def install_dependencies(self) -> bool:
        """Install missing dependencies."""
        print("\n📦 Installing dependencies...")

        try:
            # Install base dependencies
            result = subprocess.run(["uv", "sync"], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"❌ Base dependency installation failed: {result.stderr}")
                return False

            # Install GKE dependencies
            result = subprocess.run(
                ["uv", "add", "ray-mcp[gke]"], capture_output=True, text=True
            )
            if result.returncode != 0:
                print(f"❌ GKE dependency installation failed: {result.stderr}")
                return False

            print("✅ Dependencies installed successfully")
            return True

        except Exception as e:
            print(f"❌ Error installing dependencies: {e}")
            return False

    def create_test_scripts(self) -> None:
        """Create convenience test scripts."""
        print("\n📋 Creating test scripts...")

        # Create test runner script
        test_runner_script = """#!/bin/bash
# Ray MCP Testing Runner
set -e

echo "🚀 Ray MCP Testing Environment"
echo "=============================="

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check what mode to run
if [ "$1" = "gke" ]; then
    echo "Running GKE mode tests..."
    python "$SCRIPT_DIR/test_gke_mode.py"
else
    echo "Usage: $0 [gke]"
    echo ""
    echo "Options:"
    echo "  gke   - Run GKE testing (requires GCP setup)"
    exit 1
fi
"""

        with open(Path(__file__).parent / "run_tests.sh", "w") as f:
            f.write(test_runner_script)

        # Make it executable
        os.chmod(Path(__file__).parent / "run_tests.sh", 0o755)

        print("✅ Test scripts created")

    def run_setup(self) -> None:
        """Run the complete setup process."""
        print("🎯 Ray MCP Testing Environment Setup")
        print("=" * 50)

        # Check Python version
        if not self.check_python_version():
            print("\n❌ Python version incompatible. Please upgrade to Python 3.11+")
            sys.exit(1)

        # Check dependencies
        deps = self.check_dependencies()
        if not all(deps.values()):
            print("\n📦 Installing missing dependencies...")
            if not self.install_dependencies():
                print("❌ Failed to install dependencies")
                sys.exit(1)

        # Check GKE setup
        gke_results = self.check_gke_setup()
        gke_ok = all(gke_results.values())

        # Create test scripts
        self.create_test_scripts()

        # Summary
        print("\n" + "=" * 50)
        print("📊 Setup Summary:")
        print(f"  Kubernetes Mode: {'✅ Ready' if gke_ok else '❌ Not Ready'}")

        if not gke_ok:
            print("\n⚠️  To enable Kubernetes testing:")
            print("  1. Set up GCP service account with Container Admin role")
            print("  2. Export GOOGLE_APPLICATION_CREDENTIALS and GOOGLE_CLOUD_PROJECT")
            print("  3. Run: uv add 'ray-mcp[gke]'")

        print("\n🎯 Ready to test!")
        print("Usage:")
        print("  ./tests/integration/run_tests.sh gke    # Test GKE mode")

        print("\nAlternative:")
        print("  python tests/integration/test_gke_mode.py")

        print("\nExisting test suite:")
        print("  make test-fast  # Unit tests")
        print("  make test-e2e   # Integration tests")
        print("  make test       # All tests")
        print("  python tests/integration/test_runner.py unit  # Unit tests only")
        print("  python tests/integration/test_runner.py e2e   # E2E tests only")

        print("\n📚 Documentation:")
        print("  docs/TESTING_GUIDE.md  # Complete testing guide")


if __name__ == "__main__":
    setup = TestingSetup()
    setup.run_setup()
