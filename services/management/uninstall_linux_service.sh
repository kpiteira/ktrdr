#!/bin/bash
#
# Uninstall KTRDR Host Services from Linux systemd
#
# This script removes the KTRDR host services from automatic startup
# and stops any currently running instances.
#

set -e  # Exit on any error

echo "🗑️  Uninstalling KTRDR Host Services from Linux auto-startup"
echo "==========================================================="

# Check if we're on a systemd system
if ! command -v systemctl >/dev/null 2>&1; then
    echo "❌ systemctl not found. This script requires systemd."
    exit 1
fi

# Get service information
SERVICE_NAME="ktrdr-host-services"
SYSTEMD_DIR="/etc/systemd/system"
SERVICE_FILE="$SYSTEMD_DIR/$SERVICE_NAME.service"

echo "Service name: $SERVICE_NAME"
echo "Service file: $SERVICE_FILE"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  This script needs to be run as root to remove system service."
    echo "   Run with: sudo $0"
    exit 1
fi

# Check if service is installed
if ! systemctl list-unit-files | grep -q "$SERVICE_NAME"; then
    echo "❌ Service is not installed"
    exit 0
fi

# Stop the service if it's running
echo "Stopping service..."
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "Service is running, stopping it..."
    systemctl stop "$SERVICE_NAME"
    echo "✅ Service stopped"
else
    echo "Service is not running"
fi

# Disable the service
echo "Disabling service from auto-start..."
if systemctl disable "$SERVICE_NAME"; then
    echo "✅ Service disabled successfully"
else
    echo "⚠️  Service may not have been enabled"
fi

# Remove the service file
echo "Removing service configuration..."
if [ -f "$SERVICE_FILE" ]; then
    rm -f "$SERVICE_FILE"
    echo "✅ Service file removed"
else
    echo "⚠️  Service file not found"
fi

# Reload systemd daemon
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Verify removal
if systemctl list-unit-files | grep -q "$SERVICE_NAME"; then
    echo "⚠️  Service may still be registered with systemd"
else
    echo "✅ Service successfully removed from systemd"
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
echo "  sudo $PROJECT_ROOT/services/management/install_linux_service.sh"