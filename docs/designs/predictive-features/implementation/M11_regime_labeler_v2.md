---
design: docs/designs/predictive-features/regime-detection/DESIGN.md
architecture: docs/designs/predictive-features/regime-detection/ARCHITECTURE.md
---

# M11: Multi-Scale Regime Labeler

**Thread:** Regime Detection
**JTBD:** "As a researcher, I want regime labels that accurately reflect the market's own swing structure so the classifier learns real regimes — not artifacts of wrong-timescale measurement."
**Depends on:** M7 (ensemble infrastructure already built and working)
**Tasks:** 5

**Why this milestone exists:** The original SER-based RegimeLabeler (M2) produced degenerate labels — 68%+ RANGING at threshold=0.3, 91%+ at threshold=0.5. The root cause is a fixed horizon (24 bars) that doesn't match the market's actual swing timescale. Multi-scale zigzag reads the data's own structure instead of imposing a fixed measurement window.

**Branch:** Work on current branch `impl/predictive-features-M7`

---

## Task 11.1: Build MultiScaleRegimeLabeler Core

**File(s):**
- `ktrdr/training/multi_scale_regime_labeler.py` (new)

**Type:** CODING
**Estimated time:** 4 hours

**Description:**
Build `MultiScaleRegimeLabeler` that uses two zigzag scales + volatility overlay to produce 4-class regime labels. The labeler auto-adapts to any timeframe/instrument via ATR-scaled zigzag thresholds.

**Algorithm:**
1. Compute ATR(14) on price data → `median(ATR) / median(close)` = base percentage
2. `macro_threshold = macro_atr_mult × base_pct` (default 3.0×)
3. `micro_threshold = micro_atr_mult × base_pct` (default 1.0×)
4. Run zigzag at macro threshold → macro pivots → macro segments (start, end, direction)
5. Run zigzag at micro threshold → micro pivots
6. For each macro segment, extract micro pivots within that segment's bar range
7. Check progression: in macro up-segment, do micro pivot lows form higher-lows? In macro down-segment, do micro pivot highs form lower-highs?
8. Volatility overlay: forward RV / historical RV → VOLATILE mask
9. Classify each bar:
   - VOLATILE (3) if vol_mask
   - TRENDING_UP (0) if macro=up AND micro progresses
   - TRENDING_DOWN (1) if macro=down AND micro progresses
   - RANGING (2) if micro doesn't progress

**Key implementation details:**
- Reuse the zigzag algorithm from `ZigZagIndicator.compute()` but return structured pivot list `[(idx, price), ...]` instead of sparse Series
- `_check_micro_progression()`: extract the relevant pivot subset (lows for up-segments, highs for down-segments), check pairwise: `pivot[i+1] > pivot[i]` for higher-lows. Return True if `fraction_progressive >= progression_tolerance`
- Bars before the first macro pivot and after the last macro pivot get NaN (not enough structure)
- The volatility overlay reuses the same RV ratio logic from the existing `RegimeLabeler`

**Parameters (all with sensible defaults):**
- `macro_atr_mult: float = 3.0`
- `micro_atr_mult: float = 1.0`
- `atr_period: int = 14`
- `vol_lookback: int = 120`
- `vol_crisis_threshold: float = 2.0`
- `progression_tolerance: float = 0.5`

**Testing Requirements:**
- [ ] Perfect uptrend (monotonically increasing close) → all TRENDING_UP
- [ ] Perfect downtrend → all TRENDING_DOWN
- [ ] Choppy/oscillating data with no net direction → mostly RANGING
- [ ] Volatility spike data → VOLATILE labels where spike occurs
- [ ] Mixed data with clear trend + choppy section → correct regime transitions
- [ ] ATR threshold auto-scales: same multipliers work on data at different price levels
- [ ] Progression tolerance works: strict (1.0) requires all pairs progressive, lenient (0.3) allows some chop
- [ ] Bars outside macro segments are NaN
- [ ] Labels are integers 0-3 (same encoding as existing RegimeLabeler)

**Acceptance Criteria:**
- [ ] `MultiScaleRegimeLabeler.generate_labels()` returns Series with values 0-3
- [ ] No hardcoded thresholds tied to specific instruments or timeframes
- [ ] Classification priority: VOLATILE > TRENDING > RANGING
- [ ] Edge cases: constant price (ATR=0), very short data (<50 bars), single macro segment

---

## Task 11.2: Add analyze_labels() and Wire to Existing RegimeLabelStats

**File(s):**
- `ktrdr/training/multi_scale_regime_labeler.py` (extend)

**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Add `analyze_labels()` method to `MultiScaleRegimeLabeler` that reuses the `RegimeLabelStats` dataclass and analysis logic from the existing `RegimeLabeler`. Import and delegate rather than duplicate.

**Implementation Notes:**
- Import `RegimeLabelStats` from `regime_labeler.py`
- The analysis logic (distribution, duration, returns, transitions) is regime-agnostic — it just needs a Series of integer labels and the price data
- Consider extracting the analysis into a shared function both labelers can call, or simply instantiate the old labeler's `analyze_labels` method
- Also export from `ktrdr/training/__init__.py`

**Testing Requirements:**
- [ ] Distribution sums to ~1.0
- [ ] Mean duration > 0 for all present regimes
- [ ] Transition matrix rows sum to ~1.0
- [ ] Stats match manual calculation on small synthetic dataset

**Acceptance Criteria:**
- [ ] `MultiScaleRegimeLabeler.analyze_labels()` returns `RegimeLabelStats`
- [ ] Same stats format as v1 labeler (consumers don't need to change)

---

## Task 11.3: Wire MultiScaleRegimeLabeler to Training Pipeline + CLI

**File(s):**
- `ktrdr/training/training_pipeline.py` (update label dispatch)
- `training-host-service/orchestrator.py` (update label dispatch — BOTH locations!)
- `ktrdr/cli/commands/regime.py` (update to use new labeler)
- `strategies/regime_classifier_seed_v1.yaml` (update training.labels config)

**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Wire the new labeler into the training pipeline's label dispatch and update the CLI `regime analyze` command. Update the seed strategy YAML to use multi-scale parameters.

**Implementation Notes:**
- Training pipeline: `labels.source: regime` now instantiates `MultiScaleRegimeLabeler` instead of `RegimeLabeler`
- **CRITICAL**: Update BOTH `training_pipeline.py` AND `training-host-service/orchestrator.py` (dual-dispatch bug pattern)
- CLI `regime analyze` command: add new CLI params (`--macro-atr-mult`, `--micro-atr-mult`, `--atr-period`, `--progression-tolerance`) and use `MultiScaleRegimeLabeler`
- Update `strategies/regime_classifier_seed_v1.yaml` training.labels section:
  ```yaml
  training:
    labels:
      source: regime
      macro_atr_mult: 3.0
      micro_atr_mult: 1.0
      atr_period: 14
      vol_crisis_threshold: 2.0
      vol_lookback: 120
      progression_tolerance: 0.5
  ```
- Remove old SER-specific params (`horizon`, `trending_threshold`) from seed strategy

**Testing Requirements:**
- [ ] Training pipeline creates MultiScaleRegimeLabeler when source=regime
- [ ] CLI command accepts new params and passes to labeler
- [ ] Seed strategy YAML validates with updated labels config
- [ ] Old RegimeLabeler still importable (backward compat for existing tests)

**Acceptance Criteria:**
- [ ] `labels.source: regime` uses MultiScaleRegimeLabeler in both pipeline locations
- [ ] CLI `ktrdr regime analyze` uses new labeler with multi-scale params
- [ ] Seed strategy YAML updated with multi-scale parameters

---

## Task 11.4: Retrain Regime Classifier + Run Ensemble Backtest

**File(s):**
- `scripts/retrain_regime.py` (update to use MultiScaleRegimeLabeler)

**Type:** MIXED (retrain in container, evaluate results)
**Estimated time:** 3 hours

**Description:**
Update the retraining script to use `MultiScaleRegimeLabeler`, retrain the regime classifier inside the container, and run the ensemble backtest to evaluate. Compare label distribution and backtest results against the v1 labeler.

**Implementation Notes:**
- Update `scripts/retrain_regime.py`:
  - Replace `RegimeLabeler` with `MultiScaleRegimeLabeler`
  - Pass multi-scale params from strategy YAML
  - Keep class-weighted loss (inverse frequency) — distribution will differ but imbalance likely still exists
  - Print label distribution for comparison
- Run inside container: `docker exec <container> python /app/scripts/retrain_regime.py`
- After retraining, run ensemble backtest: `docker exec <container> python /app/scripts/run_ensemble_backtest.py`
- **Evaluation criteria:**
  - Label distribution: no single class >60%
  - Multiple regimes active in backtest (not all one regime)
  - Regime transitions occur at plausible chart locations
  - Ensemble routes to different models in different regimes

**Quality gate:** If labels are still degenerate (>80% one class), investigate ATR multiplier values on the actual EURUSD data and adjust before proceeding.

**Acceptance Criteria:**
- [ ] Regime classifier retrained with multi-scale labels
- [ ] Label distribution shows meaningful spread across 4 classes
- [ ] Ensemble backtest completes with multiple active regimes
- [ ] Results documented in handoff

---

## Task 11.5: Validation

**File(s):** None (validation task)
**Type:** VALIDATION
**Estimated time:** 1 hour

**Description:**
Validate the multi-scale regime labeler end-to-end: labels are meaningful, classifier trains, ensemble routes correctly.

**Validation Steps:**
1. Use e2e-test-designer agent to find/design appropriate test
2. Run `ktrdr regime analyze EURUSD 1h --start-date 2019-01-01 --end-date 2024-01-01` — verify multi-scale labels
3. Verify label quality: distribution, persistence, return-by-regime differentiation
4. Verify ensemble backtest produces regime-routed trades with multiple active regimes
5. Compare label quality metrics vs. v1 (SER-based) — document improvement

**Acceptance Criteria:**
- [ ] Labels show meaningful 4-class distribution (no class >60%)
- [ ] Mean regime duration is plausible (not flickering every bar)
- [ ] Return-by-regime shows differentiation (trending_up positive, trending_down negative)
- [ ] Ensemble backtest routes to different models per regime
- [ ] Results documented in analysis file
