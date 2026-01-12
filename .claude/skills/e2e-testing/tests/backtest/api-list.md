# Test: backtest/api-list

**Purpose:** Verify DELETE endpoint cancellation via API
**Duration:** ~10 seconds
**Category:** Backtest (Integration)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health
- [backtest](../../preflight/backtest.md) — Model, strategy, data, workers

---

## Execution Steps

### 1. Start Long Backtest

**Command:**
```bash
RESPONSE=$(curl -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/backtests/start \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "universal_zero_shot_model",
    "symbol": "EURUSD",
    "timeframe": "5m",
    "start_date": "2024-01-01",
    "end_date": "2024-11-04"
  }')

OPERATION_ID=$(echo "$RESPONSE" | jq -r '.operation_id')
```

### 2. Check Progress

**Command:**
```bash
sleep 5
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$OPERATION_ID" | \
  jq '{status:.data.status, pct:.data.progress.percentage}'
```

### 3. Cancel via API

**Command:**
```bash
curl -s -X DELETE "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$OPERATION_ID" | jq
```

**Expected:**
- HTTP 200
- Cancellation accepted

### 4. Verify Cancellation

**Command:**
```bash
sleep 2
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$OPERATION_ID" | \
  jq '{status:.data.status, pct:.data.progress.percentage}'
```

**Expected:**
- `status: "cancelled"`
- Progress frozen

### 5. System Stability

**Command:**
```bash
curl -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/backtests/start \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "universal_zero_shot_model",
    "symbol": "EURUSD",
    "timeframe": "5m",
    "start_date": "2024-11-01",
    "end_date": "2024-11-04"
  }' | jq '{success:.success, operation_id:.operation_id}'
```

**Expected:**
- New operation starts immediately

---

## Success Criteria

- [ ] DELETE returns HTTP 200
- [ ] Status becomes "cancelled"
- [ ] Progress frozen
- [ ] New operation starts OK

---

## Evidence to Capture

- Cancel response
- Pre/post cancel status
- New operation start result
