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

**Next Task Notes (2.3):**
- CLI command `ktrdr regime analyze` needs `DataRepository.load_from_cache()` for OHLCV data loading.
- Use Rich tables for output formatting. Follow existing CLI patterns in `ktrdr/cli/commands/`.
- Register `regime_app = typer.Typer()` in `app.py`.
