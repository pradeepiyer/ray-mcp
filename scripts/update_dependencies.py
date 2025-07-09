#!/usr/bin/env python3
"""
Dependency update helper script for ray-mcp.

This script helps automate dependency updates while maintaining safety.
"""

import subprocess
import sys
import json
from pathlib import Path


def run_command(cmd, cwd=None):
    """Run a command and return the result."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, cwd=cwd
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def check_outdated_packages():
    """Check for outdated packages using uv."""
    print("🔍 Checking for outdated packages...")
    
    success, stdout, stderr = run_command("uv pip list --outdated")
    
    if success and stdout.strip():
        print("\n📦 Outdated packages found:")
        print(stdout)
        return True
    elif success:
        print("✅ All packages are up to date!")
        return False
    else:
        print(f"❌ Error checking packages: {stderr}")
        return False


def update_dependencies():
    """Update dependencies to latest compatible versions."""
    print("\n🔄 Updating dependencies...")
    
    # Update dev dependencies
    success, stdout, stderr = run_command("uv sync --dev --upgrade")
    
    if success:
        print("✅ Dependencies updated successfully!")
        print(stdout)
    else:
        print(f"❌ Error updating dependencies: {stderr}")
        return False
    
    return True


def run_tests():
    """Run tests to ensure updates didn't break anything."""
    print("\n🧪 Running tests to verify updates...")
    
    success, stdout, stderr = run_command("make test")
    
    if success:
        print("✅ All tests passed!")
        return True
    else:
        print(f"❌ Tests failed: {stderr}")
        return False


def run_format_check():
    """Run formatting and type checking."""
    print("\n🎨 Running format and type checking...")
    
    success, stdout, stderr = run_command("make format")
    
    if success:
        print("✅ Formatting and type checking passed!")
        return True
    else:
        print(f"❌ Formatting or type checking failed: {stderr}")
        return False


def main():
    """Main function to orchestrate dependency updates."""
    print("🚀 Ray-MCP Dependency Update Helper")
    print("=" * 40)
    
    # Check if we're in the right directory
    if not Path("pyproject.toml").exists():
        print("❌ Please run this script from the project root directory")
        sys.exit(1)
    
    # Check for outdated packages
    has_outdated = check_outdated_packages()
    
    if not has_outdated:
        print("\n🎉 No updates needed!")
        return
    
    # Ask user if they want to update
    response = input("\n❓ Do you want to update dependencies? (y/N): ")
    if response.lower() not in ['y', 'yes']:
        print("👋 Update cancelled.")
        return
    
    # Update dependencies
    if not update_dependencies():
        sys.exit(1)
    
    # Run tests
    if not run_tests():
        print("\n⚠️  Tests failed after update. You may need to review changes.")
        sys.exit(1)
    
    # Run format check
    if not run_format_check():
        print("\n⚠️  Format/type checking failed after update. You may need to review changes.")
        sys.exit(1)
    
    print("\n🎉 Dependencies updated successfully!")
    print("💡 Consider committing these changes:")
    print("   git add uv.lock pyproject.toml")
    print("   git commit -m 'chore: update dependencies'")


if __name__ == "__main__":
    main() 