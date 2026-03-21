# Test: training/triple-barrier-labels

**Purpose:** Validate that the triple barrier labeler produces balanced 3-class labels (BUY/HOLD/SELL), that barriers scale with volatility, that CUSUM filtering reduces sample count by 30-70%, and that training with `source: triple_barrier` completes end-to-end with valid label statistics in logs.
**Duration:** ~5 minutes (1-year 1h data, 10 epochs)
**Category:** Training (Triple Barrier Labels)

**Dependency:** None (self-contained: creates strategy YAML, trains, verifies)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../../e2e-testing/preflight/common.md) -- Docker, sandbox, API health
- [training](../../../e2e-testing/preflight/training.md) -- Strategy, data, workers

**Test-specific checks:**
- [ ] EURUSD 1h data is available (1 year: 2024-01-01 to 2025-01-01)
- [ ] At least one idle training worker
- [ ] No stale model from a previous run at `~/.ktrdr/shared/models/triple_barrier_e2e/`

**Pre-flight commands:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# 1. API health
curl -sf "http://localhost:$API_PORT/api/v1/health" > /dev/null || {
  echo "FAIL: API not healthy on port $API_PORT"
  exit 1
}

# 2. Training workers available
WORKERS=$(curl -s "http://localhost:$API_PORT/api/v1/workers" | jq '[.workers[] | select(.type=="training")] | length')
echo "Training workers: $WORKERS"
test "$WORKERS" -ge 1 || {
  echo "FAIL: No training workers registered"
  exit 1
}
```

---

## Test Data

### Strategy YAML

The test creates a minimal v3 strategy with `source: triple_barrier` and CUSUM filtering. This strategy does NOT exist in the repo -- it must be written to the shared strategies directory.

```yaml
name: triple_barrier_e2e
version: "3.0"
description: "E2E test: triple barrier labeling with CUSUM filter"

training_data:
  symbols:
    mode: single
    symbol: EURUSD
  timeframes:
    mode: single
    list: [1h]
    base_timeframe: 1h
  history_required: 200

indicators:
  rsi_14:
    type: RSI
    period: 14
    source: close
  atr_14:
    type: ATR
    period: 14
  bbands_20:
    type: BBANDS
    period: 20
    std_dev: 2.0

fuzzy_sets:
  rsi_14:
    indicator: rsi_14
    oversold:
      type: triangular
      parameters: [0, 20, 40]
    neutral:
      type: triangular
      parameters: [30, 50, 70]
    overbought:
      type: triangular
      parameters: [60, 80, 100]
  atr_level:
    indicator: atr_14
    low:
      type: triangular
      parameters: [0, 0.0005, 0.001]
    medium:
      type: triangular
      parameters: [0.0005, 0.001, 0.002]
    high:
      type: triangular
      parameters: [0.001, 0.002, 0.005]

nn_inputs:
  - fuzzy_set: rsi_14
    timeframes: all
  - fuzzy_set: atr_level
    timeframes: all

model:
  type: mlp
  architecture:
    hidden_layers: [32, 16]
    activation: relu
    output_activation: softmax
    dropout: 0.1
  features:
    include_price_context: false
    lookback_periods: 1
    scale_features: true
  training:
    learning_rate: 0.001
    batch_size: 32
    epochs: 10
    optimizer: adam
    early_stopping:
      enabled: false

decisions:
  output_format: classification
  confidence_threshold: 0.6
  position_awareness: false

training:
  method: supervised
  labels:
    source: triple_barrier
    pt_multiplier: 2.0
    sl_multiplier: 1.5
    max_holding_period: 50
    vol_span: 50
    cusum_threshold: 0.0002
  data_split:
    train: 0.7
    validation: 0.15
    test: 0.15
```

**Why this strategy:**
- `source: triple_barrier` triggers the triple barrier label path in `training_pipeline.py`
- `cusum_threshold: 0.0002` is a fixed threshold calibrated for EURUSD 1h data (mean hourly vol ~0.0008). At ~25% of mean vol, this targets 30-70% event retention. Higher thresholds (0.0005+) over-filter to <15% retention for hourly FX data.
- `pt_multiplier: 2.0` / `sl_multiplier: 1.5` are asymmetric -- TP wider than SL, common in trend-following
- `max_holding_period: 50` = ~2 trading days of 1h bars
- `vol_span: 50` = EWMA lookback for daily volatility estimation
- 10 epochs keeps training fast while producing a real model
- RSI + ATR inputs: RSI for momentum, ATR for volatility awareness (mirrors what the labeler uses internally)
- EURUSD 1h for 2024: ~6,500 bars, enough for meaningful class distribution

**Why this data range (2024):**
- 2024 EURUSD had trending periods (Q1 dollar strength, Q3 euro recovery) AND ranging periods
- This means all 3 label classes (+1 TP, 0 expiry, -1 SL) should appear with meaningful representation
- 1 year is enough for statistical validity without excessive training time

---

## Execution Steps

### 1. Write Strategy File

**Command:**
```bash
source .env.sandbox

cat > ~/.ktrdr/shared/strategies/triple_barrier_e2e_v3.yaml << 'STRATEGY_EOF'
name: triple_barrier_e2e
version: "3.0"
description: "E2E test: triple barrier labeling with CUSUM filter"

training_data:
  symbols:
    mode: single
    symbol: EURUSD
  timeframes:
    mode: single
    list: [1h]
    base_timeframe: 1h
  history_required: 200

indicators:
  rsi_14:
    type: RSI
    period: 14
    source: close
  atr_14:
    type: ATR
    period: 14
  bbands_20:
    type: BBANDS
    period: 20
    std_dev: 2.0

fuzzy_sets:
  rsi_14:
    indicator: rsi_14
    oversold:
      type: triangular
      parameters: [0, 20, 40]
    neutral:
      type: triangular
      parameters: [30, 50, 70]
    overbought:
      type: triangular
      parameters: [60, 80, 100]
  atr_level:
    indicator: atr_14
    low:
      type: triangular
      parameters: [0, 0.0005, 0.001]
    medium:
      type: triangular
      parameters: [0.0005, 0.001, 0.002]
    high:
      type: triangular
      parameters: [0.001, 0.002, 0.005]

nn_inputs:
  - fuzzy_set: rsi_14
    timeframes: all
  - fuzzy_set: atr_level
    timeframes: all

model:
  type: mlp
  architecture:
    hidden_layers: [32, 16]
    activation: relu
    output_activation: softmax
    dropout: 0.1
  features:
    include_price_context: false
    lookback_periods: 1
    scale_features: true
  training:
    learning_rate: 0.001
    batch_size: 32
    epochs: 10
    optimizer: adam
    early_stopping:
      enabled: false

decisions:
  output_format: classification
  confidence_threshold: 0.6
  position_awareness: false

training:
  method: supervised
  labels:
    source: triple_barrier
    pt_multiplier: 2.0
    sl_multiplier: 1.5
    max_holding_period: 50
    vol_span: 50
    cusum_threshold: 0
  data_split:
    train: 0.7
    validation: 0.15
    test: 0.15
STRATEGY_EOF

echo "Strategy written"
ls -la ~/.ktrdr/shared/strategies/triple_barrier_e2e_v3.yaml
```

**Expected:**
- File created at shared strategies location

### 2. Remove Previous Model (Clean Slate)

**Command:**
```bash
MODEL_DIR="$HOME/.ktrdr/shared/models/triple_barrier_e2e"
if [ -d "$MODEL_DIR" ]; then
  echo "Previous model found at $MODEL_DIR -- removing for clean test"
  rm -rf "$MODEL_DIR"
fi
echo "Clean slate confirmed"
```

**Expected:**
- No pre-existing model artifacts that could give false-positive results

### 3. Start Training via API

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

RESPONSE=$(curl -s -X POST "http://localhost:$API_PORT/api/v1/trainings/start" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["EURUSD"],
    "timeframes": ["1h"],
    "strategy_name": "triple_barrier_e2e",
    "start_date": "2024-01-01",
    "end_date": "2025-01-01"
  }')

echo "Training Response: $RESPONSE"

TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id')
echo "Task ID: $TASK_ID"
```

**Expected:**
- HTTP 200 with `success: true`
- `task_id` returned (non-null, non-empty)
- No validation error about unknown label source

### 4. Wait for Training Completion

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Poll every 15s for up to 10 minutes
for i in $(seq 1 40); do
  sleep 15
  STATUS=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$TASK_ID" | jq -r '.data.status')
  echo "Poll $i: status=$STATUS"
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
done

TRAIN_RESULT=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$TASK_ID")
echo "Final status: $(echo "$TRAIN_RESULT" | jq -r '.data.status')"
echo "Result summary: $(echo "$TRAIN_RESULT" | jq '.data.result_summary')"
```

**Expected:**
- `status: "completed"` (not "failed" or still "running")
- Total wait < 10 minutes

### 5. Verify Label Distribution from Backend Logs

**Command:**
```bash
source .env.sandbox

# Triple barrier label statistics are logged by training_pipeline.py
# Look for the "Generated N triple barrier labels" log line
docker compose -f docker-compose.sandbox.yml logs backend --since 15m 2>/dev/null | \
  grep -iE "triple.barrier|CUSUM|TP=|SL=|Expiry=|mean_hold" | tail -20

echo ""
echo "=== CUSUM filter line ==="
docker compose -f docker-compose.sandbox.yml logs backend --since 15m 2>/dev/null | \
  grep -i "CUSUM filter" | tail -5
```

**Expected:**
- Log line showing `"Generated N triple barrier labels - TP=XX.X%, SL=XX.X%, Expiry=XX.X%, mean_hold=XX.X bars"`
- **Class balance check:** No single class > 60% (TP, SL, or Expiry)
- **TP and SL should both be > 15%** -- with asymmetric barriers (pt=2.0, sl=1.5) on EURUSD, both profit and loss barriers should be hit regularly
- **Expiry should be < 40%** -- most price paths hit a barrier within 50 bars on EURUSD 1h
- **mean_hold should be > 5 and < 45** -- if mean_hold is ~1, barriers are too tight; if ~50, barriers are too wide
- CUSUM filter log showing `"N/M bars selected (XX.X%)"` where the percentage is between 30% and 70%

### 6. Verify CUSUM Filtering Reduced Sample Count

**Command:**
```bash
source .env.sandbox

# Extract CUSUM filter statistics from logs
CUSUM_LINE=$(docker compose -f docker-compose.sandbox.yml logs backend --since 15m 2>/dev/null | \
  grep -i "CUSUM filter:" | tail -1)
echo "CUSUM line: $CUSUM_LINE"

# Extract the percentage
# Expected format: "CUSUM filter: N/M bars selected (XX.X%)"
CUSUM_PCT=$(echo "$CUSUM_LINE" | grep -oP '\d+\.\d+(?=%)')
echo "CUSUM retention percentage: $CUSUM_PCT%"

# Also check "After CUSUM filtering: N labels retained"
RETAINED_LINE=$(docker compose -f docker-compose.sandbox.yml logs backend --since 15m 2>/dev/null | \
  grep -i "After CUSUM filtering" | tail -1)
echo "Retained line: $RETAINED_LINE"
```

**Expected:**
- CUSUM selected between 30% and 70% of total bars
- "After CUSUM filtering" line shows reduced label count vs total available
- If CUSUM selected < 10% or > 90%, the auto-threshold is miscalibrated

### 7. Verify Model Files Exist

**Command:**
```bash
MODEL_DIR=$(ls -td ~/.ktrdr/shared/models/triple_barrier_e2e/1h_v*/ 2>/dev/null | head -1)
if [ -z "$MODEL_DIR" ]; then
  MODEL_DIR="$HOME/.ktrdr/shared/models/triple_barrier_e2e/1h_latest"
fi
echo "Model directory: $MODEL_DIR"

echo "=== Directory listing ==="
ls -la "$MODEL_DIR/"

echo "=== model.pt size ==="
MODEL_SIZE=$(stat -f%z "$MODEL_DIR/model.pt" 2>/dev/null || stat -c%s "$MODEL_DIR/model.pt" 2>/dev/null)
echo "model.pt: $MODEL_SIZE bytes"

echo "=== metadata ==="
cat "$MODEL_DIR/metadata_v3.json" | jq '{
  output_type: .output_type,
  model_name: .model_name,
  resolved_features: (.resolved_features | length),
  training_metrics: .training_metrics
}'
```

**Expected:**
- `model.pt` exists and > 1KB
- `metadata_v3.json` exists and is valid JSON
- `output_type` is `"classification"` (triple barrier maps to standard 3-class classification: BUY/HOLD/SELL)

### 8. Verify 3-Class Output Architecture

**Command:**
```bash
MODEL_DIR=$(ls -td ~/.ktrdr/shared/models/triple_barrier_e2e/1h_v*/ 2>/dev/null | head -1)
if [ -z "$MODEL_DIR" ]; then
  MODEL_DIR="$HOME/.ktrdr/shared/models/triple_barrier_e2e/1h_latest"
fi

uv run python -c "
import torch
state_dict = torch.load('$MODEL_DIR/model.pt', map_location='cpu', weights_only=True)

final_layer_keys = [k for k in state_dict.keys() if 'weight' in k]
last_layer = final_layer_keys[-1]
output_shape = state_dict[last_layer].shape
print(f'Final layer: {last_layer}')
print(f'Output shape: {output_shape}')
print(f'Output dim (num classes): {output_shape[0]}')

if output_shape[0] == 3:
    print('PASS: Model has 3 output neurons (BUY/HOLD/SELL from triple barrier)')
else:
    print(f'FAIL: Model has {output_shape[0]} output neurons, expected 3')
"
```

**Expected:**
- Output dim is 3, corresponding to: BUY (+1 mapped to 0), HOLD (0 mapped to 1), SELL (-1 mapped to 2)
- The class mapping is defined in `training_pipeline.py`: `class_map = {1: 0, 0: 1, -1: 2}`

### 9. Verify Training Metrics Are Valid

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

curl -s "http://localhost:$API_PORT/api/v1/operations/$TASK_ID" | jq '{
  status: .data.status,
  test_accuracy: .data.result_summary.test_metrics.test_accuracy,
  val_accuracy: .data.result_summary.training_metrics.final_val_accuracy,
  val_loss: .data.result_summary.training_metrics.final_val_loss,
  training_time: .data.result_summary.training_metrics.training_time
}'
```

**Expected:**
- `val_loss` > 0 (training happened)
- `training_time` > 0.5 seconds (real training, 10 epochs on filtered data)
- `test_accuracy` between 0.25 and 0.85 (3-class problem: random=0.33, perfect=suspicious)

---

## Success Criteria

- [ ] Strategy with `source: triple_barrier` starts training without validation errors
- [ ] Training completes with status `"completed"`
- [ ] Backend logs show triple barrier label statistics with all 3 classes (TP, SL, Expiry) present
- [ ] **No single class exceeds 60%** of total labels (balanced distribution)
- [ ] **TP and SL each > 15%** (barriers are being hit, not all expiry)
- [ ] CUSUM filter log shows 30-70% of bars retained (meaningful filtering occurred)
- [ ] "After CUSUM filtering" log shows reduced label count
- [ ] Model has 3-class output architecture (BUY/HOLD/SELL)
- [ ] `metadata_v3.json` exists with `output_type: "classification"`
- [ ] Training metrics are present and non-degenerate (test_accuracy between 0.25 and 0.85)

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Training status is "completed", not "failed"** -- A failed training produces no logs, making all log-grep checks vacuously pass (finding nothing is not finding evidence)
- [ ] **Label statistics log line exists** -- If grep finds nothing, the triple barrier path was never executed. Could mean zigzag labels were used instead (wrong source routing)
- [ ] **All 3 classes have > 0 count** -- If TP=0% or SL=0%, barriers are set too wide for the data's volatility. If Expiry=0%, barriers are set too tight
- [ ] **mean_hold > 5 bars** -- If mean_hold is 1-2, every trade hits a barrier on the next bar, meaning barriers are unreasonably tight. This produces labels but they are noise
- [ ] **mean_hold < 45 bars** -- If mean_hold is close to max_holding_period (50), barriers are too wide and almost everything expires. Labels would be dominated by sign-of-return, not barrier events
- [ ] **CUSUM filtering actually reduced count** -- If "After CUSUM filtering" shows the same count as generated labels, the filter passed everything (threshold too low). This means CUSUM is inert
- [ ] **model.pt > 1KB** -- Under 1KB suggests empty or corrupted model save
- [ ] **test_accuracy < 0.85** -- On a 3-class problem with CUSUM-filtered forex data, > 85% accuracy is suspicious. Could indicate data leakage or model collapse to majority class
- [ ] **output_type is "classification"** -- Triple barrier produces 3-class classification labels. The output_type_map in local_orchestrator.py has an explicit entry mapping "triple_barrier" to "classification". If it says something else, the mapping logic or map entry changed

**Sanity check command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

MODEL_DIR=$(ls -td ~/.ktrdr/shared/models/triple_barrier_e2e/1h_v*/ 2>/dev/null | head -1)
if [ -z "$MODEL_DIR" ]; then
  MODEL_DIR="$HOME/.ktrdr/shared/models/triple_barrier_e2e/1h_latest"
fi

echo "=== Training Sanity ==="
curl -s "http://localhost:$API_PORT/api/v1/operations/$TASK_ID" | jq '{
  status: .data.status,
  val_loss: .data.result_summary.training_metrics.final_val_loss,
  training_time: .data.result_summary.training_metrics.training_time,
  test_accuracy: .data.result_summary.test_metrics.test_accuracy
}'

echo "=== File Sanity ==="
test -f "$MODEL_DIR/metadata_v3.json" && echo "PASS: metadata_v3.json exists" || echo "FAIL: metadata_v3.json missing"
test -f "$MODEL_DIR/model.pt" && echo "PASS: model.pt exists" || echo "FAIL: model.pt missing"

MODEL_SIZE=$(stat -f%z "$MODEL_DIR/model.pt" 2>/dev/null || stat -c%s "$MODEL_DIR/model.pt" 2>/dev/null)
echo "model.pt size: $MODEL_SIZE bytes"
test "$MODEL_SIZE" -gt 1024 && echo "PASS: model.pt > 1KB" || echo "FAIL: model.pt suspiciously small"

echo "=== Label Distribution Sanity ==="
docker compose -f docker-compose.sandbox.yml logs backend --since 15m 2>/dev/null | \
  grep -i "triple barrier labels" | tail -1

echo "=== CUSUM Sanity ==="
docker compose -f docker-compose.sandbox.yml logs backend --since 15m 2>/dev/null | \
  grep -i "CUSUM filter\|After CUSUM" | tail -3

echo "=== Architecture Sanity ==="
uv run python -c "
import torch
sd = torch.load('$MODEL_DIR/model.pt', map_location='cpu', weights_only=True)
final = [k for k in sd if 'weight' in k][-1]
out_dim = sd[final].shape[0]
print(f'output_dim={out_dim}')
assert out_dim == 3, f'FAIL: output_dim={out_dim}, expected 3'
print('PASS: 3-class output confirmed (BUY/HOLD/SELL)')
"
```

---

## Troubleshooting

**If training fails with "Unknown label source 'triple_barrier'":**
- **Cause:** `create_labels()` in `training_pipeline.py` does not have the `source == "triple_barrier"` branch
- **Category:** CODE_BUG
- **Cure:** Check `training_pipeline.py` line ~543 for the triple_barrier handling block. Must import and invoke `TripleBarrierLabeler`

**If training fails with "Insufficient data" from TripleBarrierLabeler:**
- **Cause:** Data has fewer bars than `max_holding_period + vol_span` (100 bars minimum)
- **Category:** TEST_ISSUE
- **Cure:** Ensure the date range 2024-01-01 to 2025-01-01 yields ~6,500 1h bars. Check data availability: `curl http://localhost:$API_PORT/api/v1/data/range?symbol=EURUSD&timeframe=1h`

**If CUSUM filter retains < 10% of bars:**
- **Cause:** Auto-threshold (cusum_multiplier=1.0 * mean_vol) may be too high for the data period's volatility
- **Category:** TEST_ISSUE
- **Cure:** The strategy uses `cusum_threshold: 0` which triggers auto-threshold mode. If EURUSD 2024 vol is unusually low, the threshold captures too few events. Try increasing cusum_multiplier or using a fixed threshold

**If CUSUM filter retains > 90% of bars:**
- **Cause:** Auto-threshold is too low relative to typical log-return magnitudes
- **Category:** TEST_ISSUE
- **Cure:** The CUSUMFilter uses `cusum_multiplier * ewma_vol_mean` as threshold. If EURUSD 2024 is volatile, the threshold may be too permissive. The filter is still technically running but not filtering meaningfully

**If all labels are class 0 (HOLD/expiry):**
- **Cause:** Barriers are too wide -- TP and SL never hit within max_holding_period
- **Category:** CODE_BUG or TEST_ISSUE
- **Cure:** Check that vol calculation is correct. With pt=2.0 and sl=1.5 on EURUSD 1h EWMA vol (~0.001-0.003), barriers should be at ~0.2-0.6% from entry. If vol is computed as 0 or NaN, barriers are at exactly the entry price (division by zero edge case)

**If label distribution is heavily skewed (one class > 70%):**
- **Cause:** Barrier asymmetry or market regime. With pt=2.0 / sl=1.5, TP barrier is wider so SL should hit more often. In a trending year, TP could dominate
- **Category:** TEST_ISSUE
- **Cure:** This is not necessarily a bug -- it reflects market characteristics. Adjust multipliers if needed. The key assertion is that ALL THREE classes exist with > 0 count

**If output_type is not "classification":**
- **Cause:** The `output_type_map` in `local_orchestrator.py` (line ~731) was updated to include a specific triple_barrier mapping
- **Category:** EXPECTED_CHANGE
- **Cure:** If a specific output_type like "triple_barrier_classification" was added, update this test's assertion accordingly. The current default is "classification" because triple_barrier is not in the map

**If training times out (> 10 minutes):**
- **Cause:** Worker busy, or the triple barrier labeling loop is slow on large datasets (it's O(n * max_holding_period))
- **Category:** ENVIRONMENT
- **Cure:** Check workers: `curl http://localhost:$API_PORT/api/v1/workers | jq`. With ~6,500 bars and max_hold=50, the labeling loop processes ~325,000 iterations -- should complete in < 5 seconds

---

## Evidence to Capture

- Training Operation ID: `$TASK_ID`
- Final status: `curl ... | jq '.data.status'`
- Training metrics: `curl ... | jq '.data.result_summary'`
- Label statistics log line: `docker compose logs | grep "triple barrier labels"`
- CUSUM filter log line: `docker compose logs | grep "CUSUM filter"`
- CUSUM retention log line: `docker compose logs | grep "After CUSUM filtering"`
- Model directory path: `$MODEL_DIR`
- metadata_v3.json contents: `cat $MODEL_DIR/metadata_v3.json | jq .`
- Model output dimensions: Python torch.load inspection of final layer shape

---

## Notes

- **Port variable:** Read from `.env.sandbox` as `KTRDR_API_PORT` (slot 1 = port 8001).
- **3 classes, not 4:** Triple barrier produces +1/0/-1 mapped to 3 classes (BUY=0, HOLD=1, SELL=2). This is different from regime classification which has 4 classes.
- **output_type is "classification" (default):** The `output_type_map` in `local_orchestrator.py` does not have a specific entry for "triple_barrier" -- it falls through to the default "classification". This is correct behavior because triple barrier IS a classification problem, just with different label semantics than zigzag.
- **CUSUM is applied AFTER labeling:** The training pipeline generates labels for all bars, THEN filters to keep only CUSUM event bars. This means the "Generated N triple barrier labels" log shows pre-filter count, and "After CUSUM filtering" shows post-filter count.
- **cusum_threshold: 0 means auto-threshold:** Setting threshold to 0 in the strategy triggers the auto-threshold path in CUSUMFilter (threshold=None if threshold==0, cusum_multiplier=1.0 * mean_vol). A nonzero value would use a fixed threshold.
- **Barrier width scales with vol:** The labeler computes `upper = entry * (1 + pt_multiplier * ewma_vol)`. Higher volatility = wider barriers. This is by design -- barriers adapt to market conditions rather than using fixed pip amounts.
- **Log inspection is the primary evidence:** Unlike regime-classifier tests that can inspect metadata for class counts, triple barrier label statistics are logged but NOT saved to metadata_v3.json. The primary evidence comes from grepping backend logs.
- **Metadata file is metadata_v3.json:** Not `metadata.json`. The v3 pipeline saves to `metadata_v3.json`.
- **Strategy file naming:** The YAML file is `triple_barrier_e2e_v3.yaml` but the strategy name (inside the file) is `triple_barrier_e2e`. The API request uses the strategy name, not the filename.
