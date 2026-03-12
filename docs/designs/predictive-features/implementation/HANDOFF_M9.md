# M9 Handoff: External Data — Backtest + CFTC

## Task 9.1 Complete: Model Bundle Context Data Config Storage

**What was implemented:**
- `reconstruct_config_from_metadata` now reconstructs `context_data` entries from metadata
- `FeatureCache.compute_features()` and `compute_all_features()` accept `context_data` param
- `BacktestingEngine._load_context_data()` fetches external data using provider registry
- Engine wires context data loading between data load and feature computation in `run()`

**Gotchas:**
- Provider `fetch()` is async — engine uses `asyncio.run()` in the sync `_load_context_data()` method (same pattern as training orchestrator)
- `primary_data.index` returns `Index[Any]` — needs explicit `pd.DatetimeIndex()` cast for mypy
- `metadata.context_data_config` is `Optional[list]` — must assign to local var before using in async closure to satisfy mypy

**Next Task Notes (9.2 - IB Context Provider):**
- Registry at `ktrdr/data/context/registry.py` — register new provider as "ib"
- Follow `FredDataProvider` pattern in `fred_provider.py`
- IB data already cached by `ktrdr data load` — use `DataRepository.load_from_cache()`
- Provider returns OHLCV DataFrame, `get_source_ids()` returns `[config.symbol]`

## Task 9.2 Complete: IB Context Provider (Cross-Pair)

**What was implemented:**
- `IbContextProvider` in `ktrdr/data/context/ib_context_provider.py`
- Delegates to `DataRepository.load_from_cache()` — no new API calls
- Registered as "ib" in `ContextDataProviderRegistry`
- Filters data to requested date range, handles tz-aware/naive index

**Next Task Notes (9.3 - CFTC COT Provider):**
- Follow same pattern: implement `CftcCotProvider`, register as "cftc_cot"
- Task says use `cot_reports` Python library — check if it's already a dependency
- Weekly data: provider returns weekly DataFrame, alignment handled by `ContextDataAligner`
- Compute percentile over rolling 52w and 156w windows

## Task 9.3 Complete: CFTC COT Provider

**What was implemented:**
- `CftcCotProvider` in `ktrdr/data/context/cftc_provider.py`
- Fetches from CFTC TFF report, parses leveraged fund positions
- Computes rolling percentile (52w/156w) — 0-100 scale
- Two source IDs per currency: `cot_{report}_net_pos`, `cot_{report}_net_pct`
- Registered as "cftc_cot" in registry

**Design decision:** Used CFTC public CSV endpoint directly instead of `cot_reports` library (not installed, avoids adding dependency). TFF report parsing handles column name variations.

**Gotchas:**
- `_compute_percentiles` uses rolling apply with `raw=False` — needed for correct windowed rank calculation
- Net percentile uses 52w as primary `close` column (more responsive), 156w as extra column

**Next Task Notes (9.4 - Multi-Source Strategy):**
- All 3 providers now registered: fred, ib, cftc_cot
- Strategy YAML needs `context_data` section + `data_source` on indicators
- Architecture doc Section 2.3 has the carry momentum strategy template

## Task 9.4 Complete: Train Strategy with Multi-Source Context

**What was implemented:**
- `strategies/eurusd_carry_momentum_v1.yaml` with FRED + IB + CFTC context
- 12 unit tests validating YAML structure and v3 parsing
- Strategy loads as StrategyConfigurationV3 with all 3 context_data entries

**Gotchas:**
- Loader class is `StrategyConfigurationLoader.load_v3_strategy()`, not `StrategyLoaderV3`
- `IndicatorDefinition` uses `model_extra` for `data_source` — `extra = "allow"` in model config
- Strategy uses `date_range: {start, end}` format (not `start_date`/`end_date`)

**Next Task Notes (9.5 - Backtest with External Data):**
- Strategy needs real data: EURUSD and GBPUSD cached, FRED API key configured
- Backtest: `ktrdr backtest run eurusd_carry_momentum_v1 EURUSD 1h --start-date 2024-01-01 --end-date 2025-01-01`
- Engine will auto-load context data from model metadata (Task 9.1 work)

## Task 9.5 Complete: Backtest with External Data (Integration Tests)

**What was implemented:**
- 6 integration tests in `tests/integration/backtesting/test_context_data_backtest_integration.py`
- Tests validate full internal pipeline with synthetic data: config reconstruction, FeatureCache with all 3 context sources, feature ordering, missing context error handling, backward compatibility
- Fixed `test_registry.py::test_available_providers` — was hardcoded to `['fred', 'ib']`, now accounts for `cftc_cot`

**Gotchas:**
- Integration tests use realistic synthetic data (not mocked) through real IndicatorEngine + FuzzyEngine
- `reconstruct_config_from_metadata` returns config where `model_extra` stores `data_source` — must access via `.model_extra["data_source"]` not `.data_source`

**Next Task Notes (9.6 - E2E Validation):**
- E2E test should exercise the real backtest CLI or engine with external data providers
- Requires sandbox running with FRED API key and cached IB data

## Task 9.6 Complete: E2E Validation

**E2E test:** `backtest/context-data-multi-provider` — 12 steps, **PASSED**

**Bugs found and fixed during E2E:**
1. **CFTC headerless TFF format**: `FinFutWk.txt` has no header row — parser treated first data row as column headers. Fixed: detect headerless format, use positional columns + download annual zip files for historical data.
2. **tz-aware vs tz-naive comparison**: Engine passes tz-aware UTC dates, CFTC index is tz-naive. Fixed: strip timezone in `fetch()`.
3. **Duplicate dates from overlapping annual files**: Annual CFTC zips overlap year boundaries. Fixed: deduplicate in both parser and aligner.
4. **NaN confidence crash**: Degenerate model output caused `ValueError` in `TradingDecision.__post_init__`. Fixed: guard in `decision_function.py`, default to HOLD.

**Key evidence:** Training completed with 3 providers, metadata has 11 features, backtest loaded all context data (5661 bars × 11 features), produced 1 trade with $1,042 return.
