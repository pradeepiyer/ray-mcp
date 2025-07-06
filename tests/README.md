# Ray MCP Test Suite

A comprehensive test suite for the Ray MCP server, organized for maintainability and efficient development.

## Test Organization

### Core Component Tests (Unit Tests)
- `test_core_unified_manager.py` - Unified manager facade and delegation
- `test_core_cluster_manager.py` - Cluster lifecycle and connection management
- `test_core_state_manager.py` - State management and validation
- `test_core_job_manager.py` - Job submission and management
- `test_core_log_manager.py` - Log retrieval and analysis
- `test_core_port_manager.py` - Port allocation and management
- `test_worker_manager.py` - Worker process management

### MCP Layer Tests
- `test_mcp_tools.py` - MCP tool registry and protocol handling (unit tests)
- `test_mcp_server.py` - End-to-end server validation (slow integration tests)

### Test Infrastructure
- `conftest.py` - Shared fixtures, utilities, and test configuration

## Test Guidelines

### File Organization Rules
1. **`test_mcp_server.py`** - Reserved for slow, non-mocked integration tests only
2. **All other test files** - Fast unit tests with complete mocking
3. **Avoid adding new test files** - Consolidate into existing domain-focused files

### Test Types

#### Unit Tests (`test_core_*.py`, `test_mcp_tools.py`)
- **Fast execution** for development feedback
- **Complete mocking** of external dependencies
- **Focus on logic** and error handling
- **Independent execution** - no shared state

#### Integration Tests (`test_mcp_server.py`)
- **Slow, comprehensive** end-to-end validation
- **Real Ray cluster** operations
- **Complete workflow** testing
- **Use sparingly** - only for critical flows

## Running Tests

### Development Workflow

```bash
# Fast unit tests for development
make test-fast

# Quick validation
make test-smoke

# Full test suite
make test
```

### Direct pytest Commands

```bash
# Run all unit tests
pytest tests/test_core_*.py tests/test_mcp_tools.py -v

# Run integration tests
pytest tests/test_mcp_server.py -v

# Run specific test file
pytest tests/test_core_job_manager.py -v

# Run specific test method
pytest tests/test_core_state_manager.py::TestStateValidation::test_state_transitions -v
```

## Writing Tests

### Test Structure

```python
@pytest.mark.fast
class TestComponentName:
    """Test suite for ComponentName functionality."""
    
    def test_happy_path_scenario(self):
        """Test primary functionality with valid inputs."""
        # Arrange
        component = ComponentName()
        
        # Act
        result = component.method()
        
        # Assert
        assert result.status == "success"
    
    def test_error_handling(self):
        """Test error handling with invalid inputs."""
        # Test implementation
```

### Best Practices

#### ✅ Do
- Use descriptive test names explaining what is being tested
- Test both success and failure scenarios
- Keep tests focused on single behaviors
- Use fixtures for common setup
- Mock all external dependencies in unit tests
- Use `@pytest.mark.fast` for unit tests

#### ❌ Avoid
- Testing implementation details
- Overly complex test setups
- Brittle assertions on exact strings
- Shared state between tests
- Adding new test files without justification

## Debugging Tests

### Verbose Output
```bash
# Detailed test output
pytest -v --tb=short

# Stop on first failure
pytest -x

# Show print statements
pytest -s

# Live log output
pytest --log-cli-level=DEBUG
```

### Test Debugging
```bash
# Debug specific test
pytest tests/test_core_job_manager.py::TestJobManager::test_submit_job -v -s

# Interactive debugging
pytest --pdb tests/test_core_job_manager.py::TestJobManager::test_submit_job
```

## Adding New Tests

### For New Components
1. Add tests to appropriate existing `test_core_*.py` file
2. If no appropriate file exists, discuss creating a new one
3. Include comprehensive unit tests for all public methods
4. Add error case testing and edge condition validation
5. Update `test_mcp_tools.py` if MCP interface changes
6. Add to `test_mcp_server.py` only if critical end-to-end validation is needed

### For New Features
1. Add unit tests to appropriate domain-focused file
2. Update integration tests only if interface changes
3. Use complete mocking for unit tests
4. Update fixtures in `conftest.py` if shared setup is required

## Test Environment

### Configuration
Tests adapt to different environments:
- **CI**: Optimized for reliability with constrained resources
- **Local**: Full testing with performance validation
- **Docker**: Containerized testing environment

### Test Markers
- `@pytest.mark.fast` - Fast unit tests (all files except test_mcp_server.py)
- `@pytest.mark.integration` - Integration tests (test_mcp_server.py only)
- `@pytest.mark.e2e` - End-to-end tests
- `@pytest.mark.slow` - Tests with longer execution time

## Quality Standards

### All Tests Must
- Pass before merging
- Have clear failure messages for debugging
- Execute in reasonable time
- Be reliable and non-flaky
- Follow the mocking guidelines

### Unit Tests Must
- Use complete mocking of external dependencies
- Execute quickly for development feedback
- Be independent of each other
- Focus on component logic

### Integration Tests Must
- Justify their inclusion in test_mcp_server.py
- Test critical end-to-end workflows
- Handle real Ray cluster operations
- Be used sparingly

## Troubleshooting

### Common Issues
- **Ray cluster conflicts**: Use `make clean` to reset environment
- **Port conflicts**: Tests handle port allocation automatically
- **Timeout errors**: Check resource constraints and cluster health
- **Import errors**: Ensure proper test environment setup
- **Mocking issues**: Verify all external dependencies are mocked in unit tests

### Getting Help
- Check test output for specific error messages
- Review relevant component documentation
- Use verbose test execution for debugging
- Consult CI logs for environment-specific issues
- Verify test follows the file organization guidelines