# Test: backtest/progress

**Purpose:** Verify progress updates during backtest execution
**Duration:** ~20 seconds
**Category:** Backtest

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health
- [backtest](../../preflight/backtest.md) — Model, strategy, data, workers

---

## Test Data

```json
{
  "model_path": "models/neuro_mean_reversion/1d_v21/model.pt",
  "strategy_name": "neuro_mean_reversion",
  "symbol": "EURUSD",
  "timeframe": "1d",
  "start_date": "2023-01-01",
  "end_date": "2024-12-31"
}
```

**Why this data:**
- ~520 bars (2 years daily)
- Long enough to observe progress updates

---

## Execution Steps

### 1. Start Backtest

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

### 2. Poll Progress Every 5s

**Command:**
```bash
for i in {1..5}; do
  sleep 5
  curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$OPERATION_ID" | \
    jq '{poll:'"$i"', status:.data.status, pct:.data.progress.percentage, bars:.data.progress.items_processed}'
done
```

**Expected:**
- Progress percentage increases
- items_processed grows
- Status transitions from "running" to "completed"

---

## Success Criteria

- [ ] Progress visible at intermediate polls
- [ ] Progress percentage increases (0% → 100%)
- [ ] items_processed grows
- [ ] Final status is "completed"

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Progress observed** — At least one poll shows progress between 10% and 90%
- [ ] **Not instant** — If total time < 3s for 500 bars, something skipped

---

## Evidence to Capture

- Progress snapshots from polling
- Final status and bar count
