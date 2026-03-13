# Test: backtesting/context-gated-ensemble

**Purpose:** Validate context-gated ensemble backtesting runs end-to-end with regime routing, daily context gating, threshold modification, and backward compatibility with regime-only configs.

**Duration:** <30s (local Python execution with mock models, no Docker/API required)

**Category:** Backtesting (local pipeline)

**Dependency:** None (uses mock decision functions, no trained models needed)

---

## Pre-Flight Checks

**Required modules:**
- None (this is a local Python pipeline test, not an API/Docker test)

**Test-specific checks:**
- [ ] Config file exists: `configs/ensemble_context_gated.yaml`
- [ ] Config file exists: `configs/ensemble_regime_routed.yaml`
- [ ] Python imports succeed: `EnsembleBacktestRunner`, `RegimeRouter`, `EnsembleConfiguration`, `PositionManager`
- [ ] Working directory is repo root (config paths are relative)

---

## Test Data

This test uses synthetic OHLCV data and mock decision functions. No trained models or real data required.

```python
# Synthetic data: 168 hourly bars = 7 days
# Provides enough bars for:
#   - 7 daily context evaluations (one per day)
#   - Multiple regime transitions (controlled via mock)
#   - Meaningful trade activity

# Mock regime sequence (changes every ~48 bars):
#   Day 1-2: trending_up (48 bars)
#   Day 3-4: ranging (48 bars)  -- triggers regime transition
#   Day 5-6: trending_down (48 bars) -- triggers another transition
#   Day 7: volatile (24 bars) -- forces FLAT

# Mock context sequence (changes daily):
#   Day 1: bullish (0.7, 0.1, 0.2) -- lowers long threshold
#   Day 2: bullish (0.7, 0.1, 0.2) -- same day context, confirms caching
#   Day 3: neutral (0.3, 0.3, 0.4) -- minimal adjustment
#   Day 4: bearish (0.1, 0.8, 0.1) -- raises long threshold, lowers short
#   Day 5: bearish (0.15, 0.7, 0.15) -- counter-trend for trending_down
#   Day 6: neutral (0.35, 0.3, 0.35) -- back to neutral
#   Day 7: bearish (0.1, 0.8, 0.1) -- doesn't matter, volatile = FLAT
```

**Why this data:**
- 7 days provides enough daily boundaries to exercise context evaluation caching
- Regime transitions test stability filter and position closing
- Mixed context states (bullish/neutral/bearish) validate threshold math in both directions
- Volatile regime with FLAT action validates the no-signal path
- 168 bars is small enough to run in <1s but large enough for meaningful coverage

---

## Execution Steps

### Overview

| Step | Action | Expected Result | Evidence to Capture |
|------|--------|-----------------|---------------------|
| 1 | Load both YAML configs | EnsembleConfiguration objects created | Config names, model counts |
| 2 | Run context-gated pipeline (168 bars, 7 days) | Completes without error | Bar results array |
| 3 | Verify context evaluation frequency | Exactly 7 context calls (1 per day) | context_fn.call_count |
| 4 | Verify regime model call frequency | 168 regime calls (every bar) | regime_fn.call_count |
| 5 | Verify regime transitions occurred | At least 2 transitions | transition_count |
| 6 | Verify threshold modification math | Specific threshold values for known inputs | Captured thresholds |
| 7 | Run regime-only pipeline (same data) | Completes, no context calls | context state is None |
| 8 | Compare context-gated vs regime-only results | Different trade counts / signals | Trade count diff |

---

### Detailed Steps

#### Step 1: Load and Validate Both Configs

```python
from pathlib import Path
from ktrdr.config.ensemble_config import EnsembleConfiguration

# Context-gated config
ctx_config = EnsembleConfiguration.from_yaml("configs/ensemble_context_gated.yaml")
assert ctx_config.name == "context_gated_v1"
assert ctx_config.composition.context_gate == "context"
assert ctx_config.composition.context_modifiers is not None
assert ctx_config.composition.context_modifiers.aligned_discount == 0.2
assert ctx_config.composition.context_modifiers.counter_premium == 0.3
assert len(ctx_config.models) == 4  # regime, context, trend_signal, range_signal

# Regime-only config
reg_config = EnsembleConfiguration.from_yaml("configs/ensemble_regime_routed.yaml")
assert reg_config.name == "regime_routed_v1"
assert reg_config.composition.context_gate is None
assert reg_config.composition.context_modifiers is None
assert len(reg_config.models) == 3  # regime, trend_signal, range_signal
```

**Expected:** Both configs load without validation errors.
**Capture:** Config names, model counts, context modifier values.

#### Step 2: Run Context-Gated Pipeline (168 bars, 7 days)

```python
import numpy as np
import pandas as pd
from unittest.mock import MagicMock
from ktrdr.backtesting.engine import BacktestConfig
from ktrdr.backtesting.ensemble_runner import EnsembleBacktestRunner
from ktrdr.backtesting.regime_router import RegimeRouter
from ktrdr.backtesting.position_manager import PositionManager
from ktrdr.decision.base import Signal, Position, TradingDecision

N_BARS = 168  # 7 days * 24 hours

# Create synthetic OHLCV
dates = pd.date_range("2024-01-01", periods=N_BARS, freq="1h", tz="UTC")
rng = np.random.default_rng(42)
close = 1.1000 + np.cumsum(rng.normal(0, 0.0005, N_BARS))
data = pd.DataFrame({
    "open": close - rng.uniform(0, 0.001, N_BARS),
    "high": close + rng.uniform(0, 0.002, N_BARS),
    "low": close - rng.uniform(0, 0.002, N_BARS),
    "close": close,
    "volume": rng.integers(500, 2000, N_BARS),
}, index=dates)

# Regime mock: transitions over days
def regime_side_effect(**kw):
    """Return different regimes based on call count."""
    bar_idx = regime_fn.call_count  # 1-indexed after this call
    if bar_idx <= 48:
        regime, conf = "trending_up", 0.7
    elif bar_idx <= 96:
        regime, conf = "ranging", 0.65
    elif bar_idx <= 144:
        regime, conf = "trending_down", 0.7
    else:
        regime, conf = "volatile", 0.6
    probs = {"TRENDING_UP": 0.05, "TRENDING_DOWN": 0.05, "RANGING": 0.05, "VOLATILE": 0.05}
    probs[regime.upper()] = conf
    return TradingDecision(
        signal=Signal.HOLD, confidence=conf,
        timestamp=pd.Timestamp("2024-01-01", tz="UTC"),
        reasoning={"nn_probabilities": probs},
        current_position=Position.FLAT,
    )

# Context mock: changes daily
CONTEXT_SCHEDULE = {
    1: (0.7, 0.1, 0.2),   # bullish
    2: (0.7, 0.1, 0.2),   # bullish (same day)
    3: (0.3, 0.3, 0.4),   # neutral
    4: (0.1, 0.8, 0.1),   # bearish
    5: (0.15, 0.7, 0.15), # bearish
    6: (0.35, 0.3, 0.35), # neutral-ish
    7: (0.1, 0.8, 0.1),   # bearish
}
context_call_counter = [0]

def context_side_effect(**kw):
    context_call_counter[0] += 1
    day = context_call_counter[0]
    bull, bear, neut = CONTEXT_SCHEDULE.get(day, (0.33, 0.33, 0.34))
    return TradingDecision(
        signal=Signal.HOLD, confidence=max(bull, bear, neut),
        timestamp=pd.Timestamp("2024-01-01", tz="UTC"),
        reasoning={"nn_probabilities": {"BULLISH": bull, "BEARISH": bear, "NEUTRAL": neut}},
        current_position=Position.FLAT,
    )

# Signal mock: alternates BUY/SELL with varying confidence
signal_call_counter = [0]

def signal_side_effect(**kw):
    signal_call_counter[0] += 1
    # Alternate signals with moderate confidence to test threshold gating
    if signal_call_counter[0] % 3 == 0:
        return _make_signal(Signal.BUY, 0.55)  # borderline -- may be blocked by context
    elif signal_call_counter[0] % 3 == 1:
        return _make_signal(Signal.SELL, 0.60)
    else:
        return _make_signal(Signal.HOLD, 0.3)

regime_fn = MagicMock(side_effect=regime_side_effect)
context_fn = MagicMock(side_effect=context_side_effect)
signal_fn = MagicMock(side_effect=signal_side_effect)
signal_fn.confidence_threshold = 0.5

decision_fns = {
    "regime": regime_fn,
    "context": context_fn,
    "trend_signal": signal_fn,
    "range_signal": signal_fn,
}

mock_cache = MagicMock()
mock_cache.get_features_for_timestamp.return_value = {"f1": 0.5, "f2": 0.3}
caches = dict.fromkeys(decision_fns, mock_cache)

config = EnsembleConfiguration.from_yaml("configs/ensemble_context_gated.yaml")
backtest_config = BacktestConfig(
    strategy_config_path="", model_path=None,
    symbol="EURUSD", timeframe="1h",
    start_date="2024-01-01", end_date="2024-01-08",
    initial_capital=100000.0,
)
runner = EnsembleBacktestRunner(config, backtest_config)
router = RegimeRouter(config.composition)
pm = PositionManager(initial_capital=100000.0)

results = []
for idx in range(len(data)):
    bar = data.iloc[idx]
    result = runner._run_bar(
        timestamp=bar.name, bar=bar,
        feature_caches=caches, decision_functions=decision_fns,
        router=router, position_manager=pm,
    )
    results.append(result)
```

**Expected:** All 168 bars processed without error.
**Capture:** `results` list, call counts for all mocks.

#### Step 3: Verify Context Evaluation Frequency

```python
assert context_fn.call_count == 7, (
    f"Expected 7 context evaluations (7 days), got {context_fn.call_count}"
)
```

**Expected:** Context model called exactly 7 times (once per daily boundary).
**Capture:** `context_fn.call_count`

#### Step 4: Verify Regime Model Call Frequency

```python
assert regime_fn.call_count == 168, (
    f"Expected 168 regime evaluations (every bar), got {regime_fn.call_count}"
)
```

**Expected:** Regime model called every bar.
**Capture:** `regime_fn.call_count`

#### Step 5: Verify Regime Transitions

```python
transitions = [r for r in results if r.get("transition") is not None]
assert len(transitions) >= 2, (
    f"Expected at least 2 regime transitions, got {len(transitions)}"
)

# Verify transition details
transition_pairs = [(t["transition"].from_regime, t["transition"].to_regime) for t in transitions]
# With stability_bars=3, transitions happen after 3 consecutive bars of new regime
```

**Expected:** At least 2 transitions (trending_up->ranging, ranging->trending_down; volatile transition may or may not trigger depending on stability filter timing).
**Capture:** Transition pairs with from/to regimes.

#### Step 6: Verify Threshold Modification Math

```python
# Verify the threshold math for known inputs
from ktrdr.backtesting.regime_router import ThresholdModifier

# Bullish context: net_bias = 0.7 - 0.1 = 0.6
# aligned_discount=0.2, counter_premium=0.3
# long_factor = 1.0 - (0.6 * 0.2) = 0.88 (easier to go long)
# short_factor = 1.0 + (0.6 * 0.3) = 1.18 (harder to go short)

# Verify via RegimeRouter._compute_threshold_modifier
test_router = RegimeRouter(config.composition)
bullish_probs = {"bullish": 0.7, "bearish": 0.1, "neutral": 0.2}
modifier = test_router._compute_threshold_modifier(bullish_probs)
assert abs(modifier.long_factor - 0.88) < 0.001
assert abs(modifier.short_factor - 1.18) < 0.001

# Apply to base threshold of 0.5
assert abs(modifier.apply(0.5, Signal.BUY) - 0.44) < 0.001   # 0.5 * 0.88
assert abs(modifier.apply(0.5, Signal.SELL) - 0.59) < 0.001  # 0.5 * 1.18

# Bearish context: net_bias = 0.1 - 0.8 = -0.7
# long_factor = 1.0 + (0.7 * 0.3) = 1.21 (harder to go long)
# short_factor = 1.0 - (0.7 * 0.2) = 0.86 (easier to go short)
bearish_probs = {"bullish": 0.1, "bearish": 0.8, "neutral": 0.1}
modifier_b = test_router._compute_threshold_modifier(bearish_probs)
assert abs(modifier_b.long_factor - 1.21) < 0.001
assert abs(modifier_b.short_factor - 0.86) < 0.001
```

**Expected:** Threshold modifier math is deterministic and matches the formula.
**Capture:** Computed factors and applied thresholds.

#### Step 7: Run Regime-Only Pipeline (Backward Compatibility)

```python
reg_config = EnsembleConfiguration.from_yaml("configs/ensemble_regime_routed.yaml")
reg_backtest_config = BacktestConfig(
    strategy_config_path="", model_path=None,
    symbol="EURUSD", timeframe="1h",
    start_date="2024-01-01", end_date="2024-01-08",
    initial_capital=100000.0,
)
reg_runner = EnsembleBacktestRunner(reg_config, reg_backtest_config)

# Reset mocks
regime_fn.reset_mock()
regime_fn.side_effect = regime_side_effect
signal_fn_reg = MagicMock(side_effect=signal_side_effect)
signal_fn_reg.confidence_threshold = 0.5
signal_call_counter[0] = 0

reg_decision_fns = {
    "regime": regime_fn,
    "trend_signal": signal_fn_reg,
    "range_signal": signal_fn_reg,
}
reg_caches = dict.fromkeys(reg_decision_fns, mock_cache)

reg_router = RegimeRouter(reg_config.composition)
reg_pm = PositionManager(initial_capital=100000.0)

reg_results = []
for idx in range(len(data)):
    bar = data.iloc[idx]
    result = reg_runner._run_bar(
        timestamp=bar.name, bar=bar,
        feature_caches=reg_caches, decision_functions=reg_decision_fns,
        router=reg_router, position_manager=reg_pm,
    )
    reg_results.append(result)

# Verify no context state was set
assert reg_runner._current_context_probs is None
assert reg_runner._last_context_date is None
```

**Expected:** Regime-only pipeline completes without error, no context state set.
**Capture:** `reg_runner._current_context_probs`, `reg_runner._last_context_date`

#### Step 8: Compare Context-Gated vs Regime-Only

```python
ctx_signals = [r["signal"] for r in results if r["signal"] != Signal.HOLD]
reg_signals = [r["signal"] for r in reg_results if r["signal"] != Signal.HOLD]

# Context gating should change SOME signals (block counter-trend, allow aligned)
# The exact counts depend on mock sequence, but they should differ
# because threshold modification changes which signals pass

# Capture both for comparison
print(f"Context-gated non-HOLD signals: {len(ctx_signals)}")
print(f"Regime-only non-HOLD signals: {len(reg_signals)}")

# At minimum, both should have processed all bars
assert len(results) == 168
assert len(reg_results) == 168
```

**Expected:** Both pipelines process all bars. Signal counts may differ due to threshold gating.
**Capture:** Signal counts for both runs, specific bars where decisions diverge.

---

## Success Criteria

All must pass:

- [ ] Both YAML configs load and validate correctly
- [ ] Context-gated pipeline processes all 168 bars without error
- [ ] Context model called exactly 7 times (once per daily boundary)
- [ ] Regime model called exactly 168 times (every bar)
- [ ] At least 2 regime transitions detected
- [ ] Threshold modifier math is correct for bullish context (long_factor=0.88, short_factor=1.18)
- [ ] Threshold modifier math is correct for bearish context (long_factor=1.21, short_factor=0.86)
- [ ] ThresholdModifier.apply() produces correct adjusted thresholds
- [ ] Regime-only pipeline completes with no context state (both None)
- [ ] Regime-only pipeline has no "context" key in decision_fns

---

## Sanity Checks

**CRITICAL:** These catch false positives

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| context_fn.call_count == 7 | != 7 fails | Context not evaluated daily, or evaluated per-bar |
| regime_fn.call_count == 168 | != 168 fails | Regime model skipped or called extra |
| len(results) == 168 | != 168 fails | Bars skipped or duplicated |
| transitions >= 2 | < 2 fails | Stability filter broken or regime mock not varying |
| reg_runner._current_context_probs is None | not None fails | Regime-only runner incorrectly running context |
| At least 1 non-HOLD signal in context run | 0 fails | All signals blocked, pipeline not producing decisions |
| Execution time < 5s | > 5s fails | Something is hitting real I/O or hanging |
| ThresholdModifier factors != 1.0 | all 1.0 fails | Context modifiers not being applied |

---

## Failure Categorization

| Failure Type | Category | Suggested Action |
|--------------|----------|------------------|
| Config YAML not found | ENVIRONMENT | Run from repo root; check `configs/` directory exists |
| Config validation error | CODE_BUG | Check `EnsembleConfiguration` validators match YAML schema |
| Context called != 7 times | CODE_BUG | Check `_maybe_update_context()` daily boundary logic |
| Context called every bar | CODE_BUG | `_last_context_date` comparison not working |
| Context never called | CODE_BUG | `context_gate` not being read from config |
| Threshold math wrong | CODE_BUG | Check `_compute_threshold_modifier()` formula |
| No regime transitions | CODE_BUG | Check stability_bars filter in `RegimeRouter.route()` |
| Regime-only has context state | CODE_BUG | `_maybe_update_context` not checking for None context_gate |
| Import errors | ENVIRONMENT | Missing dependencies; run `uv sync` |

---

## Cleanup

None required. All objects are in-memory with no side effects.

---

## Notes for Implementation

- This test runs as a **local Python test** (pytest), not via HTTP API or Docker. No sandbox needed.
- The test uses `_run_bar()` directly rather than `run()` to avoid needing real model files, data repository, or feature cache computation. This is the same pattern used in the integration tests.
- The regime mock uses `call_count` to drive state transitions. Be careful with mock reset between Steps 2 and 7 -- the `call_count` must restart at 0 for the regime-only run.
- `signal_fn.confidence_threshold` must be set as an attribute on the mock because `_run_bar` reads it via `getattr(decision_functions[...], 'confidence_threshold', 0.5)`.
- The `Position.FLAT` used in `TradingDecision` constructor is from `ktrdr.decision.base.Position`, not `ktrdr.backtesting.position_manager.PositionStatus`. These are different enums.
- Context probabilities use lowercase keys (`bullish`, `bearish`, `neutral`) after `_interpret_context_output()` converts from uppercase NN output.
- The stability_bars=3 setting means regime transitions only happen after 3 consecutive bars of the new regime. With the mock changing at bar boundaries (every 48 bars), transitions should be confirmed by bar ~51, ~99, ~147.
- For the comparison step (Step 8), exact signal count differences are not asserted because the mock signal pattern interacts with position state (can't BUY when already LONG). The key assertion is that both pipelines run to completion and the context-gated one has context state while regime-only does not.
