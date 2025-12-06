#!/bin/bash
# MCP Container Restart Script
# This script ONLY restarts the MCP containers, never touches other services

set -e

SCRIPT_DIR="$(dirname "$0")"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Parse arguments
TARGET="${1:-all}"

echo "=========================================="
echo "  KTRDR MCP Container Restart"
echo "=========================================="
echo ""

cd "$PROJECT_ROOT"

case "$TARGET" in
    local)
        echo "Restarting ktrdr-mcp-local..."
        docker compose -f docker-compose.dev.yml restart mcp-local
        ;;
    preprod)
        echo "Restarting ktrdr-mcp-preprod..."
        docker compose -f docker-compose.dev.yml restart mcp-preprod
        ;;
    all|*)
        echo "Restarting all MCP containers..."
        docker compose -f docker-compose.dev.yml restart mcp-local mcp-preprod
        ;;
esac

echo ""
echo "MCP containers restarted successfully"
echo ""
echo "Container status:"
docker ps --filter "name=ktrdr-mcp" --format "table {{.Names}}\t{{.Status}}"

echo ""
echo "Usage: $0 [local|preprod|all]"
echo ""
