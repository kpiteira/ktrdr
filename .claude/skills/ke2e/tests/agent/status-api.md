# Test: agent/status-api

**Purpose:** Verify status response includes all required fields
**Duration:** ~10 seconds
**Category:** Agent

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

---

## Execution Steps

### 1. Check Idle Status

**Command:**
```bash
STATUS=$(curl -s http://localhost:${KTRDR_API_PORT:-8000}/api/v1/agent/status)
echo "Idle status:"
echo $STATUS | jq
```

**Expected:**
- `status: "idle"`
- `last_cycle` field present (may be null)

### 2. Start Cycle and Check Active Status

**Command:**
```bash
RESULT=$(curl -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/agent/trigger)
OP_ID=$(echo $RESULT | jq -r '.operation_id')
sleep 3

STATUS=$(curl -s http://localhost:${KTRDR_API_PORT:-8000}/api/v1/agent/status)
echo "Active status:"
echo $STATUS | jq
```

### 3. Verify Required Fields

**Command:**
```bash
HAS_STATUS=$(echo $STATUS | jq 'has("status")')
HAS_OP_ID=$(echo $STATUS | jq 'has("operation_id")')
HAS_PHASE=$(echo $STATUS | jq 'has("phase")')
HAS_CHILD_OP=$(echo $STATUS | jq 'has("child_operation_id")')

echo "status field: $HAS_STATUS"
echo "operation_id field: $HAS_OP_ID"
echo "phase field: $HAS_PHASE"
echo "child_operation_id field: $HAS_CHILD_OP"
```

**Expected:**
- All fields present: true

### 4. Cleanup

**Command:**
```bash
curl -s -X DELETE "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$OP_ID" > /dev/null
```

---

## Success Criteria

- [ ] Idle status has `status` field
- [ ] Active status has all required fields:
  - `status`
  - `operation_id`
  - `phase`
  - `child_operation_id`
  - `progress` (may be null)
  - `started_at`

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Fields exist** — Not null keys, actual has() check
- [ ] **Values reasonable** — Status is "active" when running
- [ ] **Phase valid** — One of: designing, training, backtesting, assessing

---

## Troubleshooting

**If fields missing:**
- **Cause:** API schema changed
- **Cure:** Check API docs, update expected fields

---

## Evidence to Capture

- Idle status response
- Active status response
- Field verification results
