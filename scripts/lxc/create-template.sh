#!/bin/bash
# Create base LXC template for KTRDR workers
#
# This script creates a reusable LXC template containing:
# - Ubuntu 22.04 LTS base system
# - Python 3.13
# - uv package manager
# - System dependencies
# - Base directory structure (/opt/ktrdr)
#
# The template does NOT contain:
# - KTRDR code (deployed separately for CD)
# - Configuration files (environment-specific)
# - Environment variables
# - Models or data
#
# Usage:
#   ./create-template.sh
#
# Requirements:
#   - Proxmox VE 8.x
#   - Root access (or sudo)
#   - Network connectivity for package downloads
#
# Output:
#   - LXC template: /var/lib/vz/template/cache/ktrdr-worker-base-v1.tar.zst

set -e  # Exit on error
set -u  # Exit on undefined variable
set -o pipefail  # Exit on pipe failure

# Configuration
TEMPLATE_ID=999
TEMPLATE_NAME="ktrdr-worker-base-v1"
UBUNTU_TEMPLATE="ubuntu-22.04-standard_22.04-1_amd64.tar.zst"
MEMORY_MB=2048
CORES=2
DISK_GB=8

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Check if running on Proxmox
check_proxmox() {
    if ! command -v pct &> /dev/null; then
        log_error "Proxmox 'pct' command not found. This script must run on Proxmox VE."
        exit 1
    fi
    log_info "Proxmox environment detected"
}

# Check if template container already exists
check_existing_container() {
    if pct status "$TEMPLATE_ID" &> /dev/null; then
        log_warn "Container $TEMPLATE_ID already exists. Destroying it..."
        pct stop "$TEMPLATE_ID" 2>/dev/null || true
        pct destroy "$TEMPLATE_ID"
        log_info "Existing container destroyed"
    fi
}

# Create LXC container
create_container() {
    log_info "Creating LXC container $TEMPLATE_ID..."

    pct create "$TEMPLATE_ID" "local:vztmpl/$UBUNTU_TEMPLATE" \
        --hostname ktrdr-template \
        --memory "$MEMORY_MB" \
        --cores "$CORES" \
        --rootfs "local-lvm:$DISK_GB" \
        --net0 name=eth0,bridge=vmbr0,ip=dhcp

    log_info "Container created successfully"
}

# Start container
start_container() {
    log_info "Starting container..."
    pct start "$TEMPLATE_ID"

    # Wait for container to be fully started
    log_info "Waiting for container to be ready..."
    sleep 5

    # Wait for network to be up
    for i in {1..30}; do
        if pct exec "$TEMPLATE_ID" -- ping -c 1 8.8.8.8 &> /dev/null; then
            log_info "Container is ready"
            return 0
        fi
        echo -n "."
        sleep 2
    done

    log_error "Container failed to become ready"
    exit 1
}

# Install system dependencies
install_system_dependencies() {
    log_info "Installing system dependencies..."

    pct exec "$TEMPLATE_ID" -- bash -c "
        apt-get update
        apt-get install -y \
            python3.13 \
            python3.13-venv \
            python3.13-dev \
            curl \
            git \
            build-essential \
            wget \
            ca-certificates
    "

    log_info "System dependencies installed"
}

# Install uv package manager
install_uv() {
    log_info "Installing uv package manager..."

    pct exec "$TEMPLATE_ID" -- bash -c "
        curl -LsSf https://astral.sh/uv/install.sh | sh

        # Add uv to PATH for all users
        echo 'export PATH=\"\$HOME/.cargo/bin:\$PATH\"' >> /etc/profile.d/uv.sh
        chmod +x /etc/profile.d/uv.sh
    "

    log_info "uv package manager installed"
}

# Create base directory structure
create_directory_structure() {
    log_info "Creating base directory structure..."

    pct exec "$TEMPLATE_ID" -- bash -c "
        mkdir -p /opt/ktrdr
        mkdir -p /opt/ktrdr/logs
        mkdir -p /opt/ktrdr/data
        mkdir -p /opt/ktrdr/models

        # Create ktrdr user for running services
        useradd -r -m -d /opt/ktrdr -s /bin/bash ktrdr || true
        chown -R ktrdr:ktrdr /opt/ktrdr
    "

    log_info "Directory structure created"
}

# Clean up container before template creation
cleanup_container() {
    log_info "Cleaning up container..."

    pct exec "$TEMPLATE_ID" -- bash -c "
        # Clean apt cache
        apt-get clean
        rm -rf /var/lib/apt/lists/*

        # Clean temporary files
        rm -rf /tmp/*
        rm -rf /var/tmp/*

        # Clean logs
        find /var/log -type f -exec truncate -s 0 {} \\;

        # Clean bash history
        rm -f /root/.bash_history
        history -c
    "

    log_info "Container cleaned"
}

# Stop container
stop_container() {
    log_info "Stopping container..."
    pct stop "$TEMPLATE_ID"
    log_info "Container stopped"
}

# Convert container to template
create_template_archive() {
    log_info "Converting container to template..."

    # Create template using vzdump
    vzdump "$TEMPLATE_ID" \
        --mode stop \
        --dumpdir /var/lib/vz/template/cache/

    # Find the created dump file
    DUMP_FILE=$(ls -t /var/lib/vz/template/cache/vzdump-lxc-${TEMPLATE_ID}-*.tar.zst | head -1)

    if [ -z "$DUMP_FILE" ]; then
        log_error "Failed to find created dump file"
        exit 1
    fi

    # Rename to standard template name
    mv "$DUMP_FILE" "/var/lib/vz/template/cache/${TEMPLATE_NAME}.tar.zst"

    log_info "Template created: /var/lib/vz/template/cache/${TEMPLATE_NAME}.tar.zst"
}

# Destroy source container
destroy_source_container() {
    log_info "Destroying source container..."
    pct destroy "$TEMPLATE_ID"
    log_info "Source container destroyed"
}

# Main execution
main() {
    log_info "=== KTRDR LXC Template Creation ==="
    log_info "Creating template: $TEMPLATE_NAME"
    log_info ""

    check_proxmox
    check_existing_container
    create_container
    start_container
    install_system_dependencies
    install_uv
    create_directory_structure
    cleanup_container
    stop_container
    create_template_archive
    destroy_source_container

    log_info ""
    log_info "=== Template Creation Complete ==="
    log_info "Template: /var/lib/vz/template/cache/${TEMPLATE_NAME}.tar.zst"
    log_info ""
    log_info "To create a worker from this template:"
    log_info "  pct create 201 local:vztmpl/${TEMPLATE_NAME}.tar.zst \\"
    log_info "    --hostname ktrdr-worker-1 \\"
    log_info "    --memory 4096 \\"
    log_info "    --cores 4 \\"
    log_info "    --rootfs local-lvm:16 \\"
    log_info "    --net0 name=eth0,bridge=vmbr0,ip=192.168.1.201/24,gw=192.168.1.1"
}

# Run main function
main
