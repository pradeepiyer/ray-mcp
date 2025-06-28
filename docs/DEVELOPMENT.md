# Ray MCP Server: Development Guide

This guide covers setup, testing, and best practices for developing Ray MCP.

## Setup
- Python 3.10+
- Install [uv](https://github.com/astral-sh/uv)

```bash
# Clone and install
git clone https://github.com/pradeepiyer/ray-mcp
cd ray-mcp
uv sync --all-extras --dev
```

## Project Structure
```
mcp/
├── ray_mcp/      # Core server code
├── tests/        # Test suite
├── examples/     # Example scripts (simple_job.py)
├── docs/         # Documentation
└── scripts/      # Utilities
```

## Development Workflow

### 1. Feature Development
```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Make changes and test
uv run pytest tests/ -k "not e2e"  # Fast feedback
uv run pytest tests/               # Full test suite

# Commit with clear message
git commit -m "feat: add new feature description"
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

### 3. Testing Strategy
- **Unit tests**: Fast execution for quick feedback
- **E2E tests**: Complete workflow testing
- **CI mode**: Head node only, minimal resources
- **Local mode**: Full cluster, comprehensive testing

```bash
# Run all tests
uv run pytest tests/

# Unit tests only (fast)
uv run pytest tests/ -k "not e2e"

# E2E tests only
uv run pytest tests/test_e2e_integration.py

# Coverage report
uv run pytest tests/ --cov=ray_mcp --cov-report=html
```

### 4. Pull Request Process
1. **Fork and clone** the repository
2. **Create feature branch** with descriptive name
3. **Make changes** following coding standards
4. **Run all tests** and quality checks
5. **Update documentation** if needed
6. **Submit PR** with clear description

## Code Quality Standards

### Code Style
- **Black**: Automatic code formatting
- **isort**: Import sorting and organization
- **Type hints**: Use throughout the codebase
- **Docstrings**: Document all public functions

### Testing Requirements
- **New features**: Must include unit tests
- **Bug fixes**: Must include regression tests
- **Coverage**: Maintain high test coverage
- **E2E tests**: Test complete workflows

### Code Review Checklist
- [ ] All tests pass (unit + e2e)
- [ ] Code is formatted and linted
- [ ] Type checking passes
- [ ] Documentation is updated
- [ ] No breaking changes (or documented)
- [ ] Performance impact considered

## Best Practices

### Development
- Keep tests fast and isolated
- Use minimal resources for CI
- Always clean up Ray clusters after tests
- Update docs for any new features
- Follow established patterns and conventions

### Testing
- Write meaningful test names
- Use appropriate assertions
- Mock external dependencies
- Test both success and failure cases
- Keep test data minimal and focused

### Documentation
- Update README.md for user-facing changes
- Keep examples current and working
- Document new tools and features
- Use clear, concise language

## Debugging

### Common Issues
```bash
# Clean up Ray processes
./scripts/ray_cleanup.sh

# Check Ray status
ray status

# Run specific test with debug output
uv run pytest tests/test_ray_manager.py::TestRayManager::test_specific -v -s
```

### Environment Issues
```bash
# Verify installation
python -c "import ray; print(ray.__version__)"

# Check environment variables
echo $CI $GITHUB_ACTIONS

# Reinstall dependencies
uv sync --all-extras --dev
```

---

For troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).