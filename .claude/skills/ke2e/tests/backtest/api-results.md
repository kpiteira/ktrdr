# Test: backtest/api-results

**Purpose:** Verify progress updates via Operations API
**Duration:** ~15 seconds
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
  "start_date": "2024-10-01",
  "end_date": "2024-11-04"
}
```

**Why this data:**
- ~9,600 bars (35 days of 5m data)
- Long enough to observe multiple progress updates

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
    "start_date": "2024-10-01",
    "end_date": "2024-11-04"
  }')

OPERATION_ID=$(echo "$RESPONSE" | jq -r '.operation_id')
```

### 2. Poll Every 3s

**Command:**
```bash
for i in {1..5}; do
  sleep 3
  curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$OPERATION_ID" | \
    jq '{poll:'"$i"', pct:.data.progress.percentage, bars:.data.progress.items_processed}'
done
```

**Expected:**
- Percentage increases monotonically
- items_processed grows
- Status transitions to "completed"

---

## Success Criteria

- [ ] Progress percentage increases (0% → 100%)
- [ ] items_processed grows steadily
- [ ] Multiple progress updates visible
- [ ] Final status is "completed"

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Progress observable** — Not just 0% then 100%
- [ ] **Reasonable timing** — Total time > 5s for this dataset

---

## Evidence to Capture

- Progress snapshots
- Final status and results
