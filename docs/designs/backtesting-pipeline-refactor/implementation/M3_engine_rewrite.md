---
design: docs/designs/backtesting-pipeline-refactor/DESIGN.md
architecture: docs/designs/backtesting-pipeline-refactor/ARCHITECTURE.md
---

# M3: Engine Rewrite (Pipeline Integration)

## Goal

Rewire `BacktestingEngine` to use `ModelBundle` + `FeatureCache` + `DecisionFunction` + `PositionManager` directly, replacing the `DecisionOrchestrator` dependency. Clean the simulation loop from 676 lines to ~80 lines core + extracted helpers. Update checkpoint builder/restore for the new engine structure. Validate by comparing backtest results against the current engine for a known strategy.

## Tasks

### Task 3.1: Rewrite BacktestingEngine.__init__

**File(s):** `ktrdr/backtesting/engine.py`
**Type:** CODING
**Estimated time:** 1.5 hours

**Description:**
Replace the `DecisionOrchestrator` initialization with direct component wiring: `ModelBundle.load()` → `FeatureCache` + `DecisionFunction` + `PositionManager` + `PerformanceTracker`. Remove the lazy import of `DecisionOrchestrator`.

**Implementation Notes:**
- Remove the lazy import block (lines 101-108):
  ```python
  # DELETE:
  from ..decision.orchestrator import DecisionOrchestrator
  self.orchestrator = DecisionOrchestrator(...)
  ```
- Replace with:
  ```python
  from .model_bundle import ModelBundle
  from .decision_function import DecisionFunction

  self.bundle = ModelBundle.load(config.model_path or self._auto_discover_model(config))
  self.feature_cache = FeatureCache(
      config=self.bundle.strategy_config,
      model_metadata=self.bundle.metadata,
  )
  decisions_config = self.bundle.strategy_config.get("decisions", {})
  self.decide = DecisionFunction(self.bundle.model, self.bundle.feature_names, decisions_config)
  ```
- `self.strategy_name` comes from `self.bundle.metadata` instead of `self.orchestrator.strategy_name`
- Keep `self.repository`, `self.position_manager`, `self.performance_tracker` as-is
- Model auto-discovery: port `_auto_discover_model_path()` from `DecisionOrchestrator._auto_discover_model()` (or simplify — for backtesting, model_path should always be provided by the worker)
- `_get_base_timeframe()` and `_get_strategy_timeframes()` should read from `self.bundle.strategy_config` instead of `self.orchestrator.strategy_config`
- `_load_historical_data()` is unchanged in logic, just reads config from `self.bundle.strategy_config` instead of `self.orchestrator.strategy_config`

**Testing Requirements:**
- [ ] `BacktestingEngine.__init__` creates all components without importing DecisionOrchestrator
- [ ] `engine.bundle` is a ModelBundle with model in eval mode
- [ ] `engine.decide` is a DecisionFunction
- [ ] `engine.feature_cache` is a FeatureCache configured from bundle's strategy_config

**Acceptance Criteria:**
- [ ] No import of `DecisionOrchestrator` in `engine.py`
- [ ] `ModelBundle.load()` called exactly once during init
- [ ] All components wired from ModelBundle outputs
- [ ] `_get_base_timeframe()` and `_get_strategy_timeframes()` work with bundle's strategy_config

---

### Task 3.2: Rewrite simulation loop

**File(s):** `ktrdr/backtesting/engine.py`
**Type:** CODING
**Estimated time:** 2.5 hours

**Description:**
Rewrite `run()` from 676 lines to a clean pipeline. Extract infrastructure (progress, checkpoints, cancellation) to focused helper methods. Remove debug tracking, position sync code, verbose print blocks, signal counting, and infinite loop detection.

**Implementation Notes:**

Core loop structure (from ARCHITECTURE.md):
```python
def run(self, bridge=None, cancellation_token=None, checkpoint_callback=None, resume_start_bar=None):
    execution_start = time.time()

    # 1. Load data
    multi_tf_data = self._load_historical_data()
    base_tf = self._get_base_timeframe()
    data = multi_tf_data[base_tf]
    if data.empty:
        raise ValueError(f"No data for {self.config.symbol} {self.config.timeframe}")

    # 2. Pre-compute features
    self.feature_cache.compute_all_features(multi_tf_data)

    # 3. Simulate
    start_idx = (resume_start_bar + 50) if resume_start_bar else 50
    last_signal_time = None  # LOCAL variable, not class state

    for idx in range(start_idx, len(data)):
        bar = data.iloc[idx]
        price = bar["close"]
        timestamp = cast(pd.Timestamp, bar.name)

        features = self.feature_cache.get_features_for_timestamp(timestamp)
        if features is None:
            continue

        decision = self.decide(
            features=features,
            position=self.position_manager.current_position_status,
            bar=bar,
            last_signal_time=last_signal_time,
        )

        if decision.signal != Signal.HOLD:
            trade = self.position_manager.execute_trade(
                signal=decision.signal, price=price,
                timestamp=timestamp, symbol=self.config.symbol,
                decision_metadata={"confidence": decision.confidence},
            )
            if trade:
                last_signal_time = timestamp

        self.position_manager.update_position(price, timestamp)
        portfolio_value = self.position_manager.get_portfolio_value(price)
        self.performance_tracker.update(
            timestamp=timestamp, price=price,
            portfolio_value=portfolio_value,
            position=self.position_manager.current_position_status,
        )

        self._report_progress(idx, start_idx, len(data), timestamp, portfolio_value, bridge)
        self._maybe_checkpoint(idx, start_idx, timestamp, checkpoint_callback)
        self._check_cancellation(idx, start_idx, len(data), cancellation_token)

    # 4. Force-close and results
    self._force_close_position(data)
    return self._generate_results(execution_start)
```

What to remove from the current loop:
- `signal_counts`, `non_hold_signals`, `trade_attempts` debug tracking (lines 328-330)
- `last_processed_timestamp` / `repeated_timestamp_count` infinite loop detection (lines 333-396)
- `end_date` safety check (lines 398-411) — data already filtered in `_load_historical_data()`
- `historical_data = data.iloc[:idx+1]` (line 414) — unused by DecisionFunction
- `portfolio_state` dict (lines 417-420) — unused by DecisionFunction
- `self.orchestrator.decision_engine.update_position()` manual sync (line 573-574)
- All desync detection and logging (lines 509-606)
- All `self.config.verbose` print blocks
- `self.progress_callback` legacy callback (separate from bridge)
- Verbose summary printing at loop end (lines 851-900)
- `sim_span` manual span management — keep the tracer but use simpler spans

Extract to helpers:
- `_report_progress(idx, start_idx, total, timestamp, portfolio_value, bridge)` — ProgressBridge updates
- `_maybe_checkpoint(idx, start_idx, timestamp, callback)` — checkpoint callback invocation
- `_check_cancellation(idx, start_idx, total, token)` — cancellation check
- `_force_close_position(data)` — end-of-backtest position closure
- `_generate_results(execution_start)` — compile BacktestResults (simplify from current 3-param signature)

**Testing Requirements:**
- [ ] `run()` executes without errors on a mock engine setup
- [ ] `last_signal_time` is a local variable, not stored on `self`
- [ ] No import of `DecisionOrchestrator` anywhere in the file
- [ ] Infrastructure helpers called at correct intervals

**Acceptance Criteria:**
- [ ] `run()` core loop under 80 lines (excluding helper method definitions)
- [ ] No debug tracking variables in the loop
- [ ] No `self.orchestrator` references anywhere in the file
- [ ] No verbose print blocks in the loop
- [ ] Progress, checkpoint, and cancellation extracted to helpers
- [ ] All existing `run()` tests adapted and passing

---

### Task 3.3: Update resume_from_context

**File(s):** `ktrdr/backtesting/engine.py`
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Update `resume_from_context()` to use the new component structure. It currently calls `self.orchestrator.prepare_feature_cache(multi_tf_data)` — this needs to call `self.feature_cache.compute_all_features(multi_tf_data)` instead.

**Implementation Notes:**
- Change line 147: `self.orchestrator.prepare_feature_cache(multi_tf_data)` → `self.feature_cache.compute_all_features(multi_tf_data)`
- `_load_historical_data()` already works (updated in Task 3.1 to use bundle's strategy_config)
- `_restore_portfolio_state()` is unchanged (only touches PositionManager)
- `_get_base_timeframe()` already updated in Task 3.1
- The `reset()` method needs updating: remove `self.orchestrator.reset_state()`, keep `self.position_manager.reset()` and `self.performance_tracker.reset()`

**Testing Requirements:**
- [ ] `resume_from_context()` works with mock checkpoint context
- [ ] Feature cache populated after resume
- [ ] Portfolio state restored correctly
- [ ] `reset()` works without orchestrator

**Acceptance Criteria:**
- [ ] No `self.orchestrator` references in `resume_from_context()` or `reset()`
- [ ] Feature computation uses `self.feature_cache.compute_all_features()`
- [ ] Existing resume tests adapted and passing

---

### Task 3.4: Update checkpoint builder/restore

**File(s):** `ktrdr/backtesting/checkpoint_builder.py`, `ktrdr/backtesting/checkpoint_restore.py`
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Adapt checkpoint builder to the new engine structure. The checkpoint state shape (cash, positions, trades, equity_samples, bar_index, original_request) is unchanged — only the source of `strategy_name` changes.

**Implementation Notes:**

`checkpoint_builder.py`:
- `_build_original_request()` currently reads `engine.config` — this is unchanged
- The builder accesses `engine.position_manager` and `engine.performance_tracker` directly — both are unchanged
- If `strategy_name` is read from `engine.orchestrator.strategy_name` anywhere, change to `engine.strategy_name` (which comes from `engine.bundle.metadata`)
- Actually, reviewing the current code: `checkpoint_builder.py` only accesses `engine.position_manager`, `engine.performance_tracker`, and `engine.config`. It does NOT access `engine.orchestrator`. So this file may need NO changes at all. Verify and confirm.

`checkpoint_restore.py`:
- `BacktestResumeContext` is a simple dataclass — no engine dependency, no changes needed
- `restore_from_checkpoint()` only accesses `CheckpointService` — no engine dependency, no changes needed

**Testing Requirements:**
- [ ] Existing `test_checkpoint_builder.py` tests pass (may need mock updates if they mock orchestrator)
- [ ] Existing `test_checkpoint_restore.py` tests pass
- [ ] Round-trip test: build checkpoint → restore → verify state matches

**Acceptance Criteria:**
- [ ] No `engine.orchestrator` references in checkpoint code
- [ ] Checkpoint state shape unchanged (backward compatible with existing checkpoints)
- [ ] All checkpoint tests pass

---

### Task 3.5: M3 Validation — equivalence test

**File(s):** Tests
**Type:** VALIDATION
**Estimated time:** 1.5 hours

**Description:**
Validate the refactored engine produces equivalent results to the current engine. This is the most critical validation in the refactor — it proves the rewrite didn't change behavior.

**Validation Steps:**
1. Run `uv run pytest tests/unit/backtesting/ -x -q` — all pass
2. Run `make quality` — clean
3. Equivalence test with real model:
   - Run a backtest using the refactored engine with `mean_reversion_momentum_v1` strategy, EURUSD 1h, 2024-03-01 to 2024-04-01
   - Compare key metrics against a saved baseline from the current engine:
     - Trade count must match exactly
     - Total PnL within floating-point tolerance (< $0.01 difference)
     - Win rate within 1 percentage point
   - The baseline should be captured BEFORE any changes (or use the current engine in a test that runs both)
4. Grep validation:
   - `grep -r "DecisionOrchestrator" ktrdr/backtesting/` → no matches
   - `grep -r "decision_engine" ktrdr/backtesting/engine.py` → no matches
   - `grep -r "self.orchestrator" ktrdr/backtesting/` → no matches
5. Container test (same as M1 but through the engine):
   ```bash
   docker exec ktrdr-prod-backtest-worker-1-1 /app/.venv/bin/python -c "
   from ktrdr.backtesting.engine import BacktestingEngine, BacktestConfig
   config = BacktestConfig(
       strategy_config_path='strategies/mean_reversion_momentum_v1.yaml',
       model_path='/app/models/rhythm_dancer_multibeat_20250211/1h_v6',
       symbol='EURUSD', timeframe='1h',
       start_date='2024-03-01', end_date='2024-03-15',
   )
   engine = BacktestingEngine(config=config)
   print(f'Engine initialized: {engine.strategy_name}')
   print(f'Model device: {next(engine.bundle.model.parameters()).device}')
   print(f'Feature count: {len(engine.bundle.feature_names)}')
   print(f'DecisionFunction: {type(engine.decide).__name__}')
   "
   ```

**Acceptance Criteria:**
- [ ] All unit tests pass
- [ ] Quality gates clean
- [ ] No `DecisionOrchestrator` or `decision_engine` imports in backtesting module
- [ ] Engine initializes in Docker container with MPS-trained model
- [ ] Backtest results equivalent to current engine for known strategy
