#!/bin/bash
# Ray MCP Testing Runner
set -e

echo "🚀 Ray MCP Testing Environment"
echo "=============================="

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check what mode to run
if [ "$1" = "local" ]; then
    echo "Running local mode tests..."
    python "$SCRIPT_DIR/test_local_mode.py"
elif [ "$1" = "gke" ]; then
    echo "Running GKE mode tests..."
    python "$SCRIPT_DIR/test_gke_mode.py"
elif [ "$1" = "both" ]; then
    echo "Running both local and GKE tests..."
    python "$SCRIPT_DIR/test_local_mode.py"
    python "$SCRIPT_DIR/test_gke_mode.py"
else
    echo "Usage: $0 [local|gke|both]"
    echo ""
    echo "Options:"
    echo "  local - Run local Ray testing"
    echo "  gke   - Run GKE testing (requires GCP setup)"
    echo "  both  - Run both test suites"
    exit 1
fi
