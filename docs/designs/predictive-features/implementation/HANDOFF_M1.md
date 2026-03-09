# HANDOFF — M1: Multi-TF Backtest Fix

## Task 1.1 Complete: Add timeframes to BacktestConfig and Worker Request

**Changes:**
- `engine.py`: Added `timeframes: list[str]` field + `get_all_timeframes()` to `BacktestConfig` dataclass
- `backtest_worker.py`: Added `timeframes: list[str]` field to `BacktestStartRequest` Pydantic model, imported `Field` from pydantic

**Gotchas:**
- `BacktestConfig` is a dataclass — uses `field(default_factory=list)`. `BacktestStartRequest` is Pydantic — uses `Field(default_factory=list)`. Don't mix them up.

## Task 1.2 Complete: Thread Timeframes Through API and Service

**Changes:**
- `backtesting.py` (API endpoint): Extracts full timeframes via `extract_symbols_timeframes_from_strategy()` and passes to service
- `backtesting_service.py`: Added `timeframes` param to `run_backtest()` and `run_backtest_on_worker()`, included in `request_payload` dict

**Design decision:** Used `extract_symbols_timeframes_from_strategy()` as the timeframes source rather than model metadata.

## Task 1.3 Complete: Multi-TF Data Loading in Backtest Engine

**Changes:**
- `engine.py` `_load_historical_data()`: Uses `config.get_all_timeframes()` as primary source, falls back to `_get_strategy_timeframes()` if config only has single TF
- `backtest_worker.py`: Both fresh start and resume paths pass `request.timeframes` into BacktestConfig

**Gotchas:**
- `MultiTimeframeCoordinator` is lazily imported — patch `ktrdr.data.multi_timeframe_coordinator.MultiTimeframeCoordinator` in tests

## Task 1.4 Complete: E2E Validation — PASSED (after training fix)

**E2E Test:** Train `v3_multi_tf_test` (1h+1d) on EURUSD, backtest it end-to-end.

**First attempt FAILED** — revealed two additional bugs:
1. **Training used only base timeframe:** `LocalTrainingOrchestrator._execute_v3_training()` used `self._context.timeframes` (from API: `["1h"]`) instead of resolving from strategy config. Model trained on 3 features but metadata declared 9.
2. **Metadata mismatch:** `metadata_v3.json` stored `resolved_features` from strategy config (all declared features) instead of `feature_names` (actual training features). Backtest validation failed: 9 expected, 3 produced.

**Fixes applied:**
- `local_orchestrator.py`: Resolve timeframes from `v3_config.training_data.timeframes` for multi-TF strategies
- `local_orchestrator.py`: Store actual `feature_names` in metadata, not config-declared `resolved_features`
- Created `strategies/v3_multi_tf_test.yaml` (1h+1d only) — avoids dependency on non-existent 4h data

**Final result:** Training produces 6 features (1h+1d), metadata matches, backtest completes with 3 trades, 1325 bars. No KeyError or feature mismatch.

**Sandbox env var fixes (not committed — .env.sandbox is gitignored):**
- Added `KTRDR_JAEGER_OTLP_GRPC_PORT=4327` / `KTRDR_JAEGER_OTLP_HTTP_PORT=4328`
- Added `KTRDR_DESIGN_AGENT_PORT=5011` / `KTRDR_ASSESSMENT_AGENT_PORT=5012`
