#!/bin/bash
#
# Install KTRDR Host Services as Linux systemd service
#
# This script installs the KTRDR host services to start automatically
# on Linux system boot using systemd.
#

set -e  # Exit on any error

echo "🐧 Installing KTRDR Host Services for Linux auto-startup"
echo "======================================================="

# Check if we're on a systemd system
if ! command -v systemctl >/dev/null 2>&1; then
    echo "❌ systemctl not found. This script requires systemd."
    exit 1
fi

# Get current user and project paths
CURRENT_USER=$(whoami)
CURRENT_GROUP=$(id -gn)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT_DIR="$PROJECT_ROOT/services/management"
SERVICE_NAME="ktrdr-host-services"
SYSTEMD_DIR="/etc/systemd/system"
SERVICE_FILE="$SYSTEMD_DIR/$SERVICE_NAME.service"

echo "Current user: $CURRENT_USER"
echo "Current group: $CURRENT_GROUP"
echo "Project root: $PROJECT_ROOT"
echo "Systemd directory: $SYSTEMD_DIR"

# Check if running as root for system service installation
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  This script needs to be run as root to install system service."
    echo "   Run with: sudo $0"
    echo ""
    echo "   Alternatively, you can install as user service by running:"
    echo "   $SCRIPT_DIR/install_linux_user_service.sh"
    exit 1
fi

# Check if service is already installed
if systemctl list-unit-files | grep -q "$SERVICE_NAME"; then
    echo "⚠️  Service already installed. Stopping and disabling existing service..."
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true
fi

# Create logs directory with appropriate permissions
echo "Creating logs directory..."
mkdir -p "$PROJECT_ROOT/logs"
chown "$CURRENT_USER:$CURRENT_GROUP" "$PROJECT_ROOT/logs"

# Make scripts executable
echo "Setting script permissions..."
chmod +x "$SCRIPT_DIR/systemd/systemd_service_wrapper.sh"
chmod +x "$SCRIPT_DIR/service_manager.py"
chmod +x "$SCRIPT_DIR/start_all_services.sh"
chmod +x "$SCRIPT_DIR/stop_all_services.sh"

# Process the service template
echo "Creating service configuration..."
sed -e "s|__PROJECT_ROOT__|$PROJECT_ROOT|g" \
    -e "s|__USER_NAME__|$CURRENT_USER|g" \
    -e "s|__USER_GROUP__|$CURRENT_GROUP|g" \
    "$SCRIPT_DIR/systemd/ktrdr-host-services.service" > "$SERVICE_FILE"

echo "Service configuration created: $SERVICE_FILE"

# Reload systemd daemon
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Enable the service
echo "Enabling service for auto-start..."
if systemctl enable "$SERVICE_NAME"; then
    echo "✅ Service enabled successfully"
else
    echo "❌ Failed to enable service"
    exit 1
fi

# Check service status
if systemctl is-enabled "$SERVICE_NAME" >/dev/null 2>&1; then
    echo "✅ Service is enabled for auto-start"
else
    echo "⚠️  Service may not be properly enabled"
fi

echo ""
echo "🎉 KTRDR Host Services installed successfully!"
echo ""
echo "Service management commands:"
echo "  • Check status:    sudo systemctl status $SERVICE_NAME"
echo "  • View logs:       sudo journalctl -u $SERVICE_NAME -f"
echo "  • Start manually:  sudo systemctl start $SERVICE_NAME"
echo "  • Stop manually:   sudo systemctl stop $SERVICE_NAME"
echo "  • Restart:         sudo systemctl restart $SERVICE_NAME"
echo "  • Uninstall:       $SCRIPT_DIR/uninstall_linux_service.sh"
echo ""
echo "The services will start automatically on next system boot."
echo "To start them now, either reboot or run:"
echo "  sudo systemctl start $SERVICE_NAME"