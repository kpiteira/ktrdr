# Training Service Architecture - Shared Pipeline, Separate Orchestration

**Date**: 2025-01-07
**Status**: Architecture Design
**Previous**: [02-requirements.md](./02-requirements.md)
**Next**: Implementation Plan (TBD)

---

## Executive Summary

This architecture eliminates code duplication in the KTRDR training system by extracting shared training logic into a reusable `TrainingPipeline` component, while keeping orchestration concerns (progress reporting, cancellation, async boundaries) separate and environment-specific.

**Core Principle**: Share the work, separate the coordination.

**Key Insight from Previous Failed Attempt**: We tried to unify orchestration (progress callbacks, cancellation tokens, async/sync boundaries) into a single flow. This failed because local and host service coordination are fundamentally different. The correct approach is to extract the **pure training logic** (80% identical) while keeping **orchestration** (20% different) separate.

**Key Design Decisions**:
1. **TrainingPipeline**: Pure, synchronous training logic - no callbacks, no cancellation checks
2. **LocalTrainingOrchestrator**: Coordinates pipeline using callback-based progress + in-memory cancellation token
3. **HostTrainingOrchestrator**: Coordinates pipeline using session-based progress + HTTP cancellation flag
4. **Zero duplication**: Both orchestrators use the exact same training logic
5. **Both flows work today**: Architecture preserves working behavior, only eliminates duplication

---

## Problem Statement

### Current State

**Both execution paths work correctly today**:
- Local (Docker container): Training executes, saves models, reports progress
- Host Service (Native macOS): Training executes, saves models, reports progress

**The problem is code duplication**:

| Component | Backend | Host Service | Duplication |
|-----------|---------|--------------|-------------|
| Data loading | `StrategyTrainer` | `TrainingService._run_real_training()` | 80% identical |
| Indicators | Uses `IndicatorEngine` | Uses `IndicatorEngine` | 80% identical |
| Fuzzy logic | Uses `FuzzyEngine` | Uses `FuzzyEngine` | 80% identical |
| Feature engineering | Uses `FuzzyNeuralProcessor` | Simplified version | 70% identical |
| Training loop | Uses `ModelTrainer` | Custom loop | 60% identical |
| Model saving | Uses `ModelStorage` | Uses `ModelStorage` | 100% identical |
| **Lines of code** | ~1,500 | ~1,000 | ~2,500 total |

**Total duplication**: ~80% of training logic exists in two places.

### Previous Failed Attempt

**What we tried**: Create a unified `TrainingExecutor` that works for both local and host execution with a single orchestration layer.

**Why it failed**:
1. **Progress mechanisms are fundamentally different**:
   - Local: Synchronous callback → immediate `GenericProgressManager` update
   - Host: Update session state → polled via HTTP every 2 seconds

2. **Cancellation mechanisms are fundamentally different**:
   - Local: In-memory `CancellationToken` checked synchronously
   - Host: `session.stop_requested` flag set via HTTP, checked asynchronously

3. **Async boundaries are different**:
   - Local: `asyncio.to_thread()` wraps entire training execution
   - Host: Already running in async context, needs different boundary

**Attempting to unify these created complexity without benefit.**

### The Right Approach

**Extract what's identical (the work), keep what's different (the coordination):**

```
❌ Previous Approach:
   One TrainingExecutor with unified orchestration
   → Failed because orchestration is fundamentally different

✅ New Approach:
   Shared TrainingPipeline (pure work functions)
   + Separate orchestrators (environment-specific coordination)
   → Succeeds because it accepts differences while eliminating duplication
```

---

## Architecture Overview

### Conceptual Model

```
┌──────────────────────────────────────────────────────────┐
│                     User Request                         │
│                    (API or CLI)                          │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ↓
┌──────────────────────────────────────────────────────────┐
│               TrainingService (decides mode)             │
└────────────┬────────────────────────┬────────────────────┘
             │                        │
    ┌────────┴────────┐      ┌────────┴────────┐
    │ Local Mode      │      │ Host Mode       │
    └────────┬────────┘      └────────┬────────┘
             │                        │
             ↓                        ↓
┌────────────────────────┐  ┌────────────────────────┐
│ LocalTrainingOrch.     │  │ HostTrainingOrch.      │
│ - Callback progress    │  │ - Session progress     │
│ - Token cancellation   │  │ - Flag cancellation    │
│ - asyncio.to_thread()  │  │ - Direct execution     │
└────────────┬───────────┘  └────────────┬───────────┘
             │                           │
             │    Both use same logic    │
             └───────────┬───────────────┘
                         │
                         ↓
              ┌─────────────────────┐
              │ TrainingPipeline    │
              │ (Pure Work Logic)   │
              │                     │
              │ - load_price_data() │
              │ - calc_indicators() │
              │ - gen_fuzzy()       │
              │ - engineer_features │
              │ - generate_labels() │
              │ - create_model()    │
              │ - train_model()     │
              │ - evaluate_model()  │
              │ - save_model()      │
              └─────────────────────┘
```

### Key Components

1. **TrainingPipeline** (New - Shared)
   - Pure, synchronous work functions
   - No callbacks, no cancellation checks, no async
   - Used by both orchestrators

2. **LocalTrainingOrchestrator** (Refactored from `LocalTrainingRunner`)
   - Uses `TrainingPipeline` for work
   - Manages local progress callbacks
   - Checks local cancellation token
   - Wraps execution in `asyncio.to_thread()`

3. **HostTrainingOrchestrator** (Refactored from `training_service._run_real_training`)
   - Uses `TrainingPipeline` for work
   - Updates session state for progress
   - Checks `session.stop_requested` for cancellation
   - Each step wrapped in `asyncio.to_thread()`

---

## Component Design

### TrainingPipeline (New Component)

**Location**: `ktrdr/training/pipeline.py`

**Responsibility**: Execute pure training transformations - no coordination concerns.

**Design Principles**:
1. **Pure functions**: Input → transformation → output
2. **No callbacks**: Returns data, caller decides what to do with it
3. **No cancellation checks**: Caller handles coordination
4. **No async**: Synchronous work, caller manages async boundaries
5. **No progress reporting**: Caller reports progress

**Interface**:

```python
class TrainingPipeline:
    """Pure training pipeline - all the work, no coordination."""

    def __init__(self):
        self.data_manager = DataManager()
        self.indicator_engine = IndicatorEngine()
        self.model_storage = ModelStorage()
        # ... other engines

    # ─────────────────────────────────────────────────────
    # Pure work functions - no side effects, no coordination
    # ─────────────────────────────────────────────────────

    def load_price_data(
        self,
        symbols: list[str],
        timeframes: list[str],
        start_date: str,
        end_date: str,
        data_mode: str
    ) -> dict[str, dict[str, pd.DataFrame]]:
        """Load price data for all symbols and timeframes.

        Returns:
            {symbol: {timeframe: DataFrame}}
        """
        all_data = {}
        for symbol in symbols:
            symbol_data = {}
            for timeframe in timeframes:
                data = self.data_manager.load_data(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date,
                    mode=data_mode,
                    validate=True
                )
                symbol_data[timeframe] = data
            all_data[symbol] = symbol_data
        return all_data

    def calculate_indicators(
        self,
        price_data: dict[str, dict[str, pd.DataFrame]],
        indicator_config: dict
    ) -> dict[str, dict[str, pd.DataFrame]]:
        """Calculate technical indicators for all symbols."""
        all_indicators = {}
        for symbol, timeframe_data in price_data.items():
            symbol_indicators = {}
            for timeframe, data in timeframe_data.items():
                indicators = self.indicator_engine.apply(data)
                symbol_indicators[timeframe] = indicators
            all_indicators[symbol] = symbol_indicators
        return all_indicators

    def generate_fuzzy_memberships(
        self,
        indicator_data: dict[str, dict[str, pd.DataFrame]],
        fuzzy_config: dict
    ) -> dict[str, dict[str, pd.DataFrame]]:
        """Generate fuzzy memberships for all symbols."""
        all_fuzzy = {}
        for symbol, timeframe_data in indicator_data.items():
            symbol_fuzzy = {}
            for timeframe, data in timeframe_data.items():
                fuzzy = self.fuzzy_engine.generate_memberships(data)
                symbol_fuzzy[timeframe] = fuzzy
            all_fuzzy[symbol] = symbol_fuzzy
        return all_fuzzy

    def engineer_features(
        self,
        fuzzy_data: dict[str, dict[str, pd.DataFrame]],
        indicator_data: dict[str, dict[str, pd.DataFrame]],
        price_data: dict[str, dict[str, pd.DataFrame]],
        feature_config: dict
    ) -> tuple[dict[str, np.ndarray], dict[str, list[str]]]:
        """Engineer features for all symbols.

        Returns:
            (features_dict, feature_names_dict)
        """
        all_features = {}
        all_feature_names = {}
        for symbol in fuzzy_data:
            features, feature_names, _ = self.fuzzy_neural_processor.engineer_features(
                fuzzy_data[symbol],
                indicator_data[symbol],
                price_data[symbol],
                feature_config
            )
            all_features[symbol] = features
            all_feature_names[symbol] = feature_names
        return all_features, all_feature_names

    def generate_labels(
        self,
        price_data: dict[str, dict[str, pd.DataFrame]],
        label_config: dict
    ) -> dict[str, np.ndarray]:
        """Generate training labels for all symbols."""
        all_labels = {}
        for symbol, timeframe_data in price_data.items():
            # Use primary timeframe for labels
            primary_tf = list(timeframe_data.keys())[0]
            labels = self.zigzag_labeler.generate_labels(
                timeframe_data[primary_tf],
                label_config
            )
            all_labels[symbol] = labels
        return all_labels

    def combine_multi_symbol_data(
        self,
        features: dict[str, np.ndarray],
        labels: dict[str, np.ndarray],
        symbols: list[str]
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Combine data from multiple symbols with balanced sampling.

        Returns:
            (combined_features, combined_labels, symbol_indices)
        """
        # Implementation from StrategyTrainer
        ...

    def split_data(
        self,
        features: np.ndarray,
        labels: np.ndarray,
        symbol_indices: np.ndarray,
        validation_split: float,
        test_split: float
    ) -> tuple[tuple, tuple, tuple]:
        """Split data into train/val/test sets.

        Returns:
            (train_data, val_data, test_data)
            where each is (features, labels, symbol_indices)
        """
        # Implementation from StrategyTrainer
        ...

    def create_model(
        self,
        input_size: int,
        model_config: dict
    ) -> MLPTradingModel:
        """Create neural network model."""
        return MLPTradingModel(
            input_size=input_size,
            hidden_layers=model_config.get("hidden_layers", [256, 128, 64]),
            output_size=3,  # Buy/Hold/Sell
            dropout=model_config.get("dropout", 0.2)
        )

    def train_model(
        self,
        model: MLPTradingModel,
        train_data: tuple,
        val_data: tuple,
        training_config: dict,
        device: torch.device,
        progress_callback=None,
        cancellation_token=None
    ) -> dict[str, Any]:
        """Train the model.

        Note: This is the ONLY function that accepts callbacks/tokens,
        because ModelTrainer's interface requires them.
        """
        trainer = ModelTrainer(
            model=model,
            device=device,
            training_config=training_config,
            progress_callback=progress_callback,
            cancellation_token=cancellation_token
        )
        return trainer.train(
            train_features=train_data[0],
            train_labels=train_data[1],
            val_features=val_data[0],
            val_labels=val_data[1]
        )

    def evaluate_model(
        self,
        model: MLPTradingModel,
        test_data: tuple,
        device: torch.device
    ) -> dict[str, float]:
        """Evaluate model on test set."""
        # Implementation from StrategyTrainer
        ...

    def save_model(
        self,
        model: MLPTradingModel,
        strategy_name: str,
        symbols: list[str],
        timeframes: list[str],
        config: dict,
        metrics: dict,
        feature_names: list[str],
        scaler: Any
    ) -> str:
        """Save model to disk.

        Returns:
            Path to saved model
        """
        return self.model_storage.save_model(
            model=model,
            strategy_name=strategy_name,
            symbol=symbols[0],  # Primary symbol
            timeframe=timeframes[0],  # Primary timeframe
            config=config,
            training_metrics=metrics,
            feature_names=feature_names,
            scaler=scaler
        )
```

**Key Characteristics**:
- Each function is **pure**: deterministic, no hidden state changes
- Returns data instead of mutating state
- Only `train_model()` accepts callbacks/tokens (because `ModelTrainer` requires them)
- All other functions: pure transformations
- Easily testable in isolation

---

### LocalTrainingOrchestrator (Refactored Component)

**Location**: `ktrdr/api/services/training/local_runner.py`

**Responsibility**: Coordinate training with local (in-process) progress/cancellation.

**Design**:

```python
class LocalTrainingOrchestrator:
    """Orchestrate training with local coordination mechanisms."""

    def __init__(
        self,
        context: TrainingOperationContext,
        progress_bridge: TrainingProgressBridge,
        cancellation_token: CancellationToken | None,
        pipeline: TrainingPipeline | None = None,
    ):
        self._context = context
        self._bridge = progress_bridge
        self._token = cancellation_token
        self._pipeline = pipeline or TrainingPipeline()

    async def run(self) -> dict[str, Any]:
        """Execute training with local coordination."""
        # Run entire training in thread pool
        return await asyncio.to_thread(self._execute_training)

    def _execute_training(self) -> dict[str, Any]:
        """Synchronous orchestration of training steps."""

        # Step 1: Load data
        self._check_cancellation()
        self._bridge.on_phase("data_loading", message="Loading market data")

        price_data = self._pipeline.load_price_data(
            symbols=self._context.symbols,
            timeframes=self._context.timeframes,
            start_date=self._context.start_date,
            end_date=self._context.end_date,
            data_mode=self._context.training_config.get("data_mode", "local")
        )

        # Step 2: Calculate indicators
        self._check_cancellation()
        self._bridge.on_phase("indicators", message="Calculating indicators")

        indicator_data = self._pipeline.calculate_indicators(
            price_data=price_data,
            indicator_config=self._context.strategy_config["indicators"]
        )

        # Step 3: Generate fuzzy memberships
        self._check_cancellation()
        self._bridge.on_phase("fuzzy", message="Generating fuzzy memberships")

        fuzzy_data = self._pipeline.generate_fuzzy_memberships(
            indicator_data=indicator_data,
            fuzzy_config=self._context.strategy_config["fuzzy_sets"]
        )

        # Step 4: Engineer features
        self._check_cancellation()
        self._bridge.on_phase("features", message="Engineering features")

        features, feature_names = self._pipeline.engineer_features(
            fuzzy_data=fuzzy_data,
            indicator_data=indicator_data,
            price_data=price_data,
            feature_config=self._context.strategy_config["model"]["features"]
        )

        # Step 5: Generate labels
        self._check_cancellation()
        self._bridge.on_phase("labels", message="Generating labels")

        labels = self._pipeline.generate_labels(
            price_data=price_data,
            label_config=self._context.strategy_config["training"]["labels"]
        )

        # Step 6: Combine data
        self._check_cancellation()
        combined_features, combined_labels, symbol_indices = (
            self._pipeline.combine_multi_symbol_data(
                features=features,
                labels=labels,
                symbols=self._context.symbols
            )
        )

        # Step 7: Split data
        self._check_cancellation()
        train_data, val_data, test_data = self._pipeline.split_data(
            features=combined_features,
            labels=combined_labels,
            symbol_indices=symbol_indices,
            validation_split=self._context.training_config.get("validation_split", 0.2),
            test_split=self._context.training_config.get("test_split", 0.1)
        )

        # Step 8: Create model
        self._check_cancellation()
        self._bridge.on_phase("model_creation", message="Creating model")

        model = self._pipeline.create_model(
            input_size=combined_features.shape[1],
            model_config=self._context.strategy_config["model"]
        )

        # Step 9: Train model
        self._check_cancellation()
        self._bridge.on_phase("training", message="Training model")

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        training_results = self._pipeline.train_model(
            model=model,
            train_data=train_data,
            val_data=val_data,
            training_config=self._context.training_config,
            device=device,
            progress_callback=self._create_training_callback(),
            cancellation_token=self._token
        )

        # Step 10: Evaluate model
        if test_data:
            self._check_cancellation()
            self._bridge.on_phase("evaluation", message="Evaluating model")

            test_metrics = self._pipeline.evaluate_model(
                model=model,
                test_data=test_data,
                device=device
            )
        else:
            test_metrics = {}

        # Step 11: Save model
        self._check_cancellation()
        self._bridge.on_phase("saving", message="Saving model")

        model_path = self._pipeline.save_model(
            model=model,
            strategy_name=self._context.strategy_name,
            symbols=self._context.symbols,
            timeframes=self._context.timeframes,
            config=self._context.strategy_config,
            metrics=training_results,
            feature_names=feature_names[self._context.symbols[0]],
            scaler=None  # TODO: Add scaler support
        )

        # Step 12: Complete
        self._bridge.on_complete()

        return {
            "success": True,
            "model_path": model_path,
            "training_metrics": training_results,
            "test_metrics": test_metrics,
        }

    def _check_cancellation(self):
        """Check local cancellation token."""
        if self._token and self._token.is_cancelled():
            raise CancellationError("Training cancelled")

    def _create_training_callback(self):
        """Create callback for ModelTrainer that bridges to progress system."""
        def callback(epoch: int, total_epochs: int, metrics: dict[str, Any]):
            # Check cancellation on every callback
            self._check_cancellation()

            # Forward to progress bridge
            progress_type = metrics.get("progress_type")
            if progress_type == "batch":
                self._bridge.on_batch(
                    epoch=epoch,
                    batch=metrics.get("batch", 0),
                    total_batches=metrics.get("total_batches_per_epoch"),
                    metrics=metrics
                )
            elif progress_type == "epoch":
                self._bridge.on_epoch(
                    epoch=epoch,
                    total_epochs=total_epochs,
                    metrics=metrics
                )
        return callback
```

**Key Characteristics**:
- **Orchestrates** the pipeline steps
- **Coordinates** progress via `TrainingProgressBridge`
- **Checks** cancellation via `CancellationToken`
- **Uses** `TrainingPipeline` for all actual work
- **No duplication** of training logic

---

### HostTrainingOrchestrator (Refactored Component)

**Location**: `training-host-service/orchestrator.py` (new file)

**Responsibility**: Coordinate training with host service (session-based) progress/cancellation.

**Design**:

```python
class HostTrainingOrchestrator:
    """Orchestrate training with host service coordination mechanisms."""

    def __init__(
        self,
        session: TrainingSession,
        pipeline: TrainingPipeline | None = None,
    ):
        self._session = session
        self._pipeline = pipeline or TrainingPipeline()

    async def run(self) -> dict[str, Any]:
        """Execute training with host service coordination."""

        # Step 1: Load data
        if self._check_stop_requested():
            return self._cancelled_result()

        self._update_progress(phase="data_loading", message="Loading market data")

        price_data = await asyncio.to_thread(
            self._pipeline.load_price_data,
            symbols=self._get_symbols(),
            timeframes=self._get_timeframes(),
            start_date=self._get_start_date(),
            end_date=self._get_end_date(),
            data_mode=self._get_data_mode()
        )

        # Step 2: Calculate indicators
        if self._check_stop_requested():
            return self._cancelled_result()

        self._update_progress(phase="indicators", message="Calculating indicators")

        indicator_data = await asyncio.to_thread(
            self._pipeline.calculate_indicators,
            price_data=price_data,
            indicator_config=self._get_indicator_config()
        )

        # Step 3: Generate fuzzy memberships
        if self._check_stop_requested():
            return self._cancelled_result()

        self._update_progress(phase="fuzzy", message="Generating fuzzy memberships")

        fuzzy_data = await asyncio.to_thread(
            self._pipeline.generate_fuzzy_memberships,
            indicator_data=indicator_data,
            fuzzy_config=self._get_fuzzy_config()
        )

        # Step 4: Engineer features
        if self._check_stop_requested():
            return self._cancelled_result()

        self._update_progress(phase="features", message="Engineering features")

        features, feature_names = await asyncio.to_thread(
            self._pipeline.engineer_features,
            fuzzy_data=fuzzy_data,
            indicator_data=indicator_data,
            price_data=price_data,
            feature_config=self._get_feature_config()
        )

        # Step 5: Generate labels
        if self._check_stop_requested():
            return self._cancelled_result()

        self._update_progress(phase="labels", message="Generating labels")

        labels = await asyncio.to_thread(
            self._pipeline.generate_labels,
            price_data=price_data,
            label_config=self._get_label_config()
        )

        # Step 6: Combine data
        if self._check_stop_requested():
            return self._cancelled_result()

        combined_features, combined_labels, symbol_indices = await asyncio.to_thread(
            self._pipeline.combine_multi_symbol_data,
            features=features,
            labels=labels,
            symbols=self._get_symbols()
        )

        # Step 7: Split data
        if self._check_stop_requested():
            return self._cancelled_result()

        train_data, val_data, test_data = await asyncio.to_thread(
            self._pipeline.split_data,
            features=combined_features,
            labels=combined_labels,
            symbol_indices=symbol_indices,
            validation_split=self._get_validation_split(),
            test_split=self._get_test_split()
        )

        # Step 8: Create model
        if self._check_stop_requested():
            return self._cancelled_result()

        self._update_progress(phase="model_creation", message="Creating model")

        model = self._pipeline.create_model(
            input_size=combined_features.shape[1],
            model_config=self._get_model_config()
        )

        # Step 9: Train model
        if self._check_stop_requested():
            return self._cancelled_result()

        self._update_progress(phase="training", message="Training model")

        # Detect device (MPS on Mac, CUDA on Linux, CPU fallback)
        device = self._detect_device()

        training_results = await asyncio.to_thread(
            self._pipeline.train_model,
            model=model,
            train_data=train_data,
            val_data=val_data,
            training_config=self._get_training_config(),
            device=device,
            progress_callback=self._create_training_callback(),
            cancellation_token=self._create_cancellation_token()
        )

        # Step 10: Evaluate model
        if test_data:
            if self._check_stop_requested():
                return self._cancelled_result()

            self._update_progress(phase="evaluation", message="Evaluating model")

            test_metrics = await asyncio.to_thread(
                self._pipeline.evaluate_model,
                model=model,
                test_data=test_data,
                device=device
            )
        else:
            test_metrics = {}

        # Step 11: Save model
        if self._check_stop_requested():
            return self._cancelled_result()

        self._update_progress(phase="saving", message="Saving model")

        model_path = await asyncio.to_thread(
            self._pipeline.save_model,
            model=model,
            strategy_name=self._get_strategy_name(),
            symbols=self._get_symbols(),
            timeframes=self._get_timeframes(),
            config=self._get_strategy_config(),
            metrics=training_results,
            feature_names=feature_names[self._get_symbols()[0]],
            scaler=None
        )

        # Step 12: Complete
        self._session.status = "completed"

        return {
            "success": True,
            "model_path": model_path,
            "training_metrics": training_results,
            "test_metrics": test_metrics,
        }

    def _check_stop_requested(self) -> bool:
        """Check session stop flag."""
        return self._session.stop_requested

    def _cancelled_result(self) -> dict:
        """Return cancelled result."""
        self._session.status = "cancelled"
        return {"success": False, "cancelled": True}

    def _update_progress(self, phase: str, message: str):
        """Update session progress."""
        self._session.update_progress(
            epoch=0,
            batch=0,
            metrics={"phase": phase, "message": message}
        )

    def _create_training_callback(self):
        """Create callback for ModelTrainer that updates session."""
        def callback(epoch: int, total_epochs: int, metrics: dict[str, Any]):
            # Check stop request on every callback
            if self._check_stop_requested():
                raise CancellationError("Training cancelled")

            # Update session with training progress
            self._session.update_progress(
                epoch=epoch,
                batch=metrics.get("batch", 0),
                metrics=metrics
            )
        return callback

    def _create_cancellation_token(self):
        """Create cancellation token that checks session flag."""
        class SessionCancellationToken:
            def __init__(self, session):
                self._session = session

            def is_cancelled(self) -> bool:
                return self._session.stop_requested

        return SessionCancellationToken(self._session)

    def _detect_device(self) -> torch.device:
        """Detect best available device."""
        if torch.backends.mps.is_available():
            return torch.device("mps")
        elif torch.cuda.is_available():
            return torch.device("cuda")
        else:
            return torch.device("cpu")

    # Helper methods to extract config from session
    def _get_symbols(self) -> list[str]:
        return self._session.config.get("data_config", {}).get("symbols", ["AAPL"])

    # ... other config getters
```

**Key Characteristics**:
- **Orchestrates** the pipeline steps (same as local)
- **Coordinates** progress via session state updates
- **Checks** cancellation via `session.stop_requested`
- **Uses** same `TrainingPipeline` as local
- **Different coordination**, same work

---

## Progress Communication

### The Complexity

Progress has **three levels of granularity**:

1. **Pipeline steps** (12 steps: load data, calc indicators, train, evaluate, save)
2. **Training epochs** (within step 7 "training": epoch 1/100, epoch 2/100, etc.)
3. **Training batches** (within each epoch: batch 1/500, batch 2/500, etc.)

### Local Flow (Callback-Based)

```
ModelTrainer.train()
  └─> progress_callback(epoch=5, total_epochs=100, metrics={...})
      └─> LocalTrainingOrchestrator._create_training_callback()
          └─> TrainingProgressBridge.on_epoch()
              └─> GenericProgressManager.update()
                  └─> ProgressRenderer displays
```

**Characteristics**:
- **Synchronous**: Callback called directly from training loop
- **Real-time**: Progress updates appear immediately
- **Granularity**: Batch-level updates (throttled to ~300ms)

### Host Flow (Polling-Based)

```
ModelTrainer.train()
  └─> progress_callback(epoch=5, total_epochs=100, metrics={...})
      └─> HostTrainingOrchestrator._create_training_callback()
          └─> session.update_progress(epoch, batch, metrics)
              └─> Updates TrainingSession state

[Meanwhile, backend polls every 2s]
GET /training/status/{session_id}
  └─> Returns session.get_progress_dict()
      └─> HostSessionManager.poll_session()
          └─> TrainingProgressBridge.on_remote_snapshot()
              └─> GenericProgressManager.update()
                  └─> ProgressRenderer displays
```

**Characteristics**:
- **Asynchronous**: Progress polled, not pushed
- **Eventual**: Up to 2s delay
- **Granularity**: Same as local (batch-level), but delayed

### Key Insight

**We're not trying to make these the same.** They're fundamentally different and that's okay:
- Local: Direct callback → immediate update
- Host: Session state → polled update

Both orchestrators call `TrainingPipeline` the same way, but route progress differently.

---

## Cancellation Propagation

### The Complexity

Cancellation needs to **stop training quickly** (< 100ms) across process boundaries.

### Local Flow (Token-Based)

```
User cancels
  ↓
operations_service.cancel_operation()
  ↓
cancellation_token.cancel()  # In-memory flag
  ↓
LocalTrainingOrchestrator._check_cancellation()
  ↓
Raises CancellationError
  ↓
Training stops immediately
```

**Characteristics**:
- **Synchronous**: In-memory flag check
- **Fast**: < 10ms
- **Simple**: Direct token check

### Host Flow (Flag-Based)

```
User cancels
  ↓
POST /training/stop
  ↓
session.stop_requested = True  # Flag set
  ↓
HostTrainingOrchestrator._check_stop_requested()
  ↓
Returns cancelled result OR
ModelTrainer checks SessionCancellationToken
  ↓
Raises CancellationError
  ↓
Training stops
```

**Characteristics**:
- **Asynchronous**: HTTP request sets flag
- **Fast enough**: < 50ms (checked every batch)
- **Adapter**: `SessionCancellationToken` bridges to session flag

### Key Insight

**We're not trying to use the same token.** Different mechanisms, same outcome:
- Local: CancellationToken (in-memory)
- Host: SessionCancellationToken (checks session flag)

Both implement `is_cancelled() -> bool`, both work.

---

## Data Flow Diagrams

### Local Execution Flow

```
API Request
  ↓
TrainingService.start_training()
  ↓
Create LocalTrainingOrchestrator
  ↓
asyncio.create_task(orchestrator.run())
  ↓
[Background Task]
asyncio.to_thread(orchestrator._execute_training)
  ↓
[Worker Thread - Synchronous]
  ├─> pipeline.load_price_data()
  ├─> Check cancellation token
  ├─> bridge.on_phase("data_loading")
  ├─> pipeline.calculate_indicators()
  ├─> Check cancellation token
  ├─> bridge.on_phase("indicators")
  ├─> ... (continue for all steps)
  ├─> pipeline.train_model(
  │     progress_callback=lambda e,t,m: bridge.on_epoch(e,t,m)
  │   )
  ├─> pipeline.save_model()
  └─> Return results
  ↓
Update operation status
  ↓
User polls /operations/{id}
```

### Host Service Execution Flow

```
API Request
  ↓
TrainingService.start_training()
  ↓
POST /training/start to host service
  ↓
Host creates TrainingSession
  ↓
Host creates HostTrainingOrchestrator
  ↓
[Host Service - Async]
  ├─> Check session.stop_requested
  ├─> session.update_progress("data_loading")
  ├─> asyncio.to_thread(pipeline.load_price_data)
  ├─> Check session.stop_requested
  ├─> session.update_progress("indicators")
  ├─> asyncio.to_thread(pipeline.calculate_indicators)
  ├─> ... (continue for all steps)
  ├─> asyncio.to_thread(pipeline.train_model,
  │     progress_callback=lambda e,t,m: session.update_progress(e,0,m)
  │   )
  ├─> asyncio.to_thread(pipeline.save_model)
  └─> Return results

[Meanwhile, Backend polls]
GET /training/status/{session_id} (every 2s)
  ↓
Returns session progress
  ↓
Update operation status
  ↓
User polls /operations/{id}
```

---

## Design Decisions

### Decision 1: Extract Pure Pipeline, Not Unified Orchestrator

**Question**: How do we eliminate duplication while supporting different coordination?

**Options**:
- A) Create unified TrainingExecutor with single orchestration layer
- B) Extract pure TrainingPipeline, keep orchestration separate
- C) Keep duplication, improve gradually

**Decision**: Option B

**Rationale**:
- **Option A failed previously** - tried to unify fundamentally different coordination
- **Option B accepts reality** - progress/cancellation ARE different, don't force unification
- **Option C perpetuates problem** - 2,500 lines of duplication will only grow

**Trade-offs**:
- ✅ Eliminates 80% duplication (all training logic)
- ✅ Preserves working behavior (both flows already work)
- ✅ Clear separation of concerns (work vs coordination)
- ❌ Two orchestrators instead of one (but they're simple)
- ❌ Some code similarity in orchestrators (acceptable - they coordinate differently)

### Decision 2: TrainingPipeline is Pure Functions

**Question**: Should TrainingPipeline be a class with methods or standalone functions?

**Decision**: Class with pure methods

**Rationale**:
- **Dependency injection**: Easy to inject engines (DataManager, IndicatorEngine)
- **State management**: Engines can be initialized once, reused
- **Testability**: Easy to mock engines in tests
- **Consistency**: Matches existing KTRDR patterns

**Trade-offs**:
- ✅ Clear dependency management
- ✅ Easy to test
- ✅ Familiar pattern
- ❌ Slightly more boilerplate than functions (acceptable)

### Decision 3: Keep Both Orchestrators Simple

**Question**: Should we create a base orchestrator class?

**Decision**: No - keep them separate and simple

**Rationale**:
- **They're fundamentally different** - extracting common behavior adds complexity
- **Both are simple** - ~100 lines each, easy to understand
- **Separation aids understanding** - clear what's different between modes

**Trade-offs**:
- ✅ No abstraction complexity
- ✅ Easy to understand each flow
- ✅ Easy to modify independently
- ❌ Some structural similarity (acceptable - clarity > DRY)

### Decision 4: Preserve ModelTrainer Interface

**Question**: Should we wrap ModelTrainer to change its callback interface?

**Decision**: No - pass callbacks through unchanged

**Rationale**:
- **Interface already works** - ModelTrainer callback signature is battle-tested
- **Wrapping adds complexity** - another layer to maintain
- **Both orchestrators can adapt** - they can create appropriate callbacks

**Trade-offs**:
- ✅ No interface changes
- ✅ No wrapper complexity
- ✅ Battle-tested code preserved
- ❌ Orchestrators must create adapter callbacks (acceptable - simple)

---

## Migration Strategy

### Phase 1: Extract TrainingPipeline (1 week)

**Goal**: Create `TrainingPipeline` with all pure training logic.

**Steps**:
1. Create `ktrdr/training/pipeline.py`
2. Extract methods from `StrategyTrainer`:
   - `load_price_data()`
   - `calculate_indicators()`
   - `generate_fuzzy_memberships()`
   - `engineer_features()`
   - `generate_labels()`
   - `combine_multi_symbol_data()`
   - `split_data()`
   - `create_model()`
   - `train_model()`
   - `evaluate_model()`
   - `save_model()`
3. Remove callbacks/cancellation from all methods except `train_model()`
4. Add comprehensive unit tests for each method

**Success Criteria**:
- All methods are pure functions (except `train_model()`)
- 100% test coverage on `TrainingPipeline`
- No imports of orchestration concerns (OperationsService, TrainingSession)

### Phase 2: Refactor Local Orchestrator (3 days)

**Goal**: Make `LocalTrainingRunner` use `TrainingPipeline`.

**Steps**:
1. Inject `TrainingPipeline` into `LocalTrainingRunner`
2. Replace inline logic with pipeline method calls
3. Keep all coordination logic (callbacks, cancellation)
4. Add integration tests

**Success Criteria**:
- `LocalTrainingRunner` uses `TrainingPipeline` for all work
- All existing tests pass
- Training results identical to before

### Phase 3: Refactor Host Orchestrator (3 days)

**Goal**: Create `HostTrainingOrchestrator` using `TrainingPipeline`.

**Steps**:
1. Create `training-host-service/orchestrator.py`
2. Extract orchestration from `training_service._run_real_training()`
3. Use `TrainingPipeline` for all work
4. Keep all session management
5. Add integration tests

**Success Criteria**:
- `HostTrainingOrchestrator` uses `TrainingPipeline` for all work
- All existing tests pass
- Training results identical to before

### Phase 4: Remove Duplicate Code (1 day)

**Goal**: Delete old duplicate training logic.

**Steps**:
1. Mark `StrategyTrainer.train_multi_symbol_strategy()` as deprecated
2. Remove duplicate logic from `training_service._run_real_training()`
3. Update all callers
4. Run full test suite

**Success Criteria**:
- Zero duplication of training logic
- All tests pass
- Both execution paths work

**Total Time**: 2-3 weeks, low risk

---

## Testing Strategy

### Unit Tests (TrainingPipeline)

Test each method independently:

```python
def test_load_price_data():
    pipeline = TrainingPipeline()
    data = pipeline.load_price_data(
        symbols=["EURUSD"],
        timeframes=["1h"],
        start_date="2024-01-01",
        end_date="2024-01-31",
        data_mode="local"
    )
    assert "EURUSD" in data
    assert "1h" in data["EURUSD"]
    assert len(data["EURUSD"]["1h"]) > 0

def test_calculate_indicators():
    pipeline = TrainingPipeline()
    price_data = {...}  # Mock data
    indicators = pipeline.calculate_indicators(
        price_data=price_data,
        indicator_config={"rsi": {"period": 14}}
    )
    assert "EURUSD" in indicators
    assert "rsi" in indicators["EURUSD"]["1h"].columns
```

### Integration Tests (Orchestrators)

Test orchestrators with real pipeline:

```python
@pytest.mark.asyncio
async def test_local_orchestrator_full_flow():
    pipeline = TrainingPipeline()
    context = TrainingOperationContext(...)
    bridge = TrainingProgressBridge(...)
    token = CancellationToken()

    orchestrator = LocalTrainingOrchestrator(
        context=context,
        progress_bridge=bridge,
        cancellation_token=token,
        pipeline=pipeline
    )

    result = await orchestrator.run()

    assert result["success"] is True
    assert "model_path" in result
    assert os.path.exists(result["model_path"])

@pytest.mark.asyncio
async def test_local_orchestrator_cancellation():
    pipeline = TrainingPipeline()
    token = CancellationToken()

    orchestrator = LocalTrainingOrchestrator(..., cancellation_token=token)

    # Cancel immediately
    token.cancel()

    with pytest.raises(CancellationError):
        await orchestrator.run()
```

### Equivalence Tests

Verify both paths produce identical results:

```python
@pytest.mark.asyncio
async def test_local_and_host_produce_same_results():
    # Train with local orchestrator
    local_result = await train_with_local(...)

    # Train with host orchestrator
    host_result = await train_with_host(...)

    # Compare metrics
    assert_metrics_equivalent(
        local_result["training_metrics"],
        host_result["training_metrics"],
        tolerance=0.01
    )
```

---

## Risks and Mitigations

### Risk 1: Extraction Introduces Bugs

**Risk**: Moving code from StrategyTrainer to TrainingPipeline changes behavior.

**Likelihood**: Medium

**Impact**: High (broken training)

**Mitigation**:
- Extract methods one at a time
- Comprehensive unit tests before migration
- Equivalence tests comparing old vs new
- Gradual rollout (local first, then host)

### Risk 2: Performance Regression

**Risk**: Additional function calls slow down training.

**Likelihood**: Low

**Impact**: Low (training is hours, function overhead is microseconds)

**Mitigation**:
- Benchmark before/after
- Profile hot paths
- Accept < 1% overhead

### Risk 3: Progress/Cancellation Edge Cases

**Risk**: Subtle differences in coordination cause issues.

**Likelihood**: Medium

**Impact**: Medium (confusing UX)

**Mitigation**:
- Extensive testing of progress updates
- Test cancellation at every step
- Manual testing of UI/CLI

---

## Appendix: Code Metrics

### Before Migration

| Component | Lines | Location |
|-----------|-------|----------|
| StrategyTrainer | 1,500 | ktrdr/training/train_strategy.py |
| Host Training | 1,000 | training-host-service/services/training_service.py |
| **Total** | **2,500** | |
| **Duplication** | **~2,000** | ~80% |

### After Migration

| Component | Lines | Location |
|-----------|-------|----------|
| TrainingPipeline | 800 | ktrdr/training/pipeline.py |
| LocalOrchestrator | 150 | ktrdr/api/services/training/local_runner.py |
| HostOrchestrator | 150 | training-host-service/orchestrator.py |
| **Total** | **1,100** | |
| **Duplication** | **0** | 0% |

**Reduction**: 56% less code, zero duplication

---

**Status**: Architecture Design Approved
**Next**: Implementation Plan (TBD)
