#!/bin/bash
#
# Stop IB Connector Host Service
#
# This script stops the IB Connector service that provides direct
# IB Gateway connectivity for the KTRDR backend.
#

echo "Stopping IB Connector Host Service..."

# Change to service directory
cd "$(dirname "$0")"

# Find the process running main.py
PID=$(ps aux | grep "python.*main.py" | grep -v grep | awk '{print $2}')

if [ -z "$PID" ]; then
    echo "❌ IB Connector Host Service is not running"
    exit 1
fi

echo "Found service running with PID: $PID"

# Stop the service
kill $PID

# Wait a moment for graceful shutdown
sleep 2

# Check if it's still running
if ps -p $PID > /dev/null 2>&1; then
    echo "⚠️  Service didn't stop gracefully, forcing shutdown..."
    kill -9 $PID
    sleep 1
fi

# Verify it's stopped
if ps -p $PID > /dev/null 2>&1; then
    echo "❌ Failed to stop service (PID: $PID)"
    exit 1
else
    echo "✅ IB Connector Host Service stopped successfully"
fi

# Check if port is free
if lsof -i :5001 > /dev/null 2>&1; then
    echo "⚠️  Port 5001 still in use"
else
    echo "✅ Port 5001 is now free"
fi