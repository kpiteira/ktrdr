# Test: backtest/lstm-temporal-backtest

**Purpose:** Validate that a trained LSTM temporal model loads correctly via ModelBundle, receives sequence windows from FeatureCache, and produces trades through the backtest pipeline.
**Duration:** <180 seconds (cold start possible on first LSTM inference)
**Category:** Backtest

**Dependency:** Requires a trained LSTM model at `~/.ktrdr/shared/models/trend_tb_lstm_signal_v1/1h_latest`. Run the LSTM training test first if model does not exist.

---

## Pre-Flight Checks

**Required modules:**
- [common](../../../e2e-testing/preflight/common.md) -- Docker, sandbox, API health

**Test-specific checks:**
- [ ] Sandbox is running (`.env.sandbox` exists, container `slot-1-backend-1` is up)
- [ ] LSTM model bundle exists inside container (`model.pt` + `metadata_v3.json`)
- [ ] `metadata_v3.json` contains `model_type: "lstm"` and `sequence_length` field
- [ ] Strategy YAML exists in shared strategies dir
- [ ] EURUSD 1h data is cached and available inside container
- [ ] Container has torch available

**Pre-flight commands:**
```bash
source .env.sandbox
CONTAINER="slot-1-backend-1"

# 1. Container is running
docker ps --filter "name=$CONTAINER" --format "{{.Names}}" | grep -q "$CONTAINER" || {
  echo "FAIL: Container $CONTAINER not running"
  exit 1
}
echo "OK: Container running"

# 2. LSTM model bundle exists
MODEL_DIR="/app/models/trend_tb_lstm_signal_v1/1h_latest"
docker exec "$CONTAINER" test -f "$MODEL_DIR/model.pt" || {
  echo "FAIL: Model not found: $MODEL_DIR/model.pt"
  echo "CURE: Run LSTM training test first"
  exit 1
}
docker exec "$CONTAINER" test -f "$MODEL_DIR/metadata_v3.json" || {
  echo "FAIL: Metadata not found: $MODEL_DIR/metadata_v3.json"
  exit 1
}
echo "OK: Model bundle exists"

# 3. Metadata confirms LSTM type and has sequence_length
docker exec "$CONTAINER" python -c "
import json
with open('$MODEL_DIR/metadata_v3.json') as f:
    meta = json.load(f)
model_type = meta.get('model_type', 'mlp')
seq_len = meta.get('sequence_length')
assert model_type == 'lstm', f'Expected model_type=lstm, got {model_type}'
assert seq_len is not None and seq_len > 0, f'sequence_length missing or invalid: {seq_len}'
print(f'model_type={model_type}, sequence_length={seq_len}')
" || {
  echo "FAIL: Metadata does not indicate LSTM model"
  exit 1
}
echo "OK: Metadata confirms LSTM"

# 4. Strategy YAML exists
docker exec "$CONTAINER" test -f "/app/strategies/trend_tb_lstm_signal_v1.yaml" || {
  echo "FAIL: Strategy YAML not found"
  exit 1
}
echo "OK: Strategy exists"

# 5. Torch available
docker exec "$CONTAINER" python -c "import torch; print(f'torch {torch.__version__}')" || {
  echo "FAIL: torch not available in container"
  exit 1
}
echo "OK: torch available"

# 6. EURUSD 1h data exists for backtest range
docker exec "$CONTAINER" python -c "
from ktrdr.data.repository import DataRepository
repo = DataRepository()
df = repo.load_from_cache('EURUSD', '1h', '2024-07-01', '2024-12-31')
print(f'EURUSD 1h bars: {len(df)}')
assert len(df) > 100, f'Insufficient data: {len(df)} bars'
" || {
  echo "FAIL: EURUSD 1h data not available for 2024-07 to 2024-12"
  exit 1
}

echo "All pre-flight checks passed"
```

---

## Test Data

```json
{
  "strategy_name": "trend_tb_lstm_signal_v1",
  "symbol": "EURUSD",
  "timeframe": "1h",
  "start_date": "2024-07-01",
  "end_date": "2024-12-31",
  "model_path": "models/trend_tb_lstm_signal_v1/1h_latest"
}
```

**Why this data:**
- 6-month range (Jul-Dec 2024) provides ~4300 bars -- enough for meaningful trading and well outside training data (trained on 2020-2023)
- 1h timeframe avoids multi-TF data loading bugs (known issue)
- Out-of-sample period validates generalization, not memorization
- `1h_latest` symlink points to the most recent training run output
- sequence_length=20 means first ~20 bars should produce no trades (insufficient history for the LSTM window)

---

## Execution Steps

### 1. Verify ModelBundle Loads with LSTM Architecture

**Command:**
```bash
source .env.sandbox
CONTAINER="slot-1-backend-1"

docker exec "$CONTAINER" python -c "
from ktrdr.backtesting.model_bundle import ModelBundle

bundle = ModelBundle.load('/app/models/trend_tb_lstm_signal_v1/1h_latest')

model_type = bundle.metadata.model_type
seq_len = bundle.metadata.sequence_length
feature_count = len(bundle.feature_names)
output_type = bundle.metadata.output_type

print(f'model_type={model_type}')
print(f'sequence_length={seq_len}')
print(f'feature_count={feature_count}')
print(f'output_type={output_type}')

# Verify LSTM architecture reconstructed correctly
model = bundle.model
has_lstm_layer = any('lstm' in name.lower() for name, _ in model.named_modules())
print(f'has_lstm_layer={has_lstm_layer}')

# Verify model accepts 3D input (batch, seq_len, features)
import torch
dummy_input = torch.randn(1, seq_len, feature_count)
with torch.no_grad():
    output = model(dummy_input)
print(f'output_shape={list(output.shape)}')
print('MODEL_BUNDLE_OK: True')
"
```

**Expected:**
- `model_type=lstm`
- `sequence_length=20` (or whatever the strategy specifies)
- `feature_count > 0`
- `output_type=classification`
- `has_lstm_layer=True`
- `output_shape=[1, C]` where C is the number of classes
- `MODEL_BUNDLE_OK: True`

### 2. Verify FeatureCache.get_feature_window() Works

**Command:**
```bash
source .env.sandbox
CONTAINER="slot-1-backend-1"

docker exec "$CONTAINER" python -c "
import asyncio
from ktrdr.backtesting.model_bundle import ModelBundle
from ktrdr.backtesting.feature_cache import FeatureCache
from ktrdr.data.repository import DataRepository

bundle = ModelBundle.load('/app/models/trend_tb_lstm_signal_v1/1h_latest')
seq_len = bundle.metadata.sequence_length

# Load data
repo = DataRepository()
df = asyncio.run(repo.load_from_cache('EURUSD', '1h', '2024-07-01', '2024-12-31'))
print(f'data_bars={len(df)}')

# Build feature cache
cache = FeatureCache(bundle=bundle)
cache.compute_features(df)

# Test early timestamp (insufficient history)
early_ts = df.index[seq_len - 5]  # 5 bars short of full window
window_early = cache.get_feature_window(early_ts, seq_len)
print(f'early_window_is_none={window_early is None}')

# Test valid timestamp (enough history)
valid_ts = df.index[seq_len + 10]
window_valid = cache.get_feature_window(valid_ts, seq_len)
print(f'valid_window_shape={list(window_valid.shape) if window_valid is not None else None}')
print(f'valid_window_cols={len(window_valid.columns) if window_valid is not None else 0}')

# Verify window has correct sequence length rows
if window_valid is not None:
    assert window_valid.shape[0] == seq_len, f'Expected {seq_len} rows, got {window_valid.shape[0]}'
    assert window_valid.shape[1] == len(bundle.feature_names), f'Feature count mismatch'

print('FEATURE_WINDOW_OK: True')
"
```

**Expected:**
- `early_window_is_none=True` (insufficient history for full sequence)
- `valid_window_shape=[20, F]` where F matches feature count
- `FEATURE_WINDOW_OK: True`

### 3. Run Full Backtest via API

**Command:**
```bash
source .env.sandbox

RESPONSE=$(curl -s -X POST http://localhost:${KTRDR_API_PORT}/api/v1/backtests/start \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "trend_tb_lstm_signal_v1",
    "symbol": "EURUSD",
    "timeframe": "1h",
    "start_date": "2024-07-01",
    "end_date": "2024-12-31",
    "model_path": "models/trend_tb_lstm_signal_v1/1h_latest"
  }')

echo "$RESPONSE" | jq .
OPERATION_ID=$(echo "$RESPONSE" | jq -r '.operation_id')
echo "Operation ID: $OPERATION_ID"
```

**Expected:**
- HTTP 200 with `operation_id` returned
- No immediate errors

### 4. Poll Until Completion

**Command:**
```bash
source .env.sandbox

for i in $(seq 1 36); do
  sleep 5
  RESULT=$(curl -s "http://localhost:${KTRDR_API_PORT}/api/v1/operations/$OPERATION_ID")
  STATUS=$(echo "$RESULT" | jq -r '.data.status')
  PROGRESS=$(echo "$RESULT" | jq -r '.data.progress // "N/A"')
  echo "Poll $i: status=$STATUS progress=$PROGRESS"
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
done
```

**Expected:**
- Status transitions from `running` to `completed`
- Should complete within 180 seconds (36 polls x 5s)
- If `failed`, capture error from result_summary for troubleshooting

### 5. Validate Results Structure and Content

**Command:**
```bash
source .env.sandbox

RESULT=$(curl -s "http://localhost:${KTRDR_API_PORT}/api/v1/operations/$OPERATION_ID")

echo "=== Status ==="
echo "$RESULT" | jq '.data.status'

echo "=== Trade Count ==="
TRADE_COUNT=$(echo "$RESULT" | jq '.data.result_summary.trade_count // .data.result_summary.total_trades // 0')
echo "trade_count=$TRADE_COUNT"

echo "=== Metrics ==="
echo "$RESULT" | jq '{
  total_return: .data.result_summary.metrics.total_return,
  sharpe_ratio: .data.result_summary.metrics.sharpe_ratio,
  win_rate: .data.result_summary.metrics.win_rate,
  max_drawdown: .data.result_summary.metrics.max_drawdown
}'

echo "=== Total Bars ==="
TOTAL_BARS=$(echo "$RESULT" | jq '.data.result_summary.total_bars // 0')
echo "total_bars=$TOTAL_BARS"

echo "=== Execution Time ==="
EXEC_TIME=$(echo "$RESULT" | jq '.data.result_summary.execution_time_seconds // 0')
echo "execution_time=$EXEC_TIME"
```

**Expected:**
- `status` is `"completed"`
- `trade_count > 0` (LSTM model should produce at least some trades over 6 months)
- `total_return` present (may be negative)
- `sharpe_ratio` present (may be negative)
- `win_rate` present
- `max_drawdown` present
- `total_bars > 3000` (6 months 1h ~4300 bars)
- `execution_time_seconds > 1.0`

### 6. Check Logs for LSTM-Specific Errors

**Command:**
```bash
source .env.sandbox

# Check for unsupported model type errors -- this is the critical failure mode
docker compose -f docker-compose.sandbox.yml logs backend --since 10m 2>/dev/null | \
  grep -i "unsupported model type\|unknown model type\|model_type.*error" | head -5

# Check for sequence/window-related errors
docker compose -f docker-compose.sandbox.yml logs backend --since 10m 2>/dev/null | \
  grep -i "feature_window\|sequence.*error\|insufficient.*history" | head -5

# Check for tensor shape mismatches (LSTM expects 3D input)
docker compose -f docker-compose.sandbox.yml logs backend --since 10m 2>/dev/null | \
  grep -i "expected.*dim\|shape.*mismatch\|RuntimeError" | head -5
```

**Expected:**
- No "Unsupported model type" errors
- No "shape mismatch" or RuntimeError lines
- Warnings about insufficient history for early bars are acceptable (expected behavior)

---

## Success Criteria

- [ ] ModelBundle loads LSTM model correctly (`model_type=lstm`, LSTM layer present) (Step 1)
- [ ] FeatureCache.get_feature_window() returns None for early timestamps and valid windows for later ones (Step 2)
- [ ] Backtest starts successfully via API (operation_id returned) (Step 3)
- [ ] Backtest completes with status `"completed"` (Step 4)
- [ ] `trade_count > 0` (model produces trades over the 6-month period) (Step 5)
- [ ] PnL metrics present: `sharpe_ratio`, `win_rate`, `max_drawdown`, `total_return` all exist (Step 5)
- [ ] `total_bars > 3000` (real data was processed, not empty run) (Step 5)
- [ ] No "Unsupported model type" errors in logs (Step 6)
- [ ] No tensor shape mismatch errors in logs (Step 6)

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **total_bars > 3000** -- 6 months of 1h EURUSD is ~4300 bars. Fewer than 3000 suggests data truncation or early abort. This catches the scenario where FeatureCache fails silently and returns partial data.

- [ ] **trade_count > 0** -- An LSTM model trained on 4 years of data backtested over 6 months should produce at least some trades. Zero trades means either: (a) DecisionFunction is not receiving DataFrame input (falling through to MLP dict path and erroring silently), or (b) get_feature_window() is returning None for all timestamps. This is the primary signal that the LSTM integration is actually working.

- [ ] **trade_count < total_bars** -- If trade_count equals total_bars, the model is signaling on every single bar, which indicates a degenerate model or broken signal extraction. Healthy trading should have trade_count well below total_bars.

- [ ] **First ~20 bars have no trades** -- The LSTM needs `sequence_length` bars of history before it can make predictions. If trades appear in the first 20 bars, get_feature_window() is not properly gating on insufficient history, or the backtest is falling back to MLP path. Verify this by checking if any trade timestamps are within the first sequence_length bars of the backtest range.

- [ ] **execution_time_seconds > 2.0** -- LSTM inference is more expensive than MLP (matrix multiplications over 20 timesteps per bar, ~4300 bars total). Under 2 seconds suggests the LSTM forward pass was bypassed or the loop exited early.

- [ ] **execution_time_seconds < 300** -- Over 5 minutes for 4300 bars of 1h inference means something is wrong (batching issue, memory leak, GPU/CPU fallback problem). Normal range is 10-60 seconds.

- [ ] **Metrics are finite, not NaN** -- If sharpe_ratio, win_rate, or max_drawdown are null/NaN despite trade_count > 0, the PnL calculation pipeline broke somewhere. This catches numeric overflow from improper position sizing.

**Sanity check command (from Step 5 output):**
```bash
# Verify early bars have no trades
source .env.sandbox
CONTAINER="slot-1-backend-1"

docker exec "$CONTAINER" python -c "
import json
# If backtest results include trade details with timestamps,
# verify none fall within the first sequence_length bars
# This is a structural validation of the LSTM windowing
print('NOTE: Verify from trade list that no trades occur before bar ~20')
print('SANITY_CHECK: Manual inspection of trade timestamps required')
"
```

---

## Troubleshooting

**If ModelBundle.load() fails with "Unsupported model type: lstm":**
- **Cause:** ModelBundle.load() does not have the LSTM dispatch path yet (M2 Task 2.3 not implemented)
- **Category:** CODE_BUG
- **Cure:** Check `ktrdr/backtesting/model_bundle.py` load() method for lstm/gru dispatch. The architecture doc specifies the required dispatch pattern.

**If backtest fails with "expected 2 dimensions but got 3" (or vice versa):**
- **Cause:** Tensor shape mismatch -- MLP expects (B, F) but LSTM provides (B, S, F), or LSTM model receives (B, F) because DecisionFunction is not passing windows
- **Category:** CODE_BUG
- **Cure:** Check `ktrdr/backtesting/decision_function.py` _predict() -- it must detect DataFrame input and produce 3D tensor for LSTM models. Check that the backtest loop calls get_feature_window() instead of get_features_for_timestamp() for temporal models.

**If trade_count is 0 but status is "completed":**
- **Cause:** get_feature_window() may be returning None for all timestamps (off-by-one in index calculation, or features not computed correctly). Or DecisionFunction may not recognize the DataFrame input.
- **Category:** CODE_BUG or TEST_ISSUE
- **Cure:** Run Step 2 (feature window validation) to isolate. If Step 2 passes, add debug logging in the backtest loop to check what _predict() receives. If sequence_length is very large relative to available data, reduce it.

**If model loads but produces identical predictions for every bar:**
- **Cause:** Model collapse during training (all outputs same class). Or scaler not applied correctly to sequence windows.
- **Category:** TEST_ISSUE (model quality, not code bug)
- **Cure:** Check training metrics. Verify the scaler used during training is saved and applied during inference. If training accuracy was suspiciously high (>95%), the model likely overfit or collapsed.

**If backtest times out (>180s):**
- **Cause:** LSTM inference on CPU for ~4300 bars can be slow, especially on first run. Worker may be busy from another operation.
- **Category:** ENVIRONMENT
- **Cure:** Check workers: `curl http://localhost:${KTRDR_API_PORT}/api/v1/workers | jq '.workers[] | select(.type=="backtest")'`. Retry once -- second run benefits from warm caches. If still slow, check if model was saved with GPU tensors but container only has CPU.

**If metadata_v3.json does not contain model_type field:**
- **Cause:** Training pipeline does not yet save model_type to metadata (M1 may not include this)
- **Category:** CODE_BUG
- **Cure:** Check `ktrdr/models/model_metadata.py` for model_type field. Check training pipeline saves it. The field should default to "mlp" for backward compatibility but must be "lstm" for LSTM-trained models.

**If DataRepository.load_from_cache fails with "No data found":**
- **Cause:** EURUSD 1h data not cached for the 2024-07 to 2024-12 range
- **Category:** ENVIRONMENT
- **Cure:** Load data: `docker exec $CONTAINER python -c "from ktrdr.data.repository import DataRepository; import asyncio; asyncio.run(DataRepository().fetch_and_cache('EURUSD', '1h', '2024-07-01', '2024-12-31'))"` or via CLI: `uv run ktrdr data load EURUSD 1h --start-date 2024-07-01 --end-date 2024-12-31`

---

## Evidence to Capture

- Pre-flight: metadata_v3.json content (model_type, sequence_length, feature_names)
- Step 1: ModelBundle load output (model_type, seq_len, feature_count, output shape)
- Step 2: Feature window validation (early=None, valid=correct shape)
- Step 3: Backtest start response (operation_id)
- Step 5: Full result summary JSON:
  - `trade_count`
  - `total_bars`
  - `total_return`
  - `sharpe_ratio`
  - `win_rate`
  - `max_drawdown`
  - `execution_time_seconds`
- Step 6: Any error lines from container logs (expect empty)
- Container logs: `docker compose -f docker-compose.sandbox.yml logs backend --since 10m 2>/dev/null | tail -50`

---

## Notes

- **Port variable:** Read from `.env.sandbox` as `KTRDR_API_PORT` (slot 1 = port 8001).
- **Container name:** `slot-1-backend-1` (from COMPOSE_PROJECT_NAME=slot-1 in .env.sandbox).
- **Model paths are container-internal:** `/app/models/` maps to `$KTRDR_MODELS_DIR` on host (`~/.ktrdr/shared/models`).
- **Non-determinism:** LSTM outputs are non-deterministic (neural network inference). Assert structure (fields present, types correct, counts reasonable) rather than specific trade outcomes or exact PnL values.
- **Sequence length gating:** The LSTM model with sequence_length=20 should produce no predictions for the first 19 bars. This is a key differentiator from MLP backtests and the primary structural assertion unique to this test.
- **Dependency chain:** This test requires a trained LSTM model. If the model does not exist, run the LSTM training test (training/lstm-temporal) first. The training test saves the model to the expected path with proper metadata.
- **Cold start:** First LSTM inference in a fresh container may be slower due to torch JIT warmup. The 180s timeout accounts for this.
- **API vs direct execution:** Steps 1-2 use docker exec for fine-grained component validation. Steps 3-5 use the API for end-to-end pipeline validation. Both are needed -- the component tests isolate where failures occur, the API test validates the full integration.
