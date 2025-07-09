# Configuration Files

This directory contains example configuration files for various MCP clients.

## Files

### `claude_desktop_config.json`
Example configuration for Claude Desktop application. Copy and modify for your setup.

### `mcp_server_config.json`
Generic MCP server configuration that can be adapted for other MCP clients.

## Usage

1. Copy the appropriate config file to your MCP client's configuration directory
2. Update the `command` path to point to your ray-mcp installation's `.venv/bin/ray-mcp`
3. **IMPORTANT:** Set the `cwd` path to point to your ray-mcp project root directory
4. **Google Cloud**: Set `GOOGLE_APPLICATION_CREDENTIALS` environment variable to your service account key file path
5. Adjust other environment variables as needed for your setup

## Important Configuration Notes

- **Working Directory (`cwd`)**: This parameter is crucial for proper operation. Set it to your ray-mcp project root directory.
- **Command Path**: Use the full path to the ray-mcp executable in your virtual environment (`.venv/bin/ray-mcp`).
- **Google Cloud Authentication**: Set `GOOGLE_APPLICATION_CREDENTIALS` to the path of your service account JSON key file for GKE functionality.
- **Enhanced Output**: Set `RAY_MCP_ENHANCED_OUTPUT` to `"true"` for better debugging and user experience.

## Client-Specific Locations

- **Claude Desktop**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Other clients**: Refer to client documentation for configuration file location

See [CONFIGURATION.md](../CONFIGURATION.md) for detailed setup instructions. 