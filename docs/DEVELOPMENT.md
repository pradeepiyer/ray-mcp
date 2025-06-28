# Ray MCP Server Development Guide

This document provides comprehensive information for developers working on the Ray MCP Server.

## Development Setup

### Prerequisites

- Python 3.10 or higher
- UV package manager
- Git

### Initial Setup

```bash
# Clone the repository
git clone <repository-url>
cd ray-mcp

# Create virtual environment and install dependencies
uv sync

# Install the package in development mode
uv pip install -e .

# Activate virtual environment
source .venv/bin/activate
```

### Development Dependencies

The project uses UV for dependency management with the following development dependencies:

```toml
[tool.uv]
dev-dependencies = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-mock>=3.10.0",
    "pytest-cov>=4.0.0",
    "black>=24.0.0",
    "isort>=5.12.0",
    "pyright>=1.1.0",
]
```

## Project Structure

```
ray-mcp/
├── ray_mcp/                 # Main package
│   ├── __init__.py
│   ├── main.py              # MCP server entry point
│   ├── tool_registry.py     # Centralized tool registry
│   ├── ray_manager.py       # Ray cluster management
│   └── worker_manager.py    # Worker node management
├── examples/                # Example applications
├── tests/                   # Test suite
├── docs/                    # Documentation
├── scripts/                 # Utility scripts
├── pyproject.toml          # Project configuration
└── Makefile                # Development commands
```

## Architecture Overview

### MCP Server Architecture

The Ray MCP Server uses a **dispatcher pattern** for reliable tool routing:

1. **Centralized Tool Registry** (`tool_registry.py`): All tool definitions, schemas, and handlers
2. **Single Dispatcher** (`main.py`): Routes all tool calls through `dispatch_tool_call()`
3. **Ray Manager** (`ray_mcp/ray_manager.py`): Core Ray cluster management logic
4. **Worker Manager** (`ray_mcp/worker_manager.py`): Multi-node cluster worker management

### Key Components

#### Tool Registry (`ray_mcp/tool_registry.py`)

- Centralized tool registration and metadata
- Parameter validation and filtering
- Enhanced output mode support
- Error handling and response formatting

#### Ray Manager (`ray_mcp/ray_manager.py`)

- Ray cluster initialization and management
- Job submission and monitoring
- Actor management
- Log retrieval and analysis
- Multi-node cluster support

#### Worker Manager (`ray_mcp/worker_manager.py`)

- Worker node process management
- Worker status monitoring
- Resource allocation tracking
- Worker lifecycle management

## Development Commands

### Testing

```bash
# Run all tests
uv run pytest

# Run fast tests (excludes e2e)
make test-fast

# Run e2e tests with cleanup
make test-e2e

# Run specific test categories
uv run pytest tests/test_ray_manager.py
uv run pytest tests/test_multi_node_cluster.py
uv run pytest tests/test_e2e_integration.py

# Run tests with coverage
uv run pytest --cov=ray_mcp tests/
```

### Code Quality

```bash
# Run all linting checks
make lint

# Format code
make format

# Type checking
uv run pyright ray_mcp/

# Tool function specific linting
make lint-tool-functions
```

### Package Management

```bash
# Sync dependencies
uv sync

# Update lock file
uv lock

# Check for updates
uv tree
uv pip check
```

## Testing Strategy

### Test Categories

1. **Unit Tests**: Fast, isolated tests for individual components
2. **Integration Tests**: Medium-speed tests with Ray interaction
3. **End-to-End Tests**: Comprehensive tests with full Ray workflows
4. **Multi-Node Tests**: Tests for multi-node cluster functionality

### Test Files

- `tests/test_ray_manager.py`: Core Ray management functionality
- `tests/test_multi_node_cluster.py`: Multi-node cluster features
- `tests/test_e2e_integration.py`: End-to-end workflow tests
- `tests/test_main.py`: MCP server functionality
- `tests/test_worker_manager.py`: Worker node management
- `tests/test_integration.py`: Integration test scenarios

### Test Configuration

```python
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --strict-markers
    --strict-config
    --tb=short
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    smoke: Smoke tests
```

## Code Style and Standards

### Code Formatting

The project uses Black for code formatting and isort for import sorting:

```bash
# Format code
uv run black ray_mcp/ examples/ tests/

# Sort imports
uv run isort ray_mcp/ examples/ tests/
```

### Type Checking

Type checking is performed with Pyright:

```bash
uv run pyright ray_mcp/
```

### Linting Rules

- Use type hints for all function parameters and return values
- Follow PEP 8 style guidelines
- Use descriptive variable and function names
- Add docstrings for all public functions and classes
- Avoid using `locals()` in tool functions (enforced by custom linting)

## Adding New Tools

### 1. Define Tool Schema

Add the tool definition to `ray_mcp/tool_registry.py`:

```python
self._register_tool(
    name="new_tool",
    description="Description of the new tool",
    schema={
        "type": "object",
        "properties": {
            "param1": {
                "type": "string",
                "description": "Description of parameter"
            }
        },
        "required": ["param1"]
    },
    handler=self._new_tool_handler,
)
```

### 2. Implement Handler

Add the handler method to the `ToolRegistry` class:

```python
async def _new_tool_handler(self, **kwargs) -> Dict[str, Any]:
    """Handler for new_tool."""
    return await self.ray_manager.new_tool_method(**kwargs)
```

### 3. Implement Core Logic

Add the core implementation to `ray_mcp/ray_manager.py`:

```python
async def new_tool_method(self, param1: str) -> Dict[str, Any]:
    """Implementation of the new tool."""
    try:
        # Implementation logic
        return {"status": "success", "result": "data"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

### 4. Add Tests

Create tests for the new tool:

```python
async def test_new_tool():
    """Test the new tool functionality."""
    manager = RayManager()
    result = await manager.new_tool_method("test_param")
    assert result["status"] == "success"
```

## Debugging

### Local Development

```bash
# Run server in debug mode
RAY_LOG_LEVEL=DEBUG python -m ray_mcp.main

# Run with enhanced output
RAY_MCP_ENHANCED_OUTPUT=true python -m ray_mcp.main
```

### Debug Configuration

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Debug Ray initialization
ray.init(log_to_driver=True)
```

### Common Debugging Scenarios

1. **Cluster Startup Issues**: Check port availability and resource conflicts
2. **Job Submission Problems**: Verify runtime environment and entrypoint
3. **Multi-Node Issues**: Check network connectivity and worker configuration
4. **Tool Routing Problems**: Verify tool registration in registry

## Performance Optimization

### Cluster Configuration

- Use appropriate object store memory for your workload
- Configure worker nodes based on resource requirements
- Monitor resource usage with `cluster_info`

### Code Optimization

- Use async/await patterns consistently
- Implement proper error handling and cleanup
- Optimize log retrieval for large outputs
- Use efficient data structures for large datasets

## Contributing

### Development Workflow

1. Create a feature branch from main
2. Implement changes with tests
3. Run all tests and linting checks
4. Update documentation as needed
5. Submit a pull request

### Code Review Checklist

- [ ] All tests pass
- [ ] Code follows style guidelines
- [ ] Type hints are complete
- [ ] Documentation is updated
- [ ] No new linting errors
- [ ] Performance impact is considered

### Release Process

1. Update version in `pyproject.toml`
2. Update changelog
3. Run full test suite
4. Create release tag
5. Build and publish package

## Troubleshooting

### Common Development Issues

1. **Import Errors**: Ensure virtual environment is activated
2. **Test Failures**: Check Ray cluster state and cleanup
3. **Linting Errors**: Run formatting tools and fix style issues
4. **Type Errors**: Add proper type hints and run type checker

### Environment Issues

```bash
# Reset development environment
make clean
uv sync
uv pip install -e .
```

### Ray Cluster Issues

```bash
# Clean up Ray processes
./scripts/ray_cleanup.sh

# Check Ray status
ray status
```

## Documentation

### Documentation Structure

- `README.md`: Main project documentation
- `docs/TOOLS.md`: Tool reference and usage
- `docs/EXAMPLES.md`: Example applications and workflows
- `docs/CONFIGURATION.md`: Configuration options
- `docs/DEVELOPMENT.md`: Development guide (this file)
- `docs/TROUBLESHOOTING.md`: Troubleshooting guide

### Updating Documentation

- Keep documentation in sync with code changes
- Update examples when adding new features
- Maintain consistent formatting and style
- Test documentation examples

## Best Practices

1. **Test-Driven Development**: Write tests before implementing features
2. **Type Safety**: Use type hints throughout the codebase
3. **Error Handling**: Implement comprehensive error handling
4. **Documentation**: Keep documentation up to date
5. **Code Review**: Review all changes before merging
6. **Performance**: Consider performance implications of changes
7. **Backward Compatibility**: Maintain compatibility when possible