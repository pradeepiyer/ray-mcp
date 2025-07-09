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

## Architecture Overview

Ray MCP uses a modular Domain-Driven Design architecture with focused components:

```
ray_mcp/
├── core/                    # Core business logic layer
│   ├── interfaces.py        # Protocol definitions and contracts
│   ├── state_manager.py     # Thread-safe cluster state management
│   ├── port_manager.py      # Port allocation with race condition prevention
│   ├── cluster_manager.py   # Pure cluster lifecycle operations
│   ├── job_manager.py       # Job operations and lifecycle management
│   ├── log_manager.py       # Centralized log retrieval with memory protection
│   └── unified_manager.py   # Backward compatibility facade
├── main.py                  # MCP server entry point
├── tool_registry.py         # Tool definitions and handlers
├── worker_manager.py        # Worker node management
└── logging_utils.py         # Logging and response formatting
```

### Core Components

- **StateManager**: Thread-safe cluster state management with validation
- **PortManager**: Port allocation with file locking and cleanup
- **ClusterManager**: Pure cluster lifecycle operations without side effects
- **JobManager**: Job operations with client management and inspection
- **LogManager**: Centralized log retrieval with memory protection and error analysis
- **UnifiedManager**: Facade providing backward compatibility

### Design Principles

- **Dependency Injection**: Components receive dependencies through constructors
- **Single Responsibility**: Each component has one clear purpose
- **Protocol-Based Contracts**: Runtime-checkable protocols define interfaces
- **Thread Safety**: State management handles concurrent access properly
- **Error Handling**: Comprehensive exception handling with structured responses

## Development Workflow

### Code Style

The project uses automated formatting and linting:

```bash
# Format code
make format

# Run linting
make lint

# Enhanced linting with tool function checks
make lint-enhanced
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

The project uses a comprehensive test suite with focused targets:

### Test Structure

```
tests/
├── conftest.py                    # Shared fixtures and utilities
├── test_core_state_manager.py     # State management unit tests
├── test_core_port_manager.py      # Port allocation unit tests  
├── test_core_cluster_manager.py   # Cluster lifecycle unit tests
├── test_core_job_manager.py       # Job management unit tests
├── test_core_log_manager.py       # Log management unit tests
├── test_core_unified_manager.py   # Unified manager unit tests
├── test_mcp_integration.py        # MCP integration layer tests
├── test_e2e_smoke.py              # Fast critical functionality validation
└── test_e2e_system.py             # System integration tests
```

### Running Tests

```bash
# Fast unit tests for development
make test-fast

# Critical functionality validation
make test-smoke  

# Complete test suite including E2E
make test

# Individual component tests
uv run pytest tests/test_core_job_manager.py
uv run pytest tests/test_core_state_manager.py

# With coverage
uv run pytest --cov=ray_mcp --cov-report=html
```

### Test Categories

- **Unit Tests** (`test_core_*.py`) - Component testing with full mocking
- **Integration Tests** (`test_mcp_integration.py`) - MCP layer integration
- **Smoke Tests** (`test_e2e_smoke.py`) - Fast critical path validation
- **System Tests** (`test_e2e_system.py`) - End-to-end system integration

## Debugging

### Logging Configuration

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('ray_mcp')
logger.setLevel(logging.DEBUG)
```

### Common Debug Scenarios

#### Component Testing

```python
# Test individual components directly
from ray_mcp.managers.state_manager import RayStateManager
from ray_mcp.managers.cluster_manager import RayClusterManager

state_mgr = RayStateManager()
cluster_mgr = RayClusterManager(state_mgr, port_mgr)
result = await cluster_mgr.init_cluster()
```

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
    return await self.unified_manager.my_new_operation(**kwargs)
```

### 3. Add Core Component Method

Choose the appropriate core component (e.g., `JobManager` for job operations):

```python
@ResponseFormatter.handle_exceptions("my operation")
async def my_new_operation(self, param1: str, param2: int = 1) -> Dict[str, Any]:
    """Implement the new operation."""
    # Implementation here
    return self._response_formatter.format_success_response(
        message="Operation completed",
        data={"result": "value"}
    )
```

### 4. Add Tests

```python
# tests/test_core_my_component.py
async def test_my_new_operation():
    manager = MyComponentManager(mock_dependencies)
    result = await manager.my_new_operation(param1="test")
    assert result["status"] == "success"
```

## Contributing

### Pull Request Process

1. Fork the repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Make changes with tests
4. Verify all tests pass: `make test`
5. Submit pull request

### Code Review Guidelines

- All new code must have unit tests
- Follow existing architectural patterns
- Update documentation for user-facing changes
- Ensure backward compatibility
- Add type hints for new functions
- Components should follow dependency injection pattern

### Issue Reporting

Include in bug reports:
- Ray version and OS
- MCP client configuration
- Full error logs with component context
- Minimal reproduction case
- Which component(s) are involved

### Architecture Guidelines

When contributing:
- Keep components focused on single responsibilities  
- Use dependency injection for component relationships
- Follow protocol-based contracts defined in `interfaces.py`
- Add comprehensive error handling with structured responses
- Maintain thread safety for shared state
- Write tests that verify behavior, not implementation details 