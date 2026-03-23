# Test: cli/operations-workflow

**Purpose:** Validate all CLI operation commands work end-to-end: backtest start, ops list, status, follow, cancel
**Duration:** ~90 seconds
**Category:** CLI / Restructure

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health
- [backtest](../../preflight/backtest.md) — Model, strategy, data, workers

**Test-specific checks:**
- [ ] Test strategy exists: `neuro_mean_reversion` or `test_e2e_local_pull`
- [ ] Data available: EURUSD 1d
- [ ] No conflicting operations running

---

## Test Data

```json
{
  "strategy": "neuro_mean_reversion",
  "symbol": "EURUSD",
  "timeframe": "1d",
  "start_date": "2024-01-01",
  "end_date": "2024-06-01",
  "capital": 100000
}
```

**Why this data:**
- 6 months daily (~120 bars): Long enough for progress, completes in reasonable time
- Known-good strategy that exists in test environments

---

## Execution Steps

### 1. Start Backtest via CLI

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Start backtest in background
uv run ktrdr backtest neuro_mean_reversion \
  --start-date 2024-01-01 \
  --end-date 2024-06-01 \
  --capital 100000 &
BG_PID=$!

sleep 5

# Get operation ID from API
OPERATION_ID=$(curl -s "http://localhost:$API_PORT/api/v1/operations?operation_type=backtesting&limit=1" | \
  jq -r '.data[0].operation_id')

echo "Started operation: $OPERATION_ID"
echo "Background PID: $BG_PID"
```

**Expected:**
- Command starts without error
- Operation ID can be retrieved from API

### 2. List Operations

**Command:**
```bash
uv run ktrdr ops
```

**Expected:**
- Table output with headers (Operation ID, Type, Status, etc.)
- New operation appears in list
- Status shows "RUNNING" or "PENDING"
- Proper table formatting

### 3. Check Operation Status

**Command:**
```bash
uv run ktrdr status $OPERATION_ID
```

**Expected:**
- Detailed status display:
  - Operation ID
  - Type: backtesting
  - Status: running
  - Progress percentage
  - Created timestamp

### 4. Follow Operation Progress

**Command:**
```bash
for i in {1..6}; do
  echo "--- Poll $i ---"
  uv run ktrdr status $OPERATION_ID 2>&1 | grep -E "Status|Progress|Percentage"
  sleep 5
done
```

**Expected:**
- Progress percentage increases across polls
- Status remains "running" during execution
- Eventually reaches "completed"

### 5. Start Second Backtest (for Cancel Test)

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Start longer backtest
uv run ktrdr backtest neuro_mean_reversion \
  --start-date 2023-01-01 \
  --end-date 2024-06-01 \
  --capital 100000 &

sleep 5

CANCEL_OP_ID=$(curl -s "http://localhost:$API_PORT/api/v1/operations?operation_type=backtesting&status=running&limit=1" | \
  jq -r '.data[0].operation_id')

echo "Operation to cancel: $CANCEL_OP_ID"
```

**Expected:**
- Second backtest starts successfully
- Can identify new running operation

### 6. Cancel Operation

**Command:**
```bash
uv run ktrdr cancel $CANCEL_OP_ID
```

**Expected:**
- Success message: "Successfully cancelled operation: op_..."
- No error messages

### 7. Verify Cancellation and Completion

**Command:**
```bash
# Verify cancelled operation status
uv run ktrdr status $CANCEL_OP_ID

# Wait for first operation and verify
sleep 30
uv run ktrdr status $OPERATION_ID
```

**Expected:**
- Cancelled operation: status FAILED or CANCELLED
- First operation: status COMPLETED
- Results present for completed operation

---

## Success Criteria

- [ ] `ktrdr backtest` starts operation successfully
- [ ] `ktrdr ops` displays operations in table format
- [ ] `ktrdr status <op-id>` displays operation details
- [ ] Progress tracking shows changes over time
- [ ] `ktrdr cancel <op-id>` cancels running operation
- [ ] Cancelled operation status changes to failed/cancelled
- [ ] Original operation completes with status "completed"
- [ ] Output formatting is correct (Rich tables render)

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Progress updates >= 2** — Progress being tracked
- [ ] **Duration > 5s** — Backtest actually ran
- [ ] **Table has columns** — Rich formatting works
- [ ] **Cancel changes status** — Cancel working
- [ ] **Final status is terminal** — Operation not stuck

**Check command:**
```bash
curl -s "http://localhost:$API_PORT/api/v1/operations/$OPERATION_ID" | \
  jq '{status:.data.status, pct:.data.progress.percentage}'
```

---

## Troubleshooting

**If command not found:**
- **Cause:** CLI not installed properly
- **Cure:** Check `uv run ktrdr --help`

**If connection refused:**
- **Cause:** Docker not running
- **Cure:** `docker compose up -d`

**If no operations listed:**
- **Cause:** API endpoint issue
- **Cure:** Check `curl localhost:8000/api/v1/operations`

**If cancel returns error:**
- **Cause:** Operation already completed or not found
- **Cure:** Verify operation ID and status before cancelling

**If progress never updates:**
- **Cause:** Progress reporting broken
- **Cure:** Check backtest worker logs

---

## Cleanup

```bash
# Cancel any operations still running
for op_id in $OPERATION_ID $CANCEL_OP_ID; do
  STATUS=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$op_id" | jq -r '.data.status')
  if [ "$STATUS" = "running" ]; then
    curl -s -X DELETE "http://localhost:$API_PORT/api/v1/operations/$op_id"
  fi
done
```

---

## Evidence to Capture

- Operation IDs (both)
- List output
- Status outputs
- Progress snapshots
- Cancel output
- Final statuses
