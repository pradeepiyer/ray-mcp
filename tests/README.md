# MCP Ray Server Test Suite

This directory contains comprehensive unit and integration tests for the MCP Ray Server project.

## Test Structure

### Test Files

1. **`test_mcp_tools.py`** - Unit tests for all MCP tool calls
   - Tests all 22 MCP tools individually
   - Covers parameter validation, error handling, and response formats
   - Mocks RayManager to isolate tool call logic

2. **`test_ray_manager.py`** - Original Ray manager tests
   - Basic RayManager functionality tests
   - Cluster initialization and management
   - Legacy test file maintained for compatibility

3. **`test_ray_manager_methods.py`** - Detailed Ray manager method tests
   - Comprehensive testing of RayManager methods
   - Edge cases and error conditions
   - Real-world scenarios with complex parameters

4. **`test_integration.py`** - End-to-end integration tests
   - Complete workflow testing
   - Tool interaction and data flow
   - Concurrent operations and complex scenarios

## Test Categories

### 1. Basic Cluster Management Tests
- `start_ray` - Starting Ray clusters with various configurations (default: 4 CPUs)
- `connect_ray` - Connecting to existing Ray clusters
- `stop_ray` - Stopping clusters gracefully
- `cluster_status` - Getting cluster health and status
- `cluster_resources` - Resource monitoring and allocation
- `cluster_nodes` - Node management and scaling


### 2. Job Management Tests
- `submit_job` - Job submission with runtime environments
- `list_jobs` - Job listing and filtering
- `job_status` - Job status monitoring
- `cancel_job` - Job cancellation
- `monitor_job` - Job progress tracking
- `debug_job` - Job debugging and troubleshooting

### 3. Actor Management Tests
- `list_actors` - Actor discovery and listing
- `kill_actor` - Actor lifecycle management



### 4. Enhanced Monitoring Tests
- `performance_metrics` - Performance monitoring
- `health_check` - Cluster health assessment
- `optimize_config` - Configuration optimization

### 5. Workflow & Orchestration Tests

- `schedule_job` - Job scheduling with cron expressions

### 6. Backup & Recovery Tests
- `backup_cluster` - Cluster state backup
- `restore_cluster` - Cluster state restoration

### 7. Logs & Debugging Tests
- `get_logs` - Log retrieval and analysis

## Running Tests

### Prerequisites

```bash
pip install pytest pytest-asyncio pytest-mock pytest-cov
```

### Run All Tests

```bash
# Run all tests with verbose output
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=ray_mcp --cov-report=html

# Run specific test file
python -m pytest tests/test_mcp_tools.py -v

# Run specific test
python -m pytest tests/test_mcp_tools.py::TestMCPToolCalls::test_start_ray_tool -v
```

### Using the Test Runner

```bash
python run_tests.py
```

## Test Configuration

The test suite is configured via `pytest.ini`:

- **Test Discovery**: Automatically finds `test_*.py` files
- **Async Support**: Full async/await test support
- **Coverage**: Code coverage reporting
- **Markers**: Custom test markers for categorization

## Test Patterns

### 1. Mocking Strategy

Tests use comprehensive mocking to isolate components:

```python
@pytest.fixture
def mock_ray_manager(self):
    """Create a mock RayManager for testing."""
    manager = Mock(spec=RayManager)
    manager.start_cluster = AsyncMock(return_value={"status": "started"})
    return manager
```

### 2. Parameter Testing

Each tool is tested with:
- Valid parameters
- Invalid parameters
- Missing required parameters
- Optional parameter handling
- Complex nested parameters

### 3. Error Handling

Comprehensive error testing includes:
- Ray unavailable scenarios
- Network failures
- Invalid configurations
- Resource constraints
- Permission errors

### 4. Response Validation

All tests validate:
- Response format consistency
- JSON structure validity
- Status code accuracy
- Error message clarity

## Test Coverage

Current test coverage includes:

- **Tool Calls**: All 22 MCP tools
- **Parameter Validation**: Required and optional parameters
- **Error Handling**: Ray unavailable, exceptions, invalid inputs
- **Response Formats**: JSON structure and content validation
- **Workflow Testing**: End-to-end scenarios
- **Concurrent Operations**: Multiple simultaneous tool calls

## Test Results Summary

Recent test run results:
- **Total Tests**: 86
- **Passing**: 86 (100%)
- **Failing**: 0 (0%)

### Test Status
✅ All tests are currently passing with comprehensive coverage of:
- All 22 MCP tools
- Error handling scenarios
- Integration workflows
- Parameter validation

## Contributing to Tests

### Adding New Tests

1. **Tool Tests**: Add to `test_mcp_tools.py`
2. **Manager Tests**: Add to `test_ray_manager_methods.py`
3. **Integration Tests**: Add to `test_integration.py`

### Test Naming Convention

- Test methods: `test_<functionality>_<scenario>`
- Test classes: `Test<ComponentName>`
- Test files: `test_<module_name>.py`

### Best Practices

1. **Isolation**: Each test should be independent
2. **Mocking**: Mock external dependencies
3. **Assertions**: Clear, specific assertions
4. **Documentation**: Descriptive docstrings
5. **Coverage**: Aim for high code coverage

## Debugging Tests

### Common Issues

1. **Import Errors**: Ensure all dependencies installed
2. **Async Issues**: Use `@pytest.mark.asyncio` for async tests
3. **Mock Problems**: Verify mock setup and assertions
4. **Path Issues**: Check relative imports and file paths

### Debug Commands

```bash
# Run with debugging
python -m pytest tests/ -v -s --tb=long

# Run single test with debugging
python -m pytest tests/test_mcp_tools.py::TestMCPToolCalls::test_start_ray_tool -v -s

# Show test output
python -m pytest tests/ -v -s --capture=no
```

## Future Improvements

1. **Performance Tests**: Add load and stress testing
2. **Real Ray Integration**: Tests with actual Ray clusters
3. **Error Simulation**: More realistic error scenarios
4. **Documentation Tests**: Validate documentation examples
5. **Security Tests**: Authentication and authorization testing 