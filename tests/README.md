# Ray MCP Tests

Comprehensive test suite for the modular Ray MCP architecture.

## Test Structure

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

## Test Categories

### Unit Tests (`test_core_*.py`)
- **Purpose**: Test individual components in isolation
- **Mocking**: Fully mocked dependencies and external services
- **Speed**: Fast execution for development feedback
- **Coverage**: Each core component thoroughly tested

### Integration Tests (`test_mcp_integration.py`)
- **Purpose**: Test MCP server integration layer
- **Scope**: Tool registry, server startup, schema validation
- **Mocking**: Minimal mocking of Ray operations
- **Focus**: Interface contracts and protocol compliance

### Smoke Tests (`test_e2e_smoke.py`) 
- **Purpose**: Fast critical functionality validation
- **Execution**: Real Ray operations, minimal setup
- **Speed**: Optimized for rapid feedback
- **Coverage**: Essential user workflows only

### System Tests (`test_e2e_system.py`)
- **Purpose**: End-to-end system integration validation
- **Scope**: Full component integration testing
- **Execution**: Real Ray clusters and operations
- **Coverage**: Complex multi-component workflows

## Running Tests

### Make Targets

```bash
# Fast unit tests for development
make test-fast

# Critical functionality validation  
make test-smoke

# Complete test suite including E2E
make test
```

### Direct pytest Commands

```bash
# Individual component tests
pytest tests/test_core_job_manager.py
pytest tests/test_core_state_manager.py::TestStateValidation

# Test categories
pytest tests/test_core_*.py          # All unit tests
pytest tests/test_e2e_*.py           # All E2E tests  
pytest tests/test_mcp_integration.py # Integration tests

# With coverage
pytest --cov=ray_mcp.core --cov-report=term-missing
```

## Test Organization

### Core Component Tests

Each `test_core_*.py` file follows consistent patterns:

- **Setup/Teardown**: Clean component initialization and cleanup
- **Happy Path**: Primary functionality testing
- **Error Cases**: Exception handling and validation
- **Edge Cases**: Boundary conditions and unusual inputs
- **Integration Points**: Component interaction testing

### Example Test Structure

```python
class TestJobManager:
    """Test suite for JobManager component."""
    
    def test_submit_job_success(self):
        """Test successful job submission."""
        
    def test_submit_job_validation_error(self):
        """Test job submission with invalid parameters."""
        
    def test_job_status_retrieval(self):
        """Test job status retrieval functionality."""
```

## Test Guidelines

### ✅ Best Practices

- **Single Responsibility**: Each test verifies one specific behavior
- **Clear Naming**: Test names describe what is being tested
- **Arrange-Act-Assert**: Clear test structure with distinct phases
- **Mock External Dependencies**: Unit tests should be isolated
- **Parameterized Tests**: Use `@pytest.mark.parametrize` for variations

### ❌ Avoid

- **Testing Implementation Details**: Focus on behavior, not internals
- **Overly Complex Tests**: Keep tests simple and focused
- **Brittle Assertions**: Don't assert on exact string matches
- **Shared State**: Tests should be independent and repeatable

## Component-Specific Testing

### StateManager Tests
- Thread safety validation
- State transitions and validation
- Concurrent access scenarios

### PortManager Tests  
- Port allocation and deallocation
- File locking mechanisms
- Race condition prevention

### ClusterManager Tests
- Cluster lifecycle operations
- Process management
- Resource configuration

### JobManager Tests
- Job submission and management
- Client lifecycle handling  
- Job inspection and monitoring

### LogManager Tests
- Log retrieval with memory limits
- Error analysis functionality
- Pagination support

## Debugging Tests

### Verbose Output

```bash
# Detailed test output
pytest -v --tb=short

# Stop on first failure
pytest -x

# Live log output
pytest --log-cli-level=DEBUG
```

### Individual Test Debugging

```bash
# Run specific test with debug info
pytest tests/test_core_job_manager.py::TestJobManager::test_submit_job -v -s

# With pdb debugging
pytest --pdb tests/test_core_job_manager.py::TestJobManager::test_submit_job
```

## Coverage and Quality

### Coverage Goals
- **Unit Tests**: High coverage of core component logic
- **Integration Tests**: Key interface and protocol paths
- **E2E Tests**: Critical user workflows and error paths

### Quality Metrics
- All tests must pass before merging
- No flaky or intermittent test failures
- Tests should complete within reasonable time limits
- Clear failure messages that aid debugging

## Adding New Tests

### For New Components

1. Create `test_core_new_component.py`
2. Follow existing test structure patterns
3. Include comprehensive error case testing
4. Add integration points to system tests

### For New Features

1. Add unit tests to appropriate `test_core_*.py` file
2. Update integration tests if MCP interface changes
3. Add E2E tests for user-facing functionality
4. Ensure backward compatibility testing

---

*Optimized for maintainable, comprehensive testing of the modular architecture.*