#!/bin/bash
# Fast test suite - excludes e2e tests (for development)

echo "🏃‍♂️ Running fast test suite..."

# Clean up Ray before starting tests
echo "🧹 Pre-test Ray cleanup..."
./scripts/ray_cleanup.sh

# Run the tests
echo "🧪 Starting fast test suite..."
uv run pytest tests/ \
    -m "fast" \
    --tb=short \
    -v \
    --maxfail=3 \
    --cov=ray_mcp \
    --cov-report=term-missing

# Store the exit code
TEST_EXIT_CODE=$?

# Clean up Ray after tests (regardless of test outcome)
echo "🧹 Post-test Ray cleanup..."
./scripts/ray_cleanup.sh

# Exit with the test exit code
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "✅ Fast test suite completed successfully!"
else
    echo "❌ Fast test suite failed!"
fi

exit $TEST_EXIT_CODE 