#!/bin/bash
# Smoke test suite - minimal tests to verify basic functionality

echo "💨 Running smoke test suite..."

uv run pytest tests/ \
    -m "smoke" \
    --tb=short \
    -v \
    --maxfail=1

echo "✅ Smoke test suite completed!" 