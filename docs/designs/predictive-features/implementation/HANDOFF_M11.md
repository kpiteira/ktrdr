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
