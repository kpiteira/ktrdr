#!/bin/bash

# Real E2E Test Runner Script
# 
# This script sets up and runs real end-to-end tests that require
# actual IB Gateway connection and running backend services.

set -e  # Exit on any error

# Configuration
IB_HOST=${IB_HOST:-"127.0.0.1"}
IB_PORT=${IB_PORT:-"4002"}
API_BASE_URL=${API_BASE_URL:-"http://localhost:8000"}
BACKEND_CONTAINER=${BACKEND_CONTAINER:-"ktrdr-backend"}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  KTRDR Real E2E Test Runner${NC}"
    echo -e "${BLUE}================================${NC}"
    echo
}

print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

check_ib_gateway() {
    echo "Checking IB Gateway connection..."
    
    # Check if port is open
    if ! nc -z "${IB_HOST}" "${IB_PORT}" 2>/dev/null; then
        print_error "IB Gateway not accessible at ${IB_HOST}:${IB_PORT}"
        echo
        print_error "🚨 CRITICAL: No IB Gateway/TWS running!"
        echo
        echo "Required setup for real E2E tests:"
        echo "  1. Download and install IB Gateway or TWS from Interactive Brokers"
        echo "  2. Configure API settings:"
        echo "     - Enable API connections"
        echo "     - Set API port to ${IB_PORT}"
        echo "     - Allow localhost connections"
        echo "  3. Start IB Gateway/TWS and log in"
        echo "  4. Ensure paper trading account is active"
        echo
        echo "Alternative: Use demo IB Gateway container:"
        echo "  docker run -d -p 4002:4002 --name ib-gateway ib-gateway:demo"
        echo
        return 1
    fi
    
    print_status "IB Gateway port ${IB_HOST}:${IB_PORT} is accessible"
    
    # Test actual IB connection via backend API
    echo "Testing IB connection functionality..."
    local ib_status=$(curl -s -m 10 "${API_BASE_URL}/api/v1/ib/status" 2>/dev/null || echo "")
    
    if echo "$ib_status" | grep -q '"success".*true'; then
        print_status "IB status endpoint responds correctly"
        
        # Critical: Test actual IB operation (symbol discovery)
        echo "Testing real IB operation (symbol discovery)..."
        local discovery_test=$(curl -s -m 15 "${API_BASE_URL}/api/v1/ib/symbols/discover" \
            -X POST \
            -H "Content-Type: application/json" \
            -d '{"symbol": "AAPL", "force_refresh": true}' 2>/dev/null || echo "TIMEOUT")
        
        if echo "$discovery_test" | grep -q '"success".*true'; then
            print_status "Real IB operations working correctly"
            return 0
        elif [ "$discovery_test" = "TIMEOUT" ]; then
            print_error "🚨 CRITICAL: IB operations timeout - connection appears fake!"
            echo
            print_error "Symptoms detected:"
            echo "  - Backend logs show 'Connected' to IB Gateway"
            echo "  - IB Gateway shows no active connections"
            echo "  - API calls timeout (30+ seconds)"
            echo
            print_error "Possible causes:"
            echo "  1. Docker host.docker.internal resolution issues"
            echo "  2. Port forwarding not working correctly"
            echo "  3. IB Gateway API not properly enabled"
            echo "  4. Firewall blocking actual data transmission"
            echo
            print_warning "This is a 'silent connection' - appears connected but can't perform operations"
            echo "Real E2E tests REQUIRE functional IB operations, not just TCP connections"
            return 1
        else
            print_error "IB symbol discovery failed"
            echo "Response: $discovery_test"
            return 1
        fi
    else
        print_error "IB connection test failed"
        echo "Response: $ib_status"
        echo
        print_warning "IB Gateway may be running but not properly configured for API access"
        echo "Check IB Gateway settings:"
        echo "  - API > Settings > Enable ActiveX and Socket Clients"
        echo "  - API > Settings > Socket port: ${IB_PORT}"
        echo "  - API > Settings > Master API client ID: 0"
        echo "  - Trusted IPs: 127.0.0.1"
        return 1
    fi
}

check_backend_api() {
    echo "Checking backend API..."
    
    if curl -s "${API_BASE_URL}/api/v1/system/status" >/dev/null 2>&1; then
        print_status "Backend API is accessible at ${API_BASE_URL}"
        return 0
    else
        print_error "Backend API not accessible at ${API_BASE_URL}"
        print_warning "Please ensure backend container/service is running"
        return 1
    fi
}

check_ib_integration() {
    echo "Checking IB integration..."
    
    local response=$(curl -s "${API_BASE_URL}/api/v1/ib/status" 2>/dev/null || echo "")
    
    if echo "$response" | grep -q '"success".*true'; then
        print_status "IB integration is working"
        return 0
    else
        print_warning "IB integration may have issues"
        print_warning "Response: $response"
        return 1
    fi
}

run_test_category() {
    local category=$1
    local description=$2
    
    echo
    echo -e "${BLUE}Running ${description}...${NC}"
    echo "----------------------------------------"
    
    if uv run pytest "tests/e2e_real/test_real_${category}.py" \
        -v --real-ib \
        --ib-host="${IB_HOST}" \
        --ib-port="${IB_PORT}" \
        --api-base-url="${API_BASE_URL}" \
        --tb=short; then
        print_status "${description} passed"
        return 0
    else
        print_error "${description} failed"
        return 1
    fi
}

show_help() {
    echo "Usage: $0 [OPTIONS] [TEST_CATEGORY]"
    echo
    echo "Options:"
    echo "  --ib-host HOST        IB Gateway host (default: 127.0.0.1)"
    echo "  --ib-port PORT        IB Gateway port (default: 4002)"
    echo "  --api-url URL         Backend API URL (default: http://localhost:8000)"
    echo "  --skip-checks         Skip pre-flight checks"
    echo "  --help               Show this help message"
    echo
    echo "Test Categories:"
    echo "  cli                  CLI commands with real IB operations"
    echo "  api                  API endpoints with real IB data flows"
    echo "  pipeline             Complete data pipeline workflows"
    echo "  error_scenarios      Error conditions and recovery"
    echo "  all                  All real E2E tests (default)"
    echo
    echo "Examples:"
    echo "  $0                           # Run all real E2E tests"
    echo "  $0 cli                       # Run only CLI tests"
    echo "  $0 --ib-host=192.168.1.100   # Use remote IB Gateway"
    echo "  $0 --skip-checks api         # Skip checks, run API tests"
}

main() {
    local test_category="all"
    local skip_checks=false
    local failed_checks=0
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --ib-host)
                IB_HOST="$2"
                shift 2
                ;;
            --ib-port)
                IB_PORT="$2"
                shift 2
                ;;
            --api-url)
                API_BASE_URL="$2"
                shift 2
                ;;
            --skip-checks)
                skip_checks=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            cli|api|pipeline|error_scenarios|all)
                test_category="$1"
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    print_header
    
    echo "Configuration:"
    echo "  IB Gateway: ${IB_HOST}:${IB_PORT}"
    echo "  API URL: ${API_BASE_URL}"
    echo "  Test Category: ${test_category}"
    echo
    
    # Pre-flight checks
    if [[ "$skip_checks" != true ]]; then
        echo "Running pre-flight checks..."
        echo
        
        if ! check_ib_gateway; then
            ((failed_checks++))
        fi
        
        if ! check_backend_api; then
            ((failed_checks++))
        fi
        
        if ! check_ib_integration; then
            ((failed_checks++))
        fi
        
        echo
        
        if [[ $failed_checks -gt 0 ]]; then
            print_error "$failed_checks pre-flight check(s) failed"
            print_warning "Tests may fail or be skipped"
            echo
            read -p "Continue anyway? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                print_error "Aborted by user"
                exit 1
            fi
        else
            print_status "All pre-flight checks passed"
        fi
    fi
    
    # Run tests
    local total_categories=0
    local passed_categories=0
    
    case $test_category in
        cli)
            ((total_categories++))
            if run_test_category "cli" "CLI Commands with Real IB"; then
                ((passed_categories++))
            fi
            ;;
        api)
            ((total_categories++))
            if run_test_category "api" "API Endpoints with Real IB"; then
                ((passed_categories++))
            fi
            ;;
        pipeline)
            ((total_categories++))
            if run_test_category "pipeline" "Complete Data Pipeline Tests"; then
                ((passed_categories++))
            fi
            ;;
        error_scenarios)
            ((total_categories++))
            if run_test_category "error_scenarios" "Error Scenarios and Recovery"; then
                ((passed_categories++))
            fi
            ;;
        all)
            # Run all categories
            categories=("cli" "api" "pipeline" "error_scenarios")
            descriptions=(
                "CLI Commands with Real IB"
                "API Endpoints with Real IB" 
                "Complete Data Pipeline Tests"
                "Error Scenarios and Recovery"
            )
            
            for i in "${!categories[@]}"; do
                ((total_categories++))
                if run_test_category "${categories[$i]}" "${descriptions[$i]}"; then
                    ((passed_categories++))
                fi
            done
            ;;
    esac
    
    # Summary
    echo
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  Test Results Summary${NC}"
    echo -e "${BLUE}================================${NC}"
    echo
    
    if [[ $passed_categories -eq $total_categories ]]; then
        print_status "All $total_categories test categories passed!"
        echo
        print_status "Real E2E testing completed successfully"
        print_status "System is working correctly with real IB connections"
        exit 0
    else
        print_error "$((total_categories - passed_categories)) of $total_categories test categories failed"
        echo
        print_warning "Some real E2E tests failed - check logs above for details"
        exit 1
    fi
}

# Run main function
main "$@"