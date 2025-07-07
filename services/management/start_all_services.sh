#!/bin/bash
#
# Unified Startup Script for KTRDR Host Services
#
# This script starts both IB Host Service and Training Host Service
# in the correct dependency order with health validation.
#

set -e  # Exit on any error

echo "🚀 Starting KTRDR Host Services..."
echo "=================================="

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

# Start services using the service manager
echo ""
echo "Starting services with dependency resolution..."
$PYTHON_CMD "$SCRIPT_DIR/service_manager.py" start

# Check final status
echo ""
echo "Final status check..."
$PYTHON_CMD "$SCRIPT_DIR/service_manager.py" status

echo ""
echo "🎉 KTRDR Host Services startup complete!"
echo ""
echo "Available services:"
echo "  • IB Host Service:      http://localhost:5001/health"
echo "  • Training Host Service: http://localhost:5002/health"
echo ""
echo "To monitor services: $PYTHON_CMD $SCRIPT_DIR/service_manager.py monitor"
echo "To stop all services: $SCRIPT_DIR/stop_all_services.sh"