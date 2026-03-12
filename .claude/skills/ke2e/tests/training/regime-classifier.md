# Test: training/regime-classifier

**Purpose:** Validate that the regime classifier training pipeline produces a 4-class model with `output_type: regime_classification` in metadata, correct output dimensions, and all 4 regime classes represented in training labels.
**Duration:** ~5 minutes (5-year 1h data, 100 epochs)
**Category:** Training (Regime Classification)

**Dependency:** None (self-contained: strategy already exists, model may already be trained)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../../e2e-testing/preflight/common.md) -- Docker, sandbox, API health
- [training](../../../e2e-testing/preflight/training.md) -- Strategy, data, workers

**Test-specific checks:**
- [ ] Strategy file exists: `ls ~/.ktrdr/shared/strategies/regime_classifier_seed_v1.yaml`
- [ ] EURUSD 1h data is available (5 years: 2019-2024)
- [ ] At least one idle training worker
- [ ] No stale model from a previous failed run blocking the path

**Pre-flight commands:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# 1. Strategy file accessible to containers
test -f ~/.ktrdr/shared/strategies/regime_classifier_seed_v1.yaml || {
  echo "FAIL: regime_classifier_seed_v1.yaml not in shared strategies dir"
  echo "Copy from repo: cp strategies/regime_classifier_seed_v1.yaml ~/.ktrdr/shared/strategies/"
  exit 1
}

# 2. API health
curl -sf "http://localhost:$API_PORT/api/v1/health" > /dev/null || {
  echo "FAIL: API not healthy on port $API_PORT"
  exit 1
}

# 3. Training workers available
WORKERS=$(curl -s "http://localhost:$API_PORT/api/v1/workers" | jq '[.workers[] | select(.type=="training")] | length')
echo "Training workers: $WORKERS"
test "$WORKERS" -ge 1 || {
  echo "FAIL: No training workers registered"
  exit 1
}
```

---

## Test Data

The strategy file `regime_classifier_seed_v1.yaml` is already in the repository at `strategies/` and should be copied to `~/.ktrdr/shared/strategies/` for container access.

**Key strategy properties:**
- `training.labels.source: regime` -- triggers regime labeling (not zigzag)
- `decisions.output_format: classification` -- classification head
- 4 regime classes: TRENDING_UP (0), TRENDING_DOWN (1), RANGING (2), VOLATILE (3)
- 5 indicators across 6 fuzzy sets = 17 fuzzy membership inputs
- MLP architecture: [64, 32] hidden layers
- Training range: 2019-01-01 to 2024-01-01 (~36,500 hourly bars)

### Request Payload

```json
{
  "symbols": ["EURUSD"],
  "timeframes": ["1h"],
  "strategy_name": "regime_classifier_seed",
  "start_date": "2019-01-01",
  "end_date": "2024-01-01"
}
```

**Why this data:**
- 5 years of 1h EURUSD provides ~36,500 bars -- sufficient for 4-class distribution
- EURUSD exhibits all 4 regimes across this period (COVID volatility, 2022 trend, ranging periods)
- The strategy uses volatility/trend indicators specifically chosen for regime detection

---

## Execution Steps

### 1. Remove Previous Model (Clean Slate)

**Command:**
```bash
# Optional: remove existing model to force fresh training
# Skip if you want to validate an already-trained model
MODEL_DIR="$HOME/.ktrdr/shared/models/regime_classifier_seed/1h_v1"
if [ -d "$MODEL_DIR" ]; then
  echo "Previous model found at $MODEL_DIR"
  echo "To retrain from scratch: rm -rf $MODEL_DIR"
  echo "To validate existing model: skip to Step 4"
fi
```

**Expected:**
- Informational only -- decide whether to retrain or validate existing

### 2. Start Training via CLI

**Command:**
```bash
source .env.sandbox

# Use CLI with --follow to stream progress
uv run ktrdr train regime_classifier_seed_v1 --start 2019-01-01 --end 2024-01-01 --follow
```

**Expected:**
- Training starts without validation errors
- Progress output shows epochs advancing
- Completes within ~5 minutes
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
    "strategy_name": "regime_classifier_seed",
    "start_date": "2019-01-01",
    "end_date": "2024-01-01"
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

# Poll every 15s for up to 10 minutes (5yr data may take longer)
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
```

**Expected:**
- `status: "completed"` (not "failed" or still "running" after 10 minutes)

### 4. Verify metadata_v3.json Contains output_type: regime_classification

**Command:**
```bash
MODEL_DIR="$HOME/.ktrdr/shared/models/regime_classifier_seed/1h_v1"

echo "=== Model directory ==="
ls -la "$MODEL_DIR/"

echo "=== metadata_v3.json ==="
cat "$MODEL_DIR/metadata_v3.json" | jq .

echo "=== output_type ==="
OUTPUT_TYPE=$(cat "$MODEL_DIR/metadata_v3.json" | jq -r '.output_type')
echo "output_type: $OUTPUT_TYPE"

if [ "$OUTPUT_TYPE" = "regime_classification" ]; then
  echo "PASS: output_type is regime_classification"
else
  echo "FAIL: output_type is '$OUTPUT_TYPE', expected 'regime_classification'"
fi
```

**Expected:**
- `metadata_v3.json` exists in model directory
- `output_type` field is exactly `"regime_classification"`
- Not `"classification"` (that would mean the regime-specific path was not triggered)

### 5. Verify Model Has 4-Class Output Architecture

**Command:**
```bash
MODEL_DIR="$HOME/.ktrdr/shared/models/regime_classifier_seed/1h_v1"

# Check model.pt output layer dimensions via Python
uv run python -c "
import torch
state_dict = torch.load('$MODEL_DIR/model.pt', map_location='cpu', weights_only=True)

# Find the final linear layer
final_layer_keys = [k for k in state_dict.keys() if 'weight' in k]
last_layer = final_layer_keys[-1]
output_shape = state_dict[last_layer].shape
print(f'Final layer: {last_layer}')
print(f'Output shape: {output_shape}')
print(f'Output dim (num classes): {output_shape[0]}')

if output_shape[0] == 4:
    print('PASS: Model has 4 output neurons (4 regime classes)')
else:
    print(f'FAIL: Model has {output_shape[0]} output neurons, expected 4')
"
```

**Expected:**
- Final linear layer has shape `[4, N]` where N is the last hidden layer size (32)
- Output dim is 4, corresponding to: TRENDING_UP, TRENDING_DOWN, RANGING, VOLATILE

### 6. Verify Training Metrics and Label Distribution

**Command:**
```bash
MODEL_DIR="$HOME/.ktrdr/shared/models/regime_classifier_seed/1h_v1"

# Check training metrics from metadata
echo "=== Training Metrics ==="
cat "$MODEL_DIR/metadata_v3.json" | jq '.training_metrics'

# Check operation result for label distribution (API path)
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# If TASK_ID is available from step 2/3:
if [ -n "$TASK_ID" ]; then
  echo "=== Operation Result Summary ==="
  curl -s "http://localhost:$API_PORT/api/v1/operations/$TASK_ID" | jq '{
    status: .data.status,
    test_accuracy: .data.result_summary.test_metrics.test_accuracy,
    val_accuracy: .data.result_summary.training_metrics.final_val_accuracy,
    training_time: .data.result_summary.training_metrics.training_time
  }'
fi
```

**Expected:**
- Training metrics are non-null
- `test_accuracy` or `val_accuracy` present and > 0 (not NaN)
- `training_time` > 1.0 (real training occurred with 100 epochs)

### 7. Verify All 4 Classes in Backend Logs

**Command:**
```bash
source .env.sandbox

# Check backend/worker logs for label distribution
docker compose -f docker-compose.sandbox.yml logs backend --since 15m 2>/dev/null | \
  grep -iE "label.*distribution|TRENDING_UP|TRENDING_DOWN|RANGING|VOLATILE|regime|output_dim|num_classes" | tail -20
```

**Expected:**
- Log lines showing label distribution with all 4 classes present
- At least some samples in each class (though RANGING will dominate)
- Evidence that `output_dim=4` or `num_classes=4` was used

### 8. Verify Resolved Features Count

**Command:**
```bash
MODEL_DIR="$HOME/.ktrdr/shared/models/regime_classifier_seed/1h_v1"

echo "=== Resolved Features ==="
cat "$MODEL_DIR/metadata_v3.json" | jq '.resolved_features'

FEATURE_COUNT=$(cat "$MODEL_DIR/metadata_v3.json" | jq '.resolved_features | length')
echo "Feature count: $FEATURE_COUNT"

if [ "$FEATURE_COUNT" -ge 15 ]; then
  echo "PASS: Feature count ($FEATURE_COUNT) is >= 15 (6 fuzzy sets with 2-3 memberships each)"
else
  echo "FAIL: Feature count ($FEATURE_COUNT) too low, expected >= 15"
fi
```

**Expected:**
- Feature count >= 15 (6 fuzzy sets: atr_short(3) + atr_long(3) + bbwidth_level(3) + adx_strength(3) + trend_direction(2) + squeeze_level(3) = 17 total)
- Features include names from all 6 fuzzy sets

---

## Success Criteria

- [ ] Training completes with status `"completed"` (CLI exit 0 or API status)
- [ ] `metadata_v3.json` exists in model directory
- [ ] `output_type` is exactly `"regime_classification"` (not `"classification"`)
- [ ] Model final layer has 4 output neurons (not 3)
- [ ] Resolved features count >= 15 (all 6 fuzzy sets contributed)
- [ ] Training metrics are present and non-degenerate

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **output_type is "regime_classification", NOT "classification"** -- If "classification", the label source mapping in `_save_v3_metadata` did not trigger the regime path. This would mean the model trained on zigzag labels instead of regime labels, producing a fundamentally different model.
- [ ] **Output dim is 4, NOT 3** -- The MLP model previously hardcoded 3 output neurons for classification. If `num_classes` was not injected into model_config, the model has 3 outputs and cannot represent 4 regime classes. This was a real bug found during M4 (see HANDOFF_M4.md Task 4.4).
- [ ] **Training time > 5 seconds** -- 100 epochs on ~36,500 bars with 17 features should take at least several seconds. Under 5s suggests training was skipped, cached, or failed silently.
- [ ] **val_accuracy < 0.98** -- Near-perfect accuracy on 4-class regime detection is suspicious. The known class imbalance (RANGING ~91%) means a degenerate always-RANGING model gets ~91% accuracy. If val_accuracy > 98%, the model likely collapsed to predicting a single class.
- [ ] **model.pt file size > 1KB** -- A valid MLP with [64, 32] hidden layers and 17 inputs should produce a model.pt of several KB. Under 1KB suggests a corrupted or empty save.
- [ ] **metadata_v3.json is not empty** -- `jq '.' metadata_v3.json` must return valid JSON. An empty file would make all jq checks silently fail.

**Sanity check command:**
```bash
MODEL_DIR="$HOME/.ktrdr/shared/models/regime_classifier_seed/1h_v1"

echo "=== File Sanity ==="
test -f "$MODEL_DIR/metadata_v3.json" && echo "PASS: metadata_v3.json exists" || echo "FAIL: metadata_v3.json missing"
test -f "$MODEL_DIR/model.pt" && echo "PASS: model.pt exists" || echo "FAIL: model.pt missing"

MODEL_SIZE=$(stat -f%z "$MODEL_DIR/model.pt" 2>/dev/null || stat -c%s "$MODEL_DIR/model.pt" 2>/dev/null)
echo "model.pt size: $MODEL_SIZE bytes"
test "$MODEL_SIZE" -gt 1024 && echo "PASS: model.pt > 1KB" || echo "FAIL: model.pt suspiciously small"

echo "=== Metadata Sanity ==="
OUTPUT_TYPE=$(cat "$MODEL_DIR/metadata_v3.json" | jq -r '.output_type')
echo "output_type: $OUTPUT_TYPE"
test "$OUTPUT_TYPE" = "regime_classification" && echo "PASS" || echo "FAIL: expected regime_classification"

echo "=== Architecture Sanity ==="
uv run python -c "
import torch
sd = torch.load('$MODEL_DIR/model.pt', map_location='cpu', weights_only=True)
final = [k for k in sd if 'weight' in k][-1]
out_dim = sd[final].shape[0]
print(f'output_dim={out_dim}')
assert out_dim == 4, f'FAIL: output_dim={out_dim}, expected 4'
print('PASS: 4-class output confirmed')
"
```

---

## Troubleshooting

**If training fails with "Strategy not found":**
- **Cause:** `regime_classifier_seed_v1.yaml` not in `~/.ktrdr/shared/strategies/`
- **Category:** ENVIRONMENT
- **Cure:** `cp strategies/regime_classifier_seed_v1.yaml ~/.ktrdr/shared/strategies/`

**If output_type is "classification" instead of "regime_classification":**
- **Cause:** `_save_v3_metadata` in `local_orchestrator.py` or `training-host-service/orchestrator.py` does not map `labels.source: regime` to `output_type: regime_classification`
- **Category:** CODE_BUG
- **Cure:** Check the label source extraction in `_save_v3_metadata`. Must be: `config.get("training", {}).get("labels", {}).get("source", "zigzag")` and mapped through: `{"zigzag": "classification", "forward_return": "regression", "regime": "regime_classification"}`

**If model has 3 output neurons instead of 4:**
- **Cause:** `num_classes` not injected into model_config before `build_model()` is called
- **Category:** CODE_BUG
- **Cure:** Check `TrainingPipeline.create_model()` sets `model_config["num_classes"] = output_dim`. Check `local_orchestrator.py` passes `output_dim=4` for regime strategies. The MLP defaults to `num_classes=3` if not specified.

**If training fails with "Unknown label source: regime":**
- **Cause:** Label source routing in `training_pipeline.py` does not handle `source: regime`
- **Category:** CODE_BUG
- **Cure:** Verify the training pipeline has a branch for `source == "regime"` that calls `RegimeLabeler.generate_labels()`. Check triple dispatch: `training_pipeline.py`, `local_orchestrator.py`, and `training-host-service/orchestrator.py`.

**If label distribution shows only 1-2 classes:**
- **Cause:** Threshold parameters in strategy YAML produce degenerate labeling
- **Category:** TEST_ISSUE
- **Cure:** Adjust `trending_threshold` and `vol_crisis_threshold` in the strategy. With horizon=24, trending=0.5, vol_crisis=2.0, EURUSD 1h 2019-2024 should produce all 4 classes (though RANGING will dominate at ~91%).

**If training times out (>10 minutes):**
- **Cause:** Worker busy, data loading slow, or cold start on 5-year dataset
- **Category:** ENVIRONMENT
- **Cure:** Check workers: `curl http://localhost:$API_PORT/api/v1/workers | jq`. Check if another training operation is running: `curl http://localhost:$API_PORT/api/v1/operations | jq '.[] | select(.status=="running")'`

**If sandbox agent port conflicts appear in logs:**
- **Cause:** Ports 5010/5020 conflict with prod agent services
- **Category:** ENVIRONMENT (non-blocking)
- **Cure:** These warnings do not block training. Agent services (design/assessment workers) are not needed for this test. Ignore unless training actually fails.

---

## Evidence to Capture

- Training completion: CLI exit code or API operation status
- Model directory listing: `ls -la $MODEL_DIR/`
- metadata_v3.json full contents: `cat $MODEL_DIR/metadata_v3.json | jq .`
- output_type value: `jq -r '.output_type' $MODEL_DIR/metadata_v3.json`
- Model output dimensions: Python torch.load inspection of final layer shape
- Resolved features list: `jq '.resolved_features' $MODEL_DIR/metadata_v3.json`
- Training metrics: `jq '.training_metrics' $MODEL_DIR/metadata_v3.json`
- Backend logs (label distribution): `docker compose logs | grep regime`

---

## Notes

- **Port variable:** Read from `.env.sandbox` as `KTRDR_API_PORT` (slot 1 = port 8001).
- **CLI flags:** Use `--start`/`--end`, NOT `--start-date`/`--end-date`. The CLI changed flag names.
- **Triple dispatch:** Regime label source handling exists in three places: `training_pipeline.py`, `local_orchestrator.py`, and `training-host-service/orchestrator.py`. If the test fails on output_type, check all three.
- **Class imbalance is expected:** RANGING dominates at ~91% of labels. This is a property of the forex market, not a bug. The test validates 4 classes exist, not that they are balanced.
- **num_classes bug was real:** The MLP model previously hardcoded 3 output neurons for all classification tasks. M4 Task 4.4 fixed this by adding `num_classes` config injection. This test catches regressions.
- **Model path:** `~/.ktrdr/shared/models/regime_classifier_seed/1h_v1/` -- the `1h_v1` subdirectory follows the `{timeframe}_v{version}` naming convention.
- **Metadata file is metadata_v3.json:** Not `metadata.json` (v2 format). The v3 pipeline saves to `metadata_v3.json` specifically.
