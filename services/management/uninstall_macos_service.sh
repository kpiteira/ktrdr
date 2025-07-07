#!/bin/bash
#
# Uninstall KTRDR Host Services from macOS launchd
#
# This script removes the KTRDR host services from automatic startup
# and stops any currently running instances.
#

set -e  # Exit on any error

echo "🗑️  Uninstalling KTRDR Host Services from macOS auto-startup"
echo "==========================================================="

# Get service information
SERVICE_LABEL="com.ktrdr.host-services"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="$LAUNCHD_DIR/$SERVICE_LABEL.plist"

echo "Service label: $SERVICE_LABEL"
echo "Plist file: $PLIST_FILE"

# Check if service is installed
if [ ! -f "$PLIST_FILE" ]; then
    echo "❌ Service is not installed (plist file not found)"
    exit 0
fi

# Stop the service if it's running
echo "Stopping service..."
if launchctl list | grep -q "$SERVICE_LABEL"; then
    echo "Service is running, stopping it..."
    launchctl stop "$SERVICE_LABEL" 2>/dev/null || true
    sleep 2
fi

# Unload the service
echo "Unloading service from launchd..."
if launchctl unload "$PLIST_FILE" 2>/dev/null; then
    echo "✅ Service unloaded successfully"
else
    echo "⚠️  Service may not have been loaded"
fi

# Remove the plist file
echo "Removing service configuration..."
rm -f "$PLIST_FILE"

# Verify removal
if launchctl list | grep -q "$SERVICE_LABEL"; then
    echo "⚠️  Service may still be registered with launchd"
else
    echo "✅ Service successfully removed from launchd"
fi

# Stop any remaining service processes
echo "Checking for remaining service processes..."
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# Try to stop services gracefully using service manager
if [ -f "services/management/service_manager.py" ]; then
    echo "Stopping any remaining host services..."
    if command -v uv >/dev/null 2>&1; then
        uv run python services/management/service_manager.py stop 2>/dev/null || true
    else
        python3 services/management/service_manager.py stop 2>/dev/null || true
    fi
fi

echo ""
echo "✅ KTRDR Host Services uninstalled successfully!"
echo ""
echo "The services will no longer start automatically on system boot."
echo "You can manually start them using:"
echo "  $PROJECT_ROOT/services/management/start_all_services.sh"
echo ""
echo "To reinstall auto-startup, run:"
echo "  $PROJECT_ROOT/services/management/install_macos_service.sh"