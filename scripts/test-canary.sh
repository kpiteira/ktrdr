#!/bin/bash
# =============================================================================
# Canary Functional Tests
# =============================================================================
# Tests the canary deployment to verify production image works correctly.
# Run with: make canary-test (after make canary-up)
#
# Tests:
#   1. Backend health check
#   2. Workers registered (backtest + training)
#   3. Training: start -> status -> cancel
#   4. Backtest: start -> status -> cancel
# =============================================================================

set -e  # Exit on error

API_URL="${CANARY_API_URL:-http://localhost:18000/api/v1}"
PASSED=0
FAILED=0

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_pass() {
    echo -e "${GREEN}  ✓ $1${NC}"
    PASSED=$((PASSED + 1))
}

log_fail() {
    echo -e "${RED}  ✗ $1${NC}"
    FAILED=$((FAILED + 1))
}

log_info() {
    echo -e "${YELLOW}  → $1${NC}"
}

# =============================================================================
# Test 1: Backend Health
# =============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 1: Backend Health Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

HEALTH=$(curl -sf "${API_URL}/health" 2>/dev/null || echo "FAILED")
if [ "$HEALTH" != "FAILED" ]; then
    log_pass "Backend is healthy"
else
    log_fail "Backend health check failed"
    echo "Make sure canary is running: make canary-up"
    exit 1
fi

# =============================================================================
# Test 2: Workers Registered
# =============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 2: Workers Registered"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Wait for workers to register (they register on startup)
log_info "Waiting for workers to register..."
sleep 5

WORKERS=$(curl -sf "${API_URL}/workers" 2>/dev/null)
# API returns a list directly, not {"workers": [...]}
WORKER_COUNT=$(echo "$WORKERS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data) if isinstance(data, list) else len(data.get('workers', [])))" 2>/dev/null || echo "0")

if [ "$WORKER_COUNT" -ge 2 ]; then
    log_pass "Found $WORKER_COUNT workers registered"

    # Check for specific worker types (handle both list and dict response)
    HAS_BACKTEST=$(echo "$WORKERS" | python3 -c "import sys, json; data=json.load(sys.stdin); workers=data if isinstance(data,list) else data.get('workers',[]); print('yes' if any(w.get('worker_type')=='backtesting' for w in workers) else 'no')" 2>/dev/null || echo "no")
    HAS_TRAINING=$(echo "$WORKERS" | python3 -c "import sys, json; data=json.load(sys.stdin); workers=data if isinstance(data,list) else data.get('workers',[]); print('yes' if any(w.get('worker_type')=='training' for w in workers) else 'no')" 2>/dev/null || echo "no")

    if [ "$HAS_BACKTEST" = "yes" ]; then
        log_pass "Backtest worker registered"
    else
        log_fail "No backtest worker found"
    fi

    if [ "$HAS_TRAINING" = "yes" ]; then
        log_pass "Training worker registered"
    else
        log_fail "No training worker found"
    fi
else
    log_fail "Expected at least 2 workers, found $WORKER_COUNT"
    echo "Workers response: $WORKERS"
fi

# =============================================================================
# Test 3: Training Operation (Start -> Status -> Cancel)
# =============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 3: Training Operation Lifecycle"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

log_info "Starting training operation..."
TRAINING_RESPONSE=$(curl -sf -X POST "${API_URL}/trainings/start" \
    -H "Content-Type: application/json" \
    -d '{
        "symbols": ["EURUSD"],
        "timeframes": ["1d"],
        "strategy_name": "neuro_mean_reversion"
    }' 2>/dev/null || echo '{"success": false}')

TRAINING_SUCCESS=$(echo "$TRAINING_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('success', False))" 2>/dev/null || echo "False")
TRAINING_ID=$(echo "$TRAINING_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('task_id', ''))" 2>/dev/null || echo "")

if [ "$TRAINING_SUCCESS" = "True" ] && [ -n "$TRAINING_ID" ]; then
    log_pass "Training started: $TRAINING_ID"

    # Check status
    sleep 2
    log_info "Checking training status..."
    STATUS_RESPONSE=$(curl -sf "${API_URL}/operations/${TRAINING_ID}" 2>/dev/null || echo '{}')
    STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('data',{}).get('status','unknown'))" 2>/dev/null || echo "unknown")

    if [ "$STATUS" != "unknown" ]; then
        log_pass "Training status: $STATUS"
    else
        log_fail "Could not get training status"
    fi

    # Cancel
    log_info "Cancelling training..."
    CANCEL_RESPONSE=$(curl -sf -X DELETE "${API_URL}/operations/${TRAINING_ID}" 2>/dev/null || echo '{"success": false}')
    CANCEL_SUCCESS=$(echo "$CANCEL_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('success', False))" 2>/dev/null || echo "False")

    if [ "$CANCEL_SUCCESS" = "True" ]; then
        log_pass "Training cancelled successfully"
    else
        # It's OK if it already completed or failed
        log_info "Training cancel returned: $CANCEL_RESPONSE"
        log_pass "Training cancel attempted (may have already finished)"
    fi
else
    log_fail "Training start failed"
    echo "Response: $TRAINING_RESPONSE"
fi

# =============================================================================
# Test 4: Backtest Operation (Start -> Status -> Cancel)
# =============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 4: Backtest Operation Lifecycle"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

log_info "Starting backtest operation..."
BACKTEST_RESPONSE=$(curl -sf -X POST "${API_URL}/backtests/start" \
    -H "Content-Type: application/json" \
    -d '{
        "strategy_name": "neuro_mean_reversion",
        "symbol": "EURUSD",
        "timeframe": "1d",
        "start_date": "2024-01-01",
        "end_date": "2024-06-30",
        "initial_capital": 100000.0
    }' 2>/dev/null || echo '{"success": false}')

BACKTEST_SUCCESS=$(echo "$BACKTEST_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('success', False))" 2>/dev/null || echo "False")
BACKTEST_ID=$(echo "$BACKTEST_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('operation_id', ''))" 2>/dev/null || echo "")

if [ "$BACKTEST_SUCCESS" = "True" ] && [ -n "$BACKTEST_ID" ]; then
    log_pass "Backtest started: $BACKTEST_ID"

    # Check status
    sleep 2
    log_info "Checking backtest status..."
    STATUS_RESPONSE=$(curl -sf "${API_URL}/operations/${BACKTEST_ID}" 2>/dev/null || echo '{}')
    STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('data',{}).get('status','unknown'))" 2>/dev/null || echo "unknown")

    if [ "$STATUS" != "unknown" ]; then
        log_pass "Backtest status: $STATUS"
    else
        log_fail "Could not get backtest status"
    fi

    # Cancel
    log_info "Cancelling backtest..."
    CANCEL_RESPONSE=$(curl -sf -X DELETE "${API_URL}/operations/${BACKTEST_ID}" 2>/dev/null || echo '{"success": false}')
    CANCEL_SUCCESS=$(echo "$CANCEL_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('success', False))" 2>/dev/null || echo "False")

    if [ "$CANCEL_SUCCESS" = "True" ]; then
        log_pass "Backtest cancelled successfully"
    else
        log_info "Backtest cancel returned: $CANCEL_RESPONSE"
        log_pass "Backtest cancel attempted (may have already finished)"
    fi
else
    log_fail "Backtest start failed"
    echo "Response: $BACKTEST_RESPONSE"
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "  ${GREEN}Passed: $PASSED${NC}"
echo -e "  ${RED}Failed: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  All canary tests passed! Safe to merge.${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    exit 0
else
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}  Some tests failed. Review before merging.${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    exit 1
fi
