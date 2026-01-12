# Test: agent/full-cycle

**Purpose:** Verify all 4 phases complete successfully (designing → training → backtesting → assessing)
**Duration:** ~2 minutes (with default 30s stub delays)
**Category:** Agent

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

**Test-specific checks:**
- [ ] Agent is idle: `curl -s http://localhost:${KTRDR_API_PORT:-8000}/api/v1/agent/status | jq '.status'` returns "idle"

---

## Execution Steps

### 1. Trigger Cycle

**Command:**
```bash
RESULT=$(curl -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/agent/trigger)
OP_ID=$(echo $RESULT | jq -r '.operation_id')
echo "Started operation: $OP_ID"
```

**Expected:**
- `triggered: true`
- `operation_id` returned

### 2. Poll Until Complete

**Command:**
```bash
PREV_PHASE=""
while true; do
    STATUS=$(curl -s http://localhost:${KTRDR_API_PORT:-8000}/api/v1/agent/status)
    PHASE=$(echo $STATUS | jq -r '.phase // .status')
    CHILD=$(echo $STATUS | jq -r '.child_operation_id // "none"')

    if [ "$PHASE" != "$PREV_PHASE" ]; then
        echo "Phase: $PHASE (child: $CHILD)"
        PREV_PHASE=$PHASE
    fi

    if [ "$PHASE" == "idle" ]; then
        break
    fi
    sleep 5
done
```

**Expected:**
- Phases progress: idle → designing → training → backtesting → assessing → idle

### 3. Verify Completion

**Command:**
```bash
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$OP_ID" | \
  jq '{status:.data.status, verdict:.data.result_summary.verdict}'
```

**Expected:**
- `status: "completed"`
- `verdict: "promising"` (from stub)

---

## Success Criteria

- [ ] Phases progress correctly through all 4 phases
- [ ] Operation status: "completed"
- [ ] Result verdict present
- [ ] child_operation_id shown during each active phase

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **All phases observed** — Not just idle → idle
- [ ] **Child operations created** — Different child IDs for each phase
- [ ] **Completed not failed** — Status is exactly "completed"

---

## Troubleshooting

**If stuck in a phase:**
- **Cause:** Worker stub timeout or error
- **Cure:** Check logs: `docker compose logs backend --since 5m | grep -i error`

**If verdict is null:**
- **Cause:** Assessment phase didn't complete
- **Cure:** Check if all child operations completed

---

## Notes

For faster testing, set `STUB_WORKER_FAST=true` in backend env (500ms per phase instead of 30s).

---

## Evidence to Capture

- Operation ID
- Phase transition log
- Final status and verdict
