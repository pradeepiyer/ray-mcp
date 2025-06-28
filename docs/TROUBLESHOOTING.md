# Troubleshooting Guide

This guide provides solutions for common issues encountered when using the Ray MCP Server.

## Common Issues and Solutions

### 1. Ray Initialization Problems

#### Issue: "Ray is not initialized. Please start Ray first."

**Symptoms**: Tools return this error when trying to use Ray functionality.

**Causes**:
- Ray cluster hasn't been started
- Ray initialization failed
- Connection to existing cluster failed

**Solutions**:
```json
// First, initialize Ray
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4
  }
}

// Then use other tools
{
  "tool": "inspect_ray",
  "arguments": {}
}
```

#### Issue: Port conflicts during cluster startup

**Symptoms**: Error messages about ports being in use.

**Solutions**:
```json
// Use automatic port allocation
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4
    // Don't specify head_node_port or dashboard_port
  }
}

// Or specify different ports
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4,
    "head_node_port": 10002,
    "dashboard_port": 8266
  }
}
```

### 2. Test Environment Issues

#### Issue: Tests fail in CI but pass locally

**Symptoms**: E2E tests fail in GitHub Actions but work on your machine.

**Causes**:
- Resource constraints in CI environment
- Different environment detection
- Timing issues with CI resources

**Solutions**:

**Check Environment Detection**:
```bash
# Verify CI environment detection
echo $GITHUB_ACTIONS
echo $CI

# Run tests in CI mode locally
CI=true uv run pytest tests/test_e2e_integration.py
```

**Resource Optimization**:
- CI tests automatically use head node only (1 CPU)
- Local tests use full cluster (2 CPU head + 2 workers)
- Wait times are reduced in CI (10s vs 30s)

**Debug CI Issues**:
```bash
# Run with verbose output in CI
CI=true uv run pytest tests/test_e2e_integration.py -v -s

# Check resource usage
ray status
```

#### Issue: E2E tests take too long

**Symptoms**: Tests run for several minutes or timeout.

**Solutions**:

**For CI Environments**:
```bash
# Ensure CI mode is enabled
export CI=true
export GITHUB_ACTIONS=true

# Run optimized tests
uv run pytest tests/test_e2e_integration.py
```

**For Local Development**:
```bash
# Run unit tests only for fast feedback
uv run pytest tests/ -k "not e2e"

# Run e2e tests separately
uv run pytest tests/test_e2e_integration.py
```

### 3. Multi-Node Cluster Issues

#### Issue: Worker nodes fail to start

**Symptoms**: Head node starts but worker nodes show errors.

**Causes**:
- Resource conflicts between head and worker nodes
- Network connectivity issues
- Insufficient system resources

**Solutions**:
```json
// Ensure worker resources don't exceed head node capacity
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4,
    "worker_nodes": [
      {
        "num_cpus": 2,  // Less than head node
        "node_name": "worker-1"
      }
    ]
  }
}

// Check cluster status
{
  "tool": "inspect_ray",
  "arguments": {}
}
```

#### Issue: Worker nodes not connecting to head node

**Symptoms**: Workers start but don't appear in cluster info.

**Solutions**:
- Check network connectivity between nodes
- Verify firewall settings
- Ensure head node is accessible from worker machines

### 4. Job Submission Issues

#### Issue: Job submission fails

**Symptoms**: Jobs fail to submit or start.

**Causes**:
- Invalid entrypoint command
- Missing runtime environment
- Resource constraints

**Solutions**:
```json
// Use absolute paths for entrypoint
{
  "tool": "submit_job",
  "arguments": {
    "entrypoint": "python /full/path/to/script.py"
  }
}

// Add runtime environment if needed
{
  "tool": "submit_job",
  "arguments": {
    "entrypoint": "python script.py",
    "runtime_env": {
      "pip": ["numpy", "pandas"]
    }
  }
}
```

#### Issue: Jobs hang or timeout

**Symptoms**: Jobs start but don't complete or take too long.

**Solutions**:
```json
// Check job status
{
  "tool": "inspect_job",
  "arguments": {
    "job_id": "your_job_id"
  }
}

// Retrieve job logs for debugging
{
  "tool": "retrieve_logs",
  "arguments": {
    "identifier": "your_job_id",
    "log_type": "job"
  }
}
```

### 5. Resource Management Issues

#### Issue: High resource usage in CI

**Symptoms**: CI builds fail due to resource constraints.

**Solutions**:

**Automatic Optimization**:
- Tests automatically detect CI environment
- Head node only configuration in CI
- Reduced wait times and resource allocation

**Manual Optimization**:
```bash
# Force CI mode
export CI=true

# Run minimal tests
uv run pytest tests/ -k "not e2e"

# Run e2e tests with minimal resources
CI=true uv run pytest tests/test_e2e_integration.py
```

#### Issue: Memory issues with large jobs

**Symptoms**: Jobs fail due to insufficient memory.

**Solutions**:
```json
// Increase object store memory
{
  "tool": "init_ray",
  "arguments": {
    "num_cpus": 4,
    "object_store_memory": 2000000000  // 2GB
  }
}

// Monitor memory usage
{
  "tool": "inspect_ray",
  "arguments": {}
}
```

### 6. Test Suite Issues

#### Issue: Unit tests fail

**Symptoms**: Unit tests fail with import or assertion errors.

**Solutions**:
```bash
# Clean up environment
./scripts/ray_cleanup.sh

# Reinstall dependencies
uv sync --all-extras --dev

# Run tests with verbose output
uv run pytest tests/ -k "not e2e" -v -s
```

#### Issue: E2E tests fail intermittently

**Symptoms**: E2E tests pass sometimes but fail randomly.

**Solutions**:
```bash
# Clean up Ray processes
ray stop
pkill -f ray

# Run cleanup script
./scripts/ray_cleanup.sh

# Run tests with retry
uv run pytest tests/test_e2e_integration.py --maxfail=1 -x
```

### 7. Development Environment Issues

#### Issue: Import errors

**Symptoms**: Module import errors when running tests or server.

**Solutions**:
```bash
# Verify virtual environment
which python
echo $VIRTUAL_ENV

# Reinstall package
uv pip install -e .

# Check dependencies
uv pip list | grep ray
```

#### Issue: Code formatting issues

**Symptoms**: Linting or formatting errors.

**Solutions**:
```bash
# Format code
uv run black ray_mcp/ tests/

# Sort imports
uv run isort ray_mcp/ tests/

# Type checking
uv run pyright ray_mcp/
```

### 8. Performance Issues

#### Issue: Slow test execution

**Symptoms**: Tests take longer than expected.

**Solutions**:

**Optimize Test Execution**:
```bash
# Run only unit tests for fast feedback
uv run pytest tests/ -k "not e2e"

# Run specific test categories
uv run pytest tests/test_ray_manager.py

# Use parallel execution (if supported)
uv run pytest tests/ -n auto
```

**Monitor Performance**:
```bash
# Track execution times
time uv run pytest tests/ -k "not e2e"
time uv run pytest tests/test_e2e_integration.py

# Check resource usage
top -p $(pgrep -f pytest)
```

### 9. CI/CD Issues

#### Issue: GitHub Actions failures

**Symptoms**: CI builds fail consistently.

**Solutions**:

**Check CI Configuration**:
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

**Debug CI Issues**:
```bash
# Run tests locally in CI mode
CI=true uv run pytest tests/ -v -s

# Check environment variables
env | grep -E "(CI|GITHUB|RAY)"
```

### 10. Logging and Debugging

#### Issue: Insufficient logging information

**Symptoms**: Hard to debug issues due to lack of information.

**Solutions**:
```bash
# Enable debug logging
export RAY_LOG_LEVEL=DEBUG
export RAY_MCP_DEBUG=true

# Run with verbose output
uv run pytest tests/ -v -s --tb=long

# Check Ray logs
tail -f /tmp/ray/session_*/logs/*
```

#### Issue: Log retrieval fails

**Symptoms**: Can't retrieve logs from jobs or nodes.

**Solutions**:
```json
// Try different log types
{
  "tool": "retrieve_logs",
  "arguments": {
    "identifier": "job_id",
    "log_type": "job"
  }
}

// Check available log types
{
  "tool": "inspect_job",
  "arguments": {
    "job_id": "job_id",
    "mode": "debug"
  }
}
```

## Environment-Specific Troubleshooting

### CI Environment

**Common Issues**:
- Resource constraints
- Timing issues
- Environment detection problems

**Solutions**:
```bash
# Force CI mode
export CI=true
export GITHUB_ACTIONS=true

# Use minimal resources
uv run pytest tests/test_e2e_integration.py

# Check resource usage
free -h
nproc
```

### Local Development

**Common Issues**:
- Port conflicts
- Resource conflicts
- Dependency issues

**Solutions**:
```bash
# Clean up environment
./scripts/ray_cleanup.sh

# Check for conflicting processes
ps aux | grep ray
lsof -i :10001

# Reinstall dependencies
uv sync --all-extras --dev
```

## Getting Help

### Before Asking for Help

1. **Check this guide** for your specific issue
2. **Run cleanup scripts**: `./scripts/ray_cleanup.sh`
3. **Check environment**: Verify Python version, dependencies, and environment variables
4. **Run tests**: Ensure tests pass in your environment
5. **Check logs**: Look for error messages and stack traces

### Providing Information

When reporting issues, include:

- **Environment**: OS, Python version, Ray version
- **Error messages**: Full error output and stack traces
- **Steps to reproduce**: Exact commands and configuration
- **Expected vs actual behavior**: What you expected vs what happened
- **Test results**: Output from running the test suite

### Resources

- **[Development Guide](DEVELOPMENT.md)**: Development workflow and best practices
- **[Configuration Guide](CONFIGURATION.md)**: Setup and configuration options
- **[Examples](EXAMPLES.md)**: Usage examples and patterns
- **[Tools Reference](TOOLS.md)**: Complete tool documentation 