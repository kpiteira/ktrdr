# Test: training/fred-context-data

**Purpose:** Validate that a v3 strategy with FRED yield spread context_data trains successfully, fetches real FRED data, computes context-derived indicators, and saves context metadata in the model for backtest reproducibility
**Duration:** ~3 minutes (FRED fetch + training)
**Category:** Training (Context Data)

**Dependency:** None (self-contained: creates strategy, trains)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../../e2e-testing/preflight/common.md) -- Docker, sandbox, API health
- [training](../../../e2e-testing/preflight/training.md) -- Strategy, data, workers

**Test-specific checks:**
- [ ] FRED API key is configured: `env | grep -c KTRDR_FRED_API_KEY` returns 1 (do NOT display the key)
- [ ] Legacy fallback: also check `env | grep -c FRED_API_KEY` if KTRDR_ variant missing
- [ ] EURUSD 1h data available in cache
- [ ] At least one idle training worker
- [ ] Strategy file `fred_carry_e2e_v3.yaml` exists at `~/.ktrdr/shared/strategies/`

**FRED API key check:**
```bash
source .env.sandbox
# Verify key exists without displaying it
if [ -n "${KTRDR_FRED_API_KEY}" ] || [ -n "${FRED_API_KEY}" ]; then
  echo "OK: FRED API key configured"
else
  echo "FAIL: No FRED API key found. Register free at https://fred.stlouisfed.org/docs/api/api_key.html"
  echo "Set KTRDR_FRED_API_KEY in .env or .env.sandbox"
  exit 1
fi
```

---

## Test Data

### Strategy YAML

The test requires a minimal v3 strategy that uses FRED context_data. Create this file at `~/.ktrdr/shared/strategies/fred_carry_e2e_v3.yaml`:

```yaml
name: fred_carry_e2e
version: "3.0"
description: "E2E test: EURUSD with FRED yield spread context data"

training_data:
  symbols:
    mode: single
    symbol: EURUSD
  timeframes:
    mode: single
    timeframe: "1h"
  history_required: 200
  start_date: "2024-01-01"
  end_date: "2024-12-31"

context_data:
  - provider: fred
    series: [DGS2, IRLTLT01DEM156N]
    frequency: daily
    alignment: forward_fill

indicators:
  # Primary instrument indicators
  rsi_14:
    type: rsi
    period: 14

  ema_20:
    type: ema
    period: 20

  # Context: yield spread indicators
  yield_spread_rsi:
    type: rsi
    period: 14
    data_source: yield_spread_DGS2_IRLTLT01DEM156N

  yield_spread_ema:
    type: ema
    period: 20
    data_source: yield_spread_DGS2_IRLTLT01DEM156N

fuzzy_sets:
  rsi_momentum:
    indicator: rsi_14
    oversold: [0, 25, 40]
    neutral: [30, 50, 70]
    overbought: [60, 75, 100]

  yield_trend:
    indicator: yield_spread_rsi
    declining: [0, 25, 45]
    neutral: [35, 50, 65]
    rising: [55, 75, 100]

nn_inputs:
  - fuzzy_set: rsi_momentum
    timeframes: all

  - fuzzy_set: yield_trend
    timeframes: all

decisions:
  output_format: classification
  threshold: 0.6
```

**Why this data:**
- EURUSD 1h for 2024: ~6,500 samples, trains in ~30s
- DGS2 (US 2Y Treasury) + IRLTLT01DEM156N (Germany 10Y): standard carry trade proxy for EUR/USD
- Two yield spread indicators (RSI + EMA) to verify context data routing works with multiple indicators
- Two fuzzy sets: one on primary data, one on context data -- verifies the full pipeline end-to-end
- Classification output (not regression) to keep the test simpler and avoid cost_model dependencies

### Request Payload

```json
{
  "symbols": ["EURUSD"],
  "timeframes": ["1h"],
  "strategy_name": "fred_carry_e2e",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31"
}
```

---

## Execution Steps

### 1. Write Strategy File

**Command:**
```bash
source .env.sandbox

# Write the strategy YAML to shared strategies directory
cat > ~/.ktrdr/shared/strategies/fred_carry_e2e_v3.yaml << 'STRATEGY_EOF'
name: fred_carry_e2e
version: "3.0"
description: "E2E test: EURUSD with FRED yield spread context data"

training_data:
  symbols:
    mode: single
    symbol: EURUSD
  timeframes:
    mode: single
    timeframe: "1h"
  history_required: 200
  start_date: "2024-01-01"
  end_date: "2024-12-31"

context_data:
  - provider: fred
    series: [DGS2, IRLTLT01DEM156N]
    frequency: daily
    alignment: forward_fill

indicators:
  rsi_14:
    type: rsi
    period: 14
  ema_20:
    type: ema
    period: 20
  yield_spread_rsi:
    type: rsi
    period: 14
    data_source: yield_spread_DGS2_IRLTLT01DEM156N
  yield_spread_ema:
    type: ema
    period: 20
    data_source: yield_spread_DGS2_IRLTLT01DEM156N

fuzzy_sets:
  rsi_momentum:
    indicator: rsi_14
    oversold: [0, 25, 40]
    neutral: [30, 50, 70]
    overbought: [60, 75, 100]
  yield_trend:
    indicator: yield_spread_rsi
    declining: [0, 25, 45]
    neutral: [35, 50, 65]
    rising: [55, 75, 100]

nn_inputs:
  - fuzzy_set: rsi_momentum
    timeframes: all
  - fuzzy_set: yield_trend
    timeframes: all

decisions:
  output_format: classification
  threshold: 0.6
STRATEGY_EOF

echo "Strategy written"
ls -la ~/.ktrdr/shared/strategies/fred_carry_e2e_v3.yaml
```

**Expected:**
- File exists at shared strategies location

### 2. Start Training via API

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

RESPONSE=$(curl -s -X POST http://localhost:$API_PORT/api/v1/trainings/start \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["EURUSD"],
    "timeframes": ["1h"],
    "strategy_name": "fred_carry_e2e",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  }')

echo "Training Response: $RESPONSE"

TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id')
echo "Task ID: $TASK_ID"
```

**Expected:**
- HTTP 200
- `success: true`
- `task_id` returned (non-null, non-empty)

### 3. Wait for Training Completion

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Poll every 15s for up to 5 minutes
# FRED fetch may add 10-20s to cold start, plus training ~30s
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
- `samples` > 5000 (1 year of 1h data should yield ~6,500)
- Total wait < 5 minutes

### 4. Verify Model Metadata Contains context_data_config

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Find the model directory
MODEL_DIR=$(ls -td ~/.ktrdr/shared/models/fred_carry_e2e/1h_v*/ 2>/dev/null | head -1)
if [ -z "$MODEL_DIR" ]; then
  MODEL_DIR="$HOME/.ktrdr/shared/models/fred_carry_e2e/1h_latest"
fi

echo "Model directory: $MODEL_DIR"

# Read metadata.json
echo "=== metadata.json ==="
cat "$MODEL_DIR/metadata.json" | jq .

# Extract context_data_config
echo "=== context_data_config ==="
cat "$MODEL_DIR/metadata.json" | jq '.context_data_config'

# Extract context_source_ids
echo "=== context_source_ids ==="
cat "$MODEL_DIR/metadata.json" | jq '.context_source_ids'
```

**Expected:**
- `metadata.json` exists in model directory
- `context_data_config` is a non-null, non-empty array
- `context_data_config[0].provider` is `"fred"`
- `context_data_config[0].series` contains `"DGS2"` and `"IRLTLT01DEM156N"`
- `context_source_ids` is a non-empty array containing at least `"yield_spread_DGS2_IRLTLT01DEM156N"`

### 5. Verify Feature Count Includes Context-Derived Features

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Check resolved features from model metadata
echo "=== resolved_features ==="
cat "$MODEL_DIR/metadata.json" | jq '.resolved_features'

FEATURE_COUNT=$(cat "$MODEL_DIR/metadata.json" | jq '.resolved_features | length')
echo "Total feature count: $FEATURE_COUNT"

# Check for yield_trend fuzzy set features (context-derived)
echo "=== Context-derived features (yield_trend) ==="
cat "$MODEL_DIR/metadata.json" | jq '[.resolved_features[] | select(contains("yield_trend"))]'

CONTEXT_FEATURE_COUNT=$(cat "$MODEL_DIR/metadata.json" | jq '[.resolved_features[] | select(contains("yield_trend"))] | length')
echo "Context-derived feature count: $CONTEXT_FEATURE_COUNT"
```

**Expected:**
- `FEATURE_COUNT` >= 6 (3 rsi_momentum memberships + 3 yield_trend memberships)
- `CONTEXT_FEATURE_COUNT` >= 3 (declining, neutral, rising from yield_trend fuzzy set)
- Features containing "yield_trend" are present in the resolved_features list

### 6. Verify FRED Data Was Cached Locally

**Command:**
```bash
# Check FRED cache directory
CACHE_DIR="${KTRDR_FRED_CACHE_DIR:-data/context/fred}"
echo "Checking cache at: $CACHE_DIR"

# Check from host filesystem
ls -la ~/.ktrdr/shared/$CACHE_DIR/ 2>/dev/null || ls -la $CACHE_DIR/ 2>/dev/null || echo "Cache not found on host"

# Check inside container
CONTAINER=$(docker ps --filter "name=predictive" --format "{{.Names}}" | grep backend | head -1)
if [ -z "$CONTAINER" ]; then
  CONTAINER=$(docker ps --filter "name=slot" --format "{{.Names}}" | grep backend | head -1)
fi
echo "Container: $CONTAINER"

if [ -n "$CONTAINER" ]; then
  echo "=== FRED cache inside container ==="
  docker exec "$CONTAINER" sh -c "find /app/data/context/fred -type f 2>/dev/null || echo 'NO_CACHE_DIR'"
fi
```

**Expected:**
- Cache directory contains files for DGS2 and IRLTLT01DEM156N series
- At least CSV or metadata.json files present per series

### 7. Verify Training Metrics Are Valid

**Command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

curl -s "http://localhost:$API_PORT/api/v1/operations/$TASK_ID" | \
  jq '{
    test_accuracy: .data.result_summary.test_metrics.test_accuracy,
    val_accuracy: .data.result_summary.training_metrics.final_val_accuracy,
    val_loss: .data.result_summary.training_metrics.final_val_loss,
    training_time: .data.result_summary.training_metrics.training_time
  }'
```

**Expected:**
- `val_loss` > 0 (training happened, not collapsed)
- `training_time` > 0.1 (real training occurred)
- `test_accuracy` between 0.3 and 0.99 (not degenerate)

### 8. Check Backend Logs for Context Data Loading

**Command:**
```bash
source .env.sandbox

# Look for FRED-related log messages
docker compose -f docker-compose.sandbox.yml logs backend --since 10m 2>/dev/null | grep -i "fred\|context_data\|yield_spread\|DGS2" | tail -20
```

**Expected:**
- Log lines showing FRED data fetch or cache hit
- No errors related to context data loading
- Evidence of yield_spread computation

---

## Success Criteria

- [ ] Strategy with `context_data` (FRED provider) accepts and starts training (HTTP 200, task_id)
- [ ] Training completes with status `"completed"` within 5 minutes
- [ ] Model `metadata.json` contains non-null `context_data_config` with FRED provider
- [ ] Model `metadata.json` contains `context_source_ids` including `yield_spread_DGS2_IRLTLT01DEM156N`
- [ ] Resolved features include context-derived features (yield_trend fuzzy set memberships)
- [ ] Total feature count > feature count from primary indicators alone (context added features)
- [ ] FRED data cached locally (CSV files for DGS2 and IRLTLT01DEM156N)
- [ ] Training metrics are valid (not collapsed, not degenerate)
- [ ] No errors in backend logs related to FRED or context data

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Training status is "completed", not "failed"** -- A failed training may leave partial metadata that passes file-existence checks
- [ ] **context_data_config is not null/empty** -- If null, context data was silently skipped (backward compat codepath ran instead)
- [ ] **context_source_ids has length > 0** -- Empty list means providers ran but returned nothing
- [ ] **context_source_ids contains "yield_spread_..."** -- If only individual series IDs (fred_DGS2) but no spread, spread computation failed
- [ ] **Context feature count >= 3** -- yield_trend has 3 memberships (declining, neutral, rising). If 0, context indicators were not routed to IndicatorEngine
- [ ] **Total features > 3** -- If only 3 features, only primary indicators were computed (context skipped)
- [ ] **test_accuracy < 0.99** -- Near-perfect accuracy with yield spread features likely means data leakage or model collapse
- [ ] **training_time > 0.1s** -- Below 0.1s suggests cached result or skipped training
- [ ] **val_loss > 0.001** -- Near-zero loss indicates collapsed model

**Sanity check command:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

echo "=== Training Sanity ==="
curl -s "http://localhost:$API_PORT/api/v1/operations/$TASK_ID" | jq '{
  status: .data.status,
  val_loss: .data.result_summary.training_metrics.final_val_loss,
  training_time: .data.result_summary.training_metrics.training_time,
  test_accuracy: .data.result_summary.test_metrics.test_accuracy
}'

echo "=== Context Data Sanity ==="
MODEL_DIR=$(ls -td ~/.ktrdr/shared/models/fred_carry_e2e/1h_v*/ 2>/dev/null | head -1)
if [ -z "$MODEL_DIR" ]; then
  MODEL_DIR="$HOME/.ktrdr/shared/models/fred_carry_e2e/1h_latest"
fi

cat "$MODEL_DIR/metadata.json" | jq '{
  context_data_config_present: (.context_data_config != null),
  context_data_config_length: (.context_data_config | length),
  context_source_ids: .context_source_ids,
  context_source_ids_count: (.context_source_ids | length),
  total_features: (.resolved_features | length),
  context_features: ([.resolved_features[] | select(contains("yield_trend"))] | length)
}'
```

---

## Troubleshooting

**If training fails with "FRED API key not configured":**
- **Cause:** `KTRDR_FRED_API_KEY` not set in the sandbox environment
- **Category:** ENVIRONMENT
- **Cure:** Add `KTRDR_FRED_API_KEY=<your-key>` to `.env` or `.env.sandbox`. Register for free at https://fred.stlouisfed.org/docs/api/api_key.html

**If training fails with "unknown provider: fred":**
- **Cause:** FredDataProvider not registered in ContextDataProviderRegistry
- **Category:** CODE_BUG
- **Cure:** Check `ktrdr/data/context/__init__.py` registers `FredDataProvider` with the registry

**If training fails with "data_source yield_spread_DGS2_IRLTLT01DEM156N not found in context_data":**
- **Cause:** FRED fetch succeeded but spread was not computed, or source ID naming mismatch
- **Category:** CODE_BUG
- **Cure:** Check `FredDataProvider.get_source_ids()` returns `yield_spread_DGS2_IRLTLT01DEM156N` for multi-series config. Verify the key in the context_data dict passed to IndicatorEngine matches.

**If context_data_config is null in metadata:**
- **Cause:** `_save_v3_metadata()` does not serialize context_data_config, or training codepath skipped context loading
- **Category:** CODE_BUG
- **Cure:** Check both `local_orchestrator.py` and `training-host-service/orchestrator.py` pass context_data_config to ModelMetadata (DUAL DISPATCH -- both must be updated)

**If context features are 0 but training succeeds:**
- **Cause:** IndicatorEngine computed context indicators but FeatureResolver/FuzzyEngine did not include them in nn_inputs resolution
- **Category:** CODE_BUG
- **Cure:** Check that fuzzy_sets referencing context indicators (yield_spread_rsi) are resolved correctly. The fuzzy set references the indicator_id, not the data_source.

**If training times out (> 5 minutes):**
- **Cause:** FRED API slow/blocked, or training worker busy
- **Category:** ENVIRONMENT
- **Cure:** Check FRED connectivity: `curl -s "https://api.stlouisfed.org/fred/series?series_id=DGS2&api_key=$KTRDR_FRED_API_KEY&file_type=json" | jq '.seriess[0].title'`. Check workers: `curl http://localhost:$API_PORT/api/v1/workers | jq`

**If strategy validation fails:**
- **Cause:** data_source reference does not match any context_data entry's source IDs
- **Category:** TEST_ISSUE
- **Cure:** Verify the strategy YAML has correct data_source value. For FRED with series `[DGS2, IRLTLT01DEM156N]`, the spread source ID is `yield_spread_DGS2_IRLTLT01DEM156N`.

---

## Evidence to Capture

- Training Operation ID: `$TASK_ID`
- Final status: `curl ... | jq '.data.status'`
- Training metrics: `curl ... | jq '.data.result_summary.training_metrics'`
- Model directory path: `$MODEL_DIR`
- metadata.json contents: `cat $MODEL_DIR/metadata.json | jq .`
- context_data_config: `cat $MODEL_DIR/metadata.json | jq '.context_data_config'`
- context_source_ids: `cat $MODEL_DIR/metadata.json | jq '.context_source_ids'`
- resolved_features: `cat $MODEL_DIR/metadata.json | jq '.resolved_features'`
- FRED cache: `find data/context/fred -type f 2>/dev/null`
- Backend logs: `docker compose -f docker-compose.sandbox.yml logs backend --since 10m | grep -i "fred\|context\|yield"`

---

## Notes

- **FRED API is free but requires registration.** Key registration is instant at https://fred.stlouisfed.org/docs/api/api_key.html. Rate limit is 120 req/min.
- **DGS2** is US 2-Year Treasury Constant Maturity Rate (daily). **IRLTLT01DEM156N** is Germany Long-Term Government Bond Yield (daily, monthly frequency but FRED interpolates). The spread between these is a standard USD-EUR carry proxy.
- **data_source vs source:** The field on indicators is `data_source` (routes to context data), NOT `source` (which is an indicator parameter like `source: close` for RSI). This naming distinction is critical.
- **DUAL DISPATCH:** Context data loading exists in both `local_orchestrator.py` and `training-host-service/orchestrator.py`. If one is broken, the test will catch it (depending on which worker processes the request).
- **Port variable:** Read from `.env.sandbox` as `KTRDR_API_PORT`.
- **Container discovery:** Use `docker ps --filter "name=predictive" --format "{{.Names}}"` or `--filter "name=slot"` depending on sandbox slot naming.
- **Cache persistence:** FRED data is cached locally at `data/context/fred/`. Subsequent test runs will hit cache instead of API, which is expected and correct behavior.
