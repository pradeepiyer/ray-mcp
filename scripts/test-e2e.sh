#!/bin/bash
# End-to-end test suite - comprehensive tests for major changes

echo "🔄 Running end-to-end test suite (this may take several minutes)..."

pytest tests/ \
    -m "e2e" \
    --tb=short \
    -v \
    --cov=ray_mcp \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    --maxfail=1

echo "✅ End-to-end test suite completed!" 