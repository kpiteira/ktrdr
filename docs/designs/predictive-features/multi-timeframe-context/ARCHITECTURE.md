# Multi-Timeframe Context ("Cortex"): Architecture

## Status: Design
## Date: 2026-03-07

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   EnsembleBacktestRunner                     │
│                                                             │
│  Per daily bar close:                                       │
│    Context Model → context_probs                            │
│      {bullish: 0.65, neutral: 0.25, bearish: 0.10}         │
│                                                             │
│  Per hourly bar:                                            │
│    Regime Model → regime_probs                              │
│      {trending_up: 0.7, trending_down: 0.1,                │
│       ranging: 0.15, volatile: 0.05}                        │
│                                                             │
│    RegimeRouter.route(regime_probs, context_probs, ...)     │
│      → active_model: trend_long                             │
│      → threshold_modifier: {long: 0.48, short: 0.72}       │
│                                                             │
│    Signal Model (trend_long) → direction + confidence       │
│      confidence (0.55) > adjusted_threshold (0.48)?         │
│      → YES → BUY                                           │
│                                                             │
│    PositionManager.execute()                                │
└─────────────────────────────────────────────────────────────┘
```

Three independent brain regions, one composition point:

| Brain Region | Model | Timescale | Output | Update |
|---|---|---|---|---|
| Regime (Thread 1) | RegimeClassifier | Same as signal (1h) | 4 soft probs | Every bar |
| Context (Thread 2) | ContextClassifier | Higher TF (1d) | 3 soft probs | On daily close |
| Signal (per-regime) | SignalModel | Same as signal (1h) | direction + confidence | Every bar |

---

## 2. Backtest Multi-TF Plumbing Fix (M1)

### 2.1 Current Flow (Broken)

```
API Request (timeframe: "1h")
  → BacktestingService (timeframe: "1h")
    → Worker (timeframe: "1h")
      → BacktestConfig(timeframe: "1h")
        → Engine loads data for "1h" only
          → FeatureCache expects ["1h", "1d"] features
            → KeyError: "1d"
```

### 2.2 Target Flow (Fixed)

```
API Request (strategy_name: "multi_tf_v1")
  → API reads strategy config → timeframes: ["1h", "1d"], base: "1h"
    → BacktestingService (timeframes: ["1h", "1d"], timeframe: "1h")
      → Worker (timeframes: ["1h", "1d"], timeframe: "1h")
        → BacktestConfig(timeframes: ["1h", "1d"], timeframe: "1h")
          → Engine loads data via MultiTimeframeCoordinator
            → data = {"1h": DataFrame, "1d": DataFrame(forward-filled)}
              → FeatureCache.compute_features(data) → Success
```

### 2.3 Components Changed

| File | Change |
|------|--------|
| `ktrdr/api/endpoints/backtesting.py` | Extract full timeframes list from strategy config, forward to service |
| `ktrdr/backtesting/backtesting_service.py` | Add `timeframes` to worker request payload |
| `ktrdr/backtesting/backtest_worker.py` | Add `timeframes: list[str]` field + `get_all_timeframes()` helper |
| `ktrdr/backtesting/engine.py` | Add `timeframes` to `BacktestConfig` + multi-TF data loading |
| `ktrdr/backtesting/remote_api.py` | Forward `timeframes` in remote backtest requests |

**No changes to:** FeatureCache, IndicatorEngine, FuzzyEngine, MultiTimeframeCoordinator, FeatureResolver.

### 2.4 Backward Compatibility

```python
@dataclass
class BacktestConfig:
    timeframe: str                          # Base timeframe (kept for compat)
    timeframes: list[str] = field(default_factory=list)

    def get_all_timeframes(self) -> list[str]:
        return self.timeframes if self.timeframes else [self.timeframe]
```

Single-TF strategies work unchanged. `get_all_timeframes()` falls back to `[timeframe]`.

---

## 3. Context Labeler (M2)

### 3.1 Labeling Method

Forward-looking signed return over H daily bars:

```python
class ContextLabeler:
    def __init__(
        self,
        horizon: int = 5,              # Daily bars to look ahead
        bullish_threshold: float = 0.005,   # +0.5% = bullish
        bearish_threshold: float = -0.005,  # -0.5% = bearish
    ):
        ...

    def label(self, daily_ohlcv: pd.DataFrame) -> pd.Series:
        """Generate context labels from daily OHLCV.

        Returns Series of integers: 0=BULLISH, 1=BEARISH, 2=NEUTRAL
        """
        forward_return = (
            daily_ohlcv["close"].shift(-self.horizon) - daily_ohlcv["close"]
        ) / daily_ohlcv["close"]

        labels = pd.Series(2, index=daily_ohlcv.index)  # Default NEUTRAL
        labels[forward_return > self.bullish_threshold] = 0   # BULLISH
        labels[forward_return < self.bearish_threshold] = 1   # BEARISH
        return labels
```

### 3.2 Why Forward-Looking

Same principle as Thread 1: **labels must use future information to be honest.** A labeler using current EMA slope to define "bullish" is circular — you'd train a model to predict what you can already compute. Forward-looking labels define "in hindsight, was this a bullish period?" The model succeeds only if current indicators contain genuine information about forward trend direction.

### 3.3 Validation Metrics

```
Context Labeler Report — EURUSD 1d (2020-01-01 to 2025-01-01)
────────────────────────────────────────────────────────────────
Distribution:
  Bullish:  35.2%  (457 days)
  Neutral:  28.6%  (371 days)
  Bearish:  36.2%  (470 days)

Persistence:
  Mean duration (bullish):   8.3 days
  Mean duration (neutral):   4.1 days
  Mean duration (bearish):   7.9 days

Return by Context (hourly bars during each context):
  Bullish context:  mean hourly return = +0.0012%  (positive ✓)
  Neutral context:  mean hourly return = -0.0001%  (near zero ✓)
  Bearish context:  mean hourly return = -0.0010%  (negative ✓)

Correlation with Regime Labels: 0.18  (low → complementary ✓)
```

**Gate:** If persistence <3 days or returns don't differentiate by context, the hypothesis is falsified.

---

## 4. Context Model (M3)

### 4.1 Seed Strategy

**Note:** The ideal context indicator is "EMA slope" (rate of change of EMA), but this doesn't exist as a standalone indicator. We can approximate it using ROC (Rate of Change) applied to price directly, combined with EMA crossover patterns. A purpose-built `ema_slope` indicator (difference between current and N-bars-ago EMA, normalized) may be worth adding during M3 implementation — it's a simple ~50-line indicator. For now, the seed uses existing indicators.

```yaml
name: context_classifier_seed_v1
version: "3.0"
description: Daily trend context classifier

training_data:
  symbols:
    mode: single
    symbol: EURUSD
  timeframes:
    mode: single
    timeframe: "1d"
  history_required: 200

indicators:
  roc_10:
    type: roc             # Rate of change — proxy for trend direction
    period: 10
  roc_20:
    type: roc
    period: 20
  adx_14:
    type: adx             # Trend strength (direction-agnostic)
    period: 14
  rsi_14:
    type: rsi             # Daily momentum level
    period: 14
  ema_20:
    type: ema             # Price position relative to trend
    period: 20

fuzzy_sets:
  short_momentum:
    indicator: roc_10
    bearish: [-2, -0.5, 0]
    neutral: [-0.3, 0, 0.3]
    bullish: [0, 0.5, 2]
  long_momentum:
    indicator: roc_20
    bearish: [-3, -1, 0]
    neutral: [-0.5, 0, 0.5]
    bullish: [0, 1, 3]
  trend_strength:
    indicator: adx_14
    weak: [0, 10, 20]
    moderate: [15, 25, 35]
    strong: [30, 45, 60]
  daily_rsi:
    indicator: rsi_14
    oversold: [0, 30, 45]
    neutral: [40, 50, 60]
    overbought: [55, 70, 100]

nn_inputs:
  - fuzzy_set: short_momentum
    timeframes: ["1d"]
  - fuzzy_set: long_momentum
    timeframes: ["1d"]
  - fuzzy_set: trend_strength
    timeframes: ["1d"]
  - fuzzy_set: daily_rsi
    timeframes: ["1d"]

model:
  type: mlp
  architecture:
    hidden_layers: [64, 32]
    activation: relu
    # Note: do NOT specify output_activation: softmax — the MLP applies softmax
    # implicitly via cross-entropy loss (log-softmax). Specifying it here would
    # cause double-softmax. Verify during M3 implementation.
    dropout: 0.2
  training:
    learning_rate: 0.001
    epochs: 100
    early_stopping:
      enabled: true
      patience: 15

decisions:
  output_format: classification
  confidence_threshold: 0.4    # Lower threshold — context is a gate, not a signal

training:
  labels:
    source: context
    horizon: 5
    bullish_threshold: 0.005
    bearish_threshold: -0.005
  loss: cross_entropy
```

### 4.2 Training Pipeline Integration

Wire `labels.source: context` as a new label source, following Thread 1's pattern for `labels.source: regime`.

**Important:** Label source dispatch must be updated in BOTH locations:
1. `ktrdr/training/training_pipeline.py` (container workers)
2. `training-host-service/orchestrator.py` (host service — has its own separate dispatch code)

We hit this exact dual-dispatch bug before with `forward_return` labels. The host service is always preferred for training, so missing it means the fix silently doesn't apply.

```python
# In label generation dispatch (BOTH training_pipeline.py AND orchestrator.py):
if config.labels.source == "regime":
    labeler = RegimeLabeler(...)
elif config.labels.source == "context":
    labeler = ContextLabeler(
        horizon=config.labels.horizon,
        bullish_threshold=config.labels.bullish_threshold,
        bearish_threshold=config.labels.bearish_threshold,
    )
```

Output: 3-class labels (0=bullish, 1=bearish, 2=neutral) for cross-entropy training.

### 4.3 Model Metadata

The trained context model stores `output_type: context_classification` in its metadata, analogous to Thread 1's `output_type: regime_classification`. The ensemble loader uses this to identify the context model.

---

## 5. Multi-Gate Router Extension (M4)

### 5.1 Extended EnsembleConfiguration

```yaml
name: regime_context_ensemble_v1
models:
  regime:
    model_path: models/regime_classifier_v1
    output_type: regime_classification
  context:
    model_path: models/context_classifier_v1
    output_type: context_classification
  trend_long:
    model_path: models/trend_follower_long_v1
    output_type: classification
  trend_short:
    model_path: models/trend_follower_short_v1
    output_type: classification
  mean_reversion:
    model_path: models/range_trader_v1
    output_type: classification

composition:
  type: regime_route
  gate_model: regime
  context_gate: context           # NEW — optional second gate
  regime_threshold: 0.4

  context_modifiers:              # NEW — threshold adjustment rules
    aligned_discount: 0.2         # Reduce threshold by 20% for aligned trades
    counter_premium: 0.3          # Increase threshold by 30% for counter-trend
    neutral_effect: 0.05          # Minimal effect in neutral context

  rules:
    trending_up:    { model: trend_long }
    trending_down:  { model: trend_short }
    ranging:        { model: mean_reversion }
    volatile:       { action: FLAT }
  on_regime_transition: close_and_switch
```

### 5.2 Router Extension

```python
class RegimeRouter:
    def route(
        self,
        regime_probs: dict[str, float],
        previous_regime: str | None,
        current_position: PositionStatus,
        context_probs: dict[str, float] | None = None,  # NEW
    ) -> RouteDecision:
        """Route based on regime, optionally modified by context."""

        # 1. Existing regime routing (unchanged)
        active_regime = self._determine_regime(regime_probs)
        transition = self._check_transition(active_regime, previous_regime)
        rule = self.config.rules[active_regime]

        # 2. NEW: Compute context-based threshold modifier
        threshold_modifier = None
        if context_probs and self.config.context_modifiers:
            threshold_modifier = self._compute_threshold_modifier(
                context_probs=context_probs,
                active_regime=active_regime,
            )

        return RouteDecision(
            active_regime=active_regime,
            active_model=rule.model,
            transition=transition,
            threshold_modifier=threshold_modifier,  # NEW
        )

    def _compute_threshold_modifier(
        self,
        context_probs: dict[str, float],
        active_regime: str,
    ) -> ThresholdModifier:
        """Compute direction-specific threshold adjustments."""

        # Dominant context and its confidence
        bullish_conf = context_probs.get("bullish", 0)
        bearish_conf = context_probs.get("bearish", 0)
        neutral_conf = context_probs.get("neutral", 0)

        mods = self.config.context_modifiers

        # Net directional bias: positive = bullish, negative = bearish
        net_bias = bullish_conf - bearish_conf  # Range: [-1, +1]

        if net_bias > 0:  # Bullish context
            long_factor = 1 - (net_bias * mods.aligned_discount)
            short_factor = 1 + (net_bias * mods.counter_premium)
        else:  # Bearish context
            long_factor = 1 + (abs(net_bias) * mods.counter_premium)
            short_factor = 1 - (abs(net_bias) * mods.aligned_discount)

        return ThresholdModifier(
            long_factor=long_factor,    # Multiply base threshold
            short_factor=short_factor,
        )
```

### 5.3 ThresholdModifier

```python
@dataclass
class ThresholdModifier:
    long_factor: float   # Multiply base threshold for long trades
    short_factor: float  # Multiply base threshold for short trades

    def apply(self, base_threshold: float, direction: str) -> float:
        if direction == "BUY":
            return base_threshold * self.long_factor
        elif direction == "SELL":
            return base_threshold * self.short_factor
        return base_threshold
```

### 5.4 Signal Model Decision with Context

In `EnsembleBacktestRunner`, after the signal model produces a decision:

```python
# Signal model output
signal_decision = decision_functions[active_model](features, position, bar)

# Apply context-adjusted threshold
if route_result.threshold_modifier:
    adjusted_threshold = route_result.threshold_modifier.apply(
        base_threshold=model_config.confidence_threshold,
        direction=signal_decision.direction,
    )
    if signal_decision.confidence < adjusted_threshold:
        final_decision = TradingDecision(HOLD, reasoning="below context-adjusted threshold")
    else:
        final_decision = signal_decision
else:
    # No context gate — use base threshold as before
    final_decision = signal_decision
```

---

## 6. EnsembleBacktestRunner Extension (M4)

### 6.1 Context Evaluation Timing

Context is evaluated **once per daily bar close**, not every hourly bar. The runner tracks when the daily bar has changed:

```python
class EnsembleBacktestRunner:
    def __init__(self, ...):
        self._current_context_probs: dict[str, float] | None = None
        self._last_context_date: date | None = None

    def _maybe_update_context(self, timestamp: pd.Timestamp) -> None:
        """Re-evaluate context model when daily bar closes."""
        bar_date = timestamp.date()
        if self._last_context_date is None or bar_date > self._last_context_date:
            context_features = self._context_cache.get_features_for_timestamp(timestamp)
            if context_features:
                context_decision = self._context_decision_fn(context_features, ...)
                self._current_context_probs = {
                    "bullish": context_decision.probabilities[0],
                    "neutral": context_decision.probabilities[2],
                    "bearish": context_decision.probabilities[1],
                }
            self._last_context_date = bar_date
```

### 6.2 Per-Bar Flow (Extended)

```python
for bar in bars:
    # 1. Update context if daily bar closed (NEW)
    self._maybe_update_context(bar.timestamp)

    # 2. Regime classification (unchanged)
    regime_features = regime_cache.get_features_for_timestamp(bar.timestamp)
    regime_probs = regime_model(regime_features)

    # 3. Route with context (EXTENDED)
    route_result = router.route(
        regime_probs=regime_probs,
        context_probs=self._current_context_probs,  # NEW
        previous_regime=previous_regime,
        current_position=position,
    )

    # 4. Regime transition handling (unchanged)
    if route_result.transition and route_result.transition.close_position:
        position_manager.execute_trade(close_signal, bar)  # Note: use execute_trade(), not close_position()

    # 5. Signal model (unchanged)
    if route_result.active_model:
        signal_features = signal_cache.get_features(bar.timestamp)
        signal_decision = signal_model(signal_features)

    # 6. Apply context-modified threshold (NEW)
    if route_result.threshold_modifier:
        adjusted_threshold = route_result.threshold_modifier.apply(
            base_threshold, signal_decision.direction)
        if signal_decision.confidence < adjusted_threshold:
            signal_decision = TradingDecision(HOLD)

    # 7. Execute (unchanged)
    position_manager.process_decision(signal_decision, bar)
```

---

## 7. Data Flow: Multi-Timeframe Alignment

Already implemented in `MultiTimeframeCoordinator` and `TimeframeSynchronizer`:

```
Input:
  1h bars:  [09:00, 10:00, 11:00, ..., 16:00]  (24 bars/day)
  1d bars:  [2024-01-15, 2024-01-16, ...]       (1 bar/day)

Alignment (forward-fill 1d → 1h grid):
  09:00  1h_data=bar1   1d_data=yesterday's_close  ← no lookahead
  10:00  1h_data=bar2   1d_data=yesterday's_close
  ...
  (after daily close)
  09:00  1h_data=bar25  1d_data=today's_close       ← updated
```

The daily context model sees yesterday's completed daily bar — no lookahead bias.

---

## 8. File Impact Summary

### M1 (Backtest Plumbing)
| File | Change | Size |
|------|--------|------|
| `ktrdr/api/endpoints/backtesting.py` | Forward full timeframes list | S |
| `ktrdr/backtesting/backtesting_service.py` | Add `timeframes` to worker payload | S |
| `ktrdr/backtesting/backtest_worker.py` | Add `timeframes` field | S |
| `ktrdr/backtesting/engine.py` | Multi-TF data loading | M |
| `ktrdr/backtesting/remote_api.py` | Forward `timeframes` | S |

### M2 (Context Labeler)
| File | Change | Size |
|------|--------|------|
| `ktrdr/training/context_labeler.py` | New: ContextLabeler class | M |
| `ktrdr/cli/commands/context.py` | New: `ktrdr context analyze` CLI | M |

### M3 (Context Model Training)
| File | Change | Size |
|------|--------|------|
| `ktrdr/training/training_pipeline.py` | Wire `labels.source: context` | S |
| `training-host-service/orchestrator.py` | Wire `labels.source: context` (dual-dispatch!) | S |
| `ktrdr/models/model_metadata.py` | Add `context_classification` output type | S |
| `strategies/context_classifier_seed_v1.yaml` | New: seed strategy | S |

### M4 (Multi-Gate Integration)
| File | Change | Size |
|------|--------|------|
| `ktrdr/backtesting/ensemble_config.py` | Add `context_gate`, `context_modifiers` | M |
| `ktrdr/backtesting/regime_router.py` | Add context_probs param + threshold modifier | M |
| `ktrdr/backtesting/ensemble_runner.py` | Context evaluation timing + per-bar flow | M |

### M5 (Researcher Integration)
| File | Change | Size |
|------|--------|------|
| Agent prompts and assessment templates | Context-aware evaluation | M |

---

## 9. Dependencies

```
Thread 1 (Regime Detection)          Thread 2 (Multi-TF Context)
─────────────────────────────        ────────────────────────────
M1: RegimeLabeler                    M1: Backtest Multi-TF Fix
M2: Regime Classifier                M2: Context Labeler
M3: Ensemble Architecture ──────┐   M3: Context Classifier
M4: Full Regime Backtest         │   M4: Multi-Gate Integration ◄──┘
M5: Agent Integration            │   M5: Researcher Integration
                                 │
                                 └── M4 depends on Thread 1 M3
                                     (ensemble architecture must exist)
```

Thread 2 M1-M3 can proceed independently of Thread 1. Thread 2 M4 (multi-gate integration) requires Thread 1 M3 (ensemble architecture) to be built first.
