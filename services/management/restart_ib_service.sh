#!/bin/bash
#
# Restart IB Host Service
#
# This script stops and then starts the IB Host Service.
#

set -e  # Exit on any error

echo "🔄 Restarting IB Host Service..."
echo "================================="

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Add project to Python path
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# Check if we have uv available
if command -v uv >/dev/null 2>&1; then
    PYTHON_CMD="uv run python"
    echo "✅ Using uv for Python execution"
else
    PYTHON_CMD="python3"
    echo "⚠️  uv not found, using system python3"
fi

# Restart IB service using the service manager
echo ""
echo "Restarting IB Host Service..."
$PYTHON_CMD "$SCRIPT_DIR/service_manager.py" restart --service ib-host

# Check final status
echo ""
echo "Final status check..."
$PYTHON_CMD "$SCRIPT_DIR/service_manager.py" status

echo ""
echo "🎉 IB Host Service restart complete!"
echo ""
echo "Service available at: http://localhost:5001/health"
