# Handoff: M1 — Triple Barrier Labeler

## Task 1.1: TripleBarrierLabeler Core
- **Pattern:** Follows `ForwardReturnLabeler` interface: `generate_labels(price_data) -> pd.Series`, `get_label_statistics(labels) -> dict`
- **vol_method parameter:** Defaults to `"atr"` (true range), not `"close"` (log returns). ATR-based vol accounts for intrabar price range since barriers are checked against high/low. Close-to-close vol produces barriers that are narrower than a single bar's high-low range, causing barriers to trigger on bar 1-2 (mean hold ~2.4 bars vs ~6.2 with ATR).
- **Gotcha:** Expiry threshold must scale with `vol * sqrt(holding_period) * 0.5`, not just `vol * 0.1`. Without this, nearly all vertical barrier hits classify as +1/-1.
- **Gotcha:** Vol estimation via EWMA needs `vol_span` bars to converge — early bars use the first valid estimate via forward-fill.
- **Holding periods:** Available via `labeler.get_holding_periods()` after `generate_labels()` — stored as instance state, not returned directly.
- **Expiry class is naturally small:** With pt=2.0, sl=1.5, barriers are hit well before max_holding_period=50 on FX hourly data. This is mathematically expected (random walk over 50 bars exceeds barrier widths). The labeler effectively produces a 2-class TP/SL classification, which IS the useful signal — "will this trade hit take-profit or stop-loss?"

## Task 1.2: CUSUM Event Filter
- **Pattern:** `CUSUMFilter.filter(price_data) -> pd.Series[bool]` — pure filter, applied before labeling.
- **Default cusum_multiplier changed to 0.5:** The CUSUM algorithm effectively doubles the threshold (subtracts h from each return AND requires accumulation > h). Default 1.0 gave ~6% retention on FX hourly data; 0.5 gives ~35% retention — in the 30-70% target range.
- **Auto-threshold mode:** `threshold=None` computes from `cusum_multiplier * mean(ewma_vol)`. Logs the computed threshold.
- **Gotcha:** The threshold operates in log-return space. For hourly data with ~0.08% per-bar vol, the effective threshold range is 0.0002-0.0008.

## Task 1.3: Uniqueness Weighting
- **Function:** `compute_uniqueness_weights(labels, holding_periods, normalize=False) -> pd.Series`
- **Wired into pipeline:** `compute_weights: true` in label_config triggers computation. Weights stored on `TrainingPipeline._sample_weights` (class attribute), accessible via `TrainingPipeline.get_sample_weights()`. Normalized to mean=1.0.
- **Gotcha:** "Non-overlapping" means active periods don't share *index positions* — even widely spaced samples overlap if holding_period >= gap.

## Task 1.4: Pipeline Integration
- **Branch added:** `source: "triple_barrier"` in `TrainingPipeline.create_labels()`
- **Parameters plumbed:** `vol_method`, `compute_weights`, `cusum_threshold`, `cusum_multiplier` all pass through from label_config to their respective components.
- **Class mapping:** TB labels (+1, 0, -1) → class indices (0, 1, 2) matching existing BUY/HOLD/SELL convention in DecisionFunction.
- **Orchestrator routing:** `local_orchestrator.py` has `triple_barrier` elif branch for label config + feature/label alignment + explicit `output_type_map` entry.

## Task 1.5: E2E Validation
- **Bug found:** `local_orchestrator.py` was missing the `triple_barrier` elif branch, silently falling back to zigzag. Fixed.
- **E2E confirmed:** Training with `source: triple_barrier` completes end-to-end in sandbox, produces valid 3-class model with TP/SL distribution.
- **ke2e recipe:** `.claude/skills/ke2e/tests/training/triple-barrier-labels.md`

## Emergent Patterns
- **ATR vol is essential for TB labels.** Close-to-close vol underestimates the price range that barriers are checked against (high/low). This produces degenerate hold times (1-2 bars) because a single bar's range already spans the barrier width.
- **E2E testing caught routing bug** in `local_orchestrator.py` that unit tests couldn't — the orchestrator has its own label config dispatch separate from `training_pipeline.py`.
- **Test synthetic data** for financial labelers requires careful calibration: barriers, thresholds, and vol parameters all operate in log-return space.

## Quality Gates
- 52 new tests pass (22 labeler + 11 CUSUM + 8 weights + 11 pipeline integration)
- Full suite: 6007 passed, 5 skipped
- `make quality` passes (lint + format + typecheck)
