# Test: agent/child-ops

**Purpose:** Verify child operations are created and tracked correctly
**Duration:** ~2 minutes
**Category:** Agent

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

**Test-specific checks:**
- [ ] Agent is idle before starting

---

## Execution Steps

### 1. Run Full Cycle

**Command:**
```bash
RESULT=$(curl -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/agent/trigger)
OP_ID=$(echo $RESULT | jq -r '.operation_id')
echo "Parent: $OP_ID"

# Wait for completion
while true; do
    STATUS=$(curl -s http://localhost:${KTRDR_API_PORT:-8000}/api/v1/agent/status | jq -r '.status')
    if [ "$STATUS" == "idle" ]; then
        break
    fi
    sleep 5
done
echo "Cycle complete"
```

### 2. Get Child Operation IDs

**Command:**
```bash
METADATA=$(curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$OP_ID" | jq '.data.metadata.parameters')
DESIGN_OP=$(echo $METADATA | jq -r '.design_op_id')
TRAINING_OP=$(echo $METADATA | jq -r '.training_op_id')
BACKTEST_OP=$(echo $METADATA | jq -r '.backtest_op_id')
ASSESSMENT_OP=$(echo $METADATA | jq -r '.assessment_op_id')

echo "Child operations:"
echo "  Design: $DESIGN_OP"
echo "  Training: $TRAINING_OP"
echo "  Backtest: $BACKTEST_OP"
echo "  Assessment: $ASSESSMENT_OP"
```

### 3. Verify All Child Operations Completed

**Command:**
```bash
for OP in $DESIGN_OP $TRAINING_OP $BACKTEST_OP $ASSESSMENT_OP; do
    STATUS=$(curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$OP" | jq -r '.data.status')
    echo "  $OP: $STATUS"
done
```

**Expected:**
- All child operations: status = "completed"

---

## Success Criteria

- [ ] 4 child operation IDs present
- [ ] All child operations exist
- [ ] All child operations status: "completed"

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **4 unique IDs** — Not same ID repeated
- [ ] **All completed** — Not just some
- [ ] **Parent completed** — Parent also shows completed

---

## Troubleshooting

**If child IDs missing:**
- **Cause:** Operations not stored in metadata
- **Cure:** Check orchestrator is saving child IDs

**If some children not completed:**
- **Cause:** Phase failed
- **Cure:** Check the specific child operation's error message

---

## Evidence to Capture

- Parent operation ID
- All 4 child operation IDs
- Status of each child operation
