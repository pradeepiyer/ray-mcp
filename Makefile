# Ray MCP Server - Prompt-Driven Architecture (UV Native)
# 
# Modern Testing Strategy:
# - test-fast:  Unit tests with 100% mocking (fast development feedback)
# - test:       Complete test suite (unit tests)

.PHONY: test test-fast test-integration-local test-integration-gke test-integration-both test-integration-setup install dev-install sync clean uv-lock uv-check lint-tool-functions wc clean-coverage clean-all test-cov

# ================================================================================
# TESTING TARGETS
# ================================================================================

# Default test - unit test suite
test:
	@echo "🔍 Running unit test suite..."
	@python tests/integration/test_runner.py unit

# Fast test suite (unit tests with 100% mocking) - for development
test-fast:
	@echo "🏃‍♂️ Running fast unit tests with 100% mocking..."
	@python tests/integration/test_runner.py unit


# Integration tests for local mode
test-integration-local:
	@echo "🔧 Running local integration tests..."
	@python tests/integration/test_local_mode.py

# Integration tests for GKE mode
test-integration-gke:
	@echo "☁️ Running GKE integration tests..."
	@python tests/integration/test_gke_mode.py

# Integration tests for both modes
test-integration-both:
	@echo "🚀 Running both local and GKE integration tests..."
	@./tests/integration/run_tests.sh both

# Setup integration testing environment
test-integration-setup:
	@echo "🔧 Setting up integration testing environment..."
	@python tests/integration/setup_testing_environment.py


# ================================================================================
# LINTING AND FORMATTING TARGETS
# ================================================================================

# Linting - matches CI workflow
lint:
	@echo "🔍 Running linting checks..."
	@uv run black --check ray_mcp/ examples/ tests/
	@uv run isort --check-only ray_mcp/ examples/ tests/
	@uv run pyright ray_mcp/ examples/ tests/
	@echo "✅ All linting checks passed!"

# Linting core files only (excluding tests)
lint-core:
	@echo "🔍 Running linting checks on core files..."
	@uv run black --check ray_mcp/ examples/
	@uv run isort --check-only ray_mcp/ examples/
	@uv run pyright ray_mcp/ examples/
	@echo "✅ Core linting checks passed!"

# Tool function specific linting for 3-tool architecture
lint-tool-functions:
	@echo "🔧 Running tool function linting for prompt-driven tools..."
	@uv run python -c "\
from ray_mcp.tools import get_ray_tools; \
tools = get_ray_tools(); \
print('🔍 Validating 3-tool architecture:'); \
print(f'   - Tool count: {len(tools)} (expected: 3)'); \
tool_names = [tool.name for tool in tools]; \
expected = ['ray_cluster', 'ray_job', 'cloud']; \
print(f'   - Tool names: {tool_names}'); \
print(f'   - Expected: {expected}'); \
print(f'   - Valid: {\"✅\" if set(tool_names) == set(expected) else \"❌\"}'); \
[print(f'   - {tool.name}: prompt parameter {\"✅\" if \"prompt\" in tool.inputSchema.get(\"required\", []) else \"❌\"}') for tool in tools]; \
print('✅ Tool function validation complete!'); \
"

# Enhanced linting - includes tool function checks
lint-enhanced: lint lint-tool-functions
	@echo "✅ All enhanced linting checks passed!"

# Format code - apply formatting fixes
format:
	@echo "🎨 Formatting code..."
	@uv run black ray_mcp/ examples/ tests/
	@uv run isort ray_mcp/ examples/ tests/
	@uv run pyright ray_mcp/ examples/ tests/
	@echo "✅ Code formatting complete!"

# ================================================================================
# INSTALLATION AND DEPENDENCY MANAGEMENT TARGETS
# ================================================================================

# UV Installation commands
install:
	@echo "📦 Installing package with uv..."
	@uv pip install -e .

dev-install: sync
	@echo "✅ Development installation complete!"

# UV sync - install all dependencies including dev dependencies
sync:
	@echo "🔄 Syncing dependencies with uv..."
	@uv sync

# Create/update lock file
uv-lock:
	@echo "🔒 Updating uv.lock file..."
	@uv lock

# Check for dependency updates
uv-check:
	@echo "🔍 Checking for dependency updates..."
	@uv tree
	@uv pip check

# Update dependencies to latest compatible versions
update-deps:
	@echo "🔄 Running dependency update helper..."
	@python scripts/update_dependencies.py

# Create virtual environment with uv
venv:
	@echo "🐍 Creating virtual environment with uv..."
	@uv venv

# Activate virtual environment (source manually)
activate:
	@echo "To activate virtual environment, run:"
	@echo "source .venv/bin/activate"

# ================================================================================
# UTILITY TARGETS
# ================================================================================

# Cleanup
clean:
	@echo "🧹 Cleaning up..."
	@rm -rf htmlcov/
	@rm -rf .coverage_data/
	@rm -rf .pytest_cache/
	@rm -rf __pycache__/
	@rm -rf .uv/
	@rm -rf *.egg-info/
	@rm -f .coverage .coverage.*
	@find . -name "*.pyc" -delete
	@find . -name "__pycache__" -type d -exec rm -rf {} +

# Count lines of code with breakdown per directory
wc:
	@echo "🔍 Counting lines of code with directory breakdown..."
	@echo ""
	@echo "📊 Total lines by file type:"
	@echo "================================"
	@echo "Python files:"
	@find . -name "*.py" -not -path "./.venv/*" -not -path "./.git/*" -not -path "./.mypy_cache/*" -not -path "./.pytest_cache/*" -not -path "./htmlcov/*" -not -path "./.coverage_data/*" | xargs wc -l | tail -1
	@echo ""
	@echo "Shell scripts:"
	@find . -name "*.sh" -not -path "./.venv/*" -not -path "./.git/*" | xargs wc -l | tail -1
	@echo ""
	@echo "Markdown files:"
	@find . -name "*.md" -not -path "./.venv/*" -not -path "./.git/*" | xargs wc -l | tail -1
	@echo ""
	@echo "Configuration files:"
	@find . -name "*.toml" -o -name "*.ini" -o -name "*.cfg" -o -name "*.yml" -o -name "*.yaml" -o -name "*.json" | grep -v ".venv" | grep -v ".git" | xargs wc -l | tail -1
	@echo ""
	@echo "📁 Breakdown by directory:"
	@echo "================================"
	@echo "ray_mcp/ (main package):"
	@find ./ray_mcp -name "*.py" | xargs wc -l | tail -1
	@echo ""
	@echo "tests/ (test files):"
	@find ./tests -name "*.py" | xargs wc -l | tail -1
	@echo ""
	@echo "examples/ (example files):"
	@find ./examples -name "*.py" | xargs wc -l | tail -1
	@echo ""
	@echo "scripts/ (utility scripts):"
	@find ./scripts -name "*.py" -o -name "*.sh" | xargs wc -l | tail -1
	@echo ""
	@echo "docs/ (documentation):"
	@find ./docs -name "*.md" -o -name "*.py" | xargs wc -l | tail -1
	@echo ""
	@echo "📈 Summary:"
	@echo "================================"
	@echo "Total Python lines:"
	@find . -name "*.py" -not -path "./.venv/*" -not -path "./.git/*" -not -path "./.mypy_cache/*" -not -path "./.pytest_cache/*" -not -path "./htmlcov/*" -not -path "./.coverage_data/*" | xargs wc -l | tail -1
	@echo ""
	@echo "Total code lines (Python + Shell + Config):"
	@find . -name "*.py" -o -name "*.sh" -o -name "*.toml" -o -name "*.ini" -o -name "*.cfg" -o -name "*.yml" -o -name "*.yaml" -o -name "*.json" | grep -v ".venv" | grep -v ".git" | grep -v ".mypy_cache" | grep -v ".pytest_cache" | grep -v "htmlcov" | grep -v ".coverage_data" | xargs wc -l | tail -1

# Coverage cleanup
clean-coverage:
	@echo "🧹 Cleaning coverage files..."
	find . -maxdepth 1 -name ".coverage*" -exec rm -rf {} \; 2>/dev/null || true
	mkdir -p .coverage_data
	rm -rf htmlcov/
	@echo "✅ Coverage files cleaned"

clean-all: clean-coverage
	@echo "🧹 Cleaning all generated files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	@echo "✅ All generated files cleaned"

# Test with coverage (using test runner)
test-cov: clean-coverage
	@echo "🧪 Running tests with coverage..."
	@python tests/integration/test_runner.py unit --coverage
	@echo "📊 Coverage report generated in htmlcov/"

# Help
help:
	@echo "Ray MCP Server - Prompt-Driven Architecture - Available Commands:"
	@echo ""
	@echo "📦 Installation:"
	@echo "  install          Install dependencies"
	@echo "  dev-install      Install development dependencies"
	@echo "  sync             Sync dependencies"
	@echo "  uv-lock          Update lock file"
	@echo "  uv-check         Check dependency consistency"
	@echo "  update-deps      Update dependencies to latest compatible versions"
	@echo ""
	@echo "🧪 Testing (New Test Runner):"
	@echo "  test             Run unit test suite"
	@echo "  test-fast        Run unit tests with 100% mocking (fast development)"
	@echo "  test-cov         Run unit tests with coverage reporting"
	@echo ""
	@echo "🔧 Integration Testing:"
	@echo "  test-integration-local    Run local integration tests"
	@echo "  test-integration-gke      Run GKE integration tests"
	@echo "  test-integration-both     Run both local and GKE integration tests"
	@echo "  test-integration-setup    Setup integration testing environment"
	@echo ""
	@echo "🔧 Development:"
	@echo "  lint             Run linting checks"
	@echo "  lint-enhanced    Run enhanced linting with 3-tool validation"
	@echo "  format           Format code"
	@echo "  lint-tool-functions  Validate prompt-driven tool architecture"
	@echo "  wc               Count lines of code with directory breakdown"
	@echo "  clean            Clean build artifacts"
	@echo "  clean-coverage   Clean coverage files"
	@echo "  clean-all        Clean all generated files"
	@echo ""
	@echo "🎯 Architecture:"
	@echo "  3 Tools: ray_cluster, ray_job, cloud"
	@echo "  Interface: Natural language prompts"
	@echo "  Tests: 96 unit tests" 