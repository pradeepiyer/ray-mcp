#!/bin/bash
# Fast test suite for development - excludes slow e2e tests

echo "🏃‍♂️ Running fast test suite (excludes e2e tests)..."

pytest tests/ \
    -m "not e2e and not slow" \
    --tb=short \
    -v \
    --cov=ray_mcp \
    --cov-report=term-missing \
    --maxfail=3

echo "✅ Fast test suite completed!" 