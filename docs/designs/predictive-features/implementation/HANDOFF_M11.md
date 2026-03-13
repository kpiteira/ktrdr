# M11 Ensemble Regime Labeler v2 — Handoff

## Task 11.1 Complete: Build MultiScaleRegimeLabeler Core

**Gotchas:**
- Micro zigzag needs actual micro swings to detect progression. With very smooth data (noise << ATR), micro zigzag finds only 2 pivots (start/end) → defaults to RANGING. This is correct behavior — no structure to analyze means no trend confirmation.
- Pivot high/low classification must iterate in chronological order. Appending first/last pivots after the middle loop produces wrong ordering for the progression check.
- ATR threshold formula: `atr_mult × median(ATR) / median(close)`. Constant price (ATR=0) → threshold=0 → returns all NaN (handled gracefully).
- The `_run_zigzag()` returns structured `list[tuple[int, float]]` pivots, not a sparse Series like `ZigZagIndicator.compute()`. This makes segment analysis straightforward.

**Next task notes (11.2):**
- `RegimeLabelStats` and `REGIME_NAMES` are imported from `regime_labeler.py`. The `analyze_labels()` method is already implemented in 11.1 — Task 11.2 just needs to add tests and ensure the analysis logic works correctly with multi-scale labels.
- The analysis uses `self.atr_period` as the forward return horizon (not a fixed `self.horizon` like v1).

## Task 11.3 Complete: Wire MultiScaleRegimeLabeler to Training Pipeline + CLI

**Gotchas:**
- `importlib.util.spec_from_file_location` lazy import in CLI creates separate module objects with different class identities. `isinstance(stats, RegimeLabelStats)` fails in full test suite because a different test loads the module first via `importlib.util`. Fix: use direct `from ktrdr.training.multi_scale_regime_labeler import ...` — neither module imports torch.
- Dual-dispatch: training pipeline changes must go in BOTH `training_pipeline.py` AND `training-host-service/orchestrator.py`. The host service uses a hardcoded label_config dict, not the YAML.
- NaN handling changed from fixed slicing (`labels[vol_lookback:]`) to `labels.notna()` mask — more robust when ATR warmup varies.
- Seed strategy YAML updated: removed `horizon`, `trending_threshold`; added `macro_atr_mult`, `micro_atr_mult`, `atr_period`, `progression_tolerance`.

**Next task notes (11.4):**
- Retrain regime classifier with new labels using `scripts/retrain_regime.py`. The script needs updated default params to match multi-scale labeler.

## Task 11.4 Complete: Retrain Regime Classifier + Run Ensemble Backtest

**Results (multi-scale zigzag labels on EURUSD 1h, 2019-2024):**
- Label distribution: TRENDING_UP=39.7%, TRENDING_DOWN=43.3%, RANGING=13.0%, VOLATILE=4.0%
- Compare v1 (SER): 68%+ RANGING — massive improvement
- Quality gate: no class >60% ✅
- Test accuracy: 50.98% (4-class seed classifier, will improve with evolution)
- Ensemble backtest (Jun-Sep 2024): 90 transitions, 3 regimes active (trending_up, trending_down, volatile)
- Class weights used: VOLATILE=6.26x, RANGING=1.92x, UP=0.63x, DOWN=0.58x

**Gotchas:**
- `/app/scripts/` doesn't exist in container — must `docker cp` the script in
- Sandbox rebuild needed to pick up code changes (kinfra sandbox down + up --build)
- The 2024 backtest window shows high VOLATILE (58%) — realistic for that period, training set was more balanced

## Task 11.5 Complete: Validation

**E2E test: cli/regime-analyze** — PASSED (all sanity checks pass)
- 4 regime classes present, no class >60%
- Mean durations: 10-39 bars (not flickering)
- Return differentiation: UP=+0.16%, DOWN=-0.16% (economically correct)
- Parameter sensitivity confirmed: macro_atr_mult=3.0 vs 5.0 produces different distributions
- Updated E2E test recipe to match multi-scale zigzag params (was stale SER params)
