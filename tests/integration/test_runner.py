#!/usr/bin/env python3
"""Test runner for Ray MCP unit tests.

This script provides convenient commands for running unit tests:
- Unit tests: Fast, fully mocked tests
- All tests: Runs unit tests (equivalent to unit)

Usage:
    python test_runner.py unit          # Run unit tests
    python test_runner.py all           # Run unit tests
    python test_runner.py --help        # Show help
"""

import argparse
from pathlib import Path
import subprocess
import sys
import time


class TestRunner:
    """Test runner for Ray MCP test suites."""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent

    def run_command(self, cmd: list[str], description: str) -> bool:
        """Run a command and return success status."""
        print(f"\n🚀 {description}")
        print(f"Command: {' '.join(cmd)}")
        print("-" * 60)

        start_time = time.time()

        # Set timeout for unit tests
        timeout = 120

        try:
            result = subprocess.run(cmd, cwd=self.project_root, timeout=timeout)
            duration = time.time() - start_time

            if result.returncode == 0:
                print(f"✅ {description} completed successfully in {duration:.1f}s")
                return True
            else:
                print(f"❌ {description} failed after {duration:.1f}s")
                return False
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            print(f"⏰ {description} timed out after {duration:.1f}s")
            return False

    def run_unit_tests(self) -> bool:
        """Run fast unit tests with full mocking."""
        cmd = ["uv", "run", "pytest", "tests/unit/", "-m", "unit", "--tb=short", "-v"]
        return self.run_command(cmd, "Running unit tests")

    def run_all_tests(self) -> bool:
        """Run the complete test suite (currently only unit tests)."""
        print("🎯 Running Ray MCP test suite")
        print("=" * 60)

        # Run unit tests
        return self.run_unit_tests()

    def check_dependencies(self) -> bool:
        """Check that required dependencies are available."""
        print("🔍 Checking test dependencies...")

        # Check pytest
        result = subprocess.run(
            ["uv", "run", "pytest", "--version"], capture_output=True, text=True
        )
        if result.returncode != 0:
            print("❌ pytest not available")
            return False
        print(f"✅ {result.stdout.strip()}")

        # Check Kubernetes client
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-c",
                "from kubernetes import client; print('Kubernetes client available')",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"✅ {result.stdout.strip()}")
        else:
            print("⚠️  Kubernetes client not available")

        return True

    def show_test_info(self):
        """Show information about available tests."""
        print("📊 Ray MCP Test Suite Information")
        print("=" * 50)

        # Count tests in each category
        try:
            # Unit tests
            result = subprocess.run(
                ["uv", "run", "pytest", "tests/unit/", "--collect-only", "-q"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                unit_count = len([l for l in lines if "test_" in l])
                print(f"Unit tests: {unit_count} tests in tests/unit/")

            # Note: E2E tests not currently implemented
            print("E2E tests: 0 tests (not implemented)")

        except Exception as e:
            print(f"Could not count tests: {e}")

        print("\nTest Categories:")
        print("- unit: Fast tests with full mocking (< 1s each)")
        print("- all: Runs unit tests (equivalent to unit)")
        print("")

        print("\nUsage Examples:")
        print("  python test_runner.py unit     # Fast feedback during development")
        print("  python test_runner.py all      # Run all available tests")


def main():
    """Main test runner entry point."""
    parser = argparse.ArgumentParser(
        description="Ray MCP Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_runner.py unit          # Fast unit tests
  python test_runner.py all           # Run all tests (unit only)
  python test_runner.py info          # Show test information
        """,
    )

    parser.add_argument(
        "suite", choices=["unit", "all", "info"], help="Test suite to run"
    )

    parser.add_argument(
        "--check-deps",
        action="store_true",
        help="Check dependencies before running tests",
    )

    args = parser.parse_args()

    runner = TestRunner()

    # Check dependencies if requested
    if args.check_deps:
        if not runner.check_dependencies():
            return 1

    # Handle info command
    if args.suite == "info":
        runner.show_test_info()
        return 0

    # Run the requested test suite
    success = False

    if args.suite == "unit":
        success = runner.run_unit_tests()
    elif args.suite == "all":
        success = runner.run_all_tests()

    if success:
        print(f"\n🎉 Test suite '{args.suite}' completed successfully!")
        return 0
    else:
        print(f"\n💥 Test suite '{args.suite}' failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
