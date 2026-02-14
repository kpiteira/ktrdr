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

# Deprecated entrypoint notice
echo "WARNING: training-host-service/start.sh is deprecated."
echo "Use: uv run kinfra local-prod start-training-host"
echo "Reason: kinfra injects DB secrets from 1Password for host services."

# Fail fast when likely started outside kinfra without DB credentials.
# This avoids hard-to-debug runtime 500s from DB auth failures.
if [[ -z "${KTRDR_DB_PASSWORD:-}" && -z "${DB_PASSWORD:-}" ]]; then
    echo "ERROR: No DB password found in environment (KTRDR_DB_PASSWORD/DB_PASSWORD)."
    echo "Start with: uv run kinfra local-prod start-training-host"
    exit 1
fi

# Start the service
echo "Starting Training Host Service..."
echo "Service will be available at http://127.0.0.1:5002"
echo "Logs will be written to $DIR/logs/"

# Create logs directory if it doesn't exist
mkdir -p "$DIR/logs"

# Run the service with logging
cd "$DIR"
# torch now lives in optional dependency group `ml`; include it explicitly
uv run --extra ml python main.py 2>&1 | tee "logs/training-host-service.log"
