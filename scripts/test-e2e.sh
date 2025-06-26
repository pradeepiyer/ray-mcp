#!/bin/bash
# End-to-end test suite - comprehensive tests for major changes

echo "🔄 Running end-to-end test suite (this may take several minutes)..."

# Clean up Ray before starting tests
echo "🧹 Pre-test Ray cleanup..."
./scripts/ray_cleanup.sh

# Run the tests
echo "🧪 Starting e2e tests..."
uv run pytest tests/ \
    -m "e2e" \
    --tb=short \
    -v \
    --cov=ray_mcp \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    --maxfail=1

# Store the exit code
TEST_EXIT_CODE=$?

# Clean up Ray after tests (regardless of test outcome)
echo "🧹 Post-test Ray cleanup..."
./scripts/ray_cleanup.sh

# Exit with the test exit code
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "✅ End-to-end test suite completed successfully!"
else
    echo "❌ End-to-end test suite failed!"
fi

exit $TEST_EXIT_CODE 