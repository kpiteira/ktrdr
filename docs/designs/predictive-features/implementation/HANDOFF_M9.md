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
