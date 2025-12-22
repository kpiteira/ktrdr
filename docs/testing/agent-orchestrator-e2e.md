# Agent Orchestrator E2E Testing Guide

This document provides comprehensive end-to-end tests for the agent research orchestrator. Use these tests to verify the system is working correctly after changes.

## Prerequisites

- Backend running: `docker compose up -d`
- Backend healthy: `curl -sf http://localhost:8000/api/v1/health`

## Quick Smoke Test

Fast check that the system is operational (< 5 seconds):

```bash
# Check backend health
curl -sf http://localhost:8000/api/v1/health | jq

# Check agent status (should be idle or active)
curl -s http://localhost:8000/api/v1/agent/status | jq
```

---

## Test 1: Full Cycle Completion

**Purpose**: Verify all 4 phases complete successfully (designing → training → backtesting → assessing)

**Duration**: ~2 minutes with default 30s stub delays

```bash
#!/bin/bash
echo "=== Test 1: Full Cycle Completion ==="

# Trigger cycle
RESULT=$(curl -s -X POST http://localhost:8000/api/v1/agent/trigger)
OP_ID=$(echo $RESULT | jq -r '.operation_id')
echo "Started operation: $OP_ID"

# Poll until complete
PREV_PHASE=""
while true; do
    STATUS=$(curl -s http://localhost:8000/api/v1/agent/status)
    PHASE=$(echo $STATUS | jq -r '.phase // .status')
    CHILD=$(echo $STATUS | jq -r '.child_operation_id // "none"')

    if [ "$PHASE" != "$PREV_PHASE" ]; then
        echo "Phase: $PHASE (child: $CHILD)"
        PREV_PHASE=$PHASE
    fi

    if [ "$PHASE" == "idle" ]; then
        break
    fi
    sleep 2
done

# Verify completion
OP_STATUS=$(curl -s "http://localhost:8000/api/v1/operations/$OP_ID" | jq -r '.data.status')
RESULT_VERDICT=$(curl -s "http://localhost:8000/api/v1/operations/$OP_ID" | jq -r '.data.result_summary.verdict')

echo ""
echo "=== Results ==="
echo "Operation status: $OP_STATUS"
echo "Verdict: $RESULT_VERDICT"

if [ "$OP_STATUS" == "completed" ] && [ "$RESULT_VERDICT" == "promising" ]; then
    echo "✅ PASS: Full cycle completed successfully"
else
    echo "❌ FAIL: Expected completed/promising, got $OP_STATUS/$RESULT_VERDICT"
    exit 1
fi
```

**Expected Results**:
- Phases progress: idle → designing → training → backtesting → assessing → idle
- Operation status: `completed`
- Result verdict: `promising` (from stub)
- `child_operation_id` shown during each active phase

---

## Test 2: Duplicate Trigger Rejection

**Purpose**: Verify only one cycle can run at a time

**Duration**: ~5 seconds

```bash
#!/bin/bash
echo "=== Test 2: Duplicate Trigger Rejection ==="

# Start first cycle
RESULT1=$(curl -s -X POST http://localhost:8000/api/v1/agent/trigger)
TRIGGERED1=$(echo $RESULT1 | jq -r '.triggered')
OP_ID=$(echo $RESULT1 | jq -r '.operation_id')

if [ "$TRIGGERED1" != "true" ]; then
    echo "❌ FAIL: First trigger should succeed"
    exit 1
fi
echo "First trigger: success (op: $OP_ID)"

# Wait for cycle to start
sleep 2

# Try second trigger
RESULT2=$(curl -s -X POST http://localhost:8000/api/v1/agent/trigger)
TRIGGERED2=$(echo $RESULT2 | jq -r '.triggered')
REASON=$(echo $RESULT2 | jq -r '.reason')

if [ "$TRIGGERED2" == "false" ] && [ "$REASON" == "active_cycle_exists" ]; then
    echo "Second trigger: rejected (reason: $REASON)"
    echo "✅ PASS: Duplicate trigger rejected correctly"
else
    echo "❌ FAIL: Second trigger should be rejected with active_cycle_exists"
    exit 1
fi

# Cancel the running cycle for cleanup
curl -s -X DELETE "http://localhost:8000/api/v1/operations/$OP_ID" > /dev/null
echo "Cleaned up: cancelled $OP_ID"
```

**Expected Results**:
- First trigger: `triggered: true`
- Second trigger: `triggered: false, reason: "active_cycle_exists"`

---

## Test 3: Cancellation Propagation

**Purpose**: Verify cancelling parent operation cancels the active child

**Duration**: ~10 seconds per phase tested

### 3a: Cancel During Designing

```bash
#!/bin/bash
echo "=== Test 3a: Cancel During Designing ==="

# Start cycle
RESULT=$(curl -s -X POST http://localhost:8000/api/v1/agent/trigger)
PARENT_OP=$(echo $RESULT | jq -r '.operation_id')
echo "Parent operation: $PARENT_OP"

# Wait for designing phase
sleep 3
STATUS=$(curl -s http://localhost:8000/api/v1/agent/status)
CHILD_OP=$(echo $STATUS | jq -r '.child_operation_id')
echo "Child operation: $CHILD_OP"

# Cancel parent
curl -s -X DELETE "http://localhost:8000/api/v1/operations/$PARENT_OP" > /dev/null
sleep 2

# Verify both cancelled
PARENT_STATUS=$(curl -s "http://localhost:8000/api/v1/operations/$PARENT_OP" | jq -r '.data.status')
CHILD_STATUS=$(curl -s "http://localhost:8000/api/v1/operations/$CHILD_OP" | jq -r '.data.status')

echo "Parent status: $PARENT_STATUS"
echo "Child status: $CHILD_STATUS"

if [ "$PARENT_STATUS" == "cancelled" ] && [ "$CHILD_STATUS" == "cancelled" ]; then
    echo "✅ PASS: Both parent and child cancelled"
else
    echo "❌ FAIL: Expected both cancelled"
    exit 1
fi
```

### 3b: Cancel During Training

```bash
#!/bin/bash
echo "=== Test 3b: Cancel During Training ==="

# Start cycle
RESULT=$(curl -s -X POST http://localhost:8000/api/v1/agent/trigger)
PARENT_OP=$(echo $RESULT | jq -r '.operation_id')
echo "Parent operation: $PARENT_OP"

# Wait for training phase (~32 seconds)
echo "Waiting for training phase..."
while true; do
    STATUS=$(curl -s http://localhost:8000/api/v1/agent/status)
    PHASE=$(echo $STATUS | jq -r '.phase')
    if [ "$PHASE" == "training" ]; then
        CHILD_OP=$(echo $STATUS | jq -r '.child_operation_id')
        echo "Reached training phase. Child: $CHILD_OP"
        break
    fi
    sleep 2
done

# Cancel parent
curl -s -X DELETE "http://localhost:8000/api/v1/operations/$PARENT_OP" > /dev/null
sleep 2

# Verify both cancelled
PARENT_STATUS=$(curl -s "http://localhost:8000/api/v1/operations/$PARENT_OP" | jq -r '.data.status')
CHILD_STATUS=$(curl -s "http://localhost:8000/api/v1/operations/$CHILD_OP" | jq -r '.data.status')

echo "Parent status: $PARENT_STATUS"
echo "Child status: $CHILD_STATUS"

if [ "$PARENT_STATUS" == "cancelled" ] && [ "$CHILD_STATUS" == "cancelled" ]; then
    echo "✅ PASS: Both parent and training child cancelled"
else
    echo "❌ FAIL: Expected both cancelled"
    exit 1
fi
```

### 3c: Cancel During Backtesting

Similar pattern - wait for backtesting phase (~64 seconds), then cancel.

**Expected Results** (all cancellation tests):
- Parent operation status: `cancelled`
- Child operation status: `cancelled`
- Agent status returns to: `idle`

---

## Test 4: Status API Contract

**Purpose**: Verify status response includes all required fields

```bash
#!/bin/bash
echo "=== Test 4: Status API Contract ==="

# Start cycle
RESULT=$(curl -s -X POST http://localhost:8000/api/v1/agent/trigger)
OP_ID=$(echo $RESULT | jq -r '.operation_id')
sleep 3

# Check active status fields
STATUS=$(curl -s http://localhost:8000/api/v1/agent/status)
echo "Active status response:"
echo $STATUS | jq

# Verify required fields
HAS_STATUS=$(echo $STATUS | jq 'has("status")')
HAS_OP_ID=$(echo $STATUS | jq 'has("operation_id")')
HAS_PHASE=$(echo $STATUS | jq 'has("phase")')
HAS_CHILD_OP=$(echo $STATUS | jq 'has("child_operation_id")')

if [ "$HAS_STATUS" == "true" ] && [ "$HAS_OP_ID" == "true" ] && \
   [ "$HAS_PHASE" == "true" ] && [ "$HAS_CHILD_OP" == "true" ]; then
    echo "✅ PASS: All required fields present"
else
    echo "❌ FAIL: Missing required fields"
    echo "  status: $HAS_STATUS, operation_id: $HAS_OP_ID"
    echo "  phase: $HAS_PHASE, child_operation_id: $HAS_CHILD_OP"
    exit 1
fi

# Cleanup
curl -s -X DELETE "http://localhost:8000/api/v1/operations/$OP_ID" > /dev/null
```

**Expected Fields** (when active):
- `status`: "active"
- `operation_id`: parent operation ID
- `phase`: current phase name
- `child_operation_id`: current child operation ID
- `progress`: progress object (may be null)
- `strategy_name`: set after design phase completes
- `started_at`: ISO timestamp

---

## Test 5: Metadata Storage

**Purpose**: Verify parent operation stores results from each phase

```bash
#!/bin/bash
echo "=== Test 5: Metadata Storage ==="

# Run full cycle
RESULT=$(curl -s -X POST http://localhost:8000/api/v1/agent/trigger)
OP_ID=$(echo $RESULT | jq -r '.operation_id')
echo "Started operation: $OP_ID"

# Wait for completion
while true; do
    STATUS=$(curl -s http://localhost:8000/api/v1/agent/status | jq -r '.status')
    if [ "$STATUS" == "idle" ]; then
        break
    fi
    sleep 5
done

# Check metadata
METADATA=$(curl -s "http://localhost:8000/api/v1/operations/$OP_ID" | jq '.data.metadata.parameters')
echo "Parent metadata:"
echo $METADATA | jq

# Verify required fields
HAS_STRATEGY=$(echo $METADATA | jq 'has("strategy_name")')
HAS_TRAINING=$(echo $METADATA | jq 'has("training_result")')
HAS_BACKTEST=$(echo $METADATA | jq 'has("backtest_result")')
HAS_VERDICT=$(echo $METADATA | jq 'has("assessment_verdict")')

echo ""
echo "=== Metadata Verification ==="
echo "strategy_name: $HAS_STRATEGY"
echo "training_result: $HAS_TRAINING"
echo "backtest_result: $HAS_BACKTEST"
echo "assessment_verdict: $HAS_VERDICT"

if [ "$HAS_STRATEGY" == "true" ] && [ "$HAS_TRAINING" == "true" ] && \
   [ "$HAS_BACKTEST" == "true" ] && [ "$HAS_VERDICT" == "true" ]; then
    echo "✅ PASS: All metadata stored correctly"
else
    echo "❌ FAIL: Missing metadata fields"
    exit 1
fi
```

**Expected Metadata** (after completion):
- `strategy_name`: from design phase
- `strategy_path`: from design phase
- `training_result`: full training metrics
- `model_path`: from training phase
- `backtest_result`: full backtest metrics
- `assessment_verdict`: from assessment phase

---

## Test 6: Child Operation IDs

**Purpose**: Verify child operations are created and tracked correctly

```bash
#!/bin/bash
echo "=== Test 6: Child Operation IDs ==="

# Run full cycle
RESULT=$(curl -s -X POST http://localhost:8000/api/v1/agent/trigger)
OP_ID=$(echo $RESULT | jq -r '.operation_id')
echo "Parent: $OP_ID"

# Wait for completion
while true; do
    STATUS=$(curl -s http://localhost:8000/api/v1/agent/status | jq -r '.status')
    if [ "$STATUS" == "idle" ]; then
        break
    fi
    sleep 5
done

# Get child operation IDs from metadata
METADATA=$(curl -s "http://localhost:8000/api/v1/operations/$OP_ID" | jq '.data.metadata.parameters')
DESIGN_OP=$(echo $METADATA | jq -r '.design_op_id')
TRAINING_OP=$(echo $METADATA | jq -r '.training_op_id')
BACKTEST_OP=$(echo $METADATA | jq -r '.backtest_op_id')
ASSESSMENT_OP=$(echo $METADATA | jq -r '.assessment_op_id')

echo "Child operations:"
echo "  Design: $DESIGN_OP"
echo "  Training: $TRAINING_OP"
echo "  Backtest: $BACKTEST_OP"
echo "  Assessment: $ASSESSMENT_OP"

# Verify all exist and completed
ALL_PASS=true
for OP in $DESIGN_OP $TRAINING_OP $BACKTEST_OP $ASSESSMENT_OP; do
    STATUS=$(curl -s "http://localhost:8000/api/v1/operations/$OP" | jq -r '.data.status')
    if [ "$STATUS" != "completed" ]; then
        echo "❌ $OP status: $STATUS (expected: completed)"
        ALL_PASS=false
    fi
done

if [ "$ALL_PASS" == "true" ]; then
    echo "✅ PASS: All child operations completed"
else
    echo "❌ FAIL: Some child operations not completed"
    exit 1
fi
```

---

## Quick Reference: API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/agent/trigger` | POST | Start new research cycle |
| `/api/v1/agent/status` | GET | Get current agent status |
| `/api/v1/operations/{id}` | GET | Get operation details |
| `/api/v1/operations/{id}` | DELETE | Cancel operation |
| `/api/v1/health` | GET | Backend health check |

---

## Timing Reference

With default 30s stub delays:

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Designing | ~30s | 30s |
| Training | ~30s | 60s |
| Backtesting | ~30s | 90s |
| Assessing | ~30s | 120s |

For faster testing, set `STUB_WORKER_FAST=true` in the backend environment (500ms per phase).

---

## Troubleshooting

### Cycle stuck in a phase
```bash
# Check backend logs
docker compose logs backend --since 5m | grep -i error

# Check operation status
curl -s http://localhost:8000/api/v1/operations/{OP_ID} | jq
```

### Cancellation not working
```bash
# Verify operation is cancellable
curl -s http://localhost:8000/api/v1/operations/{OP_ID} | jq '.data.status'
# Must be "pending" or "running" to cancel
```

### Status shows wrong phase
```bash
# Check if there's an orphan operation
curl -s http://localhost:8000/api/v1/operations | jq '.data[] | select(.status == "running")'
```
