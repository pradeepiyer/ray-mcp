# Ray MCP Test Suite

A comprehensive test suite for the Ray MCP server, organized for efficient development and reliable validation.

## Test Organization

### Core Component Tests
- `test_core_unified_manager.py` - Unified manager architecture
- `test_core_state_manager.py` - State management and validation
- `test_core_cluster_manager.py` - Cluster lifecycle operations
- `test_core_job_manager.py` - Job submission and management
- `test_core_log_manager.py` - Log retrieval and analysis
- `test_core_port_manager.py` - Port allocation and management

### Integration Tests
- `test_mcp_integration.py` - MCP protocol integration and tool registry
- `test_mcp_server.py` - Comprehensive end-to-end server validation

### Test Infrastructure
- `conftest.py` - Shared fixtures, utilities, and test configuration

## Running Tests

### Development Workflow

```bash
# Fast unit tests for development feedback
make test-fast

# Quick architecture validation
make test-smoke

# Comprehensive end-to-end validation
make test-e2e

# Complete test suite with coverage
make test
```

### Direct pytest Commands

```bash
# Run all tests in a specific file
pytest tests/test_core_job_manager.py -v

# Run specific test method
pytest tests/test_core_state_manager.py::TestStateValidation::test_state_transitions -v

# Run tests by category
pytest tests/test_core_*.py              # All unit tests
pytest tests/test_mcp_*.py               # All integration tests
pytest -m "not e2e"                     # Exclude end-to-end tests
```

## Test Types

### Unit Tests (`test_core_*.py`)
**Purpose**: Test individual components in isolation
- Fast execution for development feedback
- Comprehensive mocking of external dependencies
- Focus on component logic and error handling
- Independent test execution

### Integration Tests (`test_mcp_integration.py`)
**Purpose**: Test MCP protocol integration layer
- Tool registry functionality
- Server startup and configuration
- Schema validation and compliance
- Error handling at protocol boundaries

### End-to-End Tests (`test_mcp_server.py`)
**Purpose**: Validate complete server functionality
- Real Ray cluster operations
- Complete workflow validation
- Performance and reliability testing
- System integration scenarios

## Test Environment

### Configuration
Tests adapt to different environments:
- **CI**: Optimized for reliability with constrained resources
- **Local**: Full testing with performance validation
- **Docker**: Containerized testing environment

### Dependencies
- Ray cluster management
- MCP protocol handling
- Async test execution
- Performance benchmarking

## Writing Tests

### Test Structure

```python
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
- Use descriptive test names that explain what is being tested
- Test both success and failure scenarios
- Keep tests focused on single behaviors
- Use fixtures for common setup
- Mock external dependencies in unit tests

#### ❌ Avoid
- Testing implementation details
- Overly complex test setups
- Brittle assertions on exact strings
- Shared state between tests
- Flaky or timing-dependent tests

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

## Coverage and Quality

### Coverage Goals
- **Unit Tests**: Comprehensive coverage of core component logic
- **Integration Tests**: Key interface and protocol validation
- **End-to-End Tests**: Critical user workflows and error scenarios

### Quality Standards
- All tests must pass before merging
- Clear failure messages for debugging
- Reasonable execution time
- No flaky or intermittent failures

## Adding New Tests

### For New Components
1. Create `test_core_new_component.py` following existing patterns
2. Include comprehensive unit tests for all public methods
3. Add error case testing and edge condition validation
4. Update integration tests if component has external interfaces

### For New Features
1. Add unit tests to appropriate `test_core_*.py` file
2. Update `test_mcp_integration.py` if MCP interface changes
3. Add end-to-end scenarios to `test_mcp_server.py` if needed
4. Update fixtures in `conftest.py` if shared setup is required

## Continuous Integration

### GitHub Actions
- **CI Pipeline**: Runs `test-fast` for quick feedback
- **PR Validation**: Includes comprehensive test suite
- **Coverage Reporting**: Automated coverage analysis

### Test Markers
- `@pytest.mark.fast` - Fast unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.e2e` - End-to-end tests
- `@pytest.mark.slow` - Tests with longer execution time

## Performance Considerations

### Test Optimization
- Unit tests prioritize speed over realism
- Integration tests balance speed with realistic scenarios
- End-to-end tests focus on comprehensive validation
- CI environment uses optimized configurations

### Resource Management
- Proper cleanup of Ray clusters and resources
- Efficient use of test fixtures
- Parallel test execution where possible
- Environment-specific timeouts and limits

## Troubleshooting

### Common Issues
- **Ray cluster conflicts**: Use `make clean` to reset environment
- **Port conflicts**: Tests handle port allocation automatically
- **Timeout errors**: Check resource constraints and cluster health
- **Import errors**: Ensure proper test environment setup

### Getting Help
- Check test output for specific error messages
- Review relevant component documentation
- Use verbose test execution for debugging
- Consult CI logs for environment-specific issues