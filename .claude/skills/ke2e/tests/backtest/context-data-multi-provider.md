# Test: backtest/context-data-multi-provider

**Purpose:** Validate the full multi-provider context data pipeline: train a strategy using FRED + IB + CFTC context data, then backtest the trained model and verify context data is correctly loaded from model metadata, feature counts match, and real trades are produced.
**Duration:** ~8 minutes (FRED fetch + IB data load + CFTC fetch + training + backtest)
**Category:** Backtest (Multi-Provider Context Data)

**Dependency:** None (self-contained: uses committed strategy file, loads data, trains, backtests)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../../e2e-testing/preflight/common.md) -- Docker, sandbox, API health
- [training](../../../e2e-testing/preflight/training.md) -- Strategy, data, workers
- [backtest](../../../e2e-testing/preflight/backtest.md) -- Backtest workers

**Test-specific checks:**
- [ ] FRED API key is configured: `env | grep -c KTRDR_FRED_API_KEY` returns 1 (do NOT display the key)
- [ ] Legacy fallback: also check `env | grep -c FRED_API_KEY` if KTRDR_ variant missing
- [ ] Strategy file exists at `strategies/eurusd_carry_momentum_v1.yaml`
- [ ] Strategy has 3 context_data entries (FRED, IB, CFTC)
- [ ] EURUSD 1h data available in cache
- [ ] GBPUSD 1h data available in cache (IB cross-pair context)
- [ ] At least one idle training worker
- [ ] At least one idle backtest worker

**Pre-flight commands:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Verify FRED API key
if [ -n "${KTRDR_FRED_API_KEY}" ] || [ -n "${FRED_API_KEY}" ]; then
  echo "OK: FRED API key configured"
else
  echo "FAIL: No FRED API key found. Register free at https://fred.stlouisfed.org/docs/api/api_key.html"
  exit 1
fi

# Verify strategy file
test -f strategies/eurusd_carry_momentum_v1.yaml || {
  echo "FAIL: strategies/eurusd_carry_momentum_v1.yaml not found"
  exit 1
}

# Verify 3 context_data providers in strategy
PROVIDER_COUNT=$(grep -c "provider:" strategies/eurusd_carry_momentum_v1.yaml)
test "$PROVIDER_COUNT" -eq 3 || {
  echo "FAIL: Expected 3 context_data providers, found $PROVIDER_COUNT"
  exit 1
}

# Verify EURUSD and GBPUSD data (load if missing)
for SYMBOL in EURUSD GBPUSD; do
  if ! ls ~/.ktrdr/shared/data/${SYMBOL}_1h.csv 2>/dev/null && \
     ! ls data/${SYMBOL}_1h.csv 2>/dev/null; then
    echo "Loading $SYMBOL 1h data..."
    uv run ktrdr data load $SYMBOL --timeframe 1h --start-date 2023-01-01 --end-date 2025-01-01
  fi
done

# Verify API health
curl -sf "http://localhost:$API_PORT/api/v1/health" > /dev/null || {
  echo "FAIL: API not responding on port $API_PORT"
  exit 1
}

# Verify workers
TRAINING_WORKERS=$(curl -s "http://localhost:$API_PORT/api/v1/workers" | jq '[.workers[] | select(.type=="training")] | length')
BACKTEST_WORKERS=$(curl -s "http://localhost:$API_PORT/api/v1/workers" | jq '[.workers[] | select(.type=="backtest")] | length')
echo "Training workers: $TRAINING_WORKERS, Backtest workers: $BACKTEST_WORKERS"
test "$TRAINING_WORKERS" -ge 1 || { echo "FAIL: No training workers"; exit 1; }
test "$BACKTEST_WORKERS" -ge 1 || { echo "FAIL: No backtest workers"; exit 1; }

echo "All pre-flight checks passed"
```

---

## Test Data

**Strategy:** `strategies/eurusd_carry_momentum_v1.yaml` (committed to repo)

**Context data providers:**
| Provider  | Source                        | data_source key                     |
|-----------|-------------------------------|-------------------------------------|
| IB        | GBPUSD 1h cross-pair          | `GBPUSD`                            |
| FRED      | DGS2 + IRLTLT01DEM156N spread | `yield_spread_DGS2_IRLTLT01DEM156N` |
| CFTC COT  | EUR futures net positioning   | `cot_EUR_net_pct`                   |

**Indicators:**
| ID                 | Type | data_source                         |
|--------------------|------|-------------------------------------|
| rsi_14             | rsi  | (primary EURUSD)                    |
| gbp_rsi_14         | rsi  | GBPUSD                              |
| yield_spread_rsi   | rsi  | yield_spread_DGS2_IRLTLT01DEM156N   |
| cot_percentile_ema | ema  | cot_EUR_net_pct                     |

**Fuzzy sets and expected feature count:**
| Fuzzy Set        | Indicator          | Memberships                              | Count |
|------------------|--------------------|------------------------------------------|-------|
| rsi_momentum     | rsi_14             | oversold, neutral, overbought            | 3     |
| gbp_momentum     | gbp_rsi_14         | weak, strong                             | 2     |
| carry_direction  | yield_spread_rsi   | eur_strengthening, neutral, usd_strength | 3     |
| positioning      | cot_percentile_ema | crowded_short, neutral, crowded_long     | 3     |
| **Total**        |                    |                                          | **11**|

**Why this data:**
- 3 distinct provider types (IB, FRED, CFTC) exercise the full context data pipeline
- Each provider has a different alignment method and data frequency
- 11 features across 4 fuzzy sets cover both primary and all 3 context-derived indicators
- 1-year training period (2024-01-01 to 2025-01-01) provides sufficient data for training
- Single timeframe (1h) avoids the known multi-timeframe backtest bug

---

## Execution Steps

### Phase 1: Training

### 1. Copy Strategy to Shared Strategies Directory

**Command:**
```bash
source .env.sandbox
cp strategies/eurusd_carry_momentum_v1.yaml ~/.ktrdr/shared/strategies/
echo "Strategy copied to shared strategies"
ls -la ~/.ktrdr/shared/strategies/eurusd_carry_momentum_v1.yaml
```

**Expected:**
- File exists at shared strategies location

### 2. Start Training via CLI

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

RESPONSE=$(curl -s -X POST http://localhost:$API_PORT/api/v1/trainings/start \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["EURUSD"],
    "timeframes": ["1h"],
    "strategy_name": "eurusd_carry_momentum_v1",
    "start_date": "2024-01-01",
    "end_date": "2025-01-01"
  }')

echo "Training Response: $RESPONSE"

TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id')
echo "Task ID: $TASK_ID"
```

**Expected:**
- HTTP 200
- `task_id` returned (non-null, non-empty)

### 3. Wait for Training Completion

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Poll every 15s for up to 8 minutes
# FRED fetch + CFTC fetch + IB data + training can be slow on cold start
for i in $(seq 1 32); do
  sleep 15
  STATUS=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$TASK_ID" | jq -r '.data.status')
  echo "Poll $i: status=$STATUS"
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
done

TRAIN_RESULT=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$TASK_ID")
TRAIN_STATUS=$(echo "$TRAIN_RESULT" | jq -r '.data.status')
echo "Training final status: $TRAIN_STATUS"
```

**Expected:**
- `status: "completed"` (not "failed" or "running")
- Total wait < 8 minutes

### 4. Verify Training Succeeded (Gate Check)

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

TRAIN_RESULT=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$TASK_ID")
echo "$TRAIN_RESULT" | jq '{
  status: .data.status,
  training_time: .data.result_summary.training_metrics.training_time,
  val_loss: .data.result_summary.training_metrics.final_val_loss
}'

# HARD GATE: training must complete before proceeding to backtest
TRAIN_STATUS=$(echo "$TRAIN_RESULT" | jq -r '.data.status')
if [ "$TRAIN_STATUS" != "completed" ]; then
  echo "ABORT: Training did not complete (status=$TRAIN_STATUS). Cannot proceed to backtest."
  echo "Error details:"
  echo "$TRAIN_RESULT" | jq '.data.error // .data.result_summary.error // "no error detail"'
  exit 1
fi
```

**Expected:**
- Status is "completed"
- `training_time` > 0.1 (real training occurred)
- `val_loss` > 0.001 (not collapsed)

### Phase 2: Model Metadata Verification

### 5. Verify Model Metadata Contains All 3 Providers in context_data_config

**Command:**
```bash
source .env.sandbox

# Find the model directory
MODEL_DIR=$(ls -td ~/.ktrdr/shared/models/eurusd_carry_momentum_v1/1h_v*/ 2>/dev/null | head -1)
if [ -z "$MODEL_DIR" ]; then
  MODEL_DIR="$HOME/.ktrdr/shared/models/eurusd_carry_momentum_v1/1h_latest"
fi
echo "Model directory: $MODEL_DIR"

# Verify metadata.json exists
test -f "$MODEL_DIR/metadata.json" || {
  echo "FAIL: metadata.json not found at $MODEL_DIR"
  exit 1
}

# Extract context_data_config
echo "=== context_data_config ==="
cat "$MODEL_DIR/metadata.json" | jq '.context_data_config'

# Count providers
PROVIDER_COUNT=$(cat "$MODEL_DIR/metadata.json" | jq '.context_data_config | length')
echo "Provider count in metadata: $PROVIDER_COUNT"

# Verify each provider type is present
echo "=== Provider types ==="
cat "$MODEL_DIR/metadata.json" | jq '[.context_data_config[].provider] | sort'

IB_PRESENT=$(cat "$MODEL_DIR/metadata.json" | jq '[.context_data_config[] | select(.provider=="ib")] | length')
FRED_PRESENT=$(cat "$MODEL_DIR/metadata.json" | jq '[.context_data_config[] | select(.provider=="fred")] | length')
CFTC_PRESENT=$(cat "$MODEL_DIR/metadata.json" | jq '[.context_data_config[] | select(.provider=="cftc_cot")] | length')

echo "IB: $IB_PRESENT, FRED: $FRED_PRESENT, CFTC: $CFTC_PRESENT"
```

**Expected:**
- `metadata.json` exists
- `context_data_config` has exactly 3 entries
- All 3 provider types present: `ib`, `fred`, `cftc_cot`

### 6. Verify context_source_ids Contains All Source IDs

**Command:**
```bash
source .env.sandbox

echo "=== context_source_ids ==="
cat "$MODEL_DIR/metadata.json" | jq '.context_source_ids'

SOURCE_COUNT=$(cat "$MODEL_DIR/metadata.json" | jq '.context_source_ids | length')
echo "Source ID count: $SOURCE_COUNT"

# Verify specific source IDs
HAS_GBPUSD=$(cat "$MODEL_DIR/metadata.json" | jq '[.context_source_ids[] | select(contains("GBPUSD"))] | length')
HAS_YIELD=$(cat "$MODEL_DIR/metadata.json" | jq '[.context_source_ids[] | select(contains("yield_spread"))] | length')
HAS_COT=$(cat "$MODEL_DIR/metadata.json" | jq '[.context_source_ids[] | select(contains("cot_EUR"))] | length')

echo "GBPUSD source: $HAS_GBPUSD, yield_spread source: $HAS_YIELD, COT source: $HAS_COT"
```

**Expected:**
- `context_source_ids` is non-empty
- Contains at least: a GBPUSD-related ID, a yield_spread ID, and a cot_EUR ID
- `SOURCE_COUNT` >= 3

### 7. Verify Resolved Features Count Is 11

**Command:**
```bash
source .env.sandbox

echo "=== resolved_features ==="
cat "$MODEL_DIR/metadata.json" | jq '.resolved_features'

FEATURE_COUNT=$(cat "$MODEL_DIR/metadata.json" | jq '.resolved_features | length')
echo "Total resolved features: $FEATURE_COUNT"

# Break down by fuzzy set
echo "=== Feature breakdown ==="
RSI_FEATURES=$(cat "$MODEL_DIR/metadata.json" | jq '[.resolved_features[] | select(contains("rsi_momentum"))] | length')
GBP_FEATURES=$(cat "$MODEL_DIR/metadata.json" | jq '[.resolved_features[] | select(contains("gbp_momentum"))] | length')
CARRY_FEATURES=$(cat "$MODEL_DIR/metadata.json" | jq '[.resolved_features[] | select(contains("carry_direction"))] | length')
POS_FEATURES=$(cat "$MODEL_DIR/metadata.json" | jq '[.resolved_features[] | select(contains("positioning"))] | length')

echo "rsi_momentum: $RSI_FEATURES (expect 3)"
echo "gbp_momentum: $GBP_FEATURES (expect 2)"
echo "carry_direction: $CARRY_FEATURES (expect 3)"
echo "positioning: $POS_FEATURES (expect 3)"
echo "Sum: $(( RSI_FEATURES + GBP_FEATURES + CARRY_FEATURES + POS_FEATURES ))"
```

**Expected:**
- `FEATURE_COUNT` == 11
- `rsi_momentum`: 3 (oversold, neutral, overbought)
- `gbp_momentum`: 2 (weak, strong)
- `carry_direction`: 3 (eur_strengthening, neutral, usd_strengthening)
- `positioning`: 3 (crowded_short, neutral, crowded_long)

### Phase 3: Backtest

### 8. Start Backtest

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Use the model that was just trained
MODEL_PATH="models/eurusd_carry_momentum_v1/1h_latest"

RESPONSE=$(curl -s -X POST http://localhost:$API_PORT/api/v1/backtests/start \
  -H "Content-Type: application/json" \
  -d "{
    \"strategy_name\": \"eurusd_carry_momentum_v1\",
    \"symbol\": \"EURUSD\",
    \"timeframe\": \"1h\",
    \"start_date\": \"2024-01-01\",
    \"end_date\": \"2025-01-01\",
    \"model_path\": \"$MODEL_PATH\"
  }")

echo "Backtest Response: $RESPONSE"

BT_OP_ID=$(echo "$RESPONSE" | jq -r '.operation_id')
echo "Backtest Operation ID: $BT_OP_ID"
```

**Expected:**
- HTTP 200 with `operation_id` returned
- Operation created successfully

### 9. Wait for Backtest Completion

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Poll every 10s for up to 3 minutes
for i in $(seq 1 18); do
  sleep 10
  STATUS=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$BT_OP_ID" | jq -r '.data.status')
  echo "Poll $i: status=$STATUS"
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
done

BT_RESULT=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$BT_OP_ID")
BT_STATUS=$(echo "$BT_RESULT" | jq -r '.data.status')
echo "Backtest final status: $BT_STATUS"
```

**Expected:**
- `status: "completed"` within 3 minutes

### 10. Verify Backtest Loaded Context Data from Model Metadata

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

BT_RESULT=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$BT_OP_ID")

echo "=== Backtest Status ==="
echo "$BT_RESULT" | jq '.data.status'

echo "=== Backtest Config ==="
echo "$BT_RESULT" | jq '.data.result_summary.config'

echo "=== Backtest Feature Count ==="
BT_FEATURE_COUNT=$(echo "$BT_RESULT" | jq '.data.result_summary.feature_count // .data.metadata.feature_count // empty')
echo "Backtest feature count: $BT_FEATURE_COUNT"

# Also check logs for context data loading evidence
CONTAINER=$(docker ps --filter "name=slot-3" --format "{{.Names}}" | grep backend | head -1)
if [ -z "$CONTAINER" ]; then
  CONTAINER=$(docker ps --filter "name=predictive" --format "{{.Names}}" | grep backend | head -1)
fi
echo "Container: $CONTAINER"

if [ -n "$CONTAINER" ]; then
  echo "=== Backend logs: context data during backtest ==="
  docker logs "$CONTAINER" --since 5m 2>&1 | grep -i "context_data\|context data\|loaded.*context\|provider.*ib\|provider.*fred\|provider.*cftc" | tail -20
fi
```

**Expected:**
- Backtest status is "completed"
- Backend logs show evidence of context data loading during backtest
- If feature_count is exposed in results/metadata, it should match 11

### 11. Verify Backtest Feature Count Matches Training

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Get training feature count from model metadata
TRAIN_FEATURE_COUNT=$(cat "$MODEL_DIR/metadata.json" | jq '.resolved_features | length')

# Get backtest feature count (may be in result_summary or metadata)
BT_RESULT=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$BT_OP_ID")
BT_FEATURE_COUNT=$(echo "$BT_RESULT" | jq '.data.result_summary.feature_count // .data.result_summary.config.feature_count // empty')

echo "Training features: $TRAIN_FEATURE_COUNT"
echo "Backtest features: $BT_FEATURE_COUNT"

# If backtest feature count is not directly exposed, check via container logs
if [ -z "$BT_FEATURE_COUNT" ] || [ "$BT_FEATURE_COUNT" = "null" ]; then
  echo "NOTE: Backtest feature count not directly in API results."
  echo "Checking container logs for feature alignment evidence..."
  if [ -n "$CONTAINER" ]; then
    docker logs "$CONTAINER" --since 5m 2>&1 | grep -i "feature\|input.*shape\|nn_input" | tail -10
  fi
  echo "Primary evidence: backtest completed without feature mismatch error = features matched"
fi
```

**Expected:**
- If `BT_FEATURE_COUNT` is exposed: it equals `TRAIN_FEATURE_COUNT` (11)
- If not directly exposed: backtest completing without error is strong evidence of feature alignment (a mismatch would cause a tensor shape error and fail the backtest)

### 12. Verify Backtest Produced Trade Results

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

BT_RESULT=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$BT_OP_ID")

echo "=== Trade Results ==="
echo "$BT_RESULT" | jq '{
  status: .data.status,
  trade_count: .data.result_summary.trade_count,
  total_return: .data.result_summary.metrics.total_return,
  execution_time: .data.result_summary.execution_time_seconds,
  slippage: .data.result_summary.config.slippage,
  bar_count: .data.result_summary.bar_count
}'

TRADE_COUNT=$(echo "$BT_RESULT" | jq '.data.result_summary.trade_count')
EXEC_TIME=$(echo "$BT_RESULT" | jq '.data.result_summary.execution_time_seconds')
TOTAL_RETURN=$(echo "$BT_RESULT" | jq '.data.result_summary.metrics.total_return')

echo ""
echo "Trade count: $TRADE_COUNT"
echo "Execution time: $EXEC_TIME"
echo "Total return: $TOTAL_RETURN"
```

**Expected:**
- `trade_count` > 0 (strategy uses regression output with cost model, should produce some trades over 1 year)
- `execution_time_seconds` > 1 (real computation occurred on ~6500 bars)
- `total_return` is a finite number (not null, not NaN)

---

## Success Criteria

- [ ] Training completes with status `"completed"` using all 3 context data providers
- [ ] Model `metadata.json` contains `context_data_config` with exactly 3 entries (ib, fred, cftc_cot)
- [ ] Model `metadata.json` contains `context_source_ids` with entries for GBPUSD, yield_spread, and COT
- [ ] Model `metadata.json` has exactly 11 `resolved_features`
- [ ] Feature breakdown matches: rsi_momentum=3, gbp_momentum=2, carry_direction=3, positioning=3
- [ ] Backtest completes with status `"completed"`
- [ ] Backtest loaded context data from model metadata (no feature mismatch errors)
- [ ] Backtest produced trades (`trade_count` > 0)
- [ ] Backtest `execution_time_seconds` > 1 (real computation occurred)
- [ ] Backtest `total_return` is a finite number

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Training status is "completed", not "failed"** -- A failed training may leave partial metadata that passes file-existence checks. The training gate (Step 4) must pass before proceeding.
- [ ] **context_data_config has exactly 3 entries, not 1** -- If only FRED appears (the simplest provider), IB and CFTC providers may have failed silently and been skipped.
- [ ] **All 3 provider types are distinct** -- `jq '[.context_data_config[].provider] | unique | length'` must be 3. Duplicate providers would indicate config corruption.
- [ ] **context_source_ids contains entries from all 3 providers** -- If only 1-2 source IDs, some providers returned empty data. Check each: GBPUSD (IB), yield_spread (FRED), cot_EUR (CFTC).
- [ ] **Feature count is exactly 11, not 3 or 6** -- If 3, only primary RSI was resolved (context data not routed). If 6, only primary + one provider worked.
- [ ] **gbp_momentum has 2 features, not 3** -- This fuzzy set has only 2 memberships (weak, strong). If 3 appears, a membership was incorrectly generated.
- [ ] **Backtest status is "completed", not "failed"** -- A feature mismatch between training metadata and backtest data would cause a tensor shape error and fail the backtest. This is the key signal that context data was reproduced correctly.
- [ ] **trade_count > 0** -- With a regression output, cost model, and 1 year of data, zero trades would suggest the model is degenerate or the cost filter is too aggressive. Acceptable range: 5-500 trades.
- [ ] **execution_time > 1.0** -- Less than 1 second for 6500+ bars with context data loading suggests the engine short-circuited or returned cached results.
- [ ] **total_return is not exactly 0.0** -- Exactly zero (not a small number near zero) suggests no trades were actually executed, or the engine returned a default value.
- [ ] **training val_loss > 0.001** -- Near-zero loss indicates collapsed model. With Huber loss (delta=0.01), healthy training should produce val_loss in range [0.001, 0.01].

**Consolidated sanity command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

echo "=== Training Sanity ==="
curl -s "http://localhost:$API_PORT/api/v1/operations/$TASK_ID" | jq '{
  status: .data.status,
  val_loss: .data.result_summary.training_metrics.final_val_loss,
  training_time: .data.result_summary.training_metrics.training_time
}'

echo "=== Model Metadata Sanity ==="
cat "$MODEL_DIR/metadata.json" | jq '{
  context_config_count: (.context_data_config | length),
  provider_types: [.context_data_config[].provider] | sort,
  unique_providers: ([.context_data_config[].provider] | unique | length),
  source_id_count: (.context_source_ids | length),
  feature_count: (.resolved_features | length),
  has_gbp_source: ([.context_source_ids[] | select(contains("GBPUSD"))] | length > 0),
  has_yield_source: ([.context_source_ids[] | select(contains("yield_spread"))] | length > 0),
  has_cot_source: ([.context_source_ids[] | select(contains("cot_EUR"))] | length > 0)
}'

echo "=== Backtest Sanity ==="
curl -s "http://localhost:$API_PORT/api/v1/operations/$BT_OP_ID" | jq '{
  status: .data.status,
  trade_count: .data.result_summary.trade_count,
  total_return: .data.result_summary.metrics.total_return,
  execution_time: .data.result_summary.execution_time_seconds
}'
```

---

## Troubleshooting

**If training fails with "FRED API key not configured":**
- **Cause:** `KTRDR_FRED_API_KEY` not set in the sandbox environment
- **Category:** ENVIRONMENT
- **Cure:** Add `KTRDR_FRED_API_KEY=<key>` to `.env` or `.env.sandbox`. Register free at https://fred.stlouisfed.org/docs/api/api_key.html. Ensure the sandbox was started AFTER the key was added (secrets are injected at sandbox up time).

**If training fails with "unknown provider: cftc_cot":**
- **Cause:** CftcCotDataProvider not registered in ContextDataProviderRegistry
- **Category:** CODE_BUG
- **Cure:** Check `ktrdr/data/context/__init__.py` registers `CftcCotDataProvider`. Verify the provider name matches exactly: `cftc_cot`.

**If training fails with "unknown provider: ib":**
- **Cause:** IbDataProvider not registered, or IB cross-pair context not implemented
- **Category:** CODE_BUG
- **Cure:** Check `ktrdr/data/context/__init__.py` registers the IB context data provider. IB provider loads OHLCV from cache (not live IB Gateway), so no IB connection is needed.

**If training fails with "data_source GBPUSD not found in context_data":**
- **Cause:** IB provider returned data with a different key than the `data_source` expected by the indicator
- **Category:** CODE_BUG
- **Cure:** Verify that IB provider's `get_source_ids()` returns `["GBPUSD"]` and the context data dict uses `GBPUSD` as the key.

**If training fails with "data_source cot_EUR_net_pct not found in context_data":**
- **Cause:** CFTC COT provider uses a different source ID format than the indicator expects
- **Category:** CODE_BUG
- **Cure:** Check `CftcCotDataProvider.get_source_ids()` returns `["cot_EUR_net_pct"]`. The strategy indicator references this exact string.

**If context_data_config has < 3 entries in metadata:**
- **Cause:** One or more providers failed silently and were skipped, or `_save_v3_metadata()` does not serialize all providers
- **Category:** CODE_BUG
- **Cure:** Check training logs for warnings about provider failures. Check both `local_orchestrator.py` and `training-host-service/orchestrator.py` pass full context_data_config to ModelMetadata (DUAL DISPATCH).

**If feature count != 11:**
- **Cause:** Feature resolver or fuzzy engine did not process all context-derived fuzzy sets
- **Category:** CODE_BUG
- **Cure:** Check that all 4 fuzzy sets are resolved. Common failure: indicator with `data_source` not matched to context data, so the indicator returns NaN and the fuzzy set is dropped.

**If backtest fails with tensor shape mismatch:**
- **Cause:** Backtest did not load context data, so features computed during backtest have different count than model expects
- **Category:** CODE_BUG
- **Cure:** Check that backtest pipeline reads `context_data_config` from model metadata and loads all 3 providers before computing features.

**If backtest succeeds but trade_count is 0:**
- **Cause:** Model may be degenerate (all predictions near zero), or cost filter (`round_trip_cost: 0.003`, `min_edge_multiplier: 1.5`) is too aggressive
- **Category:** TEST_ISSUE (not necessarily a code bug)
- **Cure:** Check model predictions via logs. If model quality is the issue, this is a model quality problem, not a pipeline bug. The critical assertion is that the backtest completed (context data loaded successfully). Zero trades with valid execution_time > 1 still validates the pipeline.

**If training or backtest times out:**
- **Cause:** Cold start (FRED + CFTC fetch), worker busy, or large data processing
- **Category:** ENVIRONMENT
- **Cure:** Check workers: `curl http://localhost:$API_PORT/api/v1/workers | jq`. Check FRED connectivity. CFTC data comes from public CSV at `https://www.cftc.gov/` -- verify network access.

---

## Evidence to Capture

**Training phase:**
- Training Operation ID: `$TASK_ID`
- Training final status
- Training metrics: `curl ... | jq '.data.result_summary.training_metrics'`

**Model metadata:**
- Model directory path: `$MODEL_DIR`
- `context_data_config`: full JSON array with 3 provider entries
- `context_source_ids`: full list
- `resolved_features`: full list (should be 11 items)

**Backtest phase:**
- Backtest Operation ID: `$BT_OP_ID`
- Backtest final status
- Trade count, total return, execution time
- Backend logs showing context data loading during backtest

**Sanity check results:**
- Output of consolidated sanity command

---

## Notes

- **Port variable:** Read from `.env.sandbox` as `KTRDR_API_PORT`. This sandbox is slot 3, port 8003.
- **Container discovery:** Use `docker ps --filter "name=slot-3" --format "{{.Names}}"` for this sandbox.
- **CFTC data is public:** No API key needed. Data is fetched from public CFTC CSV endpoints. However, it requires network access.
- **IB provider uses cached data:** The IB context data provider loads GBPUSD OHLCV from the local cache (same as `ktrdr data load`), NOT from a live IB Gateway connection. GBPUSD data must be pre-cached.
- **FRED data is cached after first fetch:** Subsequent runs hit the local cache instead of the FRED API. First run may be slower by 10-20s.
- **Strategy uses regression output with cost model:** This means the backtest applies a cost-aware filter to predictions. Trade count depends on model quality -- the pipeline test is valid even with low trade counts, as long as backtest completed and loaded all context data.
- **Feature mismatch = backtest failure:** If context data is not loaded during backtest, the feature count will differ from training, causing a tensor dimension mismatch. A successful backtest completion is strong evidence that context data was reproduced correctly.
- **DUAL DISPATCH:** Context data loading exists in both `local_orchestrator.py` and `training-host-service/orchestrator.py`. Which path executes depends on which worker processes the request. The test validates whichever path runs.
- **This test is reusable:** Any future strategy using multi-provider context data can adapt this test pattern. The key verification points (metadata provider count, source IDs, feature count, backtest completion) apply generically.
