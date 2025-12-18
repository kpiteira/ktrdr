#!/bin/bash
#
# E2E Test: Agent Cancellation During All Phases
#
# This script tests cancellation during each phase of the research cycle:
#   1. Designing (Claude call)
#   2. Training (real training worker)
#   3. Backtesting (real backtest worker)
#   4. Assessing (Claude call)
#
# COST WARNING: This script makes real Claude API calls (~$0.10-0.50 per phase reached)
# TIME: ~10-15 minutes total (training and backtest take time)
#
# Prerequisites:
#   - Backend running: docker compose up -d
#   - Real workers available (training-worker, backtest-worker)
#   - ANTHROPIC_API_KEY configured
#
# Usage:
#   ./scripts/test_agent_cancellation_all_phases.sh [phase]
#
#   phase: Optional - test only specific phase (designing|training|backtesting|assessing)
#          If omitted, tests all phases sequentially
#

set -e

API_URL="http://localhost:8000/api/v1"
BOLD='\033[1m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Timing
DESIGN_WAIT_MAX=120      # Max seconds to wait for design to complete
TRAINING_WAIT_MAX=300    # Max seconds to wait for training to complete
BACKTEST_WAIT_MAX=180    # Max seconds to wait for backtest to complete
POLL_INTERVAL=1          # Seconds between status checks (1s for responsive feedback)

log_info() {
    echo -e "${CYAN}[INFO]${NC} $1" >&2
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1" >&2
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1" >&2
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" >&2
}

log_header() {
    echo "" >&2
    echo -e "${BOLD}=== $1 ===${NC}" >&2
    echo "" >&2
}

# Check if backend is healthy
check_backend() {
    log_info "Checking backend health..."
    HEALTH=$(curl -s "${API_URL}/health" 2>/dev/null || echo '{"status":"error"}')
    STATUS=$(echo "$HEALTH" | jq -r '.status // "error"')
    if [ "$STATUS" == "ok" ] || [ "$STATUS" == "healthy" ]; then
        log_success "Backend is healthy (status: $STATUS)"
        return 0
    else
        log_error "Backend is not healthy (status: $STATUS). Run: docker compose up -d"
        exit 1
    fi
}

# Ensure no active cycle before starting
ensure_idle() {
    log_info "Ensuring no active cycle..."
    curl -s -X DELETE "${API_URL}/agent/cancel" > /dev/null 2>&1 || true
    sleep 1

    STATUS=$(curl -s "${API_URL}/agent/status")
    if echo "$STATUS" | jq -e '.status == "idle"' > /dev/null 2>&1; then
        log_success "Agent is idle"
        return 0
    else
        log_warn "Agent may still have an active cycle, attempting to cancel..."
        curl -s -X DELETE "${API_URL}/agent/cancel" > /dev/null 2>&1 || true
        sleep 2
    fi
}

# Trigger a new cycle and return operation ID
trigger_cycle() {
    log_info "Triggering new research cycle..."
    RESULT=$(curl -s -X POST "${API_URL}/agent/trigger")

    TRIGGERED=$(echo "$RESULT" | jq -r '.triggered')
    if [ "$TRIGGERED" != "true" ]; then
        log_error "Failed to trigger cycle: $(echo "$RESULT" | jq -r '.reason // .message')"
        exit 1
    fi

    OP_ID=$(echo "$RESULT" | jq -r '.operation_id')
    log_success "Cycle triggered: $OP_ID"
    echo "$OP_ID"
}

# Wait for a specific phase
wait_for_phase() {
    local TARGET_PHASE=$1
    local MAX_WAIT=$2
    local ELAPSED=0

    log_info "Waiting for phase: $TARGET_PHASE (max ${MAX_WAIT}s)..."

    while [ $ELAPSED -lt $MAX_WAIT ]; do
        STATUS=$(curl -s "${API_URL}/agent/status")
        CURRENT_PHASE=$(echo "$STATUS" | jq -r '.phase // "unknown"')
        CURRENT_STATUS=$(echo "$STATUS" | jq -r '.status')

        # Check if cycle completed or failed before reaching target phase
        if [ "$CURRENT_STATUS" == "idle" ]; then
            LAST_OUTCOME=$(echo "$STATUS" | jq -r '.last_cycle.outcome // "unknown"')
            if [ "$LAST_OUTCOME" == "completed" ]; then
                log_warn "Cycle completed before reaching $TARGET_PHASE phase"
                return 1
            elif [ "$LAST_OUTCOME" == "failed" ]; then
                log_error "Cycle failed before reaching $TARGET_PHASE phase"
                return 2
            fi
        fi

        if [ "$CURRENT_PHASE" == "$TARGET_PHASE" ]; then
            log_success "Reached phase: $TARGET_PHASE (after ${ELAPSED}s)"
            return 0
        fi

        # Show progress
        printf "\r  Current: %-15s Elapsed: %3ds / %3ds" "$CURRENT_PHASE" "$ELAPSED" "$MAX_WAIT" >&2

        sleep $POLL_INTERVAL
        ELAPSED=$((ELAPSED + POLL_INTERVAL))
    done

    echo "" >&2
    log_error "Timeout waiting for phase: $TARGET_PHASE"
    return 3
}

# Cancel the active cycle and verify
cancel_and_verify() {
    local OP_ID=$1
    local PHASE=$2

    log_info "Cancelling cycle during $PHASE phase..."

    # Time the cancellation
    START_MS=$(date +%s%N | cut -b1-13)

    CANCEL_RESULT=$(curl -s -X DELETE "${API_URL}/agent/cancel")
    SUCCESS=$(echo "$CANCEL_RESULT" | jq -r '.success')

    if [ "$SUCCESS" != "true" ]; then
        log_error "Cancel failed: $(echo "$CANCEL_RESULT" | jq -r '.reason // .message')"
        return 1
    fi

    CHILD_CANCELLED=$(echo "$CANCEL_RESULT" | jq -r '.child_cancelled // "none"')
    log_info "Child operation cancelled: $CHILD_CANCELLED"

    # Wait for cancellation to complete
    for i in {1..20}; do
        OP_STATUS=$(curl -s "${API_URL}/operations/$OP_ID" | jq -r '.data.status')
        if [ "$OP_STATUS" == "cancelled" ]; then
            END_MS=$(date +%s%N | cut -b1-13)
            ELAPSED_MS=$((END_MS - START_MS))

            log_success "Parent operation cancelled (${ELAPSED_MS}ms)"

            # Verify child is also cancelled
            if [ "$CHILD_CANCELLED" != "none" ] && [ "$CHILD_CANCELLED" != "null" ]; then
                CHILD_STATUS=$(curl -s "${API_URL}/operations/$CHILD_CANCELLED" | jq -r '.data.status')
                if [ "$CHILD_STATUS" == "cancelled" ]; then
                    log_success "Child operation also cancelled"
                else
                    log_warn "Child operation status: $CHILD_STATUS (expected: cancelled)"
                fi
            fi

            # Check cancellation speed
            if [ $ELAPSED_MS -lt 500 ]; then
                log_success "Cancellation completed within 500ms requirement"
            else
                log_warn "Cancellation took ${ELAPSED_MS}ms (> 500ms target)"
            fi

            return 0
        fi
        sleep 0.1
    done

    log_error "Timeout waiting for operation to be marked cancelled"
    return 1
}

# Test cancellation during a specific phase
test_cancel_during_phase() {
    local PHASE=$1
    local WAIT_TIME=$2

    log_header "Test: Cancel During $PHASE Phase"

    ensure_idle

    OP_ID=$(trigger_cycle)

    if wait_for_phase "$PHASE" $WAIT_TIME; then
        # Give the phase a moment to establish
        sleep 1

        if cancel_and_verify "$OP_ID" "$PHASE"; then
            log_success "Cancel during $PHASE: PASSED"
            return 0
        else
            log_error "Cancel during $PHASE: FAILED (cancel/verify failed)"
            return 1
        fi
    else
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 1 ]; then
            log_warn "Skipping $PHASE test - cycle completed too fast"
            return 0
        else
            log_error "Cancel during $PHASE: FAILED (could not reach phase)"
            return 1
        fi
    fi
}

# Verify new cycle can start after cancel
test_trigger_after_cancel() {
    log_header "Test: Trigger New Cycle After Cancel"

    ensure_idle

    # Start a cycle
    OP_ID1=$(trigger_cycle)
    sleep 2

    # Cancel it
    curl -s -X DELETE "${API_URL}/agent/cancel" > /dev/null
    sleep 1

    # Verify cancelled
    STATUS1=$(curl -s "${API_URL}/operations/$OP_ID1" | jq -r '.data.status')
    if [ "$STATUS1" != "cancelled" ]; then
        log_error "First cycle not cancelled: $STATUS1"
        return 1
    fi
    log_success "First cycle cancelled"

    # Start new cycle
    OP_ID2=$(trigger_cycle)

    if [ "$OP_ID1" == "$OP_ID2" ]; then
        log_error "New cycle has same operation ID as cancelled one"
        return 1
    fi

    log_success "New cycle started with different ID: $OP_ID2"

    # Cancel the new cycle
    curl -s -X DELETE "${API_URL}/agent/cancel" > /dev/null
    sleep 1

    log_success "Trigger after cancel: PASSED"
    return 0
}

# Main test runner
run_all_tests() {
    local FAILED=0

    log_header "Agent Cancellation E2E Tests - All Phases"
    log_warn "This will make real Claude API calls and take ~10-15 minutes"
    echo ""

    check_backend

    # Test 1: Cancel during designing
    if ! test_cancel_during_phase "designing" $DESIGN_WAIT_MAX; then
        FAILED=$((FAILED + 1))
    fi

    # Test 2: Cancel during training (requires design to complete first)
    if ! test_cancel_during_phase "training" $((DESIGN_WAIT_MAX + TRAINING_WAIT_MAX)); then
        FAILED=$((FAILED + 1))
    fi

    # Test 3: Cancel during backtesting (requires design + training to complete)
    if ! test_cancel_during_phase "backtesting" $((DESIGN_WAIT_MAX + TRAINING_WAIT_MAX + BACKTEST_WAIT_MAX)); then
        FAILED=$((FAILED + 1))
    fi

    # Test 4: Cancel during assessing (requires design + training + backtest to complete)
    # This is the most expensive test - only run if explicitly requested
    log_warn "Skipping 'assessing' phase test (requires full cycle minus assessment)"
    log_info "To test assessing phase, run: $0 assessing"

    # Test 5: Trigger after cancel
    if ! test_trigger_after_cancel; then
        FAILED=$((FAILED + 1))
    fi

    # Summary
    log_header "Test Summary"
    if [ $FAILED -eq 0 ]; then
        log_success "All tests passed!"
        return 0
    else
        log_error "$FAILED test(s) failed"
        return 1
    fi
}

# Run single phase test
run_single_phase() {
    local PHASE=$1

    log_header "Agent Cancellation E2E Test - $PHASE Phase Only"

    check_backend

    case $PHASE in
        designing)
            test_cancel_during_phase "designing" $DESIGN_WAIT_MAX
            ;;
        training)
            test_cancel_during_phase "training" $((DESIGN_WAIT_MAX + TRAINING_WAIT_MAX))
            ;;
        backtesting)
            test_cancel_during_phase "backtesting" $((DESIGN_WAIT_MAX + TRAINING_WAIT_MAX + BACKTEST_WAIT_MAX))
            ;;
        assessing)
            # Full cycle minus assessment = design + training + backtest
            TOTAL_WAIT=$((DESIGN_WAIT_MAX + TRAINING_WAIT_MAX + BACKTEST_WAIT_MAX + 60))
            test_cancel_during_phase "assessing" $TOTAL_WAIT
            ;;
        *)
            log_error "Unknown phase: $PHASE"
            echo "Valid phases: designing, training, backtesting, assessing"
            exit 1
            ;;
    esac
}

# Entry point
if [ -n "$1" ]; then
    run_single_phase "$1"
else
    run_all_tests
fi
