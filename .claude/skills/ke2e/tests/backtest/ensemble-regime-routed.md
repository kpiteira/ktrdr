# Test: backtest/ensemble-regime-routed

**Purpose:** Validate that regime-routed ensemble backtesting loads a regime classifier + per-regime signal models, routes bars through the RegimeRouter, produces trades, and returns per-regime performance metrics.
**Duration:** <120 seconds
**Category:** Backtest (Ensemble)

**Dependency:** Requires three trained models at known paths inside the container:
- `regime_classifier_seed/1h_latest` (regime classification gate)
- `mean_reversion_momentum_v1/1h_latest` (trend signal model)
- `bb_stochastic_mean_reversion_eurusd_1h_v1/1h_latest` (range signal model)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../../e2e-testing/preflight/common.md) -- Docker, sandbox, API health

**Test-specific checks:**
- [ ] Sandbox is running (`source .env.sandbox` succeeds, container is up)
- [ ] All three model bundles exist inside container at `/app/models/`
- [ ] EURUSD 1h OHLCV data is cached and available inside container at `/app/data/`
- [ ] Container has torch available (backtest runs locally inside container)

**Pre-flight commands:**
```bash
source .env.sandbox
CONTAINER="slot-1-backend-1"

# 1. Container is running
docker ps --filter "name=$CONTAINER" --format "{{.Names}}" | grep -q "$CONTAINER" || {
  echo "FAIL: Container $CONTAINER not running"
  exit 1
}

# 2. All three model bundles exist
for MODEL_DIR in \
  "/app/models/regime_classifier_seed/1h_latest" \
  "/app/models/mean_reversion_momentum_v1/1h_latest" \
  "/app/models/bb_stochastic_mean_reversion_eurusd_1h_v1/1h_latest"; do
  docker exec "$CONTAINER" test -f "$MODEL_DIR/model.pt" || {
    echo "FAIL: Model not found: $MODEL_DIR/model.pt"
    exit 1
  }
  docker exec "$CONTAINER" test -f "$MODEL_DIR/metadata_v3.json" || {
    echo "FAIL: Metadata not found: $MODEL_DIR/metadata_v3.json"
    exit 1
  }
  echo "OK: $MODEL_DIR"
done

# 3. Torch available
docker exec "$CONTAINER" python -c "import torch; print(f'torch {torch.__version__}')" || {
  echo "FAIL: torch not available in container"
  exit 1
}

# 4. EURUSD 1h data exists
docker exec "$CONTAINER" python -c "
from ktrdr.data.repository import DataRepository
repo = DataRepository()
df = repo.load_from_cache('EURUSD', '1h', '2024-01-01', '2024-06-01')
print(f'EURUSD 1h bars: {len(df)}')
assert len(df) > 100, f'Insufficient data: {len(df)} bars'
" || {
  echo "FAIL: EURUSD 1h data not available in container cache"
  exit 1
}

echo "All pre-flight checks passed"
```

---

## Test Data

The ensemble configuration is constructed inline as a Python dict inside the container because the `configs/` directory is not mounted. Model paths use container-internal `/app/models/` paths.

```python
ENSEMBLE_CONFIG = {
    "name": "regime_routed_v1",
    "description": "E2E test: regime-routed ensemble backtest",
    "models": {
        "regime": {
            "model_path": "/app/models/regime_classifier_seed/1h_latest",
            "output_type": "regime_classification",
        },
        "trend_signal": {
            "model_path": "/app/models/mean_reversion_momentum_v1/1h_latest",
            "output_type": "classification",
        },
        "range_signal": {
            "model_path": "/app/models/bb_stochastic_mean_reversion_eurusd_1h_v1/1h_latest",
            "output_type": "classification",
        },
    },
    "composition": {
        "type": "regime_route",
        "gate_model": "regime",
        "regime_threshold": 0.4,
        "stability_bars": 3,
        "rules": {
            "trending_up": {"model": "trend_signal"},
            "trending_down": {"model": "trend_signal"},
            "ranging": {"model": "range_signal"},
            "volatile": {"action": "FLAT"},
        },
        "on_regime_transition": "close_and_switch",
    },
}
```

**Why this data:**
- Uses the same three models that exist from prior training milestones
- EURUSD 1h 2024-01-01 to 2024-06-01 (~4300 bars) provides enough data for regime transitions
- `close_and_switch` transition policy exercises the position-closing-on-transition path
- `stability_bars: 3` is low enough to see transitions within the date range
- `volatile` regime maps to `FLAT` action, exercising the non-model route path

---

## Execution Steps

### 1. Load Ensemble Config and Verify Validation

**Command:**
```bash
source .env.sandbox
CONTAINER="slot-1-backend-1"

docker exec "$CONTAINER" python -c "
from ktrdr.config.ensemble_config import EnsembleConfiguration

config = EnsembleConfiguration.from_dict({
    'name': 'regime_routed_v1',
    'description': 'E2E test: regime-routed ensemble backtest',
    'models': {
        'regime': {
            'model_path': '/app/models/regime_classifier_seed/1h_latest',
            'output_type': 'regime_classification',
        },
        'trend_signal': {
            'model_path': '/app/models/mean_reversion_momentum_v1/1h_latest',
            'output_type': 'classification',
        },
        'range_signal': {
            'model_path': '/app/models/bb_stochastic_mean_reversion_eurusd_1h_v1/1h_latest',
            'output_type': 'classification',
        },
    },
    'composition': {
        'type': 'regime_route',
        'gate_model': 'regime',
        'regime_threshold': 0.4,
        'stability_bars': 3,
        'rules': {
            'trending_up': {'model': 'trend_signal'},
            'trending_down': {'model': 'trend_signal'},
            'ranging': {'model': 'range_signal'},
            'volatile': {'action': 'FLAT'},
        },
        'on_regime_transition': 'close_and_switch',
    },
})

print(f'name: {config.name}')
print(f'models: {list(config.models.keys())}')
print(f'gate_model: {config.composition.gate_model}')
print(f'rules: {list(config.composition.rules.keys())}')
print(f'transition_policy: {config.composition.on_regime_transition}')
print('CONFIG_VALID: True')
"
```

**Expected:**
- `CONFIG_VALID: True` printed (no validation errors)
- 3 models listed: regime, trend_signal, range_signal
- gate_model is `regime`
- 4 rules: trending_up, trending_down, ranging, volatile

### 2. Load All Three ModelBundles

**Command:**
```bash
source .env.sandbox
CONTAINER="slot-1-backend-1"

docker exec "$CONTAINER" python -c "
from ktrdr.backtesting.model_bundle import ModelBundle

models = {
    'regime': '/app/models/regime_classifier_seed/1h_latest',
    'trend_signal': '/app/models/mean_reversion_momentum_v1/1h_latest',
    'range_signal': '/app/models/bb_stochastic_mean_reversion_eurusd_1h_v1/1h_latest',
}

for name, path in models.items():
    bundle = ModelBundle.load(path)
    output_type = bundle.metadata.output_type
    feature_count = len(bundle.feature_names)
    print(f'{name}: output_type={output_type}, features={feature_count}')

    # Sanity: regime model must be regime_classification
    if name == 'regime':
        assert output_type == 'regime_classification', f'Expected regime_classification, got {output_type}'

    # Sanity: signal models must be classification
    if name in ('trend_signal', 'range_signal'):
        assert output_type == 'classification', f'Expected classification, got {output_type}'

print('ALL_BUNDLES_LOADED: True')
"
```

**Expected:**
- All three bundles load without error
- `regime` has output_type `regime_classification`
- `trend_signal` and `range_signal` have output_type `classification`
- Each model has features > 0
- `ALL_BUNDLES_LOADED: True` printed

### 3. Run Full Ensemble Backtest

**Command:**
```bash
source .env.sandbox
CONTAINER="slot-1-backend-1"

# Run with generous timeout (60s) for cold-start scenarios
docker exec -e PYTHONDONTWRITEBYTECODE=1 "$CONTAINER" timeout 120 python -c "
import asyncio
import json
import time

from ktrdr.backtesting.engine import BacktestConfig
from ktrdr.backtesting.ensemble_runner import EnsembleBacktestRunner
from ktrdr.config.ensemble_config import EnsembleConfiguration

# Build config
ensemble_config = EnsembleConfiguration.from_dict({
    'name': 'regime_routed_v1',
    'description': 'E2E test',
    'models': {
        'regime': {
            'model_path': '/app/models/regime_classifier_seed/1h_latest',
            'output_type': 'regime_classification',
        },
        'trend_signal': {
            'model_path': '/app/models/mean_reversion_momentum_v1/1h_latest',
            'output_type': 'classification',
        },
        'range_signal': {
            'model_path': '/app/models/bb_stochastic_mean_reversion_eurusd_1h_v1/1h_latest',
            'output_type': 'classification',
        },
    },
    'composition': {
        'type': 'regime_route',
        'gate_model': 'regime',
        'regime_threshold': 0.4,
        'stability_bars': 3,
        'rules': {
            'trending_up': {'model': 'trend_signal'},
            'trending_down': {'model': 'trend_signal'},
            'ranging': {'model': 'range_signal'},
            'volatile': {'action': 'FLAT'},
        },
        'on_regime_transition': 'close_and_switch',
    },
})

backtest_config = BacktestConfig(
    strategy_config_path='',
    model_path=None,
    symbol='EURUSD',
    timeframe='1h',
    start_date='2024-01-01',
    end_date='2024-06-01',
    initial_capital=100000.0,
)

runner = EnsembleBacktestRunner(
    ensemble_config=ensemble_config,
    backtest_config=backtest_config,
)

results = asyncio.run(runner.run())

# Output structured results for validation
output = results.to_dict()
output['trade_details_count'] = len(results.trades)
output['regime_sequence_count'] = len(results.regime_sequence)

# Add regime bar totals for sanity
total_regime_bars = sum(m.get('bars', 0) for m in output['per_regime_metrics'].values())
output['total_regime_bars'] = total_regime_bars

# Regime coverage: how many regimes have bars > 0
regimes_with_bars = [r for r, m in output['per_regime_metrics'].items() if m.get('bars', 0) > 0]
output['regimes_with_bars'] = regimes_with_bars

print('ENSEMBLE_RESULT_JSON_START')
print(json.dumps(output, indent=2, default=str))
print('ENSEMBLE_RESULT_JSON_END')
"
```

**Expected:**
- Script completes without error (exit code 0)
- JSON result block printed between markers
- `trade_count` field present
- `per_regime_metrics` populated for all 4 regimes
- `execution_time_seconds` present and > 0

### 4. Validate Results Structure and Content

**Command:**
```bash
# Parse the output from Step 3 (assume it's captured in $RESULT_JSON)
# In practice, the runner agent captures Step 3 output and extracts the JSON

# Key assertions to verify from the JSON output:
# 1. ensemble_name == "regime_routed_v1"
# 2. symbol == "EURUSD"
# 3. timeframe == "1h"
# 4. total_bars > 3000 (5 months of 1h data minus 50 warmup)
# 5. trade_count >= 0 (model may be conservative)
# 6. per_regime_metrics has all 4 keys: trending_up, trending_down, ranging, volatile
# 7. At least 1 regime has bars > 0 (routing actually occurred)
# 8. execution_time_seconds > 0 and < 120
# 9. regimes_with_bars has length >= 1
```

**Expected:**
- All structural assertions pass (see Success Criteria below)

---

## Success Criteria

- [ ] Ensemble config loads from dict without validation errors (Step 1)
- [ ] All three ModelBundles load successfully with correct output_types (Step 2)
- [ ] Ensemble backtest completes without error (Step 3 exit code 0)
- [ ] Results contain `ensemble_name: "regime_routed_v1"` (correct config propagated)
- [ ] `total_bars > 3000` (real data was processed, not an empty run)
- [ ] `per_regime_metrics` has all 4 regime keys (trending_up, trending_down, ranging, volatile)
- [ ] At least 1 regime has `bars > 0` (regime classification actually ran and routed)
- [ ] `execution_time_seconds > 1.0` (real computation occurred)
- [ ] `execution_time_seconds < 120` (completed in reasonable time)

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **total_bars > 3000** -- 5 months of 1h EURUSD is ~3600 bars minus 50 warmup = ~3550. Fewer than 3000 suggests data was not loaded or date range was truncated. This catches the scenario where DataRepository.load_from_cache returns empty/partial data.

- [ ] **At least 2 regimes have bars > 0** -- If only 1 regime has bars, the regime classifier is collapsing to a single class (likely RANGING at ~91%). This means routing never occurred. At minimum trending + ranging should both appear in 5 months of EURUSD.

- [ ] **total_regime_bars approximates total_bars** -- The sum of per-regime bars should be close to total_bars (difference is bars where regime was None due to missing features). If total_regime_bars is 0 or much less than total_bars, the regime classifier is returning None features for most bars.

- [ ] **execution_time_seconds > 1.0** -- Loading 3 models + computing features + running ~3500 bars through the loop should take at least a second. Under 1s suggests the loop short-circuited (e.g., empty data, immediate error caught silently).

- [ ] **transition_count >= 0** -- Not a strict requirement (could be 0 if one regime dominates), but if total_bars > 3000 and transition_count == 0, the stability filter may be too aggressive or the classifier is stuck. Worth noting in evidence.

- [ ] **trade_count sanity: if > 0, must have per_regime_metrics with trades > 0 too** -- Trades come from signal models routed through regimes. If total trade_count > 0 but all per_regime trades are 0, the trade counting is broken (trades attributed to wrong bucket or not attributed at all).

**Sanity check command (run inside Step 3 output parsing):**
```bash
# After extracting JSON from Step 3:
# Check: total_bars
TOTAL_BARS=$(echo "$RESULT_JSON" | jq '.total_bars')
test "$TOTAL_BARS" -gt 3000 && echo "PASS: total_bars=$TOTAL_BARS" || echo "FAIL: total_bars=$TOTAL_BARS (expected > 3000)"

# Check: regimes with bars
REGIME_COUNT=$(echo "$RESULT_JSON" | jq '.regimes_with_bars | length')
test "$REGIME_COUNT" -ge 2 && echo "PASS: $REGIME_COUNT regimes have bars" || echo "WARN: only $REGIME_COUNT regime(s) have bars"

# Check: execution time
EXEC_TIME=$(echo "$RESULT_JSON" | jq '.execution_time_seconds')
echo "execution_time: $EXEC_TIME"

# Check: regime bar coverage
TOTAL_REGIME_BARS=$(echo "$RESULT_JSON" | jq '.total_regime_bars')
echo "total_regime_bars: $TOTAL_REGIME_BARS / total_bars: $TOTAL_BARS"
```

---

## Troubleshooting

**If model load fails with "FileNotFoundError":**
- **Cause:** Model not trained or not at the expected path inside the container
- **Category:** ENVIRONMENT
- **Cure:** Verify models exist on host at `~/.ktrdr/shared/models/{name}/1h_latest/model.pt`. If missing, run `training/regime-classifier` test first, then train the signal models. Check that `KTRDR_MODELS_DIR` in `.env.sandbox` points to `~/.ktrdr/shared/models`.

**If model load fails with "metadata_v3.json not found":**
- **Cause:** Model was trained with v2 pipeline (produces metadata.json, not metadata_v3.json)
- **Category:** ENVIRONMENT
- **Cure:** Retrain the model using v3 pipeline. The ModelBundle.load() method reads metadata_v3.json.

**If "regime_classification" assertion fails on gate model:**
- **Cause:** Regime classifier was trained without the regime label source, producing output_type "classification" instead of "regime_classification"
- **Category:** CODE_BUG or ENVIRONMENT
- **Cure:** Retrain with strategy that has `training.labels.source: regime`. See `training/regime-classifier` test.

**If all bars go to one regime (only ranging has bars > 0):**
- **Cause:** Regime classifier collapsed to predicting one class (known issue with class imbalance -- RANGING is ~91% of labels)
- **Category:** TEST_ISSUE (model quality, not a code bug)
- **Cure:** This is a model quality issue. The test still validates that the ensemble machinery works (config loads, models load, loop runs, metrics are produced). The routing code is correct even if the model is degenerate.

**If trade_count is 0:**
- **Cause:** Signal models may be conservative (high thresholds, no strong signals in this period)
- **Category:** TEST_ISSUE (not a code bug)
- **Cure:** Acceptable if all other criteria pass. The test validates the ensemble pipeline, not trading profitability. Zero trades with correct regime routing is a valid outcome.

**If execution times out (>120s):**
- **Cause:** Feature computation for 3 models on ~3500 bars may be slow on first run (indicator cache cold)
- **Category:** ENVIRONMENT
- **Cure:** Retry once -- second run benefits from warm caches. If still slow, check container resource limits.

**If DataRepository.load_from_cache fails with "No data found":**
- **Cause:** EURUSD 1h data not cached in the container's data directory
- **Category:** ENVIRONMENT
- **Cure:** Load data first: `docker exec $CONTAINER python -c "from ktrdr.data.repository import DataRepository; DataRepository().fetch_and_cache('EURUSD', '1h', '2024-01-01', '2024-06-01')"` or run `uv run ktrdr data load EURUSD 1h --start-date 2024-01-01 --end-date 2024-06-01`.

**If "module not found" errors for ktrdr.backtesting.ensemble_runner:**
- **Cause:** Container has stale code -- source not hot-reloaded
- **Category:** ENVIRONMENT
- **Cure:** The source is volume-mounted (`./ktrdr:/app/ktrdr`), so it should be current. If not, restart: `uv run kinfra sandbox down && uv run kinfra sandbox up`.

---

## Evidence to Capture

- Pre-flight: model directory listings inside container (`docker exec $CONTAINER ls -la /app/models/{name}/1h_latest/`)
- Step 1: Config validation output (model names, gate_model, rules)
- Step 2: ModelBundle load output (output_types, feature counts)
- Step 3: Full JSON result block (between ENSEMBLE_RESULT_JSON_START/END markers)
- Key metrics from JSON:
  - `total_bars` (expect ~3550)
  - `trade_count` (may be 0)
  - `per_regime_metrics` (all 4 regimes with bars/trades counts)
  - `transition_count` (number of regime switches)
  - `execution_time_seconds`
  - `regimes_with_bars` (list of regimes that were active)
- Container logs if failure: `docker compose -f docker-compose.sandbox.yml logs backend --since 5m 2>/dev/null | tail -50`

---

## Notes

- **Runs inside container:** This test uses `docker exec` to run Python inside the backend container because the ensemble backtest requires torch and model loading, which are only available inside the container.
- **Port variable:** Read from `.env.sandbox` as `KTRDR_API_PORT` (slot 1 = port 8001). However, this test does NOT use the API -- it runs the ensemble backtest directly via Python inside the container.
- **Container name:** `slot-1-backend-1` (from COMPOSE_PROJECT_NAME=slot-1 in .env.sandbox).
- **Model paths are container-internal:** `/app/models/` maps to `$KTRDR_MODELS_DIR` on host (`~/.ktrdr/shared/models`). The ensemble config YAML at `configs/ensemble_regime_routed.yaml` uses host paths and cannot be used directly inside the container.
- **Config not from YAML:** The `configs/` directory is not volume-mounted into the container, so the test constructs EnsembleConfiguration from a dict inline rather than loading from YAML.
- **Non-determinism:** Regime classification and signal model outputs are non-deterministic (neural network inference). The test asserts structural correctness (fields present, types correct, bars counted) rather than specific trade outcomes.
- **Dependency chain:** This test requires three previously trained models. Run `training/regime-classifier` first if the regime model is missing. The signal models come from earlier milestones.
- **Per-regime trade attribution:** Trades are attributed to regimes in the ensemble runner's per-bar loop. A trade executed during a regime transition is attributed to the regime that was active when the signal was generated, not the new regime.
