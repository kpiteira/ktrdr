#!/bin/bash

# KTRDR Complete Startup Script
# This script starts both the IB host service and the Docker backend

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Starting KTRDR Complete System..."
echo "=================================="

# Step 1: Start IB Host Service
echo ""
echo "📡 Step 1: Starting IB Host Service..."
cd ib-host-service

# Check if already running
if curl -s http://localhost:5001/health > /dev/null 2>&1; then
    echo "✅ IB Host Service already running on port 5001"
else
    echo "🔧 Starting IB Host Service..."
    ./start.sh
    
    # Wait for service to be ready
    echo "⏳ Waiting for IB Host Service to be ready..."
    for i in {1..10}; do
        if curl -s http://localhost:5001/health > /dev/null 2>&1; then
            echo "✅ IB Host Service is ready!"
            break
        fi
        echo "   Attempt $i/10 - waiting 2 seconds..."
        sleep 2
    done
    
    if ! curl -s http://localhost:5001/health > /dev/null 2>&1; then
        echo "❌ IB Host Service failed to start after 20 seconds"
        echo "   Check logs: ./ib-host-service/logs/ib-host-service.log"
        exit 1
    fi
fi

# Step 2: Start Docker Backend
echo ""
echo "🐳 Step 2: Starting Docker Backend..."
cd "$SCRIPT_DIR"

# Set environment variable to ensure host service is used
export USE_IB_HOST_SERVICE=true

# Start Docker services
echo "🔧 Starting Docker services..."
docker-compose -f docker/docker-compose.yml up -d

# Wait for backend to be ready
echo "⏳ Waiting for backend to be ready..."
for i in {1..15}; do
    if curl -s http://localhost:8000/api/v1/health > /dev/null 2>&1; then
        echo "✅ Backend is ready!"
        break
    fi
    echo "   Attempt $i/15 - waiting 3 seconds..."
    sleep 3
done

if ! curl -s http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    echo "❌ Backend failed to start after 45 seconds"
    echo "   Check logs: docker logs ktrdr-backend"
    exit 1
fi

# Step 3: Status Check
echo ""
echo "🎯 Step 3: System Status Check..."
echo ""

# IB Host Service Status
echo "📡 IB Host Service:"
if curl -s http://localhost:5001/health > /dev/null 2>&1; then
    echo "   ✅ Running on http://localhost:5001"
    echo "   📊 Detailed status: curl http://localhost:5001/health/detailed"
else
    echo "   ❌ Not responding"
fi

# Backend Status
echo ""
echo "🐳 Backend Service:"
if curl -s http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    echo "   ✅ Running on http://localhost:8000"
    echo "   📊 API docs: http://localhost:8000/docs"
else
    echo "   ❌ Not responding"
fi

# Docker Services
echo ""
echo "🐳 Docker Services:"
docker-compose -f docker/docker-compose.yml ps

echo ""
echo "🎉 KTRDR Complete System Started Successfully!"
echo ""
echo "📋 Quick Commands:"
echo "   • IB Host Service logs: tail -f ib-host-service/logs/ib-host-service.log"
echo "   • Backend logs: docker logs -f ktrdr-backend"
echo "   • Stop all: ./stop_ktrdr.sh"
echo "   • API documentation: http://localhost:8000/docs"
echo ""
echo "🔧 Troubleshooting:"
echo "   • IB Host Service status: curl http://localhost:5001/health/detailed"
echo "   • Backend health: curl http://localhost:8000/api/v1/health"
echo "   • Test data fetch: ktrdr data fetch AAPL 1h --start-date 2024-01-01 --end-date 2024-01-02"