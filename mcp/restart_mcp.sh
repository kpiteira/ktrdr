#!/bin/bash
# MCP Container Restart Script
# This script ONLY restarts the MCP container, never touches backend/frontend

set -e

echo "🔄 Restarting ONLY the MCP container..."
echo "⚠️  This will NOT affect backend or frontend containers"

cd "$(dirname "$0")/.."
docker-compose -f docker/docker-compose.yml restart mcp

echo "✅ MCP container restarted successfully"
echo "📊 Current container status:"
docker ps --filter "name=ktrdr-mcp" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"