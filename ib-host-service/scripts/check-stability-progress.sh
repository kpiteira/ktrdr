#!/bin/bash
#
# Monitor Phase 0 Stability Test Progress
# Quick commands to check stability test status
#

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Phase 0 Stability Test Status ===${NC}"
echo ""

# Check if stability test is running
STABILITY_PID=$(ps aux | grep "monitor-stability.sh" | grep -v grep | awk '{print $2}')

if [ -n "$STABILITY_PID" ]; then
    echo -e "${GREEN}✅ Stability test is running (PID: $STABILITY_PID)${NC}"
    
    # Get start time from log
    if [ -f "stability-test.log" ]; then
        START_TIME=$(head -1 stability-test.log | grep -o 'at.*' | sed 's/at //')
        echo -e "${BLUE}🕐 Started: $START_TIME${NC}"
        
        # Calculate elapsed time
        CURRENT_TIME=$(date +%s)
        START_TIMESTAMP=$(date -d "$START_TIME" +%s 2>/dev/null || date -j -f "%a %b %d %H:%M:%S %Z %Y" "$START_TIME" +%s 2>/dev/null || echo "0")
        
        if [ "$START_TIMESTAMP" != "0" ]; then
            ELAPSED_SECONDS=$((CURRENT_TIME - START_TIMESTAMP))
            ELAPSED_HOURS=$((ELAPSED_SECONDS / 3600))
            ELAPSED_MINUTES=$(( (ELAPSED_SECONDS % 3600) / 60 ))
            echo -e "${BLUE}⏱️  Elapsed: ${ELAPSED_HOURS}h ${ELAPSED_MINUTES}m${NC}"
            
            # Progress bar
            PROGRESS=$((ELAPSED_HOURS * 100 / 24))
            if [ $PROGRESS -gt 100 ]; then PROGRESS=100; fi
            
            FILLED=$((PROGRESS / 5))
            EMPTY=$((20 - FILLED))
            BAR=$(printf "%*s" $FILLED | tr ' ' '█')$(printf "%*s" $EMPTY | tr ' ' '░')
            echo -e "${YELLOW}📊 Progress: [$BAR] ${PROGRESS}%${NC}"
        fi
        
        # Get latest stats
        TOTAL_ITERATIONS=$(grep "=== Iteration" stability-test.log | wc -l | tr -d ' ')
        TOTAL_ERRORS=$(grep "❌.*Total:" stability-test.log | tail -1 | grep -o "Total: [0-9]*" | cut -d' ' -f2)
        if [ -z "$TOTAL_ERRORS" ]; then TOTAL_ERRORS=0; fi
        
        echo -e "${BLUE}🔢 Iterations completed: $TOTAL_ITERATIONS${NC}"
        
        if [ "$TOTAL_ERRORS" = "0" ]; then
            echo -e "${GREEN}✅ Total errors: $TOTAL_ERRORS${NC}"
        else
            echo -e "${RED}❌ Total errors: $TOTAL_ERRORS${NC}"
        fi
        
        # Latest status
        LATEST_STATUS=$(grep "✅ All checks passed\|❌.*errors in this iteration" stability-test.log | tail -1)
        if [[ "$LATEST_STATUS" == *"All checks passed"* ]]; then
            echo -e "${GREEN}🟢 Latest status: All checks passed${NC}"
        else
            echo -e "${RED}🔴 Latest status: Errors detected${NC}"
        fi
        
        # Memory usage trend
        echo ""
        echo -e "${BLUE}📈 Recent metrics:${NC}"
        grep "Host service memory\|Backend memory" stability-test.log | tail -4
        
    else
        echo -e "${YELLOW}⚠️  Log file not found yet${NC}"
    fi
    
else
    echo -e "${RED}❌ Stability test is not running${NC}"
    
    # Check if it completed
    if [ -f "stability-test.log" ]; then
        if grep -q "STABILITY TEST PASSED\|STABILITY TEST COMPLETED" stability-test.log; then
            echo -e "${GREEN}✅ Test completed successfully${NC}"
        else
            echo -e "${YELLOW}⚠️  Test may have stopped unexpectedly${NC}"
        fi
    fi
fi

echo ""
echo -e "${YELLOW}📋 Available commands:${NC}"
echo "  tail -f stability-test.log          # Watch live progress"
echo "  grep \"📊 Summary\" stability-test.log | tail -5  # Latest summaries"
echo "  grep \"❌\" stability-test.log        # View any errors"
echo "  ./ib-host-service/scripts/check-stability-progress.sh     # Run this status check again"

if [ -n "$STABILITY_PID" ]; then
    echo "  kill $STABILITY_PID                 # Stop stability test"
fi