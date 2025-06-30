# Development Guide

Setup and development instructions for Ray MCP contributors.

## Development Setup

### Prerequisites

- Python ≥ 3.10
- [uv](https://docs.astral.sh/uv/) package manager (recommended)
- Git

### Local Development

```bash
# Clone repository
git clone https://github.com/pradeepiyer/ray-mcp.git
cd ray-mcp

# Install with development dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows

# Verify installation
ray-mcp --help
```

### Alternative Setup (pip)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install in development mode
pip install -e ".[dev]"
```

## Project Structure

```
ray-mcp/
├── ray_mcp/                 # Main package
│   ├── __init__.py
│   ├── main.py             # MCP server entry point
│   ├── ray_manager.py      # Ray cluster operations
│   ├── tool_registry.py    # Tool definitions and handlers
│   ├── worker_manager.py   # Worker node management
│   └── logging_utils.py    # Logging and response formatting
├── tests/                  # Test suite
├── examples/               # Usage examples
├── docs/                   # Documentation
└── pyproject.toml         # Project configuration
```

## Development Workflow

### Code Style

The project uses automated formatting and linting:

```bash
# Format code
uv run black ray_mcp tests examples

# Sort imports
uv run isort ray_mcp tests examples

# Type checking
uv run pyright
```

### Running the Server

```bash
# Run server directly
uv run ray-mcp

# Run with enhanced output
RAY_MCP_ENHANCED_OUTPUT=true uv run ray-mcp

# Run with debug logging
RAY_MCP_LOG_LEVEL=DEBUG uv run ray-mcp
```

## Testing

### Test Suite

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=ray_mcp --cov-report=html

# Run specific test categories
uv run pytest tests/test_ray_manager.py
uv run pytest -k "test_init_cluster"
```

### Test Categories

- **Unit tests** - Individual component testing
- **Integration tests** - Multi-component workflows
- **End-to-end tests** - Full MCP server testing

### Manual Testing

```bash
# Test with MCP client simulator
uv run python -m ray_mcp.main

# Test individual tools
python -c "
import asyncio
from ray_mcp.ray_manager import RayManager
rm = RayManager()
result = asyncio.run(rm.init_cluster())
print(result)
"
```

## Debugging

### Logging Configuration

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('ray_mcp')
logger.setLevel(logging.DEBUG)
```

### Common Debug Scenarios

#### MCP Protocol Issues

```bash
# Enable MCP debug logging
export MCP_LOG_LEVEL=debug
uv run ray-mcp
```

#### Ray Cluster Issues

```bash
# Enable Ray debug output
export RAY_DISABLE_USAGE_STATS=1
export RAY_LOG_LEVEL=debug
uv run ray-mcp
```

#### Tool Execution Issues

```python
# Test tool directly
from ray_mcp.tool_registry import ToolRegistry
from ray_mcp.ray_manager import RayManager

registry = ToolRegistry(RayManager())
result = await registry.execute_tool("init_ray", {})
```

## Adding New Tools

### 1. Define Tool Schema

In `tool_registry.py`:

```python
self._register_tool(
    name="my_new_tool",
    description="Description of what the tool does",
    schema={
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "Parameter description"},
            "param2": {"type": "integer", "minimum": 1}
        },
        "required": ["param1"]
    },
    handler=self._my_new_tool_handler
)
```

### 2. Implement Handler

```python
async def _my_new_tool_handler(self, **kwargs) -> Dict[str, Any]:
    """Handler for my_new_tool."""
    return await self.ray_manager.my_new_operation(**kwargs)
```

### 3. Add Ray Manager Method

In `ray_manager.py`:

```python
@ResponseFormatter.handle_exceptions("my operation")
async def my_new_operation(self, param1: str, param2: int = 1) -> Dict[str, Any]:
    """Implement the new operation."""
    # Implementation here
    return ResponseFormatter.format_success_response(
        message="Operation completed",
        data={"result": "value"}
    )
```

### 4. Add Tests

```python
# tests/test_my_new_tool.py
async def test_my_new_tool():
    registry = ToolRegistry(RayManager())
    result = await registry.execute_tool("my_new_tool", {"param1": "test"})
    assert result["status"] == "success"
```

## Release Process

### Version Management

Update version in `pyproject.toml`:

```toml
[project]
version = "0.3.0"
```

### Testing Before Release

```bash
# Full test suite
uv run pytest

# Type checking
uv run pyright

# Code formatting
uv run black --check ray_mcp tests examples
uv run isort --check ray_mcp tests examples

# Build package
uv build
```

## Contributing

### Pull Request Process

1. Fork the repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Make changes with tests
4. Verify all tests pass: `uv run pytest`
5. Submit pull request

### Code Review Guidelines

- All new code must have tests
- Follow existing code style and patterns
- Update documentation for user-facing changes
- Ensure backward compatibility
- Add type hints for new functions

### Issue Reporting

Include in bug reports:
- Ray version and OS
- MCP client configuration
- Full error logs
- Minimal reproduction case 