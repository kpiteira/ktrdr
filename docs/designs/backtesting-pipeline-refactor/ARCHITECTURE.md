# Backtesting Pipeline Refactor: Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      BacktestWorker                             │
│  (receives HTTP request, manages operation lifecycle)           │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                   BacktestingEngine                       │  │
│  │  (owns the pipeline, connects components)                 │  │
│  │                                                           │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐   │  │
│  │  │ ModelBundle  │  │ FeatureCache │  │ DecisionFunc   │   │  │
│  │  │ (load once)  │──│ (precompute) │──│ (stateless)    │   │  │
│  │  └─────────────┘  └──────────────┘  └────────────────┘   │  │
│  │                                            │              │  │
│  │                                     ┌──────┴──────┐       │  │
│  │  ┌─────────────────┐               │ Position    │       │  │
│  │  │ Performance     │◄──────────────│ Manager     │       │  │
│  │  │ Tracker         │               │ (sole       │       │  │
│  │  └─────────────────┘               │  tracker)   │       │  │
│  │                                     └─────────────┘       │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Infrastructure: ProgressBridge, CheckpointService, Cancellation│
└─────────────────────────────────────────────────────────────────┘
```

## Components

### ModelBundle

**Responsibility:** Load model artifacts from disk exactly once. Immutable after creation.

**Location:** `ktrdr/backtesting/model_bundle.py` (NEW)

**Inputs:**
- `model_path: str` — path to model directory (e.g., `/app/models/strategy_name/1h_v5`)

**Outputs:**
- Frozen dataclass with: `model` (nn.Module in eval mode on CPU), `metadata` (ModelMetadata), `feature_names` (ordered list), `strategy_config` (reconstructed StrategyConfigurationV3)

**Interface:**

```python
@dataclass(frozen=True)
class ModelBundle:
    model: torch.nn.Module
    metadata: ModelMetadata
    feature_names: list[str]
    strategy_config: StrategyConfigurationV3

    @classmethod
    def load(cls, model_path: str) -> "ModelBundle": ...
```

**Internal steps:**
1. Read `metadata_v3.json` → `ModelMetadata` (JSON, no torch)
2. Read `features.json` → extract `feature_count` for input_size (JSON, no torch)
3. Build model architecture from metadata's model config
4. `torch.load("model.pt", map_location="cpu", weights_only=True)` → state dict
5. `model.load_state_dict(state_dict)` + `model.eval()`
6. Reconstruct `StrategyConfigurationV3` from metadata (moves logic currently on `BacktestingService`)

**What it replaces:**
- `ModelLoader` (deleted)
- `ModelStorage.load_model()` calls during backtesting
- `BaseNeuralModel.load_model()` calls during backtesting
- `BacktestingService.reconstruct_config_from_metadata()` (moved here)
- `BacktestingService.load_v3_metadata()` (moved here)
- `BacktestingService.is_v3_model()` (moved here)

---

### DecisionFunction

**Responsibility:** Map (features, position, bar) → TradingDecision. Stateless — all context passed in.

**Location:** `ktrdr/backtesting/decision_function.py` (NEW)

**Inputs per call:**
- `features: dict[str, float]` — pre-computed fuzzy membership values
- `position: PositionStatus` — current position from PositionManager
- `bar: pd.Series` — current OHLCV bar (for timestamp + price)
- `last_signal_time: Optional[pd.Timestamp]` — for signal separation filter

**Output:** `TradingDecision`

**Interface:**

```python
class DecisionFunction:
    def __init__(self, model: torch.nn.Module, decisions_config: dict): ...
    def __call__(self, features, position, bar, last_signal_time=None) -> TradingDecision: ...
```

**Internal steps:**
1. Convert features dict → ordered tensor (using feature name order from init)
2. Run model forward pass → probabilities
3. Extract signal (argmax) and confidence
4. Apply filters: confidence threshold, signal separation, position awareness
5. Return `TradingDecision`

**Filters preserved from current `DecisionEngine._apply_position_logic()`:**
- Confidence threshold (from `decisions.confidence_threshold`)
- Min signal separation (from `decisions.filters.min_signal_separation`)
- Position awareness: don't BUY when LONG, don't SELL when FLAT, no SHORT positions

**What it replaces:**
- `DecisionEngine` (for backtesting path only — class preserved for future use)
- `DecisionOrchestrator.make_decision()` steps 4-6 (model loading, feature filtering, orchestrator overrides)
- `PositionState` position tracking
- Manual position sync between DecisionEngine and PositionManager

---

### BacktestingEngine (Refactored)

**Responsibility:** Own the pipeline. Wire components, run simulation loop, produce results.

**Location:** `ktrdr/backtesting/engine.py` (REWRITE)

**Interface:**

```python
class BacktestingEngine:
    def __init__(self, config: BacktestConfig): ...
    def run(self, bridge=None, cancellation_token=None, checkpoint_callback=None, resume_start_bar=None) -> BacktestResults: ...
    def resume_from_context(self, context: BacktestResumeContext) -> pd.DataFrame: ...
```

**Init wiring:**

| Step | Component | Source |
|------|-----------|--------|
| 1 | `ModelBundle.load(model_path)` | disk (one torch.load) |
| 2 | `FeatureCache(strategy_config, metadata)` | from ModelBundle |
| 3 | `DecisionFunction(model, decisions_config)` | from ModelBundle |
| 4 | `PositionManager(capital, commission, slippage)` | from BacktestConfig |
| 5 | `PerformanceTracker()` | new instance |
| 6 | `DataRepository()` | for data loading |

**Simulation loop structure:**

```
run():
  data = _load_historical_data()           # multi-TF aware, returns dict[str, DataFrame]
  feature_cache.precompute(data)           # pre-compute all features

  for bar in data[base_tf][warmup:]:       # skip first 50 bars
    features = feature_cache.get(timestamp)
    decision = decide(features, position_mgr.position, bar, last_signal_time)
    if decision.signal != HOLD:
      trade = position_mgr.execute_trade(signal, price, timestamp, symbol)
      if trade: last_signal_time = timestamp
    perf_tracker.update(timestamp, price, portfolio_value, position)
    _report_progress(...)                  # extracted helper
    _maybe_checkpoint(...)                 # extracted helper
    _check_cancellation(...)               # extracted helper

  position_mgr.force_close(final_price, final_timestamp, symbol)
  return _generate_results()
```

**What it replaces:**
- Current 1150-line engine.py → ~250 lines (core loop + helpers + data loading)
- `DecisionOrchestrator` import and usage (removed from backtesting path)
- Triple position tracking → single `PositionManager` + `last_signal_time` local variable

---

### Unchanged Components

| Component | File | Why unchanged |
|-----------|------|---------------|
| `FeatureCache` | `feature_cache.py` | Already clean, correct multi-TF support |
| `PositionManager` | `position_manager.py` | Single-responsibility, becomes sole position tracker |
| `PerformanceTracker` | `performance.py` | Clean, no changes needed |
| `BacktestConfig` | `engine.py` | Simple dataclass, stays |
| `BacktestResults` | `engine.py` | Simple dataclass, stays |

### Modified Components

| Component | File | Change |
|-----------|------|--------|
| `BacktestWorker` | `backtest_worker.py` | Consolidate `_execute_backtest_work` / `_execute_resumed_backtest_work` into shared method |
| `BacktestingService` | `backtesting_service.py` | Remove static metadata utilities (moved to `ModelBundle`) |
| `checkpoint_builder` | `checkpoint_builder.py` | Adapt to new engine structure (no orchestrator reference) |
| `checkpoint_restore` | `checkpoint_restore.py` | Adapt to new engine structure |
| `base_model.py` | `neural/models/base_model.py` | Add `map_location="cpu"` at line 343 (correctness fix even though backtesting won't use this path) |

### Deleted Components

| Component | File | Reason |
|-----------|------|--------|
| `ModelLoader` | `model_loader.py` | Replaced by `ModelBundle` |

### Preserved but Decoupled

These components are deliberately kept in the codebase but are no longer part of the backtesting pipeline. Each must have a module-level docstring and inline comments explaining their status, so future developers don't wonder why two decision-making systems coexist.

| Component | File | Status | Documentation Required |
|-----------|------|--------|----------------------|
| `DecisionOrchestrator` | `decision/orchestrator.py` | No longer imported by backtesting | Module docstring: explain this is for future paper/live trading, backtesting uses `BacktestingEngine` directly. Note the triple-load and triple-position-tracking problems that motivated the split. |
| `DecisionEngine` | `decision/engine.py` | No longer imported by backtesting | Module docstring: explain this is for future paper/live trading, backtesting uses `DecisionFunction`. Note the stateful position tracking that was replaced by stateless position-as-input. |
| `BaseNeuralModel` | `neural/models/base_model.py` | Fix `map_location`; not used by backtesting pipeline | Comment on `load_model()`: explain backtesting uses `ModelBundle.load()` instead, this path is for future paper/live trading. |
| `ModelStorage.load_model()` | `training/model_storage.py` | Not called during backtesting | Comment: backtesting loads via `ModelBundle`; this method is used by training pipeline and future paper/live. |
| `_compute_features_realtime()` | `decision/orchestrator.py` | Dead for backtesting, needed for future paper/live | Inline comment: explain this is the non-cached feature path for real-time trading modes. Backtesting uses `FeatureCache` exclusively. |

**Why document, not delete:** These components represent significant work and will be needed if paper/live trading is implemented. Deleting them would require re-implementing from scratch. But without documentation, they look like dead code or a competing implementation, which leads to confusion ("which decision engine should I use?") and accidental coupling ("I'll just import the orchestrator since it's there").

---

## Data Flow

### Init Phase

```
BacktestConfig
    │
    ▼
ModelBundle.load(model_path)
    │
    ├──► torch.load("model.pt", map_location="cpu") ──► nn.Module (eval mode)
    ├──► json.load("metadata_v3.json") ──► ModelMetadata
    ├──► json.load("features.json") ──► feature_names, input_size
    └──► reconstruct_strategy_config(metadata) ──► StrategyConfigurationV3
                │                                         │
                ▼                                         ▼
        DecisionFunction(model, config)          FeatureCache(config, metadata)
```

### Simulation Phase

```
For each bar (after warmup):

  timestamp ──► FeatureCache.get_features_for_timestamp()
                    │
                    ▼
              dict[str, float]  (ordered fuzzy membership values)
                    │
                    ├──► DecisionFunction(features, position, bar, last_signal_time)
                    │         │
                    │         ├── features → tensor
                    │         ├── model.forward(tensor) → probabilities
                    │         ├── argmax → raw signal
                    │         ├── apply_filters(signal, confidence, position) → final signal
                    │         │
                    │         ▼
                    │    TradingDecision
                    │         │
                    │    if signal != HOLD:
                    │         │
                    │         ▼
                    │    PositionManager.execute_trade(signal, price, timestamp, symbol)
                    │         │
                    │         ▼
                    │    Trade (or None)
                    │
                    └──► PerformanceTracker.update(timestamp, price, portfolio_value, position)
```

## State Management

| State | Owner | Lifecycle | Notes |
|-------|-------|-----------|-------|
| Model weights | `ModelBundle.model` | Immutable after init | Frozen dataclass prevents mutation |
| Feature cache | `FeatureCache._cached_features` | Set once during precompute, read-only during simulation | DataFrame, indexed by timestamp |
| Current position | `PositionManager.current_position` | Mutated by `execute_trade()` and `force_close_position()` | SOLE position tracker |
| Trade history | `PositionManager.trade_history` | Appended by `execute_trade()` | List of completed Trade objects |
| Cash/capital | `PositionManager.current_capital` | Mutated by `execute_trade()` | Tracks available capital |
| Equity curve | `PerformanceTracker.equity_curve` | Appended by `update()` | List of (timestamp, portfolio_value) |
| Last signal time | Local variable in `run()` | Updated when trade executes | NOT a class attribute — scoped to simulation |

**Key change:** `last_signal_time` moves from being class state on `DecisionEngine` to a local variable in the simulation loop. This eliminates the need for position sync between components.

## Error Handling

| Error | Where | Behavior |
|-------|-------|----------|
| Model file not found | `ModelBundle.load()` | `FileNotFoundError` — propagates to worker, fails operation |
| Model load failure (corrupt file) | `ModelBundle.load()` | `RuntimeError` from torch — propagates to worker, fails operation |
| No v3 metadata | `ModelBundle.load()` | `FileNotFoundError` for `metadata_v3.json` — clear error message |
| Data not found | `_load_historical_data()` | `ValueError` — propagates to worker, fails operation |
| Feature computation fails | `FeatureCache.compute_all_features()` | `ValueError` with missing feature details — propagates |
| Feature not found for timestamp | `FeatureCache.get_features_for_timestamp()` | Returns `None` — loop `continue`s (warmup period) |
| Inference failure | `DecisionFunction.__call__()` | Catches exception, returns HOLD decision with error metadata |
| Cancellation | `_check_cancellation()` | `CancellationError` — caught by worker, saves checkpoint |
| Checkpoint save failure | `_maybe_checkpoint()` | Warning log, continues simulation (non-fatal) |

**Design decision:** Inference errors during simulation produce HOLD decisions (current behavior, preserved). This prevents a single bad bar from killing a multi-hour backtest. The error is logged and included in decision metadata for post-analysis.

## Integration Points

### BacktestWorker → BacktestingEngine

No interface change. Worker creates `BacktestConfig` and passes to `BacktestingEngine.__init__()`, then calls `run()`. The worker doesn't know about `ModelBundle`, `DecisionFunction`, or any internals.

```python
# Worker code stays the same:
engine = BacktestingEngine(config=engine_config)
results = await asyncio.to_thread(
    engine.run,
    bridge=bridge,
    cancellation_token=cancellation_token,
    checkpoint_callback=checkpoint_callback,
)
```

### BacktestingEngine → FeatureCache

Unchanged interface. `FeatureCache.__init__` takes `(config, model_metadata)` and provides `compute_all_features(data)` and `get_features_for_timestamp(ts)`.

### BacktestingEngine → PositionManager

Unchanged interface. Already clean and single-responsibility.

### BacktestingService → ModelBundle

Static utilities move from `BacktestingService` to `ModelBundle`:

| Before | After |
|--------|-------|
| `BacktestingService.is_v3_model(path)` | `ModelBundle.is_v3(path)` |
| `BacktestingService.load_v3_metadata(path)` | `ModelMetadata.from_file(path)` |
| `BacktestingService.reconstruct_config_from_metadata(meta)` | `ModelBundle._reconstruct_config(meta)` |

`BacktestingService` can delegate to these or call them directly. No behavior change.

### Checkpoint Integration

Checkpoint builder currently references `engine.orchestrator` and `engine.position_manager`. After refactor, it references `engine.position_manager` only (orchestrator removed). The checkpoint state shape (cash, positions, trades, equity_samples, bar_index, original_request) stays the same.

```python
# checkpoint_builder.py changes:
# BEFORE: engine.orchestrator.strategy_name
# AFTER:  engine.bundle.metadata.strategy_name
```

---

## Milestone Structure

### M1: ModelBundle + map_location fix (foundation)

Create `ModelBundle` as the single model loading point. Fix `map_location="cpu"` on `base_model.py:343`. Move metadata utilities from `BacktestingService`. Delete `ModelLoader`. Validate with unit tests + fast Docker container test.

**E2E gate:** `ModelBundle.load()` succeeds inside a CPU-only Docker container with an MPS-trained model.

### M2: DecisionFunction (stateless decisions)

Create `DecisionFunction` with all filters from current `DecisionEngine._apply_position_logic()`. Unit test: same signal outputs for same inputs as current DecisionEngine. No integration yet — engine still uses orchestrator.

**E2E gate:** Unit tests prove identical decision outputs for a test fixture of (features, position, bar) inputs.

### M3: Engine rewrite (pipeline integration)

Rewire `BacktestingEngine` to use `ModelBundle` + `FeatureCache` + `DecisionFunction` + `PositionManager` directly. Remove `DecisionOrchestrator` from import chain. Clean simulation loop with extracted helpers. Update checkpoint builder/restore.

**E2E gate:** Backtest with `mean_reversion_momentum_v1` strategy produces equivalent metrics (same trade count, similar PnL within floating-point tolerance) to current engine.

### M4: Worker consolidation + cleanup

Consolidate `_execute_backtest_work` / `_execute_resumed_backtest_work` in worker. Remove dead code (`_compute_features_realtime`, commented-out debug lines, verbose print blocks). Remove `model_full.pt` from load path.

**E2E gate — the original bug scenario:**
```bash
uv run ktrdr research -m haiku -f "Design a multi-timeframe strategy using RSI and Bollinger Bands on 1h and 5m data for EURUSD"
```
Full agent cycle: design → train (MPS) → backtest (CPU Docker) → assess. This is the exact scenario that triggered the original `mps` device error. If it completes, the refactor is proven. Resume from checkpoint also works.
