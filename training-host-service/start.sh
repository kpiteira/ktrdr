#!/bin/bash
# Start script for Training Host Service

# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Activate virtual environment if it exists
if [ -d "$DIR/venv" ]; then
    source "$DIR/venv/bin/activate"
    echo "Activated virtual environment: $DIR/venv"
fi

# Set Python path to include parent directory for ktrdr imports
export PYTHONPATH="$DIR/..:$PYTHONPATH"

# Start the service
echo "Starting Training Host Service..."
echo "Service will be available at http://127.0.0.1:5002"
echo "Logs will be written to $DIR/logs/"

# Create logs directory if it doesn't exist
mkdir -p "$DIR/logs"

# Run the service with logging
cd "$DIR"
python main.py 2>&1 | tee "logs/training-host-service.log"