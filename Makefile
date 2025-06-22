# Ray MCP Server - Test Automation

.PHONY: test test-fast test-smoke test-e2e test-full test-smart install dev-install clean

# Default development test (fast)
test: test-fast

# Fast test suite (excludes e2e tests) - for development
test-fast:
	@echo "🏃‍♂️ Running fast test suite..."
	@pytest tests/ -m "not e2e and not slow" --tb=short -v --maxfail=3

# Smoke tests - minimal verification
test-smoke:
	@echo "💨 Running smoke tests..."
	@pytest tests/ -m "smoke" --tb=short -v --maxfail=1

# End-to-end tests only - for major changes
test-e2e:
	@echo "🔄 Running e2e tests (this may take several minutes)..."
	@pytest tests/ -m "e2e" --tb=short -v --maxfail=1

# Full test suite - all tests including e2e
test-full:
	@echo "🔍 Running complete test suite..."
	@pytest tests/ --tb=short -v --cov=ray_mcp --cov-report=term-missing --cov-report=html:htmlcov

# Smart test runner - detects changes and runs appropriate tests
test-smart:
	@scripts/smart-test.sh

# Installation commands
install:
	pip install -e .

dev-install:
	pip install -e .[dev]

# Cleanup
clean:
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf __pycache__/
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +

# Help
help:
	@echo "Available test commands:"
	@echo "  make test       - Run fast test suite (default, excludes e2e)"
	@echo "  make test-fast  - Run fast test suite (excludes e2e tests)"
	@echo "  make test-smoke - Run smoke tests (minimal verification)"
	@echo "  make test-e2e   - Run e2e tests only (for major changes)"
	@echo "  make test-full  - Run complete test suite (includes e2e)"
	@echo "  make test-smart - Smart test runner (detects changes)"
	@echo ""
	@echo "Development commands:"
	@echo "  make install    - Install package"
	@echo "  make dev-install- Install with dev dependencies"
	@echo "  make clean      - Clean up test artifacts" 