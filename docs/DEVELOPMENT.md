# Development Guide

This guide covers the development workflow, testing strategies, and best practices for the Ray MCP Server.

## Development Setup

### Prerequisites

- Python 3.10+
- uv package manager
- Ray (installed automatically via dependencies)

### Initial Setup

```bash
# Clone the repository
git clone <repository-url>
cd mcp

# Install dependencies
uv sync --all-extras --dev

# Verify installation
uv run pytest tests/ -k "not e2e" --tb=short
```

## Project Structure

```
mcp/
├── ray_mcp/                    # Core server implementation
│   ├── __init__.py
│   ├── main.py                # MCP server entry point
│   ├── ray_manager.py         # Ray cluster management
│   ├── worker_manager.py      # Worker node management
│   ├── tool_registry.py       # MCP tool registry
│   └── tool_functions.py      # Individual tool functions
├── tests/                     # Test suite
│   ├── conftest.py           # Pytest configuration
│   ├── test_e2e_integration.py  # Optimized e2e tests
│   ├── test_integration.py      # Integration tests
│   ├── test_main.py             # Main module tests
│   ├── test_ray_manager.py      # Ray manager unit tests
│   ├── test_worker_manager.py   # Worker manager tests
│   └── test_multi_node_cluster.py # Multi-node cluster tests
├── examples/                  # Example scripts
├── docs/                      # Documentation
├── scripts/                   # Utility scripts
├── pyproject.toml            # Project configuration
└── pytest.ini               # Pytest configuration
```

## Testing Strategy

### Test Categories

The project uses a comprehensive testing strategy with three main categories:

#### 1. Unit Tests
- **Purpose**: Test individual components in isolation
- **Execution Time**: Fast execution for quick feedback
- **Coverage**: Core functionality, error handling, edge cases
- **Location**: `tests/test_*.py` (excluding e2e)

#### 2. Integration Tests
- **Purpose**: Test component interactions and workflows
- **Execution Time**: Fast execution (included in unit test suite)
- **Coverage**: Tool registry, MCP integration, parameter validation

#### 3. End-to-End Tests
- **Purpose**: Test complete workflows in real Ray clusters
- **Execution Time**: 
  - CI: Optimized for minimal resource usage
  - Local: Full cluster testing with comprehensive coverage
- **Coverage**: Complete cluster lifecycle, job management, debugging

### Environment-Specific Optimization

The test suite automatically adapts to different environments:

#### CI Environment
- **Detection**: `GITHUB_ACTIONS=true` or `CI=true`
- **Configuration**: Head node only (1 CPU)
- **Wait Times**: 10 seconds
- **Resource Usage**: Minimal for CI constraints

#### Local Environment
- **Configuration**: Full cluster (2 CPU head + 2 worker nodes)
- **Wait Times**: 30 seconds
- **Resource Usage**: Comprehensive testing

### Running Tests

```bash
# Run all tests (including e2e)
uv run pytest tests/

# Run unit tests only (fast)
uv run pytest tests/ -k "not e2e"

# Run e2e tests only
uv run pytest tests/test_e2e_integration.py

# Run specific test file
uv run pytest tests/test_ray_manager.py

# Run with coverage
uv run pytest tests/ --cov=ray_mcp --cov-report=html

# Run in CI mode (head node only)
CI=true uv run pytest tests/test_e2e_integration.py

# Run with verbose output
uv run pytest tests/ -v --tb=short
```

### Test Performance Metrics

| Test Category | Execution Time | Coverage |
|---------------|----------------|----------|
| Unit Tests | Fast | High |
| E2E Tests (CI) | Optimized | Good |
| E2E Tests (Local) | Moderate | Good |
| **Total** | **Fast to Moderate** | **Comprehensive** |

## Development Workflow

### 1. Feature Development

```bash
# Create feature branch
git checkout -b feature/new-feature

# Make changes
# ... edit files ...

# Run tests
uv run pytest tests/ -k "not e2e"  # Fast feedback
uv run pytest tests/               # Full test suite

# Commit changes
git add .
git commit -m "Add new feature"
```

### 2. Code Quality Checks

```bash
# Format code
uv run black ray_mcp/ tests/
uv run isort ray_mcp/ tests/

# Type checking
uv run pyright ray_mcp/

# Lint tool functions
uv run python scripts/lint_tool_functions.py

# Run all quality checks
uv run black --check ray_mcp/ tests/
uv run isort --check-only ray_mcp/ tests/
uv run pyright ray_mcp/
```

### 3. Testing Best Practices

#### Before Committing
- Run unit tests: `uv run pytest tests/ -k "not e2e"`
- Ensure all tests pass
- Check code formatting and linting

#### Before Pushing
- Run full test suite: `uv run pytest tests/`
- Verify e2e tests pass in both CI and local modes
- Check coverage reports

#### For Major Changes
- Test in CI mode: `CI=true uv run pytest tests/test_e2e_integration.py`
- Test in local mode: `uv run pytest tests/test_e2e_integration.py`
- Update documentation if needed

## Test Optimization History

### Recent Optimizations

The test suite has been optimized for CI environments:

#### E2E Test Optimizations
- **Removed redundant tests**: Eliminated unnecessary e2e tests
- **CI resource optimization**: Head node only in CI environments
- **Reduced wait times**: 10s in CI vs 30s locally
- **Lightweight test jobs**: Replaced heavy examples with minimal test scripts

#### Unit Test Optimizations
- **Removed duplicate tests**: Eliminated redundant unit tests
- **Improved test isolation**: Better mocking and cleanup
- **Faster execution**: Optimized for quick feedback

### Performance Improvements

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| E2E Test Count | Multiple | Few | Significant reduction |
| Unit Test Count | Many | Optimized | Reduced redundancy |
| CI Execution Time | Slow | Fast | Much faster |
| Resource Usage (CI) | High | Low | Minimal usage |

## Debugging

### Common Issues

#### Ray Process Cleanup
```bash
# Clean up Ray processes
./scripts/ray_cleanup.sh

# Or manually
ray stop
pkill -f ray
```

#### Test Failures
```bash
# Run specific failing test
uv run pytest tests/test_ray_manager.py::TestRayManager::test_specific_test -v -s

# Run with debug output
uv run pytest tests/ -v -s --tb=long

# Check Ray status
ray status
```

#### Environment Issues
```bash
# Verify Ray installation
python -c "import ray; print(ray.__version__)"

# Check environment variables
echo $GITHUB_ACTIONS
echo $CI
```

### Debugging E2E Tests

```bash
# Run e2e test with verbose output
uv run pytest tests/test_e2e_integration.py::TestE2EIntegration::test_complete_ray_workflow -v -s

# Run in CI mode for debugging
CI=true uv run pytest tests/test_e2e_integration.py -v -s

# Check cluster status during test
ray status
```

## CI/CD Integration

### GitHub Actions

The project includes optimized CI workflows:

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  test-full:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: "3.10"
    - name: Install uv
      uses: astral-sh/setup-uv@v1
    - name: Install dependencies
      run: uv sync --all-extras --dev
    - name: Run full test suite
      run: uv run pytest tests/ --tb=short -v --cov=ray_mcp --cov-report=xml
```

### CI Optimizations

- **Automatic environment detection**: Tests run in CI mode automatically
- **Resource constraints**: Head node only for minimal resource usage
- **Fast execution**: Optimized for CI time limits
- **Comprehensive coverage**: All essential functionality tested

## Contributing

### Pull Request Process

1. **Fork and clone** the repository
2. **Create feature branch**: `git checkout -b feature/your-feature`
3. **Make changes** following the development workflow
4. **Run tests**: Ensure all tests pass
5. **Update documentation**: If needed
6. **Submit PR**: With clear description of changes

### Code Review Checklist

- [ ] All tests pass (unit + e2e)
- [ ] Code is formatted and linted
- [ ] Documentation is updated
- [ ] No breaking changes (or documented)
- [ ] Performance impact considered
- [ ] CI optimizations maintained

### Testing Requirements

- **New features**: Must include unit tests
- **Bug fixes**: Must include regression tests
- **E2E changes**: Must test in both CI and local modes
- **Performance changes**: Must measure impact

## Performance Monitoring

### Test Performance Tracking

Monitor test performance over time:

```bash
# Track execution times
time uv run pytest tests/ -k "not e2e"
time uv run pytest tests/test_e2e_integration.py

# Check coverage trends
uv run pytest tests/ --cov=ray_mcp --cov-report=term-missing
```

### Resource Usage Monitoring

- **CI builds**: Monitor execution time and resource usage
- **Local development**: Track test performance on different machines
- **Coverage reports**: Ensure coverage doesn't decrease

## Best Practices

### Code Quality

- **Type hints**: Use throughout the codebase
- **Docstrings**: Document all public functions
- **Error handling**: Comprehensive error handling and logging
- **Testing**: High test coverage with meaningful tests

### Performance

- **Resource optimization**: Minimize resource usage in CI
- **Fast feedback**: Unit tests should run quickly
- **Efficient cleanup**: Proper resource cleanup in tests
- **Environment detection**: Automatic optimization based on environment

### Maintainability

- **Clear structure**: Well-organized project structure
- **Documentation**: Keep documentation up to date
- **Consistent patterns**: Follow established patterns
- **Regular updates**: Keep dependencies updated