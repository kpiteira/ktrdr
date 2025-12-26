---
design: docs/agentic/v1.5/DESIGN.md
architecture: docs/agentic/v1.5/ARCHITECTURE.md
plan: docs/agentic/v1.5/PLAN.md
---

# Milestone 1: Validate Analytics & Diagnostics

**Goal:** Confirm the training analytics pipeline produces correct, readable output before we depend on it for conclusions.

**Why M1:** We can't trust experiment results if the measurement system is broken. All risks (training not working, indicators not working, labeling not working) require functioning analytics to diagnose.

---

## Questions This Milestone Must Answer

| # | Question | How We'll Answer It | Success Criteria |
|---|----------|---------------------|------------------|
| Q1.1 | Does TrainingAnalyzer execute during training? | Check logs for analytics code path | Log entries show analytics running |
| Q1.2 | Are output files created? | Check `training_analytics/runs/{run_id}/` | All 4 files exist and non-empty |
| Q1.3 | Is `metrics.csv` schema correct? | Read file, check columns | Has: epoch, train_loss, val_loss, val_accuracy, learning_signal_strength |
| Q1.4 | Are metric values sensible? | Check value ranges | accuracy in [0,1], loss > 0, epochs sequential |
| Q1.5 | Is label distribution as expected? | Check training output/logs | ~50% BUY / ~1% HOLD / ~49% SELL |
| Q1.6 | Are fuzzy features non-zero? | Check feature statistics in output | Feature variance > 0 for RSI fuzzy outputs |
| Q1.7 | Can we interpret learning signal? | Read final metrics | Can state: "accuracy=X%, signal=Y" |

---

## Task 1.1: Create Minimal Test Strategy

**File:** `strategies/v15_test_analytics.yaml`
**Type:** RESEARCH + CODING
**Estimated time:** 30 minutes

**Description:**
Create a minimal strategy using only RSI (simplest Tier 1 indicator) with correct fuzzy sets from the DESIGN.md reference. This strategy exists solely to verify TrainingAnalyzer works.

**Implementation Notes:**
- Copy structure from `neuro_mean_reversion.yaml` as template
- Replace indicators with RSI only
- Use exact fuzzy sets from DESIGN.md:
  - oversold: [0, 30, 40]
  - neutral: [35, 50, 65]
  - overbought: [60, 70, 100]
- Use single symbol (EURUSD) and single timeframe (1h) for simplicity
- Enable analytics explicitly: `model.training.analytics.enabled: true`
- Short training: 10 epochs (just enough to verify analytics)
- Small date range: 2023-01-01 to 2023-06-30 (6 months)

**Strategy Configuration:**

```yaml
name: "v15_test_analytics"
description: "Minimal test strategy to validate TrainingAnalyzer output"
version: "1.0"

# Single symbol, single timeframe for simplicity
training_data:
  symbols:
    mode: "single_symbol"
    list: ["EURUSD"]
  timeframes:
    mode: "single_timeframe"
    list: ["1h"]
    base_timeframe: "1h"
  history_required: 100

# RSI only - simplest Tier 1 indicator
indicators:
  - name: "rsi"
    feature_id: rsi_14
    period: 14
    source: "close"

# Exact fuzzy sets from DESIGN.md reference
fuzzy_sets:
  rsi_14:
    oversold:
      type: "triangular"
      parameters: [0, 30, 40]
    neutral:
      type: "triangular"
      parameters: [35, 50, 65]
    overbought:
      type: "triangular"
      parameters: [60, 70, 100]

model:
  type: "mlp"
  architecture:
    hidden_layers: [32, 16]
    activation: "relu"
    output_activation: "softmax"
    dropout: 0.2
  features:
    include_price_context: false
    lookback_periods: 1
    scale_features: true
  training:
    learning_rate: 0.001
    batch_size: 32
    epochs: 10  # Short run - just validating analytics
    optimizer: "adam"
    analytics:
      enabled: true
      export_csv: true
      export_json: true
      export_alerts: true

training:
  method: "supervised"
  labels:
    source: "zigzag"
    zigzag_threshold: 0.025  # 2.5% threshold
    label_lookahead: 20
  data_split:
    train: 0.7
    validation: 0.15
    test: 0.15
  date_range:
    start: "2023-01-01"
    end: "2023-06-30"
```

**Acceptance Criteria:**
- [ ] Strategy file created at `strategies/v15_test_analytics.yaml`
- [ ] File passes YAML syntax validation
- [ ] Uses only RSI (Tier 1 indicator)
- [ ] Fuzzy sets match DESIGN.md reference exactly
- [ ] Analytics explicitly enabled

---

## Task 1.2: Run Short Training

**Type:** EXECUTION
**Estimated time:** 10-15 minutes (training runtime)

**Description:**
Execute training using the API to verify the TrainingAnalyzer code path runs.

**Execution Steps:**

```bash
# 1. Validate strategy first
curl -X POST "http://localhost:8000/api/v1/strategies/validate/v15_test_analytics" | jq

# 2. Start training
curl -X POST "http://localhost:8000/api/v1/training/start" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "v15_test_analytics",
    "symbol": "EURUSD",
    "timeframe": "1h"
  }' | jq

# 3. Note the operation_id from response
# 4. Monitor progress
curl "http://localhost:8000/api/v1/operations/{operation_id}" | jq
```

**What to Watch For:**
- Training starts without immediate errors
- Progress updates show epochs completing
- No "analytics" related errors in logs

**Acceptance Criteria:**
- [ ] Training completes without error (status: "completed")
- [ ] Operation took reasonable time (10 epochs should be < 5 minutes)
- [ ] No analytics-related errors in backend logs

---

## Task 1.3: Check Output Files Exist

**Type:** VERIFICATION
**Estimated time:** 10 minutes

**Description:**
Verify TrainingAnalyzer created the expected output files.

**Verification Steps:**

```bash
# Find the run directory (uses operation_id or timestamp)
ls -la training_analytics/runs/

# Check for expected files
RUN_DIR="training_analytics/runs/{run_id}"
ls -la $RUN_DIR

# Verify files are non-empty
wc -l $RUN_DIR/metrics.csv
wc -c $RUN_DIR/detailed_metrics.json
wc -l $RUN_DIR/alerts.txt
wc -c $RUN_DIR/config.yaml
```

**Expected Files:**

| File | Description | Non-Empty Check |
|------|-------------|-----------------|
| `metrics.csv` | Per-epoch metrics | Should have 11+ lines (header + 10 epochs) |
| `detailed_metrics.json` | Full JSON export | Should be > 1KB |
| `alerts.txt` | Human-readable alerts | May be small if no alerts |
| `config.yaml` | Training config copy | Should match input strategy |

**If Files Missing:**
- Note which files are missing
- Check backend logs for export errors
- Check if `training_analytics/` directory exists at all
- Proceed to Task 1.4 (Diagnose Issues)

**Acceptance Criteria:**
- [ ] `training_analytics/runs/{run_id}/` directory exists
- [ ] `metrics.csv` exists and has data rows
- [ ] `detailed_metrics.json` exists and is valid JSON
- [ ] `alerts.txt` exists
- [ ] `config.yaml` exists and matches input strategy

---

## Task 1.4: Diagnose Issues (Conditional)

**Type:** RESEARCH
**Estimated time:** 30-60 minutes (if needed)

**Trigger:** Only execute if Task 1.3 found missing or malformed files.

**Description:**
If analytics output is broken, identify the specific failure point before attempting fixes.

**Diagnostic Steps:**

1. **Check if analytics code path executed:**
```bash
# Search backend logs for TrainingAnalyzer mentions
docker compose logs backend --since 30m | grep -i "analytics\|TrainingAnalyzer"
```

2. **Check for exceptions during export:**
```bash
docker compose logs backend --since 30m | grep -i "error\|exception\|failed"
```

3. **Verify TrainingAnalyzer is instantiated:**
Check `ktrdr/training/model_trainer.py` for where TrainingAnalyzer is created and called.

4. **Check analytics config propagation:**
Does the `analytics.enabled: true` config actually reach the trainer?

5. **Check file permissions:**
```bash
ls -la training_analytics/
```

**Document Findings:**
Create a diagnostic summary:

```markdown
## Analytics Diagnostic Summary

**Files Status:**
- metrics.csv: [exists/missing/malformed]
- detailed_metrics.json: [exists/missing/malformed]
- alerts.txt: [exists/missing/malformed]
- config.yaml: [exists/missing/malformed]

**Failure Point:**
[Where in the code path did it fail?]

**Specific Error:**
[Error message from logs]

**Root Cause Hypothesis:**
[What we think is wrong]
```

**Acceptance Criteria:**
- [ ] Clear documentation of what's broken
- [ ] Identified specific failure point in code
- [ ] Root cause hypothesis documented
- [ ] Ready to proceed to Task 1.5 (Fix Issues)

---

## Task 1.5: Fix Issues (Conditional)

**Type:** CODING
**Estimated time:** 1-2 hours (if needed)

**Trigger:** Only execute if Task 1.4 identified fixable issues.

**Description:**
Fix identified bugs in TrainingAnalyzer or its integration.

**Common Issues and Fixes:**

| Issue | Likely Cause | Fix |
|-------|--------------|-----|
| Directory not created | Missing `mkdir -p` | Add directory creation in trainer |
| Files not written | Export not called | Call `analyzer.export_all()` after training |
| Config not propagated | Missing config path | Pass analytics config through trainer |
| JSON serialization error | Non-serializable types | Convert numpy/torch types |
| Empty metrics | collect_epoch_metrics not called | Add calls in training loop |

**Fix Requirements:**
1. Fix must not change training behavior
2. Add unit test for the specific issue
3. Verify fix with re-run of Task 1.2

**Testing:**

```python
# Example unit test for export
def test_training_analyzer_exports_files(tmp_path):
    """Verify TrainingAnalyzer creates all expected files."""
    analyzer = TrainingAnalyzer(
        run_id="test_run",
        output_dir=tmp_path,
        config={"model": {"training": {"analytics": {"enabled": True}}}}
    )

    # Simulate minimal epoch
    # ... (add mock metrics)

    analyzer.finalize_training(final_epoch=1, stopping_reason="test")
    paths = analyzer.export_all()

    assert (tmp_path / "metrics.csv").exists()
    assert (tmp_path / "detailed_metrics.json").exists()
    assert (tmp_path / "alerts.txt").exists()
    assert (tmp_path / "config.yaml").exists()
```

**Acceptance Criteria:**
- [ ] Identified issue is fixed
- [ ] Unit test added for the fix
- [ ] Re-run of Task 1.2 produces all expected files
- [ ] No regressions in existing training functionality

---

## Task 1.6: Verify Metrics Are Readable and Sensible

**Type:** VERIFICATION
**Estimated time:** 20 minutes

**Description:**
Read the analytics output and verify it contains useful, interpretable data.

**Verification Steps:**

1. **Read metrics.csv:**
```bash
# View header and first few rows
head -5 training_analytics/runs/{run_id}/metrics.csv

# Check columns exist
head -1 training_analytics/runs/{run_id}/metrics.csv
```

**Expected columns (from DetailedTrainingMetrics.to_csv_row()):**
- epoch
- train_loss
- train_accuracy
- val_loss
- val_accuracy
- learning_rate
- learning_signal_strength
- gradient_norm_avg
- prediction_confidence_avg

2. **Verify value ranges:**

| Metric | Valid Range | Red Flag If |
|--------|-------------|-------------|
| epoch | 1 to N | Non-sequential |
| train_loss | > 0 | Negative or zero |
| val_loss | > 0 | Negative or zero |
| train_accuracy | [0, 1] | Outside range |
| val_accuracy | [0, 1] | Outside range |
| learning_signal_strength | "weak"/"medium"/"strong" | Empty or numeric |

3. **Check label distribution (answers Q1.5):**
```bash
# Look for label distribution in detailed_metrics.json
cat training_analytics/runs/{run_id}/detailed_metrics.json | jq '.training_config.labels'
# Or check backend logs for label counts during training
```

Expected: ~50% BUY / ~1% HOLD / ~49% SELL (effectively binary)

4. **Check feature statistics (answers Q1.6):**
Look in detailed_metrics.json for class_supports or feature-related metrics.
- RSI fuzzy outputs should show variance (not all zeros)
- If variance is zero, fuzzy transform may not be working

5. **Interpret learning signal (answers Q1.7):**
```bash
# Get final epoch metrics
tail -1 training_analytics/runs/{run_id}/metrics.csv
```

State clearly: "Training reached X% validation accuracy, learning signal was Y"

**Acceptance Criteria:**
- [ ] metrics.csv has expected columns
- [ ] All values in valid ranges
- [ ] Can identify label distribution (Q1.5 answered)
- [ ] Fuzzy features show non-zero variance (Q1.6 answered)
- [ ] Can state final accuracy and learning signal (Q1.7 answered)

---

## Milestone 1 Verification

### E2E Test Scenario

**Purpose:** Prove TrainingAnalyzer produces correct, readable output
**Duration:** ~15 minutes (including training time)
**Prerequisites:** Backend running, EURUSD 1h data available

**Test Steps:**

```bash
# 1. Create test strategy (Task 1.1)
# (Manual: create strategies/v15_test_analytics.yaml)

# 2. Validate strategy
curl -X POST "http://localhost:8000/api/v1/strategies/validate/v15_test_analytics" | jq '.valid'
# Expected: true

# 3. Run training
RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v1/training/start" \
  -H "Content-Type: application/json" \
  -d '{"strategy_name": "v15_test_analytics", "symbol": "EURUSD", "timeframe": "1h"}')
OP_ID=$(echo $RESPONSE | jq -r '.operation_id')
echo "Operation ID: $OP_ID"

# 4. Wait for completion (poll every 30s)
while true; do
  STATUS=$(curl -s "http://localhost:8000/api/v1/operations/$OP_ID" | jq -r '.data.status')
  echo "Status: $STATUS"
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then break; fi
  sleep 30
done

# 5. Find analytics directory
RUN_DIR=$(ls -td training_analytics/runs/*/ | head -1)
echo "Run directory: $RUN_DIR"

# 6. Verify files exist
ls -la $RUN_DIR

# 7. Check metrics.csv
echo "=== Metrics CSV ==="
head -3 $RUN_DIR/metrics.csv
tail -1 $RUN_DIR/metrics.csv

# 8. Verify we can interpret results
FINAL_ACCURACY=$(tail -1 $RUN_DIR/metrics.csv | cut -d',' -f5)
SIGNAL=$(tail -1 $RUN_DIR/metrics.csv | cut -d',' -f7)
echo "Final: accuracy=$FINAL_ACCURACY, signal=$SIGNAL"
```

**Success Criteria:**
- [ ] Strategy validation passes
- [ ] Training completes without error
- [ ] All 4 analytics files exist
- [ ] metrics.csv has valid data
- [ ] Can state "Training reached X% accuracy, signal was Y"

### Completion Checklist

- [ ] Task 1.1: Test strategy created
- [ ] Task 1.2: Training completed
- [ ] Task 1.3: All output files verified
- [ ] Task 1.4: (Conditional) Issues diagnosed if any
- [ ] Task 1.5: (Conditional) Issues fixed with tests
- [ ] Task 1.6: Metrics verified as readable and sensible
- [ ] All M1 questions answered:
  - [ ] Q1.1: TrainingAnalyzer executes
  - [ ] Q1.2: Output files created
  - [ ] Q1.3: metrics.csv schema correct
  - [ ] Q1.4: Metric values sensible
  - [ ] Q1.5: Label distribution ~50/1/49
  - [ ] Q1.6: Fuzzy features non-zero variance
  - [ ] Q1.7: Can interpret learning signal

### Validation Checkpoint

After M1, we must be able to answer **YES** to:
- [ ] "Can we trust the metrics we're reading?"
- [ ] "If training fails, will we know why?"
- [ ] "Is the labeling producing the expected distribution?"

If any answer is NO, do not proceed to M2.

---

*Estimated time: 2-4 hours (depends on whether fixes needed)*
