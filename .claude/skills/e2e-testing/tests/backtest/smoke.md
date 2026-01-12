# Test: backtest/smoke

**Purpose:** Quick validation that backtest starts, completes, and returns results
**Duration:** <10 seconds
**Category:** Backtest

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health
- [backtest](../../preflight/backtest.md) — Model, strategy, data, workers

**Test-specific checks:**
- [ ] Model exists: `models/neuro_mean_reversion/1d_v21/model.pt`
- [ ] Strategy exists: `neuro_mean_reversion.yaml`
- [ ] Data available: EURUSD 1d

---

## Test Data

```json
{
  "model_path": "models/neuro_mean_reversion/1d_v21/model.pt",
  "strategy_name": "neuro_mean_reversion",
  "symbol": "EURUSD",
  "timeframe": "1d",
  "start_date": "2024-01-01",
  "end_date": "2024-01-31"
}
```

**Why this data:**
- Short date range (~21 bars) for quick execution
- Known-good model and strategy
- Tests basic workflow without long wait

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
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  }')

OPERATION_ID=$(echo "$RESPONSE" | jq -r '.operation_id')
echo "Operation ID: $OPERATION_ID"
```

**Expected:**
- HTTP 200
- `operation_id` returned

### 2. Wait and Check Completion

**Command:**
```bash
sleep 10
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$OPERATION_ID" | \
  jq '{status:.data.status, bars:.data.result_summary.total_bars}'
```

**Expected:**
- `status: "completed"`
- `bars: ~21`

### 3. Verify Results Present

**Command:**
```bash
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$OPERATION_ID" | \
  jq '{total_return:.data.result_summary.total_return, trades:.data.result_summary.total_trades}'
```

**Expected:**
- `total_return` present (may be negative or positive)
- `total_trades` present

---

## Success Criteria

- [ ] Backtest starts successfully (operation_id returned)
- [ ] Backtest completes (status = "completed")
- [ ] Correct bar count (~21 bars)
- [ ] Results present (total_return, total_trades)
- [ ] No errors in logs

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Status is completed** — Not "failed" or stuck at "running"
- [ ] **Bars processed > 0** — Not empty result
- [ ] **Results have values** — Not all null/NaN

---

## Troubleshooting

**If model not found:**
- **Cause:** Model path incorrect
- **Cure:** Check available models: `find models -name "model.pt"`

**If strategy not found:**
- **Cause:** Strategy not in expected location
- **Cure:** Copy to shared: `cp strategies/neuro_mean_reversion.yaml ~/.ktrdr/shared/strategies/`

**If backtest times out:**
- **Cause:** Worker busy or crashed
- **Cure:** Check workers: `curl http://localhost:${KTRDR_API_PORT:-8000}/api/v1/workers`

---

## Evidence to Capture

- Operation ID: `$OPERATION_ID`
- Final status
- Result summary: total_return, total_trades, bars
