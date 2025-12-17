#!/bin/bash
# Verification script for Task 1.1: Sandbox Dockerfile
# This script validates all acceptance criteria

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DOCKERFILE="$PROJECT_ROOT/deploy/docker/sandbox/Dockerfile"
IMAGE_NAME="ktrdr-sandbox-test"

echo "=== Task 1.1: Sandbox Dockerfile Verification ==="
echo ""

# Check 1: Dockerfile exists
echo "Check 1: Dockerfile exists..."
if [ ! -f "$DOCKERFILE" ]; then
    echo "  FAIL: $DOCKERFILE not found"
    exit 1
fi
echo "  PASS: Dockerfile exists"

# Check 2: Dockerfile builds successfully
echo ""
echo "Check 2: Dockerfile builds successfully..."
if ! docker build -t "$IMAGE_NAME" -f "$DOCKERFILE" "$PROJECT_ROOT" > /dev/null 2>&1; then
    echo "  FAIL: Docker build failed"
    docker build -t "$IMAGE_NAME" -f "$DOCKERFILE" "$PROJECT_ROOT"
    exit 1
fi
echo "  PASS: Docker build succeeded"

# Check 3: Container has Python 3.11+
echo ""
echo "Check 3: Python 3.11+ installed..."
PYTHON_VERSION=$(docker run --rm "$IMAGE_NAME" python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
    echo "  FAIL: Python version $PYTHON_VERSION is less than 3.11"
    exit 1
fi
echo "  PASS: Python $PYTHON_VERSION installed"

# Check 4: Node.js installed
echo ""
echo "Check 4: Node.js installed..."
if ! docker run --rm "$IMAGE_NAME" node --version > /dev/null 2>&1; then
    echo "  FAIL: Node.js not installed"
    exit 1
fi
NODE_VERSION=$(docker run --rm "$IMAGE_NAME" node --version)
echo "  PASS: Node.js $NODE_VERSION installed"

# Check 5: Git installed
echo ""
echo "Check 5: Git installed..."
if ! docker run --rm "$IMAGE_NAME" git --version > /dev/null 2>&1; then
    echo "  FAIL: Git not installed"
    exit 1
fi
GIT_VERSION=$(docker run --rm "$IMAGE_NAME" git --version)
echo "  PASS: $GIT_VERSION"

# Check 6: Docker CLI installed
echo ""
echo "Check 6: Docker CLI installed..."
if ! docker run --rm "$IMAGE_NAME" docker --version > /dev/null 2>&1; then
    echo "  FAIL: Docker CLI not installed"
    exit 1
fi
DOCKER_VERSION=$(docker run --rm "$IMAGE_NAME" docker --version)
echo "  PASS: $DOCKER_VERSION"

# Check 7: Claude Code CLI installed and in PATH
echo ""
echo "Check 7: Claude Code CLI installed..."
if ! docker run --rm "$IMAGE_NAME" which claude > /dev/null 2>&1; then
    echo "  FAIL: Claude Code CLI not in PATH"
    exit 1
fi
CLAUDE_PATH=$(docker run --rm "$IMAGE_NAME" which claude)
echo "  PASS: Claude Code CLI at $CLAUDE_PATH"

# Check 8: uv installed
echo ""
echo "Check 8: uv installed..."
if ! docker run --rm "$IMAGE_NAME" uv --version > /dev/null 2>&1; then
    echo "  FAIL: uv not installed"
    exit 1
fi
UV_VERSION=$(docker run --rm "$IMAGE_NAME" uv --version)
echo "  PASS: $UV_VERSION"

# Check 9: Additional tools (curl, jq, make)
echo ""
echo "Check 9: Additional tools (curl, jq, make)..."
for tool in curl jq make; do
    if ! docker run --rm "$IMAGE_NAME" which "$tool" > /dev/null 2>&1; then
        echo "  FAIL: $tool not installed"
        exit 1
    fi
done
echo "  PASS: curl, jq, make installed"

# Check 10: Working directory is /workspace
echo ""
echo "Check 10: Working directory is /workspace..."
WORKDIR=$(docker run --rm "$IMAGE_NAME" pwd)
if [ "$WORKDIR" != "/workspace" ]; then
    echo "  FAIL: Working directory is $WORKDIR, expected /workspace"
    exit 1
fi
echo "  PASS: Working directory is /workspace"

# Cleanup
echo ""
echo "Cleaning up test image..."
docker rmi "$IMAGE_NAME" > /dev/null 2>&1 || true

echo ""
echo "=== All checks passed! ==="
echo ""
echo "Acceptance Criteria:"
echo "  [x] Dockerfile builds successfully"
echo "  [x] Container has Python 3.11+, Node.js, Git, Docker CLI"
echo "  [x] Claude Code CLI is installed and in PATH"
echo "  [x] uv is installed"
