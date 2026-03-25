# Test: backtest/cancellation

**Purpose:** Verify cancellation stops backtest gracefully
**Duration:** ~15 seconds
**Category:** Backtest

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health
- [backtest](../../preflight/backtest.md) — Model, strategy, data, workers

---

## Test Data

Same as progress test (2 years of data).

---

## Execution Steps

### 1. Start Long Backtest

**Command:**
```bash
RESPONSE=$(curl -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/backtests/start \
  -H "Content-Type: application/json" \
  -d '{
    "model_path": "models/neuro_mean_reversion/1d_v21/model.pt",
    "strategy_name": "neuro_mean_reversion",
    "symbol": "EURUSD",
    "timeframe": "1d",
    "start_date": "2023-01-01",
    "end_date": "2024-12-31"
  }')

OPERATION_ID=$(echo "$RESPONSE" | jq -r '.operation_id')
```

### 2. Wait and Verify Running

**Command:**
```bash
sleep 5
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$OPERATION_ID" | \
  jq '{status:.data.status, pct:.data.progress.percentage}'
```

**Expected:**
- `status: "running"`
- `percentage: > 0`

### 3. Cancel

**Command:**
```bash
curl -s -X DELETE "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$OPERATION_ID" | jq
```

**Expected:**
- HTTP 200
- Cancellation acknowledged

### 4. Verify Cancelled

**Command:**
```bash
sleep 2
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$OPERATION_ID" | \
  jq '{status:.data.status, pct:.data.progress.percentage}'
```

**Expected:**
- `status: "cancelled"` or `"failed"`
- Progress frozen

### 5. Verify System Stability

**Command:**
```bash
# Start new backtest immediately
curl -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/backtests/start \
  -H "Content-Type: application/json" \
  -d '{
    "model_path": "models/neuro_mean_reversion/1d_v21/model.pt",
    "strategy_name": "neuro_mean_reversion",
    "symbol": "EURUSD",
    "timeframe": "1d",
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  }' | jq '{success:.success}'
```

**Expected:**
- New backtest starts without issues

---

## Success Criteria

- [ ] Backtest was running before cancel
- [ ] Cancel request succeeds
- [ ] Status changes to cancelled/failed
- [ ] Progress stops increasing
- [ ] New operations work immediately

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Was running** — percentage > 0 before cancel
- [ ] **Not completed** — Status is not "completed"
- [ ] **System stable** — New operation starts OK

---

## Evidence to Capture

- Pre-cancel status and progress
- Cancel response
- Post-cancel status
