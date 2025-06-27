# Ray MCP Server - Test Automation (UV Native)

.PHONY: test test-fast test-smoke test-e2e test-full test-smart install dev-install sync clean uv-lock uv-check lint-tool-functions test-tool-functions count-lines test-e2e-clean test-e2e-clean-x test-e2e-file test-e2e-clean-verbose

# Default development test (fast)
test: test-fast

# Fast test suite (excludes e2e tests) - for development
test-fast:
	@echo "🏃‍♂️ Running fast test suite..."
	@./scripts/test-fast.sh

# Smoke tests - minimal verification
test-smoke:
	@echo "💨 Running smoke tests..."
	@uv run pytest tests/ -m "smoke" --tb=short -v --maxfail=1

# End-to-end tests only - for major changes
test-e2e:
	@echo "🧪 Running e2e tests with automatic cleanup..."
	@echo "🧹 Running initial cleanup..."
	@./scripts/ray_cleanup.sh
	@echo "🚀 Starting e2e tests with automatic cleanup..."
	@python -m pytest tests/ -m e2e -v --tb=short
	@echo "🧹 Running final cleanup..."
	@./scripts/ray_cleanup.sh
	@echo "✅ E2E tests completed with cleanup"

# Full test suite - all tests including e2e
test-full:
	@echo "🔍 Running complete test suite..."
	@./scripts/test-full.sh

# Smart test runner - detects changes and runs appropriate tests
test-smart:
	@scripts/smart-test.sh

# Tool function specific tests
test-tool-functions:
	@echo "🔧 Running tool function tests..."
	@uv run pytest tests/test_tool_functions.py -v
	@uv run pytest tests/test_full_parameter_flow.py -v

# Linting - matches CI workflow
lint:
	@echo "🔍 Running linting checks..."
	@uv run black --check ray_mcp/ examples/ tests/
	@uv run isort --check-only ray_mcp/ examples/ tests/
	@uv run pyright ray_mcp/ examples/ tests/
	@echo "✅ All linting checks passed!"

# Tool function specific linting
lint-tool-functions:
	@echo "🔧 Running tool function linting..."
	@python scripts/lint_tool_functions.py

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

# Create virtual environment with uv
venv:
	@echo "🐍 Creating virtual environment with uv..."
	@uv venv

# Activate virtual environment (source manually)
activate:
	@echo "To activate virtual environment, run:"
	@echo "source .venv/bin/activate"

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

# Count lines of code (excluding common non-code files)
count-lines:
	@echo "📏 Counting lines of code in the repo..."
	@find . -type f \( -name '*.py' -o -name '*.sh' \) \
	  -not -path './.venv/*' -not -path './.git/*' -not -path './htmlcov/*' \
	  -not -path './.mypy_cache/*' -not -path './.pytest_cache/*' \
	  -not -path './*.egg-info/*' -not -path './__pycache__/*' \
	  -not -path './uv.lock' -not -path './.coverage*' \
	  -not -path './.gitignore' \
	  -exec cat {} + | wc -l

# Run e2e tests with automatic cleanup between tests (using pytest plugin)
test-e2e-clean:
	@echo "🧪 Running e2e tests with automatic cleanup..."
	@echo "🧹 Running initial cleanup..."
	@./scripts/ray_cleanup.sh
	@echo "🚀 Starting e2e tests with automatic cleanup..."
	@python -m pytest tests/ -m e2e -v --tb=short
	@echo "🧹 Running final cleanup..."
	@./scripts/ray_cleanup.sh
	@echo "✅ E2E tests completed with cleanup"

# Run e2e tests with detailed output and cleanup
test-e2e-verbose:
	@echo "🧪 Running e2e tests with detailed output and cleanup..."
	@echo "🧹 Running initial cleanup..."
	@./scripts/ray_cleanup.sh
	@echo "🚀 Starting e2e tests with automatic cleanup..."
	@python -m pytest tests/ -m e2e -v -s --tb=long
	@echo "🧹 Running final cleanup..."
	@./scripts/ray_cleanup.sh
	@echo "✅ E2E tests completed with cleanup"

# Run specific e2e test file with cleanup
test-e2e-file:
	@echo "🧪 Running specific e2e test file with automatic cleanup..."
	@echo "🧹 Running initial cleanup..."
	@./scripts/ray_cleanup.sh
	@echo "🚀 Starting e2e tests from test_e2e_integration.py..."
	@python -m pytest tests/test_e2e_integration.py -v --tb=short
	@echo "🧹 Running final cleanup..."
	@./scripts/ray_cleanup.sh
	@echo "✅ E2E tests completed with cleanup"

# Help
help:
	@echo "Ray MCP Server - Available Commands:"
	@echo ""
	@echo "📦 Installation:"
	@echo "  install          Install dependencies"
	@echo "  dev-install      Install development dependencies"
	@echo "  sync             Sync dependencies"
	@echo "  uv-lock          Update lock file"
	@echo "  uv-check         Check dependency consistency"
	@echo ""
	@echo "🧪 Testing:"
	@echo "  test             Run all tests"
	@echo "  test-fast        Run fast tests only"
	@echo "  test-smoke       Run smoke tests"
	@echo "  test-e2e         Run e2e tests with automatic cleanup"
	@echo "  test-e2e-verbose Run e2e tests with detailed output and cleanup"
	@echo "  test-full        Run full test suite"
	@echo "  test-smart       Run smart test selection"
	@echo ""
	@echo "🔧 Development:"
	@echo "  lint-tool-functions  Lint tool function signatures"
	@echo "  test-tool-functions  Test tool function signatures"
	@echo "  count-lines      Count lines of code"
	@echo "  clean            Clean build artifacts" 