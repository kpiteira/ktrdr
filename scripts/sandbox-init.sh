#!/bin/bash
# KTRDR Sandbox Initialization Script
# First-time setup: builds image, starts container, clones repo
#
# Usage: ./scripts/sandbox-init.sh
#
# This script is idempotent - safe to run multiple times.
# It will skip steps that are already complete.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/deploy/environments/sandbox/docker-compose.yml"
CONTAINER_NAME="ktrdr-sandbox"
REPO_URL="https://github.com/kpiteira/ktrdr.git"

echo "=== KTRDR Sandbox Initialization ==="
echo ""

# Check prerequisites
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed or not in PATH"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "ERROR: Docker daemon is not running"
    exit 1
fi

# Create shared data directory if it doesn't exist
SHARED_DATA_DIR="$HOME/Documents/ktrdr-shared/data"
if [ ! -d "$SHARED_DATA_DIR" ]; then
    echo "Creating shared data directory: $SHARED_DATA_DIR"
    mkdir -p "$SHARED_DATA_DIR"
fi

# Step 1: Build sandbox image
echo "Step 1: Building sandbox image..."
docker compose -f "$COMPOSE_FILE" build
echo "  Done."

# Step 2: Start container
echo ""
echo "Step 2: Starting sandbox container..."
docker compose -f "$COMPOSE_FILE" up -d
echo "  Done."

# Wait for container to be ready
echo ""
echo "Waiting for container to be ready..."
sleep 3

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "ERROR: Container $CONTAINER_NAME failed to start"
    docker compose -f "$COMPOSE_FILE" logs
    exit 1
fi

# Step 3: Clone repo (if not already cloned)
echo ""
echo "Step 3: Setting up workspace..."
if docker exec "$CONTAINER_NAME" test -d /workspace/.git 2>/dev/null; then
    echo "  Repository already cloned. Skipping."
else
    echo "  Cloning repository..."
    docker exec "$CONTAINER_NAME" git clone "$REPO_URL" /workspace
    echo "  Done."
fi

# Step 4: Create env directories (idempotent)
echo ""
echo "Step 4: Creating environment directories..."
docker exec "$CONTAINER_NAME" mkdir -p /env/models /env/strategies /env/logs
echo "  Done."

# Step 5: Verify setup
echo ""
echo "Step 5: Verifying setup..."

# Check workspace
if docker exec "$CONTAINER_NAME" test -d /workspace/.git; then
    BRANCH=$(docker exec "$CONTAINER_NAME" git -C /workspace branch --show-current 2>/dev/null || echo "unknown")
    echo "  Workspace: /workspace (branch: $BRANCH)"
else
    echo "  WARNING: Workspace has no git repository"
fi

# Check env directories
for dir in /env/models /env/strategies /env/logs; do
    if docker exec "$CONTAINER_NAME" test -d "$dir"; then
        echo "  $dir: exists"
    else
        echo "  WARNING: $dir does not exist"
    fi
done

# Check shared data
if docker exec "$CONTAINER_NAME" test -d /shared/data; then
    FILE_COUNT=$(docker exec "$CONTAINER_NAME" ls /shared/data 2>/dev/null | wc -l | xargs)
    echo "  /shared/data: mounted ($FILE_COUNT files)"
else
    echo "  WARNING: /shared/data not mounted"
fi

echo ""
echo "=== Sandbox Initialization Complete ==="
echo ""
echo "Next steps:"
echo "  ./scripts/sandbox-shell.sh     # Interactive shell"
echo "  ./scripts/sandbox-claude.sh    # Run Claude Code"
echo "  ./scripts/sandbox-reset.sh     # Reset workspace"
