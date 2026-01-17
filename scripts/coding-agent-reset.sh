#!/bin/bash
# KTRDR Coding Agent Reset Script
# Resets workspace to clean git state while preserving models/strategies
#
# Usage: ./scripts/coding-agent-reset.sh
#
# What gets reset:
#   - /workspace: Reset to clean git state (untracked files removed, modified files restored)
#   - /env/logs: Cleared
#
# What is preserved:
#   - /env/models: Kept (trained models)
#   - /env/strategies: Kept (generated strategies)
#   - /shared/data: Unchanged (read-only mount)

set -e

CONTAINER_NAME="ktrdr-coding-agent"
START_TIME=$(date +%s)

echo "=== KTRDR Coding Agent Reset ==="
echo ""

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "ERROR: Container $CONTAINER_NAME is not running"
    echo "       Run ./scripts/coding-agent-init.sh first"
    exit 1
fi

# Check if workspace has git repo
if ! docker exec "$CONTAINER_NAME" test -d /workspace/.git; then
    echo "ERROR: /workspace has no git repository"
    echo "       Run ./scripts/coding-agent-init.sh first"
    exit 1
fi

# Step 1: Reset git state (run as ubuntu to avoid ownership issues)
echo "Step 1: Resetting workspace to clean git state..."
docker exec -u ubuntu "$CONTAINER_NAME" bash -c '
    cd /workspace
    echo "  - Removing untracked files..."
    git clean -fdx
    echo "  - Restoring modified files..."
    git checkout .
    echo "  - Pulling latest changes..."
    if git pull --ff-only 2>/dev/null; then
        :
    elif git symbolic-ref --quiet HEAD >/dev/null 2>&1; then
        echo "  - WARNING: git pull failed (check network or auth)"
    else
        echo "  - (skipped: detached HEAD)"
    fi
'
echo "  Done."

# Step 2: Fix workspace ownership (in case new files were created as root)
echo ""
echo "Step 2: Fixing workspace ownership..."
docker exec "$CONTAINER_NAME" chown -R ubuntu:ubuntu /workspace
echo "  Done."

# Step 3: Clear logs
echo ""
echo "Step 3: Clearing logs..."
docker exec "$CONTAINER_NAME" bash -c 'rm -rf /env/logs/* 2>/dev/null || true'
echo "  Done."

# Step 4: Verify state
echo ""
echo "Step 4: Verifying reset..."
docker exec "$CONTAINER_NAME" bash -c '
    cd /workspace
    echo "  Workspace status:"
    echo "    Branch: $(git branch --show-current 2>/dev/null || echo "detached")"
    UNCOMMITTED=$(git status --porcelain 2>/dev/null | wc -l | xargs)
    echo "    Uncommitted changes: $UNCOMMITTED"
    echo ""
    echo "  Preserved:"
    MODELS=$(ls -1 /env/models 2>/dev/null | wc -l | xargs)
    STRATEGIES=$(ls -1 /env/strategies 2>/dev/null | wc -l | xargs)
    echo "    /env/models: $MODELS items"
    echo "    /env/strategies: $STRATEGIES items"
'

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo "=== Coding Agent Reset Complete (${DURATION}s) ==="

# Warn if reset took too long
if [ "$DURATION" -gt 30 ]; then
    echo ""
    echo "WARNING: Reset took longer than 30s target"
fi
