#!/bin/bash
# KTRDR Sandbox Shell Script
# Opens an interactive shell in the sandbox container
#
# Usage:
#   ./scripts/sandbox-shell.sh           # Opens bash
#   ./scripts/sandbox-shell.sh python3   # Runs python3
#   ./scripts/sandbox-shell.sh ls -la    # Runs ls -la

CONTAINER_NAME="ktrdr-sandbox"

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "ERROR: Container $CONTAINER_NAME is not running"
    echo "       Run ./scripts/sandbox-init.sh first"
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
