# Training Pre-Processing Progress Reporting: Architecture

**Date**: 2025-01-16
**Status**: Architecture Phase
**Related**: [Problem Statement](./01-problem-statement.md), [Design](./02-design.md)

---

## Executive Summary

This document defines the technical architecture for comprehensive progress reporting across all training phases. The solution **extends existing infrastructure** (`TrainingProgressBridge`, `TrainingProgressRenderer`) rather than creating new systems.

**Core Approach**: Add granular progress callbacks within `TrainingPipeline.train_strategy()` that route through existing orchestrators to the bridge, which formats and emits progress updates.

---

## Current Architecture

### Existing Training Progress Infrastructure

```
┌─────────────────────────────────────────────────────────────┐
│ Training Orchestrator (Local OR Host Service)               │
│  - Creates training operation                               │
│  - Creates progress callback                                │
│  - Creates TrainingProgressBridge                           │
└─────────────────────────────────────────────────────────────┘
         │
         │ creates
         ▼
┌─────────────────────────────────────────────────────────────┐
│ TrainingProgressBridge                                      │
│  - Translates training events → progress updates            │
│  - Methods: on_epoch(), on_batch(), on_complete()          │
│  - Emits to GenericProgressManager                          │
└─────────────────────────────────────────────────────────────┘
         │
         │ updates
         ▼
┌─────────────────────────────────────────────────────────────┐
│ GenericProgressManager                                      │
│  - Thread-safe progress state                               │
│  - Triggers callbacks on state change                       │
└─────────────────────────────────────────────────────────────┘
         │
         │ triggers
         ▼
┌─────────────────────────────────────────────────────────────┐
│ TrainingProgressRenderer                                    │
│  - Formats training-specific messages                       │
│  - Example: "Epoch 5/100 · Batch 120/500"                  │
└─────────────────────────────────────────────────────────────┘
         │
         │ displays via
         ▼
┌─────────────────────────────────────────────────────────────┐
│ OperationsService                                           │
│  - Stores progress in database                              │
│  - Broadcasts to clients (WebSocket/SSE)                    │
└─────────────────────────────────────────────────────────────┘
```

### Current Training Pipeline Flow

```
TrainingPipeline.train_strategy(progress_callback)
│
├─ Load market data          [NO CALLBACKS]
├─ Calculate indicators      [NO CALLBACKS]
├─ Generate fuzzy sets       [NO CALLBACKS]
├─ Create features           [NO CALLBACKS]
├─ Generate labels           [NO CALLBACKS]
├─ Combine data              [NO CALLBACKS]
├─ Split data                [NO CALLBACKS]
├─ Create model              [NO CALLBACKS]
├─ Train model               [✓ USES progress_callback]
│   └─ Reports epochs/batches
└─ Evaluate model            [NO CALLBACKS]
```

**Gap**: Progress callback exists but is only used during `train_model()`.

---

## Proposed Architecture

### High-Level Changes

**What we're adding**:
1. **New methods on TrainingProgressBridge** to handle pre-training progress
2. **Progress callbacks in TrainingPipeline** at key checkpoints
3. **Routing logic in orchestrators** to handle new progress types
4. **Enhanced rendering in TrainingProgressRenderer** for preprocessing context

**What stays the same**:
- Overall infrastructure (GenericProgressManager, OperationsService)
- Existing epoch/batch progress (on_epoch, on_batch methods)
- ServiceOrchestrator patterns
- Cancellation token support

### ⚠️ CRITICAL DESIGN PRINCIPLE

**Progress Reporting ≠ Computation**

Progress reporting happens **OUTSIDE** the computation engines:
- ✅ TrainingPipeline reports progress BEFORE calling engines
- ✅ Engines (IndicatorEngine, FuzzyEngine) remain pure computation
- ❌ Do NOT add progress callbacks to engine signatures
- ❌ Do NOT modify engine internals for progress

**Why**:
- Separation of concerns (orchestration vs computation)
- Engines stay reusable without progress dependencies
- Simpler implementation - iterate configs in pipeline, not engine internals
- Testability - engines remain pure functions

### Complete Progress Flow (After Implementation)

```
┌─────────────────────────────────────────────────────────────┐
│ Training Orchestrator (Local OR Host Service)               │
│  - Creates training operation                               │
│  - Creates progress callback                                │
│  - Creates TrainingProgressBridge                           │
└─────────────────────────────────────────────────────────────┘
         │
         │ calls
         ▼
┌─────────────────────────────────────────────────────────────┐
│ TrainingPipeline.train_strategy(progress_callback)          │
│                                                              │
│  Emits progress at checkpoints:                             │
│    - After loading data: callback("preprocessing", ...)     │
│    - Per indicator: callback("indicator_computation", ...)  │
│    - Per fuzzy set: callback("fuzzy_generation", ...)       │
│    - After features: callback("preprocessing", ...)         │
│    - After labels: callback("preprocessing", ...)           │
│    - After combining: callback("preparation", ...)          │
│    - During training: callback(epoch, batch, ...)           │
└─────────────────────────────────────────────────────────────┘
         │
         │ all callbacks flow to
         ▼
┌─────────────────────────────────────────────────────────────┐
│ Orchestrator._create_progress_callback()                    │
│                                                              │
│  Routes based on progress_type:                             │
│    "indicator_computation" → bridge.on_indicator_computation()│
│    "fuzzy_generation" → bridge.on_fuzzy_generation()        │
│    "preprocessing" → bridge.on_symbol_processing()          │
│    "preparation" → bridge.on_preparation_phase()            │
│    "batch" → bridge.on_batch() [EXISTING]                   │
│    default → bridge.on_epoch() [EXISTING]                   │
└─────────────────────────────────────────────────────────────┘
         │
         │ delegates to
         ▼
┌─────────────────────────────────────────────────────────────┐
│ TrainingProgressBridge                                      │
│                                                              │
│  NEW METHODS:                                               │
│    on_symbol_processing()                                   │
│    on_indicator_computation()                               │
│    on_fuzzy_generation()                                    │
│    on_preparation_phase()                                   │
│                                                              │
│  EXISTING METHODS (unchanged):                              │
│    on_epoch()                                               │
│    on_batch()                                               │
│    on_complete()                                            │
│                                                              │
│  All methods:                                               │
│    - Format message from context                            │
│    - Calculate percentage                                   │
│    - Emit to GenericProgressManager                         │
└─────────────────────────────────────────────────────────────┘
         │
         │ updates
         ▼
┌─────────────────────────────────────────────────────────────┐
│ GenericProgressManager (UNCHANGED)                          │
└─────────────────────────────────────────────────────────────┘
         │
         │ triggers
         ▼
┌─────────────────────────────────────────────────────────────┐
│ TrainingProgressRenderer                                    │
│                                                              │
│  ENHANCED to handle preprocessing context:                  │
│    - Check preprocessing_step in context                    │
│    - Format granular messages with timeframe + indicator    │
│    - Fall back to existing epoch/batch rendering            │
└─────────────────────────────────────────────────────────────┘
         │
         │ displays via
         ▼
┌─────────────────────────────────────────────────────────────┐
│ OperationsService (UNCHANGED)                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### 1. TrainingProgressBridge (Extended)

**Location**: `ktrdr/api/services/training/progress_bridge.py`

**Current State**:
- Has methods: `on_epoch()`, `on_batch()`, `on_complete()`, `on_phase()`, `on_remote_snapshot()`
- Handles epoch/batch progress during model training
- Emits to `GenericProgressManager`

**Changes Required**:

```
TrainingProgressBridge
│
├─ EXISTING METHODS (unchanged)
│   ├─ on_epoch(epoch, total_epochs, metrics)
│   ├─ on_batch(epoch, batch, total_batches, metrics)
│   ├─ on_complete(message)
│   ├─ on_phase(phase_name, message)
│   └─ on_remote_snapshot(snapshot)
│
├─ NEW METHODS
│   ├─ on_symbol_processing(symbol, symbol_index, total_symbols, step, context)
│   │   Purpose: Report per-symbol preprocessing steps
│   │   Example: "Processing AAPL (2/5) - Loading data"
│   │
│   ├─ on_indicator_computation(symbol, symbol_index, total_symbols,
│   │                            timeframe, indicator_name,
│   │                            indicator_index, total_indicators)
│   │   Purpose: Report per-indicator computation with timeframe
│   │   Example: "Processing AAPL (2/5) [1h] - Computing RSI (15/40)"
│   │
│   ├─ on_fuzzy_generation(symbol, symbol_index, total_symbols,
│   │                       timeframe, fuzzy_set_name,
│   │                       fuzzy_index, total_fuzzy_sets)
│   │   Purpose: Report per-fuzzy-set generation with timeframe
│   │   Example: "Processing AAPL (2/5) [1h] - Fuzzifying macd_standard (12/40)"
│   │
│   └─ on_preparation_phase(phase, message)
│       Purpose: Report data combining/splitting/model creation
│       Example: "Combining data from 5 symbols"
│
└─ INTERNAL METHODS (unchanged)
    ├─ _emit(current_step, percentage, message, items_processed, phase, context)
    ├─ _check_cancelled()
    ├─ _derive_percentage()
    └─ _clamp_items_processed()
```

**Key Design Points**:
- All new methods follow same pattern as existing methods
- Calculate simple percentages (pre-training: 0-5%, training: 5-95%)
- Build context-rich payload for renderer
- Use existing `_emit()` infrastructure

### 2. Training Orchestrators (Both Local and Host Service)

**Locations**:
- `ktrdr/api/services/training/local_orchestrator.py`
- `training-host-service/orchestrator.py` (in training host service)

**Current State**:
- `_create_progress_callback()` routes progress to bridge
- Currently handles: epoch progress, batch progress
- Both orchestrators have similar callback logic

**Changes Required**:

```
Both Orchestrators._create_progress_callback()
│
├─ EXISTING ROUTING (unchanged)
│   ├─ progress_type == "batch" → bridge.on_batch()
│   └─ default → bridge.on_epoch()
│
└─ NEW ROUTING
    ├─ progress_type == "indicator_computation"
    │   → bridge.on_indicator_computation(...)
    │
    ├─ progress_type == "fuzzy_generation"
    │   → bridge.on_fuzzy_generation(...)
    │
    ├─ progress_type == "preprocessing"
    │   → bridge.on_symbol_processing(...)
    │
    └─ progress_type == "preparation"
        → bridge.on_preparation_phase(...)
```

**Implementation Note**:
- Both orchestrators need **identical routing logic**
- Minor change since TrainingPipeline does the real work
- Just extracting fields from metrics dict and calling bridge methods

### 3. TrainingPipeline (Instrumented)

**Location**: `ktrdr/training/training_pipeline.py`

**Current State**:
- `train_strategy()` orchestrates entire training flow
- Has `progress_callback` parameter (already exists!)
- Currently only passes callback to `train_model()`

**Changes Required**:

```
TrainingPipeline.train_strategy()
│
├─ PHASE: Load market data
│   └─ ADD: Progress callbacks per timeframe load
│       Callback: progress_callback(0, 0, {
│           "progress_type": "preprocessing",
│           "symbol": symbol,
│           "symbol_index": idx,
│           "total_symbols": len(symbols),
│           "step": "loading_data",
│           "timeframe": tf
│       })
│
├─ PHASE: Calculate indicators
│   └─ MODIFY: calculate_indicators() to accept progress callback
│       └─ ADD: Progress callbacks per indicator per timeframe
│           Callback: progress_callback(0, 0, {
│               "progress_type": "indicator_computation",
│               "symbol": symbol,
│               "timeframe": tf,
│               "indicator_name": name,
│               "indicator_index": idx,
│               "total_indicators": count
│           })
│
├─ PHASE: Generate fuzzy memberships
│   └─ MODIFY: generate_fuzzy_memberships() to accept progress callback
│       └─ ADD: Progress callbacks per fuzzy set per timeframe
│           Callback: progress_callback(0, 0, {
│               "progress_type": "fuzzy_generation",
│               "symbol": symbol,
│               "timeframe": tf,
│               "fuzzy_set_name": name,
│               "fuzzy_index": idx,
│               "total_fuzzy_sets": count
│           })
│
├─ PHASE: Create features
│   └─ ADD: Single progress callback per symbol
│       Callback: progress_callback(0, 0, {
│           "progress_type": "preprocessing",
│           "step": "creating_features"
│       })
│
├─ PHASE: Generate labels
│   └─ ADD: Single progress callback per symbol
│       Callback: progress_callback(0, 0, {
│           "progress_type": "preprocessing",
│           "step": "generating_labels"
│       })
│
├─ PHASE: Combine data
│   └─ ADD: Single progress callback
│       Callback: progress_callback(0, 0, {
│           "progress_type": "preparation",
│           "phase": "combining_data",
│           "total_symbols": len(symbols)
│       })
│
├─ PHASE: Split data
│   └─ ADD: Single progress callback
│       Callback: progress_callback(0, 0, {
│           "progress_type": "preparation",
│           "phase": "splitting_data",
│           "total_samples": len(data)
│       })
│
├─ PHASE: Create model
│   └─ ADD: Single progress callback
│       Callback: progress_callback(0, 0, {
│           "progress_type": "preparation",
│           "phase": "creating_model",
│           "input_dim": dim
│       })
│
├─ PHASE: Train model
│   └─ EXISTING: progress_callback passed through (UNCHANGED)
│
└─ PHASE: Evaluate model
    └─ (Fast, no progress needed)
```

**Key Points**:
- Most changes are just inserting `if progress_callback:` checks
- Callback signature stays same: `callback(epoch, total_epochs, metrics)`
- For pre-training: pass `0, 0` for epoch/total_epochs, put data in metrics dict
- For training: existing behavior continues unchanged

### 4. IndicatorEngine and FuzzyEngine (UNCHANGED)

**Locations**:
- `ktrdr/indicators/indicator_engine.py`
- `ktrdr/fuzzy/fuzzy_engine.py`

**Current State**:
- Batch-compute all indicators/fuzzy sets
- No progress reporting

**Changes Required**: **NONE**

**Critical Design Decision**:
- IndicatorEngine and FuzzyEngine remain PURE COMPUTATION
- They know NOTHING about progress reporting
- Progress reporting happens in TrainingPipeline BEFORE calling these engines
- This keeps concerns separated: engines compute, pipeline orchestrates and reports

**Why this is better**:
- No changes to indicator/fuzzy computation logic
- No new parameters to thread through
- Engines remain testable in isolation
- Progress reporting is TrainingPipeline's responsibility (where it belongs)
- If engines are used elsewhere (non-training), they don't drag progress dependencies

### 5. TrainingProgressRenderer (Enhanced)

**Location**: `ktrdr/api/services/training/training_progress_renderer.py`

**Current State**:
- Renders epoch/batch messages: "Epoch 5/100 · Batch 120/500 🖥️ GPU: 85%"

**Changes Required**:

```
TrainingProgressRenderer.render_message(state)
│
├─ Check state.context.get("preprocessing_step")
│
├─ IF preprocessing_step == "computing_indicator":
│   └─ Format: "Processing {symbol} ({idx}/{total}) [{tf}] - Computing {indicator} ({idx}/{total})"
│
├─ ELIF preprocessing_step == "generating_fuzzy":
│   └─ Format: "Processing {symbol} ({idx}/{total}) [{tf}] - Fuzzifying {fuzzy} ({idx}/{total})"
│
├─ ELIF phase == "preprocessing":
│   └─ Format: "Processing {symbol} ({idx}/{total}) - {step}"
│
├─ ELIF phase == "preparation":
│   └─ Return: state.message (already formatted in bridge)
│
└─ ELSE (default):
    └─ EXISTING LOGIC: Format epoch/batch (UNCHANGED)
```

**Key Points**:
- Enhanced, not replaced
- Checks context to determine message type
- Falls back to existing epoch/batch rendering
- All existing functionality preserved

---

## Data Structures

### Progress Callback Context Dictionary

The `progress_callback` is invoked with `(epoch, total_epochs, metrics)` where `metrics` is a dict:

**For indicator computation**:
```python
{
    "progress_type": "indicator_computation",
    "symbol": "AAPL",
    "symbol_index": 2,
    "total_symbols": 5,
    "timeframe": "1h",
    "indicator_name": "RSI",
    "indicator_index": 15,
    "total_indicators": 40
}
```

**For fuzzy generation**:
```python
{
    "progress_type": "fuzzy_generation",
    "symbol": "AAPL",
    "symbol_index": 2,
    "total_symbols": 5,
    "timeframe": "1h",
    "fuzzy_set_name": "rsi_14",
    "fuzzy_index": 10,
    "total_fuzzy_sets": 40
}
```

**For general preprocessing**:
```python
{
    "progress_type": "preprocessing",
    "symbol": "AAPL",
    "symbol_index": 2,
    "total_symbols": 5,
    "step": "loading_data" | "creating_features" | "generating_labels",
    "timeframe": "1h"  # optional
}
```

**For preparation phase**:
```python
{
    "progress_type": "preparation",
    "phase": "combining_data" | "splitting_data" | "creating_model",
    "total_symbols": 5,  # for combining
    "total_samples": 15847,  # for splitting
    "input_dim": 256  # for model creation
}
```

---

## Error Handling

### Progress During Failures

When errors occur mid-operation:

1. **Progress callback already invoked** showing current step
2. **Error context preserved** in OperationsService
3. **User sees** exactly where failure occurred

Example: If loading AAPL (symbol 2/5) fails, user sees:
```
Processing AAPL (2/5) [1h] - Loading data
ERROR: Failed to load AAPL: Connection timeout
```

No special error handling needed in progress system - errors propagate normally, last progress update shows context.

### Cancellation

Cancellation tokens already exist and work:
- TrainingPipeline checks `cancellation_token.is_cancelled()` periodically
- Progress reporting doesn't interfere with cancellation
- On cancellation, last progress update shows where it was cancelled

---

## Performance Considerations

### Overhead Analysis

**Per progress update**:
- Context dict creation: ~0.01ms
- Callback invocation: ~0.05ms
- Bridge formatting: ~0.1ms
- GenericProgressManager update: ~0.1ms
- Database write (async): ~1-5ms

**Total**: ~1-5ms per update (non-blocking)

**Updates per training**:
- Symbol-level: ~10-20 updates
- Indicator-level: ~200-400 updates (5 symbols × 40 indicators × 2 timeframes)
- Fuzzy-level: ~200-400 updates

**Total overhead**: ~500-1000ms over 3-5 minute training = **< 0.5%**

### Optimization Opportunities

If overhead becomes an issue (unlikely):
1. **Throttle updates** in tight loops (e.g., max 5 updates/second)
2. **Batch context updates** (reuse dicts)
3. **Lazy formatting** (only format when rendered)
4. **Skip updates** for very fast operations (< 100ms)

---

## Testing Strategy

### Unit Tests

**TrainingProgressBridge**:
- Test each new method formats correct message
- Test percentage calculations
- Test context propagation
- Test cancellation handling

**Orchestrators**:
- Test routing logic for new progress types
- Test context extraction from metrics dict
- Test both Local and Host Service orchestrators

**TrainingProgressRenderer**:
- Test preprocessing message formatting
- Test fallback to existing epoch/batch rendering
- Test context-based formatting

### Integration Tests

**TrainingPipeline**:
- Test progress callbacks invoked at correct points
- Test context includes correct symbol/timeframe/indicator info
- Test with actual strategy configuration

**End-to-End**:
- Test full training flow with progress reporting
- Verify progress updates appear in OperationsService
- Verify messages render correctly

---

## Summary

This architecture provides comprehensive progress reporting by:

1. **Extending existing bridge** with 4 new methods for pre-training progress
2. **Instrumenting TrainingPipeline** with progress callbacks at ~15 checkpoints
3. **Routing in both orchestrators** to handle new progress types
4. **Enhancing renderer** to format preprocessing messages
5. **ZERO changes** to IndicatorEngine/FuzzyEngine (they stay pure computation)

**Key Benefits**:
- Leverages existing infrastructure (no new systems)
- Minimal code changes (mostly adding callbacks)
- Zero silence during training (constant feedback)
- Granular visibility (per-indicator, per-fuzzy-set with timeframe)
- < 0.5% performance overhead

---

**Next**: Implementation plan breaking this into phased tasks.

---

**END OF ARCHITECTURE DOCUMENT**
