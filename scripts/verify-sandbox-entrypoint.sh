#!/bin/bash
# Verification script for Task 1.2: Sandbox Entrypoint
# This script validates all acceptance criteria

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENTRYPOINT="$PROJECT_ROOT/deploy/docker/sandbox/entrypoint.sh"
DOCKERFILE="$PROJECT_ROOT/deploy/docker/sandbox/Dockerfile"
IMAGE_NAME="ktrdr-sandbox-entrypoint-test"
CONTAINER_NAME="ktrdr-sandbox-entrypoint-test"

cleanup() {
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
    docker rmi "$IMAGE_NAME" 2>/dev/null || true
}
trap cleanup EXIT

echo "=== Task 1.2: Sandbox Entrypoint Verification ==="
echo ""

# Check 1: Entrypoint exists and is executable
echo "Check 1: Entrypoint exists and is executable..."
if [ ! -f "$ENTRYPOINT" ]; then
    echo "  FAIL: $ENTRYPOINT not found"
    exit 1
fi
if [ ! -x "$ENTRYPOINT" ]; then
    echo "  FAIL: $ENTRYPOINT is not executable"
    exit 1
fi
echo "  PASS: Entrypoint exists and is executable"

# Build test image
echo ""
echo "Building test image..."
docker build -t "$IMAGE_NAME" -f "$DOCKERFILE" "$PROJECT_ROOT" > /dev/null 2>&1

# Check 2: Entrypoint runs without error (with API key set)
echo ""
echo "Check 2: Entrypoint runs without error..."
docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
docker run -d --name "$CONTAINER_NAME" -e ANTHROPIC_API_KEY="test-key" "$IMAGE_NAME" > /dev/null 2>&1
sleep 2

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "  FAIL: Container is not running"
    docker logs "$CONTAINER_NAME" 2>&1
    exit 1
fi
echo "  PASS: Entrypoint runs without error"

# Check 3: Logs warning if workspace empty (no .git)
echo ""
echo "Check 3: Logs warning if workspace empty..."
LOGS=$(docker logs "$CONTAINER_NAME" 2>&1)
if ! echo "$LOGS" | grep -qi "warning.*workspace\|workspace.*empty\|no.*git"; then
    echo "  FAIL: No warning about empty workspace in logs"
    echo "  Logs: $LOGS"
    exit 1
fi
echo "  PASS: Warning logged for empty workspace"

# Check 4: Logs warning if API key missing
echo ""
echo "Check 4: Logs warning if API key missing..."
docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
docker run -d --name "$CONTAINER_NAME" "$IMAGE_NAME" > /dev/null 2>&1
sleep 2

LOGS_NO_KEY=$(docker logs "$CONTAINER_NAME" 2>&1)
if ! echo "$LOGS_NO_KEY" | grep -qi "warning.*api.*key\|anthropic.*key.*missing\|api.*key.*not.*set"; then
    echo "  FAIL: No warning about missing API key in logs"
    echo "  Logs: $LOGS_NO_KEY"
    exit 1
fi
echo "  PASS: Warning logged for missing API key"

# Check 5: Container stays running for exec commands
echo ""
echo "Check 5: Container stays running for exec commands..."
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "  FAIL: Container is not running"
    exit 1
fi

# Try to exec into container
if ! docker exec "$CONTAINER_NAME" echo "exec works" > /dev/null 2>&1; then
    echo "  FAIL: Cannot exec into container"
    exit 1
fi
echo "  PASS: Container stays running and accepts exec commands"

echo ""
echo "=== All checks passed! ==="
echo ""
echo "Acceptance Criteria:"
echo "  [x] Entrypoint runs without error"
echo "  [x] Logs warning if workspace empty"
echo "  [x] Logs warning if API key missing"
echo "  [x] Container stays running for exec commands"
