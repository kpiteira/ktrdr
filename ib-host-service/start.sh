#!/bin/bash
#
# Start IB Connector Host Service
#
# This script starts the IB Connector service that provides direct
# IB Gateway connectivity for the KTRDR backend.
#

echo "Starting IB Connector Host Service..."

# Check if IB Gateway is running
if ! pgrep -f "TWS\|IB Gateway" > /dev/null; then
    echo "⚠️  Warning: IB Gateway/TWS not detected running"
    echo "   Make sure IB Gateway is started before using the service"
fi

# Change to service directory
cd "$(dirname "$0")"

# Set Python path to include parent directory for ktrdr imports
export PYTHONPATH="${PYTHONPATH}:$(pwd)/.."

# Install dependencies if not already installed
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Start the service
echo "Starting service on http://localhost:5001"
python main.py