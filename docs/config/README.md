# Configuration Files

Example configuration files for MCP clients.

## Files

**`claude_desktop_config.json`**
Example configuration for Claude Desktop application.

**`mcp_server_config.json`**
Generic MCP server configuration for other MCP clients.

## Usage

1. Copy the appropriate config file to your MCP client's configuration directory
2. Update the `command` and `args` to use `uv run ray-mcp`
3. Set the `cwd` path to your ray-mcp project root directory
4. Set environment variables as needed for your setup

## Important Notes

- **Working Directory (`cwd`)**: Set to your ray-mcp project root directory
- **Command**: Use `uv run ray-mcp` for modern uv-based execution
- **Google Cloud**: Set `GOOGLE_APPLICATION_CREDENTIALS` environment variable
- **Amazon Web Services**: Set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_DEFAULT_REGION` environment variables
- **Enhanced Output**: Set `RAY_MCP_ENHANCED_OUTPUT` to `"true"` for better debugging

## Client Locations

- **Claude Desktop**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Other clients**: Refer to client documentation

See [CONFIGURATION.md](../CONFIGURATION.md) for detailed setup instructions.