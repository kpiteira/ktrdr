#!/bin/bash
#
# Start IB Connector Host Service
#
# This script starts the IB Connector service that provides direct
# IB Gateway connectivity for the KTRDR backend.
#

echo "Starting IB Connector Host Service..."

# Check if IB Gateway is running  
if ! ps aux | grep -i "IB Gateway\|TWS" | grep -v grep > /dev/null; then
    echo "⚠️  Warning: IB Gateway/TWS not detected running"
    echo "   Make sure IB Gateway is started before using the service"
else
    echo "✅ IB Gateway/TWS detected running"
fi

# Change to service directory
cd "$(dirname "$0")"

# Set Python path to include parent directory for ktrdr imports
export PYTHONPATH="${PYTHONPATH}:$(pwd)/.."

# Create logs directory if it doesn't exist
mkdir -p logs

# Start the service with uv (this project uses uv for dependency management)
echo "Starting service on http://localhost:5001"
echo "Logs will be written to: logs/ib-host-service.log"
uv run python main.py > logs/ib-host-service.log 2>&1 &

# Show the process ID
echo "Service started with PID: $!"
echo "Monitor logs with: tail -f logs/ib-host-service.log"