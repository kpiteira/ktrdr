#!/bin/bash
#
# Phase 0 Validation Script
# 
# Validates that IB Host Service integration is working correctly
#

echo "=== Phase 0 Integration Validation ==="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

# Function to check and report status
check_status() {
    local name="$1"
    local command="$2"
    local expected="$3"
    
    echo -n "Checking $name: "
    
    if result=$(eval "$command" 2>/dev/null); then
        if [[ "$result" == *"$expected"* ]] || [[ -z "$expected" ]]; then
            echo -e "${GREEN}✅ PASS${NC}"
            return 0
        else
            echo -e "${RED}❌ FAIL${NC} (unexpected result: $result)"
            ERRORS=$((ERRORS + 1))
            return 1
        fi
    else
        echo -e "${RED}❌ FAIL${NC} (command failed)"
        ERRORS=$((ERRORS + 1))
        return 1
    fi
}

# 1. Host service health
check_status "Host service health" \
    "curl -s http://localhost:5001/health | jq -r .healthy" \
    "true"

# 2. Host service endpoints
check_status "Host service info" \
    "curl -s http://localhost:5001/ | jq -r .service" \
    "IB Connector Host Service"

# 3. Backend environment configuration
check_status "Backend environment" \
    "docker exec ktrdr-backend env | grep USE_IB_HOST_SERVICE" \
    "USE_IB_HOST_SERVICE=true"

# 4. Backend logs show host service mode
check_status "Backend host service mode" \
    "docker logs ktrdr-backend 2>&1 | grep -q 'host service.*5001' && echo 'found'" \
    "found"

# 5. Network connectivity from Docker to host
check_status "Docker→Host network" \
    "docker exec ktrdr-backend curl -s http://host.docker.internal:5001/health | jq -r .healthy" \
    "true"

# 6. IB status endpoint shows host service
check_status "IB status endpoint" \
    "curl -s http://localhost:8000/api/v1/ib/status | jq -r .data.connection.host" \
    "http://host.docker.internal:5001"

# 7. Backend API health
check_status "Backend API health" \
    "curl -s http://localhost:8000/api/v1/health | jq -r .status" \
    "ok"

echo ""
echo "=== Validation Summary ==="

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}🎉 All checks passed! Phase 0 integration is working correctly.${NC}"
    echo ""
    echo "✅ Host service is running and healthy"
    echo "✅ Backend is configured for host service mode"  
    echo "✅ Network communication is working"
    echo "✅ All endpoints are responding correctly"
    echo ""
    echo -e "${YELLOW}Ready for stability testing and validation with IB Gateway!${NC}"
    exit 0
else
    echo -e "${RED}❌ $ERRORS check(s) failed. Please review the issues above.${NC}"
    echo ""
    echo "Troubleshooting guide: docs/phase0-troubleshooting-checklist.md"
    echo "Deployment guide: docs/phase0-deployment-guide.md"
    exit 1
fi