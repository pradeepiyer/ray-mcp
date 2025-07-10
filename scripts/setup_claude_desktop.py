#!/usr/bin/env python3
"""
Setup script for Claude Desktop integration with Ray MCP.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

# Constants
CLAUDE_DESKTOP_CONFIG_PATHS = {
    "Darwin": "~/Library/Application Support/Claude/claude_desktop_config.json",
    "Linux": "~/.config/claude/claude_desktop_config.json", 
    "Windows": "~\\AppData\\Roaming\\Anthropic\\Claude\\claude_desktop_config.json"
}

def get_platform() -> str:
    """Get the current platform."""
    import platform
    return platform.system()

def get_claude_config_path() -> Path:
    """Get the Claude Desktop config path for the current platform."""
    platform_name = get_platform()
    config_path = CLAUDE_DESKTOP_CONFIG_PATHS.get(platform_name)
    if not config_path:
        raise RuntimeError(f"Unsupported platform: {platform_name}")
    return Path(config_path).expanduser()

def load_claude_config() -> Dict[str, Any]:
    """Load existing Claude Desktop configuration."""
    config_path = get_claude_config_path()
    if config_path.exists():
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}

def save_claude_config(config: Dict[str, Any]) -> None:
    """Save Claude Desktop configuration."""
    config_path = get_claude_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

def check_python_version() -> bool:
    """Check if Python version is compatible."""
    version = sys.version_info
    return version.major >= 3 and version.minor >= 10

def check_uv_installed() -> bool:
    """Check if uv is installed."""
    return shutil.which("uv") is not None

def check_dependencies() -> Dict[str, Any]:
    """Check system dependencies."""
    results = {
        "python_version": check_python_version(),
        "uv_installed": check_uv_installed(),
        "platform": get_platform(),
        "dependencies": {
            "gke": {
                "python_sdk": True,  # Assume available in base installation
                "cli": shutil.which("gcloud") is not None,
                "kubectl": shutil.which("kubectl") is not None,
            }
        }
    }
    return results

def install_dependencies() -> None:
    """Install necessary dependencies."""
    print("📦 Installing Ray MCP dependencies...")
    
    # Check environment
    env_result = check_dependencies()
    packages_to_install = []
    
    if not env_result["python_version"]:
        print("❌ Python 3.10+ required")
        sys.exit(1)
    
    if not env_result["uv_installed"]:
        print("❌ uv package manager required. Install from: https://docs.astral.sh/uv/getting-started/installation/")
        sys.exit(1)
    
    # Check GKE dependencies
    gke_deps = env_result.get("dependencies", {}).get("gke", {})
    if not gke_deps.get("python_sdk", False):
        packages_to_install.append("ray-mcp[gke]")
        print("📋 GKE Python SDK needed")
    
    # Install base package if needed
    if not packages_to_install:
        packages_to_install.append("ray-mcp")
        print("📋 Installing base Ray MCP package")
    
    # Install packages
    for package in packages_to_install:
        print(f"📦 Installing {package}...")
        try:
            subprocess.run([
                "uv", "pip", "install", package, "--upgrade"
            ], check=True, capture_output=True)
            print(f"✅ {package} installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install {package}: {e}")
            sys.exit(1)
    
    # Show next steps for cloud provider setup
    if len(packages_to_install) == 1 and packages_to_install[0] in ["ray-mcp[gke]"]:
        print("\n🔧 Cloud Provider Setup:")
        print("  For GKE: gcloud auth application-default login")
        print("  For local: minikube start")
        print("  For any: kubectl config current-context")
    
    print("\n✅ Dependencies installed successfully!")

def setup_claude_desktop() -> None:
    """Setup Claude Desktop configuration."""
    print("🔧 Setting up Claude Desktop configuration...")
    
    # Load existing config
    config = load_claude_config()
    
    # Ensure mcpServers section exists
    if "mcpServers" not in config:
        config["mcpServers"] = {}
    
    # Add Ray MCP server configuration
    ray_mcp_config = {
        "command": "python",
        "args": ["-m", "ray_mcp.main"],
        "env": {
            "RAY_MCP_LOG_LEVEL": "INFO"
        }
    }
    
    config["mcpServers"]["ray-mcp"] = ray_mcp_config
    
    # Save configuration
    save_claude_config(config)
    
    # Show authentication instructions
    print("\n🔐 Authentication Setup:")
    print("  For GKE: gcloud auth application-default login")
    print("  For local: kubectl config current-context")
    
    print(f"\n✅ Claude Desktop configuration updated!")
    print(f"📁 Config file: {get_claude_config_path()}")
    print("\n🔄 Please restart Claude Desktop to apply changes.")

def main():
    """Main setup function."""
    print("🚀 Ray MCP Setup for Claude Desktop")
    print("=" * 50)
    
    try:
        # Check and install dependencies
        install_dependencies()
        
        # Setup Claude Desktop
        setup_claude_desktop()
        
        print("\n🎉 Setup completed successfully!")
        print("\n📚 Next steps:")
        print("  1. Restart Claude Desktop")
        print("  2. Try: 'Initialize a local Ray cluster'")
        print("  3. Check docs/EXAMPLES.md for more examples")
        
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 