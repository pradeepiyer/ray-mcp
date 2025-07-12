# Development Guide

Comprehensive development guide for Ray MCP contributors covering local Ray clusters, KubeRay integration, and cloud provider support.

## Development Setup

### Prerequisites

- **Python** ≥ 3.10
- **uv** package manager (recommended) - [Installation Guide](https://docs.astral.sh/uv/)
- **Git** for version control
- **Docker** (optional, for Kubernetes development)
- **kubectl** (for KubeRay development)

### Local Development Environment

```bash
# Clone repository
git clone https://github.com/pradeepiyer/ray-mcp.git
cd ray-mcp

# Install with all dependencies including cloud providers
uv sync --extra all

# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows

# Verify installation
python -c "import ray_mcp; print('Ray MCP installed successfully')"
```

### Development Dependencies

```bash
# Install development tools
uv sync --extra dev

# Verify development setup
uv run pytest --version
uv run black --version
uv run pyright --version
```

### Cloud Provider Setup for Development

#### Google Cloud (GKE) Development

```bash
# Install GKE dependencies
uv sync --extra gke

# Set up service account for testing
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/test-service-account.json"
export GOOGLE_CLOUD_PROJECT="your-test-project"

# Verify GKE setup
python -c "from google.cloud import container_v1; print('GKE client available')"
```

#### Local Kubernetes Development

```bash
# Install minikube for local testing
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube

# Start test cluster
minikube start --cpus=4 --memory=8192

# Install KubeRay operator
kubectl create namespace kuberay-system
kubectl apply -f https://raw.githubusercontent.com/ray-project/kuberay/release-0.8/deploy/kuberay-operator.yaml

# Verify setup
kubectl get pods -n kuberay-system
```

## Architecture Overview

Ray MCP uses a modular architecture supporting both local Ray clusters and Kubernetes-based deployments.

### Directory Structure

```
ray_mcp/
├── main.py                     # MCP server entry point
├── tool_registry.py            # Centralized tool definitions and routing
├── __init__.py                 # Package initialization
├── foundation/                 # Core foundation layer
│   ├── base_managers.py        # Base classes and resource management
│   ├── interfaces.py           # Protocols and type definitions
│   ├── import_utils.py         # Dynamic import utilities
│   ├── logging_utils.py        # Logging and response formatting
│   └── test_mocks.py          # Testing utilities and mocks
├── managers/                   # Business logic managers
│   ├── unified_manager.py      # Main orchestration layer
│   ├── cluster_manager.py      # Local Ray cluster operations
│   ├── job_manager.py          # Local Ray job management
│   ├── log_manager.py          # Log retrieval and analysis
│   ├── port_manager.py         # Port allocation and management
│   └── state_manager.py        # Cluster state management
├── kubernetes/                 # Kubernetes and KubeRay integration
│   ├── config/                 # Kubernetes configuration
│   │   ├── kubernetes_client.py
│   │   └── kubernetes_config.py
│   ├── crds/                   # Custom Resource Definitions
│   │   ├── base_crd_manager.py
│   │   ├── ray_cluster_crd.py
│   │   └── ray_job_crd.py
│   └── managers/               # Kubernetes-specific managers
│       ├── kubernetes_manager.py
│       ├── kuberay_cluster_manager.py
│       └── kuberay_job_manager.py
├── cloud/                      # Cloud provider integration
│   ├── config/                 # Cloud configuration
│   │   ├── cloud_provider_config.py
│   │   └── cloud_provider_detector.py
│   └── providers/              # Cloud provider implementations
│       ├── cloud_provider_manager.py
│       └── gke_manager.py
└── tools/                      # Tool schemas and utilities
    ├── cluster_tools.py        # Cluster management tool schemas
    ├── job_tools.py            # Job management tool schemas
    ├── cloud_tools.py          # Cloud provider tool schemas
    ├── log_tools.py            # Log management tool schemas
    └── schema_utils.py         # Shared schema utilities
```

### Core Architecture Layers

#### 1. Foundation Layer (`foundation/`)
- **Base Managers** - Abstract base classes with common functionality
- **Interfaces** - Protocol definitions for type safety and contracts
- **Import Utils** - Dynamic imports for optional dependencies
- **Logging Utils** - Standardized logging and response formatting

#### 2. Manager Layer (`managers/`)
- **Unified Manager** - Main orchestration coordinating all subsystems
- **Cluster Manager** - Local Ray cluster lifecycle management
- **Job Manager** - Local Ray job operations and monitoring
- **State Manager** - Thread-safe cluster state tracking
- **Port Manager** - Port allocation with conflict resolution

#### 3. Kubernetes Layer (`kubernetes/`)
- **CRD Managers** - RayCluster and RayJob custom resource management
- **Kubernetes Manager** - Cluster discovery and connection
- **KubeRay Managers** - KubeRay-specific cluster and job operations

#### 4. Cloud Layer (`cloud/`)
- **Provider Managers** - Cloud-specific cluster operations (GKE, etc.)
- **Configuration** - Cloud provider detection and setup
- **Authentication** - Service account and credential management

#### 5. Tools Layer (`tools/`)
- **Schema Definitions** - JSON schemas for all MCP tools
- **Validation** - Parameter validation and type checking
- **Documentation** - Schema-driven tool documentation

## Development Workflow

### Code Quality

```bash
# Format code
make format

# Run linting
make lint

# Enhanced linting with tool function signature validation
make lint-enhanced

# Type checking
uv run pyright

# Complete quality check
make lint && make format && uv run pyright
```

### Running the Development Server

```bash
# Basic server
uv run ray-mcp

# With enhanced LLM output
RAY_MCP_ENHANCED_OUTPUT=true uv run ray-mcp

# With debug logging
RAY_MCP_LOG_LEVEL=DEBUG uv run ray-mcp

# With all cloud features enabled
GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json \
RAY_MCP_ENHANCED_OUTPUT=true \
uv run ray-mcp
```

### Interactive Development

```python
# Test components directly
from ray_mcp.managers.unified_manager import RayUnifiedManager

# Initialize manager
manager = RayUnifiedManager()

# Test local cluster operations
result = await manager.init_ray_cluster()
print(result)

# Test KubeRay operations
result = await manager.init_ray_cluster(
    cluster_type="kubernetes",
    cluster_name="test-cluster"
)
print(result)
```

## Testing Strategy

### Test Architecture

The project uses a comprehensive testing strategy covering multiple environments:

```
tests/
├── conftest.py                 # Core test configuration and fixtures
├── helpers/                    # Reusable test utilities
│   ├── fixtures.py            # Common test fixtures
│   ├── utils.py               # Test helper functions
│   ├── e2e.py                 # End-to-end test utilities
│   └── __init__.py            # Test helper imports
├── test_core_functionality.py # Tool registry and core system tests
├── test_managers.py           # Manager behavior and integration tests
├── test_kubernetes.py         # KubeRay and Kubernetes functionality
└── test_mcp_server.py         # End-to-end MCP integration tests
```

### Running Tests

```bash
# Fast development tests (unit tests only)
make test-fast

# Critical functionality validation
make test-smoke

# Complete test suite including E2E
make test

# Kubernetes/KubeRay tests (requires local cluster)
uv run pytest tests/test_kubernetes.py

# GKE integration tests (requires GKE setup)
uv run pytest -m gke

# Coverage reporting
uv run pytest --cov=ray_mcp --cov-report=html
```

### Test Categories

#### Unit Tests
- **Fast** - Complete in seconds with full mocking
- **Isolated** - Test individual components in isolation
- **Deterministic** - No external dependencies

#### Integration Tests
- **Manager Integration** - Test component interactions
- **MCP Protocol** - Test tool registry and protocol handling
- **Local Ray** - Test local cluster operations

#### End-to-End Tests
- **System Tests** - Complete workflows from tool call to result
- **Kubernetes Tests** - KubeRay cluster and job lifecycle
- **Cloud Tests** - GKE integration with real clusters

### Writing Tests

#### Unit Test Example

```python
# tests/test_managers.py
import pytest
from unittest.mock import AsyncMock, Mock

from ray_mcp.managers.cluster_manager import ClusterManager

@pytest.mark.asyncio
async def test_init_cluster_success():
    # Setup mocks
    state_manager = Mock()
    port_manager = Mock()
    port_manager.get_available_port.return_value = 10001
    
    # Create manager
    manager = ClusterManager(state_manager, port_manager)
    
    # Test operation
    result = await manager.init_ray_cluster(num_cpus=4)
    
    # Assertions
    assert result["status"] == "success"
    assert "cluster_info" in result["data"]
```

#### Integration Test Example

```python
# tests/test_kubernetes.py
@pytest.mark.asyncio
async def test_kuberay_cluster_lifecycle():
    manager = RayUnifiedManager()
    
    # Create cluster
    create_result = await manager.init_ray_cluster(
        cluster_type="kubernetes",
        cluster_name="test-cluster",
        namespace="test-ns"
    )
    assert create_result["status"] == "success"
    
    # Verify cluster exists
    inspect_result = await manager.inspect_ray_cluster(
        cluster_name="test-cluster",
        namespace="test-ns"
    )
    assert inspect_result["status"] == "success"
    
    # Cleanup
    await manager.stop_ray_cluster(
        cluster_name="test-cluster",
        namespace="test-ns"
    )
```

## Adding New Features

### Adding a New Tool

#### 1. Define Tool Schema

Create schema in appropriate tools file:

```python
# ray_mcp/tools/cluster_tools.py
def get_my_new_tool_schema() -> Dict[str, Any]:
    """Schema for my_new_tool."""
    return {
        "type": "object",
        "properties": {
            "cluster_name": get_string_property("Name of the cluster"),
            "config": {
                "type": "object",
                "description": "Configuration options"
            }
        },
        "required": ["cluster_name"]
    }
```

#### 2. Register Tool

Add to tool registry:

```python
# ray_mcp/tool_registry.py
self._register_tool(
    name="my_new_tool",
    description="Description of what the tool does",
    schema=cluster_tools.get_my_new_tool_schema(),
    handler=self._my_new_tool_handler,
)
```

#### 3. Implement Handler

```python
# ray_mcp/tool_registry.py
async def _my_new_tool_handler(self, **kwargs) -> Dict[str, Any]:
    """Handler for my_new_tool."""
    return await self.ray_manager.my_new_operation(**kwargs)
```

#### 4. Add Manager Method

```python
# ray_mcp/managers/unified_manager.py
async def my_new_operation(
    self, 
    cluster_name: str, 
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Implement new operation with proper error handling."""
    try:
        # Implementation logic here
        result = await self._perform_operation(cluster_name, config)
        
        return self._response_formatter.format_success_response(
            message="Operation completed successfully",
            data=result
        )
    except Exception as e:
        return self._response_formatter.format_error_response(
            "my new operation", e
        )
```

#### 5. Add Tests

```python
# tests/test_managers.py
@pytest.mark.asyncio
async def test_my_new_operation():
    manager = RayUnifiedManager()
    
    result = await manager.my_new_operation(
        cluster_name="test-cluster",
        config={"setting": "value"}
    )
    
    assert result["status"] == "success"
    assert "data" in result
```

### Adding Cloud Provider Support

#### 1. Create Provider Manager

```python
# ray_mcp/cloud/providers/new_provider_manager.py
from ...foundation.base_managers import ResourceManager

class NewProviderManager(ResourceManager):
    """Manager for new cloud provider operations."""
    
    def __init__(self, state_manager, detector, config_manager):
        super().__init__(state_manager, enable_cloud=True)
        self._detector = detector
        self._config_manager = config_manager
    
    async def create_cluster(self, cluster_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Create cluster on new provider."""
        # Implementation
        pass
```

#### 2. Add to Unified Cloud Manager

```python
# ray_mcp/cloud/providers/cloud_provider_manager.py
from .new_provider_manager import NewProviderManager

class UnifiedCloudProviderManager:
    def __init__(self, state_manager):
        # ... existing code ...
        self._new_provider_manager = NewProviderManager(
            state_manager, self._detector, self._config_manager
        )
```

#### 3. Update Tool Schemas

```python
# ray_mcp/tools/cloud_tools.py
def get_cloud_provider_property(include_all: bool = False) -> Dict[str, Any]:
    """Update to include new provider."""
    enum_values = ["gke", "local", "new_provider"]  # Add new provider
    # ... rest of implementation
```

### Adding KubeRay Features

#### 1. Extend CRD Manager

```python
# ray_mcp/kubernetes/crds/ray_cluster_crd.py
def create_spec(self, **kwargs) -> Dict[str, Any]:
    """Add new KubeRay cluster features."""
    # Extend existing CRD spec generation
    pass
```

#### 2. Add to KubeRay Managers

```python
# ray_mcp/kubernetes/managers/kuberay_cluster_manager.py
async def new_kuberay_operation(self, **kwargs) -> Dict[str, Any]:
    """Add new KubeRay-specific operation."""
    # Implementation
    pass
```

## Debugging and Troubleshooting

### Development Debugging

#### Component-Level Debugging

```python
# Debug individual components
import logging
logging.basicConfig(level=logging.DEBUG)

from ray_mcp.managers.unified_manager import RayUnifiedManager

# Enable debug logging for specific components
logging.getLogger('ray_mcp.managers').setLevel(logging.DEBUG)
logging.getLogger('ray_mcp.kubernetes').setLevel(logging.DEBUG)

manager = RayUnifiedManager()
result = await manager.init_ray_cluster(cluster_type="kubernetes")
```

#### MCP Protocol Debugging

```bash
# Enable MCP debug logging
export MCP_LOG_LEVEL=DEBUG
export RAY_MCP_LOG_LEVEL=DEBUG
uv run ray-mcp
```

## Contributing Guidelines

### Pull Request Process

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/my-feature
   git checkout -b bugfix/fix-issue
   ```

2. **Development Workflow**
   ```bash
   # Make changes
   # Add comprehensive tests
   make test-fast  # Quick validation
   make lint       # Code quality
   make test       # Full test suite
   make format
   ```

3. **Documentation Updates**
   - Update relevant documentation in `docs/`
   - Add examples for new features
   - Update tool schemas and descriptions

4. **Submit Pull Request**
   - Clear description of changes
   - Link to related issues
   - Include test coverage information
