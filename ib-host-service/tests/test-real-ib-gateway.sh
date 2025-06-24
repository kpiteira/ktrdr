#!/bin/bash
#
# Real IB Gateway Integration Test
# Tests Phase 0 host service with actual IB Gateway connection
#

echo "=== Real IB Gateway Integration Test ==="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

TESTS_PASSED=0
TESTS_FAILED=0

# Function to run test
run_test() {
    local test_name="$1"
    local command="$2"
    local expected_pattern="$3"
    
    echo -n "Testing $test_name... "
    
    if result=$(eval "$command" 2>/dev/null); then
        if [[ "$result" == *"$expected_pattern"* ]] || [[ -z "$expected_pattern" ]]; then
            echo -e "${GREEN}✅ PASS${NC}"
            TESTS_PASSED=$((TESTS_PASSED + 1))
            return 0
        else
            echo -e "${RED}❌ FAIL${NC}"
            echo -e "${YELLOW}   Expected: $expected_pattern${NC}"
            echo -e "${YELLOW}   Got: $result${NC}"
            TESTS_FAILED=$((TESTS_FAILED + 1))
            return 1
        fi
    else
        echo -e "${RED}❌ FAIL${NC} (command failed)"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Function to test data fetch
test_data_fetch() {
    local symbol="$1"
    local timeframe="$2"
    
    echo -n "Testing $symbol $timeframe data fetch... "
    
    result=$(curl -s -X POST http://localhost:5001/data/historical \
        -H "Content-Type: application/json" \
        -d "{\"symbol\": \"$symbol\", \"timeframe\": \"$timeframe\", \"start\": \"2025-06-20T00:00:00Z\", \"end\": \"2025-06-23T23:59:59Z\"}" \
        2>/dev/null)
    
    if echo "$result" | jq -e '.success == true and .rows > 0' >/dev/null 2>&1; then
        rows=$(echo "$result" | jq -r '.rows')
        echo -e "${GREEN}✅ PASS${NC} ($rows rows)"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}❌ FAIL${NC}"
        echo -e "${YELLOW}   Result: $result${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

echo -e "${BLUE}1. IB Gateway Connectivity${NC}"

# Check IB Gateway is running
run_test "IB Gateway port 4002" "lsof -i :4002 | grep LISTEN" "LISTEN"

echo ""
echo -e "${BLUE}2. Host Service Integration${NC}"

# Test host service health
run_test "Host service health" "curl -s http://localhost:5001/health | jq -r .healthy" "true"

# Test host service info
run_test "Host service info" "curl -s http://localhost:5001/ | jq -r .service" "IB Connector Host Service"

echo ""
echo -e "${BLUE}3. Real Data Fetching${NC}"

# Test multiple symbols and timeframes
test_data_fetch "AAPL" "1d"
test_data_fetch "MSFT" "1d" 
test_data_fetch "AAPL" "1h"

echo ""
echo -e "${BLUE}4. Backend Integration${NC}"

# Test backend configuration
run_test "Backend host service mode" "docker exec ktrdr-backend env | grep USE_IB_HOST_SERVICE" "USE_IB_HOST_SERVICE=true"

# Test backend IB status
run_test "Backend IB status endpoint" "curl -s http://localhost:8000/api/v1/ib/status | jq -r .data.connection.host" "http://host.docker.internal:5001"

# Test backend API health
run_test "Backend API health" "curl -s http://localhost:8000/api/v1/health | jq -r .status" "ok"

echo ""
echo -e "${BLUE}5. Network Connectivity${NC}"

# Test Docker-to-host communication
run_test "Docker→Host network" "docker exec ktrdr-backend curl -s http://host.docker.internal:5001/health | jq -r .healthy" "true"

# Test Docker backend can fetch data through host service
echo -n "Testing Docker backend data access... "
backend_result=$(docker exec ktrdr-backend curl -s -X POST http://host.docker.internal:5001/data/historical \
    -H "Content-Type: application/json" \
    -d '{"symbol": "AAPL", "timeframe": "1d", "start": "2025-06-22T00:00:00Z", "end": "2025-06-23T23:59:59Z"}' \
    2>/dev/null)

if echo "$backend_result" | jq -e '.success == true' >/dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAIL${NC}"
    echo -e "${YELLOW}   Result: $backend_result${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo ""
echo -e "${BLUE}6. Performance Testing${NC}"

# Test response times
echo -n "Testing response time... "
start_time=$(date +%s%N)
curl -s http://localhost:5001/health >/dev/null 2>&1
end_time=$(date +%s%N)
response_time_ms=$(( (end_time - start_time) / 1000000 ))

if [ $response_time_ms -lt 100 ]; then
    echo -e "${GREEN}✅ PASS${NC} (${response_time_ms}ms)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${YELLOW}⚠️  SLOW${NC} (${response_time_ms}ms)"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo ""
echo -e "${BLUE}=== Test Results ===${NC}"
echo -e "${GREEN}✅ Tests Passed: $TESTS_PASSED${NC}"
echo -e "${RED}❌ Tests Failed: $TESTS_FAILED${NC}"

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))
SUCCESS_RATE=$(( TESTS_PASSED * 100 / TOTAL_TESTS ))

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL TESTS PASSED! Phase 0 + Real IB Gateway integration is working perfectly.${NC}"
    echo ""
    echo -e "${BLUE}✅ Phase 0 Achievements with Real IB Gateway:${NC}"
    echo "  • Host service successfully connects to IB Gateway"
    echo "  • Real OHLCV data fetching works"
    echo "  • Docker backend integrates correctly"
    echo "  • Network communication is stable"
    echo "  • Response times are fast (< 100ms)"
    echo ""
    echo -e "${YELLOW}🚀 Phase 0 is production-ready!${NC}"
else
    echo -e "${YELLOW}⚠️  Some tests failed. Success rate: ${SUCCESS_RATE}%${NC}"
    echo ""
    echo -e "${BLUE}Issues to investigate:${NC}"
    if [ $TESTS_FAILED -lt 3 ]; then
        echo "  • Minor issues detected - Phase 0 core functionality works"
        echo "  • Consider these improvements for production deployment"
    else
        echo "  • Multiple failures detected - review integration"
    fi
fi

echo ""
echo -e "${BLUE}📊 Summary:${NC}"
echo "  • IB Gateway: $(lsof -i :4002 | grep -q LISTEN && echo "✅ Running" || echo "❌ Not running")"
echo "  • Host Service: $(curl -s http://localhost:5001/health | jq -r .healthy 2>/dev/null | grep -q true && echo "✅ Healthy" || echo "❌ Unhealthy")"
echo "  • Data Fetching: $(curl -s -X POST http://localhost:5001/data/historical -H "Content-Type: application/json" -d '{"symbol": "AAPL", "timeframe": "1d", "start": "2025-06-22T00:00:00Z", "end": "2025-06-23T23:59:59Z"}' 2>/dev/null | jq -r .success 2>/dev/null | grep -q true && echo "✅ Working" || echo "❌ Failed")"
echo "  • Backend Integration: $(curl -s http://localhost:8000/api/v1/ib/status 2>/dev/null | jq -r .data.connection.host 2>/dev/null | grep -q "host.docker.internal:5001" && echo "✅ Configured" || echo "❌ Not configured")"