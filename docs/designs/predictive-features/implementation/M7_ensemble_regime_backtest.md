---
design: docs/designs/predictive-features/regime-detection/DESIGN.md
architecture: docs/designs/predictive-features/regime-detection/ARCHITECTURE.md
---

# M7: Ensemble + Regime Backtest

**Thread:** Regime Detection
**JTBD:** "As a trader, I want to run a regime-routed ensemble backtest with per-regime signal models so I can compare routed vs unrouted performance."
**Depends on:** M4 (Regime Classifier)
**Tasks:** 7

---

## Task 7.1: Build EnsembleConfiguration

**File(s):**
- `ktrdr/config/ensemble_config.py` (new)

**Type:** CODING
**Estimated time:** 3 hours

**Description:**
Build the ensemble configuration model: `ModelReference`, `RouteRule`, `CompositionConfig`, and `EnsembleConfiguration`. Supports loading from YAML files and validation (all model references resolve, all regime routes have targets, gate_model exists).

**Implementation Notes:**
- Use Pydantic models (consistent with existing config patterns)
- `ModelReference`: `name`, `model_path`, `output_type`
- `RouteRule`: `model: str | None`, `action: str | None` — mutually exclusive
- `CompositionConfig`: `type` (only "regime_route" for now), `gate_model`, `regime_threshold` (default 0.4), `stability_bars` (default 3), `rules`, `on_regime_transition` ("close_and_switch" | "let_run")
- `EnsembleConfiguration`: `name`, `description`, `models`, `composition`
- Validation: every model in `rules` must exist in `models`, `gate_model` must exist, `gate_model`'s `output_type` must be `regime_classification`
- YAML loader: `EnsembleConfiguration.from_yaml(path)` and `EnsembleConfiguration.from_dict(data)`
- See architecture doc Section 2.2 for example YAML

**Testing Requirements:**
- [ ] Valid ensemble YAML loads without errors
- [ ] Missing model reference in route rule raises validation error
- [ ] Missing gate_model raises validation error
- [ ] Invalid `on_regime_transition` value raises error
- [ ] RouteRule with both `model` and `action` raises error
- [ ] Serialization round-trip (dict → config → dict)

**Acceptance Criteria:**
- [ ] `EnsembleConfiguration` loads from YAML
- [ ] All validation rules enforced
- [ ] Matches architecture doc Section 2.2 schema

---

## Task 7.2: Build RegimeRouter

**File(s):**
- `ktrdr/backtesting/regime_router.py` (new)

**Type:** CODING
**Estimated time:** 3 hours

**Description:**
Build `RegimeRouter` that determines the active regime from probability output, applies stability filter, handles transitions, and returns `RouteDecision`. The stability filter requires N consecutive bars of new regime before transitioning — prevents costly flicker (Scenario 7 in architecture doc).

**Implementation Notes:**
- `route(regime_probs, previous_regime, current_position)` → `RouteDecision`
- Determine dominant regime: highest probability above `regime_threshold`. If none above threshold, default to "volatile" (most conservative)
- **Stability filter:** Track `_pending_regime` and `_regime_counter`. When proposed regime differs from current: start counting. Only transition after `stability_bars` consecutive bars of new regime. Reset counter if regime flickers back.
- Transition handling: if regime changed (after stability), create `TransitionAction` based on `on_regime_transition`:
  - `close_and_switch`: `TransitionAction(close_position=True, from_regime, to_regime)`
  - `let_run`: `TransitionAction(close_position=False, from_regime, to_regime)`
- Route lookup: `rules[active_regime]` → model name or forced action
- See architecture doc Section 2.4 for `RouteDecision`, `TransitionAction` dataclasses

**Testing Requirements:**
- [ ] Dominant regime correctly identified from probabilities
- [ ] Below-threshold probabilities default to volatile
- [ ] Stability filter prevents transition before N consecutive bars
- [ ] Stability filter allows transition after N consecutive bars
- [ ] Flicker resets counter (A→B for 2 bars → back to A → counter resets)
- [ ] `close_and_switch` creates TransitionAction with `close_position=True`
- [ ] `let_run` creates TransitionAction with `close_position=False`
- [ ] Route returns correct model for each regime
- [ ] FLAT action routes return `active_model=None`

**Acceptance Criteria:**
- [ ] RegimeRouter correctly routes based on regime probabilities
- [ ] Stability filter prevents costly flicker
- [ ] Transition handling matches architecture doc policies

---

## Task 7.3: Generalize DecisionFunction to N-Class

**File(s):**
- `ktrdr/backtesting/decision_function.py` (generalize from 3-class to N-class)

**Type:** CODING
**Estimated time:** 2 hours

**Description:**
The existing `DecisionFunction` is hardcoded to 3-class output (`_SIGNAL_MAP = {0: BUY, 1: HOLD, 2: SELL}` at line 28-29, probabilities dict at lines 196-219). Generalize to N-class. For 3-class (backward compat): BUY/HOLD/SELL. For 4-class regime: TRENDING_UP/TRENDING_DOWN/RANGING/VOLATILE. For 3-class context: BULLISH/BEARISH/NEUTRAL.

**Implementation Notes:**
- Make `_SIGNAL_MAP` configurable based on `output_type` from model metadata
- Default 3-class map: `{0: BUY, 1: HOLD, 2: SELL}` (backward compatible)
- Regime 4-class map: `{0: TRENDING_UP, 1: TRENDING_DOWN, 2: RANGING, 3: VOLATILE}`
- Context 3-class map: `{0: BULLISH, 1: BEARISH, 2: NEUTRAL}`
- The probabilities dict should use class names from the map, not hardcoded BUY/HOLD/SELL
- Signal detection (line ~208): `signal_idx = int(np.argmax(probs))` — this already works for any N
- The key change is the probabilities dict construction and the signal mapping
- **All existing 3-class tests must pass unchanged** — this is the biggest risk

**Testing Requirements:**
- [ ] 3-class output produces BUY/HOLD/SELL (existing behavior, no regression)
- [ ] 4-class output produces regime labels with correct probabilities dict
- [ ] 3-class context output produces BULLISH/BEARISH/NEUTRAL
- [ ] argmax works correctly for 4-class
- [ ] Confidence threshold applies correctly for N-class

**Acceptance Criteria:**
- [ ] DecisionFunction handles any N-class output
- [ ] Existing 3-class backtests produce identical results (regression test)
- [ ] Regime and context output types produce correctly labeled decisions

---

## Task 7.4: Build EnsembleBacktestRunner

**File(s):**
- `ktrdr/backtesting/ensemble_runner.py` (new)

**Type:** CODING
**Estimated time:** 4 hours

**Description:**
Build `EnsembleBacktestRunner` that orchestrates multi-model backtesting. Loads all model bundles, creates per-model FeatureCaches, creates RegimeRouter, runs per-bar loop with regime classification → routing → signal model → position management. Shares one PositionManager across all regime-routed models.

**Implementation Notes:**
- Constructor: takes `EnsembleConfiguration` + `BacktestConfig`
- `run()`: async method returning `EnsembleBacktestResults`
- `_load_models()`: load `ModelBundle` for each model in config
- `_create_feature_caches()`: one `FeatureCache` per model (each has different indicators/features)
- Per-bar loop (architecture doc Section 2.3 / Section 4.3):
  1. Get regime features → run regime model → get 4-class probabilities
  2. `router.route(regime_probs, previous_regime, position)` → RouteDecision
  3. If transition with `close_position=True`: `position_manager.execute_trade()` to close
  4. If `active_model` is not None: get signal features → run signal model → get decision
  5. If `active_model` is None (FLAT route): hold
  6. `position_manager.execute_trade()` for signal decision
- Use existing `PositionManager` (at `ktrdr/backtesting/position_manager.py`) — single instance shared
- Use existing `FeatureCache` pattern — one per model
- `EnsembleBacktestResults`: extends backtest results with per-regime metrics (trades per regime, accuracy, transition count, transition cost)

**Testing Requirements:**
- [ ] Loads all model bundles from config
- [ ] Creates separate FeatureCache per model
- [ ] Regime model runs every bar
- [ ] Router correctly determines active model
- [ ] Transition closes position via `execute_trade()`
- [ ] Signal model runs only when route has active_model
- [ ] FLAT route produces HOLD decision
- [ ] Single PositionManager shared across models
- [ ] Results include per-regime breakdown

**Acceptance Criteria:**
- [ ] Full ensemble backtest runs end-to-end with regime routing
- [ ] Per-regime performance metrics in results
- [ ] Transition costs tracked

---

## Task 7.5: Wire Ensemble Backtest to CLI

**File(s):**
- `ktrdr/cli/commands/ensemble.py` (new or extend backtest command)
- `ktrdr/cli/app.py` (register)

**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Add CLI command to run ensemble backtests: `ktrdr ensemble backtest <ensemble_config.yaml> --start-date ... --end-date ...`. Loads ensemble config, runs EnsembleBacktestRunner, prints results with per-regime breakdown.

**Implementation Notes:**
- Ensemble config is a YAML file (separate from strategy YAMLs)
- The command loads the config, creates BacktestConfig with date params, runs the ensemble runner
- Output: overall performance metrics + per-regime breakdown (trades, P&L, accuracy)
- Follow existing CLI patterns — use Rich tables, async client if needed
- Consider: should this also be available via API endpoint? Defer to M10 unless needed sooner.

**Testing Requirements:**
- [ ] CLI command loads ensemble config YAML
- [ ] Missing config file gives clear error
- [ ] Output includes overall and per-regime metrics
- [ ] Date parameters work correctly

**Acceptance Criteria:**
- [ ] `ktrdr ensemble backtest config.yaml --start-date ... --end-date ...` runs successfully
- [ ] Results displayed with per-regime breakdown

---

## Task 7.6: Run Full Regime-Routed Backtest

**File(s):** None (execution/evaluation task)
**Type:** MIXED
**Estimated time:** 3 hours

**Description:**
Train per-regime signal models (or use existing ones), create ensemble config, run the full regime-routed backtest. Compare vs single unrouted model baseline.

**Implementation Notes:**
- Need at least 3 signal models: trend_long, trend_short (or same as trend_long), mean_reversion
- These can be existing models or newly trained with different strategy configs
- Ensemble config references: regime classifier (from M4) + signal models
- Compare: ensemble Sharpe vs single-model Sharpe, win rate, max drawdown
- Track transition costs explicitly — if transitions are too frequent/costly, regime approach may not help
- This is where the hypothesis is truly tested

**Acceptance Criteria:**
- [ ] Full ensemble backtest completes with regime + signal models
- [ ] Per-regime performance breakdown available
- [ ] Comparison vs single unrouted model documented
- [ ] Transition costs quantified

---

## Task 7.7: Validation

**File(s):** None (validation task)
**Type:** VALIDATION
**Estimated time:** 2 hours

**Description:**
Validate ensemble backtest end-to-end.

**Validation Steps:**
1. Load the `ke2e` skill before designing any validation
2. Invoke `ke2e-test-scout` with: "Run a regime-routed ensemble backtest using a regime classifier and per-regime signal models. Verify the ensemble produces trades, routes to different models based on regime, and generates per-regime performance metrics."
3. Invoke `ke2e-test-runner` with the identified test recipes
4. Tests must exercise real infrastructure — real models, real backtest engine
5. Verify: ensemble runs, multiple models used, per-regime metrics in results, transition events logged

**Acceptance Criteria:**
- [ ] Ensemble backtest completes end-to-end
- [ ] Multiple signal models were used (not just one)
- [ ] Per-regime breakdown shows different trading patterns
- [ ] Transition events recorded with costs
- [ ] Results include comparison metrics
