# Test: regression/full-cycle

**Purpose:** Validate that a regression strategy can be trained and backtested end-to-end, with correct model config, cost-aware trade filtering, and predicted_return metadata in results
**Duration:** ~5 minutes (training ~2-3min, backtest ~1min)
**Category:** Training + Backtest (Regression)

**Dependency:** None (self-contained: trains then backtests)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) -- Docker, sandbox, API health
- [training](../../preflight/training.md) -- Strategy, data, workers

**Test-specific checks:**
- [ ] Regression strategy file exists: `~/.ktrdr/shared/strategies/regression_example_v3.yaml`
- [ ] EURUSD 1h data available in cache
- [ ] Sandbox port is 8006 (source `.env.sandbox` and verify `KTRDR_API_PORT=8006`)
- [ ] At least one idle training worker
- [ ] At least one backtest worker registered

**Strategy copy (if missing):**
```bash
cp /Users/karl/Documents/dev/ktrdr-impl-forward-return-regression-M1/strategies/regression_example_v3.yaml \
   ~/.ktrdr/shared/strategies/regression_example_v3.yaml
```

---

## Test Data

```json
{
  "strategy_name": "regression_example",
  "strategy_file": "regression_example_v3.yaml",
  "symbol": "EURUSD",
  "timeframe": "1h",
  "train_start": "2024-01-01",
  "train_end": "2025-03-01",
  "backtest_start": "2025-03-01",
  "backtest_end": "2025-06-01"
}
```

**Why this data:**
- EURUSD 1h over 14 months: ~10,000 samples for training, sufficient for regression
- Backtest range (3 months) is out-of-sample relative to training, giving ~2,000 bars
- `regression_example_v3` is the canonical regression strategy with cost_model and forward_return labels
- 1h timeframe: enough bars for meaningful trading without excessive runtime

---

## Execution Steps

### 1. Environment Setup

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-forward-return-regression-M1
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8006}
echo "Using API_PORT=$API_PORT"
```

**Expected:**
- API_PORT is 8006

### 2. Copy Strategy to Shared Directory

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-forward-return-regression-M1
cp strategies/regression_example_v3.yaml ~/.ktrdr/shared/strategies/regression_example_v3.yaml
echo "Strategy copied"
ls -la ~/.ktrdr/shared/strategies/regression_example_v3.yaml
```

**Expected:**
- File exists at shared strategies location

### 3. Start Regression Training via API

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-forward-return-regression-M1
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8006}

RESPONSE=$(curl -s -X POST http://localhost:$API_PORT/api/v1/trainings/start \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["EURUSD"],
    "timeframes": ["1h"],
    "strategy_name": "regression_example",
    "start_date": "2024-01-01",
    "end_date": "2025-03-01"
  }')

echo "Training Response: $RESPONSE"

TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id')
echo "Task ID: $TASK_ID"
```

**Expected:**
- HTTP 200
- `success: true`
- `task_id` returned (non-null, non-empty)

### 4. Wait for Training Completion

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-forward-return-regression-M1
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8006}

# Poll every 15s for up to 5 minutes
for i in $(seq 1 20); do
  sleep 15
  STATUS=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$TASK_ID" | jq -r '.data.status')
  echo "Poll $i: status=$STATUS"
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
done

TRAIN_RESULT=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$TASK_ID")
echo "Training Result: $TRAIN_RESULT" | jq '{status:.data.status, samples:.data.result_summary.data_summary.total_samples}'
```

**Expected:**
- `status: "completed"` (not "failed" or "running")
- `samples` > 5000 (14 months of 1h data should yield ~10,000)
- Total wait < 5 minutes

### 5. Verify Model Config Contains output_format: regression

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-forward-return-regression-M1
source .env.sandbox

# Find the model directory -- models are stored in shared models dir
MODEL_DIR=$(find ~/.ktrdr/shared/models/regression_example -maxdepth 2 -name "config.json" -newer /tmp/e2e_start_marker 2>/dev/null | head -1 | xargs dirname)

# If find by timestamp fails, get latest version directory
if [ -z "$MODEL_DIR" ]; then
  MODEL_DIR=$(ls -td ~/.ktrdr/shared/models/regression_example/1h_v*/ 2>/dev/null | head -1)
fi

# Also check for latest symlink
if [ -z "$MODEL_DIR" ]; then
  MODEL_DIR="$HOME/.ktrdr/shared/models/regression_example/1h_latest"
fi

echo "Model directory: $MODEL_DIR"
ls -la "$MODEL_DIR/"

echo "--- config.json ---"
cat "$MODEL_DIR/config.json" | jq .

# Extract key fields
OUTPUT_FORMAT=$(cat "$MODEL_DIR/config.json" | jq -r '.decisions.output_format // .output_format // "NOT_FOUND"')
echo "output_format: $OUTPUT_FORMAT"

LOSS=$(cat "$MODEL_DIR/config.json" | jq -r '.training.loss // .loss // "NOT_FOUND"')
echo "loss: $LOSS"

LABELS_SOURCE=$(cat "$MODEL_DIR/config.json" | jq -r '.training.labels.source // .labels.source // "NOT_FOUND"')
echo "labels_source: $LABELS_SOURCE"
```

**Expected:**
- `config.json` exists in model directory
- `output_format` is `"regression"` (not `"classification"` or `"NOT_FOUND"`)
- `loss` is `"huber"` (regression-specific loss function)
- `labels_source` is `"forward_return"` (regression label type)

### 6. Verify Training Metrics are Regression-Appropriate

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-forward-return-regression-M1
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8006}

curl -s "http://localhost:$API_PORT/api/v1/operations/$TASK_ID" | \
  jq '{
    test_accuracy: .data.result_summary.test_metrics.test_accuracy,
    val_accuracy: .data.result_summary.training_metrics.final_val_accuracy,
    val_loss: .data.result_summary.training_metrics.final_val_loss,
    training_time: .data.result_summary.training_metrics.training_time
  }'
```

**Expected:**
- `val_loss` > 0 (training happened, not collapsed)
- `training_time` > 1.0 (real training, not cached or skipped)
- `test_accuracy` or `val_accuracy` may represent direction accuracy for regression (> 0.4 and < 0.99)

### 7. Start Backtest with Trained Regression Model

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-forward-return-regression-M1
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8006}

# Determine model path from training result
MODEL_PATH=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$TASK_ID" | \
  jq -r '.data.result_summary.model_path // empty')

# Fallback: construct from convention
if [ -z "$MODEL_PATH" ]; then
  MODEL_PATH="models/regression_example/1h_latest"
fi

echo "Using model_path: $MODEL_PATH"

BT_RESPONSE=$(curl -s -X POST http://localhost:$API_PORT/api/v1/backtests/start \
  -H "Content-Type: application/json" \
  -d "{
    \"model_path\": \"$MODEL_PATH\",
    \"strategy_name\": \"regression_example\",
    \"symbol\": \"EURUSD\",
    \"timeframe\": \"1h\",
    \"start_date\": \"2025-03-01\",
    \"end_date\": \"2025-06-01\"
  }")

echo "Backtest Response: $BT_RESPONSE"

BT_OP_ID=$(echo "$BT_RESPONSE" | jq -r '.operation_id')
echo "Backtest Operation ID: $BT_OP_ID"
```

**Expected:**
- HTTP 200
- `operation_id` returned (non-null, non-empty)

### 8. Wait for Backtest Completion

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-forward-return-regression-M1
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8006}

for i in $(seq 1 12); do
  sleep 10
  BT_STATUS=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$BT_OP_ID" | jq -r '.data.status')
  echo "Poll $i: status=$BT_STATUS"
  if [ "$BT_STATUS" = "completed" ] || [ "$BT_STATUS" = "failed" ]; then
    break
  fi
done

BT_RESULT=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$BT_OP_ID")
echo "Backtest Result:"
echo "$BT_RESULT" | jq '{
  status: .data.status,
  total_return: .data.result_summary.metrics.total_return,
  trade_count: .data.result_summary.trade_count,
  total_bars: .data.result_summary.total_bars
}'
```

**Expected:**
- `status: "completed"`
- `trade_count` present and > 0
- `total_bars` > 1000 (3 months of 1h data ~ 2,000 bars)

### 9. Verify Cost-Aware Trade Filtering

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-forward-return-regression-M1
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8006}

BT_RESULT=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$BT_OP_ID")

TRADE_COUNT=$(echo "$BT_RESULT" | jq -r '.data.result_summary.trade_count')
TOTAL_BARS=$(echo "$BT_RESULT" | jq -r '.data.result_summary.total_bars // .data.result_summary.equity_curve_length')

echo "Trades: $TRADE_COUNT"
echo "Total bars: $TOTAL_BARS"

# Cost filtering means: trades < total_bars (not trading every bar)
# With cost_model.round_trip_cost=0.003 and min_edge_multiplier=1.5,
# the trade_threshold = 0.0045, which should filter many weak signals
if [ "$TRADE_COUNT" -gt 0 ] && [ "$TRADE_COUNT" -lt "$TOTAL_BARS" ]; then
  echo "OK: Cost filtering active ($TRADE_COUNT trades out of $TOTAL_BARS bars)"
else
  echo "WARN: Trade count ($TRADE_COUNT) vs bars ($TOTAL_BARS) may indicate filtering issue"
fi

# Trade ratio (trades / bars) should be well below 1.0
# Typical regression with cost filtering: 5-20% of bars produce trades
RATIO=$(echo "scale=4; $TRADE_COUNT / $TOTAL_BARS" | bc 2>/dev/null || echo "N/A")
echo "Trade ratio: $RATIO"
```

**Expected:**
- `TRADE_COUNT` > 0 (model produces some signals above threshold)
- `TRADE_COUNT` < `TOTAL_BARS` (cost filtering is working)
- Trade ratio < 0.5 (not trading every other bar -- cost filtering should be selective)

### 10. Verify Backtest Result Structure (Regression-Specific Fields)

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-forward-return-regression-M1
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8006}

# Check the full result summary for regression-specific fields
BT_RESULT=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$BT_OP_ID")

echo "Full result_summary keys:"
echo "$BT_RESULT" | jq '.data.result_summary | keys'

echo "Metrics:"
echo "$BT_RESULT" | jq '.data.result_summary.metrics'
```

**Expected:**
- `result_summary` contains `metrics`, `trade_count`
- `metrics` contains standard fields: `total_return`, `sharpe_ratio`, `max_drawdown`, `win_rate`

### 11. Inspect Model Config Inside Container (Container Filesystem Evidence)

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-forward-return-regression-M1

# Find the sandbox container
CONTAINER=$(docker ps --filter "name=slot-6" --format "{{.Names}}" | grep backend | head -1)
echo "Container: $CONTAINER"

if [ -n "$CONTAINER" ]; then
  # Check model config.json inside the container's view of shared models
  docker exec "$CONTAINER" sh -c "cat /app/models/regression_example/1h_latest/config.json 2>/dev/null || cat /models/regression_example/1h_latest/config.json 2>/dev/null || echo 'MODEL_NOT_FOUND_IN_CONTAINER'" | jq .

  # Verify output_format field
  docker exec "$CONTAINER" sh -c "cat /app/models/regression_example/1h_latest/config.json 2>/dev/null || cat /models/regression_example/1h_latest/config.json 2>/dev/null" | jq -r '.decisions.output_format // .output_format // "NOT_FOUND"'
else
  echo "WARN: Could not find backend container for slot-6"
  echo "Falling back to host filesystem check"
  cat ~/.ktrdr/shared/models/regression_example/1h_latest/config.json | jq -r '.decisions.output_format // .output_format // "NOT_FOUND"'
fi
```

**Expected:**
- `output_format` is `"regression"` whether read from container or host

---

## Success Criteria

- [ ] Training starts successfully (HTTP 200, task_id returned)
- [ ] Training completes (status = "completed") within 5 minutes
- [ ] Model `config.json` contains `output_format: "regression"`
- [ ] Model `config.json` contains `loss: "huber"` (regression loss)
- [ ] Model `config.json` contains `labels.source: "forward_return"`
- [ ] Backtest starts successfully (operation_id returned)
- [ ] Backtest completes (status = "completed")
- [ ] Backtest produces trades (trade_count > 0)
- [ ] Trade count is less than total bars (cost filtering active)
- [ ] Backtest result contains standard metrics (total_return, sharpe_ratio)
- [ ] No errors in backend logs related to regression

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Training status is "completed", not "failed"** -- A failed training that produces partial output could look like success
- [ ] **output_format is literally "regression", not "classification"** -- If the strategy fell back to classification defaults, the whole test is meaningless
- [ ] **Training time > 1.0s** -- If < 1s, training may have been skipped or cached
- [ ] **Val loss > 0.0001** -- Near-zero loss on regression = collapsed model
- [ ] **Trade count > 0** -- Zero trades means model never predicts above cost threshold (degenerate)
- [ ] **Trade count < total_bars * 0.5** -- Trading on > 50% of bars means cost filtering is not working
- [ ] **trade_count is an integer, not null** -- Null trade_count could mean backtest ran but produced no results dict
- [ ] **Direction accuracy between 0.4 and 0.99** -- < 0.4 = worse than random on direction; > 0.99 = data leak or collapsed model

**Sanity check command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-forward-return-regression-M1
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8006}

echo "=== Training Sanity ==="
curl -s "http://localhost:$API_PORT/api/v1/operations/$TASK_ID" | jq '{
  status: .data.status,
  val_loss: .data.result_summary.training_metrics.final_val_loss,
  training_time: .data.result_summary.training_metrics.training_time,
  direction_accuracy: .data.result_summary.test_metrics.test_accuracy
}'

echo "=== Backtest Sanity ==="
curl -s "http://localhost:$API_PORT/api/v1/operations/$BT_OP_ID" | jq '{
  status: .data.status,
  trade_count: .data.result_summary.trade_count,
  total_bars: (.data.result_summary.total_bars // .data.result_summary.equity_curve_length),
  total_return: .data.result_summary.metrics.total_return
}'

echo "=== Model Config Sanity ==="
cat ~/.ktrdr/shared/models/regression_example/1h_latest/config.json 2>/dev/null | jq '{
  output_format: (.decisions.output_format // .output_format),
  loss: (.training.loss // .loss),
  labels_source: (.training.labels.source // .labels.source)
}'
```

---

## Troubleshooting

**If training fails with "strategy not found":**
- **Cause:** Strategy file not copied to shared directory
- **Cure:** `cp strategies/regression_example_v3.yaml ~/.ktrdr/shared/strategies/regression_example_v3.yaml`

**If training fails with "unknown output_format" or similar:**
- **Cause:** Strategy loader does not yet support `decisions.output_format: regression`
- **Cure:** This is an M1 implementation issue -- the v3 strategy loader needs to propagate the decisions config including output_format

**If model config.json has no output_format field:**
- **Cause:** Model storage does not preserve the decisions config from the strategy
- **Cure:** Check `model_storage.py` -- the `config` dict passed to `save_model()` must include the decisions section with output_format

**If backtest fails with "unknown output_format" or model load error:**
- **Cause:** `model_bundle.py` does not reconstruct regression config from config.json
- **Cure:** Check `reconstruct_config_from_metadata()` in model_bundle.py -- it must read and pass through the decisions config including output_format and cost_model

**If trade_count is 0:**
- **Cause:** Model predicts all returns below cost threshold (degenerate model), or cost threshold is too high
- **Cure:** Check `trade_threshold` calculation: `round_trip_cost * min_edge_multiplier = 0.003 * 1.5 = 0.0045`. If model never predicts |return| > 0.0045, all signals become HOLD. May need to check model output scale.

**If trade_count equals total_bars (no filtering):**
- **Cause:** Cost filtering not applied -- decision function fell back to classification path
- **Cure:** Verify that `DecisionFunction.output_format` is set to "regression" at runtime. Check model_bundle.py passes output_format through to decision function initialization.

**If training times out (> 5 minutes):**
- **Cause:** Worker busy or training hung
- **Cure:** Check workers: `curl http://localhost:$API_PORT/api/v1/workers | jq`; check logs: `docker compose -f docker-compose.sandbox.yml logs backend --tail 50`

**If backtest times out (> 2 minutes):**
- **Cause:** Backtest worker stuck or model loading error
- **Cure:** Check backtest worker logs: `docker compose -f docker-compose.sandbox.yml logs --tail 50`

---

## Evidence to Capture

- Training Operation ID: `$TASK_ID`
- Backtest Operation ID: `$BT_OP_ID`
- Model directory path and `config.json` contents (full JSON)
- Training metrics: val_loss, training_time, direction accuracy
- Backtest metrics: trade_count, total_bars, total_return, sharpe_ratio
- Trade ratio: trade_count / total_bars (proves cost filtering)
- Backend logs: `docker compose -f docker-compose.sandbox.yml logs backend --since 10m | grep -i "regression\|output_format\|trade_threshold"`
