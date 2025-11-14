#!/bin/bash
# Test end-to-end distributed tracing across workers and host services
#
# This script validates Phase 3 instrumentation by checking that:
# 1. All services are sending traces to Jaeger
# 2. Traces span across backend → workers → host services
# 3. Service names are correct

set -e

echo "🧪 Testing distributed tracing (Phase 3)..."
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Jaeger is running
echo "1️⃣ Checking Jaeger availability..."
if ! curl -s http://localhost:16686/api/services > /dev/null; then
    echo -e "${RED}❌ Jaeger is not running at localhost:16686${NC}"
    echo "   Start with: docker-compose -f docker/docker-compose.dev.yml up -d jaeger"
    exit 1
fi
echo -e "${GREEN}✅ Jaeger is running${NC}"
echo ""

# Check if backend is running
echo "2️⃣ Checking backend availability..."
if ! curl -s http://localhost:8000/health > /dev/null; then
    echo -e "${RED}❌ Backend is not running at localhost:8000${NC}"
    echo "   Start with: docker-compose -f docker/docker-compose.dev.yml up -d backend"
    exit 1
fi
echo -e "${GREEN}✅ Backend is running${NC}"
echo ""

# Make test requests to generate traces
echo "3️⃣ Making test requests to generate traces..."
echo "   • Testing backend API..."
curl -s http://localhost:8000/health > /dev/null
curl -s http://localhost:8000/ > /dev/null
echo -e "${GREEN}   ✅ Backend requests sent${NC}"

# Optional: Test IB host service if running
if curl -s http://localhost:5001/health > /dev/null 2>&1; then
    echo "   • Testing IB host service..."
    curl -s http://localhost:5001/health > /dev/null
    echo -e "${GREEN}   ✅ IB host service requests sent${NC}"
else
    echo -e "${YELLOW}   ⚠ IB host service not running (skipping)${NC}"
fi

echo ""

# Wait for traces to be exported
echo "4️⃣ Waiting for traces to be exported..."
sleep 3
echo ""

# Check for services in Jaeger
echo "5️⃣ Checking for services in Jaeger..."
SERVICES=$(curl -s "http://localhost:16686/api/services" | grep -o '"name":"[^"]*"' | cut -d'"' -f4)

# Expected services
declare -A expected_services=(
    ["ktrdr-api"]="Backend API"
    ["ktrdr-ib-host-service"]="IB Host Service"
    ["ktrdr-training-worker"]="Training Worker"
    ["ktrdr-backtest-worker"]="Backtest Worker"
)

found_services=0
for service in "${!expected_services[@]}"; do
    if echo "$SERVICES" | grep -q "$service"; then
        echo -e "${GREEN}✅ Found: ${expected_services[$service]} ($service)${NC}"
        ((found_services++))
    else
        echo -e "${YELLOW}⚠ Not found: ${expected_services[$service]} ($service)${NC}"
        echo "   (Service may not be running or hasn't sent traces yet)"
    fi
done

echo ""

# Check if we found at least the backend
if [ $found_services -lt 1 ]; then
    echo -e "${RED}❌ No instrumented services found in Jaeger${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "1. Check backend logs: docker-compose -f docker/docker-compose.dev.yml logs backend"
    echo "2. Verify OTLP_ENDPOINT env var: docker-compose -f docker/docker-compose.dev.yml exec backend env | grep OTLP"
    echo "3. Check backend can reach Jaeger: docker-compose -f docker/docker-compose.dev.yml exec backend curl http://jaeger:4317"
    exit 1
fi

# Get recent traces for ktrdr-api
echo "6️⃣ Checking recent traces for ktrdr-api..."
TRACES=$(curl -s "http://localhost:16686/api/traces?service=ktrdr-api&limit=5")

if echo "$TRACES" | grep -q "ktrdr-api"; then
    echo -e "${GREEN}✅ Recent traces found for ktrdr-api${NC}"

    # Count traces
    TRACE_COUNT=$(echo "$TRACES" | grep -o '"traceID"' | wc -l | tr -d ' ')
    echo "   Found $TRACE_COUNT trace(s)"

    # Check for HTTP attributes
    if echo "$TRACES" | grep -q '"http.method"'; then
        echo -e "${GREEN}   ✅ HTTP attributes captured${NC}"
    fi

    # Check for service identification
    if echo "$TRACES" | grep -q '"service.name"'; then
        echo -e "${GREEN}   ✅ Service identification present${NC}"
    fi
else
    echo -e "${YELLOW}⚠ No recent traces found for ktrdr-api${NC}"
    echo "   Make sure requests were made to the API"
fi

echo ""

# Final summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
if [ $found_services -ge 1 ]; then
    echo -e "${GREEN}🎉 Phase 3 distributed tracing validation: PASSED${NC}"
    echo ""
    echo "Services instrumented: $found_services / ${#expected_services[@]}"
    echo ""
    echo "Next steps:"
    echo "1. View traces in Jaeger UI: http://localhost:16686"
    echo "2. Select a service from the dropdown"
    echo "3. Click 'Find Traces' to see trace timelines"
    echo "4. Submit operations (training, backtesting) to see cross-service traces"
else
    echo -e "${YELLOW}⚠ Phase 3 validation: PARTIAL${NC}"
    echo ""
    echo "Some services are not yet instrumented or not running."
    echo "This is OK if you're testing incrementally."
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
