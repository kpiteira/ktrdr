# Test: training/multi-timeframe-backtest

**Purpose:** Validate that a multi-timeframe v3 strategy (1h+4h+1d) can be trained and backtested end-to-end without KeyError on secondary timeframes, producing non-zero trades
**Duration:** ~5 minutes (training ~3min, backtest ~1min)
**Category:** Training + Backtest (Multi-Timeframe)

**Dependency:** None (self-contained: trains then backtests)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) -- Docker, sandbox, API health

**Test-specific checks:**
- [ ] Strategy file exists: `strategies/v3_multi_timeframe.yaml` in repo root
- [ ] Strategy copied to shared directory: `~/.ktrdr/shared/strategies/v3_multi_timeframe.yaml`
- [ ] EURUSD data available for 1h, 4h, and 1d timeframes
- [ ] At least one idle training worker
- [ ] At least one backtest worker registered

**Strategy copy (if missing):**
```bash
cp strategies/v3_multi_timeframe.yaml ~/.ktrdr/shared/strategies/v3_multi_timeframe.yaml
```

---

## Context: Why This Test Exists

The existing `test_v3_train_backtest.py` validates single-timeframe v3 strategies only. Multi-timeframe strategies define indicators computed across multiple timeframes (e.g., RSI on 1h, 4h, 1d). The backtest worker must load and align features from all timeframes. A known bug pattern is `KeyError: '4h'` or `KeyError: '1d'` when the backtest only receives the base timeframe but the model expects features from all configured timeframes.

This test proves the full pipeline handles multi-timeframe correctly: training resolves features across all timeframes, and backtest reconstructs them without errors.

---

## Test Data

```json
{
  "strategy_name": "v3_multi_timeframe",
  "strategy_file": "v3_multi_timeframe.yaml",
  "symbol": "EURUSD",
  "base_timeframe": "1h",
  "all_timeframes": ["1h", "4h", "1d"],
  "train_start": "2024-01-01",
  "train_end": "2025-03-01",
  "backtest_start": "2025-03-01",
  "backtest_end": "2025-06-01"
}
```

**Why this data:**
- EURUSD 1h over 14 months: ~10,000 samples, sufficient for training
- Multi-timeframe (1h, 4h, 1d): exercises the exact code path where KeyError occurs
- Backtest range (3 months) is out-of-sample relative to training
- Strategy uses RSI across all timeframes -- simple indicator, focuses test on multi-TF plumbing not indicator complexity

---

## Execution Steps

### 1. Environment Setup

**Command:**
```bash
cd <REPO_ROOT>
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8001}
echo "Using API_PORT=$API_PORT"
```

**Expected:**
- API_PORT is set (likely 8001 for sandbox slot 1)

### 2. Copy Strategy to Shared Directory

**Command:**
```bash
cd <REPO_ROOT>
cp strategies/v3_multi_timeframe.yaml ~/.ktrdr/shared/strategies/v3_multi_timeframe.yaml
echo "Strategy copied"
ls -la ~/.ktrdr/shared/strategies/v3_multi_timeframe.yaml
```

**Expected:**
- File exists at shared strategies location

### 3. Start Multi-Timeframe Training via API

**Command:**
```bash
cd <REPO_ROOT>
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8001}

RESPONSE=$(curl -s -X POST http://localhost:$API_PORT/api/v1/trainings/start \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["EURUSD"],
    "timeframes": ["1h"],
    "strategy_name": "v3_multi_timeframe",
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

**NOTE:** The `timeframes` parameter in the training request specifies the base timeframe for the API. The strategy file itself declares all three timeframes (1h, 4h, 1d) and the training pipeline resolves them from the strategy config. Do NOT pass all three timeframes in the request -- the strategy config is authoritative.

### 4. Wait for Training Completion

**Command:**
```bash
cd <REPO_ROOT>
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8001}

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
echo "Training Result:"
echo "$TRAIN_RESULT" | jq '{status:.data.status, samples:.data.result_summary.data_summary.total_samples}'
```

**Expected:**
- `status: "completed"` (not "failed" or "running")
- `samples` > 5000 (14 months of 1h data should yield ~10,000)
- Total wait < 5 minutes

**If status is "failed":**
```bash
echo "$TRAIN_RESULT" | jq '.data.error // .data.result_summary.error // "no error field"'
```
Capture the error message -- it likely indicates a multi-timeframe data resolution failure.

### 5. Extract Model Path from Training Result

**Command:**
```bash
cd <REPO_ROOT>
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8001}

MODEL_PATH=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$TASK_ID" | \
  jq -r '.data.result_summary.model_path // empty')

# Fallback: construct from convention
if [ -z "$MODEL_PATH" ]; then
  MODEL_PATH="models/v3_multi_timeframe/1h_latest"
fi

echo "Using model_path: $MODEL_PATH"
```

**Expected:**
- `MODEL_PATH` is non-empty
- Path contains the strategy name

### 6. Verify metadata_v3.json Contains Multi-Timeframe Features

**Command:**
```bash
cd <REPO_ROOT>

# Check metadata_v3.json exists and has multi-TF features
METADATA_FILE="$HOME/.ktrdr/shared/$MODEL_PATH/metadata_v3.json"
if [ ! -f "$METADATA_FILE" ]; then
  # Try alternative paths
  METADATA_FILE=$(find ~/.ktrdr/shared/models/v3_multi_timeframe -name "metadata_v3.json" -newer /tmp/e2e_start_marker 2>/dev/null | head -1)
fi

if [ -f "$METADATA_FILE" ]; then
  echo "metadata_v3.json found: $METADATA_FILE"
  cat "$METADATA_FILE" | jq '{
    strategy_version: .strategy_version,
    feature_count: (.resolved_features | length),
    features: .resolved_features
  }'
else
  echo "WARN: metadata_v3.json not found at expected paths"
fi
```

**Expected:**
- `strategy_version: "3.0"`
- `feature_count` > 3 (should be 9: 3 fuzzy sets x 3 timeframes)
- `resolved_features` includes references to 1h, 4h, and 1d timeframes

**This step is informational.** The critical validation is that backtest completes (Step 8). But capturing metadata here helps diagnose failures.

### 7. Start Backtest with Trained Multi-Timeframe Model

**Command:**
```bash
cd <REPO_ROOT>
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8001}

BT_RESPONSE=$(curl -s -X POST http://localhost:$API_PORT/api/v1/backtests/start \
  -H "Content-Type: application/json" \
  -d "{
    \"strategy_name\": \"v3_multi_timeframe\",
    \"symbol\": \"EURUSD\",
    \"timeframe\": \"1h\",
    \"start_date\": \"2025-03-01\",
    \"end_date\": \"2025-06-01\",
    \"model_path\": \"$MODEL_PATH\"
  }")

echo "Backtest Response: $BT_RESPONSE"

BT_OP_ID=$(echo "$BT_RESPONSE" | jq -r '.operation_id')
echo "Backtest Operation ID: $BT_OP_ID"
```

**Expected:**
- HTTP 200
- `operation_id` returned (non-null, non-empty)

### 8. Wait for Backtest Completion -- THE CRITICAL STEP

**Command:**
```bash
cd <REPO_ROOT>
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8001}

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
- `status: "completed"` -- NOT "failed"
- If "failed", capture error: `echo "$BT_RESULT" | jq '.data.error'`
- The specific failure this test guards against is `KeyError: '4h'` or `KeyError: '1d'` during feature resolution

### 9. Verify Trade Count > 0

**Command:**
```bash
cd <REPO_ROOT>
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8001}

BT_RESULT=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$BT_OP_ID")

TRADE_COUNT=$(echo "$BT_RESULT" | jq -r '.data.result_summary.trade_count // .data.result_summary.total_trades // 0')
TOTAL_BARS=$(echo "$BT_RESULT" | jq -r '.data.result_summary.total_bars // 0')

echo "Trades: $TRADE_COUNT"
echo "Total bars: $TOTAL_BARS"

if [ "$TRADE_COUNT" -gt 0 ]; then
  echo "PASS: Model produced $TRADE_COUNT trades"
else
  echo "FAIL: Zero trades -- features may not have resolved correctly"
fi
```

**Expected:**
- `TRADE_COUNT` > 0 (model produces trading signals)
- `TOTAL_BARS` > 1000 (3 months of 1h data ~ 2,000 bars)

### 10. Check Logs for Multi-Timeframe Errors

**Command:**
```bash
cd <REPO_ROOT>

# Check backend logs for KeyError or timeframe-related failures
docker compose -f docker-compose.sandbox.yml logs backend --since 10m 2>/dev/null | \
  grep -i "keyerror\|timeframe.*not found\|feature.*mismatch\|multi.*time" | tail -20
```

**Expected:**
- No `KeyError` lines mentioning timeframe keys (4h, 1d)
- No "feature mismatch" errors

---

## Success Criteria

All must pass for test to pass:

- [ ] Training starts successfully (HTTP 200, task_id returned)
- [ ] Training completes (status = "completed") within 5 minutes
- [ ] Model path is extractable from training result
- [ ] Backtest starts successfully (operation_id returned)
- [ ] Backtest completes without KeyError (status = "completed")
- [ ] Backtest produces trades (trade_count > 0)
- [ ] Backtest processed > 1000 bars (total_bars > 1000)
- [ ] No multi-timeframe errors in backend logs

---

## Sanity Checks

**CRITICAL:** These catch false positives

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| Training status is "completed" | "failed" or "running" fails | Training pipeline cannot handle multi-TF strategy |
| Training time > 1.0s | <= 1s fails | Training was skipped or cached |
| Training samples > 5000 | < 5000 fails | Data not loaded for all timeframes |
| Backtest status is "completed" | "failed" fails | KeyError or feature resolution bug |
| trade_count > 0 | 0 fails | Model degenerate or features not resolved |
| trade_count < total_bars | >= total_bars fails | Decision function ignoring confidence threshold |
| total_bars > 1000 | < 1000 fails | Backtest ran on truncated data |
| Training accuracy < 99% | >= 99% fails | Model collapse or data leakage |

**Sanity check command:**
```bash
cd <REPO_ROOT>
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8001}

echo "=== Training Sanity ==="
curl -s "http://localhost:$API_PORT/api/v1/operations/$TASK_ID" | jq '{
  status: .data.status,
  samples: .data.result_summary.data_summary.total_samples,
  val_loss: .data.result_summary.training_metrics.final_val_loss,
  training_time: .data.result_summary.training_metrics.training_time,
  test_accuracy: .data.result_summary.test_metrics.test_accuracy
}'

echo "=== Backtest Sanity ==="
curl -s "http://localhost:$API_PORT/api/v1/operations/$BT_OP_ID" | jq '{
  status: .data.status,
  trade_count: .data.result_summary.trade_count,
  total_bars: .data.result_summary.total_bars,
  total_return: .data.result_summary.metrics.total_return
}'
```

---

## Failure Categorization

| Failure Type | Category | Suggested Action |
|--------------|----------|------------------|
| Training: "strategy not found" | CONFIGURATION | Copy strategy to `~/.ktrdr/shared/strategies/` |
| Training: "No data for timeframe 4h/1d" | ENVIRONMENT | Load EURUSD data for all three timeframes via data API |
| Training: status "failed" with feature error | CODE_BUG | Check v3 feature resolver handles multi-timeframe nn_inputs |
| Backtest: KeyError '4h' or '1d' | CODE_BUG | Backtest worker only receives base_timeframe; must resolve all TFs from strategy config |
| Backtest: "feature mismatch" | CODE_BUG | model_bundle.py not reconstructing multi-TF features for backtest |
| Backtest: trade_count = 0 | CODE_BUG or CONFIGURATION | Features may resolve to all-zero (wrong column names), or confidence threshold too high |
| Timeout (training > 5min) | ENVIRONMENT | Check worker availability: `curl .../api/v1/workers` |
| Timeout (backtest > 2min) | ENVIRONMENT | Check backtest worker logs |
| Training: 100% accuracy | CODE_BUG | Model collapse -- check label distribution and training loop |

---

## Troubleshooting

**If training fails with "strategy not found":**
- **Cause:** Strategy file not copied to shared directory
- **Cure:** `cp strategies/v3_multi_timeframe.yaml ~/.ktrdr/shared/strategies/v3_multi_timeframe.yaml`

**If training fails with data-related error:**
- **Cause:** EURUSD data not available for 4h or 1d timeframes
- **Cure:** Load data via API for each timeframe:
  ```bash
  for TF in 1h 4h 1d; do
    curl -s -X POST "http://localhost:$API_PORT/api/v1/data/load" \
      -H "Content-Type: application/json" \
      -d "{\"symbol\":\"EURUSD\",\"timeframe\":\"$TF\",\"start_date\":\"2024-01-01\",\"end_date\":\"2025-06-01\"}"
  done
  ```

**If backtest fails with KeyError on a timeframe:**
- **Cause:** This is the exact bug this test is designed to catch. The backtest worker receives only `timeframe: 1h` but the model needs features from 1h, 4h, and 1d. The worker must read the strategy config (or metadata_v3.json) to discover all required timeframes.
- **Cure:** Fix the backtest pipeline to resolve all timeframes from the strategy/model metadata, not just the single timeframe passed in the API request.

**If backtest completes but trade_count = 0:**
- **Cause:** Features may have resolved to wrong column names, producing all-zero inputs. Model outputs uniform low-confidence predictions, all filtered by confidence threshold.
- **Cure:** Check metadata_v3.json resolved_features against what the backtest actually computes. Column name mismatch is the most likely cause.

**If training or backtest timeout:**
- **Cause:** Worker busy or crashed
- **Cure:** Check workers: `curl http://localhost:$API_PORT/api/v1/workers | jq`

---

## Evidence to Capture

- Training Operation ID: `$TASK_ID`
- Backtest Operation ID: `$BT_OP_ID`
- Model path: `$MODEL_PATH`
- metadata_v3.json contents (resolved_features list)
- Training metrics: samples, val_loss, training_time, test_accuracy
- Backtest metrics: trade_count, total_bars, total_return
- Backend logs: `docker compose -f docker-compose.sandbox.yml logs backend --since 10m | grep -i "keyerror\|timeframe\|multi_timeframe\|feature"`

---

## Notes for Implementation

- The strategy file `v3_multi_timeframe.yaml` has `name: v3_multi_timeframe_example` inside, but the API resolves by filename stem (`v3_multi_timeframe`). Use `strategy_name: "v3_multi_timeframe"` in API requests.
- The training API expects `symbols` (list) and `timeframes` (list) -- pass only the base timeframe `["1h"]`, not all three. The strategy config is authoritative for multi-TF resolution.
- The backtest API expects `symbol` (string) and `timeframe` (string) -- singular form, different from training API.
- Training returns `task_id` in the response. Backtest returns `operation_id`. Both are polled via `/api/v1/operations/{id}`.
- This test is reusable for any future multi-timeframe regression testing. The pattern (train multi-TF, backtest, verify no KeyError) applies to any multi-TF strategy.
- The 4h timeframe is particularly interesting because it requires resampling from 1h data in many data providers -- this exercises an additional code path beyond just 1h and 1d.
