#!/bin/bash
#
# Phase 0 Stability Monitoring Script
# 
# Monitors IB Host Service integration stability over 24+ hours
# Logs metrics to stability-test.log for analysis
#

LOG_FILE="stability-test.log"
INTERVAL_SECONDS=300  # 5 minutes
MAX_DURATION_HOURS=24

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Initialize log file
echo "=== Phase 0 Stability Test Started at $(date) ===" > "$LOG_FILE"
echo "Monitoring interval: ${INTERVAL_SECONDS}s" >> "$LOG_FILE"
echo "Target duration: ${MAX_DURATION_HOURS}h" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

START_TIME=$(date +%s)
ITERATION=0
ERRORS=0

echo -e "${BLUE}🔍 Starting Phase 0 stability monitoring...${NC}"
echo -e "${YELLOW}⏱️  Monitoring every ${INTERVAL_SECONDS}s for ${MAX_DURATION_HOURS}h${NC}"
echo -e "${YELLOW}📄 Logging to: ${LOG_FILE}${NC}"
echo ""

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
while true; do
    ITERATION=$((ITERATION + 1))
    CURRENT_TIME=$(date +%s)
    ELAPSED_HOURS=$(( (CURRENT_TIME - START_TIME) / 3600 ))
    
    # Check if we've reached target duration
    if [ $ELAPSED_HOURS -ge $MAX_DURATION_HOURS ]; then
        echo -e "${GREEN}✅ Target monitoring duration reached: ${ELAPSED_HOURS}h${NC}"
        break
    fi
    
    echo -e "${BLUE}--- Iteration $ITERATION (${ELAPSED_HOURS}h elapsed) ---${NC}"
    log_metric "=== Iteration $ITERATION (${ELAPSED_HOURS}h elapsed) ==="
    
    ITERATION_ERRORS=0
    
    # 1. Host service health & response time
    HOST_RESPONSE_TIME=$(get_response_time "http://localhost:5001/health")
    if test_metric "Host service health" "curl -s http://localhost:5001/health | jq -r .healthy" "true"; then
        log_metric "⏱️  Host service response time: ${HOST_RESPONSE_TIME}ms"
    else
        ITERATION_ERRORS=$((ITERATION_ERRORS + 1))
    fi
    
    # 2. Docker backend environment
    if ! test_metric "Backend environment" "docker exec ktrdr-backend env | grep USE_IB_HOST_SERVICE" "USE_IB_HOST_SERVICE=true"; then
        ITERATION_ERRORS=$((ITERATION_ERRORS + 1))
    fi
    
    # 3. Network connectivity & response time
    NETWORK_RESPONSE_TIME=$(get_response_time "http://localhost:8000/api/v1/health")
    if test_metric "Docker→Host network" "docker exec ktrdr-backend curl -s http://host.docker.internal:5001/health | jq -r .healthy" "true"; then
        log_metric "⏱️  Backend API response time: ${NETWORK_RESPONSE_TIME}ms"
    else
        ITERATION_ERRORS=$((ITERATION_ERRORS + 1))
    fi
    
    # 4. IB status endpoint consistency
    if ! test_metric "IB status endpoint" "curl -s http://localhost:8000/api/v1/ib/status | jq -r .data.connection.host" "http://host.docker.internal:5001"; then
        ITERATION_ERRORS=$((ITERATION_ERRORS + 1))
    fi
    
    # 5. Backend API health
    if ! test_metric "Backend API health" "curl -s http://localhost:8000/api/v1/health | jq -r .status" "ok"; then
        ITERATION_ERRORS=$((ITERATION_ERRORS + 1))
    fi
    
    # 6. Memory usage monitoring
    HOST_MEMORY=$(ps -o pid,ppid,%mem,command | grep "main.py" | grep -v grep | awk '{print $3}' | head -1)
    BACKEND_MEMORY=$(docker stats ktrdr-backend --no-stream --format "{{.MemPerc}}" | sed 's/%//')
    log_metric "💾 Host service memory: ${HOST_MEMORY}%"
    log_metric "💾 Backend memory: ${BACKEND_MEMORY}%"
    
    # 7. Container status
    BACKEND_STATUS=$(docker inspect -f '{{.State.Status}}' ktrdr-backend 2>/dev/null)
    log_metric "🐳 Backend container status: $BACKEND_STATUS"
    
    # Update error counts
    if [ $ITERATION_ERRORS -gt 0 ]; then
        ERRORS=$((ERRORS + ITERATION_ERRORS))
        echo -e "${RED}❌ $ITERATION_ERRORS errors in this iteration${NC}"
        log_metric "❌ Iteration errors: $ITERATION_ERRORS (Total: $ERRORS)"
    else
        echo -e "${GREEN}✅ All checks passed${NC}"
        log_metric "✅ All checks passed"
    fi
    
    # Log summary stats
    log_metric "📊 Summary: Iteration $ITERATION, Errors: $ERRORS, Uptime: ${ELAPSED_HOURS}h"
    log_metric ""
    
    echo -e "${YELLOW}⏭️  Next check in ${INTERVAL_SECONDS}s...${NC}"
    echo ""
    
    # Sleep until next iteration
    sleep $INTERVAL_SECONDS
done

# Final summary
TOTAL_TIME=$(( ($(date +%s) - START_TIME) / 3600 ))
echo -e "${BLUE}=== Phase 0 Stability Test Completed ===${NC}"
echo -e "${GREEN}📊 Total duration: ${TOTAL_TIME}h${NC}"
echo -e "${GREEN}🔢 Total iterations: $ITERATION${NC}"

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}🎉 STABILITY TEST PASSED: Zero errors over ${TOTAL_TIME}h${NC}"
    log_metric "🎉 STABILITY TEST PASSED: Zero errors over ${TOTAL_TIME}h"
else
    echo -e "${YELLOW}⚠️  STABILITY TEST COMPLETED WITH ISSUES: $ERRORS errors over ${TOTAL_TIME}h${NC}"
    log_metric "⚠️  STABILITY TEST COMPLETED WITH ISSUES: $ERRORS errors over ${TOTAL_TIME}h"
fi

log_metric "=== Phase 0 Stability Test Completed at $(date) ==="
echo -e "${BLUE}📄 Full log available in: ${LOG_FILE}${NC}"