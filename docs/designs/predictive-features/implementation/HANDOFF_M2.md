# Handoff: M2 Regime Labeling

## Task 2.1 Complete: Build RegimeLabeler

**Gotchas:**
- `ktrdr.training.__init__` imports torch via model_trainer. Tests use `importlib.util.spec_from_file_location` to import regime_labeler directly, bypassing the package __init__. This avoids needing torch for a pure numpy/pandas module.
- Synthetic test data for volatile priority needs extreme vol contrast (0.0005 → 0.05 returns) and careful index management — use `labels.iloc[start:end]` not `valid.iloc[...]` since `dropna()` reindexes.

**Implementation notes:**
- `compute_signed_efficiency_ratio`: Uses numpy loop (not vectorized rolling) for clarity. Returns 0.0 for constant price (path_length=0).
- `compute_realized_volatility_ratio`: Uses log returns for numerical stability. RV_ratio = forward_std / hist_std. Returns 0.0 when hist_rv=0.
- `generate_labels`: Builds labels in priority order — set RANGING first, override with TRENDING, override with VOLATILE.
- Module constants: `TRENDING_UP=0, TRENDING_DOWN=1, RANGING=2, VOLATILE=3` and `REGIME_NAMES` dict.

## Task 2.2 Complete: Build RegimeLabelStats Analysis

**Implementation notes:**
- `RegimeLabelStats` is a `@dataclass` (not Pydantic) — simple data container, no validation needed.
- `analyze_labels()` drops NaN from labels before analysis. Uses `labels.dropna().astype(int)`.
- `_compute_mean_returns` uses `.index.intersection()` to handle index length mismatches between labels and price_data (e.g., when NaN labels are dropped).
- Transition matrix only includes regimes that actually transition — absent source regimes have no row.

## Task 2.3 Complete: Build CLI Command `ktrdr regime analyze`

**Gotchas:**
- `from ktrdr.training.regime_labeler import RegimeLabeler` triggers torch import via `ktrdr.training.__init__`. Used `importlib.util.spec_from_file_location` workaround to load the module directly — both in tests and in the CLI command itself.
- Mock patch for DataRepository must target `ktrdr.data.repository.DataRepository` (where it's defined), not `ktrdr.cli.commands.regime.DataRepository` (lazy import inside function body doesn't create a module-level name).

## Task 2.4 Complete: Generate and Analyze Labels for EURUSD 1h

**Findings:**
- Default params (H=24, thresh=0.5) fail: 91% ranging, only 4-bar trending persistence.
- Tuned params (H=48, thresh=0.20): 63% ranging, 17-18% trending, 1.5% volatile, 1.9 trans/day.
- Return differentiation strong: trending_up=+0.94%, trending_down=-0.89%.
- Persistence (8-10 bars) below 24-bar target — structural SER issue, handled by router stability filter.
- Decision: **PROCEED.** Regimes exist and differentiate returns. See analysis report at `docs/designs/predictive-features/regime-detection/analysis/EURUSD_1h_regime_analysis.md`.

**Next Task Notes (2.5):**
- VALIDATION task. Need cached EURUSD 1h data in `data/` directory. Already copied from ktrdr2.
- Use tuned params: `--horizon 48 --trending-threshold 0.2`.
