# Test: training/focal-loss-classification

**Purpose:** Validate that a classification model can be trained with `loss: "focal"` and `focal_gamma` config, producing a model that actually used focal loss (not silently falling back to cross-entropy).
**Duration:** ~3 minutes (2 months of 1h data, 50 epochs)
**Category:** Training (Focal Loss)

**Dependency:** None (self-contained: strategy created by test, model may already be trained)

---

## CRITICAL: Known Wiring Bug

**Before running this test, verify the orchestrator wiring is fixed.**

As of M2 completion, `local_orchestrator.py` (line 377-384) and `training-host-service/orchestrator.py` (line 913-922) only inject `loss` and related config into `training_config` when `output_format == "regression"`. For classification models, the `training_config` dict only gets `epochs`, `learning_rate`, and `batch_size` -- the `loss` and `focal_gamma` keys from the strategy YAML are silently dropped.

This means ModelTrainer's focal loss support (unit-tested and working) is unreachable through the production training path for classification models. The test below will expose this: training will "succeed" but silently use cross-entropy instead of focal loss.

**The fix:** In both orchestrators, extract `loss` and `focal_gamma` from the training section for ALL output formats, not just regression:

```python
# After building base training_config (epochs, lr, batch_size):
# Always pass loss config -- ModelTrainer handles both classification and regression
loss_type = training_section.get("loss")
if loss_type:
    training_config["loss"] = loss_type
focal_gamma = training_section.get("focal_gamma")
if focal_gamma is not None:
    training_config["focal_gamma"] = focal_gamma
```

Files to fix:
- `ktrdr/api/services/training/local_orchestrator.py` (~line 375)
- `training-host-service/orchestrator.py` (~line 911)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../../e2e-testing/preflight/common.md) -- Docker, sandbox, API health
- [training](../../../e2e-testing/preflight/training.md) -- Strategy, data, workers

**Test-specific checks:**
- [ ] Focal loss strategy file exists (created by setup step below)
- [ ] EURUSD 1h data is available (2 months: 2024-01-01 to 2024-03-01)
- [ ] At least one idle training worker
- [ ] Orchestrator wiring fix is applied (see CRITICAL section above)

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

### Strategy File: `focal_loss_classification_test_v1.yaml`

This strategy must be created in `~/.ktrdr/shared/strategies/` before running the test. It is a minimal classification strategy with focal loss enabled -- intentionally small (50 epochs, 2 months of data) to keep execution time under 3 minutes.

```yaml
name: focal_loss_classification_test
version: "3.0"
description: >
  Minimal classification strategy with focal loss for E2E validation.
  Uses zigzag labels (3-class: BUY/SELL/HOLD) with focal loss to handle
  class imbalance. This is a test fixture, not a production strategy.

training_data:
  symbols:
    mode: single
    symbol: EURUSD
  timeframes:
    mode: single
    timeframe: 1h
  history_required: 100
  start_date: "2024-01-01"
  end_date: "2024-03-01"

indicators:
  rsi_14:
    type: RSI
    period: 14

fuzzy_sets:
  rsi_level:
    indicator: rsi_14
    oversold: [0, 20, 40]
    neutral: [30, 50, 70]
    overbought: [60, 80, 100]

nn_inputs:
  - fuzzy_set: rsi_level
    timeframes: all

model:
  type: mlp
  architecture:
    hidden_layers: [16, 8]
    dropout: 0.1
    activation: relu

decisions:
  output_format: classification
  confidence_threshold: 0.5

training:
  labels:
    source: zigzag
    zigzag_threshold: 0.02
    label_lookahead: 10
  loss: focal
  focal_gamma: 2.0
  epochs: 50
  learning_rate: 0.001
  data_split:
    train: 0.7
    validation: 0.15
    test: 0.15
```

**Why this data:**
- Minimal strategy (1 indicator, 3 fuzzy memberships, tiny MLP) for fast execution
- 2 months of 1h EURUSD provides ~1,400 bars -- sufficient for 3-class zigzag labels
- `loss: focal` and `focal_gamma: 2.0` are the fields under test
- Classification output with zigzag labels is the simplest focal loss scenario

### Request Payload

```json
{
  "symbols": ["EURUSD"],
  "timeframes": ["1h"],
  "strategy_name": "focal_loss_classification_test",
  "start_date": "2024-01-01",
  "end_date": "2024-03-01"
}
```

---

## Execution Steps

### 0. Create Strategy File

**Command:**
```bash
# Write the strategy YAML to the shared strategies directory
cat > ~/.ktrdr/shared/strategies/focal_loss_classification_test_v1.yaml << 'EOF'
name: focal_loss_classification_test
version: "3.0"
description: >
  Minimal classification strategy with focal loss for E2E validation.

training_data:
  symbols:
    mode: single
    symbol: EURUSD
  timeframes:
    mode: single
    timeframe: 1h
  history_required: 100
  start_date: "2024-01-01"
  end_date: "2024-03-01"

indicators:
  rsi_14:
    type: RSI
    period: 14

fuzzy_sets:
  rsi_level:
    indicator: rsi_14
    oversold: [0, 20, 40]
    neutral: [30, 50, 70]
    overbought: [60, 80, 100]

nn_inputs:
  - fuzzy_set: rsi_level
    timeframes: all

model:
  type: mlp
  architecture:
    hidden_layers: [16, 8]
    dropout: 0.1
    activation: relu

decisions:
  output_format: classification
  confidence_threshold: 0.5

training:
  labels:
    source: zigzag
    zigzag_threshold: 0.02
    label_lookahead: 10
  loss: focal
  focal_gamma: 2.0
  epochs: 50
  learning_rate: 0.001
  data_split:
    train: 0.7
    validation: 0.15
    test: 0.15
EOF

echo "Strategy file created."
ls -la ~/.ktrdr/shared/strategies/focal_loss_classification_test_v1.yaml
```

**Expected:**
- File created successfully in shared strategies directory

### 1. Remove Previous Model (Clean Slate)

**Command:**
```bash
MODEL_DIR="$HOME/.ktrdr/shared/models/focal_loss_classification_test/1h_v1"
if [ -d "$MODEL_DIR" ]; then
  echo "Previous model found at $MODEL_DIR -- removing for clean test"
  rm -rf "$MODEL_DIR"
fi
echo "Clean slate confirmed."
```

**Expected:**
- Any previous model removed to force fresh training

### 2. Start Training via CLI

**Command:**
```bash
source .env.sandbox

uv run ktrdr train focal_loss_classification_test_v1 \
  --symbols EURUSD --timeframes 1h \
  --start 2024-01-01 --end 2024-03-01 --follow
```

**Expected:**
- Training starts without validation errors
- Progress output shows epochs advancing
- Completes within ~3 minutes
- Exit code 0

**Alternative (API path):**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

RESPONSE=$(curl -s -X POST "http://localhost:$API_PORT/api/v1/trainings/start" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["EURUSD"],
    "timeframes": ["1h"],
    "strategy_name": "focal_loss_classification_test",
    "start_date": "2024-01-01",
    "end_date": "2024-03-01"
  }')

echo "Response: $RESPONSE"
TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id')
echo "Task ID: $TASK_ID"
```

### 3. Wait for Training Completion (API path only)

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Poll every 10s for up to 5 minutes
for i in $(seq 1 30); do
  sleep 10
  STATUS=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$TASK_ID" | jq -r '.data.status')
  echo "Poll $i: status=$STATUS"
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
done

TRAIN_RESULT=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$TASK_ID")
echo "Final status: $(echo "$TRAIN_RESULT" | jq -r '.data.status')"
```

**Expected:**
- `status: "completed"` (not "failed" or still "running" after 5 minutes)

### 4. Verify Model Files Exist

**Command:**
```bash
MODEL_DIR="$HOME/.ktrdr/shared/models/focal_loss_classification_test/1h_v1"

echo "=== Model directory ==="
ls -la "$MODEL_DIR/"

echo "=== Required files ==="
test -f "$MODEL_DIR/model.pt" && echo "PASS: model.pt exists" || echo "FAIL: model.pt missing"
test -f "$MODEL_DIR/metadata_v3.json" && echo "PASS: metadata_v3.json exists" || echo "FAIL: metadata_v3.json missing"

MODEL_SIZE=$(stat -f%z "$MODEL_DIR/model.pt" 2>/dev/null || stat -c%s "$MODEL_DIR/model.pt" 2>/dev/null)
echo "model.pt size: $MODEL_SIZE bytes"
test "$MODEL_SIZE" -gt 1024 && echo "PASS: model.pt > 1KB" || echo "FAIL: model.pt suspiciously small ($MODEL_SIZE bytes)"
```

**Expected:**
- `model.pt` exists and is > 1KB
- `metadata_v3.json` exists

### 5. Verify metadata_v3.json Has Valid Classification Output Type

**Command:**
```bash
MODEL_DIR="$HOME/.ktrdr/shared/models/focal_loss_classification_test/1h_v1"

echo "=== metadata_v3.json ==="
cat "$MODEL_DIR/metadata_v3.json" | jq .

echo "=== output_type ==="
OUTPUT_TYPE=$(cat "$MODEL_DIR/metadata_v3.json" | jq -r '.output_type')
echo "output_type: $OUTPUT_TYPE"

if [ "$OUTPUT_TYPE" = "classification" ]; then
  echo "PASS: output_type is classification"
else
  echo "FAIL: output_type is '$OUTPUT_TYPE', expected 'classification'"
fi
```

**Expected:**
- `output_type` is `"classification"` (zigzag labels produce standard classification, not regime_classification)

### 6. Verify Training Metrics Exist and Are Non-Degenerate

**Command:**
```bash
MODEL_DIR="$HOME/.ktrdr/shared/models/focal_loss_classification_test/1h_v1"

echo "=== Training Metrics ==="
cat "$MODEL_DIR/metadata_v3.json" | jq '.training_metrics'

# Check that training actually ran (metrics are populated)
TRAIN_LOSS=$(cat "$MODEL_DIR/metadata_v3.json" | jq -r '.training_metrics.final_train_loss // .training_metrics.train_loss // "null"')
VAL_LOSS=$(cat "$MODEL_DIR/metadata_v3.json" | jq -r '.training_metrics.final_val_loss // .training_metrics.val_loss // "null"')
EPOCHS=$(cat "$MODEL_DIR/metadata_v3.json" | jq -r '.training_metrics.epochs_completed // "null"')

echo "train_loss: $TRAIN_LOSS"
echo "val_loss: $VAL_LOSS"
echo "epochs_completed: $EPOCHS"

# Validate non-null and non-zero
test "$TRAIN_LOSS" != "null" && echo "PASS: train_loss present" || echo "FAIL: train_loss missing"
test "$VAL_LOSS" != "null" && echo "PASS: val_loss present" || echo "FAIL: val_loss missing"
test "$EPOCHS" != "null" && echo "PASS: epochs_completed present" || echo "FAIL: epochs_completed missing"
```

**Expected:**
- `train_loss` and `val_loss` are present and numeric
- `epochs_completed` is present and > 0
- Loss values are > 0 (real training occurred)

### 7. Verify Focal Loss Was Actually Used (Log Evidence)

**Command:**
```bash
source .env.sandbox

# Check backend/worker logs for focal loss evidence
# ModelTrainer logs the loss type at debug level; grep for it
docker compose -f docker-compose.sandbox.yml logs --since 15m 2>/dev/null | \
  grep -iE "focal|FocalLoss|loss.*type|criterion" | tail -20

echo "---"
echo "If no focal loss log lines appear above, the orchestrator may not be"
echo "passing loss config through to ModelTrainer for classification models."
echo "This is the known wiring bug described in the CRITICAL section."
```

**Expected:**
- Log evidence that FocalLoss was instantiated (e.g., "Using focal loss with gamma=2.0")
- If no such evidence appears, the wiring bug is still present

### 8. Compare Against Cross-Entropy Baseline (Optional Validation)

This step validates that focal loss produces meaningfully different training dynamics from the default cross-entropy. It is optional but strongly recommended for first-time validation.

**Command:**
```bash
MODEL_DIR="$HOME/.ktrdr/shared/models/focal_loss_classification_test/1h_v1"

# Focal loss with gamma=2.0 down-weights easy examples, so:
# - Early epoch losses will typically be HIGHER than CE (hard examples weighted more)
# - Final loss magnitude may differ from CE
# We can't assert exact values but can check the loss is in a reasonable range

uv run python -c "
import json
with open('$MODEL_DIR/metadata_v3.json') as f:
    meta = json.load(f)

metrics = meta.get('training_metrics', {})
train_loss = metrics.get('final_train_loss', metrics.get('train_loss'))
val_loss = metrics.get('final_val_loss', metrics.get('val_loss'))

print(f'train_loss = {train_loss}')
print(f'val_loss = {val_loss}')

# Focal loss with gamma=2.0 on 3-class problem:
# - Theoretical max ~ -log(1/3) * (1-1/3)^2 ~ 0.49
# - Typical range: 0.01 to 1.0
# - Cross-entropy typical range: 0.3 to 1.1
# If loss is 0.0 or > 5.0, something is wrong
if train_loss is not None:
    if 0.0 < train_loss < 5.0:
        print('PASS: train_loss in reasonable range for focal loss')
    else:
        print(f'WARNING: train_loss={train_loss} outside expected range (0, 5)')
"
```

**Expected:**
- Loss values are in a reasonable range (0 < loss < 5)
- Not a hard pass/fail -- informational for first-time validation

---

## Success Criteria

- [ ] Training completes with status `"completed"` (CLI exit 0 or API status)
- [ ] `model.pt` exists and is > 1KB
- [ ] `metadata_v3.json` exists with `output_type: "classification"`
- [ ] Training metrics are present: `train_loss`, `val_loss`, `epochs_completed` all non-null
- [ ] `epochs_completed` > 0 (training actually ran)
- [ ] Loss values are > 0 and < 5.0 (not degenerate)

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Training time > 2 seconds** -- 50 epochs on ~1,400 bars should take several seconds even on fast hardware. Under 2s suggests training was skipped or short-circuited.
- [ ] **model.pt file size > 1KB** -- A valid MLP with [16, 8] hidden layers should produce a model.pt of at least a few KB. Under 1KB suggests a corrupted or empty save.
- [ ] **metadata_v3.json is valid JSON** -- `jq '.' metadata_v3.json` must succeed. An empty or corrupt file makes all jq checks silently produce "null".
- [ ] **Focal loss was not silently replaced by cross-entropy** -- This is the hardest check. Without log evidence or a metadata field recording the loss function used, a successful training completion does NOT prove focal loss was used. The model could have silently trained with cross-entropy (the default). See the CRITICAL section above about the known wiring bug.
- [ ] **epochs_completed matches config (50)** -- If epochs_completed is much less than 50 and early_stopping is not configured, something interrupted training.

**Sanity check command:**
```bash
MODEL_DIR="$HOME/.ktrdr/shared/models/focal_loss_classification_test/1h_v1"

echo "=== File Sanity ==="
test -f "$MODEL_DIR/metadata_v3.json" && echo "PASS: metadata_v3.json exists" || echo "FAIL: metadata_v3.json missing"
test -f "$MODEL_DIR/model.pt" && echo "PASS: model.pt exists" || echo "FAIL: model.pt missing"

MODEL_SIZE=$(stat -f%z "$MODEL_DIR/model.pt" 2>/dev/null || stat -c%s "$MODEL_DIR/model.pt" 2>/dev/null)
echo "model.pt size: $MODEL_SIZE bytes"
test "$MODEL_SIZE" -gt 1024 && echo "PASS: model.pt > 1KB" || echo "FAIL: model.pt suspiciously small"

echo "=== Metadata Sanity ==="
cat "$MODEL_DIR/metadata_v3.json" | jq '.' > /dev/null 2>&1 && echo "PASS: valid JSON" || echo "FAIL: invalid JSON"

OUTPUT_TYPE=$(cat "$MODEL_DIR/metadata_v3.json" | jq -r '.output_type')
echo "output_type: $OUTPUT_TYPE"
test "$OUTPUT_TYPE" = "classification" && echo "PASS" || echo "FAIL: expected classification"

EPOCHS=$(cat "$MODEL_DIR/metadata_v3.json" | jq -r '.training_metrics.epochs_completed // "null"')
echo "epochs_completed: $EPOCHS"
test "$EPOCHS" != "null" && test "$EPOCHS" -gt 0 && echo "PASS: training ran" || echo "FAIL: no epochs completed"
```

---

## Troubleshooting

**If training fails with "Strategy not found":**
- **Cause:** `focal_loss_classification_test_v1.yaml` not in `~/.ktrdr/shared/strategies/`
- **Category:** ENVIRONMENT
- **Cure:** Run Step 0 to create the strategy file

**If training completes but focal loss was not used (no log evidence):**
- **Cause:** Orchestrator wiring bug -- `loss` and `focal_gamma` only injected for regression, not classification
- **Category:** CODE_BUG
- **Cure:** See CRITICAL section above. Both `local_orchestrator.py` and `training-host-service/orchestrator.py` need to extract `loss` and `focal_gamma` for all output formats, not just regression.

**If training fails with "Unknown loss type: focal":**
- **Cause:** ModelTrainer's loss selection does not handle the "focal" value
- **Category:** CODE_BUG (unlikely -- unit tests cover this)
- **Cure:** Check `model_trainer.py` around line 302 for the `if loss_type == "focal"` branch

**If training fails with import error for FocalLoss:**
- **Cause:** `ktrdr/neural/losses.py` missing or not importable in container
- **Category:** ENVIRONMENT
- **Cure:** Verify the file exists and is included in the Docker image. Check `docker exec <container> python -c "from ktrdr.neural.losses import FocalLoss; print('OK')"`

**If epochs_completed < 50 unexpectedly:**
- **Cause:** Early stopping triggered (not configured in this strategy, so this should not happen)
- **Category:** CODE_BUG
- **Cure:** Check if early stopping defaults are being applied even when not configured. Look at ModelTrainer's early stopping setup.

**If training times out (>5 minutes):**
- **Cause:** Worker busy, data loading slow, or cold start
- **Category:** ENVIRONMENT
- **Cure:** Check workers: `curl http://localhost:$API_PORT/api/v1/workers | jq`. Check for running operations: `curl http://localhost:$API_PORT/api/v1/operations | jq '.[] | select(.status=="running")'`

---

## Evidence to Capture

- Training completion: CLI exit code or API operation status
- Model directory listing: `ls -la $MODEL_DIR/`
- metadata_v3.json full contents: `cat $MODEL_DIR/metadata_v3.json | jq .`
- output_type value: `jq -r '.output_type' $MODEL_DIR/metadata_v3.json`
- Training metrics: `jq '.training_metrics' $MODEL_DIR/metadata_v3.json`
- Backend logs for focal loss evidence: `docker compose logs | grep -i focal`

---

## Notes

- **Port variable:** Read from `.env.sandbox` as `KTRDR_API_PORT` (current sandbox: slot 5, port 8005).
- **CLI flags:** Use `--start`/`--end`, NOT `--start-date`/`--end-date`. The CLI changed flag names.
- **Loss config location:** The `loss` and `focal_gamma` fields belong in the `training` section of the strategy YAML, NOT in `decisions`. The `decisions` section controls `output_format` and `confidence_threshold`.
- **Wiring bug is the primary risk:** ModelTrainer supports focal loss (unit-tested). The gap is that the orchestrator does not pass `loss`/`focal_gamma` through to ModelTrainer for classification models. This E2E test exists specifically to catch that gap.
- **No metadata field records loss function used:** Currently, `metadata_v3.json` does not record which loss function was used during training. This makes it impossible to verify focal loss from metadata alone. Log evidence is the only way to confirm. Consider adding a `loss_function` field to metadata as a follow-up improvement.
- **Metadata file is metadata_v3.json:** Not `metadata.json` (v2 format). The v3 pipeline saves to `metadata_v3.json` specifically.
- **Model path:** `~/.ktrdr/shared/models/focal_loss_classification_test/1h_v1/` follows the `{strategy_name}/{timeframe}_v{version}` convention.
- **Cleanup:** After validation, optionally remove the test strategy and model:
  ```bash
  rm ~/.ktrdr/shared/strategies/focal_loss_classification_test_v1.yaml
  rm -rf ~/.ktrdr/shared/models/focal_loss_classification_test/
  ```
