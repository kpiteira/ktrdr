#!/bin/bash
#
# Unified Stop Script for KTRDR Host Services
#
# This script stops both IB Host Service and Training Host Service
# in the correct reverse dependency order.
#

set -e  # Exit on any error

echo "🛑 Stopping KTRDR Host Services..."
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

# Stop services using the service manager
echo ""
echo "Stopping services in reverse dependency order..."
$PYTHON_CMD "$SCRIPT_DIR/service_manager.py" stop

# Check final status
echo ""
echo "Final status check..."
$PYTHON_CMD "$SCRIPT_DIR/service_manager.py" status

echo ""
echo "✅ KTRDR Host Services shutdown complete!"