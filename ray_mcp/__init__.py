"""Ray MCP Server - Model Context Protocol server for Ray distributed computing.

This package provides a Model Context Protocol (MCP) server that enables LLM agents
to interact with Ray clusters for distributed computing tasks. The server exposes
high-level tools for cluster management, job submission, monitoring, and debugging.

Key Features:
    - Cluster Management: Start, connect to, and stop Ray clusters
    - Job Management: Submit, monitor, and cancel distributed jobs
    - Debugging: Log retrieval and job debugging tools

The server supports both single-node and multi-node Ray clusters, with automatic
resource management and worker node configuration. It provides comprehensive error
handling and detailed status reporting for all operations.

Usage:
    The server can be run as a standalone process or integrated into existing
    MCP-compatible applications. It communicates via stdio and provides JSON
    responses for all operations.

Environment Variables:
    - RAY_MCP_ENHANCED_OUTPUT: When set to "true", enables LLM-enhanced responses
      with summaries, context, and suggested next steps

Dependencies:
    - Ray: The distributed computing framework
    - MCP: Model Context Protocol libraries
    - Python 3.10+: Required for async/await support

For more information, see the documentation in the docs/ directory.
"""

# Get version dynamically from package metadata (populated from pyproject.toml)
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("ray-mcp")
except PackageNotFoundError:
    # Fallback when package not installed (e.g., development mode)
    __version__ = "dev"

__author__ = "ray-mcp authors"
__email__ = "ray-mcp@example.com"
