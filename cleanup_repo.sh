#!/bin/bash

# Repository Cleanup Script
# Run this script to clean up the repository before committing to GitHub

set -e  # Exit on any error

echo "🧹 Starting repository cleanup..."

# Remove Python cache files
echo "🗑️  Removing Python cache files..."
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Remove build artifacts
echo "🗑️  Removing build artifacts..."
rm -rf ray_mcp.egg-info/ 2>/dev/null || true
rm -rf mcp_ray.egg-info/ 2>/dev/null || true
rm -rf mcp_ray_server.egg-info/ 2>/dev/null || true
rm -rf .pytest_cache/ 2>/dev/null || true
rm -rf build/ 2>/dev/null || true
rm -rf dist/ 2>/dev/null || true

# Remove virtual environment
echo "🗑️  Removing virtual environment..."
rm -rf .venv/ 2>/dev/null || true

# Remove system files
echo "🗑️  Removing system files..."
find . -name ".DS_Store" -delete 2>/dev/null || true
find . -name "Thumbs.db" -delete 2>/dev/null || true
find . -name "*~" -delete 2>/dev/null || true

# Remove development/testing files
echo "🗑️  Removing development files..."
rm -f TEST_SUMMARY.md 2>/dev/null || true
rm -f test_installation.py 2>/dev/null || true
rm -f run_tests.py 2>/dev/null || true
rm -rf ~/ 2>/dev/null || true

# Remove this cleanup script and checklist (they're not needed in the final repo)
echo "🗑️  Removing cleanup files..."
rm -f CLEANUP_CHECKLIST.md 2>/dev/null || true
rm -f cleanup_repo.sh 2>/dev/null || true

# Create .gitignore if it doesn't exist
if [ ! -f .gitignore ]; then
    echo "📝 Creating .gitignore..."
    cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
.venv/
venv/
ENV/
env/

# Testing
.pytest_cache/
.coverage
htmlcov/

# IDEs
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
*~

# Personal configs
config/claude_desktop_config.json.local
config/personal_*

# Logs
*.log
ray_logs/

# Package artifacts
ray_mcp.egg-info/
mcp_ray.egg-info/
mcp_ray_server.egg-info/
EOF
else
    echo "✅ .gitignore already exists"
fi

# Update config files to remove personal paths
echo "📝 Updating configuration files..."

# Update Claude Desktop config to use placeholders
if [ -f "config/claude_desktop_config.json" ]; then
    echo "📝 Updating Claude Desktop config..."
    cat > config/claude_desktop_config.json << 'EOF'
{
  "mcpServers": {
    "ray-mcp": {
      "command": "/path/to/your/venv/bin/ray-mcp",
      "args": [],
      "env": {
        "RAY_ADDRESS": "",
        "RAY_DASHBOARD_HOST": "0.0.0.0"
      }
    }
  }
}
EOF
fi

# Update MCP server config to use placeholders
if [ -f "config/mcp_server_config.json" ]; then
    echo "📝 Updating MCP server config..."
    # Replace any absolute paths with placeholders
    sed -i.bak 's|/Users/[^/]*/[^"]*|/path/to/your/project|g' config/mcp_server_config.json 2>/dev/null || true
    sed -i.bak 's|mcp-ray-server|ray-mcp|g' config/mcp_server_config.json 2>/dev/null || true
    sed -i.bak 's|mcp-ray|ray-mcp|g' config/mcp_server_config.json 2>/dev/null || true
    rm -f config/mcp_server_config.json.bak 2>/dev/null || true
fi

echo ""
echo "✅ Repository cleanup completed!"
echo ""
echo "📋 Next steps:"
echo "1. Review the updated configuration files in config/"
echo "2. Update README.md to remove any personal references"
echo "3. Run tests to ensure everything still works: pytest"
echo "4. Initialize git repository: git init"
echo "5. Add files: git add ."
echo "6. Commit: git commit -m 'Initial commit'"
echo ""
echo "⚠️  Remember to:"
echo "- Review all files for personal information"
echo "- Test installation from scratch: pip install -e ."
echo "- Verify console script works: ray-mcp --help"
echo "- Update documentation with generic paths" 