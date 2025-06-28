# Ray MCP Server - Test Automation (UV Native)

.PHONY: test test-fast test-e2e test-full install dev-install sync clean uv-lock uv-check lint-tool-functions test-tool-functions wc test-e2e-clean test-e2e-clean-x test-e2e-file test-e2e-clean-verbose

# Default development test (fast)
test: test-fast

# Fast test suite (excludes e2e tests) - for development
test-fast:
	@echo "🏃‍♂️ Running fast test suite..."
	@uv run pytest tests/ -k "not e2e" --tb=short -v --cov=ray_mcp --cov-report=term-missing

# End-to-end tests only - for major changes
test-e2e:
	@echo "🧪 Running e2e tests with automatic cleanup..."
	@echo "🧹 Running initial cleanup..."
	@./scripts/ray_cleanup.sh
	@echo "🚀 Starting e2e tests with automatic cleanup..."
	@uv run pytest tests/ -m e2e -v --tb=short
	@echo "🧹 Running final cleanup..."
	@./scripts/ray_cleanup.sh
	@echo "✅ E2E tests completed with cleanup"

# Full test suite - all tests including e2e
test-full:
	@echo "🔍 Running complete test suite..."
	@uv run pytest tests/ --tb=short -v --cov=ray_mcp --cov-report=term-missing --cov-report=html:htmlcov

# Tool function specific tests
test-tool-functions:
	@echo "🔧 Running tool function tests..."
	@echo "Note: tool_functions.py has been removed. Use test-full instead."

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

# Run e2e tests with automatic cleanup between tests (using pytest plugin)
test-e2e-clean:
	@echo "🧪 Running e2e tests with automatic cleanup..."
	@echo "🧹 Running initial cleanup..."
	@./scripts/ray_cleanup.sh
	@echo "🚀 Starting e2e tests with automatic cleanup..."
	@uv run pytest tests/ -m e2e -v --tb=short
	@echo "🧹 Running final cleanup..."
	@./scripts/ray_cleanup.sh
	@echo "✅ E2E tests completed with cleanup"

# Run e2e tests with detailed output and cleanup
test-e2e-verbose:
	@echo "🧪 Running e2e tests with detailed output and cleanup..."
	@echo "🧹 Running initial cleanup..."
	@./scripts/ray_cleanup.sh
	@echo "🚀 Starting e2e tests with automatic cleanup..."
	@uv run pytest tests/ -m e2e -v -s --tb=long
	@echo "🧹 Running final cleanup..."
	@./scripts/ray_cleanup.sh
	@echo "✅ E2E tests completed with cleanup"

# Run specific e2e test file with cleanup
test-e2e-file:
	@echo "🧪 Running specific e2e test file with automatic cleanup..."
	@echo "🧹 Running initial cleanup..."
	@./scripts/ray_cleanup.sh
	@echo "🚀 Starting e2e tests from test_e2e_integration.py..."
	@uv run pytest tests/test_e2e_integration.py -v --tb=short
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
	@echo "  test             Run fast tests only"
	@echo "  test-fast        Run fast tests only"
	@echo "  test-e2e         Run e2e tests with automatic cleanup"
	@echo "  test-e2e-verbose Run e2e tests with detailed output and cleanup"
	@echo "  test-full        Run full test suite"
	@echo ""
	@echo "🔧 Development:"
	@echo "  lint-tool-functions  Lint tool function signatures"
	@echo "  test-tool-functions  Test tool function signatures"
	@echo "  wc                 Count lines of code with directory breakdown"
	@echo "  clean              Clean build artifacts" 