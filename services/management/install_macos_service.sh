#!/bin/bash
#
# Install KTRDR Host Services as macOS launchd service
#
# This script installs the KTRDR host services to start automatically
# on macOS system boot using launchd.
#

set -e  # Exit on any error

echo "🍎 Installing KTRDR Host Services for macOS auto-startup"
echo "======================================================="

# Get current user and project paths
CURRENT_USER=$(whoami)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT_DIR="$PROJECT_ROOT/services/management"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"
SERVICE_LABEL="com.ktrdr.host-services"
PLIST_FILE="$LAUNCHD_DIR/$SERVICE_LABEL.plist"

echo "Current user: $CURRENT_USER"
echo "Project root: $PROJECT_ROOT"
echo "Launchd directory: $LAUNCHD_DIR"

# Ensure LaunchAgents directory exists
mkdir -p "$LAUNCHD_DIR"

# Check if service is already installed
if [ -f "$PLIST_FILE" ]; then
    echo "⚠️  Service already installed. Unloading existing service..."
    launchctl unload "$PLIST_FILE" 2>/dev/null || true
    rm -f "$PLIST_FILE"
fi

# Create logs directory
echo "Creating logs directory..."
mkdir -p "$PROJECT_ROOT/logs"

# Make scripts executable
echo "Setting script permissions..."
chmod +x "$SCRIPT_DIR/launchd/launchd_service_wrapper.sh"
chmod +x "$SCRIPT_DIR/service_manager.py"
chmod +x "$SCRIPT_DIR/start_all_services.sh"
chmod +x "$SCRIPT_DIR/stop_all_services.sh"

# Process the plist template
echo "Creating service configuration..."
sed -e "s|__PROJECT_ROOT__|$PROJECT_ROOT|g" \
    -e "s|__USER_NAME__|$CURRENT_USER|g" \
    "$SCRIPT_DIR/launchd/com.ktrdr.host-services.plist" > "$PLIST_FILE"

echo "Service configuration created: $PLIST_FILE"

# Validate the plist file
if plutil -lint "$PLIST_FILE" >/dev/null 2>&1; then
    echo "✅ Service configuration is valid"
else
    echo "❌ Service configuration is invalid"
    exit 1
fi

# Load the service
echo "Loading service with launchd..."
if launchctl load "$PLIST_FILE"; then
    echo "✅ Service loaded successfully"
else
    echo "❌ Failed to load service"
    exit 1
fi

# Check service status
sleep 2
if launchctl list | grep -q "$SERVICE_LABEL"; then
    echo "✅ Service is registered with launchd"
else
    echo "⚠️  Service may not be properly registered"
fi

echo ""
echo "🎉 KTRDR Host Services installed successfully!"
echo ""
echo "Service management commands:"
echo "  • Check status:    launchctl list | grep ktrdr"
echo "  • View logs:       tail -f $PROJECT_ROOT/logs/ktrdr-host-services.out.log"
echo "  • Start manually:  launchctl start $SERVICE_LABEL"
echo "  • Stop manually:   launchctl stop $SERVICE_LABEL"
echo "  • Uninstall:       $SCRIPT_DIR/uninstall_macos_service.sh"
echo ""
echo "The services will start automatically on next system boot."
echo "To start them now, either reboot or run:"
echo "  launchctl start $SERVICE_LABEL"