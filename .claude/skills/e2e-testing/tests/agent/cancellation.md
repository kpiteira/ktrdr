# Test: agent/cancellation

**Purpose:** Verify cancelling parent operation cancels the active child
**Duration:** ~15 seconds
**Category:** Agent

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

**Test-specific checks:**
- [ ] Agent is idle before starting

---

## Execution Steps

### 1. Start Cycle

**Command:**
```bash
RESULT=$(curl -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/agent/trigger)
PARENT_OP=$(echo $RESULT | jq -r '.operation_id')
echo "Parent operation: $PARENT_OP"
```

### 2. Wait for Active Phase

**Command:**
```bash
sleep 5
STATUS=$(curl -s http://localhost:${KTRDR_API_PORT:-8000}/api/v1/agent/status)
CHILD_OP=$(echo $STATUS | jq -r '.child_operation_id')
PHASE=$(echo $STATUS | jq -r '.phase')
echo "Phase: $PHASE, Child: $CHILD_OP"
```

**Expected:**
- Phase is one of: designing, training, backtesting, assessing
- Child operation ID present

### 3. Cancel Parent

**Command:**
```bash
curl -s -X DELETE "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$PARENT_OP" > /dev/null
sleep 2
```

### 4. Verify Both Cancelled

**Command:**
```bash
PARENT_STATUS=$(curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$PARENT_OP" | jq -r '.data.status')
CHILD_STATUS=$(curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$CHILD_OP" | jq -r '.data.status')

echo "Parent status: $PARENT_STATUS"
echo "Child status: $CHILD_STATUS"
```

**Expected:**
- Parent status: `cancelled`
- Child status: `cancelled`

### 5. Verify Agent is Idle

**Command:**
```bash
AGENT_STATUS=$(curl -s http://localhost:${KTRDR_API_PORT:-8000}/api/v1/agent/status | jq -r '.status')
echo "Agent status: $AGENT_STATUS"
```

**Expected:**
- Agent status: `idle`

---

## Success Criteria

- [ ] Parent operation status: "cancelled"
- [ ] Child operation status: "cancelled"
- [ ] Agent returns to "idle"

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Child was active** — Child operation ID was not null
- [ ] **Both cancelled** — Not just parent
- [ ] **Agent idle** — Not stuck in active state

---

## Troubleshooting

**If child not cancelled:**
- **Cause:** Cancellation propagation bug
- **Cure:** Report bug — parent cancel should cascade

**If agent stuck in active:**
- **Cause:** Orphan state
- **Cure:** May need backend restart

---

## Evidence to Capture

- Parent operation ID
- Child operation ID
- Pre/post cancel status
