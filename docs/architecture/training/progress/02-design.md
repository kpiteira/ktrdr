# Training Pre-Processing Progress Reporting: Design

**Date**: 2025-01-16
**Status**: Design Phase
**Related**: [Problem Statement](./01-problem-statement.md)

---

## Executive Summary

**Problem**: Training reports progress during model training (epochs/batches) but is silent during 2-5 minutes of data loading, indicator computation, fuzzy generation, and feature engineering.

**Solution**: Extend the existing `TrainingProgressBridge` to capture and report progress from pre-training phases with granular visibility into each step.

**Key Insight**: **Visibility > Precision**. Users need to know "Processing TSLA [1h] - Computing RSI (15/40)" more than they need exact percentages.

---

## Design Principles

1. **Leverage Existing Infrastructure**: Use `TrainingProgressBridge` and `TrainingProgressRenderer` - don't rebuild
2. **Context-Rich Messages**: Show symbol, timeframe, indicator name, step number
3. **Granular Visibility**: Report per-indicator during computation, per-fuzzy-set during fuzzification
4. **Simple Percentages**: Pre-training ≈5%, Training ≈90%, Evaluation ≈5%
5. **Per-Symbol Flow**: Follow actual code structure (process each symbol completely before next)

---

## Current Architecture

### Existing Infrastructure (Already Working!)

```
┌─────────────────────────────────────────────────────────────────┐
│ LocalTrainingOrchestrator                                       │
│  - Coordinates training operation                               │
│  - Creates progress infrastructure                              │
└─────────────────────────────────────────────────────────────────┘
         │
         │ creates
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ TrainingProgressBridge                                          │
│  - Translates training callbacks → generic progress updates     │
│  - Methods: on_epoch(), on_batch(), on_complete()              │
│  - Emits to GenericProgressManager                              │
└─────────────────────────────────────────────────────────────────┘
         │
         │ updates
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ GenericProgressManager                                          │
│  - Manages progress state (percentage, message, context)        │
│  - Thread-safe state updates                                    │
└─────────────────────────────────────────────────────────────────┘
         │
         │ triggers
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ TrainingProgressRenderer                                        │
│  - Formats training-specific messages                           │
│  - Example: "Epoch 5/100 · Batch 120/500 🖥️ GPU: 85%"         │
└─────────────────────────────────────────────────────────────────┘
         │
         │ displays
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ User Interface (CLI/API)                                        │
└─────────────────────────────────────────────────────────────────┘
```

### Current Training Flow (What Gets Reported)

```
TrainingPipeline.train_strategy()
├─ Load market data          [NO PROGRESS REPORTED]
├─ Calculate indicators       [NO PROGRESS REPORTED]
├─ Generate fuzzy sets        [NO PROGRESS REPORTED]
├─ Create features            [NO PROGRESS REPORTED]
├─ Generate labels            [NO PROGRESS REPORTED]
├─ Combine data               [NO PROGRESS REPORTED]
├─ Split data                 [NO PROGRESS REPORTED]
├─ Create model               [NO PROGRESS REPORTED]
├─ Train model                [✓ PROGRESS REPORTED via TrainingProgressBridge]
│   ├─ Epoch 1
│   │   ├─ Batch 1/500
│   │   ├─ Batch 2/500
│   │   └─ ...
│   └─ Epoch 2...
└─ Evaluate model             [NO PROGRESS REPORTED]
```

**Result**: 2-5 minutes of silence before progress starts.

---

## Proposed Design

### High-Level Approach

**Extend TrainingProgressBridge with new methods** to capture pre-training progress:

```
TrainingProgressBridge (EXISTING)
├─ on_epoch()                 [EXISTING - handles epoch completion]
├─ on_batch()                 [EXISTING - handles batch progress]
├─ on_complete()              [EXISTING - marks training complete]
├─ on_symbol_processing()     [NEW - handles per-symbol steps]
├─ on_indicator_computation() [NEW - handles per-indicator progress]
├─ on_fuzzy_generation()      [NEW - handles per-fuzzy-set progress]
└─ on_preparation_phase()     [NEW - handles data combining/splitting]
```

**Why this works**:
- Reuses existing progress infrastructure (no new systems)
- Bridge already knows how to emit to GenericProgressManager
- Renderer already knows how to format training messages
- Just need to add new message types for pre-training phases

### Granular Progress Hierarchy

The design supports **4 levels of granularity**:

```
Level 1: Symbol Level
└─ "Processing AAPL (2/5)"

Level 2: Timeframe Level
└─ "Processing AAPL (2/5) [1h]"

Level 3: Step Level
└─ "Processing AAPL (2/5) [1h] - Computing indicators"

Level 4: Sub-Step Level (MOST GRANULAR)
└─ "Processing AAPL (2/5) [1h] - Computing RSI (15/40)"
└─ "Processing AAPL (2/5) [1h] - Fuzzifying macd_standard (12/40)"
```

**User Requirement**: We need **Level 4 granularity** for indicators and fuzzy sets.

### Progress Flow (After Implementation)

```
┌─────────────────────────────────────────────────────────────────┐
│ TrainingPipeline.train_strategy()                               │
│                                                                  │
│  for symbol in symbols:                                         │
│    ┌────────────────────────────────────────────────┐          │
│    │ Load data                                       │          │
│    │  → progress_callback("preprocessing", ...)     │          │
│    └────────────────────────────────────────────────┘          │
│                                                                  │
│    ┌────────────────────────────────────────────────┐          │
│    │ Calculate indicators                            │          │
│    │  for indicator in indicators:                   │          │
│    │    → progress_callback("indicator_computation") │          │
│    └────────────────────────────────────────────────┘          │
│                                                                  │
│    ┌────────────────────────────────────────────────┐          │
│    │ Generate fuzzy sets                             │          │
│    │  for fuzzy_set in fuzzy_sets:                   │          │
│    │    → progress_callback("fuzzy_generation")      │          │
│    └────────────────────────────────────────────────┘          │
│                                                                  │
│    ┌────────────────────────────────────────────────┐          │
│    │ Create features                                 │          │
│    │  → progress_callback("preprocessing", ...)     │          │
│    └────────────────────────────────────────────────┘          │
│                                                                  │
│    ┌────────────────────────────────────────────────┐          │
│    │ Generate labels                                 │          │
│    │  → progress_callback("preprocessing", ...)     │          │
│    └────────────────────────────────────────────────┘          │
│                                                                  │
│  ┌────────────────────────────────────────────────┐            │
│  │ Combine data                                    │            │
│  │  → progress_callback("preparation", ...)       │            │
│  └────────────────────────────────────────────────┘            │
│                                                                  │
│  ┌────────────────────────────────────────────────┐            │
│  │ Split data                                      │            │
│  │  → progress_callback("preparation", ...)       │            │
│  └────────────────────────────────────────────────┘            │
│                                                                  │
│  ┌────────────────────────────────────────────────┐            │
│  │ Train model (EXISTING PROGRESS)                │            │
│  │  → progress_callback(epoch, batch, ...)        │            │
│  └────────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
         │
         │ all callbacks flow to
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ LocalOrchestrator._create_progress_callback()                   │
│                                                                  │
│  Routes based on progress_type:                                │
│    - "indicator_computation" → bridge.on_indicator_computation() │
│    - "fuzzy_generation" → bridge.on_fuzzy_generation()          │
│    - "preprocessing" → bridge.on_symbol_processing()            │
│    - "preparation" → bridge.on_preparation_phase()              │
│    - "batch" → bridge.on_batch() [EXISTING]                     │
│    - default → bridge.on_epoch() [EXISTING]                     │
└─────────────────────────────────────────────────────────────────┘
         │
         │ delegates to
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ TrainingProgressBridge                                          │
│                                                                  │
│  NEW METHODS (added):                                           │
│    on_symbol_processing() → formats "Processing AAPL (2/5)"    │
│    on_indicator_computation() → "Computing RSI (15/40)"         │
│    on_fuzzy_generation() → "Fuzzifying macd_standard (12/40)"  │
│    on_preparation_phase() → "Combining data from 5 symbols"     │
│                                                                  │
│  EXISTING METHODS (unchanged):                                  │
│    on_epoch() → "Epoch 5/100"                                   │
│    on_batch() → "Epoch 5/100 · Batch 120/500"                  │
└─────────────────────────────────────────────────────────────────┘
         │
         │ emits to
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ GenericProgressManager (UNCHANGED)                              │
└─────────────────────────────────────────────────────────────────┘
         │
         │ triggers
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ TrainingProgressRenderer                                        │
│                                                                  │
│  ENHANCED to check context for preprocessing_step:              │
│    - "computing_indicator" → render with timeframe + indicator  │
│    - "generating_fuzzy" → render with timeframe + fuzzy set     │
│    - "preprocessing" → render general step                      │
│    - default → render epoch/batch (EXISTING)                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## User Experience Transformation

### Before (3 minutes of silence)

```
[user initiates training]
[... waits 180 seconds with no feedback ...]
Epoch 1/100 · Batch 10/500
Epoch 1/100 · Batch 20/500
```

**Problems**:
- No idea what's happening for 3 minutes
- Can't tell if process is stuck or working
- Can't cancel with confidence (might be mid-operation)
- No debugging context if something fails

### After (full visibility)

```
Processing AAPL (1/5) [1h] - Loading data
Processing AAPL (1/5) [4h] - Loading data
Processing AAPL (1/5) [1d] - Loading data

Processing AAPL (1/5) [1h] - Computing RSI (1/40)
Processing AAPL (1/5) [1h] - Computing MACD (2/40)
Processing AAPL (1/5) [1h] - Computing EMA (3/40)
... [continues for all 40 indicators]

Processing AAPL (1/5) [4h] - Computing RSI (1/40)
... [continues for all timeframes]

Processing AAPL (1/5) [1h] - Fuzzifying rsi_14 (1/40)
Processing AAPL (1/5) [1h] - Fuzzifying macd_standard (2/40)
... [continues for all fuzzy sets]

Processing AAPL (1/5) - Creating features
Processing AAPL (1/5) - Generating labels

Processing TSLA (2/5) [1h] - Loading data
... [repeats for all symbols]

Combining data from 5 symbols
Splitting 15847 samples (train/val/test)
Creating model (input_dim=256)

Epoch 1/100 · Batch 10/500 🖥️ GPU: 85%  ← Existing progress continues seamlessly!
Epoch 1/100 · Batch 20/500
```

**Benefits**:
- **Zero silence** - constant feedback
- **Debugging context** - know exactly where process is
- **Cancellation confidence** - see it's responsive
- **Time estimation** - can gauge remaining time
- **Granular visibility** - symbol, timeframe, indicator name, progress counters

---

## Key Design Decisions

### Decision 1: Extend Bridge vs. New Coordinator

**Options Considered**:
- A) Create new `TrainingProgressCoordinator` to orchestrate pre-training progress
- B) Extend existing `TrainingProgressBridge` with new methods

**Decision**: **Option B - Extend TrainingProgressBridge**

**Rationale**:
- Bridge already handles progress translation (training callbacks → generic progress)
- Bridge already knows how to emit to GenericProgressManager
- Adding a coordinator would be redundant - the bridge IS the coordinator
- Simpler, leverages existing patterns, less code

### Decision 2: Granularity Level

**Options Considered**:
- A) Symbol-level only: "Processing AAPL (2/5)"
- B) Step-level: "Processing AAPL (2/5) - Computing indicators"
- C) Sub-step level: "Processing AAPL (2/5) [1h] - Computing RSI (15/40)"

**Decision**: **Option C - Sub-step level for indicators and fuzzy sets**

**Rationale**:
- User explicitly requested: "which indicator is being computed, that's good information"
- Provides maximum debugging context
- Shows exact progress through long operations
- Timeframe context helps identify multi-timeframe issues

### Decision 3: Progress Percentage Allocation

**Options Considered**:
- A) Complex phase-weighted percentages (track each symbol's progress precisely)
- B) Simple allocation: Pre-training 5%, Training 90%, Evaluation 5%

**Decision**: **Option B - Simple allocation**

**Rationale**:
- User feedback: "The percentages themselves are less important"
- Training is 95% of actual wall-clock time
- Rendering visibility is more important than precise percentages
- Simpler implementation, less error-prone

### Decision 4: Implementation Strategy

**Options Considered**:

- A) Refactor how indicators/fuzzy sets are computed to enable progress hooks
- B) Add progress callbacks within existing computation loops (no refactoring)

**Decision**: **Option B - Add callbacks to existing loops**

**Rationale**:

- Current computation flow (per-symbol, per-timeframe) is correct - don't change it
- Just need to insert progress callbacks at the right points in existing loops
- `IndicatorEngine` and `FuzzyEngine` already iterate internally - hook into those iterations
- Minimal code changes, preserves existing architecture
- No performance impact, no risk of breaking existing computation logic

---

## Integration Points

### Component Changes Overview

```
┌────────────────────────────────────────────────────────────┐
│ TrainingProgressBridge                                     │
│  ADD: 4 new methods for pre-training progress              │
│  UNCHANGED: existing epoch/batch methods                   │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ TrainingPipeline                                           │
│  train_strategy(): ADD progress callbacks at checkpoints   │
│  calculate_indicators(): ADD per-indicator iteration       │
│  generate_fuzzy_memberships(): ADD per-fuzzy-set iteration │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ LocalOrchestrator + HostServiceOrchestrator                │
│  _create_progress_callback(): ADD routing for new types    │
│  (Both orchestrators need identical callback routing)      │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ TrainingProgressRenderer                                   │
│  render_message(): ADD formatting for preprocessing context│
│  UNCHANGED: existing epoch/batch rendering                 │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ IndicatorEngine / FuzzyEngine                              │
│  ADD: Progress callback parameter to existing methods      │
│  ADD: Progress reporting within existing iteration loops   │
└────────────────────────────────────────────────────────────┘
```

### Callback Data Flow

```
TrainingPipeline sends callback with context dict:
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
         ↓
Orchestrator routes to bridge method
  (LocalOrchestrator OR HostServiceOrchestrator)
  (Both need identical routing logic for new progress types)
         ↓
TrainingProgressBridge.on_indicator_computation()
  - Formats message: "Processing AAPL (2/5) [1h] - Computing RSI (15/40)"
  - Calculates percentage: ~2.3% (within 0-5% pre-training range)
  - Emits to GenericProgressManager
         ↓
GenericProgressManager updates state
         ↓
TrainingProgressRenderer formats final display
         ↓
User sees: "Processing AAPL (2/5) [1h] - Computing RSI (15/40)"
```

**Important**: Both `LocalOrchestrator` and `HostServiceOrchestrator` need the same callback routing updates since both call `TrainingPipeline.train_strategy()`. The change is minor since all the real work happens in TrainingPipeline - the orchestrators just route callbacks to the bridge.

---

## What Stays the Same

**Critical**: This design **extends** existing infrastructure, doesn't replace it.

- ✓ Existing epoch/batch progress reporting (UNCHANGED)
- ✓ TrainingProgressBridge.on_epoch() and on_batch() (UNCHANGED)
- ✓ TrainingProgressRenderer epoch/batch formatting (UNCHANGED)
- ✓ GenericProgressManager (UNCHANGED)
- ✓ OperationsService integration (UNCHANGED)
- ✓ Cancellation token support (UNCHANGED)
- ✓ ServiceOrchestrator patterns (UNCHANGED)

**The existing training progress continues to work exactly as before!**

---

## Next Steps

See [03-architecture.md](./03-architecture.md) for detailed architecture and [04-implementation-plan.md](./04-implementation-plan.md) for implementation tasks.

---

**END OF DESIGN DOCUMENT**
