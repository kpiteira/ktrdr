# E2E Test: cli/research-strategy-cycle

**Purpose:** Validate full end-to-end research cycle with `--strategy` flag, verifying design phase is skipped and `design_complete` flag is set correctly

**Duration:** ~2-3 minutes (with stub workers)

**Category:** CLI / Agent / Integration

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) - Docker, sandbox, API health

**Test-specific checks:**
- [ ] v3_minimal strategy exists: `ls strategies/v3_minimal.yaml`
- [ ] Agent is idle: `curl -s http://localhost:${KTRDR_API_PORT:-8000}/api/v1/agent/status | jq '.status'` returns "idle"
- [ ] USE_STUB_WORKERS is enabled (for fast testing): `docker compose exec backend printenv USE_STUB_WORKERS` returns "true"

---

## Test Data

```json
{
  "strategy": "v3_minimal",
  "expected_phases": ["designing", "training", "backtesting", "assessing"],
  "timeout_seconds": 180
}
```

**Why this data:**
- v3_minimal: Minimal valid v3 strategy, fastest possible test
- Phases: Full cycle should progress through all phases, but designing is effectively skipped (design_complete=true)
- Timeout: 3 minutes allows for worker delays with buffer

---

## Execution Steps

### 1. Verify Agent Is Idle

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

STATUS=$(curl -s "http://localhost:$API_PORT/api/v1/agent/status")
echo "Initial status: $STATUS"

AGENT_STATUS=$(echo "$STATUS" | jq -r '.status')
echo "Agent status: $AGENT_STATUS"
```

**Expected:**
- Agent status is "idle"
- No active researches

### 2. Trigger Research with --strategy Flag

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

START_TIME=$(date +%s)

# Use --strategy to skip design phase
RESPONSE=$(uv run python -m ktrdr.cli.app research --strategy v3_minimal 2>&1)
EXIT_CODE=$?

END_TIME=$(date +%s)
TRIGGER_DURATION=$((END_TIME - START_TIME))

echo "Response: $RESPONSE"
echo "Exit code: $EXIT_CODE"
echo "Trigger duration: ${TRIGGER_DURATION}s"

OPERATION_ID=$(echo "$RESPONSE" | grep -oE 'op_[a-zA-Z0-9_]+' | head -1)
echo "Operation ID: $OPERATION_ID"
```

**Expected:**
- Exit code 0
- Response contains operation ID
- Trigger duration < 3 seconds (fire-and-forget)

### 3. Verify Operation Has design_complete Flag

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Wait a moment for operation to be stored
sleep 1

OP_DETAILS=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$OPERATION_ID")
echo "Operation details: $OP_DETAILS"

# Extract design_complete flag from metadata.parameters
DESIGN_COMPLETE=$(echo "$OP_DETAILS" | jq -r '.data.metadata.parameters.design_complete // false')
echo "design_complete: $DESIGN_COMPLETE"

# Extract initial phase
INITIAL_PHASE=$(echo "$OP_DETAILS" | jq -r '.data.metadata.parameters.phase // "unknown"')
echo "Initial phase: $INITIAL_PHASE"

# Extract strategy_name
STRATEGY_NAME=$(echo "$OP_DETAILS" | jq -r '.data.metadata.parameters.strategy_name // "unknown"')
echo "Strategy name: $STRATEGY_NAME"
```

**Expected:**
- `design_complete` is `true`
- Initial phase is "designing" (but with design_complete flag, worker will skip to training)
- `strategy_name` is "v3_minimal"

### 4. Poll Until Complete (Track Phase Transitions)

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

PREV_PHASE=""
PHASES_SEEN=""
POLL_COUNT=0
MAX_POLLS=36  # 3 minutes at 5s intervals

while [ $POLL_COUNT -lt $MAX_POLLS ]; do
    STATUS=$(curl -s "http://localhost:$API_PORT/api/v1/agent/status")
    AGENT_STATUS=$(echo "$STATUS" | jq -r '.status')

    # Get phase from active_researches for our operation
    PHASE=$(echo "$STATUS" | jq -r ".active_researches[] | select(.operation_id == \"$OPERATION_ID\") | .phase // \"idle\"")

    # If no active research found, might be completed
    if [ -z "$PHASE" ] || [ "$PHASE" = "null" ]; then
        if [ "$AGENT_STATUS" = "idle" ]; then
            PHASE="completed"
        else
            PHASE="unknown"
        fi
    fi

    if [ "$PHASE" != "$PREV_PHASE" ]; then
        echo "Phase transition: $PREV_PHASE -> $PHASE"
        PHASES_SEEN="$PHASES_SEEN $PHASE"
        PREV_PHASE=$PHASE
    fi

    if [ "$PHASE" = "completed" ] || [ "$AGENT_STATUS" = "idle" ]; then
        break
    fi

    POLL_COUNT=$((POLL_COUNT + 1))
    sleep 5
done

echo "Phases observed:$PHASES_SEEN"
echo "Poll count: $POLL_COUNT"
```

**Expected:**
- Phases progress from designing (briefly) -> training -> backtesting -> assessing -> idle
- Note: designing phase is present but design_complete flag means no actual design work
- Total time < 3 minutes

### 5. Verify Design Phase Was Skipped (No Design Child Operation)

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Get final operation state
OP_FINAL=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$OPERATION_ID")
echo "Final operation: $OP_FINAL"

# Check for design_op_id - should NOT be present when design is skipped
DESIGN_OP_ID=$(echo "$OP_FINAL" | jq -r '.data.metadata.parameters.design_op_id // "none"')
echo "Design child op: $DESIGN_OP_ID"

# Check that training_op_id IS present
TRAINING_OP_ID=$(echo "$OP_FINAL" | jq -r '.data.metadata.parameters.training_op_id // "none"')
echo "Training child op: $TRAINING_OP_ID"

# Check that backtest_op_id IS present
BACKTEST_OP_ID=$(echo "$OP_FINAL" | jq -r '.data.metadata.parameters.backtest_op_id // "none"')
echo "Backtest child op: $BACKTEST_OP_ID"
```

**Expected:**
- `design_op_id` is "none" (design phase was skipped)
- `training_op_id` is present (training ran)
- `backtest_op_id` is present (backtest ran)

### 6. Verify Final Completion Status

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

OP_FINAL=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$OPERATION_ID")

STATUS=$(echo "$OP_FINAL" | jq -r '.data.status')
RESULT=$(echo "$OP_FINAL" | jq -r '.data.result_summary')

echo "Final status: $STATUS"
echo "Result summary: $RESULT"

# Extract verdict if present
VERDICT=$(echo "$OP_FINAL" | jq -r '.data.result_summary.verdict // "unknown"')
echo "Verdict: $VERDICT"
```

**Expected:**
- Status is "completed"
- Result summary contains verdict
- Strategy name matches "v3_minimal"

---

## Success Criteria

- [ ] Operation triggered successfully with --strategy flag
- [ ] `design_complete: true` flag present in operation metadata
- [ ] `strategy_name: v3_minimal` present in operation metadata
- [ ] No `design_op_id` created (design phase skipped)
- [ ] `training_op_id` created (training phase ran)
- [ ] `backtest_op_id` created (backtest phase ran)
- [ ] Phases progress: designing -> training -> backtesting -> assessing -> idle
- [ ] Final status is "completed"
- [ ] Result summary contains verdict
- [ ] Total duration < 3 minutes

---

## Sanity Checks

**CRITICAL:** These catch false positives

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| Total duration > 10s | <= 10s fails | Cycle was too fast, likely skipped phases |
| Total duration < 180s | >= 180s fails | Environment/worker issues |
| Phase count >= 3 | < 3 fails | Phases were skipped incorrectly |
| No design_op_id | design_op_id present | Design phase wasn't skipped |
| Has training_op_id | No training_op_id | Training phase didn't run |
| Status == completed | Status != completed | Cycle failed |

**Check command:**
```bash
# Verify cycle actually executed meaningful work
TRAINING_OP=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$TRAINING_OP_ID")
TRAINING_STATUS=$(echo "$TRAINING_OP" | jq -r '.data.status')
[ "$TRAINING_STATUS" = "completed" ] && echo "OK: Training completed" || echo "FAIL: Training status = $TRAINING_STATUS"
```

---

## Troubleshooting

**If design_op_id is present:**
- **Cause:** design_complete flag not checked in research_worker
- **Cure:** Check `_handle_designing_phase()` for design_complete check

**If stuck in designing phase:**
- **Cause:** Worker availability check failing
- **Cure:** Check `_is_training_worker_available()` returns true, verify stub workers registered

**If cycle times out:**
- **Cause:** Stub worker delays too long, or workers not started
- **Cure:** Check USE_STUB_WORKERS=true, check STUB_WORKER_FAST=true for faster tests

**If final status is "failed":**
- **Cause:** Strategy validation failed or worker error
- **Cure:** Check operation error_message, check backend logs

**If verdict is null:**
- **Cause:** Assessment phase didn't complete
- **Cure:** Check if backtest completed, check assessment worker

---

## Notes for Implementation

- **Stub workers are required** for fast, deterministic testing. Set `USE_STUB_WORKERS=true` in backend environment.
- **STUB_WORKER_FAST=true** can reduce stub delays from 30s to 500ms per phase for faster testing.
- The test verifies the **absence** of `design_op_id` which proves design was skipped. This is the key validation.
- Phase transitions may be fast with stubs - capture all phases seen for debugging.
- The `design_complete` flag in metadata is the mechanism that tells the research worker to skip design.

---

## Evidence to Capture

- Operation ID
- design_complete flag value
- All phase transitions observed
- Child operation IDs (training_op_id, backtest_op_id)
- Final status and verdict
- Total cycle duration
