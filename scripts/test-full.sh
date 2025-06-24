#!/bin/bash
# Full test suite - all tests including e2e (for CI/CD or major releases)

echo "🔍 Running complete test suite (this will take several minutes)..."

python -m pytest tests/ \
    --tb=short \
    -v \
    --cov=ray_mcp \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    --cov-fail-under=80

echo "✅ Complete test suite finished!" 