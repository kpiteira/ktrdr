---
design: docs/designs/predictive-features/multi-timeframe-context/DESIGN.md
architecture: docs/designs/predictive-features/multi-timeframe-context/ARCHITECTURE.md
---

# M8: Multi-Gate Context Integration

**Thread:** Multi-TF Context
**JTBD:** "As a trader, I want daily trend context to adjust my trading aggressiveness so I trade with the macro trend, not against it — and I can compare this vs regime-only performance."
**Depends on:** M7 (Ensemble + Regime Backtest), M5 (Context Classifier)
**Tasks:** 5

---

## Task 8.1: Extend EnsembleConfiguration with Context Gate

**File(s):**
- `ktrdr/config/ensemble_config.py` (add `context_gate` and `context_modifiers` to `CompositionConfig`)

**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Add optional context gate to `CompositionConfig`: `context_gate: Optional[str]` (references a model in the ensemble), and `context_modifiers: Optional[ContextModifiers]` with `aligned_discount`, `counter_premium`, `neutral_effect` parameters.

**Implementation Notes:**
- `context_gate` is optional — ensemble works without it (regime-only), matching M7 behavior
- `ContextModifiers` dataclass: `aligned_discount: float = 0.2`, `counter_premium: float = 0.3`, `neutral_effect: float = 0.05`
- Validation: if `context_gate` is set, it must reference a model with `output_type: context_classification`
- If `context_gate` is set, `context_modifiers` must also be set (or use defaults)
- See architecture doc Section 5.1 for example YAML with context gate

**Testing Requirements:**
- [ ] Ensemble without `context_gate` works unchanged (backward compat)
- [ ] `context_gate` referencing non-existent model raises error
- [ ] `context_gate` referencing non-context model raises error
- [ ] Default modifier values used when not specified
- [ ] Custom modifier values override defaults

**Acceptance Criteria:**
- [ ] Context gate is optional extension of existing ensemble config
- [ ] Validation enforces correct output_type for context model
- [ ] Backward compatible with regime-only ensembles

---

## Task 8.2: Build ThresholdModifier and Router Extension

**File(s):**
- `ktrdr/backtesting/regime_router.py` (extend with context support)

**Type:** CODING
**Estimated time:** 3 hours

**Description:**
Add `ThresholdModifier` dataclass and extend `RegimeRouter.route()` to accept optional `context_probs`. When context is provided, compute direction-specific threshold adjustments: bullish context lowers long thresholds (aligned discount), raises short thresholds (counter premium), and vice versa.

**Implementation Notes:**
- `ThresholdModifier`: `long_factor: float`, `short_factor: float`, `apply(base_threshold, direction) → float`
- `route()` gains optional `context_probs: dict[str, float] | None` parameter
- `_compute_threshold_modifier()`: net_bias = bullish_conf - bearish_conf. If positive (bullish): long_factor = 1 - (net_bias * aligned_discount), short_factor = 1 + (net_bias * counter_premium). If negative (bearish): reverse.
- `RouteDecision` gains `threshold_modifier: ThresholdModifier | None`
- Without context_probs: `threshold_modifier` is None (existing behavior preserved)
- See architecture doc Section 5.2-5.3 for implementation detail

**Testing Requirements:**
- [ ] Without context_probs: route returns no threshold_modifier (backward compat)
- [ ] Bullish context: long_factor < 1.0 (lower threshold), short_factor > 1.0 (higher threshold)
- [ ] Bearish context: long_factor > 1.0, short_factor < 1.0
- [ ] Neutral context (0.5/0.5): factors near 1.0 (minimal effect)
- [ ] Strong bullish (0.9/0.1): large discount/premium
- [ ] `ThresholdModifier.apply()` correctly multiplies base threshold

**Acceptance Criteria:**
- [ ] Context-based threshold modification works correctly
- [ ] All existing regime-only tests pass unchanged
- [ ] Threshold adjustments match design doc examples

---

## Task 8.3: Extend EnsembleBacktestRunner with Context Evaluation

**File(s):**
- `ktrdr/backtesting/ensemble_runner.py` (add context model evaluation + threshold application)

**Type:** CODING
**Estimated time:** 3 hours

**Description:**
Extend the runner to evaluate the context model once per daily bar close and apply threshold modifications to signal model decisions. Track when daily bar changes, re-evaluate context model, pass context_probs to router, apply adjusted thresholds to signal decisions.

**Implementation Notes:**
- Track `_current_context_probs` and `_last_context_date` on the runner
- `_maybe_update_context(timestamp)`: if `bar_date > _last_context_date`, evaluate context model → update `_current_context_probs`
- Context model needs its own FeatureCache (daily features, different indicators)
- Context FeatureCache uses daily data — the runner must load daily data alongside hourly
- Per-bar flow (architecture doc Section 6.2):
  1. `_maybe_update_context(timestamp)` — once per day
  2. Regime classification (unchanged)
  3. `router.route(regime_probs, context_probs=self._current_context_probs, ...)`
  4. Handle transition (unchanged)
  5. Run signal model → get decision
  6. Apply `route_result.threshold_modifier` to signal decision
- Context threshold application: if `signal_decision.confidence < adjusted_threshold` → HOLD
- Track context-related metrics: how often context changed a decision

**Testing Requirements:**
- [ ] Context model evaluated only once per daily bar change
- [ ] Context probs passed to router on every bar (held constant within day)
- [ ] Signal decisions below adjusted threshold converted to HOLD
- [ ] Without context gate: identical behavior to M7 (regression test)
- [ ] Context model FeatureCache uses daily data

**Acceptance Criteria:**
- [ ] Context evaluation happens once per daily bar close
- [ ] Threshold modification applied to signal decisions
- [ ] Regime-only ensemble produces identical results to M7

---

## Task 8.4: Run Context-Gated Ensemble Backtest

**File(s):** None (execution/evaluation task)
**Type:** MIXED
**Estimated time:** 3 hours

**Description:**
Create ensemble config with regime + context + signal models. Run full backtest and compare vs regime-only ensemble from M7.

**Implementation Notes:**
- Ensemble config: regime classifier (M4) + context classifier (M5) + per-regime signal models (M7)
- Compare metrics: Sharpe, win rate, max drawdown, trade count
- Key question: does context gate improve or hurt performance?
- Track: how many trades were blocked by context threshold modification, how many bad trades avoided, how many good trades missed
- If context hurts: the hypothesis is that the specific threshold parameters need tuning, or context and regime are too correlated

**Acceptance Criteria:**
- [ ] Full ensemble with regime + context + signal models runs
- [ ] Comparison vs regime-only documented
- [ ] Context impact quantified (trades blocked, net effect)

---

## Task 8.5: Validation

**File(s):** None (validation task)
**Type:** VALIDATION
**Estimated time:** 2 hours

**Description:**
Validate context-gated ensemble backtest end-to-end.

**Validation Steps:**
1. Load the `ke2e` skill before designing any validation
2. Invoke `ke2e-test-scout` with: "Run a context-gated ensemble backtest with regime router + context gate + signal models. Verify context model evaluates daily, threshold modifications are applied, and results include context impact metrics."
3. Invoke `ke2e-test-runner` with the identified test recipes
4. Tests must exercise real infrastructure
5. Verify: context evaluated once per day, threshold adjustments applied, results show context contribution

**Acceptance Criteria:**
- [ ] Full ensemble with context gate runs end-to-end
- [ ] Context model evaluation frequency is daily (not per bar)
- [ ] Threshold modifications affect signal decisions
- [ ] Results include context impact analysis
- [ ] Regime-only comparison available
