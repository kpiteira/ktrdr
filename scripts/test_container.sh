#!/bin/bash
#
# Container E2E Test Script
#
# This script provides a simple interface to run comprehensive container-based
# end-to-end tests for the KTRDR system.
#

set -e

# Configuration
CONTAINER_NAME="${CONTAINER_NAME:-ktrdr-backend}"
API_BASE_URL="${API_BASE_URL:-http://localhost:8000/api/v1}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependencies() {
    log_info "Checking dependencies..."
    
    # Check if docker is available
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    # Check if uv is available
    if ! command -v uv &> /dev/null; then
        log_error "uv is not installed or not in PATH"
        exit 1
    fi
    
    # Check if python is available
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed or not in PATH"
        exit 1
    fi
    
    log_success "All dependencies available"
}

check_container_status() {
    log_info "Checking container status..."
    
    # Check if container exists
    if ! docker ps -a --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        log_error "Container '$CONTAINER_NAME' does not exist"
        log_info "Start the container first with: ./docker_dev.sh start"
        exit 1
    fi
    
    # Check if container is running
    if ! docker ps --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        log_error "Container '$CONTAINER_NAME' is not running"
        log_info "Start the container with: ./docker_dev.sh start"
        exit 1
    fi
    
    log_success "Container '$CONTAINER_NAME' is running"
}

wait_for_api() {
    log_info "Waiting for API to be ready at $API_BASE_URL..."
    
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$API_BASE_URL/health" > /dev/null 2>&1; then
            log_success "API is ready"
            return 0
        fi
        
        log_info "Attempt $attempt/$max_attempts - API not ready yet, waiting..."
        sleep 2
        ((attempt++))
    done
    
    log_error "API did not become ready within expected time"
    log_info "Check container logs with: docker logs $CONTAINER_NAME"
    return 1
}

run_quick_tests() {
    log_info "Running quick smoke tests..."
    
    cd "$PROJECT_ROOT"
    
    # Run basic API tests
    log_info "Testing API endpoints..."
    uv run pytest tests/e2e/test_container_api_endpoints.py::TestContainerAPIHealth::test_api_health_endpoint \
        --run-container-e2e --api-base-url="$API_BASE_URL" -v
    
    # Run basic CLI tests
    log_info "Testing CLI commands..."
    uv run pytest tests/e2e/test_container_cli_commands.py::TestContainerCLIBasics::test_cli_help_command \
        --run-container-cli --container-name="$CONTAINER_NAME" -v
    
    log_success "Quick tests completed"
}

run_full_tests() {
    log_info "Running comprehensive E2E test suite..."
    
    cd "$PROJECT_ROOT"
    
    # Run the full test suite using the Python runner
    python3 scripts/run_container_e2e_tests.py \
        --container-name="$CONTAINER_NAME" \
        --api-base-url="$API_BASE_URL" \
        --output-json="test_results.json"
    
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        log_success "All E2E tests passed!"
    else
        log_error "Some E2E tests failed"
        log_info "Check test_results.json for detailed results"
    fi
    
    return $exit_code
}

run_api_tests_only() {
    log_info "Running API endpoint tests only..."
    
    cd "$PROJECT_ROOT"
    
    uv run pytest tests/e2e/test_container_api_endpoints.py \
        --run-container-e2e --api-base-url="$API_BASE_URL" -v
}

run_cli_tests_only() {
    log_info "Running CLI functionality tests only..."
    
    cd "$PROJECT_ROOT"
    
    uv run pytest tests/e2e/test_container_cli_commands.py \
        --run-container-cli --container-name="$CONTAINER_NAME" -v
}

show_help() {
    cat << EOF
Container E2E Test Script

Usage: $0 [COMMAND]

Commands:
    quick       Run quick smoke tests (default)
    full        Run comprehensive E2E test suite
    api         Run API endpoint tests only
    cli         Run CLI functionality tests only
    help        Show this help message

Environment Variables:
    CONTAINER_NAME    Name of the container to test (default: ktrdr-backend)
    API_BASE_URL      Base URL for API testing (default: http://localhost:8000)

Examples:
    $0                          # Run quick tests
    $0 quick                    # Run quick tests  
    $0 full                     # Run full test suite
    $0 api                      # Test API endpoints only
    $0 cli                      # Test CLI commands only
    
    CONTAINER_NAME=my-backend $0 full    # Test custom container

Prerequisites:
    - Docker container must be running
    - API must be accessible at the specified URL
    - uv and Python 3 must be installed

EOF
}

# Main script logic
main() {
    local command="${1:-quick}"
    
    case "$command" in
        "quick")
            check_dependencies
            check_container_status
            wait_for_api
            run_quick_tests
            ;;
        "full")
            check_dependencies
            check_container_status
            wait_for_api
            run_full_tests
            ;;
        "api")
            check_dependencies
            check_container_status
            wait_for_api
            run_api_tests_only
            ;;
        "cli")
            check_dependencies
            check_container_status
            run_cli_tests_only
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            log_error "Unknown command: $command"
            echo
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"