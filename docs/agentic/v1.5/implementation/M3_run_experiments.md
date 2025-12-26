---
design: docs/agentic/v1.5/DESIGN.md
architecture: docs/agentic/v1.5/ARCHITECTURE.md
plan: docs/agentic/v1.5/PLAN.md
---

# Milestone 3: Run Experiments

**Goal:** Execute training on all 27 strategies, collect clean results.

**Why M3:** This is the actual experiment execution. The quality of our conclusions depends on having complete, reliable data from all strategies.

---

## Questions This Milestone Must Answer

| # | Question | How We'll Answer It | Success Criteria |
|---|----------|---------------------|------------------|
| Q3.1 | Did all strategies complete training? | Track operation status | ≥25/27 completed (>90%) |
| Q3.2 | Do we have analytics for each run? | Check output directories | Analytics files exist for each completed run |
| Q3.3 | Were there systematic failures? | Analyze failure patterns | No pattern suggesting infrastructure issue |
| Q3.4 | Is the data quality consistent? | Spot-check metrics files | No corrupted/truncated files |

---

## Training Configuration (from PLAN.md)

All strategies use these fixed parameters:

| Parameter | Value |
|-----------|-------|
| Symbol | EURUSD |
| Timeframe | 1h |
| Date range | 2015-01-01 to 2023-12-31 (8 years) |
| Split | 70% train / 15% val / 15% test |
| Epochs | 100 (with early stopping, patience 15) |
| Analytics | Enabled |

Expected training time per strategy: 10-30 minutes (depends on early stopping)

---

## Task 3.1: Create Execution Tracker

**File:** `docs/agentic/v1.5/EXECUTION_LOG.md`
**Type:** RESEARCH + CODING
**Estimated time:** 15 minutes

**Description:**
Create a tracking document to record each training run's status and results.

**Tracker Template:**

```markdown
# v1.5 Experiment Execution Log

## Status Summary

| Status | Count |
|--------|-------|
| Completed | 0 |
| Running | 0 |
| Failed | 0 |
| Pending | 27 |

## Execution Log

| Strategy | Started | Operation ID | Status | Duration | Notes |
|----------|---------|--------------|--------|----------|-------|
| v15_rsi_only | - | - | pending | - | - |
| v15_stochastic_only | - | - | pending | - | - |
| v15_williams_only | - | - | pending | - | - |
| v15_mfi_only | - | - | pending | - | - |
| v15_adx_only | - | - | pending | - | - |
| v15_aroon_only | - | - | pending | - | - |
| v15_cmf_only | - | - | pending | - | - |
| v15_rvi_only | - | - | pending | - | - |
| v15_di_only | - | - | pending | - | - |
| v15_rsi_adx | - | - | pending | - | - |
| v15_rsi_stochastic | - | - | pending | - | - |
| v15_rsi_williams | - | - | pending | - | - |
| v15_rsi_mfi | - | - | pending | - | - |
| v15_adx_aroon | - | - | pending | - | - |
| v15_adx_di | - | - | pending | - | - |
| v15_stochastic_williams | - | - | pending | - | - |
| v15_mfi_cmf | - | - | pending | - | - |
| v15_rsi_cmf | - | - | pending | - | - |
| v15_adx_rsi | - | - | pending | - | - |
| v15_aroon_rvi | - | - | pending | - | - |
| v15_rsi_adx_stochastic | - | - | pending | - | - |
| v15_mfi_adx_aroon | - | - | pending | - | - |
| v15_williams_stochastic_cmf | - | - | pending | - | - |
| v15_rsi_zigzag_1.5 | - | - | pending | - | - |
| v15_rsi_zigzag_2.0 | - | - | pending | - | - |
| v15_rsi_zigzag_3.0 | - | - | pending | - | - |
| v15_rsi_zigzag_3.5 | - | - | pending | - | - |

## Failures (if any)

### [Strategy Name]
- **Error:** [error message]
- **Logs:** [relevant log snippet]
- **Action:** [retry / skip / investigate]
```

**Acceptance Criteria:**
- [ ] Tracker file created
- [ ] All 27 strategies listed
- [ ] Status summary section ready

---

## Task 3.2: Execute All Training Runs

**Type:** EXECUTION
**Estimated time:** 4-8 hours (wall clock, mostly waiting)

**Description:**
Run training for all 27 strategies, one at a time, tracking progress.

**Execution Script:**

```bash
#!/bin/bash
# run_v15_experiments.sh

STRATEGIES=(
  "v15_rsi_only"
  "v15_stochastic_only"
  "v15_williams_only"
  "v15_mfi_only"
  "v15_adx_only"
  "v15_aroon_only"
  "v15_cmf_only"
  "v15_rvi_only"
  "v15_di_only"
  "v15_rsi_adx"
  "v15_rsi_stochastic"
  "v15_rsi_williams"
  "v15_rsi_mfi"
  "v15_adx_aroon"
  "v15_adx_di"
  "v15_stochastic_williams"
  "v15_mfi_cmf"
  "v15_rsi_cmf"
  "v15_adx_rsi"
  "v15_aroon_rvi"
  "v15_rsi_adx_stochastic"
  "v15_mfi_adx_aroon"
  "v15_williams_stochastic_cmf"
  "v15_rsi_zigzag_1.5"
  "v15_rsi_zigzag_2.0"
  "v15_rsi_zigzag_3.0"
  "v15_rsi_zigzag_3.5"
)

LOG_FILE="docs/agentic/v1.5/experiment_results.txt"
echo "v1.5 Experiment Execution Log" > $LOG_FILE
echo "Started: $(date)" >> $LOG_FILE
echo "" >> $LOG_FILE

for strategy in "${STRATEGIES[@]}"; do
  echo "=== Starting: $strategy ===" | tee -a $LOG_FILE
  START_TIME=$(date +%s)

  # Start training
  RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v1/training/start" \
    -H "Content-Type: application/json" \
    -d "{\"strategy_name\": \"$strategy\", \"symbol\": \"EURUSD\", \"timeframe\": \"1h\"}")

  OP_ID=$(echo $RESPONSE | jq -r '.operation_id // .data.operation_id // empty')

  if [ -z "$OP_ID" ]; then
    echo "FAILED to start: $RESPONSE" | tee -a $LOG_FILE
    continue
  fi

  echo "Operation ID: $OP_ID" | tee -a $LOG_FILE

  # Poll for completion
  while true; do
    STATUS_RESPONSE=$(curl -s "http://localhost:8000/api/v1/operations/$OP_ID")
    STATUS=$(echo $STATUS_RESPONSE | jq -r '.data.status // .status')

    if [ "$STATUS" = "completed" ]; then
      END_TIME=$(date +%s)
      DURATION=$((END_TIME - START_TIME))
      echo "COMPLETED in ${DURATION}s" | tee -a $LOG_FILE
      break
    elif [ "$STATUS" = "failed" ]; then
      ERROR=$(echo $STATUS_RESPONSE | jq -r '.data.error // .error // "unknown"')
      echo "FAILED: $ERROR" | tee -a $LOG_FILE
      break
    fi

    sleep 30
  done

  echo "" >> $LOG_FILE
done

echo "" >> $LOG_FILE
echo "Completed: $(date)" >> $LOG_FILE
```

**Manual Execution Alternative:**

If automated script has issues, run manually:

```bash
# For each strategy:
curl -X POST "http://localhost:8000/api/v1/training/start" \
  -H "Content-Type: application/json" \
  -d '{"strategy_name": "v15_rsi_only", "symbol": "EURUSD", "timeframe": "1h"}' | jq

# Note the operation_id, then poll:
curl "http://localhost:8000/api/v1/operations/{operation_id}" | jq
```

**During Execution:**

1. Update EXECUTION_LOG.md after each completion
2. Note any failures with error messages
3. Check backend logs if training seems stuck

**Acceptance Criteria:**
- [ ] All 27 strategies attempted
- [ ] ≥25/27 completed successfully (>90%)
- [ ] Each run's operation_id recorded
- [ ] Failures documented with error messages

---

## Task 3.3: Verify Analytics Output

**Type:** VERIFICATION
**Estimated time:** 30 minutes

**Description:**
Confirm analytics files exist for all completed runs and data quality is acceptable.

**Verification Steps:**

```bash
#!/bin/bash
# verify_analytics.sh

echo "=== Analytics Verification ==="
echo ""

TOTAL=0
FOUND=0
MISSING=0

for run_dir in training_analytics/runs/*/; do
  TOTAL=$((TOTAL + 1))
  RUN_ID=$(basename $run_dir)

  # Check all expected files
  METRICS_OK=false
  JSON_OK=false
  ALERTS_OK=false
  CONFIG_OK=false

  [ -f "$run_dir/metrics.csv" ] && [ -s "$run_dir/metrics.csv" ] && METRICS_OK=true
  [ -f "$run_dir/detailed_metrics.json" ] && [ -s "$run_dir/detailed_metrics.json" ] && JSON_OK=true
  [ -f "$run_dir/alerts.txt" ] && ALERTS_OK=true
  [ -f "$run_dir/config.yaml" ] && [ -s "$run_dir/config.yaml" ] && CONFIG_OK=true

  if $METRICS_OK && $JSON_OK && $ALERTS_OK && $CONFIG_OK; then
    echo "✓ $RUN_ID"
    FOUND=$((FOUND + 1))
  else
    echo "✗ $RUN_ID"
    $METRICS_OK || echo "  - Missing/empty: metrics.csv"
    $JSON_OK || echo "  - Missing/empty: detailed_metrics.json"
    $ALERTS_OK || echo "  - Missing: alerts.txt"
    $CONFIG_OK || echo "  - Missing/empty: config.yaml"
    MISSING=$((MISSING + 1))
  fi
done

echo ""
echo "=== Summary ==="
echo "Total runs: $TOTAL"
echo "Complete analytics: $FOUND"
echo "Missing analytics: $MISSING"
```

**Data Quality Spot Checks:**

```bash
# Check a few metrics.csv files for validity
for run_dir in training_analytics/runs/*/; do
  RUN_ID=$(basename $run_dir)
  LINES=$(wc -l < "$run_dir/metrics.csv")
  LAST_EPOCH=$(tail -1 "$run_dir/metrics.csv" | cut -d',' -f1)
  LAST_VAL_ACC=$(tail -1 "$run_dir/metrics.csv" | cut -d',' -f5)

  echo "$RUN_ID: $LINES lines, last_epoch=$LAST_EPOCH, val_acc=$LAST_VAL_ACC"
done | head -10
```

**Expected Data Quality:**
- Each metrics.csv should have 10-100 lines (early stopping may reduce)
- val_accuracy should be between 0 and 1
- No NaN or empty values in required columns

**Acceptance Criteria:**
- [ ] Analytics exist for all completed runs
- [ ] metrics.csv files have valid data
- [ ] No corrupted or truncated files
- [ ] Strategy names can be mapped to run directories (via config.yaml)

---

## Task 3.4: Handle Failures

**Type:** RESEARCH + EXECUTION
**Estimated time:** Variable (depends on failures)

**Trigger:** Only execute if any strategies failed in Task 3.2.

**Description:**
Investigate and resolve training failures.

**Failure Triage:**

| Failure Type | Symptoms | Action |
|--------------|----------|--------|
| Data not available | "No data for EURUSD" | Check data cache, reload if needed |
| Config error | "Invalid indicator" | Fix strategy YAML, re-run M2 validation |
| OOM | Backend crashes | Reduce batch_size or run outside Docker |
| Timeout | Status stuck at "running" | Check logs, may need longer timeout |
| Model error | "Shape mismatch" | Likely fuzzy config issue, check feature_ids |

**For Each Failure:**

1. Check backend logs:
```bash
docker compose logs backend --since 1h | grep -i error
```

2. Document in EXECUTION_LOG.md

3. Decide action:
   - **Retry once** if transient (OOM, timeout)
   - **Fix and retry** if config error
   - **Skip** if fundamental issue (document why)

**Acceptance Criteria:**
- [ ] All failures investigated
- [ ] Retriable failures retried
- [ ] Remaining failures documented with reason
- [ ] Final count: ≥25/27 completed

---

## Milestone 3 Verification

### E2E Test Scenario

**Purpose:** Verify all experiments ran and produced usable data
**Duration:** After training completes
**Prerequisites:** M1 and M2 complete

**Test Steps:**

```bash
# 1. Count completed runs
grep "completed" docs/agentic/v1.5/EXECUTION_LOG.md | wc -l
# Expected: ≥25

# 2. Count analytics directories
ls -d training_analytics/runs/*/ | wc -l
# Expected: ≥25

# 3. Verify analytics completeness
for dir in training_analytics/runs/*/; do
  [ -f "$dir/metrics.csv" ] && [ -f "$dir/detailed_metrics.json" ] && echo "OK: $dir"
done | wc -l
# Expected: ≥25

# 4. Check for systematic failures
grep "failed" docs/agentic/v1.5/EXECUTION_LOG.md
# Expected: ≤2 failures, no common pattern

# 5. Spot check data quality
tail -1 training_analytics/runs/*/metrics.csv | head -5
# Expected: Valid accuracy values (not NaN, in 0-1 range)
```

**Success Criteria:**
- [ ] ≥25/27 strategies completed successfully
- [ ] Analytics files exist for all completed runs
- [ ] No systematic failure pattern
- [ ] Data quality verified

### Completion Checklist

- [ ] Task 3.1: Execution tracker created
- [ ] Task 3.2: All training runs executed
- [ ] Task 3.3: Analytics output verified
- [ ] Task 3.4: Failures handled (if any)
- [ ] All M3 questions answered:
  - [ ] Q3.1: ≥25/27 completed
  - [ ] Q3.2: Analytics exist for each run
  - [ ] Q3.3: No systematic failures
  - [ ] Q3.4: Data quality consistent

### Validation Checkpoint

After M3, we must be able to answer **YES** to:
- [ ] "Do we have enough data to draw conclusions?" (≥25 strategies)
- [ ] "Are failures random or systematic?" (Random is acceptable)

If completion rate is <90%, investigate before proceeding to M4.

---

*Estimated time: 4-8 hours (mostly training runtime)*
