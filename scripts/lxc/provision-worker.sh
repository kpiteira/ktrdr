#!/bin/bash
# Provision new KTRDR worker from LXC template
#
# This script creates a new worker LXC container from the base template,
# configures networking, and sets up environment variables for the worker.
#
# Usage:
#   ./provision-worker.sh WORKER_ID WORKER_IP [WORKER_TYPE]
#
# Parameters:
#   WORKER_ID    - Unique LXC container ID (e.g., 201, 202, 203)
#   WORKER_IP    - IP address for the worker (e.g., 192.168.1.201)
#   WORKER_TYPE  - Worker type: "backtesting" or "training" (default: "backtesting")
#
# Examples:
#   ./provision-worker.sh 201 192.168.1.201 backtesting
#   ./provision-worker.sh 202 192.168.1.202 training
#   ./provision-worker.sh 203 192.168.1.203  # Defaults to backtesting
#
# Requirements:
#   - Proxmox VE with pct command
#   - Base template (ID 999) created via create-template.sh
#   - Available IP address on network
#
# What this script does:
#   1. Validates parameters
#   2. Clones worker from template (ID 999)
#   3. Configures network settings
#   4. Starts the worker container
#   5. Creates .env file with configuration
#   6. Verifies worker is running

set -e  # Exit on error
set -u  # Exit on undefined variable
set -o pipefail  # Exit on pipe failure

# Configuration
TEMPLATE_ID=999
BACKEND_API_URL=${KTRDR_BACKEND_API:-"http://192.168.1.100:8000"}
NETWORK_GATEWAY=${KTRDR_GATEWAY:-"192.168.1.1"}
NETWORK_MASK=${KTRDR_NETMASK:-"24"}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Usage message
usage() {
    cat << EOF
Usage: $0 WORKER_ID WORKER_IP [WORKER_TYPE]

Provision a new KTRDR worker from template.

Parameters:
  WORKER_ID    - Unique LXC container ID (e.g., 201, 202, 203)
  WORKER_IP    - IP address for the worker (e.g., 192.168.1.201)
  WORKER_TYPE  - Worker type: "backtesting" or "training" (default: "backtesting")

Examples:
  $0 201 192.168.1.201 backtesting
  $0 202 192.168.1.202 training
  $0 203 192.168.1.203  # Defaults to backtesting

Worker Types:
  backtesting - Runs backtesting operations (port 5003)
  training    - Runs training operations (port 5004)
EOF
    exit 1
}

# Validate parameters
validate_parameters() {
    if [ -z "${WORKER_ID:-}" ]; then
        log_error "WORKER_ID is required"
        usage
    fi

    if [ -z "${WORKER_IP:-}" ]; then
        log_error "WORKER_IP is required"
        usage
    fi

    # Validate WORKER_ID is numeric
    if ! [[ "$WORKER_ID" =~ ^[0-9]+$ ]]; then
        log_error "WORKER_ID must be numeric"
        exit 1
    fi

    # Validate IP format (basic check)
    if ! [[ "$WORKER_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        log_error "WORKER_IP must be a valid IP address"
        exit 1
    fi

    # Validate worker type
    if [ "$WORKER_TYPE" != "backtesting" ] && [ "$WORKER_TYPE" != "training" ]; then
        log_error "WORKER_TYPE must be 'backtesting' or 'training'"
        usage
    fi
}

# Check if running on Proxmox
check_proxmox() {
    if ! command -v pct &> /dev/null; then
        log_error "Proxmox 'pct' command not found. This script must run on Proxmox VE."
        exit 1
    fi
    log_info "Proxmox environment detected"
}

# Check if template exists
check_template_exists() {
    if ! pct status "$TEMPLATE_ID" &> /dev/null; then
        log_error "Template $TEMPLATE_ID does not exist. Run create-template.sh first."
        exit 1
    fi
    log_info "Template $TEMPLATE_ID found"
}

# Check if worker already exists
check_worker_not_exists() {
    if pct status "$WORKER_ID" &> /dev/null; then
        log_error "Worker $WORKER_ID already exists. Choose a different ID or destroy existing worker."
        exit 1
    fi
    log_info "Worker ID $WORKER_ID is available"
}

# Clone worker from template
clone_worker() {
    log_step "Cloning worker $WORKER_ID from template $TEMPLATE_ID..."

    local hostname="ktrdr-${WORKER_TYPE}-${WORKER_ID}"

    pct clone "$TEMPLATE_ID" "$WORKER_ID" \
        --hostname "$hostname" \
        --description "KTRDR ${WORKER_TYPE} worker"

    if [ $? -ne 0 ]; then
        log_error "Failed to clone worker from template"
        exit 1
    fi

    log_info "Worker cloned successfully"
}

# Configure network
configure_network() {
    log_step "Configuring network for worker $WORKER_ID..."

    pct set "$WORKER_ID" \
        --net0 "name=eth0,bridge=vmbr0,ip=${WORKER_IP}/${NETWORK_MASK},gw=${NETWORK_GATEWAY}"

    if [ $? -ne 0 ]; then
        log_error "Failed to configure network"
        exit 1
    fi

    log_info "Network configured: ${WORKER_IP}/${NETWORK_MASK}"
}

# Start worker
start_worker() {
    log_step "Starting worker $WORKER_ID..."

    pct start "$WORKER_ID"

    if [ $? -ne 0 ]; then
        log_error "Failed to start worker"
        exit 1
    fi

    # Wait for worker to be ready
    log_info "Waiting for worker to be ready..."
    sleep 5

    # Wait for network to be up
    for i in {1..30}; do
        if pct exec "$WORKER_ID" -- ping -c 1 "$NETWORK_GATEWAY" &> /dev/null; then
            log_info "Worker is ready"
            return 0
        fi
        echo -n "."
        sleep 2
    done

    log_error "Worker failed to become ready"
    exit 1
}

# Create environment configuration
configure_environment() {
    log_step "Configuring environment for worker $WORKER_ID..."

    # Determine worker port based on type
    local worker_port
    if [ "$WORKER_TYPE" == "backtesting" ]; then
        worker_port=5003
    else
        worker_port=5004
    fi

    # Create .env file
    pct exec "$WORKER_ID" -- bash -c "
        mkdir -p /opt/ktrdr

        # Create .env file
        cat > /opt/ktrdr/.env << 'EOF'
# KTRDR Worker Configuration
# Generated by provision-worker.sh

# Backend API URL
KTRDR_API_URL=${BACKEND_API_URL}

# Worker endpoint URL (this worker's own URL)
WORKER_ENDPOINT_URL=http://${WORKER_IP}:${worker_port}

# Worker type (backtesting or training)
WORKER_TYPE=${WORKER_TYPE}

# Worker ID
WORKER_ID=${WORKER_TYPE}-worker-${WORKER_ID}

# Worker capabilities
WORKER_CAPABILITIES=cpu
EOF

        # Set ownership
        chown -R ktrdr:ktrdr /opt/ktrdr/.env
        chmod 600 /opt/ktrdr/.env
    "

    if [ $? -ne 0 ]; then
        log_error "Failed to configure environment"
        exit 1
    fi

    log_info "Environment configured"
}

# Verify worker
verify_worker() {
    log_step "Verifying worker $WORKER_ID..."

    # Check if worker is running
    local status=$(pct status "$WORKER_ID" 2>/dev/null | awk '{print $2}')
    if [ "$status" != "running" ]; then
        log_error "Worker is not running (status: $status)"
        return 1
    fi

    # Check if .env file exists
    if ! pct exec "$WORKER_ID" -- test -f /opt/ktrdr/.env; then
        log_error ".env file not found"
        return 1
    fi

    log_info "Worker verified successfully"
    return 0
}

# Display summary
display_summary() {
    echo ""
    log_info "=== Worker Provisioning Complete ==="
    log_info "Worker ID:   $WORKER_ID"
    log_info "Worker IP:   $WORKER_IP"
    log_info "Worker Type: $WORKER_TYPE"
    log_info "Hostname:    ktrdr-${WORKER_TYPE}-${WORKER_ID}"
    echo ""
    log_info "Next steps:"
    echo "  1. Deploy code:    ./scripts/deploy/deploy-code.sh \"$WORKER_ID\" main"
    echo "  2. Install service:"
    echo "     pct enter $WORKER_ID"
    echo "     cp /opt/ktrdr/scripts/deploy/systemd/ktrdr-${WORKER_TYPE}-worker.service /etc/systemd/system/ktrdr-worker.service"
    echo "     systemctl daemon-reload"
    echo "     systemctl enable ktrdr-worker"
    echo "     systemctl start ktrdr-worker"
    echo "  3. Verify health:"
    if [ "$WORKER_TYPE" == "backtesting" ]; then
        echo "     curl http://${WORKER_IP}:5003/health"
    else
        echo "     curl http://${WORKER_IP}:5004/health"
    fi
    echo ""
}

# Main execution
main() {
    # Parse parameters
    WORKER_ID=${1:-}
    WORKER_IP=${2:-}
    WORKER_TYPE=${3:-"backtesting"}  # Default to backtesting

    log_info "=== KTRDR Worker Provisioning ==="
    log_info "Worker ID:   ${WORKER_ID:-<not set>}"
    log_info "Worker IP:   ${WORKER_IP:-<not set>}"
    log_info "Worker Type: $WORKER_TYPE"
    echo ""

    validate_parameters
    check_proxmox
    check_template_exists
    check_worker_not_exists
    clone_worker
    configure_network
    start_worker
    configure_environment
    verify_worker

    display_summary
}

# Run main function
main "$@"
