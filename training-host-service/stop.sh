#!/bin/bash
# Stop script for Training Host Service

echo "Stopping Training Host Service..."

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Find the process using port 5002 (Training Host Service port)
PID=$(lsof -ti :5002 2>/dev/null)

if [ -z "$PID" ]; then
    echo "No Training Host Service process found (port 5002 not in use)"
    exit 0
fi

echo "Found Training Host Service process: $PID"

# Verify it's running from the correct directory
PROCESS_DIR=$(lsof -p $PID 2>/dev/null | grep cwd | awk '{print $NF}')
if [[ "$PROCESS_DIR" != *"training-host-service"* ]]; then
    echo "Warning: Process on port 5002 is not from training-host-service directory"
    echo "Process directory: $PROCESS_DIR"
fi

# Kill the process gracefully
echo "Stopping process $PID..."
kill $PID

# Wait a bit for graceful shutdown
sleep 2

# Check if process is still running
if kill -0 $PID 2>/dev/null; then
    echo "Process $PID still running, forcing termination..."
    kill -9 $PID
    sleep 1
fi

# Verify it's stopped
if kill -0 $PID 2>/dev/null; then
    echo "Failed to stop process $PID"
    exit 1
else
    echo "Training Host Service stopped successfully"
fi

# Verify port is free
if lsof -i :5002 > /dev/null 2>&1; then
    echo "Warning: Port 5002 still in use"
else
    echo "Port 5002 is now free"
fi