# Development

## Architecture

```
ray_mcp/
├── __init__.py          # Package initialization
├── main.py              # MCP server entry point and handlers
├── ray_manager.py       # Core Ray cluster management logic
├── tools.py             # Individual tool function implementations
└── types.py             # Type definitions

examples/
├── simple_job.py        # Basic Ray job example
└── actor_example.py     # Ray actor usage example

tests/
├── test_mcp_tools.py           # MCP tool call tests
├── test_ray_manager.py         # Ray manager unit tests
├── test_ray_manager_methods.py # Detailed method tests
├── test_integration.py         # Integration tests
└── README.md                   # Test documentation

config/
├── claude_desktop_config.json # Claude Desktop configuration
├── mcp_server_config.json     # Comprehensive config examples
└── README.md                  # Configuration guide
```

### Key Components

- **MCP Server**: Main server handling MCP protocol communication
- **RayManager**: Core class managing Ray cluster operations
- **Tool Functions**: Individual async functions for each MCP tool
- **Error Handling**: Comprehensive error handling and status reporting

## Setup for Development

### Prerequisites
- Python 3.8 or higher
- Ray 2.30.0 or higher (current latest: 2.47.1)
- MCP SDK 1.0.0 or higher

### Install from source
```bash
git clone https://github.com/pradeepiyer/ray-mcp.git
cd ray-mcp
pip install -e .
```

### Install dependencies only
```bash
pip install -r requirements.txt
```

## Running Tests
```bash
pip install -e .
pytest tests/
```

### Test Categories
- **Unit tests**: `test_ray_manager.py`, `test_ray_manager_methods.py`
- **Integration tests**: `test_integration.py`, `test_mcp_tools.py`
- **End-to-end tests**: `test_e2e_integration.py`

## Code Quality

### Code Formatting
```bash
black ray_mcp/
isort ray_mcp/
```

### Type Checking
```bash
pyright .
```

### Linting
```bash
ruff check ray_mcp/
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make changes with tests
4. Ensure tests pass (`pytest tests/`)
5. Format code (`black . && isort .`)
6. Submit a pull request

### Contribution Guidelines
- Add tests for new functionality
- Follow existing code style
- Update documentation as needed
- Ensure all tests pass

## Release Process

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Create release PR
4. Tag release after merge
5. GitHub Actions will handle PyPI deployment

## Debugging

### Common Development Issues

1. **Ray import errors**: Ensure Ray is properly installed
   ```bash
   pip install ray[default]
   ```

2. **MCP protocol issues**: Check server logs and client configuration
   ```bash
   ray-mcp --log-level DEBUG
   ```

3. **Test failures**: Run specific test files
   ```bash
   pytest tests/test_specific_module.py -v
   ```

### Debugging Tools

- Ray Dashboard: `http://localhost:8265`
- MCP Server logs: Check stdout/stderr
- Ray logs: Usually in `/tmp/ray/session_*/logs/` 