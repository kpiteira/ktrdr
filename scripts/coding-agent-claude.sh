#!/bin/bash
# KTRDR Coding Agent Claude Script
# Runs Claude Code CLI in the coding agent container
#
# Usage:
#   ./scripts/coding-agent-claude.sh -p "hello"
#   ./scripts/coding-agent-claude.sh -p "implement feature X" --output-format json
#   ./scripts/coding-agent-claude.sh --help

CONTAINER_NAME="ktrdr-coding-agent"

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "ERROR: Container $CONTAINER_NAME is not running"
    echo "       Run ./scripts/coding-agent-init.sh first"
    exit 1
fi

# Check if ANTHROPIC_API_KEY is set in container
if ! docker exec "$CONTAINER_NAME" printenv ANTHROPIC_API_KEY > /dev/null 2>&1; then
    echo "WARNING: ANTHROPIC_API_KEY may not be set in container"
    echo "         Export it before running coding-agent-init.sh"
    echo ""
fi

# Determine if we need TTY allocation
if [ -t 0 ]; then
    TTY_FLAG="-it"
else
    TTY_FLAG="-i"
fi

# Run claude in coding agent container with all arguments passed through
docker exec $TTY_FLAG -w /workspace "$CONTAINER_NAME" claude "$@"
