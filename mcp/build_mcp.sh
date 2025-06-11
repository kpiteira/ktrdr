#!/bin/bash
# MCP Container Build Script  
# This script ONLY builds the MCP container, never touches backend/frontend

set -e

echo "🔨 Building ONLY the MCP container..."
echo "⚠️  This will NOT affect backend or frontend containers"

cd "$(dirname "$0")/.."
# Build only MCP container (dependencies removed from compose file)
docker-compose -f docker/docker-compose.yml build mcp

echo "✅ MCP container built successfully"
echo "🚀 Starting MCP container..."
docker-compose -f docker/docker-compose.yml up -d mcp

echo "📊 Current container status:"
docker ps --filter "name=ktrdr" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"