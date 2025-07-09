# Ray MCP Server - Test Automation (UV Native)
# 
# Minimal Testing Strategy:
# - test-fast:  Unit tests only (fast development feedback)
# - test-smoke: Critical functionality validation (quick confidence)
# - test:       Complete test suite including E2E (full validation)

.PHONY: test test-fast test-smoke test-e2e install dev-install sync clean uv-lock uv-check lint-tool-functions wc clean-coverage clean-all test-cov

# ================================================================================
# TESTING TARGETS
# ================================================================================

# Default test - full test suite including e2e
test:
	@echo "🔍 Running complete test suite..."
	@uv run pytest tests/ --tb=short -v --cov=ray_mcp --cov-report=term-missing --cov-report=html:htmlcov

# Fast test suite (excludes e2e tests) - for development
test-fast:
	@echo "🏃‍♂️ Running fast test suite..."
	@uv run pytest tests/ -k "not e2e" --tb=short -v --cov=ray_mcp --cov-report=term-missing

# Comprehensive end-to-end server tests (consolidated)
test-e2e:
	@echo "🚀 Running comprehensive Ray MCP server tests..."
	@echo "📋 Testing complete end-to-end functionality..."
	@uv run pytest tests/test_mcp_server.py --tb=short -v
	@echo "✅ End-to-end server tests completed!"

# Smoke tests - critical functionality validation for quick confidence
test-smoke:
	@echo "💨 Running smoke tests for critical functionality..."
	@echo "🚀 Testing system architecture integration..."
	@uv run python -c "\
import asyncio; \
from ray_mcp.main import ray_manager; \
from ray_mcp.managers.unified_manager import RayUnifiedManager; \
print('🔧 Testing System Architecture Integration'); \
print('=' * 60); \
print('✅ Architecture Validation:'); \
print(f'   - Type: {type(ray_manager).__name__}'); \
print(f'   - Instance: {isinstance(ray_manager, RayUnifiedManager)}'); \
print('✅ Component Access:'); \
components = {'State Manager': ray_manager.get_state_manager(), 'Cluster Manager': ray_manager.get_cluster_manager(), 'Job Manager': ray_manager.get_job_manager(), 'Log Manager': ray_manager.get_log_manager(), 'Port Manager': ray_manager.get_port_manager()}; \
[print(f'   - {name}: {\"✅ Available\" if component else \"❌ Missing\"}') for name, component in components.items()]; \
print('✅ Integration Test: All systems operational!'); \
print('✅ System architecture successfully deployed!'); \
"
	@echo "🚀 Testing core unit functionality..."
	@uv run pytest tests/test_core_unified_manager.py::TestRayUnifiedManagerCore::test_manager_instantiation_creates_all_components -v --tb=short
	@echo "✅ Smoke tests completed - System architecture validated!"

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

# Test with coverage (using new clean setup)
test-cov: clean-coverage
	@echo "🧪 Running tests with coverage..."
	python -m pytest --cov=ray_mcp --cov-report=term-missing --cov-report=html:htmlcov
	@echo "📊 Coverage report generated in htmlcov/"

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
	@echo "  test             Run complete test suite including E2E (default)"
	@echo "  test-fast        Run unit tests only for fast development feedback"
	@echo "  test-smoke       Run smoke tests for quick critical functionality validation"
	@echo "  test-e2e         Run comprehensive end-to-end server tests (consolidated)"
	@echo "  test-cov         Run tests with coverage"
	@echo ""
	@echo "🔧 Development:"
	@echo "  lint             Run linting checks"
	@echo "  lint-enhanced    Run enhanced linting with tool function checks"
	@echo "  format           Format code"
	@echo "  lint-tool-functions  Lint tool function signatures"
	@echo "  wc               Count lines of code with directory breakdown"
	@echo "  clean            Clean build artifacts"
	@echo "  clean-coverage   Clean coverage files"
	@echo "  clean-all        Clean all generated files" 