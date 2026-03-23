# Test: backtest/api-start

**Purpose:** Verify full API workflow for backtest
**Duration:** ~10 seconds
**Category:** Backtest (Integration)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health
- [backtest](../../preflight/backtest.md) — Model, strategy, data, workers

---

## Test Data

```json
{
  "strategy_name": "universal_zero_shot_model",
  "symbol": "EURUSD",
  "timeframe": "5m",
  "start_date": "2024-11-01",
  "end_date": "2024-11-04"
}
```

**Why this data:**
- Uses universal model (no specific model path required)
- 3 days of 5m data (~864 bars)
- Quick execution

---

## Execution Steps

### 1. Start Backtest

**Command:**
```bash
RESPONSE=$(curl -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/backtests/start \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "universal_zero_shot_model",
    "symbol": "EURUSD",
    "timeframe": "5m",
    "start_date": "2024-11-01",
    "end_date": "2024-11-04"
  }')

OPERATION_ID=$(echo "$RESPONSE" | jq -r '.operation_id')
echo "Operation ID: $OPERATION_ID"
```

### 2. Query Status

**Command:**
```bash
sleep 10
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$OPERATION_ID" | \
  jq '{status:.data.status, progress:.data.progress.percentage}'
```

**Expected:**
- `status: "completed"`
- `progress: 100`

### 3. Verify Listable

**Command:**
```bash
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations?operation_type=backtesting" | \
  jq '.data | map(select(.operation_id == "'$OPERATION_ID'")) | length'
```

**Expected:**
- Returns 1 (operation found in list)

---

## Success Criteria

- [ ] HTTP 200, operation_id returned
- [ ] Status: "completed"
- [ ] Progress: 100%
- [ ] Operation listable via /operations?operation_type=backtesting

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Operation ID valid** — Not null or empty
- [ ] **In operations list** — Can be found after completion

---

## Evidence to Capture

- Operation ID
- Final status
- Operations list query result
