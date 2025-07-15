# Development Guide

Development guide for Ray MCP Server's prompt-driven architecture.

## Quick Setup

```bash
# Install development dependencies
make dev-install

# Run tests
make test-fast      # Unit tests with mocking
make test-e2e       # End-to-end integration tests
make test           # Complete test suite

# Code quality
make lint           # Linting checks
make format         # Code formatting
```

## Architecture

### Prompt-Driven Design

Ray MCP Server uses a prompt-driven architecture with 3 simple tools:

```
┌─────────────────┐    Natural Language    ┌─────────────────┐
│   LLM Agent     │──────────────────────►│   Ray MCP       │
│                 │     Single Prompt      │   Server        │
└─────────────────┘                        └─────────┬───────┘
                                                     │
                   ┌─────────────────────────────────┼─────────────────────────────┐
                   │                                 │                             │
                   ▼                                 ▼                             ▼
            ┌─────────────┐                  ┌─────────────┐              ┌─────────────┐
            │ Local Ray   │                  │  KubeRay    │              │   Cloud     │
            │ Clusters    │                  │ Clusters    │              │ Providers   │
            └─────────────┘                  └─────────────┘              └─────────────┘
```

### Core Components

**ActionParser** (`ray_mcp/foundation/action_parser.py`)
- Converts natural language prompts to structured actions
- Handles intent recognition and parameter extraction

**RayUnifiedManager** (`ray_mcp/managers/unified_manager.py`)
- Central orchestration layer
- Routes requests between local Ray, KubeRay, and cloud providers
- Provides unified interface for all Ray operations

**RayHandlers** (`ray_mcp/handlers.py`)
- Processes MCP tool calls
- Validates parameters and routes to appropriate managers
- Handles the 3-tool interface: `ray_cluster`, `ray_job`, `cloud`

## Development Environment

### Prerequisites

- Python 3.10+
- uv package manager
- kubectl (for KubeRay operator setup and debugging only - the MCP server uses native Kubernetes APIs)
- Docker (optional, for local Kubernetes)

### Installation

```bash
# Clone repository
git clone https://github.com/pradeepiyer/ray-mcp.git
cd ray-mcp

# Install all dependencies
uv sync --extra all

# Verify installation
uv run ray-mcp --version
```

### Cloud Provider Setup

#### Google Cloud (GKE)

```bash
# Install GKE dependencies
uv sync --extra gke

# Set up authentication
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
export GOOGLE_CLOUD_PROJECT="your-project-id"
```

#### Local Kubernetes

```bash
# Start minikube
minikube start --cpus=4 --memory=8192

# Install KubeRay operator
kubectl apply -f https://raw.githubusercontent.com/ray-project/kuberay/release-0.8/deploy/kuberay-operator.yaml

# Verify installation
kubectl get pods -n kuberay-system
```

## Testing Strategy

### Two-Tier Testing

**Unit Tests** (`make test-fast`)
- 100% mocked for fast execution
- Tests individual components in isolation
- Focused on logic and edge cases


**End-to-End Tests** (`make test-e2e`)
- No mocking, real system integration
- Complete workflows from prompt to result
- Validates actual Ray/Kubernetes operations

### Test Structure

```
tests/
├── conftest.py                 # Test configuration
├── test_runner.py              # Unified test runner
├── unit/                       # Unit tests (mocked)
│   ├── test_prompt_managers.py
│   └── test_tool_registry.py
└── e2e/                        # End-to-end tests
    └── test_mcp_server.py
```

### Running Tests

```bash
# Development workflow
make test-fast      # Quick feedback during development

# System validation

# Complete validation
make test-e2e       # Integration testing
make test           # Full test suite
```

## Adding New Features

### Adding a New Prompt Pattern

```python
# ray_mcp/foundation/action_parser.py
class ActionParser:
    def _parse_cluster_action(self, prompt: str) -> Dict[str, Any]:
        # Add new pattern recognition
        if "new operation" in prompt.lower():
            return {
                "action": "new_operation",
                "parameters": self._extract_parameters(prompt)
            }
```

### Extending Cloud Provider Support

```python
# ray_mcp/cloud/providers/new_provider_manager.py
from ...foundation.resource_manager import ResourceManager

class NewProviderManager(ResourceManager):
    """Manager for new cloud provider operations."""
    
    async def authenticate(self, **kwargs) -> Dict[str, Any]:
        """Authenticate with new provider."""
        # Implementation
        pass
    
    async def create_cluster(self, cluster_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Create cluster on new provider."""
        # Implementation
        pass
```

## Code Quality

### Linting and Formatting

```bash
# Format code
make format

# Run linting
make lint

# Enhanced linting with tool validation
make lint-enhanced
```

### Tool Function Validation

The system validates the 3-tool architecture:

```bash
# Validate tool structure
make lint-tool-functions
```

This ensures:
- Exactly 3 tools: `ray_cluster`, `ray_job`, `cloud`
- Each tool has required `prompt` parameter
- Tool schemas are valid

## Debugging

### Development Server

```bash
# Basic server
uv run ray-mcp

# With enhanced output
RAY_MCP_ENHANCED_OUTPUT=true uv run ray-mcp

# With debug logging
RAY_MCP_LOG_LEVEL=DEBUG uv run ray-mcp
```

### Component Testing

```python
# Test individual components
from ray_mcp.managers.unified_manager import RayUnifiedManager

manager = RayUnifiedManager()

# Test cluster operations
result = await manager.handle_cluster_request("create a local cluster")
print(result)

# Test job operations
result = await manager.handle_job_request("submit job with script train.py")
print(result)
```

## Environment Variables

```bash
# Enhanced LLM-friendly output
export RAY_MCP_ENHANCED_OUTPUT=true

# Debug logging
export RAY_MCP_LOG_LEVEL=DEBUG

# Disable Ray usage statistics
export RAY_DISABLE_USAGE_STATS=1

# Cloud authentication
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
export GOOGLE_CLOUD_PROJECT="your-project-id"
```

## Contributing

### Development Workflow

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/prompt-enhancement
   ```

2. **Development Cycle**
   ```bash
   # Make changes
   make test-fast      # Quick validation
   make lint           # Code quality
   make format         # Apply formatting
   ```

3. **Final Validation**
   ```bash
   make test           # Full test suite
   make lint-enhanced  # Complete linting
   ```

4. **Submit Pull Request**
   - Clear description of changes
   - Include test coverage
   - Update relevant documentation

### Code Standards

- Follow existing prompt-driven patterns
- Add comprehensive tests for new features
- Update documentation for user-facing changes
- Maintain backward compatibility with existing prompts