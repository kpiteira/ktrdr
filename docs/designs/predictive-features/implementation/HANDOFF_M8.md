# M8 Handoff: Multi-Gate Context Integration

## Task 8.1 Complete: Extend EnsembleConfiguration with Context Gate

**Emergent patterns:**
- `ContextModifiers` uses Pydantic `BaseModel` (not dataclass) for consistency with rest of ensemble config
- `CompositionConfig.validate_context_gate()` auto-creates default `ContextModifiers()` when `context_gate` is set but modifiers are omitted — this simplifies YAML authoring

## Task 8.2 Complete: Build ThresholdModifier and Router Extension

**Implementation notes:**
- `ThresholdModifier` is a dataclass in `regime_router.py` with `apply(base_threshold, signal) → float`
- `_compute_threshold_modifier()` uses net_bias = bullish - bearish to drive asymmetric adjustments
- `RouteDecision.threshold_modifier` defaults to `None` via `field(default=None)` — all existing tests pass untouched

## Task 8.3 Complete: Extend EnsembleBacktestRunner with Context Evaluation

**Gotchas:**
- MagicMock has arbitrary attribute access — `getattr(mock, "confidence_threshold", 0.5)` returns MagicMock, not 0.5. Must explicitly set `mock.confidence_threshold = 0.5` in tests
- `_maybe_update_context()` needs position and bar args for DecisionFunction call signature

## Task 8.4 Complete: Run Context-Gated Ensemble Backtest

**Implementation notes:**
- Created `configs/ensemble_context_gated.yaml` with regime + context + 2 signal models
- Integration tests validate: daily context eval, context→router flow, counter-trend blocking, regime-only backward compat

## Task 8.5 Complete: Validation (Real E2E)

**Bugs found & fixed:**
1. **Multi-TF data loading**: `run()` only loaded base 1h data. Context model (1d) failed with "No features computed." Fixed by collecting all required timeframes from `bundle.metadata.training_timeframes`.
2. **Equity short-from-flat filter**: Classification models blocked all SELL signals from FLAT position — inappropriate for forex pairs. Added `allow_short_from_flat` config option to `CompositionConfig` and `DecisionFunction`, injected by runner for signal models.
3. **Context gate inert for regression models**: Original ThresholdModifier only adjusted `confidence_threshold` (classification). Regression models skip confidence threshold entirely, using `trade_threshold = round_trip_cost * min_edge_multiplier`. Extended `_run_bar()` to detect `output_format == "regression"` and adjust `trade_threshold` instead — re-evaluates `predicted_return` against context-adjusted buy/sell thresholds.

**Regression signal models trained:**
- `trend_regression_signal`: RSI/ADX/MACD/ROC → forward_return horizon=12, Huber loss, 80 epochs
- `range_regression_signal`: Stochastic/WilliamsR/RSI/BBWidth → forward_return horizon=8, Huber loss, 80 epochs
- Both use cost_model: rtc=0.0002, mem=2.0, trade_threshold=0.0004

**Key E2E results with regression models (EURUSD Jan-Jun 2024, 2358 bars):**
- Context-gated: **15 trades** vs Regime-only: **18 trades** — context gate blocked 3 counter-trend shorts
- All 3 blocked trades in trending_down regime where bullish context (67.4%) raised SELL threshold
- 95 daily context evaluations, 139 regime transitions
- E2E test: `backtesting/regression-context-gated-ensemble` — PASSED
