# Handoff: M3 Context Labeling & Analysis

## Task 3.1 Complete: Build ContextLabeler

**Pattern:** Follows `ForwardReturnLabeler` pattern (not RegimeLabeler — which doesn't exist yet despite the milestone referencing it).

**Key decisions:**
- Labels are float values (0.0, 1.0, 2.0, NaN) not integers — because NaN requires float Series in pandas
- Last `horizon` bars are NaN (kept in series, not truncated like ForwardReturnLabeler)
- Module imports only pandas + ktrdr.errors — no torch dependency
- Tests use `pytest.importorskip("torch")` because importing via `ktrdr.training.context_labeler` triggers `__init__.py` which imports torch

**Gotcha:** `ktrdr.training.__init__.py` imports torch transitively. Any test importing from `ktrdr.training.*` needs the torch guard even if the module itself is pure pandas.

**Next task notes:** Task 3.2 adds `analyze_labels()` method and `ContextLabelStats` dataclass to the same file. Consider the hourly return aggregation — needs hourly data aligned to daily context labels via forward-fill.

## Task 3.2 Complete: Build ContextLabelStats Analysis

**Key decisions:**
- `ContextLabelStats` is a dataclass with 4 fields: distribution, mean_duration_days, mean_hourly_return_by_context (optional), regime_correlation (optional)
- Hourly return alignment: forward-fill daily labels onto hourly index using `reindex(union).ffill()` — same approach MultiTimeframeCoordinator uses
- Cramér's V for regime correlation: chi-squared based, no scipy dependency (computed manually)
- Duration computed by tracking consecutive runs, not using groupby

**Gotcha:** Test hourly data must span enough calendar time to cover all daily labels. Using `periods=32, freq='h'` only covers ~1.3 days even if daily labels span 4 business days.

**Next task notes:** Task 3.3 builds CLI command `ktrdr context analyze`. Needs to register in `app.py`, load daily data, optionally load hourly data, call labeler + analyze_labels, format with Rich tables.

## Task 3.3 Complete: Build CLI Command `ktrdr context analyze`

**Pattern:** Follows `agent_app` pattern — `typer.Typer` group registered in `app.py` with `add_typer()`. Lazy imports inside function body for fast CLI startup.

**Gotcha:** Testing CLI commands that lazy-import from `ktrdr.training.*` requires pre-registering a stub `ktrdr.training` module in `sys.modules` before importing the app. Otherwise the `patch()` target fails because Python can't resolve the module path through the torch-dependent `__init__.py`. See `test_context.py` header for the pattern.

**Next task notes:** Task 3.4 is RESEARCH — run `ktrdr context analyze EURUSD 1d` on real cached data. Requires cached EURUSD 1d data. Command supports `--hourly-timeframe 1h` for return-by-context. Quality gate: distribution balanced, persistence >3 days, returns differentiate.

## Task 3.4 Complete: Generate and Analyze Labels for EURUSD 1d

**Result:** Default params (H=5, ±0.5%) FAIL quality gate. After parameter sweep, **H=10, T=±0.7%** passes all 3 gates.

**Key findings:**
- 5-day horizon too noisy for EURUSD — neutral persistence only 2.3 days, returns don't differentiate
- 10-day horizon is the sweet spot: balanced distribution (28/33/39%), persistence >3d, directional hourly returns
- Wider thresholds improve return diff but collapse distribution into >60% neutral
- Only H=10 with moderate thresholds passes all gates simultaneously

**Decision:** PROCEED with Thread 2. Recommended defaults for context model: horizon=10, threshold=±0.007.

**Analysis saved:** `docs/designs/predictive-features/multi-timeframe-context/analysis/context_label_analysis_EURUSD.md`
