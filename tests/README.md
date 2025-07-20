# Ray MCP Test Suite

Comprehensive test suite for Ray MCP Server's prompt-driven architecture.

## Test Strategy

### Two-Tier Testing Architecture

**Unit Tests** (`tests/unit/`)
- 100% mocked for fast execution
- Tests individual components in isolation
- Focused on logic validation and edge cases

**End-to-End Tests** (`tests/e2e/`)
- No mocking, real system integration
- Complete workflows from prompt to result
- Validates actual Ray/Kubernetes operations


## Test Structure

```
tests/
├── conftest.py                     # Core test configuration
├── test_runner.py                  # Unified test runner
├── unit/                           # Unit tests (100% mocked)
│   ├── test_prompt_managers.py     # Manager behavior with mocking
│   ├── test_tool_registry.py       # Tool registry and MCP integration
│   ├── test_mcp_tools.py          # MCP tool functionality
│   └── test_parsers_and_formatters.py  # Parsing and formatting logic
├── e2e/                            # End-to-end tests (no mocking)
│   └── (Future GKE integration tests)
└── helpers/                        # Test utilities
    ├── fixtures.py                 # Reusable test fixtures
    ├── utils.py                    # Test helper functions
    └── e2e.py                      # End-to-end utilities
```

## Running Tests

### Quick Development Workflow

```bash
# Fast unit tests with mocking
make test-fast


# Integration testing
make test-e2e

# Complete test suite
make test
```

### Direct Test Runner

```bash
# Run specific test types
python test_runner.py unit      # Unit tests only
python test_runner.py e2e       # End-to-end tests only
python test_runner.py all       # All tests

# With coverage
python test_runner.py unit --coverage
```

### Traditional pytest

```bash
# Run all unit tests
pytest tests/unit/ -m unit

# Run all e2e tests
pytest tests/e2e/ -m e2e

# Run specific test file
pytest tests/unit/test_prompt_managers.py
```

## Test Categories

### Unit Tests (`tests/unit/`)

**test_prompt_managers.py**
- Tests all manager classes with full mocking
- Validates prompt parsing and action execution
- Tests error handling and edge cases
- Covers ClusterManager, JobManager, UnifiedManager, CloudProviderManager

**test_tool_registry.py**
- Tests MCP tool registration and routing
- Validates tool schema and parameter handling
- Tests integration with handlers and managers
- Covers 3-tool architecture validation

**test_mcp_tools.py**
- Tests MCP tool functionality
- Validates tool parameter validation
- Tests tool execution workflows

**test_parsers_and_formatters.py**
- Tests ActionParser natural language processing
- Validates prompt parsing logic
- Tests response formatting

### End-to-End Tests (`tests/e2e/`)

**Future GKE Integration Tests**
- Will test complete system workflows without mocking
- Will validate real Kubernetes cluster operations
- Will test actual MCP server integration with GKE
- Will cover critical cloud user scenarios

## Test Utilities

### Fixtures (`tests/helpers/fixtures.py`)

```python
from tests.helpers import mock_state_manager, mock_ray_cluster

@pytest.fixture
def mock_cluster_manager(mock_state_manager):
    """Pre-configured cluster manager with mocks."""
    return ClusterManager(mock_state_manager)
```

### Utilities (`tests/helpers/utils.py`)

```python
from tests.helpers import create_test_job_config, validate_response_format

# Test data generation
job_config = create_test_job_config(entrypoint="python test.py")

# Response validation
assert validate_response_format(response)
```

### End-to-End Helpers (`tests/helpers/e2e.py`)

```python
from tests.helpers import E2ETestRunner

# Complete workflow testing
runner = E2ETestRunner()
await runner.test_cluster_lifecycle()
```

## Writing Tests

### Unit Test Guidelines

```python
@pytest.mark.unit
@pytest.mark.asyncio
async def test_cluster_creation_success():
    """Test successful cluster creation with mocking."""
    # Setup comprehensive mocks
    mock_ray = Mock()
    mock_ray.init.return_value = Mock()
    
    # Test the behavior
    manager = ClusterManager(mock_state_manager)
    result = await manager.handle_cluster_request("create a local cluster")
    
    # Validate behavior, not implementation
    assert result["status"] == "success"
    assert "cluster_info" in result["data"]
```

### End-to-End Test Guidelines

```python
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_complete_job_workflow():
    """Test complete job workflow without mocking."""
    # Use real components
    manager = RayUnifiedManager()
    
    # Test actual workflow
    cluster_result = await manager.handle_cluster_request("create a local cluster")
    assert cluster_result["status"] == "success"
    
    job_result = await manager.handle_job_request("submit job with script test.py")
    assert job_result["status"] == "success"
```

## Test Markers

- `@pytest.mark.unit`: Unit tests with mocking
- `@pytest.mark.e2e`: End-to-end tests without mocking
- `@pytest.mark.asyncio`: Async test functions

## Environment Requirements

### Unit Tests
- Python 3.10+
- Ray MCP dependencies
- pytest and mocking libraries

### End-to-End Tests
- All unit test requirements
- Ray cluster capability
- Optional: Kubernetes cluster for KubeRay tests
- Optional: GKE credentials for cloud tests

## Benefits

1. **Fast Development**: Unit tests provide immediate feedback
2. **Reliable Integration**: E2E tests validate real system behavior
3. **Maintainable**: Clear separation between mocked and real tests
4. **Focused**: Tests validate critical user workflows
5. **Scalable**: Easy to add new tests in appropriate categories

## Migration Notes

This test suite implements a modern testing strategy:
- **Unit tests** with 100% mocking for fast execution
- **End-to-end tests** with no mocking for integration validation
- **Unified test runner** for consistent execution
- **Prompt-driven testing** aligned with the 3-tool architecture