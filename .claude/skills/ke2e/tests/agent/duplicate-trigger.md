# Test: agent/duplicate-trigger

**Purpose:** Verify only one cycle can run at a time
**Duration:** ~10 seconds
**Category:** Agent

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

**Test-specific checks:**
- [ ] Agent is idle before starting

---

## Execution Steps

### 1. Start First Cycle

**Command:**
```bash
RESULT1=$(curl -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/agent/trigger)
TRIGGERED1=$(echo $RESULT1 | jq -r '.triggered')
OP_ID=$(echo $RESULT1 | jq -r '.operation_id')
echo "First trigger: triggered=$TRIGGERED1, op=$OP_ID"
```

**Expected:**
- `triggered: true`
- `operation_id` returned

### 2. Wait for Cycle to Start

**Command:**
```bash
sleep 3
```

### 3. Try Second Trigger

**Command:**
```bash
RESULT2=$(curl -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/agent/trigger)
TRIGGERED2=$(echo $RESULT2 | jq -r '.triggered')
REASON=$(echo $RESULT2 | jq -r '.reason')
echo "Second trigger: triggered=$TRIGGERED2, reason=$REASON"
```

**Expected:**
- `triggered: false`
- `reason: "active_cycle_exists"`

### 4. Cleanup

**Command:**
```bash
curl -s -X DELETE "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$OP_ID" > /dev/null
echo "Cleaned up: cancelled $OP_ID"
```

---

## Success Criteria

- [ ] First trigger: `triggered: true`
- [ ] Second trigger: `triggered: false`
- [ ] Reason: `"active_cycle_exists"`

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **First succeeded** — First trigger returned operation_id
- [ ] **Second rejected** — Not both succeeded (race condition bug)
- [ ] **Correct reason** — Reason is "active_cycle_exists" not "error"

---

## Troubleshooting

**If both triggers succeed:**
- **Cause:** Race condition in agent orchestrator
- **Cure:** Report bug — should never allow concurrent cycles

**If first trigger fails:**
- **Cause:** Previous cycle still running
- **Cure:** Wait for idle state before testing

---

## Evidence to Capture

- First trigger response
- Second trigger response
