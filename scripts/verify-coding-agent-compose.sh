#!/bin/bash
# Verification script for Task 1.3: Coding Agent Docker Compose
# This script validates all acceptance criteria

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/deploy/environments/coding-agent/docker-compose.yml"
CONTAINER_NAME="ktrdr-coding-agent"

cleanup() {
    echo ""
    echo "Cleaning up..."
    docker compose -f "$COMPOSE_FILE" down -v 2>/dev/null || true
}
trap cleanup EXIT

echo "=== Task 1.3: Coding Agent Docker Compose Verification ==="
echo ""

# Check 1: Compose file exists
echo "Check 1: Compose file exists..."
if [ ! -f "$COMPOSE_FILE" ]; then
    echo "  FAIL: $COMPOSE_FILE not found"
    exit 1
fi
echo "  PASS: Compose file exists"

# Check 2: Valid YAML (docker compose config validates)
echo ""
echo "Check 2: Valid YAML..."
if ! docker compose -f "$COMPOSE_FILE" config > /dev/null 2>&1; then
    echo "  FAIL: Invalid docker-compose YAML"
    docker compose -f "$COMPOSE_FILE" config
    exit 1
fi
echo "  PASS: Valid docker-compose YAML"

# Check 3: Container starts successfully
echo ""
echo "Check 3: Container starts successfully..."

# Create shared data directory if it doesn't exist (for testing)
mkdir -p ~/Documents/ktrdr-shared/data

# Export a test API key for the container
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-test-key-for-verification}"

if ! docker compose -f "$COMPOSE_FILE" up -d --build 2>&1; then
    echo "  FAIL: Container failed to start"
    exit 1
fi

# Wait for container to be running
sleep 3

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "  FAIL: Container $CONTAINER_NAME is not running"
    docker compose -f "$COMPOSE_FILE" logs
    exit 1
fi
echo "  PASS: Container started successfully"

# Check 4: All mounts are accessible
echo ""
echo "Check 4: All mounts are accessible..."

# Check workspace mount
if ! docker exec "$CONTAINER_NAME" test -d /workspace; then
    echo "  FAIL: /workspace not accessible"
    exit 1
fi
echo "  - /workspace: accessible"

# Check shared data mount (read-only)
if ! docker exec "$CONTAINER_NAME" test -d /shared/data; then
    echo "  FAIL: /shared/data not accessible"
    exit 1
fi
echo "  - /shared/data: accessible"

# Check env mounts
for dir in /env/models /env/strategies /env/logs; do
    if ! docker exec "$CONTAINER_NAME" test -d "$dir"; then
        echo "  FAIL: $dir not accessible"
        exit 1
    fi
    echo "  - $dir: accessible"
done

# Verify shared data is read-only
if docker exec "$CONTAINER_NAME" touch /shared/data/test-write 2>/dev/null; then
    echo "  FAIL: /shared/data should be read-only but is writable"
    docker exec "$CONTAINER_NAME" rm -f /shared/data/test-write
    exit 1
fi
echo "  - /shared/data: confirmed read-only"

echo "  PASS: All mounts accessible"

# Check 5: Can reach Docker daemon from inside container
echo ""
echo "Check 5: Can reach Docker daemon..."
if ! docker exec "$CONTAINER_NAME" docker ps > /dev/null 2>&1; then
    echo "  FAIL: Cannot reach Docker daemon from inside container"
    exit 1
fi
echo "  PASS: Docker daemon accessible"

# Check 6: ANTHROPIC_API_KEY is passed through
echo ""
echo "Check 6: ANTHROPIC_API_KEY environment variable..."
API_KEY_IN_CONTAINER=$(docker exec "$CONTAINER_NAME" printenv ANTHROPIC_API_KEY 2>/dev/null || echo "")
if [ -z "$API_KEY_IN_CONTAINER" ]; then
    echo "  FAIL: ANTHROPIC_API_KEY not set in container"
    exit 1
fi
echo "  PASS: ANTHROPIC_API_KEY is set"

echo ""
echo "=== All checks passed! ==="
echo ""
echo "Acceptance Criteria:"
echo "  [x] Compose file is valid YAML"
echo "  [x] Container starts successfully"
echo "  [x] All mounts are accessible"
echo "  [x] Can reach Docker daemon from inside container"
