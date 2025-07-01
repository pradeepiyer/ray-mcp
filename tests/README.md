# Ray MCP Tests

Optimized test suite focused on maintainability and proper test classification.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and test utilities
├── test_ray_manager.py      # Core Ray manager unit tests
├── test_worker_manager.py   # Worker node management tests
├── test_integration.py      # Essential integration tests
├── test_e2e_integration.py  # End-to-end workflow tests
└── test_main.py            # MCP server entry point tests
```

## Test Categories

### Unit Tests (`@pytest.mark.fast`)
- **100% mocked** - No real Ray operations
- **Fast execution** - Complete in seconds
- **Implementation focused** - Test individual components
- Files: `test_ray_manager.py`, `test_worker_manager.py`, `test_main.py`

### Integration Tests (`@pytest.mark.integration`)
- **Partially mocked** - Test component interactions
- **Moderate speed** - Ray manager + tool registry integration
- File: `test_integration.py`

### End-to-End Tests (`@pytest.mark.e2e`, `@pytest.mark.slow`)
- **No mocking** - Real Ray clusters and workflows
- **Slow execution** - Full system testing
- **User journey focused** - Critical workflows only
- File: `test_e2e_integration.py`

## Running Tests

```bash
# Fast unit tests only (recommended for development)
pytest -m fast

# All tests except E2E
pytest -m "not e2e"

# Full test suite including E2E
pytest

# With coverage
pytest --cov=ray_mcp --cov-report=term-missing
```

## Test Organization Principles

### ✅ Do
- **One behavior per test** - Test specific functionality, not implementation details
- **Parameterize similar tests** - Use `@pytest.mark.parametrize` for variations
- **Group related tests** - Logical test classes with focused responsibilities
- **Mock external dependencies** - Unit tests should be isolated and fast

### ❌ Don't
- **Over-test implementation details** - Focus on behavior, not internal methods
- **Create redundant tests** - Each test should add unique value
- **Mix test types** - Keep unit/integration/E2E boundaries clear
- **Add new test files** - Extend existing files unless absolutely necessary

## Test Classes

### `test_ray_manager.py`
- **`TestRayManagerCore`** - Cluster lifecycle, state management, validation
- **`TestProcessCommunication`** - Streaming, timeouts, port allocation
- **`TestLogProcessing`** - Log handling, memory limits, analysis

### Key Guidelines
- E2E tests are **reserved for critical user workflows only**
- Add new tests to existing files and classes
- Maintain the logical class structure in `test_ray_manager.py`
- All tests must pass before merging

## Coverage Philosophy
- **Quality over quantity** - Meaningful tests, not coverage theater
- **Focus on critical paths** - Core modules like `ray_manager.py`, `tool_registry.py`
- **Behavior over implementation** - Test what matters to users

## Debugging Failed Tests

```bash
# Verbose output with short traceback
pytest -v --tb=short

# Stop on first failure
pytest -x

# Run specific test
pytest tests/test_ray_manager.py::TestRayManagerCore::test_cluster_lifecycle
```

---

*Optimized for maintainability. Each test adds unique value while minimizing technical debt.*