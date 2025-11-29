#!/bin/bash
# MCP Container Build Script
# This script ONLY builds and starts the MCP containers, never touches other services

set -e

SCRIPT_DIR="$(dirname "$0")"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "  KTRDR MCP Container Build"
echo "=========================================="
echo ""
echo "This will build and start MCP containers:"
echo "  - ktrdr-mcp-local   (targets local backend)"
echo "  - ktrdr-mcp-preprod (targets pre-prod backend)"
echo ""

cd "$PROJECT_ROOT"

# Build MCP containers (they share the backend image)
echo "Building MCP containers..."
docker compose -f docker-compose.dev.yml build mcp-local mcp-preprod

echo ""
echo "Starting MCP containers..."
docker compose -f docker-compose.dev.yml up -d mcp-local mcp-preprod

echo ""
echo "MCP containers built and started successfully"
echo ""
echo "Container status:"
docker ps --filter "name=ktrdr-mcp" --format "table {{.Names}}\t{{.Status}}"

echo ""
echo "=========================================="
echo "  Claude MCP Configuration"
echo "=========================================="
echo ""
echo "Copy the contents of mcp/claude_mcp_config.json to your Claude config:"
echo ""
echo "  Mac: ~/Library/Application Support/Claude/claude_desktop_config.json"
echo "  Linux: ~/.config/claude/claude_desktop_config.json"
echo ""
echo "Then restart Claude Desktop/Code to connect."
echo ""
