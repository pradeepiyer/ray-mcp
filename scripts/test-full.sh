#!/bin/bash
# Full test suite - all tests including e2e (for CI/CD or major releases)

echo "🔍 Running complete test suite (this will take several minutes)..."

# Clean up Ray before starting tests
echo "🧹 Pre-test Ray cleanup..."
./scripts/ray_cleanup.sh

# Run the tests
echo "🧪 Starting full test suite..."
uv run pytest tests/ \
    --tb=short \
    -v \
    --cov=ray_mcp \
    --cov-report=term-missing \
    --cov-report=html:htmlcov

# Store the exit code
TEST_EXIT_CODE=$?

# Clean up Ray after tests (regardless of test outcome)
echo "🧹 Post-test Ray cleanup..."
./scripts/ray_cleanup.sh

# Exit with the test exit code
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "✅ Complete test suite finished successfully!"
else
    echo "❌ Complete test suite failed!"
fi

exit $TEST_EXIT_CODE 