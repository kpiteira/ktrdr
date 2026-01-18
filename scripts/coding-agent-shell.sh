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
    echo ""
    echo "The container is started by the orchestrator, or you can start it manually:"
    echo ""
    echo "  docker run -d --name ktrdr-coding-agent \\"
    echo "    -v \$(pwd):/workspace \\"
    echo "    --add-host=host.docker.internal:host-gateway \\"
    echo "    ktrdr-coding-agent:latest"
    echo ""
    echo "If the image doesn't exist, build it first with:"
    echo "  ./scripts/coding-agent-init.sh"
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
