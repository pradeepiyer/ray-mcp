# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Project Overview

Ray MCP Server (v0.4.0) is a Model Context Protocol server that enables LLM agents to manage Ray distributed computing through natural language prompts. The project features a **3-tool prompt-driven architecture** where users interact using natural language rather than complex parameters.

**Core Philosophy**: Simple, prompt-driven interface with just 3 tools: `ray_cluster`, `ray_job`, and `cloud`.

## Architecture Overview

### Prompt-Driven Design
- **3 Simple Tools**: Each tool takes only a natural language `prompt` parameter
- **Unified Interface**: Natural language requests are automatically parsed and routed
- **Environment Detection**: Intelligent routing between local Ray and Kubernetes environments

### Project Structure
```
ray_mcp/
├── main.py                     # MCP server entry point
├── tools.py                    # 3-tool definitions (ray_cluster, ray_job, cloud)
├── handlers.py                 # Tool handlers for MCP protocol
├── parsers.py                  # Natural language parsing logic
├── foundation/                 # Base classes, interfaces, logging utilities
├── managers/                   # Business logic managers
├── kubernetes/                 # KubeRay integration and CRD management
└── cloud/                      # Cloud provider integration (GKE)
```

### Core Components
- **RayUnifiedManager**: Central orchestrator composing all specialized managers
- **RayHandlers**: MCP tool call handlers
- **ActionParser**: Natural language parsing engine
- **Specialized Managers**: `ClusterManager`, `JobManager`, `LogManager`

## Development Commands

### Testing Strategy (Modern 2-Tier)
```bash
make test-fast     # Unit tests with 100% mocking (fast development feedback)
make test-e2e      # End-to-end tests without mocking (integration validation)
make test          # Complete test suite (unit + e2e)
```

### Alternative Test Runner
```bash
python test_runner.py unit     # Fast feedback for development
python test_runner.py e2e      # Integration validation
python test_runner.py all      # Complete validation
```

### Code Quality & Linting
```bash
make lint                      # Run black, isort, pyright
make lint-enhanced             # Enhanced linting with 3-tool validation
make lint-tool-functions       # Validate prompt-driven tool architecture
make format                    # Apply code formatting
```

### Development Setup
```bash
make sync                      # Sync dependencies with uv
make dev-install               # Complete development installation
uv sync --extra all            # Install with all optional dependencies
uv sync --extra gke            # Install with GKE support only
```

### Utility Commands
```bash
make clean                     # Clean build artifacts
make clean-all                 # Clean all generated files
make wc                        # Count lines of code with directory breakdown
uv run ray-mcp                 # Run the MCP server locally
```

## Dependencies & Features

### Core Dependencies
- `ray[default]>=2.47.0` - Distributed computing framework
- `mcp>=1.0.0` - Model Context Protocol
- `kubernetes>=26.1.0` - Kubernetes API client
- `pydantic>=2.0.0` - Data validation and parsing
- Python 3.10+ required

### Optional Features
- `gke/gcp/cloud`: Google Cloud integration
- `all`: All optional dependencies

### Development Tools
- `uv` - Modern Python package manager
- `pytest` - Testing framework with asyncio support
- `black`, `isort`, `pyright` - Code quality tools

## Environment Support

### Dual Environment Architecture
- **Local Ray**: Traditional Ray clusters on local machines
- **KubeRay**: Kubernetes-native Ray deployments with CRD management
- **Automatic Detection**: Tools intelligently route based on prompt keywords

### Cloud Provider Integration
- **Google Cloud (GKE)**: Full integration with service account authentication
- **Provider Detection**: Automatic cloud environment detection
- **Authentication**: Service account and kubeconfig support

## Testing Approach

### Test Organization
```
tests/
├── unit/                      # Fast tests with 100% mocking
│   ├── test_mcp_tools.py     # MCP tool functionality
│   ├── test_parsers_and_formatters.py  # Natural language parsing
│   ├── test_prompt_managers.py  # Manager business logic
│   └── test_tool_registry.py    # Tool registration and routing
├── e2e/                       # Integration tests without mocking
│   └── test_critical_workflows.py  # End-to-end user workflows
└── helpers/                   # Test utilities and fixtures
```

### Test Markers
- `@pytest.mark.unit` - Fast mocked tests
- `@pytest.mark.e2e` - Integration tests
- `@pytest.mark.gke` - GKE-specific tests

## Configuration & Environment

### Environment Variables
```bash
RAY_MCP_ENHANCED_OUTPUT=true      # Enhanced LLM-friendly output
RAY_MCP_LOG_LEVEL=DEBUG           # Debug logging
GOOGLE_APPLICATION_CREDENTIALS=   # GKE authentication
RAY_DISABLE_USAGE_STATS=1         # Disable Ray usage statistics
```

### Configuration Files
- `pyproject.toml` - Project metadata, dependencies, tool configuration
- `pytest.ini` - Test configuration with async support
- `Makefile` - Development automation
- `uv.lock` - Dependency lock file

## Development Patterns

### Tool Development (3-Tool Architecture)
1. Tools are defined in `ray_mcp/tools.py` with single `prompt` parameter
2. Handlers in `ray_mcp/handlers.py` process MCP calls
3. Parsers in `ray_mcp/parsers.py` handle natural language interpretation
4. Managers execute the actual operations

### Error Handling
All operations use consistent error responses via `ResponseFormatter`:
```python
from ray_mcp.foundation.logging_utils import ResponseFormatter
return ResponseFormatter.format_error_response("operation_name", exception)
```

### Testing Standards
- **Unit Tests**: 100% mocked for fast execution (< 1s each)
- **E2E Tests**: No mocking, real system integration
- **Coverage**: 96% test coverage with HTML reports
- **Quality**: Black formatting, isort imports, pyright type checking

## Important Implementation Details

### Natural Language Processing
- Prompt parsing for cluster operations, job management, and cloud tasks
- Intelligent environment detection (local vs Kubernetes)
- Context-aware command interpretation

### Kubernetes Integration
- **KubeRay Integration**: CRD management for RayCluster and RayJob
- **Namespace Awareness**: Operations with proper resource cleanup
- **Operator Discovery**: Automatic KubeRay operator validation

### Authentication & Security
- Service account-based GKE authentication
- Kubernetes config file support
- Credential validation and environment checks

### State Management
- Thread-safe state management
- Centralized cluster and job tracking
- Supports both local and distributed scenarios

## Common Development Tasks

### Validating 3-Tool Architecture
```bash
make lint-tool-functions
```
This validates that exactly 3 tools exist with proper prompt parameters.

### Adding New Cloud Provider Support
1. Create provider manager in `ray_mcp/cloud/`
2. Update cloud provider enum in `ray_mcp/foundation/interfaces.py`
3. Add detection logic in cloud provider manager
4. Update parsing logic in `ray_mcp/parsers.py`
5. Add comprehensive tests

### Extending Natural Language Capabilities
1. Update parsers in `ray_mcp/parsers.py`
2. Add new action patterns and keywords
3. Update manager methods as needed
4. Add comprehensive test cases

### Debugging Common Issues
- **GKE Connection**: Check `GOOGLE_APPLICATION_CREDENTIALS` and project permissions
- **KubeRay Operator**: Verify with `kubectl get pods -n kuberay-system`
- **Test Failures**: Use `make test-fast` for quick system validation
- **Tool Validation**: Use `make lint-tool-functions` to verify architecture

## Entry Points

- **MCP Server**: `uv run ray-mcp` (maps to `ray_mcp.main:run_server`)
- **Test Runner**: `python test_runner.py [unit|e2e|all]`
- **Direct Module**: `python -m ray_mcp.main`

## Code Standards

### Quality Requirements
- Python 3.10+ with comprehensive type hints
- Async/await patterns throughout
- Black formatting (88 character lines)
- Pyright type checking in basic mode
- 96% test coverage with HTML reports

### Architecture Principles
- **Prompt-First**: All interactions through natural language
- **Unified Interface**: Single entry point for local and cloud operations
- **Composable Managers**: Specialized managers composed by unified manager
- **Comprehensive Testing**: Fast unit tests + thorough integration tests

The codebase represents a modern, clean implementation focused on simplicity and natural language interaction while supporting both local and cloud-native Ray deployments.