#!/bin/bash
# Test script for Training Host Service

# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SERVICE_DIR="$DIR/.."

echo "🧪 Training Host Service Test Suite"
echo "===================================="

# Set Python path
export PYTHONPATH="$SERVICE_DIR/..:$PYTHONPATH"

# Function to check if service is running
check_service_health() {
    local max_attempts=30
    local attempt=1
    
    echo "⏳ Waiting for service to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:5002/health >/dev/null 2>&1; then
            echo "✅ Service is ready"
            return 0
        fi
        
        echo "   Attempt $attempt/$max_attempts - waiting for service..."
        sleep 2
        ((attempt++))
    done
    
    echo "❌ Service failed to become ready within 60 seconds"
    return 1
}

# Function to run unit tests
run_unit_tests() {
    echo ""
    echo "🔬 Running Unit Tests"
    echo "--------------------"
    
    cd "$SERVICE_DIR"
    python -m pytest tests/unit/ -v --tb=short
    
    if [ $? -eq 0 ]; then
        echo "✅ Unit tests passed"
        return 0
    else
        echo "❌ Unit tests failed"
        return 1
    fi
}

# Function to start service for integration tests
start_service() {
    echo ""
    echo "🚀 Starting Training Host Service for Integration Tests"
    echo "------------------------------------------------------"
    
    cd "$SERVICE_DIR"
    
    # Start service in background
    python main.py > logs/test-service.log 2>&1 &
    SERVICE_PID=$!
    
    # Save PID for cleanup
    echo $SERVICE_PID > /tmp/training-host-service-test.pid
    
    # Wait for service to be ready
    if check_service_health; then
        echo "✅ Service started successfully (PID: $SERVICE_PID)"
        return 0
    else
        echo "❌ Failed to start service"
        kill $SERVICE_PID 2>/dev/null
        return 1
    fi
}

# Function to stop service
stop_service() {
    echo ""
    echo "🛑 Stopping Training Host Service"
    echo "---------------------------------"
    
    if [ -f /tmp/training-host-service-test.pid ]; then
        SERVICE_PID=$(cat /tmp/training-host-service-test.pid)
        
        if kill $SERVICE_PID 2>/dev/null; then
            echo "✅ Service stopped (PID: $SERVICE_PID)"
        else
            echo "⚠️  Service process not found or already stopped"
        fi
        
        rm -f /tmp/training-host-service-test.pid
    else
        echo "⚠️  No service PID file found"
    fi
}

# Function to run integration tests
run_integration_tests() {
    echo ""
    echo "🔗 Running Integration Tests"
    echo "----------------------------"
    
    cd "$SERVICE_DIR"
    python -m pytest tests/integration/ -v --tb=short -m "integration and not integration_slow"
    
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo "✅ Integration tests passed"
    else
        echo "❌ Integration tests failed"
    fi
    
    return $exit_code
}

# Function to run performance tests
run_performance_tests() {
    echo ""
    echo "⚡ Running Performance Tests"
    echo "---------------------------"
    
    cd "$SERVICE_DIR"
    python -m pytest tests/integration/ -v --tb=short -m "integration_slow"
    
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo "✅ Performance tests passed"
    else
        echo "❌ Performance tests failed"
    fi
    
    return $exit_code
}

# Function to test basic service functionality
test_basic_functionality() {
    echo ""
    echo "🔍 Testing Basic Service Functionality"
    echo "--------------------------------------"
    
    # Test root endpoint
    echo "Testing root endpoint..."
    if curl -s http://localhost:5002/ | grep -q "Training Host Service"; then
        echo "✅ Root endpoint working"
    else
        echo "❌ Root endpoint failed"
        return 1
    fi
    
    # Test health endpoint
    echo "Testing health endpoint..."
    if curl -s http://localhost:5002/health | grep -q '"healthy":true'; then
        echo "✅ Health endpoint working"
    else
        echo "❌ Health endpoint failed"
        return 1
    fi
    
    # Test detailed health endpoint
    echo "Testing detailed health endpoint..."
    if curl -s http://localhost:5002/health/detailed | grep -q '"healthy":true'; then
        echo "✅ Detailed health endpoint working"
    else
        echo "❌ Detailed health endpoint failed"
        return 1
    fi
    
    # Test training sessions list
    echo "Testing training sessions list..."
    if curl -s http://localhost:5002/training/sessions | grep -q '"total_sessions"'; then
        echo "✅ Training sessions endpoint working"
    else
        echo "❌ Training sessions endpoint failed"
        return 1
    fi
    
    echo "✅ All basic functionality tests passed"
    return 0
}

# Function to display service logs
show_logs() {
    echo ""
    echo "📋 Service Logs (last 20 lines)"
    echo "-------------------------------"
    
    if [ -f "$SERVICE_DIR/logs/test-service.log" ]; then
        tail -20 "$SERVICE_DIR/logs/test-service.log"
    else
        echo "No service logs found"
    fi
}

# Main test execution
main() {
    local run_integration=false
    local run_performance=false
    local show_help=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --integration)
                run_integration=true
                shift
                ;;
            --performance)
                run_performance=true
                shift
                ;;
            --all)
                run_integration=true
                run_performance=true
                shift
                ;;
            --help|-h)
                show_help=true
                shift
                ;;
            *)
                echo "Unknown option: $1"
                show_help=true
                shift
                ;;
        esac
    done
    
    if [ "$show_help" = true ]; then
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --integration    Run integration tests (requires service to be started)"
        echo "  --performance    Run performance tests (requires service to be started)"
        echo "  --all            Run all tests including integration and performance"
        echo "  --help, -h       Show this help message"
        echo ""
        echo "Default: Run unit tests only"
        return 0
    fi
    
    # Create logs directory
    mkdir -p "$SERVICE_DIR/logs"
    
    local overall_success=true
    
    # Always run unit tests
    if ! run_unit_tests; then
        overall_success=false
    fi
    
    # Run integration tests if requested
    if [ "$run_integration" = true ] || [ "$run_performance" = true ]; then
        if start_service; then
            # Test basic functionality first
            if test_basic_functionality; then
                if [ "$run_integration" = true ]; then
                    if ! run_integration_tests; then
                        overall_success=false
                    fi
                fi
                
                if [ "$run_performance" = true ]; then
                    if ! run_performance_tests; then
                        overall_success=false
                    fi
                fi
            else
                echo "❌ Basic functionality tests failed, skipping remaining tests"
                overall_success=false
            fi
            
            stop_service
        else
            echo "❌ Failed to start service for integration tests"
            overall_success=false
        fi
        
        show_logs
    fi
    
    # Final summary
    echo ""
    echo "📊 Test Results Summary"
    echo "======================"
    
    if [ "$overall_success" = true ]; then
        echo "🎉 All tests passed successfully!"
        return 0
    else
        echo "💥 Some tests failed. Check the output above for details."
        return 1
    fi
}

# Cleanup function for script interruption
cleanup() {
    echo ""
    echo "🧹 Cleaning up..."
    stop_service
    exit 1
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Run main function
main "$@"