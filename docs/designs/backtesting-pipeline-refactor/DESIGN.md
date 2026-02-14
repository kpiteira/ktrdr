# Backtesting Pipeline Refactor: Design

## Problem Statement

The backtesting system was built incrementally over many iterations and has accumulated significant structural debt. A model trained on Apple Silicon (MPS) cannot be backtested on a CPU-only Docker worker because `torch.load` is called without `map_location="cpu"` — but this bug is a symptom of a deeper problem: the model is loaded THREE times through three different code paths, and only one of them has the correct parameter. The architecture makes bugs like this inevitable.

### Specific Problems

1. **Triple model loading** — The same model is loaded 3 times during backtest init: once by `ModelLoader` (metadata extraction), once by `DecisionEngine` → `BaseNeuralModel` (inference), and conditionally a third time at decision time (lazy multi-symbol support). The MPS bug exists because path #2 is missing `map_location="cpu"`.

2. **Triple position tracking** — Position state is independently tracked by `PositionManager` (authoritative), `DecisionEngine.current_position` (for signal filtering), and `PositionState` in the orchestrator (per-symbol). The engine must manually sync them after every trade, and desync detection code exists because they drift apart.

3. **God-object orchestrator** — `DecisionOrchestrator` (842 lines) handles: strategy loading, indicator/fuzzy initialization, model loading, FeatureCache creation, model auto-discovery, feature computation (2 paths), decision making, position management, risk management, and decision history. Too many responsibilities in one class.

4. **676-line simulation loop** — `BacktestingEngine.run()` mixes simulation logic with debug tracking, infinite loop detection, 3 progress mechanisms, verbose console output, commented-out code, and "IMPOSSIBLE" state assertions.

5. **Dead code** — `_compute_features_realtime()` (75 lines) in the orchestrator is never called during backtesting. It uses v2-era column-matching heuristics that don't work with v3 strategies.

6. **`model_full.pt` security risk** — Two model files are saved: `model_full.pt` (full pickle, `weights_only=False`) and `model.pt` (state dict, `weights_only=True`). The pickle approach enables arbitrary code execution and breaks when class definitions change. Path A uses the risky pickle path.

7. **Circular dependency** — The orchestrator (decision layer) imports `BacktestingService` (API service layer) to access static utility methods like `is_v3_model()` and `reconstruct_config_from_metadata()`.

8. **Checkpoint duplication** — `_execute_backtest_work` and `_execute_resumed_backtest_work` in the worker share ~80% of their code.

## Goals

1. **One model load** — Model loaded exactly once, with correct `map_location="cpu"`, using `weights_only=True`
2. **One position tracker** — `PositionManager` is the single source of truth; position passed as input to decision function
3. **Clean pipeline** — `Data → Features → Decision → Trade → Metrics`, each step has one owner
4. **Readable simulation loop** — Core loop under 80 lines, infrastructure (progress, checkpoints, cancellation) extracted to helpers
5. **No dead code** — Remove unused realtime feature path, commented-out debug code, dead model loading paths
6. **Correct layering** — No upward dependencies from decision layer to API service layer

## Non-Goals

1. **Paper/live trading support** — Not needed now. `DecisionOrchestrator` can be preserved for future paper/live modes but is removed from the backtesting path
2. **New feature computation logic** — `FeatureCache` already works correctly; we keep it
3. **Model storage changes** — `ModelStorage.save_model()` is fine; the save-side round-trip fix stays as defense-in-depth
4. **Worker architecture changes** — `BacktestWorker` structure stays; we only consolidate the fresh/resume duplication
5. **Performance optimization** — The current bar-by-bar simulation is fast enough; vectorization is a separate concern

## Architecture

### Current Flow (What's Wrong)

```
BacktestWorker._execute_backtest_work()
  └─ BacktestingEngine.__init__()
       └─ DecisionOrchestrator.__init__()
            ├─ ModelLoader.load_model()           ← LOAD A: model_full.pt + all JSON metadata
            ├─ DecisionEngine.__init__()
            │    └─ BaseNeuralModel.load_model()  ← LOAD B: model.pt, NO map_location ← BUG
            ├─ _create_feature_cache()            ← imports BacktestingService ← circular dep
            └─ PositionState()                    ← position tracker #3
       └─ PositionManager()                       ← position tracker #1
  └─ engine.run() [676 lines]
       ├─ for each bar:
       │    ├─ orchestrator.make_decision()
       │    │    ├─ [lazy LOAD C if model not loaded]
       │    │    ├─ [filter features against metadata] ← redundant with FeatureCache
       │    │    └─ DecisionEngine.generate_decision()
       │    │         └─ DecisionEngine.current_position ← position tracker #2
       │    ├─ position_manager.execute_trade()
       │    ├─ decision_engine.update_position()  ← manual sync!
       │    └─ [debug tracking, infinite loop detection, 3x progress, verbose print...]
       └─ [100+ lines of summary printing]
```

### Proposed Flow

```
BacktestWorker._execute_backtest_work()
  └─ BacktestingEngine.__init__(config)
       ├─ StrategyLoader.load(config_path)        ← YAML → validated dict
       ├─ ModelBundle.load(model_path)             ← ONE load: state dict + JSON metadata
       ├─ FeatureCache(strategy, metadata)         ← existing, mostly unchanged
       ├─ PositionManager(capital, commission...)   ← existing, unchanged, SOLE position tracker
       └─ DecisionFunction(model, decisions_config) ← stateless: (features, position) → signal
  └─ engine.run() [~80 lines]
       ├─ load_multi_tf_data()
       ├─ feature_cache.precompute(data)
       ├─ for each bar:
       │    ├─ features = feature_cache.get(timestamp)
       │    ├─ decision = decision_fn(features, position_mgr.position, bar)
       │    ├─ position_mgr.execute_trade(decision, bar)
       │    └─ performance_tracker.update(bar, portfolio_value)
       │    # Infrastructure extracted to helpers:
       │    ├─ _report_progress(bridge, idx, total)
       │    ├─ _maybe_checkpoint(callback, idx, timestamp)
       │    └─ _check_cancellation(token, idx, total)
       └─ position_mgr.force_close()
       └─ _generate_results()
```

### Key Differences

| Aspect | Before | After |
|--------|--------|-------|
| Model loads | 3 (A: pickle+metadata, B: state dict w/o map_location, C: lazy re-load) | 1 (`ModelBundle.load`, state dict, `map_location="cpu"`) |
| Position trackers | 3 (`PositionManager`, `DecisionEngine.current_position`, `PositionState`) | 1 (`PositionManager`, position passed as input) |
| Simulation loop | 676 lines, mixed concerns | ~80 lines core + helper methods |
| Decision path | Engine → Orchestrator → DecisionEngine → BaseNeuralModel | Engine → DecisionFunction (stateless) |
| Feature validation | 2 places (FeatureCache + orchestrator filtering) | 1 place (FeatureCache) |
| Dependencies | decision → backtesting_service (circular) | No circular dependencies |

## Component Design

### ModelBundle

Replaces `ModelLoader`, the model-loading half of `ModelStorage.load_model()`, and `BaseNeuralModel.load_model()`. Single class that loads everything needed for inference.

```python
@dataclass(frozen=True)
class ModelBundle:
    """Everything needed for inference. Immutable after creation."""
    model: torch.nn.Module          # Ready-to-infer, in eval mode, on CPU
    metadata: ModelMetadata         # From metadata_v3.json
    feature_names: list[str]        # Ordered feature names from model metadata
    strategy_config: dict           # Reconstructed from metadata (for FeatureCache)

    @classmethod
    def load(cls, model_path: str) -> "ModelBundle":
        """Load model artifacts from disk. ONE torch.load, always CPU-safe."""
        path = Path(model_path)

        # 1. Load metadata (JSON only, no torch)
        metadata = ModelMetadata.from_file(path / "metadata_v3.json")
        features_info = json.load(open(path / "features.json"))

        # 2. Determine input size from metadata
        input_size = (
            features_info.get("feature_count")
            or metadata.input_size
        )

        # 3. Build model architecture from config
        model_config = metadata.model_config  # stored in metadata
        model = _build_model(model_config, input_size)

        # 4. Load weights — ONE load, always safe
        state_dict = torch.load(
            path / "model.pt",
            map_location="cpu",
            weights_only=True,
        )
        model.load_state_dict(state_dict)
        model.eval()

        return cls(
            model=model,
            metadata=metadata,
            feature_names=metadata.resolved_features,
            strategy_config=_reconstruct_strategy_config(metadata),
        )
```

**Key decisions:**
- `frozen=True` — immutable after creation, no accidental mutation
- Metadata loaded from JSON only — no torch import needed for metadata extraction
- `_reconstruct_strategy_config` moves from `BacktestingService` static method to here (fixes circular dependency)
- `model_full.pt` is not loaded during backtesting (security improvement)

### DecisionFunction

Replaces `DecisionEngine` + `DecisionOrchestrator.make_decision()` for backtesting. Stateless — all state is passed in.

```python
class DecisionFunction:
    """Stateless decision maker: (features, position, bar) → TradingDecision.

    No model loading, no position tracking, no feature computation.
    Just: prepare tensor → run inference → apply filters → return signal.
    """

    def __init__(self, model: torch.nn.Module, decisions_config: dict):
        self.model = model
        self.confidence_threshold = decisions_config.get("confidence_threshold", 0.5)
        self.min_separation = decisions_config.get("filters", {}).get("min_signal_separation", 4)
        self.position_awareness = decisions_config.get("position_awareness", True)

    def __call__(
        self,
        features: dict[str, float],
        position: PositionStatus,
        bar: pd.Series,
        last_signal_time: Optional[pd.Timestamp] = None,
    ) -> TradingDecision:
        """Generate trading decision. Pure function (no side effects)."""
        timestamp = bar.name
        tensor = self._to_tensor(features)
        nn_output = self._predict(tensor)

        raw_signal = Signal[nn_output["signal"]]
        confidence = nn_output["confidence"]
        final_signal = self._apply_filters(raw_signal, confidence, position, timestamp, last_signal_time)

        return TradingDecision(
            signal=final_signal,
            confidence=confidence,
            timestamp=timestamp,
            reasoning={...},
            current_position=Position(position.value),
        )
```

**Key decisions:**
- `__call__` makes it feel like a function, which is what it is
- `position` is an input parameter, not internal state
- `last_signal_time` is passed in (tracked by the engine, not by the decision function)
- No model loading, no feature computation — single responsibility

### BacktestingEngine (Refactored)

The pipeline owner. Replaces the current engine + orchestrator combination.

```python
class BacktestingEngine:
    def __init__(self, config: BacktestConfig):
        self.config = config

        # Load model bundle (ONE load)
        model_path = config.model_path or self._auto_discover_model_path(config)
        self.bundle = ModelBundle.load(model_path)

        # Feature computation
        self.feature_cache = FeatureCache(
            config=self.bundle.strategy_config,
            model_metadata=self.bundle.metadata,
        )

        # Decision making (stateless)
        decisions_config = self.bundle.strategy_config.get("decisions", {})
        self.decide = DecisionFunction(self.bundle.model, decisions_config)

        # Trade execution and tracking (SOLE position tracker)
        self.position_manager = PositionManager(
            initial_capital=config.initial_capital,
            commission=config.commission,
            slippage=config.slippage,
        )
        self.performance_tracker = PerformanceTracker()

        # Data loading
        self.repository = DataRepository()

    def run(self, bridge=None, cancellation_token=None, checkpoint_callback=None, resume_start_bar=None):
        execution_start = time.time()

        # 1. Load data
        multi_tf_data = self._load_historical_data()
        base_tf = self._get_base_timeframe()
        data = multi_tf_data[base_tf]

        # 2. Pre-compute features
        self.feature_cache.compute_all_features(multi_tf_data)

        # 3. Simulate
        start_idx = (resume_start_bar + 50) if resume_start_bar else 50
        last_signal_time = None

        for idx in range(start_idx, len(data)):
            bar = data.iloc[idx]
            price = bar["close"]
            timestamp = cast(pd.Timestamp, bar.name)

            # Feature lookup
            features = self.feature_cache.get_features_for_timestamp(timestamp)
            if features is None:
                continue

            # Decision (stateless — position passed in, not tracked internally)
            decision = self.decide(
                features=features,
                position=self.position_manager.current_position_status,
                bar=bar,
                last_signal_time=last_signal_time,
            )

            # Execution
            if decision.signal != Signal.HOLD:
                trade = self.position_manager.execute_trade(
                    signal=decision.signal,
                    price=price,
                    timestamp=timestamp,
                    symbol=self.config.symbol,
                    decision_metadata={"confidence": decision.confidence},
                )
                if trade:
                    last_signal_time = timestamp

            # Track performance
            self.performance_tracker.update(
                timestamp=timestamp,
                price=price,
                portfolio_value=self.position_manager.get_portfolio_value(price),
                position=self.position_manager.current_position_status,
            )

            # Infrastructure (extracted to focused helpers)
            self._report_progress(idx, start_idx, len(data), bar, bridge)
            self._maybe_checkpoint(idx, start_idx, timestamp, checkpoint_callback)
            self._check_cancellation(idx, start_idx, len(data), cancellation_token)

        # 4. Force-close and generate results
        self._force_close_position(data)
        return self._generate_results(execution_start)
```

### Files Changed

| File | Action | Notes |
|------|--------|-------|
| `ktrdr/backtesting/model_bundle.py` | **NEW** | `ModelBundle` — single model load point |
| `ktrdr/backtesting/decision_function.py` | **NEW** | `DecisionFunction` — stateless decisions |
| `ktrdr/backtesting/engine.py` | **REWRITE** | Clean pipeline, ~200 lines (from 1150) |
| `ktrdr/backtesting/model_loader.py` | **DELETE** | Replaced by `ModelBundle` |
| `ktrdr/decision/engine.py` | **KEEP** | Preserved for future paper/live use, not imported by backtesting |
| `ktrdr/decision/orchestrator.py` | **KEEP** | Preserved for future paper/live use, not imported by backtesting |
| `ktrdr/neural/models/base_model.py` | **FIX** | Add `map_location="cpu"` (even though backtesting won't use this path anymore, it should be correct) |
| `ktrdr/backtesting/feature_cache.py` | **MINOR** | Unchanged logic, minor interface cleanup |
| `ktrdr/backtesting/backtest_worker.py` | **REFACTOR** | Consolidate fresh/resume code duplication |
| `ktrdr/backtesting/backtesting_service.py` | **REFACTOR** | Move static metadata utilities to `model_bundle.py` |
| `ktrdr/backtesting/position_manager.py` | **UNCHANGED** | Already clean, single-responsibility |
| `ktrdr/backtesting/performance.py` | **UNCHANGED** | Already clean |
| `ktrdr/backtesting/checkpoint_builder.py` | **MINOR** | Adapt to new engine structure |
| `ktrdr/backtesting/checkpoint_restore.py` | **MINOR** | Adapt to new engine structure |
| `ktrdr/training/model_storage.py` | **MINOR** | Keep save-side round-trip fix, no changes to save logic |
| Tests in `tests/unit/backtesting/` | **UPDATE** | Adapt to new interfaces |

## Risks and Mitigations

### Risk: Breaking existing backtests
**Mitigation:** The core simulation logic (PositionManager, FeatureCache, PerformanceTracker) is unchanged. The refactor changes how they're wired together, not what they do. Unit tests for these components continue to pass. New integration test validates same results for a known strategy.

### Risk: DecisionFunction missing orchestrator-level logic
**Mitigation:** The only orchestrator logic that matters for backtesting is: confidence threshold, signal separation, and position awareness (don't buy when long, don't sell when flat). All three are preserved in `DecisionFunction._apply_filters()`. The risk management overrides (max position size, mode-specific logic) are not used in backtest mode.

### Risk: model_full.pt backward compatibility
**Mitigation:** `model_full.pt` continues to be saved by `ModelStorage.save_model()`. We only stop LOADING it during backtesting. If a future use case needs it (unlikely — state dict is strictly better), the files exist.

### Risk: Orchestrator rot
**Mitigation:** `DecisionOrchestrator` and `DecisionEngine` are preserved but no longer imported by backtesting. They remain available for future paper/live trading. If they're never used, they can be removed in a future cleanup.

## Testing Strategy

1. **Unit tests for new components** — `ModelBundle.load()`, `DecisionFunction.__call__()`, refactored `BacktestingEngine`
2. **Regression test** — Run backtest with known strategy (e.g., `mean_reversion_momentum_v1`), verify identical metrics to current output
3. **MPS portability test** — Load model trained on MPS in CPU-only container (the original bug)
4. **Fast validation test** — Direct `ModelBundle.load()` inside Docker container (~2 seconds, not 10-minute research cycles)
5. **Existing test suite** — All `tests/unit/backtesting/` tests must pass (adapted for new interfaces)
6. **Ultimate E2E — the original bug scenario:**
   ```bash
   uv run ktrdr research -m haiku -f "Design a multi-timeframe strategy using RSI and Bollinger Bands on 1h and 5m data for EURUSD"
   ```
   Full agent cycle: design → train (MPS) → backtest (CPU Docker) → assess. This is the exact scenario that triggered the original `mps` device error. If it completes, the refactor is proven.
