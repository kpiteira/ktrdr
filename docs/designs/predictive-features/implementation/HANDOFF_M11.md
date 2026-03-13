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
