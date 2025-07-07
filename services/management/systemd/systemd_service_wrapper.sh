#!/bin/bash
#
# Systemd Service Wrapper for KTRDR Host Services
#
# This script acts as a bridge between systemd and the KTRDR service manager.
# It handles service startup, monitoring, and graceful shutdown for Linux systems.
#

set -e  # Exit on any error

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Setup logging function for systemd journal
log() {
    echo "SYSTEMD-WRAPPER: $1"
    logger -t ktrdr-host-services "SYSTEMD-WRAPPER: $1"
}

log "Starting KTRDR Host Services via systemd wrapper"
log "Project root: $PROJECT_ROOT"

# Setup environment
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
export KTRDR_SERVICE_AUTO_START="true"

# Check if we have uv available
if command -v uv >/dev/null 2>&1; then
    PYTHON_CMD="uv run python"
    log "Using uv for Python execution"
else
    PYTHON_CMD="python3"
    log "uv not found, using system python3"
fi

# Function to handle shutdown signals
shutdown_handler() {
    log "Received shutdown signal, stopping services..."
    cd "$PROJECT_ROOT"
    $PYTHON_CMD services/management/service_manager.py stop
    log "Services stopped, exiting"
    exit 0
}

# Setup signal handlers
trap shutdown_handler SIGTERM SIGINT

# Function to check dependencies
check_dependencies() {
    # Check if Python is available
    if ! command -v python3 >/dev/null 2>&1 && ! command -v uv >/dev/null 2>&1; then
        log "ERROR: Neither python3 nor uv found in PATH"
        exit 1
    fi
    
    # Check if project directory exists
    if [ ! -d "$PROJECT_ROOT" ]; then
        log "ERROR: Project directory not found: $PROJECT_ROOT"
        exit 1
    fi
    
    # Check if service manager exists
    if [ ! -f "$PROJECT_ROOT/services/management/service_manager.py" ]; then
        log "ERROR: Service manager not found: $PROJECT_ROOT/services/management/service_manager.py"
        exit 1
    fi
    
    log "Dependencies check passed"
}

# Main service function
main() {
    log "Checking dependencies..."
    check_dependencies
    
    log "Changing to project directory: $PROJECT_ROOT"
    cd "$PROJECT_ROOT"
    
    # Create logs directory
    mkdir -p "$PROJECT_ROOT/logs"
    
    # Wait a moment for system to settle
    if [ "$KTRDR_SERVICE_AUTO_START" = "true" ]; then
        log "Auto-start mode detected, waiting 5 seconds for system to settle..."
        sleep 5
    fi
    
    # Start services using the service manager
    log "Starting KTRDR host services..."
    if $PYTHON_CMD services/management/service_manager.py start; then
        log "Services started successfully"
    else
        log "ERROR: Failed to start services"
        exit 1
    fi
    
    # Run in monitoring mode (this will block and monitor services)
    log "Entering monitoring mode..."
    exec $PYTHON_CMD services/management/service_manager.py daemon
}

# Run main function
main