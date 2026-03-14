# Test: backtesting/regression-context-gated-ensemble

**Purpose:** Validate that context-gated ensemble backtesting works correctly with regression signal models, where the ThresholdModifier adjusts `trade_threshold` (not `confidence_threshold`) and re-evaluates `predicted_return` against adjusted buy/sell thresholds.

**Duration:** ~2min (two full backtest runs inside container with real model inference)

**Category:** Backtesting (container E2E with real models)

**Dependency:** Trained regression models must exist inside the container

---

## Pre-Flight Checks

**Required:** preflight/common.md (Docker healthy, API responsive, sandbox detection)

**Test-specific checks:**

- [ ] Sandbox is slot 1, port 8001 (`source .env.sandbox && echo $KTRDR_API_PORT` returns `8001`)
- [ ] Backend container is running: `docker compose -f docker-compose.sandbox.yml ps backend | grep running`
- [ ] Ensemble CLI subcommand exists: `docker exec slot-1-backend-1 uv run ktrdr ensemble backtest --help` returns usage info (not error)
- [ ] Regime classifier model exists: `docker exec slot-1-backend-1 ls /app/models/regime_classifier_seed/1h_latest/model.pt`
- [ ] Context classifier model exists: `docker exec slot-1-backend-1 ls /app/models/context_classifier_seed_v1/1d_latest/model.pt`
- [ ] Trend regression signal model exists: `docker exec slot-1-backend-1 ls /app/models/trend_regression_signal/1h_latest/model.pt`
- [ ] Range regression signal model exists: `docker exec slot-1-backend-1 ls /app/models/range_regression_signal/1h_latest/model.pt`
- [ ] EURUSD 1h data available for 2024-01-01 to 2024-06-01 (enough bars for meaningful test)

**If ensemble CLI subcommand does not exist:** Fall back to Python API execution via `docker exec` (see Step 2 alternate path).

---

## Setup

1. Copy container-specific ensemble configs into the backend container:

```bash
docker cp configs/ensemble_regression_context_gated_container.yaml \
  slot-1-backend-1:/app/configs/ensemble_regression_context_gated_container.yaml

docker cp configs/ensemble_regression_regime_only_container.yaml \
  slot-1-backend-1:/app/configs/ensemble_regression_regime_only_container.yaml
```

2. Verify configs are in place:

```bash
docker exec slot-1-backend-1 cat /app/configs/ensemble_regression_context_gated_container.yaml | head -5
docker exec slot-1-backend-1 cat /app/configs/ensemble_regression_regime_only_container.yaml | head -5
```

**Expected:** First line contains `name: regression_context_gated` and `name: regression_regime_only` respectively.

---

## Execution Steps

### Overview

| Step | Action | Expected Result | Evidence to Capture |
|------|--------|-----------------|---------------------|
| 1 | Validate both configs load | Config names and model counts correct | Config YAML parsed |
| 2 | Run context-gated ensemble backtest | Completes with trades, transitions, no errors | Full stdout output |
| 3 | Run regime-only ensemble backtest | Completes with trades, transitions, no errors | Full stdout output |
| 4 | Parse and compare results | Trade counts, regime bars, transitions extracted | Parsed metrics from both |
| 5 | Verify regression path was used | Output format is regression, trade_threshold applied | Evidence in output or logs |
| 6 | Verify context gate was evaluated | Context-gated run has daily context evaluations | Log lines or different trade counts |

---

### Detailed Steps

#### Step 1: Validate Config Loading

```bash
docker exec slot-1-backend-1 uv run python -c "
from ktrdr.config.ensemble_config import EnsembleConfiguration

# Context-gated
ctx = EnsembleConfiguration.from_yaml('configs/ensemble_regression_context_gated_container.yaml')
assert ctx.name == 'regression_context_gated', f'Wrong name: {ctx.name}'
assert len(ctx.models) == 4, f'Expected 4 models, got {len(ctx.models)}'
assert 'regime' in ctx.models
assert 'context' in ctx.models
assert 'trend_signal' in ctx.models
assert 'range_signal' in ctx.models
assert ctx.composition.context_gate == 'context'
assert ctx.composition.context_modifiers is not None
assert ctx.composition.allow_short_from_flat is True
# Verify regression output_type on signal models
assert ctx.models['trend_signal'].output_type == 'regression'
assert ctx.models['range_signal'].output_type == 'regression'
print('OK: Context-gated config validated (4 models, regression output_type, context_gate=context)')

# Regime-only
reg = EnsembleConfiguration.from_yaml('configs/ensemble_regression_regime_only_container.yaml')
assert reg.name == 'regression_regime_only', f'Wrong name: {reg.name}'
assert len(reg.models) == 3, f'Expected 3 models, got {len(reg.models)}'
assert 'context' not in reg.models
assert reg.composition.context_gate is None
assert reg.composition.context_modifiers is None
assert reg.composition.allow_short_from_flat is True
assert reg.models['trend_signal'].output_type == 'regression'
assert reg.models['range_signal'].output_type == 'regression'
print('OK: Regime-only config validated (3 models, regression output_type, no context_gate)')
"
```

**Expected:** Both "OK" lines printed, no assertion errors.
**Capture:** Full output including model counts and output types.

#### Step 2: Run Context-Gated Ensemble Backtest

**Primary path (CLI exists):**

```bash
docker exec slot-1-backend-1 uv run ktrdr ensemble backtest \
  configs/ensemble_regression_context_gated_container.yaml \
  --start-date 2024-01-01 --end-date 2024-06-01 \
  --symbol EURUSD --timeframe 1h 2>&1 | tee /tmp/e2e_ctx_gated_output.txt
```

**Alternate path (if CLI subcommand does not exist):**

```bash
docker exec slot-1-backend-1 uv run python -c "
import asyncio
from ktrdr.backtesting.engine import BacktestConfig
from ktrdr.backtesting.ensemble_runner import EnsembleBacktestRunner
from ktrdr.config.ensemble_config import EnsembleConfiguration

config = EnsembleConfiguration.from_yaml('configs/ensemble_regression_context_gated_container.yaml')
bt_config = BacktestConfig(
    strategy_config_path='', model_path=None,
    symbol='EURUSD', timeframe='1h',
    start_date='2024-01-01', end_date='2024-06-01',
    initial_capital=100000.0,
)
runner = EnsembleBacktestRunner(config, bt_config)
results = asyncio.run(runner.run())

print(f'ENSEMBLE_NAME={results.ensemble_name}')
print(f'TOTAL_BARS={results.total_bars}')
print(f'TOTAL_TRADES={len(results.trades)}')
print(f'TRANSITION_COUNT={results.transition_count}')
print(f'EXECUTION_TIME={results.execution_time_seconds:.1f}')
for regime, metrics in results.per_regime_metrics.items():
    print(f'REGIME_{regime.upper()}_BARS={metrics.get(\"bars\", 0)}')
    print(f'REGIME_{regime.upper()}_TRADES={metrics.get(\"trades\", 0)}')
" 2>&1 | tee /tmp/e2e_ctx_gated_output.txt
```

**Expected:**
- Exit code 0 (no errors)
- `TOTAL_BARS` > 0 (data was processed)
- `TOTAL_TRADES` > 0 (regression models produced actionable signals)
- `TRANSITION_COUNT` >= 1 (regime transitions occurred over 6 months)

**Capture:** Full output, save to `/tmp/e2e_ctx_gated_output.txt`

#### Step 3: Run Regime-Only Ensemble Backtest

**Primary path (CLI):**

```bash
docker exec slot-1-backend-1 uv run ktrdr ensemble backtest \
  configs/ensemble_regression_regime_only_container.yaml \
  --start-date 2024-01-01 --end-date 2024-06-01 \
  --symbol EURUSD --timeframe 1h 2>&1 | tee /tmp/e2e_regime_only_output.txt
```

**Alternate path (Python API):**

```bash
docker exec slot-1-backend-1 uv run python -c "
import asyncio
from ktrdr.backtesting.engine import BacktestConfig
from ktrdr.backtesting.ensemble_runner import EnsembleBacktestRunner
from ktrdr.config.ensemble_config import EnsembleConfiguration

config = EnsembleConfiguration.from_yaml('configs/ensemble_regression_regime_only_container.yaml')
bt_config = BacktestConfig(
    strategy_config_path='', model_path=None,
    symbol='EURUSD', timeframe='1h',
    start_date='2024-01-01', end_date='2024-06-01',
    initial_capital=100000.0,
)
runner = EnsembleBacktestRunner(config, bt_config)
results = asyncio.run(runner.run())

print(f'ENSEMBLE_NAME={results.ensemble_name}')
print(f'TOTAL_BARS={results.total_bars}')
print(f'TOTAL_TRADES={len(results.trades)}')
print(f'TRANSITION_COUNT={results.transition_count}')
print(f'EXECUTION_TIME={results.execution_time_seconds:.1f}')
for regime, metrics in results.per_regime_metrics.items():
    print(f'REGIME_{regime.upper()}_BARS={metrics.get(\"bars\", 0)}')
    print(f'REGIME_{regime.upper()}_TRADES={metrics.get(\"trades\", 0)}')
" 2>&1 | tee /tmp/e2e_regime_only_output.txt
```

**Expected:**
- Exit code 0 (no errors)
- `TOTAL_BARS` > 0 (same data range processed)
- `TOTAL_TRADES` > 0 (regression models produced actionable signals)

**Capture:** Full output, save to `/tmp/e2e_regime_only_output.txt`

#### Step 4: Parse and Compare Results

```bash
# Extract key metrics from both runs
CTX_TRADES=$(grep 'TOTAL_TRADES=' /tmp/e2e_ctx_gated_output.txt | cut -d= -f2 | tr -d ' ')
REG_TRADES=$(grep 'TOTAL_TRADES=' /tmp/e2e_regime_only_output.txt | cut -d= -f2 | tr -d ' ')
CTX_BARS=$(grep 'TOTAL_BARS=' /tmp/e2e_ctx_gated_output.txt | cut -d= -f2 | tr -d ' ')
REG_BARS=$(grep 'TOTAL_BARS=' /tmp/e2e_regime_only_output.txt | cut -d= -f2 | tr -d ' ')

echo "Context-gated trades: $CTX_TRADES"
echo "Regime-only trades: $REG_TRADES"
echo "Context-gated bars: $CTX_BARS"
echo "Regime-only bars: $REG_BARS"

# Both should have same bar count (same data)
if [ "$CTX_BARS" != "$REG_BARS" ]; then
  echo "FAIL: Bar counts differ ($CTX_BARS vs $REG_BARS) -- unexpected for same date range"
fi

# Trade counts should differ (context gate changes marginal decisions)
if [ "$CTX_TRADES" = "$REG_TRADES" ]; then
  echo "WARNING: Trade counts identical ($CTX_TRADES) -- context gate may not be affecting decisions"
  echo "This is not necessarily a failure if predicted returns are far from thresholds"
else
  echo "OK: Trade counts differ (context=$CTX_TRADES, regime=$REG_TRADES) -- context gate is affecting decisions"
fi
```

**Expected:** Both runs processed same number of bars. Trade counts ideally differ (context gate changes marginal threshold decisions for regression models).
**Capture:** Trade count comparison.

**Important nuance:** Trade counts _may_ be identical if all predicted returns are far from the threshold boundaries (either clearly above or clearly below). The context gate only affects marginal decisions where `predicted_return` is near `trade_threshold`. A WARNING (not FAIL) is appropriate here.

#### Step 5: Verify Regression Path Was Exercised

```bash
docker exec slot-1-backend-1 uv run python -c "
import asyncio
import logging
from ktrdr.backtesting.engine import BacktestConfig
from ktrdr.backtesting.ensemble_runner import EnsembleBacktestRunner
from ktrdr.config.ensemble_config import EnsembleConfiguration

# Enable debug logging to see context updates and threshold adjustments
logging.basicConfig(level=logging.DEBUG)

config = EnsembleConfiguration.from_yaml('configs/ensemble_regression_context_gated_container.yaml')

# Verify signal models have regression output_type in config
for name in ['trend_signal', 'range_signal']:
    model_ref = config.models[name]
    assert model_ref.output_type == 'regression', f'{name} output_type is {model_ref.output_type}, expected regression'
    print(f'OK: {name} output_type = regression')

# Load model bundles and check DecisionFunction attributes
from ktrdr.backtesting.model_bundle import ModelBundle
from ktrdr.backtesting.decision_function import DecisionFunction

for name in ['trend_signal', 'range_signal']:
    bundle = ModelBundle.load(config.models[name].model_path)
    decisions = getattr(bundle.strategy_config, 'decisions', {})
    if hasattr(decisions, 'model_dump'):
        decisions_config = decisions.model_dump()
    elif isinstance(decisions, dict):
        decisions_config = decisions
    else:
        decisions_config = {}

    fn = DecisionFunction(
        model=bundle.model,
        feature_names=bundle.feature_names,
        decisions_config=decisions_config,
        output_type=config.models[name].output_type,
    )
    assert fn.output_format == 'regression', f'{name} output_format is {fn.output_format}'
    assert hasattr(fn, 'trade_threshold'), f'{name} missing trade_threshold attribute'
    print(f'OK: {name} output_format=regression, trade_threshold={fn.trade_threshold:.6f}')
" 2>&1 | tee /tmp/e2e_regression_verify.txt
```

**Expected:**
- Both `trend_signal` and `range_signal` have `output_format == "regression"`
- Both have `trade_threshold` attribute (computed from `round_trip_cost * min_edge_multiplier`)
- No `confidence_threshold` attribute on these (regression path does not set it)

**Capture:** Output format and trade_threshold values for both signal models.

#### Step 6: Verify Context Gate Daily Evaluation

```bash
docker exec slot-1-backend-1 uv run python -c "
import asyncio
import logging

# Capture context update log messages
context_log_msgs = []
original_debug = logging.Logger.debug

def capture_debug(self, msg, *args, **kwargs):
    if 'Context updated' in str(msg):
        context_log_msgs.append(str(msg))
    return original_debug(self, msg, *args, **kwargs)

logging.Logger.debug = capture_debug
logging.basicConfig(level=logging.DEBUG)

from ktrdr.backtesting.engine import BacktestConfig
from ktrdr.backtesting.ensemble_runner import EnsembleBacktestRunner
from ktrdr.config.ensemble_config import EnsembleConfiguration

config = EnsembleConfiguration.from_yaml('configs/ensemble_regression_context_gated_container.yaml')
bt_config = BacktestConfig(
    strategy_config_path='', model_path=None,
    symbol='EURUSD', timeframe='1h',
    start_date='2024-01-01', end_date='2024-06-01',
    initial_capital=100000.0,
)
runner = EnsembleBacktestRunner(config, bt_config)
results = asyncio.run(runner.run())

# Count unique context evaluation dates
print(f'CONTEXT_UPDATES={len(context_log_msgs)}')
print(f'TOTAL_BARS={results.total_bars}')

# Context should be evaluated once per trading day, NOT once per bar
# ~130 trading days in Jan-Jun 2024 for forex (5 days/week * 26 weeks)
# But context is evaluated once per CALENDAR day boundary in hourly data
# So expect roughly 182 context evaluations (Jan 1 to Jun 1 = ~152 days)
if len(context_log_msgs) > 0:
    print(f'OK: Context gate was evaluated {len(context_log_msgs)} times')
    # Should be WAY less than total_bars (which is ~3600+ for 6 months of hourly)
    ratio = len(context_log_msgs) / results.total_bars
    print(f'CONTEXT_TO_BAR_RATIO={ratio:.4f}')
    if ratio < 0.1:
        print('OK: Context evaluated much less frequently than bars (daily, not per-bar)')
    else:
        print('FAIL: Context evaluated too frequently -- may be running per-bar instead of daily')
else:
    print('FAIL: No context update log messages captured -- context gate may not be firing')

# Verify runner state was set
assert runner._last_context_date is not None, 'Context was never evaluated (_last_context_date is None)'
assert runner._current_context_probs is not None, 'Context probs never set'
print(f'LAST_CONTEXT_DATE={runner._last_context_date}')
print(f'FINAL_CONTEXT_PROBS={runner._current_context_probs}')

# Restore
logging.Logger.debug = original_debug
" 2>&1 | tee /tmp/e2e_context_verify.txt
```

**Expected:**
- `CONTEXT_UPDATES` > 0 (context gate is firing)
- `CONTEXT_TO_BAR_RATIO` < 0.1 (evaluated daily, not per-bar)
- `_last_context_date` is not None
- `_current_context_probs` contains bullish/bearish/neutral keys

**Capture:** Context update count, ratio, final context state.

---

## Success Criteria

All must pass:

- [ ] Both ensemble YAML configs load and validate (correct model counts, output types)
- [ ] Context-gated backtest completes without error (exit code 0)
- [ ] Regime-only backtest completes without error (exit code 0)
- [ ] Both runs process > 0 bars
- [ ] Both runs produce > 0 trades (regression models generate actionable signals)
- [ ] Signal models have `output_format == "regression"` and `trade_threshold` attribute
- [ ] Signal models do NOT have `confidence_threshold` attribute (regression path)
- [ ] Context gate was evaluated (context_update_count > 0)
- [ ] Context evaluated daily, not per-bar (context_to_bar_ratio < 0.1)
- [ ] Runner `_last_context_date` is set after context-gated run
- [ ] Runner `_current_context_probs` contains bullish/bearish/neutral probabilities
- [ ] Both runs processed same number of bars (same data range)

---

## Sanity Checks

**CRITICAL:** These catch false positives.

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| Total bars > 3000 | <= 100 fails | Data not loaded, wrong date range, or early abort |
| Total trades > 0 (both runs) | 0 fails | Regression models all outputting HOLD, trade_threshold too high |
| Total trades < total_bars (both runs) | trades >= bars fails | Every bar generating a trade (degenerate model) |
| Context updates > 0 | 0 fails | Context gate not firing at all |
| Context updates < total_bars / 10 | ratio >= 0.1 fails | Context evaluated per-bar instead of daily |
| Execution time > 5s (per run) | <= 5s fails | Backtest was skipped or used cached result |
| Execution time < 300s (per run) | >= 300s fails | Hung or excessively slow inference |
| signal_fn.output_format == "regression" | != "regression" fails | Classification path used instead of regression |
| signal_fn has trade_threshold | missing fails | Regression DecisionFunction not initialized correctly |
| signal_fn lacks confidence_threshold | has it fails | Wrong code path -- both attributes should not coexist |

---

## Failure Categorization

| Failure Type | Category | Suggested Action |
|--------------|----------|------------------|
| Model file not found | ENVIRONMENT | Check model paths in container. Models must be pre-trained and placed at `/app/models/` paths |
| Config YAML not found | ENVIRONMENT | Re-run setup step to copy configs into container |
| ImportError on ensemble modules | ENVIRONMENT | Container may need rebuild (`kinfra sandbox up --build`) |
| No trades produced | CODE_BUG or CONFIGURATION | Check trade_threshold value -- if too high, all predicted_returns fall in HOLD zone. Inspect `round_trip_cost` and `min_edge_multiplier` in strategy decisions config |
| Context not evaluated | CODE_BUG | Check `_maybe_update_context()` -- is `context_gate` being read from config? |
| Context evaluated every bar | CODE_BUG | Check `_last_context_date` comparison in `_maybe_update_context()` |
| Same trade counts (ctx vs regime) | EXPECTED or CODE_BUG | If predicted returns are far from threshold, context adjustment has no effect. Not necessarily a bug. Check if `route.threshold_modifier` is being set by RegimeRouter when context_probs are passed |
| output_format is "classification" | CODE_BUG | Check DecisionFunction.__init__ -- output_format should come from decisions_config, and ensemble_runner should pass output_type through |
| Timeout (> 5min) | ENVIRONMENT | Container resource constrained, or data loading hanging. Check container logs |
| Data error (wrong date range) | ENVIRONMENT | EURUSD 1h data may not be available for 2024 range. Check data cache |
| ensemble CLI subcommand not found | ENVIRONMENT | Use alternate Python API path (Step 2 alternate). CLI registration may not include ensemble app |

---

## Cleanup

```bash
# Remove configs from container (optional, harmless to leave)
docker exec slot-1-backend-1 rm -f \
  /app/configs/ensemble_regression_context_gated_container.yaml \
  /app/configs/ensemble_regression_regime_only_container.yaml

# Remove local temp files
rm -f /tmp/e2e_ctx_gated_output.txt /tmp/e2e_regime_only_output.txt \
  /tmp/e2e_regression_verify.txt /tmp/e2e_context_verify.txt
```

---

## Notes for Implementation

- **CLI vs Python API:** The `ktrdr ensemble backtest` CLI command exists (registered in `app.py` line 134). Prefer the CLI path for a true E2E test. The Python API alternate path is provided as fallback if CLI invocation fails for any reason.

- **Regression vs Classification distinction:** The core code under test (lines 287-312 of `ensemble_runner.py`) uses `getattr(signal_fn, "output_format", "classification")` to detect regression models. If `output_format` is not set on the DecisionFunction, it defaults to "classification" and takes the wrong code path. Step 5 verifies this attribute exists.

- **Trade count comparison caveat:** The context gate adjusts `trade_threshold` by factors of ~0.8-1.2x. If all predicted returns are far from the threshold (e.g., 10x above or below), the adjustment has no observable effect on signal decisions. This means identical trade counts between context-gated and regime-only is _possible_ and not necessarily a bug. The test treats this as a WARNING, not a FAIL.

- **Container naming:** Sandbox slot 1 uses `slot-1-backend-1` as the container name (from `COMPOSE_PROJECT_NAME=slot-1`).

- **`allow_short_from_flat: true`:** Both configs enable shorting from flat, which is standard for forex. This means SELL signals from flat position will open short positions, increasing the total trade count compared to equity-style configs.

- **Daily context evaluation:** The `_maybe_update_context()` method compares `timestamp.date()` against `_last_context_date`. For 6 months of hourly data (~3600 bars), context should be evaluated ~152 times (unique calendar days), giving a ratio of ~0.04.

- **Log capture approach in Step 6:** Monkey-patching `logging.Logger.debug` is fragile but necessary because the context update log message is emitted at DEBUG level inside `_maybe_update_context()`. An alternative approach is to check `runner._last_context_date is not None` and `runner._current_context_probs is not None` as simpler assertions, which Step 6 also includes as a fallback.

- **Date range rationale:** 2024-01-01 to 2024-06-01 provides ~3600 hourly bars and ~152 daily boundaries. This is enough to see multiple regime transitions and context evaluations without being excessively slow (~30-60s per run with CPU inference).
