#!/usr/bin/env python3
"""Test runner for Ray MCP with different test suites.

This script provides convenient commands for running different test categories:
- Unit tests: Fast, fully mocked tests
- E2E tests: End-to-end integration tests
- Smoke tests: Quick validation tests
- All tests: Complete test suite

Usage:
    python test_runner.py unit          # Run unit tests only
    python test_runner.py e2e           # Run E2E tests only
    python test_runner.py smoke         # Run smoke tests only
    python test_runner.py all           # Run all tests
    python test_runner.py --help        # Show help
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path


class TestRunner:
    """Test runner for Ray MCP test suites."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        
    def run_command(self, cmd: list[str], description: str) -> bool:
        """Run a command and return success status."""
        print(f"\n🚀 {description}")
        print(f"Command: {' '.join(cmd)}")
        print("-" * 60)
        
        start_time = time.time()
        result = subprocess.run(cmd, cwd=self.project_root)
        duration = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ {description} completed successfully in {duration:.1f}s")
            return True
        else:
            print(f"❌ {description} failed after {duration:.1f}s")
            return False
    
    def run_unit_tests(self) -> bool:
        """Run fast unit tests with full mocking."""
        cmd = [
            "uv", "run", "pytest", 
            "tests/unit/",
            "-m", "unit",
            "--tb=short",
            "-v"
        ]
        return self.run_command(cmd, "Running unit tests")
    
    def run_e2e_tests(self) -> bool:
        """Run end-to-end integration tests."""
        cmd = [
            "uv", "run", "pytest",
            "tests/e2e/", 
            "-m", "e2e",
            "--tb=short",
            "-v",
            "-s"  # Don't capture output for E2E tests
        ]
        return self.run_command(cmd, "Running E2E tests")
    
    def run_smoke_tests(self) -> bool:
        """Run quick smoke tests for basic validation."""
        cmd = [
            "uv", "run", "pytest",
            "-m", "smoke or (unit and fast)",
            "--tb=short",
            "-v"
        ]
        return self.run_command(cmd, "Running smoke tests")
    
    def run_all_tests(self) -> bool:
        """Run the complete test suite."""
        print("🎯 Running complete Ray MCP test suite")
        print("=" * 60)
        
        success = True
        
        # Run unit tests first (fast feedback)
        if not self.run_unit_tests():
            success = False
        
        # Run E2E tests (slower but critical)
        if not self.run_e2e_tests():
            success = False
            
        return success
    
    def check_dependencies(self) -> bool:
        """Check that required dependencies are available."""
        print("🔍 Checking test dependencies...")
        
        # Check pytest
        result = subprocess.run(
            ["uv", "run", "pytest", "--version"], 
            capture_output=True, 
            text=True
        )
        if result.returncode != 0:
            print("❌ pytest not available")
            return False
        print(f"✅ {result.stdout.strip()}")
        
        # Check Ray (optional but recommended for E2E tests)
        result = subprocess.run(
            ["uv", "run", "python", "-c", "import ray; print(f'Ray {ray.__version__}')"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"✅ {result.stdout.strip()}")
        else:
            print("⚠️  Ray not available (E2E tests may fail)")
        
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
                capture_output=True, text=True
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                unit_count = len([l for l in lines if 'test_' in l])
                print(f"Unit tests: {unit_count} tests in tests/unit/")
            
            # E2E tests  
            result = subprocess.run(
                ["uv", "run", "pytest", "tests/e2e/", "--collect-only", "-q"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                e2e_count = len([l for l in lines if 'test_' in l])
                print(f"E2E tests: {e2e_count} tests in tests/e2e/")
                
        except Exception as e:
            print(f"Could not count tests: {e}")
        
        print("\nTest Categories:")
        print("- unit: Fast tests with full mocking (< 1s each)")
        print("- e2e: Integration tests without mocking (5-60s each)")
        print("- smoke: Quick validation tests for CI/CD")
        
        print("\nUsage Examples:")
        print("  python test_runner.py unit     # Fast feedback during development")
        print("  python test_runner.py e2e      # Validate real functionality")
        print("  python test_runner.py smoke    # Quick health check")
        print("  python test_runner.py all      # Complete validation")


def main():
    """Main test runner entry point."""
    parser = argparse.ArgumentParser(
        description="Ray MCP Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_runner.py unit          # Fast unit tests
  python test_runner.py e2e           # Integration tests  
  python test_runner.py smoke         # Quick smoke tests
  python test_runner.py all           # Complete test suite
  python test_runner.py info          # Show test information
        """
    )
    
    parser.add_argument(
        'suite',
        choices=['unit', 'e2e', 'smoke', 'all', 'info'],
        help='Test suite to run'
    )
    
    parser.add_argument(
        '--check-deps',
        action='store_true',
        help='Check dependencies before running tests'
    )
    
    args = parser.parse_args()
    
    runner = TestRunner()
    
    # Check dependencies if requested
    if args.check_deps:
        if not runner.check_dependencies():
            return 1
    
    # Handle info command
    if args.suite == 'info':
        runner.show_test_info()
        return 0
    
    # Run the requested test suite
    success = False
    
    if args.suite == 'unit':
        success = runner.run_unit_tests()
    elif args.suite == 'e2e':
        success = runner.run_e2e_tests() 
    elif args.suite == 'smoke':
        success = runner.run_smoke_tests()
    elif args.suite == 'all':
        success = runner.run_all_tests()
    
    if success:
        print(f"\n🎉 Test suite '{args.suite}' completed successfully!")
        return 0
    else:
        print(f"\n💥 Test suite '{args.suite}' failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())