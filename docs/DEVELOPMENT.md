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
git clone https://github.com/ray-mcp/ray-mcp.git
cd ray-mcp
pip install -e .
```

### Install dependencies only
```bash
pip install -r requirements.txt
```

## Running Tests

### Test Categories

We have organized tests into different categories for optimal development workflow:

- **Unit tests**: Fast, isolated tests (`test_ray_manager.py`, `test_ray_manager_methods.py`)
- **Integration tests**: Medium-speed tests with some Ray interaction (`test_integration.py`, `test_mcp_tools.py`)
- **End-to-end tests**: Comprehensive, slow tests with full Ray workflows (`test_e2e_integration.py`)

### Quick Test Commands

```bash
# Fast development testing (excludes e2e tests) - recommended for daily development
make test

# Smoke tests - minimal verification (30 seconds)
make test-smoke

# End-to-end tests only - for major changes (5-10 minutes)
make test-e2e

# Complete test suite - for releases (10-15 minutes)
make test-full

# Smart test runner - automatically chooses appropriate tests based on changes
make test-smart
```

### Manual Test Execution

```bash
# Fast tests (excludes e2e) - typical development workflow
pytest tests/ -m "not e2e and not slow" --tb=short -v

# Only end-to-end tests
pytest tests/ -m "e2e" --tb=short -v

# Only smoke tests
pytest tests/ -m "smoke" --tb=short -v

# All tests
pytest tests/ --tb=short -v
```

### When to Run Different Test Suites

- **Daily Development**: `make test` (fast tests, ~1-2 minutes)
- **Before Committing**: `make test-smart` (intelligent test selection)
- **Major Changes**: `make test-e2e` (comprehensive e2e tests)
- **Before Releases**: `make test-full` (complete test suite)
- **Quick Verification**: `make test-smoke` (basic functionality check)

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
4. Ensure tests pass (`make test`)
5. For major changes, run e2e tests (`make test-e2e`)
6. Format code (`black . && isort .`)
7. Submit a pull request

### Contribution Guidelines
- Add tests for new functionality
- Follow existing code style
- Update documentation as needed
- Ensure all tests pass
- Use `make test-smart` to run appropriate tests for your changes

## Release Process

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Run full test suite (`make test-full`)
4. Create release PR
5. Tag release after merge
6. GitHub Actions will handle PyPI deployment

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