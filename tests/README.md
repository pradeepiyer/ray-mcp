# Ray MCP Test Suite

A comprehensive test suite for the Ray MCP server, organized for maintainability and efficient development.

## Test Organization

**Integration over Unit Tests**: Focus on testing workflows and behavior rather than implementation details. This approach provides better bug detection while requiring less maintenance as code evolves.

**Strategic Coverage**: Test critical system functionality that users depend on, not every getter/setter or utility function.

**Behavior-Driven**: Tests should validate what the system does, not how it does it internally.

## Test Structure

```
tests/
├── test_core_functionality.py    # Tool registry, unified manager, system interfaces
├── test_managers.py              # Manager behavior patterns & cross-integration  
├── test_kubernetes.py            # Kubernetes/KubeRay operations & workflows
├── test_mcp_server.py            # End-to-end integration tests
├── helpers/                      # Reusable test utilities
│   ├── fixtures.py              # Core test fixtures
│   ├── utils.py                 # General utilities & test helpers
│   ├── e2e.py                   # End-to-end testing workflows
│   └── __init__.py              # Convenient imports
└── conftest.py                   # Streamlined core fixtures
```

## Running Tests

### All Tests
```bash
pytest
```

### Fast Tests Only
```bash
pytest -m fast
```

### Integration Tests
```bash
pytest tests/test_mcp_server.py
```

### GKE Integration (requires GKE environment)
```bash
pytest -m gke
```

### Specific Test Files
```bash
pytest tests/test_core_functionality.py
pytest tests/test_managers.py  
pytest tests/test_kubernetes.py
```

## Test Categories

### Core Functionality (`test_core_functionality.py`)
- **Tool Registry**: MCP protocol integration, tool execution workflows
- **Unified Manager**: Component delegation, architecture validation
- **System Interfaces**: MCP server startup, workflow integration
- **Foundation Components**: Critical imports, base managers, utilities

**Focus**: System-level behavior and contracts that users interact with.

### Manager Behavior (`test_managers.py`)
- **Behavior Patterns**: How managers handle common operations
- **Cross-Manager Integration**: Component interaction and delegation
- **Error Handling**: Consistent error patterns across managers
- **State Management**: Manager state coordination and consistency

**Focus**: Manager contracts and integration patterns, not implementation details.

### Kubernetes Operations (`test_kubernetes.py`)
- **CRD Operations**: Ray cluster and job custom resource management
- **KubeRay Workflows**: Complete cluster and job lifecycle testing
- **Kubernetes Integration**: Cluster connection, authentication, operations
- **Cloud Provider Coordination**: GKE integration and coordination
- **Error Handling**: Kubernetes-specific error patterns

**Focus**: End-to-end Kubernetes workflows and KubeRay operator integration.

### Integration Tests (`test_mcp_server.py`)
- **GKE + KubeRay Workflow**: Complete end-to-end integration testing
- **System Integration**: Full workflow validation with real components
- **Environment Setup**: Test environment configuration and validation

**Focus**: Real-world usage scenarios with minimal mocking.

## Test Utilities (`helpers/`)

### Fixtures (`helpers/fixtures.py`)
```python
from tests.helpers import e2e_ray_manager

async def test_something(e2e_ray_manager):
    # Use the configured manager
    result = await e2e_ray_manager.init_cluster()
```

### Utilities (`helpers/utils.py`)
```python
from tests.helpers import E2EConfig, TempScriptManager, TestScripts

# Environment configuration
config = E2EConfig.from_environment()

# Temporary script management
with TempScriptManager() as script_manager:
    script_path = script_manager.create_script("print('hello')")
```

### End-to-End Workflows (`helpers/e2e.py`)
```python
from tests.helpers import E2EWorkflows

# Complete workflow testing
await E2EWorkflows.start_cluster_and_submit_job(
    manager, job_script="print('test')"
)
```

## Writing Tests

### Guidelines

1. **Test Behavior, Not Implementation**
   ```python
   # Good: Tests what happens
   result = await manager.submit_job("python script.py")
   assert result["status"] == "success"
   assert "job_id" in result
   
   # Avoid: Tests how it's implemented
   assert manager._internal_method.call_count == 1
   ```

2. **Use Integration Over Unit Tests**
   ```python
   # Good: Tests real workflow
   await registry.execute_tool("init_ray_cluster", {"num_cpus": 2})
   result = await registry.execute_tool("submit_ray_job", {"entrypoint": "python script.py"})
   
   # Avoid: Excessive mocking
   mock_manager.method1.return_value = {...}
   mock_manager.method2.return_value = {...}
   ```

3. **Focus on User-Facing Functionality**
   - Tool execution workflows
   - Manager delegation patterns  
   - Error handling and recovery
   - System integration points

4. **Use Descriptive Test Names**
   ```python
   def test_kuberay_cluster_lifecycle_workflow():
       """Test complete KubeRay cluster creation, scaling, and deletion."""
   
   def test_system_workflow_integration():
       """Test that core system workflows integrate properly."""
   ```

### Adding New Tests

1. **Choose the Right File**:
   - Tool/registry behavior → `test_core_functionality.py`
   - Manager interactions → `test_managers.py`
   - Kubernetes workflows → `test_kubernetes.py`
   - Full integration → `test_mcp_server.py`

2. **Use Existing Helpers**:
   ```python
   from tests.helpers import e2e_ray_manager, E2EWorkflows
   ```

3. **Mark Tests Appropriately**:
   ```python
   @pytest.mark.fast
   def test_quick_validation():
       pass
   
   @pytest.mark.gke  
   def test_gke_integration():
       pass
   ```

## Test Markers

- `@pytest.mark.fast`: Quick tests (default, no external dependencies)
- `@pytest.mark.gke`: Requires GKE environment and credentials
- `@pytest.mark.asyncio`: Async test functions

## Environment Requirements

### Basic Tests
- Python 3.10+
- Ray MCP dependencies (see `pyproject.toml`)

### GKE Integration Tests
- Google Cloud SDK (`gcloud`)
- GKE cluster access
- Service account credentials
- Environment variables: `GOOGLE_APPLICATION_CREDENTIALS`, `GKE_PROJECT_ID`, `GKE_CLUSTER_NAME`, `GKE_ZONE`

## Benefits of This Structure

1. **Maintainability**: Fewer files to update when code changes
2. **Quality**: Tests catch real bugs in user workflows  
3. **Speed**: Faster test development and execution
4. **Clarity**: Clear organization by functionality domain
5. **Strategic Value**: Focus on critical system behavior

## Migration from Legacy Tests

This test suite replaces numerous smaller unit test files with strategic, behavior-focused tests. The new structure provides:

- **64% fewer test files** while maintaining coverage
- **Integration-focused testing** for better bug detection
- **Behavior validation** over implementation testing
- **Faster development cycle** with less brittle tests