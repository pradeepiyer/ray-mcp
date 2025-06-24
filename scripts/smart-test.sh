#!/bin/bash
# Smart test runner - detects changes and runs appropriate test suite

echo "🧠 Smart test runner - analyzing changes..."

# Check if git is available and we're in a git repo
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Not in a git repository. Running fast test suite."
    exec scripts/test-fast.sh
    exit $?
fi

# Get changed files since last commit
CHANGED_FILES=$(git diff --name-only HEAD~1 2>/dev/null || git diff --name-only --cached)

if [ -z "$CHANGED_FILES" ]; then
    echo "No changes detected. Running smoke tests."
    exec scripts/test-smoke.sh
    exit $?
fi

echo "Changed files:"
echo "$CHANGED_FILES"

# Check for major changes that require e2e tests
MAJOR_CHANGES=false

# Core functionality changes
if echo "$CHANGED_FILES" | grep -E "(ray_mcp/main\.py|ray_mcp/ray_manager\.py|ray_mcp/tools\.py)" > /dev/null; then
    echo "🔴 Core functionality changes detected"
    MAJOR_CHANGES=true
fi

# Configuration changes
if echo "$CHANGED_FILES" | grep -E "(pyproject\.toml|uv\.lock)" > /dev/null; then
    echo "🟠 Configuration changes detected"
    MAJOR_CHANGES=true
fi

# Example changes (might affect e2e tests)
if echo "$CHANGED_FILES" | grep -E "examples/" > /dev/null; then
    echo "🟡 Example changes detected"
    MAJOR_CHANGES=true
fi

# If only test files or docs changed, run fast tests
if echo "$CHANGED_FILES" | grep -v -E "(\.py$|\.toml$|\.txt$)" | grep -E "(\.md$|\.rst$|docs/)" > /dev/null; then
    if ! echo "$CHANGED_FILES" | grep -E "\.py$" > /dev/null; then
        echo "📝 Only documentation changes detected. Running smoke tests."
        exec scripts/test-smoke.sh
        exit $?
    fi
fi

# Run appropriate test suite
if [ "$MAJOR_CHANGES" = true ]; then
    echo "🔄 Major changes detected. Running e2e test suite."
    exec scripts/test-e2e.sh
else
    echo "🏃‍♂️ Minor changes detected. Running fast test suite."
    exec scripts/test-fast.sh
fi 