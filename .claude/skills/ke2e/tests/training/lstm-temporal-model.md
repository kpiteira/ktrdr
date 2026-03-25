# Test: training/lstm-temporal-model

**Purpose:** Validate that an LSTM temporal signal model trains end-to-end through the ktrdr training pipeline, producing correct artifacts with LSTM-specific metadata (model_type, sequence_length) and a model architecture that accepts sequential input.
**Duration:** ~8-15 minutes (6 months of multi-TF 5m+1h data, up to 200 epochs with early stopping)
**Category:** Training (LSTM Temporal Model)

**Dependency:** M1 of temporal-signal-models must be implemented (LSTMTradingModel, SequenceDataset, ModelTrainer integration, create_model dispatch)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../../e2e-testing/preflight/common.md) -- Docker, sandbox, API health
- [training](../../../e2e-testing/preflight/training.md) -- Strategy, data, workers

**Test-specific checks:**
- [ ] EURUSD 1h data available (6 months: 2024-01-01 to 2024-06-30)
- [ ] EURUSD 5m data available (strategy uses multi-TF: 5m + 1h)
- [ ] At least one idle training worker
- [ ] No stale model from a previous run at `~/.ktrdr/shared/models/trend_tb_lstm_signal_v1/`

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

# 3. Strategy file exists
test -f ~/.ktrdr/shared/strategies/trend_tb_lstm_signal_v1.yaml || {
  echo "FAIL: Strategy file not found. Copy from repo: cp strategies/trend_tb_lstm_signal_v1.yaml ~/.ktrdr/shared/strategies/"
  exit 1
}
echo "Strategy file found"
```

---

## Test Data

### Strategy: `trend_tb_lstm_signal_v1.yaml`

This strategy is part of the repo at `strategies/trend_tb_lstm_signal_v1.yaml`. It uses:
- **model.type: lstm** with `sequence_length: 20`, `hidden_size: 64`, `num_layers: 2`
- **Multi-timeframe:** 5m + 1h (base: 1h)
- **Triple barrier labels** with focal loss
- **4 indicators:** RSI, ADX, MACD, ROC -- each with fuzzy + raw hybrid inputs
- **Early stopping:** patience=20, min_delta=0.001
- **200 max epochs** (early stopping will typically cut this to 40-80)

**Why this strategy tests LSTM specifically:**
- `model.type: lstm` triggers the new LSTM code path in create_model() and ModelTrainer
- `sequence_length: 20` means SequenceDataset must create sliding windows of 20 bars
- The model receives (batch, 20, F) tensors, not (batch, F) like MLP
- Multi-TF + hybrid inputs produce a rich feature set (~32 features) that exercises the full pipeline
- If SequenceDataset is missing or broken, training will fail with shape mismatch errors

**Why this data range:**
- 6 months (Jan-Jun 2024) provides ~3,000 1h bars
- After triple barrier labeling and sequence windowing, effective samples ~2,800
- Enough for meaningful train/val/test splits while keeping training time under 15 minutes
- Early stopping at patience=20 will typically terminate well before epoch 200

### Request Payload

```json
{
  "symbols": ["EURUSD"],
  "timeframes": ["5m", "1h"],
  "strategy_name": "trend_tb_lstm_signal_v1",
  "start_date": "2024-01-01",
  "end_date": "2024-06-30"
}
```

---

## Execution Steps

### 1. Copy Strategy File to Shared Directory

**Command:**
```bash
# Strategy lives in repo; copy to shared location where the backend reads it
cp strategies/trend_tb_lstm_signal_v1.yaml ~/.ktrdr/shared/strategies/
echo "Strategy copied"
ls -la ~/.ktrdr/shared/strategies/trend_tb_lstm_signal_v1.yaml
```

**Expected:**
- File exists at shared strategies location

### 2. Remove Previous Model (Clean Slate)

**Command:**
```bash
MODEL_DIR="$HOME/.ktrdr/shared/models/trend_tb_lstm_signal_v1"
if [ -d "$MODEL_DIR" ]; then
  echo "Previous model found at $MODEL_DIR -- removing for clean test"
  rm -rf "$MODEL_DIR"
fi
echo "Clean slate confirmed"
```

**Expected:**
- No pre-existing model artifacts that could give false-positive results

### 3. Start Training via CLI

**Command:**
```bash
source .env.sandbox

uv run ktrdr models train trend_tb_lstm_signal_v1.yaml EURUSD 1h \
  --start-date 2024-01-01 --end-date 2024-06-30 --follow
```

**Expected:**
- Training starts without validation errors
- Progress output shows epochs advancing
- No shape mismatch errors (proves SequenceDataset is feeding correct (batch, seq_len, features) tensors)
- Completes within ~15 minutes (early stopping should trigger sooner)
- Exit code 0

**Alternative (API path):**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

RESPONSE=$(curl -s -X POST "http://localhost:$API_PORT/api/v1/trainings/start" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["EURUSD"],
    "timeframes": ["5m", "1h"],
    "strategy_name": "trend_tb_lstm_signal_v1",
    "start_date": "2024-01-01",
    "end_date": "2024-06-30"
  }')

echo "Training Response: $RESPONSE"

TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id')
echo "Task ID: $TASK_ID"
```

### 4. Wait for Training Completion (API path only)

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Poll every 20s for up to 15 minutes (LSTM trains longer than MLP)
for i in $(seq 1 45); do
  sleep 20
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
- Total wait < 15 minutes

### 5. Verify Model Directory and Required Files

**Command:**
```bash
MODEL_BASE="$HOME/.ktrdr/shared/models/trend_tb_lstm_signal_v1"

# Find the actual version directory
MODEL_DIR=$(ls -td "$MODEL_BASE"/1h_v*/ 2>/dev/null | head -1)
if [ -z "$MODEL_DIR" ]; then
  MODEL_DIR="$MODEL_BASE/1h_latest"
fi
echo "Model directory: $MODEL_DIR"

echo "=== Directory listing ==="
ls -la "$MODEL_DIR/"

echo "=== Required files check ==="
test -f "$MODEL_DIR/model.pt" && echo "PASS: model.pt exists" || echo "FAIL: model.pt missing"
test -f "$MODEL_DIR/metadata_v3.json" && echo "PASS: metadata_v3.json exists" || echo "FAIL: metadata_v3.json missing"
test -f "$MODEL_DIR/config.json" && echo "PASS: config.json exists" || echo "FAIL: config.json missing"

echo "=== File sizes ==="
MODEL_SIZE=$(stat -f%z "$MODEL_DIR/model.pt" 2>/dev/null || stat -c%s "$MODEL_DIR/model.pt" 2>/dev/null)
echo "model.pt: $MODEL_SIZE bytes"
test "$MODEL_SIZE" -gt 1024 && echo "PASS: model.pt > 1KB" || echo "FAIL: model.pt suspiciously small ($MODEL_SIZE bytes)"
```

**Expected:**
- `model.pt` exists and > 1KB (LSTM with hidden_size=64, 2 layers should be at least 50KB)
- `metadata_v3.json` exists and is valid JSON
- `config.json` exists and is valid JSON

### 6. Verify config.json Contains LSTM Architecture

**Command:**
```bash
MODEL_BASE="$HOME/.ktrdr/shared/models/trend_tb_lstm_signal_v1"
MODEL_DIR=$(ls -td "$MODEL_BASE"/1h_v*/ 2>/dev/null | head -1)
if [ -z "$MODEL_DIR" ]; then MODEL_DIR="$MODEL_BASE/1h_latest"; fi

echo "=== config.json model section ==="
cat "$MODEL_DIR/config.json" | jq '.model'

echo "=== LSTM-specific checks ==="
MODEL_TYPE=$(cat "$MODEL_DIR/config.json" | jq -r '.model.type')
SEQ_LEN=$(cat "$MODEL_DIR/config.json" | jq -r '.model.architecture.sequence_length')
HIDDEN=$(cat "$MODEL_DIR/config.json" | jq -r '.model.architecture.hidden_size')
LAYERS=$(cat "$MODEL_DIR/config.json" | jq -r '.model.architecture.num_layers')

echo "model.type: $MODEL_TYPE"
echo "sequence_length: $SEQ_LEN"
echo "hidden_size: $HIDDEN"
echo "num_layers: $LAYERS"

test "$MODEL_TYPE" = "lstm" && echo "PASS: model type is lstm" || echo "FAIL: model type is '$MODEL_TYPE', expected 'lstm'"
test "$SEQ_LEN" = "20" && echo "PASS: sequence_length is 20" || echo "FAIL: sequence_length is '$SEQ_LEN', expected 20"
test "$HIDDEN" = "64" && echo "PASS: hidden_size is 64" || echo "FAIL: hidden_size is '$HIDDEN', expected 64"
test "$LAYERS" = "2" && echo "PASS: num_layers is 2" || echo "FAIL: num_layers is '$LAYERS', expected 2"
```

**Expected:**
- `model.type` is `"lstm"` (not `"mlp"`)
- `architecture.sequence_length` is 20
- `architecture.hidden_size` is 64
- `architecture.num_layers` is 2

### 7. Verify metadata_v3.json Contents

**Command:**
```bash
MODEL_BASE="$HOME/.ktrdr/shared/models/trend_tb_lstm_signal_v1"
MODEL_DIR=$(ls -td "$MODEL_BASE"/1h_v*/ 2>/dev/null | head -1)
if [ -z "$MODEL_DIR" ]; then MODEL_DIR="$MODEL_BASE/1h_latest"; fi

echo "=== metadata_v3.json ==="
cat "$MODEL_DIR/metadata_v3.json" | jq '{
  model_name: .model_name,
  output_type: .output_type,
  strategy_version: .strategy_version,
  resolved_features_count: (.resolved_features | length),
  training_symbols: .training_symbols,
  training_timeframes: .training_timeframes,
  training_metrics: .training_metrics
}'

# Check output_type
OUTPUT_TYPE=$(cat "$MODEL_DIR/metadata_v3.json" | jq -r '.output_type')
echo "output_type: $OUTPUT_TYPE"
test "$OUTPUT_TYPE" = "classification" && echo "PASS: output_type is classification" || echo "FAIL: output_type is '$OUTPUT_TYPE'"

# Check resolved features exist (non-empty list)
FEAT_COUNT=$(cat "$MODEL_DIR/metadata_v3.json" | jq '.resolved_features | length')
echo "resolved_features count: $FEAT_COUNT"
test "$FEAT_COUNT" -gt 0 && echo "PASS: resolved_features non-empty" || echo "FAIL: resolved_features is empty"
```

**Expected:**
- `output_type` is `"classification"` (triple barrier maps to classification)
- `resolved_features` is a non-empty list (should be ~32 features from 4 indicators x 2 timeframes x fuzzy+raw)
- `training_symbols` includes "EURUSD"
- `training_timeframes` includes "1h" (and possibly "5m")

### 8. Verify LSTM Architecture via torch Inspection

**Command:**
```bash
MODEL_BASE="$HOME/.ktrdr/shared/models/trend_tb_lstm_signal_v1"
MODEL_DIR=$(ls -td "$MODEL_BASE"/1h_v*/ 2>/dev/null | head -1)
if [ -z "$MODEL_DIR" ]; then MODEL_DIR="$MODEL_BASE/1h_latest"; fi

uv run python -c "
import torch

state_dict = torch.load('$MODEL_DIR/model.pt', map_location='cpu', weights_only=True)

print('=== State dict keys ===')
for k, v in state_dict.items():
    print(f'  {k}: {v.shape}')

# Check for LSTM-specific layer names
lstm_keys = [k for k in state_dict.keys() if 'lstm' in k.lower()]
print(f'\nLSTM layers found: {len(lstm_keys)}')
if lstm_keys:
    print('PASS: Model contains LSTM layers')
else:
    # May use different naming -- check for weight_ih (LSTM signature parameter)
    ih_keys = [k for k in state_dict.keys() if 'weight_ih' in k]
    hh_keys = [k for k in state_dict.keys() if 'weight_hh' in k]
    if ih_keys or hh_keys:
        print(f'PASS: Model contains LSTM params (weight_ih: {len(ih_keys)}, weight_hh: {len(hh_keys)})')
    else:
        print('FAIL: No LSTM layers found in state dict')

# Check output layer has 3 neurons (BUY/HOLD/SELL from triple barrier)
weight_keys = [k for k in state_dict.keys() if 'weight' in k and 'bias' not in k.replace('weight','')]
if weight_keys:
    last_weight = weight_keys[-1]
    output_dim = state_dict[last_weight].shape[0]
    print(f'\nFinal layer: {last_weight} -> output_dim={output_dim}')
    if output_dim == 3:
        print('PASS: 3-class output (BUY/HOLD/SELL)')
    else:
        print(f'FAIL: Expected 3 output neurons, got {output_dim}')
"
```

**Expected:**
- State dict contains LSTM parameters (`weight_ih_l0`, `weight_hh_l0`, etc.)
- This proves the model is genuinely LSTM, not an MLP that was mis-labeled
- Output dimension is 3 (BUY/HOLD/SELL from triple barrier labels)
- Hidden dimension matches config (64)

### 9. Verify Training Metrics Are Valid

**Command:**
```bash
MODEL_BASE="$HOME/.ktrdr/shared/models/trend_tb_lstm_signal_v1"
MODEL_DIR=$(ls -td "$MODEL_BASE"/1h_v*/ 2>/dev/null | head -1)
if [ -z "$MODEL_DIR" ]; then MODEL_DIR="$MODEL_BASE/1h_latest"; fi

echo "=== metrics.json ==="
cat "$MODEL_DIR/metrics.json" | jq '.'

echo "=== Key metrics ==="
TRAIN_LOSS=$(cat "$MODEL_DIR/metrics.json" | jq -r '.final_train_loss // .train_loss // "null"')
VAL_LOSS=$(cat "$MODEL_DIR/metrics.json" | jq -r '.final_val_loss // .val_loss // "null"')
EPOCHS=$(cat "$MODEL_DIR/metrics.json" | jq -r '.epochs_completed // .epochs // "null"')

echo "train_loss: $TRAIN_LOSS"
echo "val_loss: $VAL_LOSS"
echo "epochs_completed: $EPOCHS"

# Non-degenerate checks
test "$TRAIN_LOSS" != "null" && echo "PASS: train_loss present" || echo "FAIL: train_loss missing"
test "$VAL_LOSS" != "null" && echo "PASS: val_loss present" || echo "FAIL: val_loss missing"
test "$EPOCHS" != "null" && echo "PASS: epochs present" || echo "FAIL: epochs missing"
```

**Expected:**
- `train_loss` and `val_loss` are present, numeric, > 0, and not NaN
- `epochs_completed` > 0 (early stopping at patience=20 should yield 20-80 epochs)
- Loss values should be in a reasonable range for focal loss on 3-class problem (0.01 to 3.0)

### 10. Verify Loss Decreased During Training (Not Stuck)

**Command:**
```bash
source .env.sandbox

# Check training logs for epoch-by-epoch loss progression
docker compose -f docker-compose.sandbox.yml logs --since 20m 2>/dev/null | \
  grep -iE "epoch.*loss|Epoch.*val" | head -5
echo "..."
docker compose -f docker-compose.sandbox.yml logs --since 20m 2>/dev/null | \
  grep -iE "epoch.*loss|Epoch.*val" | tail -5

echo ""
echo "=== Early stopping evidence ==="
docker compose -f docker-compose.sandbox.yml logs --since 20m 2>/dev/null | \
  grep -iE "early.stop|stopped.*epoch|no improvement" | tail -5
```

**Expected:**
- Loss values should generally decrease over epochs (not necessarily monotonic, but trending down)
- If early stopping triggered, a log line should indicate at which epoch
- Loss should NOT be NaN or stuck at exactly the same value for multiple epochs (indicates gradient issues)

---

## Success Criteria

- [ ] Training completes with status `"completed"` (CLI exit 0 or API status)
- [ ] Model directory created at `~/.ktrdr/shared/models/trend_tb_lstm_signal_v1/`
- [ ] `model.pt` exists and > 1KB (realistically > 50KB for a 2-layer LSTM)
- [ ] `metadata_v3.json` exists with `output_type: "classification"`
- [ ] `config.json` exists with `model.type: "lstm"` and `architecture.sequence_length: 20`
- [ ] Model state dict contains LSTM parameters (`weight_ih`, `weight_hh`)
- [ ] Model has 3-class output (BUY/HOLD/SELL from triple barrier)
- [ ] Training metrics present: `train_loss` and `val_loss` are numeric and > 0
- [ ] Loss is not NaN and not stuck (some evidence of learning)
- [ ] `resolved_features` in metadata is a non-empty list

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Training status is "completed", not "failed"** -- A failed training may still leave partial artifacts (config.json written before training starts). Always check status FIRST, then inspect files.
- [ ] **State dict contains LSTM layers, not just linear layers** -- If model dispatch fell back to MLP, training would succeed and produce valid files, but the model would be an MLP. The torch inspection step (Step 8) catches this: look for `weight_ih_l0`/`weight_hh_l0` keys that only LSTM produces.
- [ ] **model.pt > 50KB** -- An LSTM with hidden_size=64, 2 layers, and ~32 input features should produce a model file of at least 50KB. An MLP fallback would be much smaller (~5-10KB). If model.pt is between 1KB and 50KB, it might be an MLP mis-labeled as LSTM.
- [ ] **sequence_length in config.json is 20, not null/absent** -- If the pipeline ignored the LSTM config and used MLP defaults, sequence_length would be absent from the saved config. Its presence confirms the LSTM code path was taken.
- [ ] **epochs_completed < 200** -- With early_stopping patience=20 on 6 months of data, training should stop well before 200 epochs. If it ran all 200 epochs, early stopping may not be working with the SequenceDataset, or the model is not learning (flat loss).
- [ ] **epochs_completed > 5** -- Under 5 epochs suggests training was interrupted or data was insufficient. SequenceDataset reduces effective sample count by sequence_length, so very short data ranges could produce too few sequences.
- [ ] **val_loss is not exactly equal to train_loss** -- If they are identical, the train/val split may not be working correctly with SequenceDataset (e.g., sequence overlap between train and val sets causing data leakage).
- [ ] **No shape mismatch errors in logs** -- The most common LSTM integration failure is tensor shape mismatches: ModelTrainer passing (batch, features) instead of (batch, seq_len, features). Grep logs for "RuntimeError" or "shape" to confirm no silent failures.

**Sanity check command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

MODEL_BASE="$HOME/.ktrdr/shared/models/trend_tb_lstm_signal_v1"
MODEL_DIR=$(ls -td "$MODEL_BASE"/1h_v*/ 2>/dev/null | head -1)
if [ -z "$MODEL_DIR" ]; then MODEL_DIR="$MODEL_BASE/1h_latest"; fi

echo "=== Status Sanity ==="
if [ -n "$TASK_ID" ]; then
  curl -s "http://localhost:$API_PORT/api/v1/operations/$TASK_ID" | jq '{
    status: .data.status,
    training_time: .data.result_summary.training_metrics.training_time
  }'
fi

echo "=== File Sanity ==="
test -f "$MODEL_DIR/metadata_v3.json" && echo "PASS: metadata_v3.json exists" || echo "FAIL: metadata_v3.json missing"
test -f "$MODEL_DIR/model.pt" && echo "PASS: model.pt exists" || echo "FAIL: model.pt missing"
test -f "$MODEL_DIR/config.json" && echo "PASS: config.json exists" || echo "FAIL: config.json missing"

MODEL_SIZE=$(stat -f%z "$MODEL_DIR/model.pt" 2>/dev/null || stat -c%s "$MODEL_DIR/model.pt" 2>/dev/null)
echo "model.pt size: $MODEL_SIZE bytes"
test "$MODEL_SIZE" -gt 51200 && echo "PASS: model.pt > 50KB (likely real LSTM)" || echo "WARNING: model.pt only $MODEL_SIZE bytes (may be MLP fallback)"

echo "=== Architecture Sanity ==="
uv run python -c "
import torch
sd = torch.load('$MODEL_DIR/model.pt', map_location='cpu', weights_only=True)
ih_keys = [k for k in sd if 'weight_ih' in k]
hh_keys = [k for k in sd if 'weight_hh' in k]
if ih_keys:
    print(f'PASS: LSTM confirmed ({len(ih_keys)} weight_ih layers)')
else:
    linear_keys = [k for k in sd if 'weight' in k]
    print(f'FAIL: No LSTM layers. Found: {linear_keys}')

# Output dim
weight_keys = [k for k in sd if 'weight' in k and 'bias' not in k.replace(\"weight\",\"\")]
last = weight_keys[-1]
print(f'output_dim={sd[last].shape[0]}')
assert sd[last].shape[0] == 3, f'Expected 3 outputs, got {sd[last].shape[0]}'
print('PASS: 3-class output')
"

echo "=== Config Sanity ==="
MODEL_TYPE=$(cat "$MODEL_DIR/config.json" | jq -r '.model.type')
SEQ_LEN=$(cat "$MODEL_DIR/config.json" | jq -r '.model.architecture.sequence_length')
echo "model.type: $MODEL_TYPE (expect: lstm)"
echo "sequence_length: $SEQ_LEN (expect: 20)"

echo "=== Log Sanity ==="
docker compose -f docker-compose.sandbox.yml logs --since 20m 2>/dev/null | \
  grep -iE "RuntimeError|shape.*mismatch|size mismatch" | tail -5 || echo "PASS: no shape errors in logs"
```

---

## Troubleshooting

**If training fails with "Unknown model type: lstm":**
- **Cause:** `create_model()` in the training pipeline does not have an `elif model_type == "lstm"` branch
- **Category:** CODE_BUG (M1 Task 1.4 not implemented)
- **Cure:** Check the model factory/create_model function for LSTM dispatch. Must import and instantiate LSTMTradingModel.

**If training fails with shape mismatch (RuntimeError: size mismatch):**
- **Cause:** ModelTrainer is not using SequenceDataset for LSTM. It is passing (batch, features) tensors when LSTM expects (batch, seq_len, features).
- **Category:** CODE_BUG (M1 Task 1.3 not integrated)
- **Cure:** Check ModelTrainer.train() for the model_type detection that switches between TensorDataset (MLP) and SequenceDataset (LSTM/GRU).

**If training completes but model.pt contains only linear layers (no LSTM):**
- **Cause:** Model dispatch fell back to MLP despite config saying lstm. The create_model() function may not be reading model.type correctly.
- **Category:** CODE_BUG
- **Cure:** Inspect create_model() to verify it reads `config["model"]["type"]` and dispatches to LSTMTradingModel.

**If training fails with "Insufficient data for sequence_length":**
- **Cause:** After triple barrier labeling + train/val/test split, the effective sample count per split is less than sequence_length (20).
- **Category:** TEST_ISSUE
- **Cure:** 6 months of 1h data should yield ~3,000 bars, producing ~2,980 sequences. If the data range is somehow shorter, extend it. Also check that SequenceDataset.\_\_len\_\_ = T - sequence_length + 1 is computed correctly.

**If val_loss equals train_loss exactly:**
- **Cause:** SequenceDataset may have overlapping sequences between train and val splits. The purge window between splits must be at least sequence_length bars to prevent data leakage.
- **Category:** CODE_BUG (M1 Task 1.3 purged split)
- **Cure:** Check ModelTrainer's train/val split logic. For LSTM, the split point must leave a gap of at least sequence_length bars between the last training sequence and the first validation sequence.

**If early stopping never triggers (200 epochs completed):**
- **Cause:** Early stopping may not be compatible with SequenceDataset, or the model is not learning (flat loss).
- **Category:** CODE_BUG or CONFIG_ISSUE
- **Cure:** Check that early stopping monitors val_loss correctly with sequence data. If loss is flat, check learning rate and gradient clipping settings.

**If training times out (> 15 minutes):**
- **Cause:** LSTM is slower than MLP per epoch due to sequential processing. With 200 max epochs and ~2,800 sequences, this could be slow on CPU workers.
- **Category:** ENVIRONMENT
- **Cure:** Check workers: `curl http://localhost:$API_PORT/api/v1/workers | jq`. Early stopping (patience=20) should terminate well before 200 epochs. If not, the model may not be learning.

**If multi-TF data loading fails:**
- **Cause:** Known issue from M8 testing -- multi-TF data loading has bugs that only surface with real data in sandbox, not mocks.
- **Category:** CODE_BUG
- **Cure:** Check backend logs for data loading errors: `docker compose -f docker-compose.sandbox.yml logs backend --since 5m | grep -i "error\|fail"`. May need to verify 5m data availability separately.

---

## Evidence to Capture

- Training Operation ID: `$TASK_ID`
- Final status: `curl ... | jq '.data.status'`
- Training result summary: `curl ... | jq '.data.result_summary'`
- Model directory path: `$MODEL_DIR`
- Model directory listing: `ls -la $MODEL_DIR/`
- config.json model section: `cat $MODEL_DIR/config.json | jq '.model'`
- metadata_v3.json summary: `cat $MODEL_DIR/metadata_v3.json | jq '{model_name, output_type, resolved_features: (.resolved_features | length), training_metrics}'`
- metrics.json full contents: `cat $MODEL_DIR/metrics.json | jq .`
- State dict key listing: Python torch.load inspection
- LSTM layer confirmation: weight_ih / weight_hh key presence
- Output dimension: final weight layer shape[0]
- Training loss progression: first and last epoch log lines
- Shape error check: `docker compose logs | grep -i "RuntimeError\|shape"`

---

## Notes

- **Port variable:** Read from `.env.sandbox` as `KTRDR_API_PORT`. The impl worktree at `/Users/karl/Documents/dev/ktrdr-impl-temporal-signal-models-M1` uses sandbox slot 1 (port 8001).
- **CLI flags:** The `models train` command uses `--start-date`/`--end-date` (not `--start`/`--end`). The newer `train` command uses `--start`/`--end`. Use whichever is available in the impl worktree.
- **Strategy is NOT created by test:** Unlike triple-barrier-labels and focal-loss tests, this strategy exists in the repo at `strategies/trend_tb_lstm_signal_v1.yaml`. It must be copied to `~/.ktrdr/shared/strategies/` but should not be modified.
- **metadata_v3.json may not contain model_type yet:** The current ModelMetadata dataclass does not have model_type or sequence_length fields. M1 Task 1.4 adds these. If they are absent from metadata_v3.json, check config.json instead (it is a raw dump of the strategy config and will always contain model.type).
- **config.json is the reliable source for LSTM config:** config.json is saved by model_storage.py as a raw JSON dump of the full strategy config dict. It will always contain `model.type: "lstm"` and `architecture.sequence_length: 20` regardless of whether ModelMetadata was updated.
- **LSTM model.pt is significantly larger than MLP:** An LSTM with hidden_size=64, num_layers=2 has ~100K parameters vs ~2K for a small MLP. model.pt should be 50KB+ for LSTM, vs 5-10KB for MLP. This size difference is a useful sanity check.
- **Early stopping changes expected epoch count:** Do not assert exact epoch count. Assert it is > 5 (training ran) and < 200 (early stopping worked). The actual count depends on data and random initialization.
- **Multi-TF complication:** This strategy uses 5m + 1h timeframes. The training pipeline must align both timeframes and compute indicators on each. If multi-TF data loading has issues (as discovered in M8), training may fail before reaching the model training step. Check logs for data-loading errors first.
- **Focal loss + triple barrier:** This strategy uses both focal loss and triple barrier labels. If the focal loss wiring bug (see training/focal-loss-classification.md) is not fixed, training will silently use cross-entropy. This does not invalidate the LSTM test but means focal loss is not being verified here.
- **Sequence overlap in splits:** The train/val/test split for LSTM must include a purge window of at least sequence_length bars between splits. Without this, sequences near the split boundary would contain data from both train and val sets, causing leakage. This is a subtle bug that manifests as val_loss tracking train_loss too closely.
