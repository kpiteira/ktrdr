# Test: training/context-classifier

**Purpose:** Validate that context classifier training produces a 3-class model with correct metadata (output_type=context_classification) and softmax outputs
**Duration:** ~2 minutes (daily timeframe = fewer bars, faster training)
**Category:** Training

**Dependency:** None (self-contained)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) -- Docker, sandbox, API health
- [training](../../preflight/training.md) -- Strategy, data, workers

**Test-specific checks:**
- [ ] Strategy file exists: `~/.ktrdr/shared/strategies/context_classifier_seed_v1.yaml`
- [ ] EURUSD 1d data available in cache
- [ ] Sandbox port is 8002 (source `.env.sandbox` and verify `KTRDR_API_PORT=8002`)
- [ ] At least one idle training worker

**Strategy copy (if missing):**
```bash
cp strategies/context_classifier_seed_v1.yaml ~/.ktrdr/shared/strategies/context_classifier_seed_v1.yaml
```

---

## Test Data

```json
{
  "symbols": ["EURUSD"],
  "timeframes": ["1d"],
  "strategy_name": "context_classifier_seed_v1",
  "start_date": "2024-01-01",
  "end_date": "2025-03-01"
}
```

**Why this data:**
- EURUSD 1d over 14 months: ~300 daily bars, trains quickly (~30s)
- `context_classifier_seed_v1` is the canonical 3-class context strategy (BULLISH/BEARISH/NEUTRAL)
- Daily timeframe matches the strategy's `training_data.timeframes.timeframe: "1d"`
- Labels use `source: context` with `horizon: 5` and +/-0.5% thresholds for regime classification

---

## Execution Steps

### 1. Environment Setup

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-predictive-features-M5
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8002}
echo "Using API_PORT=$API_PORT"
```

**Expected:**
- API_PORT is 8002

### 2. Copy Strategy to Shared Directory

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-predictive-features-M5
cp strategies/context_classifier_seed_v1.yaml ~/.ktrdr/shared/strategies/context_classifier_seed_v1.yaml
echo "Strategy copied"
ls -la ~/.ktrdr/shared/strategies/context_classifier_seed_v1.yaml
```

**Expected:**
- File exists at shared strategies location

### 3. Start Context Classifier Training via API

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-predictive-features-M5
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8002}

RESPONSE=$(curl -s -X POST http://localhost:$API_PORT/api/v1/trainings/start \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["EURUSD"],
    "timeframes": ["1d"],
    "strategy_name": "context_classifier_seed_v1",
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
cd /Users/karl/Documents/dev/ktrdr-impl-predictive-features-M5
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8002}

# Poll every 10s for up to 3 minutes
for i in $(seq 1 18); do
  sleep 10
  STATUS=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$TASK_ID" | jq -r '.data.status')
  echo "Poll $i: status=$STATUS"
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
done

TRAIN_RESULT=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$TASK_ID")
echo "Training Result:"
echo "$TRAIN_RESULT" | jq '{status:.data.status, samples:.data.result_summary.data_summary.total_samples}'
```

**Expected:**
- `status: "completed"` (not "failed" or "running")
- `samples` > 200 (14 months of daily data ~ 300 bars)
- Total wait < 3 minutes

### 5. Verify metadata_v3.json Contains output_type=context_classification

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-predictive-features-M5

# Find the model directory
MODEL_DIR=$(ls -td ~/.ktrdr/shared/models/context_classifier_seed_v1/1d_v*/ 2>/dev/null | head -1)

# Fallback to latest symlink
if [ -z "$MODEL_DIR" ]; then
  MODEL_DIR="$HOME/.ktrdr/shared/models/context_classifier_seed_v1/1d_latest"
fi

echo "Model directory: $MODEL_DIR"
ls -la "$MODEL_DIR/"

echo "--- metadata_v3.json ---"
cat "$MODEL_DIR/metadata_v3.json" | jq .

# Extract the critical field
OUTPUT_TYPE=$(cat "$MODEL_DIR/metadata_v3.json" | jq -r '.output_type // "NOT_FOUND"')
echo "output_type: $OUTPUT_TYPE"
```

**Expected:**
- `metadata_v3.json` exists in model directory
- `output_type` is `"context_classification"` (not `"classification"` or `"NOT_FOUND"`)

### 6. Verify Model Config Contains Context-Specific Settings

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-predictive-features-M5

MODEL_DIR=$(ls -td ~/.ktrdr/shared/models/context_classifier_seed_v1/1d_v*/ 2>/dev/null | head -1)
if [ -z "$MODEL_DIR" ]; then
  MODEL_DIR="$HOME/.ktrdr/shared/models/context_classifier_seed_v1/1d_latest"
fi

echo "--- config.json ---"
cat "$MODEL_DIR/config.json" | jq .

# Extract key fields
LABELS_SOURCE=$(cat "$MODEL_DIR/config.json" | jq -r '.training.labels.source // .labels.source // "NOT_FOUND"')
echo "labels_source: $LABELS_SOURCE"

LOSS=$(cat "$MODEL_DIR/config.json" | jq -r '.training.loss // .loss // "NOT_FOUND"')
echo "loss: $LOSS"

OUTPUT_FORMAT=$(cat "$MODEL_DIR/config.json" | jq -r '.decisions.output_format // .output_format // "NOT_FOUND"')
echo "output_format: $OUTPUT_FORMAT"

OUTPUT_ACTIVATION=$(cat "$MODEL_DIR/config.json" | jq -r '.model.architecture.output_activation // "NOT_FOUND"')
echo "output_activation: $OUTPUT_ACTIVATION"
```

**Expected:**
- `labels_source` is `"context"` (not `"zigzag"` or `"forward_return"`)
- `loss` is `"cross_entropy"` (3-class classification loss)
- `output_format` is `"classification"`
- `output_activation` is `"softmax"` (produces probabilities summing to 1)

### 7. Verify Model Architecture Has 3-Class Output

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-predictive-features-M5

MODEL_DIR=$(ls -td ~/.ktrdr/shared/models/context_classifier_seed_v1/1d_v*/ 2>/dev/null | head -1)
if [ -z "$MODEL_DIR" ]; then
  MODEL_DIR="$HOME/.ktrdr/shared/models/context_classifier_seed_v1/1d_latest"
fi

# Check config.json for num_classes or output dimensions
NUM_CLASSES=$(cat "$MODEL_DIR/config.json" | jq -r '.model.num_classes // .num_classes // "NOT_FOUND"')
echo "num_classes from config: $NUM_CLASSES"

# Check metadata_v3.json for any output dimension info
echo "--- metadata_v3.json training_metrics ---"
cat "$MODEL_DIR/metadata_v3.json" | jq '.training_metrics // {}'

# Verify the model.pt file exists (actual trained weights)
if [ -f "$MODEL_DIR/model.pt" ]; then
  MODEL_SIZE=$(ls -la "$MODEL_DIR/model.pt" | awk '{print $5}')
  echo "model.pt size: $MODEL_SIZE bytes"
else
  echo "ERROR: model.pt not found"
fi

# Check features.json for input feature count
if [ -f "$MODEL_DIR/features.json" ]; then
  FEATURE_COUNT=$(cat "$MODEL_DIR/features.json" | jq 'length')
  echo "Input features: $FEATURE_COUNT"
else
  echo "features.json not found (checking resolved_features in metadata)"
  FEATURE_COUNT=$(cat "$MODEL_DIR/metadata_v3.json" | jq '.resolved_features | length')
  echo "Resolved features: $FEATURE_COUNT"
fi
```

**Expected:**
- `model.pt` exists with size > 1000 bytes (real trained weights, not empty)
- Feature count should be 11 (4 fuzzy sets x 2-3 memberships each: short_momentum has 3, long_momentum has 3, trend_strength has 3, daily_rsi has 3 = 12 memberships, though exact count depends on resolution)
- Training metrics present and non-empty

### 8. Verify Training Metrics are Classification-Appropriate

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-predictive-features-M5
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8002}

curl -s "http://localhost:$API_PORT/api/v1/operations/$TASK_ID" | \
  jq '{
    test_accuracy: .data.result_summary.test_metrics.test_accuracy,
    val_accuracy: .data.result_summary.training_metrics.final_val_accuracy,
    val_loss: .data.result_summary.training_metrics.final_val_loss,
    training_time: .data.result_summary.training_metrics.training_time
  }'
```

**Expected:**
- `test_accuracy` between 0.30 and 0.95 (3-class: random baseline is ~33%, near-perfect is suspicious)
- `val_accuracy` between 0.30 and 0.95
- `val_loss` > 0.1 (cross-entropy loss for 3 classes; near-zero = collapsed)
- `training_time` > 0.5 (real training, not cached)

---

## Success Criteria

- [ ] Training starts successfully (HTTP 200, task_id returned)
- [ ] Training completes (status = "completed") within 3 minutes
- [ ] `metadata_v3.json` exists in model directory
- [ ] `metadata_v3.json` contains `output_type: "context_classification"`
- [ ] `config.json` contains `labels.source: "context"`
- [ ] `config.json` contains `loss: "cross_entropy"`
- [ ] `config.json` contains `output_activation: "softmax"`
- [ ] `model.pt` exists with size > 1000 bytes
- [ ] Test accuracy between 0.30 and 0.95
- [ ] No errors in backend logs related to context training

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Training status is "completed", not "failed"** -- A failed training that produces partial output could look like success
- [ ] **output_type is literally "context_classification", not "classification"** -- If the label source detection failed, the strategy fell back to generic classification and the context-specific metadata is wrong
- [ ] **labels_source is "context", not "zigzag"** -- If the strategy loader dropped the labels config, it defaults to zigzag (2-class), which would train but produce wrong output
- [ ] **Test accuracy < 95%** -- Near-perfect accuracy on 3-class daily data = data leakage or model collapse to majority class
- [ ] **Test accuracy > 30%** -- Below random baseline (33%) indicates degenerate model that predicts single class
- [ ] **Val loss > 0.1** -- Cross-entropy for 3 classes should be at least ~1.0 for random; near-zero = trivial solution
- [ ] **Training time > 0.5s** -- If < 0.5s, training may have been skipped or used cached results
- [ ] **model.pt > 1000 bytes** -- Tiny model file indicates failed serialization
- [ ] **Sample count > 200** -- 14 months of daily data should yield ~300 bars; significantly fewer means data loading failed partially

**Sanity check command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-predictive-features-M5
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8002}

echo "=== Training Sanity ==="
curl -s "http://localhost:$API_PORT/api/v1/operations/$TASK_ID" | jq '{
  status: .data.status,
  test_accuracy: .data.result_summary.test_metrics.test_accuracy,
  val_accuracy: .data.result_summary.training_metrics.final_val_accuracy,
  val_loss: .data.result_summary.training_metrics.final_val_loss,
  training_time: .data.result_summary.training_metrics.training_time,
  samples: .data.result_summary.data_summary.total_samples
}'

echo "=== Metadata Sanity ==="
MODEL_DIR=$(ls -td ~/.ktrdr/shared/models/context_classifier_seed_v1/1d_v*/ 2>/dev/null | head -1)
if [ -z "$MODEL_DIR" ]; then
  MODEL_DIR="$HOME/.ktrdr/shared/models/context_classifier_seed_v1/1d_latest"
fi

cat "$MODEL_DIR/metadata_v3.json" 2>/dev/null | jq '{
  output_type: .output_type,
  strategy_name: .strategy_name,
  resolved_features_count: (.resolved_features | length)
}'

echo "=== Config Sanity ==="
cat "$MODEL_DIR/config.json" 2>/dev/null | jq '{
  labels_source: (.training.labels.source // .labels.source),
  loss: (.training.loss // .loss),
  output_format: (.decisions.output_format // .output_format),
  output_activation: (.model.architecture.output_activation)
}'

echo "=== Model File ==="
ls -la "$MODEL_DIR/model.pt" 2>/dev/null || echo "model.pt MISSING"
```

---

## Troubleshooting

**If training fails with "strategy not found":**
- **Cause:** Strategy file not copied to shared directory
- **Cure:** `cp strategies/context_classifier_seed_v1.yaml ~/.ktrdr/shared/strategies/context_classifier_seed_v1.yaml`

**If metadata_v3.json has output_type="classification" instead of "context_classification":**
- **Cause:** The label source detection in `_save_metadata_v3()` did not fire. The code checks `config.get("training", {}).get("labels", {}).get("source")` -- if the training config was not propagated through to metadata saving, it defaults to generic classification.
- **Cure:** Check `local_orchestrator.py` around line 694-708 -- the `label_source == "context"` branch must be reached. Verify the full config dict is passed to `_save_metadata_v3()`.

**If labels_source is "zigzag" instead of "context":**
- **Cause:** Strategy loader did not propagate the `training.labels` section from the YAML. The v3 strategy loader may be dropping non-standard label sources.
- **Cure:** Check the strategy loading path -- verify `context` is a supported label source type.

**If 0 samples or data error:**
- **Cause:** EURUSD 1d data not in cache
- **Cure:** Load data first: `curl -X POST http://localhost:$API_PORT/api/v1/data/EURUSD/1d`

**If training times out (> 3 minutes):**
- **Cause:** Worker busy or training hung. Daily data is small (~300 bars), so training should be fast.
- **Cure:** Check workers: `curl http://localhost:$API_PORT/api/v1/workers | jq`; check logs: `docker compose -f docker-compose.sandbox.yml logs backend --tail 50`

**If test accuracy is exactly 33% or all predictions are one class:**
- **Cause:** Model collapsed to predicting majority class. With 3 classes, degenerate behavior produces ~33% accuracy.
- **Cure:** Check label distribution -- if data is heavily imbalanced (e.g., 80% NEUTRAL), the model may learn to always predict NEUTRAL. The +/-0.5% thresholds in the strategy may need adjustment.

**If model.pt is missing but training shows "completed":**
- **Cause:** Model saving failed silently after training succeeded
- **Cure:** Check backend logs for write permission errors on the shared models directory

---

## Evidence to Capture

- Operation ID: `$TASK_ID`
- Final status: `curl ... | jq '.data.status'`
- Training metrics: `curl ... | jq '.data.result_summary.training_metrics'`
- Test metrics: `curl ... | jq '.data.result_summary.test_metrics'`
- Model directory path and file listing
- `metadata_v3.json` full contents (especially `output_type`)
- `config.json` key fields: `labels.source`, `loss`, `output_format`, `output_activation`
- `model.pt` file size
- Backend logs: `docker compose -f docker-compose.sandbox.yml logs backend --since 5m | grep -i "context\|output_type\|label"`
