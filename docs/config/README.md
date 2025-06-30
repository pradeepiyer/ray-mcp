# Configuration Files

This directory contains example configuration files for various MCP clients.

## Files

### `claude_desktop_config.json`
Example configuration for Claude Desktop application. Copy and modify for your setup.

### `mcp_server_config.json`
Generic MCP server configuration that can be adapted for other MCP clients.

## Usage

1. Copy the appropriate config file to your MCP client's configuration directory
2. Update the `cwd` path to point to your ray-mcp installation
3. Adjust command and arguments as needed for your environment

## Client-Specific Locations

- **Claude Desktop**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Other clients**: Refer to client documentation for configuration file location

See [CONFIGURATION.md](../CONFIGURATION.md) for detailed setup instructions. 