#!/bin/bash
# v2.0 Memory Foundation E2E Test
# Tests that experiments are saved to memory after assessment
#
# Prerequisites:
# - Docker compose running (docker compose up -d)
# - Training and backtest workers available
# - Memory directory mounted (./memory:/app/memory in docker-compose.yml)
#
# Usage:
#   ./scripts/e2e_v2_memory.sh

set -e

API_URL="${KTRDR_API_URL:-http://localhost:8000}"
MEMORY_DIR="${MEMORY_DIR:-memory}"

echo "=== v2.0 Memory Foundation E2E Test ==="
echo ""

# Check prerequisites
echo "Checking prerequisites..."
if ! curl -s "$API_URL/api/v1/workers" | jq -e 'length > 0' > /dev/null 2>&1; then
    echo "❌ No workers available. Start workers first:"
    echo "   docker compose up -d training-worker-1 backtest-worker-1"
    exit 1
fi
echo "✅ Workers available"

if [ ! -d "$MEMORY_DIR/experiments" ]; then
    echo "❌ Memory directory not found: $MEMORY_DIR/experiments"
    echo "   Create it: mkdir -p $MEMORY_DIR/experiments"
    exit 1
fi
echo "✅ Memory directory exists"

# Capture initial state
INITIAL_COUNT=$(ls "$MEMORY_DIR/experiments/" | wc -l | tr -d ' ')
echo ""
echo "Initial experiments: $INITIAL_COUNT"

# Trigger research cycle
echo ""
echo "Triggering research cycle (haiku model, bypassing gates)..."
TRIGGER_RESULT=$(curl -s -X POST "$API_URL/api/v1/agent/trigger" \
    -H "Content-Type: application/json" \
    -d '{"model": "haiku", "bypass_gates": true}')

TRIGGERED=$(echo "$TRIGGER_RESULT" | jq -r '.triggered')
OP_ID=$(echo "$TRIGGER_RESULT" | jq -r '.operation_id')

if [ "$TRIGGERED" != "true" ]; then
    echo "❌ Failed to trigger cycle: $TRIGGER_RESULT"
    exit 1
fi
echo "✅ Cycle triggered: $OP_ID"

# Poll for completion
echo ""
echo "Polling for completion (timeout: 10 minutes)..."
MAX_POLLS=60
POLL_INTERVAL=10

for i in $(seq 1 $MAX_POLLS); do
    STATUS=$(curl -s "$API_URL/api/v1/agent/status" | jq -r '.status')
    PHASE=$(curl -s "$API_URL/api/v1/agent/status" | jq -r '.phase // "idle"')

    if [ "$STATUS" = "idle" ]; then
        echo "✅ Cycle completed"
        break
    fi

    echo "  Poll $i: status=$STATUS, phase=$PHASE"
    sleep $POLL_INTERVAL
done

if [ "$STATUS" != "idle" ]; then
    echo "❌ Timeout waiting for cycle completion"
    exit 1
fi

# Check operation result
echo ""
echo "Checking operation result..."
OP_RESULT=$(curl -s "$API_URL/api/v1/operations/$OP_ID")
OP_STATUS=$(echo "$OP_RESULT" | jq -r '.data.status')
OP_ERROR=$(echo "$OP_RESULT" | jq -r '.data.error_message // "none"')

if [ "$OP_STATUS" != "completed" ]; then
    echo "❌ Operation failed: $OP_ERROR"
    exit 1
fi
echo "✅ Operation completed successfully"

# Verify memory was updated
echo ""
echo "Verifying memory update..."
FINAL_COUNT=$(ls "$MEMORY_DIR/experiments/" | wc -l | tr -d ' ')
echo "Final experiments: $FINAL_COUNT"

if [ "$FINAL_COUNT" -gt "$INITIAL_COUNT" ]; then
    echo "✅ New experiment saved to memory"

    # Show the new experiment
    LATEST=$(ls -t "$MEMORY_DIR/experiments/" | head -1)
    echo ""
    echo "Latest experiment: $LATEST"
    echo "Content preview:"
    head -20 "$MEMORY_DIR/experiments/$LATEST"
else
    echo "❌ No new experiment created"
    echo ""
    echo "Checking logs for errors..."
    docker logs ktrdr2-backend-1 --since 10m 2>&1 | grep -iE "memory|error" | tail -10
    exit 1
fi

echo ""
echo "=== v2.0 E2E Test PASSED ==="
