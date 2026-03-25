# Test: training/cancellation

**Purpose:** Validate operation cancellation during training
**Duration:** ~30 seconds
**Category:** Training

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

**Test-specific checks:**
- [ ] Strategy file exists: `~/.ktrdr/shared/strategies/test_e2e_local_pull.yaml`
- [ ] Data available: EURUSD 5m has sufficient data (2+ years)

---

## Test Data

```json
{
  "symbols": ["EURUSD"],
  "timeframes": ["5m"],
  "strategy_name": "test_e2e_local_pull",
  "start_date": "2023-01-01",
  "end_date": "2025-01-01"
}
```

**Why this data:**
- Same as progress test — long enough training to cancel mid-execution
- 2 years of 5m data takes ~60s to train, plenty of time to cancel

---

## Execution Steps

### 1. Start Training

**Command:**
```bash
RESPONSE=$(curl -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/trainings/start \
  -H "Content-Type: application/json" \
  -d '{"symbols":["EURUSD"],"timeframes":["5m"],"strategy_name":"test_e2e_local_pull","start_date":"2023-01-01","end_date":"2025-01-01"}')

TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id')
echo "Task ID: $TASK_ID"
```

**Expected:**
- HTTP 200
- `task_id` returned

### 2. Wait and Verify Running

**Command:**
```bash
sleep 10
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$TASK_ID" | \
  jq '{status:.data.status, percentage:.data.progress.percentage}'
```

**Expected:**
- `status: "running"`
- `percentage: > 0` (some progress made)

### 3. Cancel Operation

**Command:**
```bash
curl -s -X DELETE "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$TASK_ID" | jq
```

**Expected:**
- HTTP 200
- Response indicates cancellation accepted

### 4. Verify Cancellation

**Command:**
```bash
sleep 2
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$TASK_ID" | \
  jq '{status:.data.status, percentage:.data.progress.percentage}'
```

**Expected:**
- `status: "failed"` (known quirk — cancelled operations show as failed)
- Progress frozen at cancellation point

### 5. Verify System Stability

**Command:**
```bash
# Start a new training immediately to verify system is stable
NEW_RESPONSE=$(curl -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/trainings/start \
  -H "Content-Type: application/json" \
  -d '{"symbols":["EURUSD"],"timeframes":["1d"],"strategy_name":"test_e2e_local_pull","start_date":"2024-01-01","end_date":"2024-12-31"}')

echo "$NEW_RESPONSE" | jq '{success:.success, task_id:.task_id}'
```

**Expected:**
- New training starts successfully
- No resource leaks from cancelled operation

---

## Success Criteria

- [ ] Training starts successfully
- [ ] Training is running after 10s (not already complete)
- [ ] Cancel request succeeds (HTTP 200)
- [ ] Operation status changes to failed/cancelled
- [ ] Progress stops increasing after cancellation
- [ ] New operations can start immediately after

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Was actually running** — Percentage > 0 before cancel (verify we didn't cancel after completion)
- [ ] **Cancel was effective** — Status is not "completed" after cancel
- [ ] **System is stable** — New operation starts without errors

**Check command:**
```bash
# Verify the cancelled operation is not "completed"
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$TASK_ID" | \
  jq '{status:.data.status}'
```

**Expected:** `status` should be `"failed"` or `"cancelled"`, NOT `"completed"`

---

## Troubleshooting

**If operation completes before cancel:**
- **Cause:** Dataset too small, training finished too fast
- **Cure:** Use larger dataset or reduce wait time before cancel

**If cancel returns 404:**
- **Cause:** Operation already completed or ID incorrect
- **Cure:** Verify task_id is correct, increase cancel speed

**If status shows "cancelled" not "failed":**
- **Note:** This is acceptable — the status name is a known inconsistency
- **Both "failed" and "cancelled" indicate successful cancellation

**If new operation fails to start:**
- **Cause:** Resource leak from cancelled operation
- **Cure:** Check backend logs for cleanup errors, may need container restart

---

## Known Quirks

**Status inconsistency:** Cancel endpoint returns `"cancelled"` but final operation status shows `"failed"`. This is documented behavior, not a bug.

---

## Evidence to Capture

- Operation ID: `$TASK_ID`
- Pre-cancel status: Save output from step 2
- Cancel response: Save output from step 3
- Post-cancel status: Save output from step 4
- Logs: `docker compose logs backend --since 5m | grep -E "cancel|$TASK_ID"`
