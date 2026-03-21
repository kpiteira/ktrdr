# Test: training/experiment-1-tb-vs-forward-return

**Purpose:** Validate that triple barrier labels (TB) produce a viable classification model and compare its backtest performance against the forward-return regression baseline (FR) -- the critical Experiment 1 for signal model evolution.
**Duration:** ~20-30 minutes (two training runs on 4 years of 1h data + two backtests)
**Category:** Training (Experiment Comparison)

**Dependency:**
- Strategies: `trend_tb_signal_v1.yaml` (repo), `trend_regression_signal_v1.yaml` (shared)
- Both strategies MUST use identical indicators (RSI, ADX, MACD, ROC) and fuzzy sets for apples-to-apples comparison

---

## Pre-Flight Checks

**Required modules:**
- [common](../../../e2e-testing/preflight/common.md) -- Docker, sandbox, API health
- [training](../../../e2e-testing/preflight/training.md) -- Strategy, data, workers
- [backtest](../../../e2e-testing/preflight/backtest.md) -- Workers for backtest phase

**Test-specific checks:**
- [ ] TB strategy exists: `strategies/trend_tb_signal_v1.yaml` (repo) AND `~/.ktrdr/shared/strategies/trend_tb_signal_v1.yaml`
- [ ] FR strategy exists: `~/.ktrdr/shared/strategies/trend_regression_signal_v1.yaml`
- [ ] EURUSD 1h data is available (2020-01-01 to 2025-01-01 -- 4 years train + 1 year backtest)
- [ ] At least 2 idle training workers (to avoid blocking if one is busy)
- [ ] At least 1 backtest worker
- [ ] No stale models from previous runs at `~/.ktrdr/shared/models/trend_tb_signal_v1/` or `~/.ktrdr/shared/models/trend_regression_signal/`

**Pre-flight commands:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# 1. API health
curl -sf "http://localhost:$API_PORT/api/v1/health" > /dev/null || {
  echo "FAIL: API not healthy on port $API_PORT"
  exit 1
}

# 2. Training workers
TRAIN_WORKERS=$(curl -s "http://localhost:$API_PORT/api/v1/workers" | jq '[.workers[] | select(.type=="training")] | length')
echo "Training workers: $TRAIN_WORKERS"
test "$TRAIN_WORKERS" -ge 1 || {
  echo "FAIL: No training workers registered"
  exit 1
}

# 3. Backtest workers
BT_WORKERS=$(curl -s "http://localhost:$API_PORT/api/v1/workers" | jq '[.workers[] | select(.type=="backtest")] | length')
echo "Backtest workers: $BT_WORKERS"
test "$BT_WORKERS" -ge 1 || {
  echo "FAIL: No backtest workers registered"
  exit 1
}

# 4. TB strategy in repo
test -f strategies/trend_tb_signal_v1.yaml && echo "OK: TB strategy in repo" || echo "FAIL: TB strategy missing from repo"

# 5. FR strategy in shared
test -f ~/.ktrdr/shared/strategies/trend_regression_signal_v1.yaml && echo "OK: FR strategy in shared" || echo "FAIL: FR strategy missing from shared"

# 6. Copy TB strategy to shared (needed for API to find it)
cp strategies/trend_tb_signal_v1.yaml ~/.ktrdr/shared/strategies/trend_tb_signal_v1.yaml
echo "OK: TB strategy copied to shared"
```

---

## Test Data

### Strategy Comparison Matrix

| Property | TB (trend_tb_signal_v1) | FR (trend_regression_signal) |
|---|---|---|
| Labels | triple_barrier (3-class: BUY/HOLD/SELL) | forward_return (regression, horizon=12) |
| Output | classification | regression |
| Loss | focal (gamma=2.0) | huber (delta=0.005) |
| Epochs | 200 (early stopping patience=15) | 80 |
| Architecture | MLP [64, 32], dropout=0.3 | MLP [64, 32], dropout=0.2 |
| Indicators | RSI, ADX, MACD, ROC | RSI, ADX, MACD, ROC (identical) |
| Fuzzy sets | rsi_zone, adx_strength, adx_direction, macd_signal, macd_momentum, roc_direction | Identical |
| Training period | 2020-01-01 to 2024-01-01 | 2019-01-01 to 2024-01-01 (FR has 1 extra year) |
| TB-specific | pt=2.0, sl=1.5, max_hold=50, vol_span=50, CUSUM+uniqueness weights | N/A |
| M3-specific | Purged cross-validation, sample weights | N/A |

**Why this comparison:**
- Same indicators and fuzzy encoding ensures difference comes from label methodology, not feature engineering
- 4 years of 1h data (~26,000 bars for TB, ~32,500 for FR) provides sufficient statistical power
- Backtest on 2024 data is out-of-sample for both
- TB model exercises all M1-M3 features: triple barrier labels, focal loss, purged CV, sample weights

### Training Payloads

**TB model:**
```json
{
  "symbols": ["EURUSD"],
  "timeframes": ["1h"],
  "strategy_name": "trend_tb_signal_v1",
  "start_date": "2020-01-01",
  "end_date": "2024-01-01"
}
```

**FR model:**
```json
{
  "symbols": ["EURUSD"],
  "timeframes": ["1h"],
  "strategy_name": "trend_regression_signal",
  "start_date": "2019-01-01",
  "end_date": "2024-01-01"
}
```

---

## Execution Steps

### Phase A: Train Both Models

#### 1. Copy TB Strategy to Shared Directory

**Command:**
```bash
cp strategies/trend_tb_signal_v1.yaml ~/.ktrdr/shared/strategies/trend_tb_signal_v1.yaml
echo "TB strategy copied"
ls -la ~/.ktrdr/shared/strategies/trend_tb_signal_v1.yaml
```

**Expected:**
- File exists in shared strategies directory

#### 2. Clean Previous TB Model (Clean Slate)

**Command:**
```bash
TB_MODEL_DIR="$HOME/.ktrdr/shared/models/trend_tb_signal_v1"
if [ -d "$TB_MODEL_DIR" ]; then
  echo "Removing previous TB model at $TB_MODEL_DIR"
  rm -rf "$TB_MODEL_DIR"
fi
echo "TB model clean slate confirmed"
```

**Expected:**
- No pre-existing TB model artifacts

#### 3. Start TB Model Training

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

TB_RESPONSE=$(curl -s -X POST "http://localhost:$API_PORT/api/v1/trainings/start" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["EURUSD"],
    "timeframes": ["1h"],
    "strategy_name": "trend_tb_signal_v1",
    "start_date": "2020-01-01",
    "end_date": "2024-01-01"
  }')

echo "TB Training Response: $TB_RESPONSE"

TB_TASK_ID=$(echo "$TB_RESPONSE" | jq -r '.task_id')
echo "TB Task ID: $TB_TASK_ID"
```

**Expected:**
- HTTP 200 with `task_id` returned
- No error about unknown label source `triple_barrier`
- No error about unknown loss `focal`

#### 4. Start FR Model Training (Can Run in Parallel If Workers Available)

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

FR_RESPONSE=$(curl -s -X POST "http://localhost:$API_PORT/api/v1/trainings/start" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["EURUSD"],
    "timeframes": ["1h"],
    "strategy_name": "trend_regression_signal",
    "start_date": "2019-01-01",
    "end_date": "2024-01-01"
  }')

echo "FR Training Response: $FR_RESPONSE"

FR_TASK_ID=$(echo "$FR_RESPONSE" | jq -r '.task_id')
echo "FR Task ID: $FR_TASK_ID"
```

**Expected:**
- HTTP 200 with `task_id` returned
- If only 1 worker: FR queues until TB completes (that is fine, poll will handle it)

#### 5. Wait for Both Trainings to Complete

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Poll every 30s for up to 25 minutes (TB with 200 epochs + early stopping on 4y data is slow)
TB_DONE=false
FR_DONE=false

for i in $(seq 1 50); do
  sleep 30

  if [ "$TB_DONE" = "false" ]; then
    TB_STATUS=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$TB_TASK_ID" | jq -r '.data.status')
    echo "Poll $i: TB=$TB_STATUS"
    if [ "$TB_STATUS" = "completed" ] || [ "$TB_STATUS" = "failed" ]; then
      TB_DONE=true
    fi
  fi

  if [ "$FR_DONE" = "false" ]; then
    FR_STATUS=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$FR_TASK_ID" | jq -r '.data.status')
    echo "Poll $i: FR=$FR_STATUS"
    if [ "$FR_STATUS" = "completed" ] || [ "$FR_STATUS" = "failed" ]; then
      FR_DONE=true
    fi
  fi

  if [ "$TB_DONE" = "true" ] && [ "$FR_DONE" = "true" ]; then
    echo "Both trainings finished"
    break
  fi
done

echo ""
echo "=== Final Training Status ==="
echo "TB: $TB_STATUS"
echo "FR: $FR_STATUS"
```

**Expected:**
- Both reach `status: "completed"` (not "failed")
- Total wait < 25 minutes

#### 6. Verify TB Training Results

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

echo "=== TB Training Results ==="
curl -s "http://localhost:$API_PORT/api/v1/operations/$TB_TASK_ID" | jq '{
  status: .data.status,
  result_summary: .data.result_summary
}'
```

**Expected:**
- `status: "completed"`
- `result_summary` contains training metrics (val_accuracy, val_loss, etc.)

#### 7. Verify FR Training Results

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

echo "=== FR Training Results ==="
curl -s "http://localhost:$API_PORT/api/v1/operations/$FR_TASK_ID" | jq '{
  status: .data.status,
  result_summary: .data.result_summary
}'
```

**Expected:**
- `status: "completed"`
- `result_summary` contains training metrics

#### 8. Verify TB Model Files and Architecture

**Command:**
```bash
TB_MODEL_DIR=$(ls -td ~/.ktrdr/shared/models/trend_tb_signal_v1/1h_v*/ 2>/dev/null | head -1)
if [ -z "$TB_MODEL_DIR" ]; then
  TB_MODEL_DIR="$HOME/.ktrdr/shared/models/trend_tb_signal_v1/1h_latest"
fi
echo "TB model dir: $TB_MODEL_DIR"

echo "=== Files ==="
ls -la "$TB_MODEL_DIR/"

echo "=== Metadata ==="
cat "$TB_MODEL_DIR/metadata_v3.json" | jq '{
  output_type: .output_type,
  model_name: .model_name,
  resolved_features: (.resolved_features | length),
  training_metrics: .training_metrics
}'

echo "=== Architecture (3-class output check) ==="
uv run python -c "
import torch
sd = torch.load('$TB_MODEL_DIR/model.pt', map_location='cpu', weights_only=True)
final = [k for k in sd if 'weight' in k][-1]
out_dim = sd[final].shape[0]
print(f'output_dim={out_dim}')
assert out_dim == 3, f'FAIL: TB model output_dim={out_dim}, expected 3'
print('PASS: 3-class output confirmed (BUY/HOLD/SELL)')
"
```

**Expected:**
- `model.pt` exists and > 1KB
- `metadata_v3.json` has `output_type: "classification"`
- Output dimension is 3 (triple barrier = 3-class: BUY/HOLD/SELL)

#### 9. Verify TB Label Distribution from Logs

**Command:**
```bash
source .env.sandbox

echo "=== Triple Barrier Label Stats ==="
docker compose -f docker-compose.sandbox.yml logs backend --since 30m 2>/dev/null | \
  grep -iE "triple.barrier|TP=|SL=|Expiry=|mean_hold" | tail -10

echo ""
echo "=== CUSUM Filter Stats ==="
docker compose -f docker-compose.sandbox.yml logs backend --since 30m 2>/dev/null | \
  grep -iE "CUSUM|cusum" | tail -5

echo ""
echo "=== Focal Loss Evidence ==="
docker compose -f docker-compose.sandbox.yml logs --since 30m 2>/dev/null | \
  grep -iE "focal|FocalLoss" | tail -5

echo ""
echo "=== Purged CV Evidence ==="
docker compose -f docker-compose.sandbox.yml logs --since 30m 2>/dev/null | \
  grep -iE "purged|cross.valid|cv.fold|embargo" | tail -5

echo ""
echo "=== Sample Weights Evidence ==="
docker compose -f docker-compose.sandbox.yml logs --since 30m 2>/dev/null | \
  grep -iE "sample.weight|uniqueness" | tail -5
```

**Expected:**
- Label stats: All 3 classes present (TP, SL, Expiry). No single class > 65%
- CUSUM: Evidence of filtering (if enabled in pipeline for non-zero threshold)
- Focal loss: Evidence that FocalLoss was instantiated
- Purged CV: Evidence of purged cross-validation folds (new M3 feature)
- Sample weights: Evidence of uniqueness-based sample weighting (if `compute_weights: true`)

#### 10. Verify FR Model Files

**Command:**
```bash
FR_MODEL_DIR=$(ls -td ~/.ktrdr/shared/models/trend_regression_signal/1h_v*/ 2>/dev/null | head -1)
if [ -z "$FR_MODEL_DIR" ]; then
  FR_MODEL_DIR="$HOME/.ktrdr/shared/models/trend_regression_signal/1h_latest"
fi
echo "FR model dir: $FR_MODEL_DIR"

echo "=== Files ==="
ls -la "$FR_MODEL_DIR/"

echo "=== Metadata ==="
cat "$FR_MODEL_DIR/metadata_v3.json" | jq '{
  output_type: .output_type,
  model_name: .model_name,
  resolved_features: (.resolved_features | length),
  training_metrics: .training_metrics
}'

echo "=== Architecture (1-output regression check) ==="
uv run python -c "
import torch
sd = torch.load('$FR_MODEL_DIR/model.pt', map_location='cpu', weights_only=True)
final = [k for k in sd if 'weight' in k][-1]
out_dim = sd[final].shape[0]
print(f'output_dim={out_dim}')
assert out_dim == 1, f'FAIL: FR model output_dim={out_dim}, expected 1'
print('PASS: 1-output regression confirmed')
"
```

**Expected:**
- `model.pt` exists and > 1KB
- `metadata_v3.json` has `output_type: "regression"`
- Output dimension is 1 (single regression output)

### Phase B: Backtest Both Models on 2024 Data

#### 11. Start TB Backtest

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

TB_MODEL_DIR=$(ls -td ~/.ktrdr/shared/models/trend_tb_signal_v1/1h_v*/ 2>/dev/null | head -1)
# Extract relative model path (from ~/.ktrdr/shared/)
TB_MODEL_PATH=$(echo "$TB_MODEL_DIR" | sed "s|$HOME/.ktrdr/shared/||")

TB_BT_RESPONSE=$(curl -s -X POST "http://localhost:$API_PORT/api/v1/backtests/start" \
  -H "Content-Type: application/json" \
  -d "{
    \"model_path\": \"$TB_MODEL_PATH\",
    \"strategy_name\": \"trend_tb_signal_v1\",
    \"symbol\": \"EURUSD\",
    \"timeframe\": \"1h\",
    \"start_date\": \"2024-01-01\",
    \"end_date\": \"2025-01-01\"
  }")

echo "TB Backtest Response: $TB_BT_RESPONSE"
TB_BT_ID=$(echo "$TB_BT_RESPONSE" | jq -r '.operation_id')
echo "TB Backtest ID: $TB_BT_ID"
```

**Expected:**
- HTTP 200 with `operation_id`

#### 12. Start FR Backtest

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

FR_MODEL_DIR=$(ls -td ~/.ktrdr/shared/models/trend_regression_signal/1h_v*/ 2>/dev/null | head -1)
FR_MODEL_PATH=$(echo "$FR_MODEL_DIR" | sed "s|$HOME/.ktrdr/shared/||")

FR_BT_RESPONSE=$(curl -s -X POST "http://localhost:$API_PORT/api/v1/backtests/start" \
  -H "Content-Type: application/json" \
  -d "{
    \"model_path\": \"$FR_MODEL_PATH\",
    \"strategy_name\": \"trend_regression_signal\",
    \"symbol\": \"EURUSD\",
    \"timeframe\": \"1h\",
    \"start_date\": \"2024-01-01\",
    \"end_date\": \"2025-01-01\"
  }")

echo "FR Backtest Response: $FR_BT_RESPONSE"
FR_BT_ID=$(echo "$FR_BT_RESPONSE" | jq -r '.operation_id')
echo "FR Backtest ID: $FR_BT_ID"
```

**Expected:**
- HTTP 200 with `operation_id`

#### 13. Wait for Both Backtests to Complete

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

TB_BT_DONE=false
FR_BT_DONE=false

for i in $(seq 1 30); do
  sleep 15

  if [ "$TB_BT_DONE" = "false" ]; then
    TB_BT_STATUS=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$TB_BT_ID" | jq -r '.data.status')
    echo "Poll $i: TB_BT=$TB_BT_STATUS"
    if [ "$TB_BT_STATUS" = "completed" ] || [ "$TB_BT_STATUS" = "failed" ]; then
      TB_BT_DONE=true
    fi
  fi

  if [ "$FR_BT_DONE" = "false" ]; then
    FR_BT_STATUS=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$FR_BT_ID" | jq -r '.data.status')
    echo "Poll $i: FR_BT=$FR_BT_STATUS"
    if [ "$FR_BT_STATUS" = "completed" ] || [ "$FR_BT_STATUS" = "failed" ]; then
      FR_BT_DONE=true
    fi
  fi

  if [ "$TB_BT_DONE" = "true" ] && [ "$FR_BT_DONE" = "true" ]; then
    echo "Both backtests finished"
    break
  fi
done

echo ""
echo "=== Final Backtest Status ==="
echo "TB: $TB_BT_STATUS"
echo "FR: $FR_BT_STATUS"
```

**Expected:**
- Both reach `status: "completed"`
- Total wait < 8 minutes

### Phase C: Compare Results

#### 14. Extract and Compare Backtest Results

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

echo "============================================"
echo "  EXPERIMENT 1: TB vs Forward Return"
echo "============================================"
echo ""

echo "=== TB Model (Triple Barrier + Focal Loss) ==="
TB_RESULTS=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$TB_BT_ID")
echo "$TB_RESULTS" | jq '{
  status: .data.status,
  total_return: .data.result_summary.total_return,
  sharpe_ratio: .data.result_summary.sharpe_ratio,
  max_drawdown: .data.result_summary.max_drawdown,
  win_rate: .data.result_summary.win_rate,
  total_trades: .data.result_summary.total_trades,
  profit_factor: .data.result_summary.profit_factor
}'

echo ""
echo "=== FR Model (Forward Return + Huber Loss) ==="
FR_RESULTS=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$FR_BT_ID")
echo "$FR_RESULTS" | jq '{
  status: .data.status,
  total_return: .data.result_summary.total_return,
  sharpe_ratio: .data.result_summary.sharpe_ratio,
  max_drawdown: .data.result_summary.max_drawdown,
  win_rate: .data.result_summary.win_rate,
  total_trades: .data.result_summary.total_trades,
  profit_factor: .data.result_summary.profit_factor
}'

echo ""
echo "=== Side-by-Side Comparison ==="
uv run python -c "
import json, sys

tb = json.loads('''$(echo "$TB_RESULTS")''')
fr = json.loads('''$(echo "$FR_RESULTS")''')

tb_r = tb.get('data', {}).get('result_summary', {})
fr_r = fr.get('data', {}).get('result_summary', {})

def safe_get(d, k):
    v = d.get(k)
    return v if v is not None else 'N/A'

metrics = ['total_return', 'sharpe_ratio', 'max_drawdown', 'win_rate', 'total_trades', 'profit_factor']
print(f'{\"Metric\":<20} {\"TB (class)\":<15} {\"FR (regress)\":<15} {\"Winner\":<10}')
print('-' * 60)

for m in metrics:
    tb_v = safe_get(tb_r, m)
    fr_v = safe_get(fr_r, m)

    winner = ''
    if isinstance(tb_v, (int, float)) and isinstance(fr_v, (int, float)):
        if m == 'max_drawdown':
            winner = 'TB' if abs(tb_v) < abs(fr_v) else 'FR'
        elif m == 'total_trades':
            winner = '-'  # more trades is not necessarily better
        else:
            winner = 'TB' if tb_v > fr_v else 'FR'

    tb_str = f'{tb_v:.4f}' if isinstance(tb_v, float) else str(tb_v)
    fr_str = f'{fr_v:.4f}' if isinstance(fr_v, float) else str(fr_v)
    print(f'{m:<20} {tb_str:<15} {fr_str:<15} {winner:<10}')

# Signal diversity check
tb_trades = tb_r.get('total_trades', 0) or 0
fr_trades = fr_r.get('total_trades', 0) or 0
print()
print(f'Trade ratio (TB/FR): {tb_trades/fr_trades:.2f}x' if fr_trades > 0 else 'FR has 0 trades')
"
```

**Expected:**
- Both models produce non-trivial backtest results
- Comparison table shows relative strengths
- This is INFORMATIONAL -- we do not assert TB > FR on every metric

#### 15. Verify TB Training Metrics (val_accuracy Target)

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

echo "=== TB Training Metrics ==="
TB_TRAIN=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$TB_TASK_ID")
echo "$TB_TRAIN" | jq '{
  val_accuracy: .data.result_summary.training_metrics.final_val_accuracy,
  val_loss: .data.result_summary.training_metrics.final_val_loss,
  test_accuracy: .data.result_summary.test_metrics.test_accuracy,
  epochs_completed: .data.result_summary.training_metrics.epochs_completed,
  training_time: .data.result_summary.training_metrics.training_time
}'

# Check val_accuracy target
uv run python -c "
import json
result = json.loads('''$(echo "$TB_TRAIN")''')
metrics = result.get('data', {}).get('result_summary', {})

# Training metrics may be nested differently -- check both paths
train_m = metrics.get('training_metrics', {})
test_m = metrics.get('test_metrics', {})

val_acc = train_m.get('final_val_accuracy')
test_acc = test_m.get('test_accuracy')

print(f'val_accuracy: {val_acc}')
print(f'test_accuracy: {test_acc}')

if val_acc is not None:
    if val_acc > 0.55:
        print(f'TARGET MET: val_accuracy {val_acc:.4f} > 0.55')
    elif val_acc > 0.45:
        print(f'MARGINAL: val_accuracy {val_acc:.4f} between 0.45-0.55 (3-class random=0.33)')
    else:
        print(f'BELOW TARGET: val_accuracy {val_acc:.4f} < 0.45')
else:
    print('WARNING: val_accuracy not found in training metrics')
"
```

**Expected:**
- `val_accuracy > 0.45` (above random chance of 0.33 for 3-class)
- Aspirational target: `val_accuracy > 0.55`

---

## Success Criteria

### Hard Requirements (must all pass)

- [ ] TB strategy accepted by training pipeline without validation errors
- [ ] TB training completes with status `"completed"`
- [ ] FR training completes with status `"completed"`
- [ ] TB model has 3-class output architecture (BUY/HOLD/SELL)
- [ ] FR model has 1-output regression architecture
- [ ] TB `metadata_v3.json` has `output_type: "classification"`
- [ ] FR `metadata_v3.json` has `output_type: "regression"`
- [ ] TB backtest completes with status `"completed"`
- [ ] FR backtest completes with status `"completed"`
- [ ] TB backtest produces `total_trades > 0`
- [ ] FR backtest produces `total_trades > 0`

### Soft Targets (informational, not pass/fail)

- [ ] TB `val_accuracy > 0.55` (above random=0.33, aspirational target)
- [ ] TB backtest `sharpe_ratio > 0.3`
- [ ] TB backtest produces diverse signals (not all BUY or all SELL)
- [ ] Label distribution: no single class > 65% (TP, SL, Expiry)
- [ ] Log evidence of focal loss, purged CV, and sample weights (M1-M3 features exercised)
- [ ] TB backtest `total_trades > 10` (model is not degenerate single-signal)

### Comparison Metrics (capture, do not assert winner)

- [ ] Total return: TB vs FR
- [ ] Sharpe ratio: TB vs FR
- [ ] Max drawdown: TB vs FR
- [ ] Win rate: TB vs FR
- [ ] Trade count: TB vs FR

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Both trainings have status "completed", not "failed"** -- A failed training produces empty results. All subsequent metric checks vacuously pass on null/empty data.
- [ ] **TB model has 3 output neurons, FR model has 1** -- If both have the same output dim, the wrong label source was used. This would mean the pipeline ignored the `source: triple_barrier` config.
- [ ] **TB model.pt > 1KB** -- Under 1KB suggests empty or corrupted model save.
- [ ] **TB val_accuracy between 0.25 and 0.90** -- On a 3-class problem, < 25% is worse than random guessing (broken model). > 90% on 4 years of 1h forex is suspicious and indicates data leakage or model collapse to majority class.
- [ ] **TB total_trades > 0 in backtest** -- If 0 trades, the classification-to-signal mapping may be broken (model predicts HOLD for everything, or confidence_threshold too high).
- [ ] **FR total_trades > 0 in backtest** -- Same check for baseline. If 0 trades, the trade_threshold may be too high for the predicted return magnitudes.
- [ ] **Both backtests processed > 1000 bars** -- 2024 1h data should have ~6,500 bars. Under 1000 means data was not loaded or processing terminated early.
- [ ] **TB and FR sharpe/return are not identical** -- If both models produce identical results, something is wrong (e.g., both using the same model file, or both ignoring model predictions and using a default signal).
- [ ] **TB backtest has trades in multiple directions** -- If all trades are BUY or all are SELL, the model collapsed to a single class prediction. This invalidates the comparison.

**Sanity check command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

echo "=== Training Sanity ==="
TB_STATUS=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$TB_TASK_ID" | jq -r '.data.status')
FR_STATUS=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$FR_TASK_ID" | jq -r '.data.status')
echo "TB training: $TB_STATUS"
echo "FR training: $FR_STATUS"
test "$TB_STATUS" = "completed" && echo "PASS" || echo "FAIL: TB training not completed"
test "$FR_STATUS" = "completed" && echo "PASS" || echo "FAIL: FR training not completed"

echo ""
echo "=== Model Sanity ==="
TB_MODEL_DIR=$(ls -td ~/.ktrdr/shared/models/trend_tb_signal_v1/1h_v*/ 2>/dev/null | head -1)
FR_MODEL_DIR=$(ls -td ~/.ktrdr/shared/models/trend_regression_signal/1h_v*/ 2>/dev/null | head -1)

TB_SIZE=$(stat -f%z "$TB_MODEL_DIR/model.pt" 2>/dev/null || stat -c%s "$TB_MODEL_DIR/model.pt" 2>/dev/null)
FR_SIZE=$(stat -f%z "$FR_MODEL_DIR/model.pt" 2>/dev/null || stat -c%s "$FR_MODEL_DIR/model.pt" 2>/dev/null)
echo "TB model.pt: $TB_SIZE bytes"
echo "FR model.pt: $FR_SIZE bytes"
test "$TB_SIZE" -gt 1024 && echo "PASS: TB > 1KB" || echo "FAIL: TB model suspiciously small"
test "$FR_SIZE" -gt 1024 && echo "PASS: FR > 1KB" || echo "FAIL: FR model suspiciously small"

echo ""
echo "=== Architecture Sanity ==="
uv run python -c "
import torch
tb_sd = torch.load('$TB_MODEL_DIR/model.pt', map_location='cpu', weights_only=True)
fr_sd = torch.load('$FR_MODEL_DIR/model.pt', map_location='cpu', weights_only=True)

tb_final = [k for k in tb_sd if 'weight' in k][-1]
fr_final = [k for k in fr_sd if 'weight' in k][-1]

tb_out = tb_sd[tb_final].shape[0]
fr_out = fr_sd[fr_final].shape[0]

print(f'TB output_dim={tb_out}, FR output_dim={fr_out}')
assert tb_out == 3, f'FAIL: TB output_dim={tb_out}, expected 3'
assert fr_out == 1, f'FAIL: FR output_dim={fr_out}, expected 1'
assert tb_out != fr_out, 'FAIL: Both models have same output dim -- wrong label source?'
print('PASS: TB=3-class, FR=1-regression')
"

echo ""
echo "=== Backtest Sanity ==="
TB_BT_STATUS=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$TB_BT_ID" | jq -r '.data.status')
FR_BT_STATUS=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$FR_BT_ID" | jq -r '.data.status')
echo "TB backtest: $TB_BT_STATUS"
echo "FR backtest: $FR_BT_STATUS"

TB_TRADES=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$TB_BT_ID" | jq -r '.data.result_summary.total_trades // 0')
FR_TRADES=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$FR_BT_ID" | jq -r '.data.result_summary.total_trades // 0')
echo "TB trades: $TB_TRADES"
echo "FR trades: $FR_TRADES"
test "$TB_TRADES" -gt 0 && echo "PASS: TB has trades" || echo "FAIL: TB has 0 trades"
test "$FR_TRADES" -gt 0 && echo "PASS: FR has trades" || echo "FAIL: FR has 0 trades"

TB_SHARPE=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$TB_BT_ID" | jq -r '.data.result_summary.sharpe_ratio // "null"')
FR_SHARPE=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$FR_BT_ID" | jq -r '.data.result_summary.sharpe_ratio // "null"')
echo "TB sharpe: $TB_SHARPE"
echo "FR sharpe: $FR_SHARPE"
test "$TB_SHARPE" != "$FR_SHARPE" && echo "PASS: Different results (not identical)" || echo "WARNING: Identical sharpe -- investigate"
```

---

## Troubleshooting

**If TB training fails with "Unknown label source 'triple_barrier'":**
- **Cause:** Training pipeline does not have the `source == "triple_barrier"` branch
- **Category:** CODE_BUG
- **Cure:** Check `training_pipeline.py` for the triple_barrier handling block. This is M1 code -- verify it was merged to the current branch.

**If TB training fails with "Unknown loss type: focal":**
- **Cause:** ModelTrainer focal loss support not integrated, or orchestrator not passing `loss` config for classification
- **Category:** CODE_BUG
- **Cure:** Check the known wiring bug: `local_orchestrator.py` may only inject `loss`/`focal_gamma` for regression models. See focal-loss-classification test for details.

**If FR training fails with strategy not found:**
- **Cause:** `trend_regression_signal_v1.yaml` not in `~/.ktrdr/shared/strategies/`
- **Category:** ENVIRONMENT
- **Cure:** The FR strategy must be manually placed in the shared strategies directory. It is not in the repo `strategies/` folder.

**If TB backtest has 0 trades:**
- **Cause:** Classification model predicts HOLD for everything (class imbalance collapse), or `confidence_threshold: 0.5` is too high for the model's softmax outputs
- **Category:** CODE_BUG or TUNING
- **Cure:** Check model predictions distribution. If all predictions are HOLD, the model may need more training data or lower confidence threshold. Inspect via: `docker compose -f docker-compose.sandbox.yml logs --since 15m 2>/dev/null | grep -i "signal\|trade\|predict" | tail -20`

**If FR backtest has 0 trades:**
- **Cause:** Regression model predictions too small to exceed `trade_threshold` (implicit from cost_model)
- **Category:** TUNING
- **Cure:** The trade_threshold is derived from `round_trip_cost * min_edge_multiplier = 0.0002 * 2.0 = 0.0004`. If predicted returns are consistently < 0.04%, the model learned to be conservative. This is a valid outcome but makes comparison impossible.

**If both models produce identical backtest results:**
- **Cause:** Both using same model file, or backtesting ignoring model predictions
- **Category:** CODE_BUG
- **Cure:** Verify model paths are different. Check that backtest loads the correct model via logs.

**If TB val_accuracy < 0.33 (below random):**
- **Cause:** Model failed to learn. Possible reasons: label imbalance (one class > 80%), learning rate too high/low, gradient clipping too aggressive, or features not informative for this label type
- **Category:** TUNING
- **Cure:** Check label distribution first. If one class dominates, the model may learn to predict that class exclusively. Consider adjusting barrier multipliers or using class-weighted focal loss.

**If training times out (> 25 minutes):**
- **Cause:** 200 epochs on ~26,000 bars with [64,32] MLP should take < 15 minutes. Cold start, worker contention, or data loading issues.
- **Category:** ENVIRONMENT
- **Cure:** Check workers: `curl http://localhost:$API_PORT/api/v1/workers | jq`. Check if early stopping should have triggered sooner.

---

## Evidence to Capture

### Training Evidence
- TB Training Operation ID: `$TB_TASK_ID`
- FR Training Operation ID: `$FR_TASK_ID`
- TB final status + result_summary
- FR final status + result_summary
- TB label distribution log line (triple barrier stats)
- TB focal loss / purged CV / sample weights log evidence
- TB model directory path and metadata_v3.json contents
- FR model directory path and metadata_v3.json contents

### Backtest Evidence
- TB Backtest Operation ID: `$TB_BT_ID`
- FR Backtest Operation ID: `$FR_BT_ID`
- TB backtest result_summary (total_return, sharpe, drawdown, win_rate, trades)
- FR backtest result_summary (same metrics)

### Comparison Evidence
- Side-by-side comparison table (Step 14 output)
- Trade ratio (TB trades / FR trades)
- Winner per metric

---

## Notes

- **Port variable:** Read from `.env.sandbox` as `KTRDR_API_PORT` (slot 1 = port 8001).
- **This is a comparison test, not an assertion test:** The primary goal is to produce a valid comparison. We assert that both models train and backtest successfully, but we do NOT assert that TB beats FR on any specific metric. The comparison data informs the next design iteration.
- **Different training periods:** TB trains on 2020-2024 (4 years), FR trains on 2019-2024 (5 years). The FR strategy has `start_date: "2019-01-01"` hardcoded. This is a minor difference that slightly favors FR (more training data). For a stricter comparison, both could use 2020-2024, but using the strategies as-designed is more realistic.
- **TB is classification, FR is regression:** Direct metric comparison (e.g., val_accuracy vs val_loss) is not meaningful across model types. Comparison must be on backtest outcomes (returns, sharpe, trades) which are comparable regardless of model type.
- **Parallel training:** With 2 training workers, both models can train simultaneously. With 1 worker, the second training queues. The polling loop handles both cases.
- **Model path for backtest:** The backtest API expects a relative model path (relative to `~/.ktrdr/shared/`). The script extracts this from the absolute model directory path.
- **TB strategy location:** The TB strategy lives in `strategies/` in the repo and must be copied to `~/.ktrdr/shared/strategies/` for the API to find it.
- **FR strategy location:** The FR strategy is ONLY in `~/.ktrdr/shared/strategies/` (not in the repo `strategies/` folder). It was placed there as the baseline.
- **M3 features exercised:** This test is specifically designed to exercise all M3 integration: purged cross-validation (via strategy config), sample weights (via `compute_weights: true`), and the full pipeline from triple barrier labels through focal loss training to backtest. Evidence of these features should appear in backend logs.
- **Early stopping:** TB strategy has `patience: 15` and 200 max epochs. With 4 years of data, training may stop well before 200 epochs. This is expected and desirable -- it means the model converged.
- **Metadata file is metadata_v3.json:** Not `metadata.json`. The v3 pipeline saves to `metadata_v3.json`.
- **Strategy name vs filename:** The API uses the `name` field inside the YAML (e.g., `trend_tb_signal_v1`), not the filename. The filename convention is `{name}.yaml` but the match is on the internal name field.
