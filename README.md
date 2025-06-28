# Ray MCP Server

A fast, standardized server for managing Ray clusters and distributed jobs via the Model Context Protocol (MCP).

## Features
- Start, monitor, and stop Ray clusters (single or multi-node)
- Submit, track, and debug distributed jobs
- Retrieve logs and cluster health info
- Optimized for CI and local development

## Quick Start

```bash
# Clone and install
 git clone https://github.com/pradeepiyer/ray-mcp
 cd ray-mcp
 uv sync --all-extras --dev
```

### Example Usage

```json
{
  "tool": "init_ray",
  "arguments": {"num_cpus": 4}
}
{
  "tool": "submit_job",
  "arguments": {"entrypoint": "python examples/simple_job.py"}
}
{
  "tool": "inspect_ray",
  "arguments": {}
}
```

## Testing

- Run all tests: `uv run pytest tests/`
- Unit only: `uv run pytest tests/ -k "not e2e"`
- E2E only: `uv run pytest tests/test_e2e_integration.py`
- Coverage: `uv run pytest tests/ --cov=ray_mcp --cov-report=html`

## Project Structure

```
mcp/
├── ray_mcp/      # Core server code
├── tests/        # Test suite
├── examples/     # Example scripts (simple_job.py)
├── docs/         # Documentation
└── scripts/      # Utilities
```

## Documentation
- [Tools Reference](docs/TOOLS.md)
- [Configuration Guide](docs/CONFIGURATION.md)
- [Development Guide](docs/DEVELOPMENT.md)
- [Examples](docs/EXAMPLES.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

## Contributing
- Fork, branch, and submit a PR
- Run all tests before submitting

## License
See LICENSE file.

## Support
- See [Troubleshooting](docs/TROUBLESHOOTING.md)
- Open an issue on GitHub
