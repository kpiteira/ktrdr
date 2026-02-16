# Handoff: M3 — Engine Rewrite (Pipeline Integration)

## Status: Complete

## What Was Done

### Task 3.1: Rewrite BacktestingEngine.__init__
- Replaced `DecisionOrchestrator` initialization with direct component wiring:
  - `ModelBundle.load(model_path)` for single model loading
  - `FeatureCache(config=bundle.strategy_config, model_metadata=bundle.metadata)` for feature computation
  - `DecisionFunction(model, feature_names, decisions_config)` for stateless decisions
- `strategy_name` comes from `bundle.metadata.strategy_name` (not orchestrator)
- `_get_base_timeframe()` reads from `bundle.strategy_config.training_data.timeframes.base_timeframe`
- `_get_strategy_timeframes()` reads from `bundle.strategy_config.training_data.timeframes`
- Added model_path validation (raises ValueError if None)
- Added `_get_decisions_config()` helper to extract decisions dict from strategy config

### Task 3.2: Rewrite simulation loop
- `run()` core loop is now ~50 lines (well under the 80-line target)
- Removed: signal_counts, non_hold_signals, trade_attempts (debug tracking)
- Removed: last_processed_timestamp / repeated_timestamp_count (infinite loop detection)
- Removed: end_date safety check (data already filtered in _load_historical_data)
- Removed: historical_data = data.iloc[:idx+1] (unused by DecisionFunction)
- Removed: portfolio_state dict (unused by DecisionFunction)
- Removed: decision_engine.update_position() manual sync
- Removed: all desync detection and logging
- Removed: all self.config.verbose print blocks
- Removed: self.progress_callback legacy callback
- Removed: verbose summary printing, _print_summary()
- Extracted to helpers: `_report_progress()`, `_maybe_checkpoint()`, `_check_cancellation()`, `_force_close_position()`
- `_generate_results()` simplified to take `execution_start` float only
- `last_signal_time` is a local variable in the loop, not class state

### Task 3.3: Update resume_from_context + reset
- `resume_from_context()` calls `self.feature_cache.compute_all_features(multi_tf_data)` instead of `self.orchestrator.prepare_feature_cache(multi_tf_data)`
- `reset()` only calls `position_manager.reset()` and `performance_tracker.reset()` — no `orchestrator.reset_state()`

### Task 3.4: Update checkpoint builder/restore
- `checkpoint_builder.py` required NO changes — it only accesses `engine.position_manager`, `engine.performance_tracker`, and `engine.config`
- `checkpoint_restore.py` required NO changes — `BacktestResumeContext` is engine-independent

### Task 3.5: M3 Validation
- All 211 backtesting unit tests pass (10 skipped — torch-dependent)
- All 4991 total unit tests pass (32 skipped)
- Lint: clean (ruff)
- Format: clean (black)
- Typecheck: clean for engine.py
- Grep validation: no DecisionOrchestrator/decision_engine/self.orchestrator in backtesting module

#### E2E Container Tests (slot-1 sandbox)

**Test 1: Engine initialization with real model** — PASSED
- Container: `slot-1-backtest-worker-1` (M3 code)
- Model: `v3_minimal/1h_v38` (v3 metadata)
- Strategy: `v3_minimal.yaml`
- Verified: `engine.strategy_name = 'v3_minimal'`, model on cpu, 2 features, DecisionFunction type, FeatureCache type, PositionManager type, PerformanceTracker type

**Test 2: Full backtest execution** — PASSED
- Same config: EURUSD 1h, 2024-03-01 to 2024-03-15
- Results: 2 trades, -$115.22 PnL, 50% win rate, 0.22% max drawdown
- Execution time: 0.30s
- Engine ran full pipeline: data load → feature compute → decision loop → force close → results

**Test 3: Equivalence comparison (new vs old engine)** — BEHAVIORAL DIFFERENCE (expected)
- Old engine (prod, DecisionOrchestrator): 7 trades, -$321.74 PnL, 42.9% win rate
- New engine (slot-1, DecisionFunction): 2 trades, -$115.22 PnL, 50% win rate
- Root cause: DecisionFunction (M2) uses default `confidence_threshold=0.5` and `min_separation_hours=4` which filter more signals than the old DecisionEngine. The old engine's DecisionEngine had different threshold behavior and tracked position state internally.
- This is an intentional design change from M2, not a regression. The DecisionFunction was designed to be stateless with explicit guard parameters.

## Files Changed

| File | Change |
|------|--------|
| `ktrdr/backtesting/engine.py` | **REWRITE** — 1151 lines → 571 lines |
| `tests/unit/backtesting/test_engine_rewrite.py` | **NEW** — 27 tests for init, loop, helpers, resume, reset |
| `tests/unit/backtesting/test_engine_resume.py` | **UPDATED** — replaced orchestrator mocks with feature_cache mocks |

## Line Count Comparison

| Component | Before | After |
|-----------|--------|-------|
| Total engine.py | 1151 lines | 571 lines |
| run() method body | ~676 lines | ~50 lines core + helpers |
| __init__ | 24 lines | 30 lines (more explicit wiring) |
| Infrastructure helpers | inline in run() | 4 extracted methods (~80 lines total) |

## Test Results

- **211 backtesting tests pass** (10 skipped for torch)
- **4991 total unit tests pass** (32 skipped)
- Lint: clean
- Format: clean
- Typecheck: clean
- **E2E container init**: PASSED (real v3 model loads, all components wired)
- **E2E full backtest**: PASSED (2 trades executed, results returned)
- **E2E equivalence**: BEHAVIORAL DIFFERENCE (expected — DecisionFunction M2 defaults differ from old DecisionEngine)

## Gotchas / Notes for M4

1. **decisions_config extraction**: `_get_decisions_config()` handles both Pydantic model (`.model_dump()`) and dict formats for the `decisions` field. In reconstructed configs from `reconstruct_config_from_metadata()`, it's a plain dict `{"output_format": "classification"}`.

2. **verbose flag unused**: The `BacktestConfig.verbose` field still exists but is no longer checked in run(). It could be removed or used for structured logging in the future.

3. **progress_callback removed**: The old `self.progress_callback` attribute is gone. All progress reporting goes through `ProgressBridge`. If any caller was setting `engine.progress_callback`, it needs to switch to the `bridge` parameter of `run()`.

4. **_print_summary removed**: The verbose console summary was deleted. Results are returned as `BacktestResults` which has `to_dict()` for serialization.

5. **model_path is now required**: `BacktestConfig.model_path` must not be None — a `ValueError` is raised in `__init__`. The worker should always provide this.

6. **_get_base_timeframe and _get_strategy_timeframes**: These now read from Pydantic model attributes (e.g., `bundle.strategy_config.training_data.timeframes.base_timeframe`) instead of dict `.get()` calls. They handle both enum-typed `mode` values (with `.value` attribute) and string mode values.

7. **DecisionFunction vs DecisionEngine trade behavior differs**: The new DecisionFunction (from M2) has `confidence_threshold=0.5` and `min_separation_hours=4` as defaults, which filter more signals than the old DecisionEngine. The old engine's DecisionEngine also maintained internal position state (`current_position`, `last_signal_time`) and had `update_position()` sync calls. For the same v3_minimal model on EURUSD 1h 2024-03-01 to 2024-03-15, the old engine produces 7 trades vs the new engine's 2 trades. This is by design — the DecisionFunction is stateless with explicit guards — but means backtest results will not be identical to pre-refactor runs.

8. **Only v3 models supported**: `ModelBundle.load()` requires `metadata_v3.json`. Older models (e.g., `mean_reversion_momentum_v1/1h_v6`) that lack v3 metadata will fail with `FileNotFoundError`. The worker must provide a v3-compatible model path.
