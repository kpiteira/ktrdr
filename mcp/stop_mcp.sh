#!/bin/bash
# MCP Container Stop Script
# This script ONLY stops the MCP containers, never touches other services

set -e

SCRIPT_DIR="$(dirname "$0")"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Parse arguments
TARGET="${1:-all}"

echo "=========================================="
echo "  KTRDR MCP Container Stop"
echo "=========================================="
echo ""

cd "$PROJECT_ROOT"

case "$TARGET" in
    local)
        echo "Stopping ktrdr-mcp-local..."
        docker compose -f docker-compose.dev.yml stop mcp-local
        ;;
    preprod)
        echo "Stopping ktrdr-mcp-preprod..."
        docker compose -f docker-compose.dev.yml stop mcp-preprod
        ;;
    all|*)
        echo "Stopping all MCP containers..."
        docker compose -f docker-compose.dev.yml stop mcp-local mcp-preprod
        ;;
esac

echo ""
echo "MCP containers stopped successfully"
echo ""
echo "Container status:"
docker ps -a --filter "name=ktrdr-mcp" --format "table {{.Names}}\t{{.Status}}"

echo ""
echo "Usage: $0 [local|preprod|all]"
echo ""
