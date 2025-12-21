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

# Check for GH_TOKEN
if [ -z "$GH_TOKEN" ]; then
    echo "WARNING: GH_TOKEN environment variable is not set"
    echo "  GitHub CLI (gh) will not be able to create PRs without it."
    echo ""
    echo "  To fix:"
    echo "    1. Create a token at: https://github.com/settings/tokens"
    echo "    2. Select 'repo' scope (for private repos) or 'public_repo' (for public)"
    echo "    3. Add to your shell profile: export GH_TOKEN=\"ghp_xxxx\""
    echo "    4. Run: source ~/.zshrc (or ~/.bashrc)"
    echo ""
    read -p "Continue without GH_TOKEN? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "GH_TOKEN: set"
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

# Step 3b: Fix workspace ownership (Claude runs as ubuntu, not root)
echo ""
echo "Step 3b: Setting workspace ownership..."
docker exec "$CONTAINER_NAME" chown -R ubuntu:ubuntu /workspace
echo "  Done."

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

# Step 6: Check Claude Code authentication
echo "Step 6: Checking Claude Code authentication..."
if docker exec "$CONTAINER_NAME" test -f /home/ubuntu/.claude/credentials.json 2>/dev/null || \
   docker exec "$CONTAINER_NAME" test -f /root/.claude/credentials.json 2>/dev/null; then
    echo "  Claude Code: logged in"
else
    echo "  Claude Code: NOT logged in"
    echo ""
    echo "  You need to authenticate Claude Code in the sandbox."
    read -p "  Run 'claude login' now? [Y/n] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        echo ""
        echo "  Opening interactive shell for Claude login..."
        echo "  Run 'claude login' and follow the browser auth flow."
        echo "  Type 'exit' when done."
        echo ""
        docker exec -it "$CONTAINER_NAME" bash -c "claude login && echo 'Login successful!'"
    fi
fi

# Step 7: Check GitHub CLI authentication
echo ""
echo "Step 7: Checking GitHub CLI authentication..."
if docker exec "$CONTAINER_NAME" gh auth status &>/dev/null; then
    GH_USER=$(docker exec "$CONTAINER_NAME" gh api user --jq '.login' 2>/dev/null || echo "unknown")
    echo "  GitHub CLI: authenticated as $GH_USER"
else
    if [ -n "$GH_TOKEN" ]; then
        echo "  GitHub CLI: GH_TOKEN set but not yet verified"
        echo "  (Will authenticate on first use)"
    else
        echo "  GitHub CLI: NOT authenticated (GH_TOKEN not set)"
    fi
fi

echo ""
echo "=== Setup Summary ==="
echo ""
echo "Next steps:"
echo "  ./scripts/sandbox-shell.sh     # Interactive shell"
echo "  ./scripts/sandbox-claude.sh    # Run Claude Code"
echo "  ./scripts/sandbox-reset.sh     # Reset workspace"
