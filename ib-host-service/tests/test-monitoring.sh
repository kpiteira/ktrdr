#!/bin/bash
#
# Quick test of Phase 0 stability monitoring (5 iterations)
# Tests the monitoring script before starting 24h run
#

LOG_FILE="stability-test-quick.log"
INTERVAL_SECONDS=10  # 10 seconds for quick test
MAX_ITERATIONS=5

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 Testing Phase 0 stability monitoring (${MAX_ITERATIONS} iterations)...${NC}"

# Initialize log file
echo "=== Phase 0 Stability Test (QUICK) Started at $(date) ===" > "$LOG_FILE"
echo "Monitoring interval: ${INTERVAL_SECONDS}s" >> "$LOG_FILE"
echo "Max iterations: ${MAX_ITERATIONS}" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

START_TIME=$(date +%s)
ITERATION=0
ERRORS=0

# Function to log with timestamp
log_metric() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $1" >> "$LOG_FILE"
}

# Function to test single metric
test_metric() {
    local name="$1"
    local command="$2"
    local expected="$3"
    
    if result=$(eval "$command" 2>/dev/null); then
        if [[ "$result" == *"$expected"* ]] || [[ -z "$expected" ]]; then
            log_metric "✅ $name: PASS"
            return 0
        else
            log_metric "❌ $name: FAIL (unexpected: $result)"
            return 1
        fi
    else
        log_metric "❌ $name: FAIL (command failed)"
        return 1
    fi
}

# Function to get response time
get_response_time() {
    local url="$1"
    local time_ms=$(curl -o /dev/null -s -w "%{time_total}" "$url" 2>/dev/null | awk '{print $1 * 1000}')
    echo "${time_ms}"
}

# Main monitoring loop
while [ $ITERATION -lt $MAX_ITERATIONS ]; do
    ITERATION=$((ITERATION + 1))
    ELAPSED_SECONDS=$(( $(date +%s) - START_TIME ))
    
    echo -e "${BLUE}--- Test Iteration $ITERATION/${MAX_ITERATIONS} (${ELAPSED_SECONDS}s elapsed) ---${NC}"
    log_metric "=== Test Iteration $ITERATION/${MAX_ITERATIONS} (${ELAPSED_SECONDS}s elapsed) ==="
    
    ITERATION_ERRORS=0
    
    # 1. Host service health & response time
    echo -n "Testing host service health... "
    HOST_RESPONSE_TIME=$(get_response_time "http://localhost:5001/health")
    if test_metric "Host service health" "curl -s http://localhost:5001/health | jq -r .healthy" "true"; then
        echo -e "${GREEN}✅${NC} (${HOST_RESPONSE_TIME}ms)"
        log_metric "⏱️  Host service response time: ${HOST_RESPONSE_TIME}ms"
    else
        echo -e "${RED}❌${NC}"
        ITERATION_ERRORS=$((ITERATION_ERRORS + 1))
    fi
    
    # 2. Backend environment
    echo -n "Testing backend environment... "
    if test_metric "Backend environment" "docker exec ktrdr-backend env | grep USE_IB_HOST_SERVICE" "USE_IB_HOST_SERVICE=true"; then
        echo -e "${GREEN}✅${NC}"
    else
        echo -e "${RED}❌${NC}"
        ITERATION_ERRORS=$((ITERATION_ERRORS + 1))
    fi
    
    # 3. Network connectivity & response time
    echo -n "Testing network connectivity... "
    if test_metric "Docker→Host network" "docker exec ktrdr-backend curl -s http://host.docker.internal:5001/health | jq -r .healthy" "true"; then
        echo -e "${GREEN}✅${NC}"
    else
        echo -e "${RED}❌${NC}"
        ITERATION_ERRORS=$((ITERATION_ERRORS + 1))
    fi
    
    # 4. Backend API response time
    echo -n "Testing backend API... "
    BACKEND_RESPONSE_TIME=$(get_response_time "http://localhost:8000/api/v1/health")
    if test_metric "Backend API health" "curl -s http://localhost:8000/api/v1/health | jq -r .status" "ok"; then
        echo -e "${GREEN}✅${NC} (${BACKEND_RESPONSE_TIME}ms)"
        log_metric "⏱️  Backend API response time: ${BACKEND_RESPONSE_TIME}ms"
    else
        echo -e "${RED}❌${NC}"
        ITERATION_ERRORS=$((ITERATION_ERRORS + 1))
    fi
    
    # 5. IB status consistency
    echo -n "Testing IB status endpoint... "
    if test_metric "IB status endpoint" "curl -s http://localhost:8000/api/v1/ib/status | jq -r .data.connection.host" "http://host.docker.internal:5001"; then
        echo -e "${GREEN}✅${NC}"
    else
        echo -e "${RED}❌${NC}"
        ITERATION_ERRORS=$((ITERATION_ERRORS + 1))
    fi
    
    # Update error counts and summary
    if [ $ITERATION_ERRORS -gt 0 ]; then
        ERRORS=$((ERRORS + ITERATION_ERRORS))
        echo -e "${RED}❌ $ITERATION_ERRORS errors in this iteration${NC}"
        log_metric "❌ Iteration errors: $ITERATION_ERRORS (Total: $ERRORS)"
    else
        echo -e "${GREEN}✅ All checks passed${NC}"
        log_metric "✅ All checks passed"
    fi
    
    log_metric "📊 Summary: Iteration $ITERATION, Errors: $ERRORS"
    log_metric ""
    
    if [ $ITERATION -lt $MAX_ITERATIONS ]; then
        echo -e "${YELLOW}⏭️  Next check in ${INTERVAL_SECONDS}s...${NC}"
        echo ""
        sleep $INTERVAL_SECONDS
    fi
done

# Final summary
TOTAL_TIME=$(( $(date +%s) - START_TIME ))
echo -e "${BLUE}=== Quick Stability Test Completed ===${NC}"
echo -e "${GREEN}📊 Total duration: ${TOTAL_TIME}s${NC}"
echo -e "${GREEN}🔢 Total iterations: $ITERATION${NC}"

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}🎉 QUICK TEST PASSED: Zero errors over ${ITERATION} iterations${NC}"
    log_metric "🎉 QUICK TEST PASSED: Zero errors over ${ITERATION} iterations"
    echo -e "${YELLOW}✅ Monitoring script is working correctly. Ready for 24h test!${NC}"
else
    echo -e "${YELLOW}⚠️  QUICK TEST ISSUES: $ERRORS errors over ${ITERATION} iterations${NC}"
    log_metric "⚠️  QUICK TEST ISSUES: $ERRORS errors over ${ITERATION} iterations"
    echo -e "${RED}❌ Fix issues before starting 24h test${NC}"
fi

log_metric "=== Quick Stability Test Completed at $(date) ==="
echo -e "${BLUE}📄 Quick test log: ${LOG_FILE}${NC}"