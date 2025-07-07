#!/bin/bash
#
# Launchd Service Wrapper for KTRDR Host Services
#
# This script acts as a bridge between macOS launchd and the KTRDR service manager.
# It handles service startup, monitoring, and graceful shutdown.
#

set -e  # Exit on any error

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Setup logging
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') | LAUNCHD-WRAPPER | $1" | tee -a "$LOG_DIR/launchd-wrapper.log"
}

log "Starting KTRDR Host Services via launchd wrapper"
log "Project root: $PROJECT_ROOT"
log "Script directory: $SCRIPT_DIR"

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

# Function to check if we should run (not already running)
check_running() {
    if pgrep -f "service_manager.py daemon" > /dev/null; then
        log "Service manager already running, exiting"
        exit 0
    fi
}

# Main service loop
main() {
    log "Checking if service manager is already running..."
    check_running
    
    log "Changing to project directory: $PROJECT_ROOT"
    cd "$PROJECT_ROOT"
    
    # Start services using the service manager
    log "Starting KTRDR host services..."
    if $PYTHON_CMD services/management/service_manager.py start; then
        log "Services started successfully"
    else
        log "ERROR: Failed to start services"
        exit 1
    fi
    
    # Run in monitoring mode
    log "Entering monitoring mode..."
    exec $PYTHON_CMD services/management/service_manager.py daemon
}

# Check for dependencies
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

# Run dependency checks
check_dependencies

# Wait a moment for system to settle after boot
if [ "$KTRDR_SERVICE_AUTO_START" = "true" ]; then
    log "Auto-start mode detected, waiting 10 seconds for system to settle..."
    sleep 10
fi

# Start main service loop
main