# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Ray MCP Server is a Model Context Protocol (MCP) server for Ray distributed computing. It enables LLM agents to programmatically manage Ray clusters, submit jobs, and monitor distributed workloads across local and Kubernetes environments.

## Development Commands

### Testing
- `make test-fast` - Run unit tests only (fast development feedback)
- `make test-smoke` - Run smoke tests for critical functionality validation
- `make test` - Run complete test suite including E2E (default, includes coverage)
- `make test-e2e` - Run comprehensive end-to-end server tests
- `uv run pytest tests/test_kubernetes.py` - Run Kubernetes/KubeRay specific tests
- `uv run pytest -m gke` - Run GKE integration tests (requires credentials)

### Code Quality & Linting
- `make lint` - Run all linting checks (black, isort, pyright)
- `make lint-enhanced` - Enhanced linting including tool function checks
- `make format` - Apply code formatting (black, isort, pyright)
- `make lint-tool-functions` - Lint tool function signatures specifically

### Development Setup
- `make sync` or `uv sync` - Install all dependencies including dev dependencies
- `make dev-install` - Complete development installation
- `uv sync --extra all` - Install with all optional dependencies (GKE, etc.)
- `uv sync --extra gke` - Install with GKE support only

### Utility Commands
- `make clean` - Clean build artifacts and cache files
- `make clean-all` - Clean all generated files including coverage
- `make wc` - Count lines of code with directory breakdown
- `uv run ray-mcp` - Run the MCP server locally

### Environment Variables for Development
- `RAY_MCP_ENHANCED_OUTPUT=true` - Enable enhanced LLM-friendly output
- `RAY_MCP_LOG_LEVEL=DEBUG` - Set debug logging
- `GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json` - GKE authentication
- `RAY_DISABLE_USAGE_STATS=1` - Disable Ray usage statistics

## Architecture Overview

### Modular Component Architecture
The project uses a layered architecture with focused, composable components:

**Core Layers:**
1. **Foundation Layer** (`ray_mcp/foundation/`) - Base classes, interfaces, logging, import utilities
2. **Manager Layer** (`ray_mcp/managers/`) - Business logic managers for clusters, jobs, logs, ports, state
3. **Kubernetes Layer** (`ray_mcp/kubernetes/`) - KubeRay integration, CRD management, K8s operations
4. **Cloud Layer** (`ray_mcp/cloud/`) - Cloud provider integration (GKE, etc.)
5. **Tools Layer** (`ray_mcp/tools/`) - MCP tool schemas and validation

### Key Components

**Unified Manager (`ray_mcp/managers/unified_manager.py`)**
- Central orchestration layer that composes all specialized managers
- Provides unified interface for local and Kubernetes Ray operations
- Handles automatic detection between local Ray and KubeRay workflows

**Tool Registry (`ray_mcp/tool_registry.py`)**
- Centralized registration and routing for all MCP tools
- Maps tool names to handlers and manages parameter validation
- Handles automatic job/cluster type detection for unified tools

**Main Entry Point (`ray_mcp/main.py`)**
- MCP server initialization and protocol handling
- Global manager instances: `ray_manager = RayUnifiedManager()` and `tool_registry = ToolRegistry(ray_manager)`

### Dual Environment Support
The system supports both local Ray clusters and Kubernetes-based KubeRay deployments:
- **Local Mode**: Traditional Ray clusters on local machines
- **Kubernetes Mode**: KubeRay operators for cloud-native deployments
- **Automatic Detection**: Tools automatically detect and route to appropriate backend

### Cloud Provider Integration
- **Google Cloud (GKE)**: Full integration with service account authentication
- **Local Kubernetes**: Support for minikube, Docker Desktop, etc.
- **Provider Detection**: Automatic cloud environment detection

## Development Patterns

### Testing Strategy
- **Unit Tests**: Fast tests with full mocking (`test_managers.py`, `test_core_functionality.py`)
- **Integration Tests**: Component interaction tests (`test_kubernetes.py`)
- **E2E Tests**: Complete workflows (`test_mcp_server.py`)
- **Smoke Tests**: Quick system validation for CI/CD

### Error Handling
All operations use `ResponseFormatter` for consistent error responses:
```python
from ray_mcp.foundation.logging_utils import ResponseFormatter
return ResponseFormatter.format_error_response("operation_name", exception)
```

### Tool Development
1. Define schema in appropriate `ray_mcp/tools/*_tools.py` file
2. Register in `ToolRegistry._register_all_tools()`
3. Implement handler method in `ToolRegistry`
4. Add corresponding manager method in `RayUnifiedManager`
5. Add comprehensive tests

### State Management
- Thread-safe state management via `StateManager`
- Centralized cluster and job state tracking
- Supports both local and distributed state scenarios

## Important Implementation Details

### Port Management
- Automatic port allocation with conflict resolution
- Cleanup of stale port locks via `PortManager`
- Supports concurrent cluster operations

### Log Processing
- Unified log retrieval supporting both local Ray and KubeRay
- Pagination and size limits for large log files
- Error analysis and filtering capabilities

### Authentication Flows
- Service account-based GKE authentication
- Kubernetes config file support for local clusters
- Credential validation and environment checks

### Kubernetes Integration
- Custom Resource Definition (CRD) management for RayCluster and RayJob
- Automatic KubeRay operator discovery and validation
- Namespace-aware operations with proper resource cleanup

## Common Development Tasks

### Adding Support for a New Cloud Provider
1. Create provider manager in `ray_mcp/cloud/providers/`
2. Update cloud provider enum in `ray_mcp/foundation/interfaces.py`
3. Add detection logic in `CloudProviderDetector`
4. Update tool schemas in `ray_mcp/tools/cloud_tools.py`
5. Add comprehensive tests for the new provider

### Extending KubeRay Functionality
1. Extend CRD specifications in `ray_mcp/kubernetes/crds/`
2. Add manager methods in `ray_mcp/kubernetes/managers/`
3. Update unified manager delegation in `RayUnifiedManager`
4. Add tool schemas and handlers as needed

### Debugging Common Issues
- **GKE Connection Issues**: Check `GOOGLE_APPLICATION_CREDENTIALS` and project permissions
- **KubeRay Operator**: Verify operator installation with `kubectl get pods -n kuberay-system`
- **Port Conflicts**: Clean stale locks with port manager cleanup methods
- **Test Failures**: Use `make test-smoke` for quick system validation

## Configuration Files

- `pyproject.toml` - Project metadata, dependencies, tool configuration (black, isort, pyright, coverage)
- `pytest.ini` - Test configuration, markers, async settings
- `Makefile` - Development automation and command shortcuts
- `uv.lock` - Dependency lock file (managed by uv)

The codebase follows Python 3.10+ standards with comprehensive type hints and async/await patterns throughout.