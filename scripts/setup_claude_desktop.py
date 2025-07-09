#!/usr/bin/env python3
"""
Setup script for Claude Desktop to install cloud provider dependencies.

This script automatically installs the necessary dependencies for ray-mcp
cloud provider support in Claude Desktop environments.
"""

import sys
import subprocess
import os
import asyncio
from pathlib import Path


async def check_environment():
    """Check current environment and what's needed."""
    print("🔍 Checking current environment...")
    
    # Try to import ray_mcp to check if it's installed
    try:
        import ray_mcp
        print(f"✅ ray-mcp is installed at: {ray_mcp.__file__}")
        
        # Get the environment check
        from ray_mcp.managers.unified_manager import RayUnifiedManager
        unified_manager = RayUnifiedManager()
        env_result = await unified_manager.check_environment()
        
        return env_result
    except ImportError:
        print("❌ ray-mcp is not installed")
        return None


def find_python_executable():
    """Find the best Python executable to use."""
    # Prefer the current executable
    current_python = sys.executable
    print(f"📍 Using Python: {current_python}")
    return current_python


def install_dependencies(python_exe: str, packages: list):
    """Install missing dependencies."""
    print(f"📦 Installing dependencies: {packages}")
    
    for package in packages:
        print(f"  Installing {package}...")
        try:
            result = subprocess.run(
                [python_exe, "-m", "pip", "install", package],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode == 0:
                print(f"  ✅ {package} installed successfully")
            else:
                print(f"  ❌ Failed to install {package}: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            print(f"  ⏰ Installation of {package} timed out")
            return False
        except Exception as e:
            print(f"  ❌ Error installing {package}: {e}")
            return False
    
    return True


def install_with_uv(packages: list):
    """Try to install with uv if available."""
    print("🚀 Trying to install with uv...")
    
    # Check if uv is available
    try:
        result = subprocess.run(["uv", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            print("  uv not found, falling back to pip")
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("  uv not found, falling back to pip")
        return False
    
    # Install with uv
    for package in packages:
        print(f"  Installing {package} with uv...")
        try:
            result = subprocess.run(
                ["uv", "add", package],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                print(f"  ✅ {package} installed successfully with uv")
            else:
                print(f"  ❌ Failed to install {package} with uv: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            print(f"  ⏰ uv installation of {package} timed out")
            return False
        except Exception as e:
            print(f"  ❌ Error installing {package} with uv: {e}")
            return False
    
    return True


async def main():
    """Main setup function."""
    print("🎯 Ray MCP Claude Desktop Setup")
    print("=" * 40)
    
    # Check current environment
    env_result = await check_environment()
    
    if not env_result:
        print("❌ ray-mcp is not installed. Please install it first:")
        print("   pip install ray-mcp")
        print("   or: uv add ray-mcp")
        return 1
    
    # Determine what needs to be installed
    packages_to_install = []
    
    # Check GKE dependencies
    gke_deps = env_result.get("dependencies", {}).get("gke", {})
    if not gke_deps.get("python_sdk", False):
        packages_to_install.append("ray-mcp[gke]")
        print("📋 GKE Python SDK needed")
    
    # Check EKS dependencies
    eks_deps = env_result.get("dependencies", {}).get("eks", {})
    if not eks_deps.get("python_sdk", False):
        packages_to_install.append("ray-mcp[eks]")
        print("📋 EKS Python SDK needed")
    
    if not packages_to_install:
        print("🎉 All cloud dependencies are already installed!")
        
        # Show authentication status
        auth_info = env_result.get("authentication", {})
        for provider, auth in auth_info.items():
            if any(auth.values()):
                print(f"✅ {provider.upper()} authentication is configured")
            else:
                print(f"⚠️  {provider.upper()} authentication not configured")
        
        return 0
    
    print(f"\n📦 Need to install: {packages_to_install}")
    
    # Try uv first, then fall back to pip
    success = False
    
    # Method 1: Try uv
    if len(packages_to_install) == 1 and packages_to_install[0] in ["ray-mcp[gke]", "ray-mcp[eks]"]:
        # For single provider, try uv with extras
        provider = packages_to_install[0].split("[")[1].split("]")[0]
        try:
            print(f"🚀 Trying uv sync --extra {provider}...")
            result = subprocess.run(
                ["uv", "sync", "--extra", provider],
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                print(f"✅ Successfully installed {provider} dependencies with uv")
                success = True
            else:
                print(f"❌ uv sync failed: {result.stderr}")
        except Exception as e:
            print(f"❌ uv sync failed: {e}")
    
    # Method 2: Fall back to pip
    if not success:
        python_exe = find_python_executable()
        success = install_dependencies(python_exe, packages_to_install)
    
    if success:
        print("\n🎉 Installation completed successfully!")
        print("\n📋 Next steps:")
        print("1. Restart Claude Desktop")
        print("2. Test the installation with: check_environment")
        
        # Show authentication setup instructions
        print("\n🔐 Authentication setup:")
        if "ray-mcp[gke]" in packages_to_install:
            print("  For GKE: gcloud auth login && gcloud config set project YOUR_PROJECT")
        if "ray-mcp[eks]" in packages_to_install:
            print("  For EKS: aws configure")
        
        return 0
    else:
        print("\n❌ Installation failed!")
        print("\n🔧 Manual installation options:")
        for package in packages_to_install:
            print(f"  pip install '{package}'")
        print("\n💡 Or install all cloud providers:")
        print("  pip install 'ray-mcp[cloud]'")
        print("  uv sync --extra cloud")
        
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Installation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1) 