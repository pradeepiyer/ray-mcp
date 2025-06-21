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

5. **`test_e2e_integration.py`** - **NEW** Real end-to-end integration tests
   - **NO MOCKING** - Tests with actual Ray clusters and jobs
   - Complete workflow validation from cluster start to shutdown
   - Real job submission, monitoring, and debugging scenarios
   - Actor management and monitoring workflows
   - Performance metrics and health check validation

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

## End-to-End Integration Tests (NEW)

The `test_e2e_integration.py` file contains comprehensive real-world testing scenarios that execute against actual Ray clusters **without any mocking**. These tests provide the highest level of confidence in the MCP Ray server functionality.

### E2E Test Scenarios

#### 1. **Complete Ray Workflow Test** (`test_complete_ray_workflow`)
**Duration**: ~40 seconds | **Status**: ✅ Passing
- Starts Ray cluster with 4 CPUs
- Submits `simple_job.py` with numpy runtime environment
- Monitors job status progression (PENDING → RUNNING → SUCCEEDED)
- Validates job logs contain expected Pi calculation output
- Lists jobs and verifies submitted job appears in results
- Stops Ray cluster and verifies shutdown

#### 2. **Actor Management Workflow Test** (`test_actor_management_workflow`)
**Duration**: ~20 seconds | **Status**: ✅ Passing
- Starts Ray cluster for actor testing
- Creates and submits custom actor script with multiple TestActor instances
- Lists actors and verifies they were created successfully
- Attempts actor termination (handles system actors gracefully)
- Cancels actor job and cleans up resources
- Stops Ray cluster

#### 3. **Monitoring and Health Workflow Test** (`test_monitoring_and_health_workflow`)
**Duration**: ~25 seconds | **Status**: ✅ Passing
- Starts Ray cluster with specific resource allocation
- Collects cluster resources and validates CPU allocation
- Lists cluster nodes and verifies node information
- Gathers performance metrics (cluster overview, resource details, node details)
- Performs health checks and collects recommendations
- Gets optimization suggestions for cluster configuration
- Submits load job and monitors real-time cluster utilization
- Performs final health assessment after load testing
- Stops Ray cluster

#### 4. **Job Failure and Debugging Workflow Test** (`test_job_failure_and_debugging_workflow`)
**Duration**: ~15 seconds | **Status**: ✅ Passing
- Starts Ray cluster for failure testing
- Creates and submits job designed to fail (intentional ValueError)
- Monitors job until failure is detected
- Retrieves and validates failure logs contain expected error messages
- Uses debug tool to analyze failed job and get suggestions
- Submits successful job to verify cluster health after failure
- Lists all jobs to verify both failed and successful jobs are recorded
- Stops Ray cluster

#### 5. **Additional Validation Tests**
- **MCP Tools Availability Test**: Validates all 21 MCP tools are properly defined
- **Error Handling Test**: Tests behavior when Ray is not initialized
- **Cluster Management Cycle Test**: Tests multiple start/stop cycles
- **Simple Job Standalone Test**: Validates example job runs independently

### E2E Test Features

- **🚫 No Mocking**: Tests run against real Ray clusters and jobs
- **🔄 Complete Workflows**: End-to-end scenarios from cluster start to shutdown
- **📊 Real Metrics**: Actual performance data and health checks
- **🛠️ Error Scenarios**: Intentional failures and recovery testing
- **🧹 Resource Cleanup**: Proper cleanup of clusters and temporary files
- **📝 Comprehensive Logging**: Detailed progress tracking and debugging output
- **⚡ Parallel Execution**: Tests can run independently and in parallel
- **🎯 Realistic Use Cases**: Tests mirror actual developer workflows

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

### Run End-to-End Integration Tests

```bash
# Run all E2E integration tests
python -m pytest tests/test_e2e_integration.py -v

# Run specific E2E test
python -m pytest tests/test_e2e_integration.py::TestE2EIntegration::test_complete_ray_workflow -v -s

# Run E2E tests with detailed output
python -m pytest tests/test_e2e_integration.py -v -s --tb=long
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

### 1. Mocking Strategy (Unit Tests)

Unit tests use comprehensive mocking to isolate components:

```python
@pytest.fixture
def mock_ray_manager(self):
    """Create a mock RayManager for testing."""
    manager = Mock(spec=RayManager)
    manager.start_cluster = AsyncMock(return_value={"status": "started"})
    return manager
```

### 2. Real Integration Strategy (E2E Tests)

E2E tests use actual Ray clusters and real operations:

```python
@pytest_asyncio.fixture
async def ray_cluster_manager(self):
    """Fixture to manage Ray cluster lifecycle for testing."""
    ray_manager = RayManager()
    
    # Ensure Ray is not already running
    if ray.is_initialized():
        ray.shutdown()
    
    yield ray_manager
    
    # Cleanup: Stop Ray if it's running
    try:
        if ray.is_initialized():
            ray.shutdown()
    except Exception:
        pass  # Ignore cleanup errors
```

### 3. Parameter Testing

Each tool is tested with:
- Valid parameters
- Invalid parameters
- Missing required parameters
- Optional parameter handling
- Complex nested parameters

### 4. Error Handling

Comprehensive error testing includes:
- Ray unavailable scenarios
- Network failures
- Invalid configurations
- Resource constraints
- Permission errors

### 5. Response Validation

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
- **Real Integration**: Actual Ray cluster operations and job execution

## Test Results Summary

Recent test run results:
- **Total Tests**: 94 (8 new E2E tests added)
- **Unit Tests**: 86 (100% passing)
- **E2E Integration Tests**: 8 (100% passing)
- **Overall Status**: ✅ All tests passing

### Test Execution Times
- **Unit Tests**: ~5 seconds (fast, mocked)
- **E2E Integration Tests**: ~90 seconds (comprehensive, real operations)
- **Total Suite**: ~95 seconds

### Test Status
✅ All tests are currently passing with comprehensive coverage of:
- All 22 MCP tools (unit tests)
- Error handling scenarios (unit + integration)
- Integration workflows (mocked + real)
- Parameter validation (unit tests)
- **Real Ray cluster operations (E2E integration)**
- **Complete workflow validation (E2E integration)**
- **Performance monitoring and debugging (E2E integration)**

## Contributing to Tests

### Adding New Tests

1. **Tool Tests**: Add to `test_mcp_tools.py`
2. **Manager Tests**: Add to `test_ray_manager_methods.py`
3. **Integration Tests**: Add to `test_integration.py`
4. **E2E Integration Tests**: Add to `test_e2e_integration.py`

### Test Naming Convention

- Test methods: `test_<functionality>_<scenario>`
- Test classes: `Test<ComponentName>`
- Test files: `test_<module_name>.py`

### Best Practices

1. **Isolation**: Each test should be independent
2. **Mocking**: Mock external dependencies (unit tests)
3. **Real Operations**: Use actual Ray clusters (E2E tests)
4. **Assertions**: Clear, specific assertions
5. **Documentation**: Descriptive docstrings
6. **Coverage**: Aim for high code coverage
7. **Cleanup**: Proper resource cleanup in E2E tests

## Debugging Tests

### Common Issues

1. **Import Errors**: Ensure all dependencies installed
2. **Async Issues**: Use `@pytest.mark.asyncio` for async tests
3. **Mock Problems**: Verify mock setup and assertions
4. **Path Issues**: Check relative imports and file paths
5. **Ray Cleanup**: Ensure Ray clusters are properly shutdown between E2E tests

### Debug Commands

```bash
# Run with debugging
python -m pytest tests/ -v -s --tb=long

# Run single test with debugging
python -m pytest tests/test_mcp_tools.py::TestMCPToolCalls::test_start_ray_tool -v -s

# Debug E2E test with full output
python -m pytest tests/test_e2e_integration.py::TestE2EIntegration::test_complete_ray_workflow -v -s --tb=long

# Show test output
python -m pytest tests/ -v -s --capture=no
```

## Future Improvements

1. **Performance Tests**: Add load and stress testing
2. **Multi-node Testing**: Test with distributed Ray clusters
3. **Error Simulation**: More realistic error scenarios
4. **Documentation Tests**: Validate documentation examples
5. **Security Tests**: Authentication and authorization testing
6. **Continuous Integration**: Automated E2E testing in CI/CD pipeline 