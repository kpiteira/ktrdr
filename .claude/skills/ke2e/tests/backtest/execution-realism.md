# Test: backtest/execution-realism

**Purpose:** Validate that the backtest engine uses execution-realism defaults (next-bar open pricing, 0.0005 slippage) through the full API pipeline
**Duration:** <120 seconds
**Category:** Backtest (Regression)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../../e2e-testing/preflight/common.md) -- Docker, sandbox, API health
- [backtest](../../../e2e-testing/preflight/backtest.md) -- Model, strategy, data, workers

**Test-specific checks:**
- [ ] At least one backtest worker registered at the API
- [ ] A trained model exists (any v3 strategy with model)
- [ ] OHLCV data cached for the test symbol/timeframe

---

## Test Data

```json
{
  "strategy_name": "test_e2e_local_pull",
  "symbol": "EURUSD",
  "timeframe": "1h",
  "start_date": "2024-01-01",
  "end_date": "2024-06-30",
  "model_path": "models/test_e2e_local_pull/1h_latest"
}
```

**Why this data:**
- Reuses the same model/strategy as backtest/smoke (dependency chain already established)
- 6-month 1h range provides ~4250 bars -- enough for meaningful trades
- 1h timeframe avoids multi-timeframe bugs (known issue with 5m+1h)
- **Slippage is intentionally omitted** from the request to verify the API default of 0.0005

---

## Execution Steps

### 1. Start Backtest WITHOUT Slippage Parameter

**Command:**
```bash
source .env.sandbox
RESPONSE=$(curl -s -X POST http://localhost:${KTRDR_API_PORT}/api/v1/backtests/start \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "test_e2e_local_pull",
    "symbol": "EURUSD",
    "timeframe": "1h",
    "start_date": "2024-01-01",
    "end_date": "2024-06-30",
    "model_path": "models/test_e2e_local_pull/1h_latest"
  }')

echo "$RESPONSE" | jq .
OPERATION_ID=$(echo "$RESPONSE" | jq -r '.operation_id')
echo "Operation ID: $OPERATION_ID"
```

**Expected:**
- HTTP 200 with `operation_id` returned
- No slippage specified in request body

### 2. Verify Operation Metadata Shows Slippage Default

**Command:**
```bash
source .env.sandbox
# Check the operation metadata immediately (before completion)
curl -s "http://localhost:${KTRDR_API_PORT}/api/v1/operations/$OPERATION_ID" | \
  jq '{status: .data.status, slippage_in_metadata: .data.metadata.parameters.slippage}'
```

**Expected:**
- `metadata.parameters.slippage` equals `0.0005`
- This confirms the API default was applied before execution began

### 3. Poll Until Completion

**Command:**
```bash
source .env.sandbox
for i in $(seq 1 20); do
  sleep 5
  STATUS=$(curl -s "http://localhost:${KTRDR_API_PORT}/api/v1/operations/$OPERATION_ID" | jq -r '.data.status')
  echo "Poll $i: status=$STATUS"
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
done
```

**Expected:**
- Status transitions from `running` to `completed`
- Should complete within 100 seconds (20 polls x 5s)

### 4. Verify Completion and Slippage in Results Config

**Command:**
```bash
source .env.sandbox
RESULT=$(curl -s "http://localhost:${KTRDR_API_PORT}/api/v1/operations/$OPERATION_ID")

echo "=== Status ==="
echo "$RESULT" | jq '.data.status'

echo "=== Config (slippage) ==="
echo "$RESULT" | jq '.data.result_summary.config.slippage'

echo "=== Trade Count ==="
echo "$RESULT" | jq '.data.result_summary.trade_count'

echo "=== Metrics (total_return) ==="
echo "$RESULT" | jq '.data.result_summary.metrics.total_return'

echo "=== Full Config ==="
echo "$RESULT" | jq '.data.result_summary.config'
```

**Expected:**
- `status` is `"completed"`
- `result_summary.config.slippage` is `0.0005` (the standardized default)
- `trade_count` is present and >= 0
- `metrics.total_return` is present (may be negative or positive)

### 5. Verify Trades Were Produced (Execution Realism Evidence)

**Command:**
```bash
source .env.sandbox
RESULT=$(curl -s "http://localhost:${KTRDR_API_PORT}/api/v1/operations/$OPERATION_ID")

TRADE_COUNT=$(echo "$RESULT" | jq '.data.result_summary.trade_count')
TOTAL_RETURN=$(echo "$RESULT" | jq '.data.result_summary.metrics.total_return')
EXECUTION_TIME=$(echo "$RESULT" | jq '.data.result_summary.execution_time_seconds')

echo "trade_count=$TRADE_COUNT"
echo "total_return=$TOTAL_RETURN"
echo "execution_time=$EXECUTION_TIME"
```

**Expected:**
- `trade_count >= 0` (model may or may not produce trades; zero is valid if the model is conservative)
- `execution_time_seconds > 0` (proves real computation occurred)
- If `trade_count > 0`, `total_return` should be a finite number (not null/NaN)

---

## Success Criteria

- [ ] Backtest starts successfully without specifying slippage (operation_id returned)
- [ ] Operation metadata contains `slippage: 0.0005` (API default applied)
- [ ] Backtest completes with status `"completed"`
- [ ] Result config shows `slippage: 0.0005` (default propagated through engine)
- [ ] Results contain valid metrics (`total_return` present, not null)
- [ ] `execution_time_seconds > 0` (real computation occurred)

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Status is "completed", not "failed"** -- A failed backtest returns results_summary={}, which would make slippage checks pass vacuously
- [ ] **result_summary is not empty** -- `result_summary.config` must exist; if null/empty, the results were not stored properly
- [ ] **execution_time_seconds > 1.0** -- A 4250-bar backtest should take at least a few seconds; <1s suggests the engine short-circuited or returned cached results
- [ ] **Slippage is exactly 0.0005, not 0** -- Zero slippage would mean the default was not applied (old default was 0 in some code paths)
- [ ] **Slippage is exactly 0.0005, not 0.001** -- 0.001 is the commission default; confirms these are not confused

---

## Troubleshooting

**If backtest fails with "model not found":**
- **Cause:** No trained model at the specified path
- **Category:** ENVIRONMENT
- **Cure:** Run `training/smoke` test first, or find an existing model: `find ~/.ktrdr/shared/models -name "model.pt" | head -5` and update `model_path` accordingly

**If slippage is null or missing in result_summary:**
- **Cause:** BacktestResults.to_dict() changed or result_summary not stored correctly
- **Category:** CODE_BUG
- **Cure:** Check `ktrdr/backtesting/engine.py` BacktestResults.to_dict() includes `config.slippage`; check backtest_worker.py passes results_dict to complete_operation()

**If slippage is 0 instead of 0.0005:**
- **Cause:** An entry point is not using the standardized default
- **Category:** CODE_BUG
- **Cure:** Check BacktestStartRequest.slippage default in `ktrdr/api/models/backtesting.py` and BacktestConfig.slippage in `ktrdr/backtesting/engine.py` -- both should default to 0.0005

**If backtest times out (>100s):**
- **Cause:** Worker busy, crashed, or cold start
- **Category:** ENVIRONMENT
- **Cure:** Check workers: `curl http://localhost:${KTRDR_API_PORT}/api/v1/workers | jq '.workers[] | select(.type=="backtest")'`

**If trade_count is 0:**
- **Cause:** Model may not produce trades for this period (conservative predictions, high thresholds)
- **Category:** TEST_ISSUE (not necessarily a bug)
- **Cure:** This is acceptable -- the test validates execution realism defaults, not trading performance. The slippage config assertions are the primary signal.

---

## Evidence to Capture

- Operation ID: `$OPERATION_ID`
- Operation metadata (includes slippage): `.data.metadata`
- Result config: `.data.result_summary.config` (contains slippage, commission, initial_capital)
- Result metrics: `.data.result_summary.metrics` (total_return, trade_count)
- Execution time: `.data.result_summary.execution_time_seconds`

---

## Notes

- **Port variable:** Read from `.env.sandbox` as `KTRDR_API_PORT` (slot 6 = port 8006)
- **Container discovery:** Use `docker ps --filter "name=slot-6" --format "{{.Names}}" | head -1`
- **Next-bar execution is internal:** The unit tests in `test_next_bar_execution.py` verify exact price mechanics (trade price matches next bar's open). This E2E test validates the pipeline works end-to-end with correct defaults. If you need to verify actual execution prices against OHLCV data, that requires container-level inspection of trade logs, which is beyond what the API exposes.
- **Slippage 0.0005 is the key assertion:** This value was standardized across BacktestStartRequest (API), BacktestConfig (engine), backtest CLI, and remote API. If any entry point diverges, this test catches it through the API path.
- **Dependency:** This test should run after `training/smoke` or any test that creates the model at `models/test_e2e_local_pull/1h_latest`.
