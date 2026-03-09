# HANDOFF — M1: Multi-TF Backtest Fix

## Task 1.1 Complete: Add timeframes to BacktestConfig and Worker Request

**Changes:**
- `engine.py`: Added `timeframes: list[str]` field + `get_all_timeframes()` to `BacktestConfig` dataclass
- `backtest_worker.py`: Added `timeframes: list[str]` field to `BacktestStartRequest` Pydantic model, imported `Field` from pydantic

**Gotchas:**
- `BacktestConfig` is a dataclass — uses `field(default_factory=list)`. `BacktestStartRequest` is Pydantic — uses `Field(default_factory=list)`. Don't mix them up.
- `backtest_worker.py` had no existing `pydantic.Field` import — had to add it explicitly

**Next Task Notes (1.2):**
- `BacktestStartRequest` now accepts `timeframes` — thread it through API endpoint → service → remote_api
- `ModelMetadata.training_timeframes` is the source of truth for which timeframes a model was trained on
- Check `backtesting_service.py` for how it constructs the worker payload dict

## Task 1.2 Complete: Thread Timeframes Through API and Service

**Changes:**
- `backtesting.py` (API endpoint): Extracts full timeframes via `extract_symbols_timeframes_from_strategy()` and passes to service
- `backtesting_service.py`: Added `timeframes` param to `run_backtest()` and `run_backtest_on_worker()`, included in `request_payload` dict
- `remote_api.py` not modified — it's DEPRECATED and the `BacktestStartRequest` Pydantic model already has the `timeframes` field from Task 1.1

**Design decision:** Used `extract_symbols_timeframes_from_strategy()` as the timeframes source rather than model metadata. The API endpoint already uses this function and it doesn't require loading the model. The strategy config is the canonical source of timeframe configuration.

**Next Task Notes (1.3):**
- Worker now receives `timeframes` in the payload. Engine needs to use `config.get_all_timeframes()` to decide single vs multi-TF data loading
- `MultiTimeframeCoordinator` is at `ktrdr/data/multi_timeframe_coordinator.py`
- `FeatureCache.compute_features()` already accepts `dict[str, pd.DataFrame]`

## Task 1.3 Complete: Multi-TF Data Loading in Backtest Engine

**Changes:**
- `engine.py` `_load_historical_data()`: Now uses `config.get_all_timeframes()` as primary source, falls back to `_get_strategy_timeframes()` if config only has single TF
- `backtest_worker.py`: Both fresh start (line ~306) and resume (line ~359) paths now pass `request.timeframes` / `original_request.get("timeframes", [])` into BacktestConfig

**Design decision:** `config.get_all_timeframes()` takes priority because it's threaded from the API (extracted from strategy file). Falls back to `_get_strategy_timeframes()` (model bundle) only if config has single TF — this preserves backward compat for old code paths that don't thread timeframes.

**Gotchas:**
- `MultiTimeframeCoordinator` is lazily imported inside `_load_historical_data()` — patch `ktrdr.data.multi_timeframe_coordinator.MultiTimeframeCoordinator` not `ktrdr.backtesting.engine.MultiTimeframeCoordinator` in tests

## Task 1.4 Complete: E2E Validation

**E2E Test:** `training/multi-timeframe-backtest` — 10 steps executed — **FAILED**

**Result:** Timeframes threading (M1 plumbing) works correctly. Training completes, `metadata_v3.json` correctly lists 9 multi-TF features. Backtest receives timeframes but fails at `feature_cache._validate_features()` with `ValueError: Feature mismatch: missing 6 features`.

**Root cause:** Two issues surfaced:
1. **Missing 4h data:** No EURUSD 4h CSV cache exists. System doesn't auto-resample from 1h.
2. **FeatureCache only computes 1h features:** Even though engine loads multi-TF data via coordinator, `FeatureCache.compute_all_features()` only produces features for the base timeframe. The 4h and 1d features are missing from the computed result. This is a pre-existing issue in the feature computation pipeline, not in M1's timeframes threading.

**M1 scope assessment:** M1 fixes the plumbing (timeframes threaded API→service→worker→engine→coordinator). The remaining feature computation issue is in the FeatureCache/indicator resolution layer — a different fix needed in `ktrdr/backtesting/feature_cache.py`.

**Sandbox gotchas:**
- `.env.sandbox` had wrong var names: `KTRDR_OTLP_GRPC_PORT` → compose expects `KTRDR_JAEGER_OTLP_GRPC_PORT`. Added both JAEGER variants.
- Port 5010 conflict: sandbox `KTRDR_WORKER_PORT_4=5010` clashes with `KTRDR_DESIGN_AGENT_PORT` default of 5010. Added explicit `KTRDR_DESIGN_AGENT_PORT=5011` and `KTRDR_ASSESSMENT_AGENT_PORT=5012`.
- Port 5010/5020 also conflict with prod agent containers when both running simultaneously.
