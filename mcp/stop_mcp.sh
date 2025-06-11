#!/bin/bash
# MCP Container Stop Script
# This script ONLY stops the MCP container, never touches backend/frontend

set -e

echo "🛑 Stopping ONLY the MCP container..."
echo "⚠️  This will NOT affect backend or frontend containers"

cd "$(dirname "$0")/.."
docker-compose -f docker/docker-compose.yml stop mcp

echo "✅ MCP container stopped successfully"
echo "📊 Current container status:"
docker ps --filter "name=ktrdr" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"