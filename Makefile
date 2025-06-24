# Ray MCP Server - Test Automation (UV Native)

.PHONY: test test-fast test-smoke test-e2e test-full test-smart install dev-install sync clean uv-lock uv-check

# Default development test (fast)
test: test-fast

# Fast test suite (excludes e2e tests) - for development
test-fast:
	@echo "🏃‍♂️ Running fast test suite..."
	@python -m pytest tests/ -m "fast" --tb=short -v --maxfail=3 --cov=ray_mcp --cov-report=term-missing

# Smoke tests - minimal verification
test-smoke:
	@echo "💨 Running smoke tests..."
	@python -m pytest tests/ -m "smoke" --tb=short -v --maxfail=1

# End-to-end tests only - for major changes
test-e2e:
	@echo "🔄 Running e2e tests (this may take several minutes)..."
	@python -m pytest tests/ -m "e2e" --tb=short -v --maxfail=1

# Full test suite - all tests including e2e
test-full:
	@echo "🔍 Running complete test suite..."
	@python -m pytest tests/ --tb=short -v --cov=ray_mcp --cov-report=term-missing --cov-report=html

# Smart test runner - detects changes and runs appropriate tests
test-smart:
	@scripts/smart-test.sh

# Linting - matches CI workflow
lint:
	@echo "🔍 Running linting checks..."
	@uv run black --check ray_mcp/ examples/ tests/
	@uv run isort --check-only ray_mcp/ examples/ tests/
	@uv run pyright --check-only ray_mcp/ examples/ tests/
	@echo "✅ All linting checks passed!"

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

# Help
help:
	@echo "Available test commands:"
	@echo "  make test       - Run fast test suite (default, uses 'fast' marker)"
	@echo "  make test-fast  - Run fast test suite (uses 'fast' marker, excludes e2e)"
	@echo "  make test-smoke - Run smoke tests (minimal verification)"
	@echo "  make test-e2e   - Run e2e tests only (for major changes)"
	@echo "  make test-full  - Run complete test suite (includes e2e)"
	@echo "  make test-smart - Smart test runner (detects changes)"
	@echo ""
	@echo "Linting and formatting:"
	@echo "  make lint       - Run linting checks (black, isort, pyright)"
	@echo "  make format     - Format code with black and isort"
	@echo ""
	@echo "Test markers:"
	@echo "  fast           - Fast unit and integration tests"
	@echo "  e2e            - End-to-end tests"
	@echo "  smoke          - Minimal smoke tests"
	@echo "  slow           - Slow running tests"
	@echo ""
	@echo "UV dependency management:"
	@echo "  make sync       - Install all dependencies (dev + prod)"
	@echo "  make install    - Install package only"
	@echo "  make dev-install- Full development setup (recommended)"
	@echo "  make uv-lock    - Update lock file"
	@echo "  make uv-check   - Check dependencies"
	@echo "  make venv       - Create virtual environment"
	@echo ""
	@echo "Other commands:"
	@echo "  make clean      - Clean up build artifacts"
	@echo "  make help       - Show this help message" 