# Training Pre-Processing Progress Reporting: Implementation Plan

**Date**: 2025-01-16
**Status**: Implementation Phase
**Related**: [Problem Statement](./01-problem-statement.md), [Design](./02-design.md), [Architecture](./03-architecture.md)

---

## Executive Summary

This plan breaks implementation into **5 vertical slices** where each slice delivers working, testable functionality end-to-end. No horizontal layering - each phase can be tested via CLI/MCP immediately after implementation.

**Key Principle**: Each phase should work end-to-end. User can run training and see incremental progress improvements after each phase.

**Estimated Total Duration**: 3-4 days

---

## Implementation Approach

### Vertical Slicing Strategy

Each phase:
1. Adds one new progress type/granularity level
2. Updates ALL layers (bridge → orchestrators → pipeline → engines)
3. Is immediately testable end-to-end via CLI
4. Can be deployed independently

**NOT doing**: Implement all bridge methods first, then all orchestrator routing, then all pipeline callbacks (that's horizontal and untestable).

**DOING**: Implement one complete flow (bridge + orchestrator + pipeline + engine) per phase, test it, deploy it.

---

## Phase 1: Basic Symbol-Level Progress

**Goal**: User sees "Processing AAPL (2/5)" during training preprocessing.

**Duration**: 1 day

### What Gets Built

**End-to-end flow for symbol-level progress**:
1. TrainingProgressBridge gets `on_symbol_processing()` method
2. Both orchestrators route `"preprocessing"` type to bridge
3. TrainingPipeline reports progress at symbol boundaries
4. User sees progress in CLI

### Implementation Tasks

#### 1.1: Add `on_symbol_processing()` to TrainingProgressBridge

**File**: `ktrdr/api/services/training/progress_bridge.py`

**Add method**:
```python
def on_symbol_processing(
    self,
    symbol: str,
    symbol_index: int,
    total_symbols: int,
    step: str,
    context: dict[str, Any] | None = None
) -> None:
    """Report per-symbol preprocessing steps."""
    self._check_cancelled()

    message = f"Processing {symbol} ({symbol_index}/{total_symbols}) - {step.replace('_', ' ').title()}"

    # Simple percentage: pre-training is 0-5%
    symbols_progress = (symbol_index - 1) / total_symbols
    percentage = symbols_progress * 5.0

    payload_context = {
        "phase": "preprocessing",
        "symbol": symbol,
        "symbol_index": symbol_index,
        "total_symbols": total_symbols,
        "preprocessing_step": step,
    }
    if context:
        payload_context.update(context)

    self._emit(
        current_step=0,
        percentage=percentage,
        message=message,
        items_processed=symbol_index,
        phase="preprocessing",
        context=payload_context,
    )
```

**Test**: Unit test that method formats message correctly and calls `_emit()`.

#### 1.2: Route in Orchestrators

**Files**:
- `ktrdr/api/services/training/local_orchestrator.py`
- `training-host-service/orchestrator.py`

**Update `_create_progress_callback()`** in BOTH:
```python
def _create_progress_callback(self) -> Callable:
    def callback(epoch: int, total_epochs: int, metrics: dict[str, Any] | None = None):
        self._check_cancellation()

        metrics = metrics or {}
        progress_type = metrics.get("progress_type")

        # NEW: Handle preprocessing
        if progress_type == "preprocessing":
            symbol = metrics.get("symbol", "Unknown")
            symbol_index = metrics.get("symbol_index", 0)
            total_symbols = metrics.get("total_symbols", 0)
            step = metrics.get("step", "processing")

            context = {}
            if "timeframes" in metrics:
                context["timeframes"] = metrics["timeframes"]

            self._bridge.on_symbol_processing(
                symbol=symbol,
                symbol_index=symbol_index,
                total_symbols=total_symbols,
                step=step,
                context=context,
            )

        # EXISTING: Handle batch progress
        elif progress_type == "batch":
            self._bridge.on_batch(...)

        # EXISTING: Default to epoch
        else:
            self._bridge.on_epoch(...)

    return callback
```

**Test**: Unit test that routing works for `"preprocessing"` type.

#### 1.3: Report Progress in TrainingPipeline

**File**: `ktrdr/training/training_pipeline.py`

**Add progress callbacks** in `train_strategy()`:
```python
@staticmethod
def train_strategy(..., progress_callback=None, ...):
    # ... existing code ...

    for symbol_idx, symbol in enumerate(symbols, start=1):
        logger.info(f"📊 Processing symbol: {symbol}")

        # REPORT: Loading data
        if progress_callback:
            progress_callback(0, 0, {
                "progress_type": "preprocessing",
                "symbol": symbol,
                "symbol_index": symbol_idx,
                "total_symbols": len(symbols),
                "step": "loading_data",
            })

        # Load data (existing)
        price_data = TrainingPipeline.load_market_data(...)

        # REPORT: Computing indicators
        if progress_callback:
            progress_callback(0, 0, {
                "progress_type": "preprocessing",
                "symbol": symbol,
                "symbol_index": symbol_idx,
                "total_symbols": len(symbols),
                "step": "computing_indicators",
            })

        # Compute indicators (existing)
        indicators_data = TrainingPipeline.calculate_indicators(...)

        # REPORT: Generating fuzzy sets
        if progress_callback:
            progress_callback(0, 0, {
                "progress_type": "preprocessing",
                "symbol": symbol,
                "symbol_index": symbol_idx,
                "total_symbols": len(symbols),
                "step": "generating_fuzzy",
            })

        # Generate fuzzy (existing)
        fuzzy_data = TrainingPipeline.generate_fuzzy_memberships(...)

        # REPORT: Creating features
        if progress_callback:
            progress_callback(0, 0, {
                "progress_type": "preprocessing",
                "symbol": symbol,
                "symbol_index": symbol_idx,
                "total_symbols": len(symbols),
                "step": "creating_features",
            })

        # Create features (existing)
        features, feature_names = TrainingPipeline.create_features(...)

        # REPORT: Generating labels
        if progress_callback:
            progress_callback(0, 0, {
                "progress_type": "preprocessing",
                "symbol": symbol,
                "symbol_index": symbol_idx,
                "total_symbols": len(symbols),
                "step": "generating_labels",
            })

        # Generate labels (existing)
        labels = TrainingPipeline.create_labels(...)
```

**Test**: Integration test with mock strategy - verify progress callbacks invoked.

### Testing Phase 1

**Unit Tests**:
- `test_on_symbol_processing()` - Bridge method works
- `test_preprocessing_routing()` - Orchestrators route correctly

**Integration Test**:
```python
def test_symbol_level_progress():
    progress_updates = []

    def callback(progress):
        progress_updates.append(progress)

    result = TrainingPipeline.train_strategy(
        symbols=["AAPL", "TSLA"],
        timeframes=["1h"],
        strategy_config=simple_strategy,
        ...,
        progress_callback=callback
    )

    # Should see per-symbol progress
    preprocessing_updates = [u for u in progress_updates if u.get("context", {}).get("phase") == "preprocessing"]
    assert len(preprocessing_updates) > 0

    # Should see both symbols
    symbols_seen = set(u["context"]["symbol"] for u in preprocessing_updates)
    assert symbols_seen == {"AAPL", "TSLA"}
```

**CLI Test**:
```bash
ktrdr models train --strategy config/strategies/simple.yaml

# Expected output (NEW):
# Processing AAPL (1/2) - Loading Data
# Processing AAPL (1/2) - Computing Indicators
# Processing AAPL (1/2) - Generating Fuzzy
# Processing AAPL (1/2) - Creating Features
# Processing AAPL (1/2) - Generating Labels
# Processing TSLA (2/2) - Loading Data
# ... (continues)
# Epoch 1/100 · Batch 10/500 (existing)
```

### Acceptance Criteria

- [ ] Bridge method `on_symbol_processing()` implemented and tested
- [ ] Both orchestrators route `"preprocessing"` type
- [ ] TrainingPipeline reports progress at symbol boundaries
- [ ] CLI shows "Processing SYMBOL (X/Y)" messages
- [ ] Integration test passes
- [ ] No regression - training still works without callback

---

## Phase 2: Per-Indicator Granularity

**Goal**: User sees "Processing AAPL (2/5) [1h] - Computing RSI (15/40)"

**Duration**: 1 day

### What Gets Built

**End-to-end flow for indicator-level progress**:
1. TrainingProgressBridge gets `on_indicator_computation()` method
2. Both orchestrators route `"indicator_computation"` type
3. TrainingPipeline passes callback to `calculate_indicators()`
4. IndicatorEngine reports per-indicator progress
5. User sees granular indicator progress in CLI

### Implementation Tasks

#### 2.1: Add `on_indicator_computation()` to Bridge

**File**: `ktrdr/api/services/training/progress_bridge.py`

**Add method**:
```python
def on_indicator_computation(
    self,
    symbol: str,
    symbol_index: int,
    total_symbols: int,
    timeframe: str,
    indicator_name: str,
    indicator_index: int,
    total_indicators: int,
) -> None:
    """Report per-indicator computation with timeframe."""
    self._check_cancelled()

    message = (
        f"Processing {symbol} ({symbol_index}/{total_symbols}) [{timeframe}] - "
        f"Computing {indicator_name} ({indicator_index}/{total_indicators})"
    )

    # Fine-grained percentage within 0-5% range
    symbols_progress = (symbol_index - 1) / total_symbols
    indicator_progress = indicator_index / max(total_indicators, 1)
    percentage = symbols_progress * 5.0 + (indicator_progress / total_symbols) * 0.5

    payload_context = {
        "phase": "preprocessing",
        "preprocessing_step": "computing_indicator",
        "symbol": symbol,
        "symbol_index": symbol_index,
        "total_symbols": total_symbols,
        "timeframe": timeframe,
        "indicator_name": indicator_name,
        "indicator_index": indicator_index,
        "total_indicators": total_indicators,
    }

    self._emit(
        current_step=0,
        percentage=min(percentage, 5.0),
        message=message,
        items_processed=symbol_index,
        phase="preprocessing",
        context=payload_context,
    )
```

#### 2.2: Route in Orchestrators

**Update both orchestrators**:
```python
# In _create_progress_callback():
if progress_type == "indicator_computation":
    self._bridge.on_indicator_computation(
        symbol=metrics.get("symbol", "Unknown"),
        symbol_index=metrics.get("symbol_index", 1),
        total_symbols=metrics.get("total_symbols", 1),
        timeframe=metrics.get("timeframe", "unknown"),
        indicator_name=metrics.get("indicator_name", "unknown"),
        indicator_index=metrics.get("indicator_index", 1),
        total_indicators=metrics.get("total_indicators", 1),
    )
```

#### 2.3: Report Progress in TrainingPipeline (BEFORE indicator computation)

**File**: `ktrdr/training/training_pipeline.py`

**CRITICAL**: Do NOT modify `calculate_indicators()` signature or IndicatorEngine!

**Add progress reporting BEFORE the existing `calculate_indicators()` call**:

```python
# Step 2: Calculate indicators
# REPORT: Per-indicator progress (Phase 2 granularity)
if progress_callback:
    indicator_configs = strategy_config["indicators"]
    total_indicators = len(indicator_configs)

    # Report progress for each indicator being computed
    for ind_idx, indicator_config in enumerate(indicator_configs, start=1):
        indicator_name = indicator_config.get("indicator", "unknown")

        # Report for each timeframe (indicators are computed per timeframe)
        for timeframe in strategy_config.get("timeframes", ["unknown"]):
            progress_callback(
                0,
                0,
                {
                    "progress_type": "indicator_computation",
                    "symbol": symbol,
                    "symbol_index": symbol_idx,
                    "total_symbols": len(symbols),
                    "timeframe": timeframe,
                    "indicator_name": indicator_name,
                    "indicator_index": ind_idx,
                    "total_indicators": total_indicators,
                },
            )

# Now actually compute all indicators (unchanged computation logic)
indicators_data = TrainingPipeline.calculate_indicators(
    price_data, strategy_config["indicators"]
)
```

**Key Points**:
- Progress reporting happens BEFORE computation
- We iterate through the indicator configs we have available
- Report for each indicator × timeframe combination
- Then call the existing `calculate_indicators()` unchanged
- IndicatorEngine knows NOTHING about progress - stays pure computation

### Testing Phase 2

**Integration Test**:
```python
def test_indicator_level_progress():
    progress_updates = []

    def callback(progress):
        progress_updates.append(progress)

    result = TrainingPipeline.train_strategy(
        symbols=["AAPL"],
        timeframes=["1h", "4h"],
        strategy_config=strategy_with_many_indicators,  # 40 indicators
        ...,
        progress_callback=callback
    )

    # Should see per-indicator progress
    indicator_updates = [
        u for u in progress_updates
        if u.get("context", {}).get("preprocessing_step") == "computing_indicator"
    ]
    assert len(indicator_updates) > 0

    # Should see multiple indicators
    indicators_seen = set(u["context"]["indicator_name"] for u in indicator_updates)
    assert len(indicators_seen) > 5  # Should see multiple indicators
```

**CLI Test**:
```bash
ktrdr models train --strategy config/strategies/complex.yaml

# Expected output (NEW):
# Processing AAPL (1/5) [1h] - Loading data
# Processing AAPL (1/5) [1h] - Computing RSI (1/40)
# Processing AAPL (1/5) [1h] - Computing MACD (2/40)
# Processing AAPL (1/5) [1h] - Computing EMA (3/40)
# ... (all 40 indicators on 1h)
# Processing AAPL (1/5) [4h] - Computing RSI (1/40)
# ... (continues)
```

### Acceptance Criteria

- [x] Bridge method `on_indicator_computation()` implemented
- [x] Orchestrators route `"indicator_computation"` type
- [x] TrainingPipeline reports per-indicator progress (IndicatorEngine unchanged)
- [ ] CLI shows granular indicator progress with timeframe (needs E2E testing)
- [ ] Integration test passes

---

## Phase 3: Per-Fuzzy-Set Granularity

**Goal**: User sees "Processing AAPL (2/5) [1h] - Fuzzifying macd_standard (12/40)"

**Duration**: 0.5 day

### What Gets Built

**End-to-end flow for fuzzy-level progress** (same pattern as Phase 2):
1. TrainingProgressBridge gets `on_fuzzy_generation()` method
2. Both orchestrators route `"fuzzy_generation"` type
3. TrainingPipeline reports progress BEFORE calling `generate_fuzzy_memberships()`
4. FuzzyEngine remains UNCHANGED (pure computation)
5. User sees granular fuzzy progress in CLI

### Implementation Tasks

Follow same pattern as Phase 2:
1. Add `on_fuzzy_generation()` to bridge (same as Phase 2 indicator method)
2. Route in both orchestrators (same routing pattern)
3. **Add progress loop BEFORE `generate_fuzzy_memberships()` call** in TrainingPipeline
4. **DO NOT modify FuzzyEngine** - it stays pure computation
5. Test end-to-end

**Key Point**: Progress reporting happens in TrainingPipeline by iterating through fuzzy_set configs BEFORE calling FuzzyEngine, exactly like Phase 2 with indicators.

### Acceptance Criteria

- [ ] Bridge method `on_fuzzy_generation()` implemented
- [ ] Orchestrators route `"fuzzy_generation"` type
- [ ] TrainingPipeline reports per-fuzzy-set progress (FuzzyEngine unchanged)
- [ ] CLI shows granular fuzzy progress with timeframe
- [ ] Integration test passes

---

## Phase 4: Preparation Phase Progress

**Goal**: User sees "Combining data from 5 symbols", "Splitting data", "Creating model"

**Duration**: 0.5 day

### What Gets Built

**End-to-end flow for preparation steps**:
1. TrainingProgressBridge gets `on_preparation_phase()` method
2. Both orchestrators route `"preparation"` type
3. TrainingPipeline reports progress for combine/split/model-create
4. User sees preparation messages in CLI

### Implementation Tasks

#### 4.1: Add `on_preparation_phase()` to Bridge

```python
def on_preparation_phase(self, phase: str, message: str | None = None) -> None:
    """Report pre-training preparation phases."""
    self._check_cancelled()

    display_message = message or phase.replace('_', ' ').title()

    percentage = 5.0  # After preprocessing

    payload_context = {
        "phase": "preparation",
        "preparation_phase": phase,
    }

    self._emit(
        current_step=0,
        percentage=percentage,
        message=display_message,
        items_processed=0,
        phase="preparation",
        context=payload_context,
    )
```

#### 4.2: Route in Orchestrators

```python
elif progress_type == "preparation":
    phase = metrics.get("phase", "preparing")
    message = None

    if phase == "combining_data":
        total_symbols = metrics.get("total_symbols", 0)
        message = f"Combining data from {total_symbols} symbol(s)"
    elif phase == "splitting_data":
        total_samples = metrics.get("total_samples", 0)
        message = f"Splitting {total_samples} samples (train/val/test)"
    elif phase == "creating_model":
        input_dim = metrics.get("input_dim", 0)
        message = f"Creating model (input_dim={input_dim})"

    self._bridge.on_preparation_phase(phase=phase, message=message)
```

#### 4.3: Report in TrainingPipeline

```python
# After all symbol processing, before training

# Combining data
if progress_callback:
    progress_callback(0, 0, {
        "progress_type": "preparation",
        "phase": "combining_data",
        "total_symbols": len(symbols),
    })

combined_features, combined_labels = TrainingPipeline.combine_multi_symbol_data(...)

# Splitting data
if progress_callback:
    progress_callback(0, 0, {
        "progress_type": "preparation",
        "phase": "splitting_data",
        "total_samples": len(combined_features),
    })

# ... split logic ...

# Creating model
if progress_callback:
    progress_callback(0, 0, {
        "progress_type": "preparation",
        "phase": "creating_model",
        "input_dim": input_dim,
    })

model = TrainingPipeline.create_model(...)
```

### Testing Phase 4

**CLI Test**:
```bash
ktrdr models train --strategy config/strategies/complex.yaml

# Expected output (NEW at end of preprocessing):
# ... (all symbol/indicator/fuzzy progress) ...
# Combining data from 5 symbols
# Splitting 15847 samples (train/val/test)
# Creating model (input_dim=256)
# Epoch 1/100 · Batch 10/500 (existing)
```

### Acceptance Criteria

- [ ] Bridge method `on_preparation_phase()` implemented
- [ ] Orchestrators route `"preparation"` type
- [ ] TrainingPipeline reports preparation steps
- [ ] CLI shows preparation messages
- [ ] Integration test passes

---

## Phase 5: Enhanced Rendering & Polish

**Goal**: Polish message formatting, add visual indicators, improve readability

**Duration**: 0.5 day

**Note**: Phase 2/3 were simplified to symbol-level progress (not per-indicator/fuzzy).
This phase focuses on polishing what we actually have, not the original granular design.

### What Gets Built

**Enhanced TrainingProgressRenderer**:

1. Polish preprocessing message formatting
2. Add visual indicators (emojis/symbols) for different phases
3. Improve preparation phase message clarity
4. Ensure consistent formatting across all phases

### Implementation Tasks

#### 5.1: Enhance TrainingProgressRenderer

**File**: `ktrdr/api/services/training/training_progress_renderer.py`

**Update `render_message()` to polish existing messages**:
```python
def render_message(self, state: GenericProgressState) -> str:
    """Render training-specific progress message with polish."""

    phase = state.context.get("phase")
    preprocessing_step = state.context.get("preprocessing_step")

    # Preprocessing phase - add visual indicators
    if phase == "preprocessing":
        message = state.message  # Already formatted by bridge

        # Add phase-specific emoji/icon for visual clarity
        if preprocessing_step == "loading_data":
            return f"📊 {message}"
        elif preprocessing_step == "computing_indicators":
            return f"📈 {message}"
        elif preprocessing_step == "generating_fuzzy":
            return f"🔀 {message}"
        elif preprocessing_step == "creating_features":
            return f"🔧 {message}"
        elif preprocessing_step == "generating_labels":
            return f"🏷️  {message}"
        else:
            return message

    # Preparation phase - add visual indicator
    elif phase == "preparation":
        return f"⚙️  {state.message}"

    # Training phase - EXISTING LOGIC (unchanged)
    else:
        epoch_index = state.context.get("epoch_index", 0)
        total_epochs = state.context.get("total_epochs", 0)
        batch_number = state.context.get("batch_number")
        batch_total = state.context.get("batch_total_per_epoch")

        if epoch_index > 0 and total_epochs > 0:
            message = f"🎯 Epoch {epoch_index}/{total_epochs}"

            if batch_number is not None and batch_total is not None:
                message += f" · Batch {batch_number}/{batch_total}"

            # GPU info if available
            resource_usage = state.context.get("resource_usage", {})
            if isinstance(resource_usage, dict) and resource_usage.get("gpu_used"):
                gpu_util = resource_usage.get("gpu_utilization_percent")
                if gpu_util is not None:
                    message += f" · GPU {gpu_util:.0f}%"

            return message
        else:
            return state.message
```

**Key Changes from Original Design**:

- ❌ Removed per-indicator/fuzzy-set rendering (not implemented in Phase 2/3)
- ✅ Added emoji/icons for visual phase distinction
- ✅ Polished existing symbol-level messages
- ✅ Kept training phase rendering clean and informative

### Testing Phase 5

**Manual CLI Test**: Run training with complex strategy, verify messages look good.

**Integration Test**: Verify renderer formats all progress types correctly.

### Acceptance Criteria

- [ ] Renderer formats granular messages nicely
- [ ] Timeframe visible in messages
- [ ] Existing epoch/batch rendering still works
- [ ] All message types tested
- [ ] CLI output looks polished

---

## Testing Strategy

### Per-Phase Testing

Each phase includes:
1. **Unit tests** - Bridge methods, orchestrator routing
2. **Integration test** - Full training flow with progress
3. **CLI test** - Manual verification of user experience

### Final Integration Tests

After Phase 5, run comprehensive tests:

```python
def test_complete_training_progress():
    """Test full training with all progress types."""
    progress_updates = []

    def callback(progress):
        progress_updates.append(progress)

    result = TrainingPipeline.train_strategy(
        symbols=["AAPL", "TSLA", "MSFT"],
        timeframes=["1h", "4h"],
        strategy_config=complex_strategy,  # 40 indicators, 40 fuzzy sets
        ...,
        progress_callback=callback
    )

    # Should see all progress types
    progress_types = set(u.get("context", {}).get("phase") for u in progress_updates)
    assert "preprocessing" in progress_types
    assert "preparation" in progress_types

    # Should see granular indicator updates
    indicator_updates = [
        u for u in progress_updates
        if u.get("context", {}).get("preprocessing_step") == "computing_indicator"
    ]
    assert len(indicator_updates) > 100  # Many indicators across symbols/timeframes

    # Should see granular fuzzy updates
    fuzzy_updates = [
        u for u in progress_updates
        if u.get("context", {}).get("preprocessing_step") == "generating_fuzzy"
    ]
    assert len(fuzzy_updates) > 100  # Many fuzzy sets

    # Progress should increase monotonically
    percentages = [u["percentage"] for u in progress_updates if "percentage" in u]
    for i in range(1, len(percentages)):
        assert percentages[i] >= percentages[i-1], "Progress should not decrease"
```

### CLI End-to-End Test

```bash
# Test with complex strategy
ktrdr models train --strategy config/strategies/complex.yaml

# Expected output shows:
# 1. Symbol-level: "Processing AAPL (1/5)"
# 2. Indicator-level: "Processing AAPL (1/5) [1h] - Computing RSI (15/40)"
# 3. Fuzzy-level: "Processing AAPL (1/5) [1h] - Fuzzifying macd_standard (12/40)"
# 4. Preparation: "Combining data from 5 symbols"
# 5. Training: "Epoch 1/100 · Batch 10/500" (existing)

# Verify:
# - No silence periods > 2 seconds
# - Progress visible throughout
# - Messages clear and helpful
# - Training completes successfully
```

---

## Rollback Plan

**If issues found in any phase**:

1. **Identify failing phase** (e.g., Phase 2 breaks something)
2. **Revert that phase only** (git revert specific commits)
3. **Keep earlier phases** (Phase 1 still works)
4. **Previous functionality preserved** (training still works)

**Each phase is independently revertible** because each is a complete vertical slice.

---

## Success Criteria

### Technical

- [ ] All 5 phases implemented and tested
- [ ] Unit tests pass (>90% coverage)
- [ ] Integration tests pass
- [ ] CLI shows progress at all granularity levels
- [ ] No regression - training works with and without callback
- [ ] Performance overhead < 1%

### User Experience

- [ ] Zero silence during training (max 2s between updates)
- [ ] Clear, helpful progress messages
- [ ] Granular visibility (per-indicator, per-fuzzy-set)
- [ ] Timeframe context visible
- [ ] Preparation steps visible

---

## Timeline

| Phase | Duration | Testable Output |
|-------|----------|----------------|
| Phase 1: Symbol-level | 1 day | "Processing AAPL (2/5)" |
| Phase 2: Indicator-level | 1 day | "Computing RSI (15/40) [1h]" |
| Phase 3: Fuzzy-level | 0.5 day | "Fuzzifying macd (12/40) [1h]" |
| Phase 4: Preparation | 0.5 day | "Combining data from 5 symbols" |
| Phase 5: Polish | 0.5 day | Polished, formatted messages |

**Total**: 3.5 days (~1 week)

**Critical Path**: Linear (each phase builds on previous)

---

**END OF IMPLEMENTATION PLAN**
