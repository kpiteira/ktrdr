#!/bin/bash
# Stop script for Training Host Service

echo "Stopping Training Host Service..."

# Find and kill the training host service process
PIDS=$(ps aux | grep "python.*main.py" | grep -v grep | awk '{print $2}')

if [ -z "$PIDS" ]; then
    echo "No Training Host Service process found"
    exit 0
fi

echo "Found Training Host Service processes: $PIDS"

# Kill the processes gracefully
for PID in $PIDS; do
    echo "Stopping process $PID..."
    kill $PID
    
    # Wait a bit for graceful shutdown
    sleep 2
    
    # Check if process is still running
    if kill -0 $PID 2>/dev/null; then
        echo "Process $PID still running, forcing termination..."
        kill -9 $PID
    fi
done

echo "Training Host Service stopped"