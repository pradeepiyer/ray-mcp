# Ray MCP Server Test Suite

This document provides comprehensive information about the test suite for the Ray MCP Server.

## Test Organization

The test suite is organized into different categories for optimal development workflow:

### Test Categories

1. **Unit Tests**: Fast, isolated tests for individual components
2. **Integration Tests**: Medium-speed tests with Ray interaction
3. **End-to-End Tests**: Comprehensive tests with full Ray workflows
4. **Multi-Node Tests**: Tests for multi-node cluster functionality

### Test Files

- `test_ray_manager.py`: Core Ray management functionality
- `test_multi_node_cluster.py`: Multi-node cluster features
- `test_e2e_integration.py`: End-to-end workflow tests
- `test_main.py`: MCP server functionality
- `test_worker_manager.py`: Worker node management
- `test_integration.py`: Integration test scenarios
- `test_utils.py`: Utility functions and helpers
- `conftest.py`: Pytest configuration and fixtures

## Running Tests

### Quick Test Commands

```bash
# Run all tests
uv run pytest

# Run fast tests (excludes e2e)
make test-fast

# Run e2e tests with cleanup
make test-e2e

# Run complete test suite
make test-full

# Run smoke tests
make test-smoke
```

### Manual Test Execution

```bash
# Run specific test categories
uv run pytest tests/test_ray_manager.py
uv run pytest tests/test_multi_node_cluster.py
uv run pytest tests/test_e2e_integration.py

# Run tests with markers
uv run pytest -m "not e2e"  # Exclude e2e tests
uv run pytest -m "e2e"      # Only e2e tests
uv run pytest -m "smoke"    # Only smoke tests

# Run tests with coverage
uv run pytest --cov=ray_mcp tests/
```

### Test Configuration

The test suite uses pytest with the following configuration:

```ini
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

## Test Categories Details

### Unit Tests

**Purpose**: Test individual components in isolation.

**Characteristics**:
- Fast execution (< 1 second per test)
- No external dependencies
- Mock external services
- Test specific functions and methods

**Examples**:
- Parameter validation
- Data structure operations
- Utility functions
- Error handling

**Files**:
- `test_ray_manager.py` (unit test methods)
- `test_utils.py`
- Parts of `test_main.py`

### Integration Tests

**Purpose**: Test component interactions with Ray.

**Characteristics**:
- Medium speed (1-10 seconds per test)
- Ray cluster interaction
- Real Ray operations
- Component integration

**Examples**:
- Tool execution
- Ray manager operations
- Job submission and monitoring
- Actor management

**Files**:
- `test_integration.py`
- Parts of `test_ray_manager.py`
- Parts of `test_worker_manager.py`

### End-to-End Tests

**Purpose**: Test complete workflows and user scenarios.

**Characteristics**:
- Slow execution (10-60 seconds per test)
- Full Ray cluster lifecycle
- Complete job workflows
- Real-world scenarios

**Examples**:
- Complete cluster startup/shutdown
- Job submission and monitoring
- Multi-node cluster operations
- Error recovery scenarios

**Files**:
- `test_e2e_integration.py`
- Parts of `test_multi_node_cluster.py`

### Multi-Node Tests

**Purpose**: Test multi-node cluster functionality.

**Characteristics**:
- Complex setup with multiple nodes
- Worker node management
- Network communication
- Resource distribution

**Examples**:
- Worker node startup/shutdown
- Resource allocation across nodes
- Node failure scenarios
- Cluster scaling

**Files**:
- `test_multi_node_cluster.py`
- Parts of `test_e2e_integration.py`

## Test Fixtures

### Common Fixtures

```python
# conftest.py
@pytest.fixture
def ray_manager():
    """Provide a RayManager instance for testing."""
    return RayManager()

@pytest.fixture
def tool_registry(ray_manager):
    """Provide a ToolRegistry instance for testing."""
    return ToolRegistry(ray_manager)

@pytest.fixture
async def ray_cluster():
    """Provide a running Ray cluster for testing."""
    # Setup cluster
    yield cluster_info
    # Cleanup cluster
```

### Ray Cluster Fixtures

```python
@pytest.fixture
async def single_node_cluster():
    """Single-node Ray cluster for testing."""
    manager = RayManager()
    await manager.init_cluster(num_cpus=2)
    yield manager
    await manager.stop_cluster()

@pytest.fixture
async def multi_node_cluster():
    """Multi-node Ray cluster for testing."""
    manager = RayManager()
    await manager.init_cluster(
        num_cpus=2,
        worker_nodes=[{"num_cpus": 1, "node_name": "worker-1"}]
    )
    yield manager
    await manager.stop_cluster()
```

## Test Patterns

### Async Test Pattern

```python
import pytest

@pytest.mark.asyncio
async def test_ray_initialization():
    """Test Ray cluster initialization."""
    manager = RayManager()
    result = await manager.init_cluster(num_cpus=4)
    assert result["status"] == "success"
    assert manager.is_initialized
```

### Mock Pattern

```python
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_job_submission_with_mock():
    """Test job submission with mocked Ray client."""
    with patch('ray.job_submission.JobSubmissionClient') as mock_client:
        mock_client.return_value.submit_job = AsyncMock(return_value="job_id")
        
        manager = RayManager()
        result = await manager.submit_job("python script.py")
        
        assert result["status"] == "success"
        assert result["job_id"] == "job_id"
```

### Error Handling Pattern

```python
@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling in tool execution."""
    manager = RayManager()
    
    # Test without Ray initialization
    result = await manager.get_cluster_info()
    assert result["status"] == "error"
    assert "not initialized" in result["message"]
```

## Test Utilities

### Test Helpers

```python
# test_utils.py
def create_test_job_config(entrypoint="python test.py"):
    """Create a test job configuration."""
    return {
        "entrypoint": entrypoint,
        "runtime_env": {"pip": ["numpy"]}
    }

def assert_success_response(response):
    """Assert that a response indicates success."""
    assert response["status"] == "success"

def assert_error_response(response, expected_message=None):
    """Assert that a response indicates an error."""
    assert response["status"] == "error"
    if expected_message:
        assert expected_message in response["message"]
```

### Ray Cleanup Utilities

```python
def cleanup_ray_processes():
    """Clean up any running Ray processes."""
    import subprocess
    subprocess.run(["./scripts/ray_cleanup.sh"], check=True)

@pytest.fixture(autouse=True)
def auto_cleanup():
    """Automatically clean up Ray processes after tests."""
    yield
    cleanup_ray_processes()
```

## Test Data

### Sample Data

```python
# Test data for various scenarios
SAMPLE_JOB_CONFIG = {
    "entrypoint": "python examples/simple_job.py",
    "runtime_env": {"pip": ["numpy", "pandas"]}
}

SAMPLE_WORKER_CONFIG = {
    "num_cpus": 2,
    "num_gpus": 0,
    "node_name": "test-worker"
}

SAMPLE_CLUSTER_CONFIG = {
    "num_cpus": 4,
    "num_gpus": 1,
    "object_store_memory": 1000000000
}
```

## Performance Testing

### Load Testing

```python
@pytest.mark.asyncio
async def test_concurrent_job_submission():
    """Test submitting multiple jobs concurrently."""
    manager = RayManager()
    await manager.init_cluster(num_cpus=8)
    
    # Submit multiple jobs concurrently
    tasks = [
        manager.submit_job(f"python job_{i}.py")
        for i in range(5)
    ]
    results = await asyncio.gather(*tasks)
    
    # Verify all jobs were submitted successfully
    for result in results:
        assert result["status"] == "success"
```

### Resource Testing

```python
@pytest.mark.asyncio
async def test_resource_allocation():
    """Test resource allocation and limits."""
    manager = RayManager()
    await manager.init_cluster(num_cpus=4, object_store_memory=2000000000)
    
    # Test resource constraints
    result = await manager.get_cluster_info()
    assert result["cluster_info"]["num_cpus"] == 4
    assert result["cluster_info"]["object_store_memory"] == 2000000000
```

## Continuous Integration

### CI Configuration

The test suite is configured for CI/CD with:

- **Fast Tests**: Run on every commit
- **Integration Tests**: Run on pull requests
- **E2E Tests**: Run on main branch
- **Coverage Reports**: Generated for all test runs

### Test Commands for CI

```yaml
# GitHub Actions example
- name: Run Fast Tests
  run: make test-fast

- name: Run Integration Tests
  run: uv run pytest -m "integration"

- name: Run E2E Tests
  run: make test-e2e

- name: Generate Coverage Report
  run: uv run pytest --cov=ray_mcp --cov-report=xml
```

## Best Practices

### Test Writing Guidelines

1. **Descriptive Names**: Use clear, descriptive test names
2. **Single Responsibility**: Each test should test one thing
3. **Setup/Teardown**: Properly clean up resources
4. **Async Support**: Use `@pytest.mark.asyncio` for async tests
5. **Error Testing**: Test both success and error scenarios
6. **Mocking**: Mock external dependencies appropriately

### Test Organization

1. **Group Related Tests**: Use test classes for related functionality
2. **Use Markers**: Mark tests with appropriate categories
3. **Fixture Reuse**: Create reusable fixtures for common setup
4. **Test Data**: Use consistent test data across tests

### Performance Considerations

1. **Fast Unit Tests**: Keep unit tests under 1 second
2. **Efficient Integration**: Minimize Ray cluster startup time
3. **Parallel Execution**: Use pytest-xdist for parallel test execution
4. **Resource Cleanup**: Ensure proper cleanup to prevent resource leaks

## Troubleshooting

### Common Test Issues

1. **Ray Process Leaks**: Use cleanup scripts and fixtures
2. **Port Conflicts**: Use dynamic port allocation in tests
3. **Async Issues**: Ensure proper async/await usage
4. **Resource Limits**: Monitor system resources during tests

### Debug Commands

```bash
# Run tests with verbose output
uv run pytest -v

# Run specific test with debug output
uv run pytest tests/test_specific.py::test_function -v -s

# Run tests with coverage
uv run pytest --cov=ray_mcp --cov-report=html

# Clean up before running tests
./scripts/ray_cleanup.sh
```

## Coverage

### Coverage Goals

- **Unit Tests**: > 90% line coverage
- **Integration Tests**: > 80% line coverage
- **Overall**: > 85% line coverage

### Coverage Reports

```bash
# Generate coverage report
uv run pytest --cov=ray_mcp --cov-report=html

# View coverage report
open htmlcov/index.html
```

The test suite provides comprehensive coverage of the Ray MCP Server functionality, ensuring reliability and maintainability of the codebase. 