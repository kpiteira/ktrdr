#!/bin/bash
# KTRDR Coding Agent Initialization Script
# Builds the coding agent Docker image for use with the orchestrator.
#
# Usage: ./scripts/coding-agent-init.sh
#
# NOTE: This script only builds the image. The container is started by the
# orchestrator with the code folder mounted at runtime:
#
#   docker run -d --name ktrdr-coding-agent \
#     -v /path/to/code:/workspace \
#     --add-host=host.docker.internal:host-gateway \
#     ktrdr-coding-agent:latest
#
# For manual testing, you can start a container with:
#   docker run -it --rm -v $(pwd):/workspace ktrdr-coding-agent:latest bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/deploy/environments/coding-agent/docker-compose.yml"

echo "=== KTRDR Coding Agent Image Build ==="
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

# Build coding agent image
echo "Building coding agent image..."
docker compose -f "$COMPOSE_FILE" build
echo "Done."

echo ""
echo "=== Image Build Complete ==="
echo ""
echo "The ktrdr-coding-agent:latest image is ready."
echo ""
echo "The orchestrator will start the container automatically when running"
echo "milestones. For manual testing, use:"
echo ""
echo "  docker run -d --name ktrdr-coding-agent \\"
echo "    -v \$(pwd):/workspace \\"
echo "    --add-host=host.docker.internal:host-gateway \\"
echo "    ktrdr-coding-agent:latest"
echo ""
echo "Then access with:"
echo "  ./scripts/coding-agent-shell.sh"
echo ""
