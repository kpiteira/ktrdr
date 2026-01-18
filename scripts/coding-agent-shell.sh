#!/bin/bash
# KTRDR Coding Agent Shell Script
# Opens an interactive shell in the coding agent container
#
# Usage:
#   ./scripts/coding-agent-shell.sh           # Opens bash
#   ./scripts/coding-agent-shell.sh python3   # Runs python3
#   ./scripts/coding-agent-shell.sh ls -la    # Runs ls -la

CONTAINER_NAME="ktrdr-coding-agent"

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "ERROR: Container $CONTAINER_NAME is not running"
    echo "       Run ./scripts/coding-agent-init.sh first"
    exit 1
fi

# Determine if we need TTY allocation
if [ -t 0 ]; then
    # Interactive terminal available
    TTY_FLAG="-it"
else
    # No TTY (running from script/pipe)
    TTY_FLAG="-i"
fi

# Run command or default to bash
docker exec $TTY_FLAG -w /workspace "$CONTAINER_NAME" "${@:-bash}"
