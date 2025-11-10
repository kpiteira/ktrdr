#!/bin/bash
# Deploy KTRDR code to worker LXC containers
#
# This script deploys KTRDR application code to one or more worker containers.
# It handles git clone/update, dependency installation, and service restart.
#
# Usage:
#   ./deploy-code.sh [WORKER_IDS] [GIT_REF]
#
# Parameters:
#   WORKER_IDS - Space-separated list of LXC container IDs (default: "201 202 203")
#   GIT_REF    - Git branch/tag/commit to deploy (default: "main")
#
# Examples:
#   ./deploy-code.sh "201"              # Deploy main to worker 201
#   ./deploy-code.sh "201 202" develop  # Deploy develop branch to workers 201, 202
#   ./deploy-code.sh "" v1.2.3          # Deploy tag v1.2.3 to default workers
#
# Requirements:
#   - Proxmox VE with pct command
#   - Workers created from ktrdr-worker-base template
#   - Git repository URL configured
#   - Network connectivity to git repository

set -e  # Exit on error
set -u  # Exit on undefined variable
set -o pipefail  # Exit on pipe failure

# Configuration
WORKER_IDS=${1:-"201 202 203"}  # Default to workers 201-203
GIT_REF=${2:-"main"}             # Default to main branch
GIT_REPO_URL=${KTRDR_GIT_REPO:-"https://github.com/your-org/ktrdr.git"}

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

# Check if running on Proxmox
check_proxmox() {
    if ! command -v pct &> /dev/null; then
        log_error "Proxmox 'pct' command not found. This script must run on Proxmox VE."
        exit 1
    fi
}

# Check if worker exists
check_worker_exists() {
    local worker_id=$1
    if ! pct status "$worker_id" &> /dev/null; then
        log_error "Worker $worker_id does not exist"
        return 1
    fi
    return 0
}

# Check if worker is running
ensure_worker_running() {
    local worker_id=$1
    local status=$(pct status "$worker_id" 2>/dev/null | awk '{print $2}')

    if [ "$status" != "running" ]; then
        log_warn "Worker $worker_id is not running. Starting..."
        pct start "$worker_id"
        sleep 3
    fi
}

# Clone or update git repository
deploy_code() {
    local worker_id=$1

    log_step "Deploying code to worker $worker_id..."

    # Clone or update repository
    log_info "Updating git repository to $GIT_REF..."
    pct exec "$worker_id" -- bash -c "
        cd /opt/ktrdr

        if [ -d .git ]; then
            # Repository exists - update it
            echo 'Repository exists, updating...'
            git fetch origin
            git checkout $GIT_REF
            git pull origin $GIT_REF
        else
            # Repository doesn't exist - clone it
            echo 'Repository not found, cloning...'
            git clone $GIT_REPO_URL .
            git checkout $GIT_REF
        fi

        # Set ownership
        chown -R ktrdr:ktrdr /opt/ktrdr
    "

    if [ $? -ne 0 ]; then
        log_error "Failed to deploy code to worker $worker_id"
        return 1
    fi

    log_info "Code deployed successfully"
    return 0
}

# Install dependencies
install_dependencies() {
    local worker_id=$1

    log_step "Installing dependencies on worker $worker_id..."

    pct exec "$worker_id" -- bash -c "
        cd /opt/ktrdr
        su - ktrdr -c 'cd /opt/ktrdr && uv sync'
    "

    if [ $? -ne 0 ]; then
        log_error "Failed to install dependencies on worker $worker_id"
        return 1
    fi

    log_info "Dependencies installed successfully"
    return 0
}

# Restart worker service
restart_service() {
    local worker_id=$1

    log_step "Restarting worker service on worker $worker_id..."

    # Try to restart the service (may not exist on first deployment)
    pct exec "$worker_id" -- bash -c "
        if systemctl is-active --quiet ktrdr-worker; then
            systemctl restart ktrdr-worker
            echo 'Service restarted'
        else
            echo 'Service not running (this is OK for first deployment)'
        fi
    "

    log_info "Service restart complete"
    return 0
}

# Verify deployment
verify_deployment() {
    local worker_id=$1

    log_step "Verifying deployment on worker $worker_id..."

    # Check if code exists
    pct exec "$worker_id" -- bash -c "
        test -f /opt/ktrdr/pyproject.toml && echo 'OK: pyproject.toml found'
    " > /dev/null 2>&1

    if [ $? -ne 0 ]; then
        log_warn "Deployment verification failed for worker $worker_id"
        return 1
    fi

    log_info "Deployment verified successfully"
    return 0
}

# Deploy to a single worker
deploy_to_worker() {
    local worker_id=$1
    local failed=0

    echo ""
    log_info "=== Deploying to Worker $worker_id ==="

    # Check worker exists
    if ! check_worker_exists "$worker_id"; then
        return 1
    fi

    # Ensure worker is running
    ensure_worker_running "$worker_id"

    # Deploy code
    if ! deploy_code "$worker_id"; then
        failed=1
    fi

    # Install dependencies
    if [ $failed -eq 0 ]; then
        if ! install_dependencies "$worker_id"; then
            failed=1
        fi
    fi

    # Restart service
    if [ $failed -eq 0 ]; then
        if ! restart_service "$worker_id"; then
            log_warn "Service restart failed (may not be installed yet)"
        fi
    fi

    # Verify deployment
    if [ $failed -eq 0 ]; then
        if ! verify_deployment "$worker_id"; then
            failed=1
        fi
    fi

    if [ $failed -eq 0 ]; then
        log_info "✅ Worker $worker_id deployed successfully"
        return 0
    else
        log_error "❌ Worker $worker_id deployment failed"
        return 1
    fi
}

# Main execution
main() {
    log_info "=== KTRDR Code Deployment ==="
    log_info "Workers: $WORKER_IDS"
    log_info "Git ref: $GIT_REF"
    log_info "Git repo: $GIT_REPO_URL"
    echo ""

    check_proxmox

    local total_workers=0
    local successful_workers=0
    local failed_workers=0

    # Deploy to each worker
    for worker_id in $WORKER_IDS; do
        total_workers=$((total_workers + 1))

        if deploy_to_worker "$worker_id"; then
            successful_workers=$((successful_workers + 1))
        else
            failed_workers=$((failed_workers + 1))
        fi
    done

    # Summary
    echo ""
    log_info "=== Deployment Summary ==="
    log_info "Total workers: $total_workers"
    log_info "Successful: $successful_workers"
    log_info "Failed: $failed_workers"
    echo ""

    if [ $failed_workers -gt 0 ]; then
        log_error "Deployment completed with failures"
        exit 1
    else
        log_info "✅ All deployments successful!"
        exit 0
    fi
}

# Run main function
main
