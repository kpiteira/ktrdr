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

# Find the process using port 5001 (IB Host Service port)
PID=$(lsof -ti :5001 2>/dev/null)

if [ -z "$PID" ]; then
    echo "❌ IB Connector Host Service is not running (port 5001 not in use)"
    exit 1
fi

echo "Found service running with PID: $PID"

# Verify it's running from the correct directory
PROCESS_DIR=$(lsof -p $PID 2>/dev/null | grep cwd | awk '{print $NF}')
if [[ "$PROCESS_DIR" != *"ib-host-service"* ]]; then
    echo "⚠️  Warning: Process on port 5001 is not from ib-host-service directory"
    echo "Process directory: $PROCESS_DIR"
fi

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