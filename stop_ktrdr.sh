#!/bin/bash

# KTRDR Complete Stop Script
# This script stops both the Docker backend and the IB host service

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🛑 Stopping KTRDR Complete System..."
echo "==================================="

# Step 1: Stop Docker Services
echo ""
echo "🐳 Step 1: Stopping Docker Services..."
docker-compose -f docker/docker-compose.yml down

echo "✅ Docker services stopped"

# Step 2: Stop IB Host Service
echo ""
echo "📡 Step 2: Stopping IB Host Service..."
cd ib-host-service

if curl -s http://localhost:5001/health > /dev/null 2>&1; then
    echo "🔧 Stopping IB Host Service..."
    ./stop.sh
    echo "✅ IB Host Service stopped"
else
    echo "ℹ️  IB Host Service was not running"
fi

echo ""
echo "🎉 KTRDR Complete System Stopped Successfully!"
echo ""
echo "📋 To start again: ./start_ktrdr.sh"