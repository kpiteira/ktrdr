# Training Service Architecture - Shared Pipeline, Separate Orchestration

**Date**: 2025-01-07
**Status**: Architecture Design
**Previous**: [02-requirements.md](./02-requirements.md)
**Next**: Implementation Plan (TBD)

---

## Executive Summary

This architecture eliminates code duplication in the KTRDR training system by extracting shared training logic into a reusable `TrainingPipeline` component, while keeping orchestration concerns (progress reporting, cancellation, async boundaries) separate and environment-specific.

**Core Principle**: Share the work, separate the coordination.

**Two-Phase Approach**:

- **Phase 1** (This Document): Minimal refactoring to eliminate duplication
  - Extract pure training logic into `TrainingPipeline`
  - Preserve all current behavior (async model, cancellation, mode selection)
  - Goal: Zero divergence while ensuring everything works

- **Phase 2** (Future): Risk-bearing improvements
  - Harmonize async model (explore single pattern)
  - Unify cancellation mechanisms
  - Dynamic execution mode selection
  - Progress improvements
  - Any other risky changes

**This document focuses exclusively on Phase 1.**

---

## Problem Statement

### Current State: Both Paths Work, But Code is Duplicated

**Both execution paths work correctly today**:
- Local (Docker container): Training executes, saves models, reports progress
- Host Service (Native macOS): Training executes, saves models, reports progress

**The problem is code duplication**:

| Component | Backend | Host Service | Duplication % |
|-----------|---------|--------------|---------------|
| Data loading | `StrategyTrainer` | `TrainingService._run_real_training()` | 80% |
| Indicators | Uses `IndicatorEngine` | Uses `IndicatorEngine` | 80% |
| Fuzzy logic | Uses `FuzzyEngine` | Uses `FuzzyEngine` | 80% |
| Feature engineering | Uses `FuzzyNeuralProcessor` | Simplified version | 70% |
| Training loop | Uses `ModelTrainer` | Custom loop | 60% |
| Model saving | Uses `ModelStorage` | Uses `ModelStorage` | 100% |
| **Total** | **~1,500 lines** | **~1,000 lines** | **~80%** |

**Consequences of duplication**:
- Bugs fixed in one place but not the other
- Features added requiring duplicate work
- Divergent behavior over time
- Double testing overhead

### Previous Failed Attempt

**What we tried**: Create a unified `TrainingExecutor` that works for both local and host execution with a single orchestration layer.

**Why it failed**:
1. Tried to unify progress mechanisms (callback-based vs polling-based)
2. Tried to unify cancellation (in-memory token vs HTTP flag)
3. Tried to unify async boundaries (different contexts)

**These are fundamentally different and forcing unification added complexity without benefit.**

### The Right Approach for Phase 1

**Extract what's identical (the work), accept what's different (the coordination):**

- **Shared**: TrainingPipeline with pure work functions
- **Different but OK**: Progress mechanisms (callbacks vs polling)
- **Different but OK**: Cancellation mechanisms (token vs HTTP)
- **Different but OK**: Async patterns (to_thread wrapper vs direct async)
- **Different but OK**: Mode selection (env var at startup)

**Phase 2 can explore harmonization after Phase 1 proves the pattern works.**

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
│            TrainingService (execution mode selection)    │
│  - Reads USE_TRAINING_HOST_SERVICE env var at startup   │
│  - Routes to local OR host orchestrator                  │
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
│ - Token cancellation   │  │ - HTTP cancellation    │
│ - asyncio.to_thread()  │  │ - Direct async         │
│   wraps entire run     │  │   (preserve current)   │
└────────────┬───────────┘  └────────────┬───────────┘
             │                           │
             │    Both use same logic    │
             └───────────┬───────────────┘
                         │
                         ↓
              ┌─────────────────────────────────┐
              │ TrainingPipeline                │
              │ (Pure Work Logic)               │
              │                                 │
              │ - load_price_data()             │
              │ - calculate_indicators()        │
              │ - generate_fuzzy_memberships()  │
              │ - engineer_features()           │
              │ - generate_labels()             │
              │ - combine_multi_symbol_data()   │
              │ - split_data()                  │
              │ - create_model()                │
              │ - train_model()                 │
              │ - evaluate_model()              │
              │ - save_model()                  │
              │                                 │
              │ Uses DeviceManager for GPU      │
              └─────────────────────────────────┘
```

### Key Components (Phase 1)

1. **TrainingPipeline** (New - Shared)
   - Pure, synchronous work functions
   - No callbacks, no cancellation checks, no async
   - Accepts callbacks/tokens only in `train_model()` (ModelTrainer interface)
   - Used by both orchestrators

2. **DeviceManager** (New - Shared)
   - Centralized GPU/device detection (MPS, CUDA, CPU)
   - Device capability checking
   - Used by all training code

3. **LocalTrainingOrchestrator** (Refactored from `LocalTrainingRunner`)
   - Uses `TrainingPipeline` for work
   - Manages local progress callbacks (preserve current)
   - Checks local cancellation token (preserve current)
   - Wraps execution in `asyncio.to_thread()` (preserve current)

4. **HostTrainingOrchestrator** (Refactored from `training_service._run_real_training`)
   - Uses `TrainingPipeline` for work
   - Updates session state for progress (preserve current)
   - Checks `session.stop_requested` for cancellation (preserve current)
   - Direct async execution (preserve current - NO to_thread)

---

## Execution Mode Selection (Current System - Preserved)

### How Backend Decides Execution Mode

**Current Implementation** (at startup - preserved in Phase 1):

1. Environment variable `USE_TRAINING_HOST_SERVICE` read at TrainingManager initialization
2. TrainingAdapter created with `use_host_service` flag
3. TrainingService checks `is_using_host_service()` when building context
4. Context includes `use_host_service` flag
5. `_legacy_operation_entrypoint()` routes based on flag:
   - `True` → `_run_host_training()` → HostSessionManager
   - `False` → `_run_local_training()` → LocalTrainingRunner

**Characteristics (Phase 1 - keep as-is)**:
- **Static**: Set at process startup, cannot change without restart
- **Global**: All training requests use same mode
- **Simple**: No health checks or fallback logic

**Phase 2 could add**: Dynamic selection, health checks, fallback

### How Host Service is Triggered (Current - Preserved)

**Current Flow**:

```
TrainingService._run_host_training()
  ↓
Creates HostSessionManager
  ↓
HostSessionManager.start_session()
  ↓
TrainingAdapter.train_multi_symbol_strategy()
  ↓
POST /training/start to host service
  ↓
Host service creates TrainingSession
  ↓
Host service runs _run_real_training() in background (async, not threaded)
  ↓
Returns session_id to backend
  ↓
HostSessionManager.poll_session()
  ↓
Loop: GET /training/status/{session_id} every 2 seconds
  ↓
Until status is terminal (completed/failed/cancelled)
```

**Key Points**:
- Backend polls host service every 2 seconds (configurable via `poll_interval`)
- Poll interval has exponential backoff (2s → 3s → 4.5s up to max 10s)
- Polling continues until training reaches terminal state
- Progress updates retrieved from session state during each poll

---

## Device Detection (New Component - Phase 1)

### Problem: Inconsistent Device Management

Currently device detection is scattered:
- `LocalTrainingRunner`: Simple `torch.device("cuda" if torch.cuda.is_available() else "cpu")`
- Host service: Complex MPS/CUDA detection with configuration
- No shared logic for device capabilities

### Solution: Centralized DeviceManager

**Design**: Single class that detects device and returns capabilities

**Responsibilities**:
- Detect best available device (CUDA > MPS > CPU)
- Return device capabilities (mixed precision support, memory, etc.)
- Log detection decisions
- Provide manual override option

**Key Insight**: Different devices have different capabilities:
- **CUDA**: Full capabilities (mixed precision, memory profiling)
- **MPS**: Limited capabilities (no mixed precision, no memory query)
- **CPU**: Fallback (no GPU features)

**Usage**: Training adapts to device capabilities rather than assuming features

**Phase 1 Focus**: Extract current device detection logic into shared component

---

## Component Design (Phase 1)

### TrainingPipeline (New Component)

**Location**: `ktrdr/training/pipeline.py`

**Responsibility**: Execute pure training transformations - no coordination

**Design Principles**:
1. **Pure functions**: Input → transformation → output
2. **No callbacks**: Returns data (except `train_model()` which passes through)
3. **No cancellation checks**: Caller handles coordination
4. **No async**: Synchronous work, caller manages async
5. **No progress reporting**: Caller reports progress

**Key Methods** (signatures only):
- `load_price_data(...) -> dict[str, dict[str, pd.DataFrame]]`
- `calculate_indicators(...) -> dict[str, dict[str, pd.DataFrame]]`
- `generate_fuzzy_memberships(...) -> dict[str, dict[str, pd.DataFrame]]`
- `engineer_features(...) -> tuple[dict, dict]`
- `generate_labels(...) -> dict[str, np.ndarray]`
- `combine_multi_symbol_data(...) -> tuple[np.ndarray, np.ndarray, np.ndarray]`
- `split_data(...) -> tuple[tuple, tuple, tuple]`
- `create_model(...) -> MLPTradingModel`
- `train_model(..., progress_callback, cancellation_token) -> dict` ← Only method accepting callbacks/tokens
- `evaluate_model(...) -> dict[str, float]`
- `save_model(...) -> str`

**Key Point**: Only `train_model()` accepts callbacks/tokens because `ModelTrainer` interface requires them

---

### LocalTrainingOrchestrator (Phase 1 - Preserve Current Pattern)

**Location**: `ktrdr/api/services/training/local_runner.py`

**Responsibility**: Coordinate training with local (in-process) mechanisms

**Current Pattern** (preserve in Phase 1):

```python
async def run(self) -> dict[str, Any]:
    # Wrap ENTIRE execution in thread pool (current behavior)
    return await asyncio.to_thread(self._execute_training)

def _execute_training(self) -> dict[str, Any]:
    # Synchronous orchestration

    # Check cancellation (current: in-memory token)
    self._check_cancellation()

    # Report progress (current: callback to bridge)
    self._bridge.on_phase("data_loading", message="...")

    # Do work (NEW: use pipeline)
    result = self._pipeline.load_price_data(...)

    # Training step passes callbacks through (current behavior)
    training_results = self._pipeline.train_model(
        ...,
        progress_callback=self._create_training_callback(),
        cancellation_token=self._token
    )
```

**What Changes**: Use `TrainingPipeline` for work
**What Stays**: Async pattern, callbacks, cancellation, progress reporting

---

### HostTrainingOrchestrator (Phase 1 - Preserve Current Pattern)

**Location**: `training-host-service/orchestrator.py` (new file)

**Responsibility**: Coordinate training with host service (session-based) mechanisms

**Current Pattern** (preserve in Phase 1):

Host service `_run_real_training()` is **already async** and does **NOT** use `asyncio.to_thread()`.

```python
async def run(self) -> dict[str, Any]:
    # Direct async execution (current behavior)

    # Check cancellation (current: session flag)
    if self._check_stop_requested():
        return self._cancelled_result()

    # Report progress (current: session state)
    self._update_progress(phase="data_loading", message="...")

    # Do work (NEW: use pipeline - but still async context)
    result = self._pipeline.load_price_data(...)

    # Training step passes callbacks through (current behavior)
    training_results = self._pipeline.train_model(
        ...,
        progress_callback=self._create_training_callback(),
        cancellation_token=SessionCancellationToken(session)
    )
```

**What Changes**: Use `TrainingPipeline` for work
**What Stays**: Async pattern (direct, no to_thread), session progress, HTTP cancellation

**Key Difference from Local**:
- Local wraps entire execution in `asyncio.to_thread()`
- Host runs directly in async context

**Why**: Host service is already async (FastAPI), can call sync pipeline methods directly

**Phase 2 Could Explore**: Should we unify these patterns? Trade-offs need analysis.

---

## Model Persistence (Phase 1 - Critical Gap to Fix)

### Problem: Host Service Doesn't Save Models

**Current State**:
- **Local**: Uses `ModelStorage` to save trained models to `models/` directory
- **Host**: Does NOT save models - just sets `session.status = "completed"`

**Consequence**: Models trained on host service are lost when session ends

**Evidence**:
```python
# Host service training_service.py line 795:
session.status = "completed"
# No ModelStorage.save_model() call
# No model_path in session
```

**This must be fixed in Phase 1** - otherwise host service training is useless.

### Solution: Host Service Uses Shared ModelStorage

**Design**: Host service saves model using same `ModelStorage` as backend

**Why This Works**:
- Host service runs natively (not in Docker)
- Has direct filesystem access to `models/` directory
- Can import `ModelStorage` from `ktrdr` package
- Both services write to same shared location

**Implementation**:

```python
# Host orchestrator after training completes:
from ktrdr.training.model_storage import ModelStorage

def _execute_training(self) -> dict[str, Any]:
    # ... training steps ...

    # Save model (NEW in Phase 1)
    model_path = self._pipeline.save_model(
        model=trained_model,
        strategy_name=self._get_strategy_name(),
        symbols=self._get_symbols(),
        timeframes=self._get_timeframes(),
        config=self._get_strategy_config(),
        metrics=training_results,
        feature_names=feature_names,
        scaler=scaler
    )

    # Store model_path in session for backend retrieval
    self._session.model_path = model_path
    self._session.status = "completed"

    return {
        "success": True,
        "model_path": model_path,
        "training_metrics": training_results,
        ...
    }
```

**Backend retrieves model_path from session**:

```python
# HostSessionManager.poll_session() already does this:
snapshot = await self._adapter.get_training_status(session_id)

# Snapshot includes model_path from session
artifacts = {
    "model_path": snapshot.get("model_path"),  # Now present
    ...
}
```

### Key Points

1. **Same Storage, Different Processes**:
   - Both backend and host service use `ModelStorage`
   - Both write to shared `models/` directory
   - Model files accessible to both

2. **No Network Transfer Needed**:
   - Host service saves directly to filesystem
   - Backend reads from same filesystem
   - No need to transfer model bytes over HTTP

3. **Consistent Model Format**:
   - Same `ModelStorage.save_model()` method
   - Same file structure
   - Same metadata format

4. **TrainingPipeline Handles This**:
   - Pipeline already has `save_model()` method
   - Both orchestrators call it
   - Works identically in both contexts

### Limitation (Phase 1)

**Assumption**: Backend and host service run on the same machine (or share filesystem)

**Why**: Both must access the same `models/` directory

**Current Deployment**: This assumption holds
- Development: Both run on same macOS machine
- Docker: Backend in container, host service on host, shared via volume mount

**Phase 2 Improvement**: Add remote model transfer for distributed deployment (see Phase 2 doc)

### Success Criteria (Phase 1)

- ✅ Host service saves models via `ModelStorage`
- ✅ Model path returned in session snapshot
- ✅ Backend can load models trained on host service
- ✅ Models from both modes are interchangeable
- ✅ Works for same-machine deployment (current setup)

---

## Progress Communication (Phase 1 - Preserve Current)

### Local Flow (Callback-Based - Keep)

```
ModelTrainer.train()
  └─> progress_callback(epoch, metrics)
      └─> LocalTrainingOrchestrator callback
          └─> TrainingProgressBridge.on_epoch()
              └─> GenericProgressManager.update()
                  └─> ProgressRenderer displays (immediate)
```

**Latency**: Immediate (same process)

### Host Flow (Polling-Based - Keep)

```
ModelTrainer.train()
  └─> progress_callback(epoch, metrics)
      └─> HostTrainingOrchestrator callback
          └─> session.update_progress(epoch, batch, metrics)
              └─> Stored in TrainingSession state

[Backend polls separately every 2s]
HostSessionManager.poll_session()
  └─> GET /training/status/{session_id}
      └─> Returns session.get_progress_dict()
          └─> TrainingProgressBridge.on_remote_snapshot()
              └─> GenericProgressManager.update()
                  └─> ProgressRenderer displays (delayed)
```

**Latency**: Up to 2s (polling interval)

**Phase 1**: Accept these are different, both work fine
**Phase 2**: Could explore WebSocket streaming

---

## Cancellation Propagation (Phase 1 - Preserve Current)

### Local Flow (Token-Based - Keep)

```
User cancels
  ↓
POST /api/v1/operations/{id}/cancel
  ↓
OperationsService.cancel_operation()
  ↓
cancellation_token.cancel()  # In-memory flag
  ↓
LocalTrainingOrchestrator._check_cancellation()
  ↓
Raises CancellationError
  ↓
Training stops
```

**Latency**: < 50ms

### Host Flow (HTTP-Based - Keep)

```
User cancels
  ↓
POST /api/v1/operations/{id}/cancel
  ↓
OperationsService.cancel_operation()
  ↓
cancellation_token.cancel()  # Backend token
  ↓
HostSessionManager detects on next poll
  ↓
POST /training/stop to host service
  ↓
session.stop_requested = True
  ↓
HostTrainingOrchestrator._check_stop_requested()
  ↓
Returns cancelled result OR raises CancellationError
  ↓
Training stops
```

**Latency**: < 2.5s (poll interval + check)

**Phase 1**: Accept these are different, both work acceptably
**Phase 2**: Could explore token passing to host service

---

## Data Flow Diagrams (Phase 1)

### Local Execution Flow

```
API Request
  ↓
TrainingService.start_training()
  ↓
Check is_using_host_service() → False
  ↓
Create LocalTrainingOrchestrator(pipeline, bridge, token)
  ↓
asyncio.create_task(orchestrator.run())
  ↓
asyncio.to_thread(orchestrator._execute_training) ← Single async boundary
  ↓
[Worker Thread - Synchronous]
  For each step:
    ├─> Check cancellation token
    ├─> Report progress via bridge
    ├─> Call pipeline.step_method()
    └─> Return to async context
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
Check is_using_host_service() → True
  ↓
Create HostSessionManager
  ↓
POST /training/start to host service
  ↓
Host creates TrainingSession
  ↓
Host creates HostTrainingOrchestrator(pipeline, session)
  ↓
Host runs orchestrator.run() in background ← Already async, no to_thread
  ↓
Returns session_id to backend
  ↓
[Backend Polling Loop]
while not terminal:
  GET /training/status/{session_id} (every 2s)
  ↓
  Update operation status
  ↓
User polls /operations/{id}

[Meanwhile on Host Service - Direct Async]
HostTrainingOrchestrator.run():
  For each step:
    ├─> Check session.stop_requested
    ├─> Update session progress
    ├─> Call pipeline.step_method() ← Direct call, no threading
    └─> Continue async
```

---

## Design Decisions (Phase 1)

### Decision 1: Extract Pure Pipeline, Keep Orchestration Patterns

**Question**: How to eliminate duplication without breaking working systems?

**Decision**: Extract shared work into TrainingPipeline, preserve all orchestration patterns

**Rationale**:
- 80% duplication is in the work (data loading, indicators, fuzzy, training)
- Orchestration is only 20% and already works
- Phase 1 minimizes risk by changing only what's necessary

**What Changes**:
- Both orchestrators call same `TrainingPipeline` methods
- Zero code duplication

**What Stays**:
- Local: asyncio.to_thread wrapper, callback progress, token cancellation
- Host: Direct async, polling progress, HTTP cancellation
- Mode selection via env var at startup

### Decision 2: Centralize Device Management

**Question**: How to handle scattered device detection?

**Decision**: Create shared `DeviceManager` component

**Rationale**:
- Device detection is currently inconsistent
- MPS/CUDA/CPU have different capabilities
- Training should adapt to device limitations

**Benefit**: Single source of truth, used by both orchestrators

### Decision 3: Preserve All Async Patterns (Phase 1)

**Question**: Should we try to unify async patterns in Phase 1?

**Decision**: No - preserve current patterns

**Rationale**:
- Local uses `asyncio.to_thread()` - works fine
- Host uses direct async - works fine
- Unifying adds risk without clear benefit in Phase 1

**Phase 2**: Can explore harmonization after proving extraction works

### Decision 4: Preserve Cancellation Mechanisms (Phase 1)

**Question**: Should we try to unify cancellation in Phase 1?

**Decision**: No - preserve current mechanisms

**Rationale**:
- Local token-based cancellation works (< 50ms)
- Host HTTP-based cancellation works (< 2.5s)
- Latency acceptable for both

**Phase 2**: Can explore token passing if needed

### Decision 5: Keep Static Mode Selection (Phase 1)

**Question**: Should we add dynamic mode selection in Phase 1?

**Decision**: No - keep env var at startup

**Rationale**:
- Current system is reliable and predictable
- Dynamic selection adds complexity and failure modes
- Phase 1 goal is eliminate duplication, not add features

**Phase 2**: Can add health checks, fallback logic, dynamic selection

---

## Testing Strategy (Phase 1)

### Critical Property: Functional Equivalence

**Primary Goal**: Prove both orchestrators produce identical training results

**Why**: This validates that refactoring succeeded without changing behavior

### Unit Testing (TrainingPipeline)

**Objective**: Verify each pipeline method works correctly in isolation

**Approach**:
- Test each method independently with mocked dependencies
- Verify input/output contracts
- Test edge cases (empty data, invalid configs, missing symbols)

**Why This Matters**: Pipeline is shared - bugs here affect both execution modes

**Example Tests**:
- `test_load_price_data_returns_correct_structure()`
- `test_calculate_indicators_applies_all_configured_indicators()`
- `test_generate_fuzzy_memberships_handles_missing_data()`
- `test_combine_multi_symbol_data_preserves_sample_balance()`
- `test_split_data_respects_split_ratios()`

### Integration Testing (Orchestrators)

**Objective**: Verify coordination works correctly with real pipeline

**Approach**:
- Test with real `TrainingPipeline` instance (not mocked)
- Verify progress callbacks/updates are invoked correctly
- Test cancellation at various execution points
- Verify error propagation

**Why This Matters**: Ensures orchestration differences don't break training

**Example Tests**:
- `test_local_orchestrator_completes_full_training_flow()`
- `test_local_orchestrator_reports_progress_correctly()`
- `test_local_orchestrator_respects_cancellation_token()`
- `test_host_orchestrator_updates_session_state_correctly()`
- `test_host_orchestrator_respects_stop_requested_flag()`

### Equivalence Testing (Critical for Phase 1)

**Objective**: **PROVE** both orchestrators produce identical results

**Approach**:
- Run same training configuration through both orchestrators
- Compare final model weights (within numerical tolerance ~1e-5)
- Compare training metrics (loss, accuracy, etc.)
- Verify saved model files are structurally identical

**Why This Matters**: THIS IS THE PRIMARY VALIDATION THAT PHASE 1 SUCCEEDED

**Success Criteria**:
- Model weights within 0.001% difference
- Training metrics within 0.1% difference
- Model files load and predict identically

**Example Tests**:
- `test_local_and_host_produce_identical_model_weights()`
- `test_local_and_host_produce_identical_training_metrics()`
- `test_models_from_both_modes_predict_identically()`

### Device Detection Testing

**Objective**: Verify `DeviceManager` works correctly in all environments

**Approach**:
- Mock `torch.cuda.is_available()` and `torch.backends.mps.is_available()`
- Test each device path (CUDA, MPS, CPU)
- Verify capabilities set correctly for each device
- Test on actual hardware when possible

**Why This Matters**: Wrong device selection causes training failures

**Example Tests**:
- `test_device_manager_selects_cuda_when_available()`
- `test_device_manager_selects_mps_on_apple_silicon()`
- `test_device_manager_falls_back_to_cpu()`
- `test_mps_disables_mixed_precision()`
- `test_cuda_enables_all_features()`

### Performance Testing

**Objective**: Ensure refactoring doesn't add significant overhead

**Approach**:
- Benchmark training time before/after Phase 1
- Measure function call overhead (should be negligible)
- Profile hot paths if performance degrades

**Success Criteria**: < 2% overhead

**Why This Matters**: Training is already expensive, can't add significant cost

### End-to-End Testing

**Objective**: Verify complete user flows work

**Approach**:
- Test via API endpoints (simulate real usage)
- Verify progress updates reach CLI/UI correctly
- Test cancellation from user perspective
- Verify trained models load and work in backtesting

**Why This Matters**: Tests actual user experience, not just internal APIs

**Example Tests**:
- `test_api_train_via_local_returns_working_model()`
- `test_api_train_via_host_with_polling_completes()`
- `test_cli_cancel_local_training_stops_immediately()`
- `test_cli_cancel_host_training_stops_within_3s()`

---

## Phase 2 Improvements (Out of Scope for This Doc)

After Phase 1 is complete and proven stable, Phase 2 could explore:

1. **Async Harmonization**
   - Should host orchestrator wrap execution in `asyncio.to_thread()` like local?
   - Trade-offs: Code similarity vs. current working pattern

2. **Cancellation Unification**
   - Pass cancellation token ID to host service?
   - Host service polls backend for token status?
   - Trade-offs: Lower latency vs. added complexity

3. **Dynamic Mode Selection**
   - Health check host service before routing
   - Automatic fallback to local if host unavailable
   - Trade-offs: Reliability vs. complexity

4. **Progress Streaming**
   - WebSocket-based real-time progress from host?
   - Trade-offs: Real-time updates vs. infrastructure complexity

5. **Other Improvements**
   - Identified during Phase 1 implementation

---

## Risks and Mitigations (Phase 1)

### Risk 1: Extraction Introduces Bugs

**Risk**: Moving code from StrategyTrainer to TrainingPipeline changes behavior

**Likelihood**: Medium
**Impact**: High (broken training)

**Mitigation**:
- Extract methods one at a time
- Comprehensive equivalence testing after each extraction
- Keep old code working until equivalence proven
- Gradual rollout (local first, validate, then host)

### Risk 2: Device Detection Edge Cases

**Risk**: DeviceManager doesn't handle all hardware correctly

**Likelihood**: Medium
**Impact**: Medium (training uses wrong device or fails)

**Mitigation**:
- Test on all supported hardware (CUDA GPU, Apple Silicon, CPU)
- Provide manual override option
- Extensive logging of detection decisions
- Fallback to CPU on any detection error

### Risk 3: Progress/Cancellation Regressions

**Risk**: Refactoring breaks progress updates or cancellation

**Likelihood**: Low (we're preserving current patterns)
**Impact**: Medium (user confusion, not data loss)

**Mitigation**:
- Comprehensive testing of progress at each step
- Test cancellation at every pipeline stage
- Manual testing with real CLI/UI

### Risk 4: Performance Regression

**Risk**: Additional function call overhead slows training

**Likelihood**: Low
**Impact**: Low (training is hours, overhead is microseconds)

**Mitigation**:
- Benchmark before/after
- Accept < 2% overhead
- Profile only if overhead exceeds threshold

---

## Success Criteria (Phase 1)

Phase 1 is successful when:

1. ✅ **Zero Duplication**: No training logic exists in multiple places
2. ✅ **Functional Equivalence**: Both orchestrators produce identical results (proven by tests)
3. ✅ **Working Coordination**: Progress and cancellation work correctly in both modes
4. ✅ **All Tests Pass**: Unit, integration, equivalence, E2E tests all pass
5. ✅ **No Performance Regression**: Training time within 2% of current
6. ✅ **Behavioral Preservation**: All current behaviors maintained (async, cancellation, mode selection)

---

## Implementation Status (Phase 2 - Task 3.2)

**Date**: 2025-01-10

### Deprecated Code Removal

As part of Phase 2 Task 3.2, the following deprecated code has been removed:

1. **StrategyTrainer** (`ktrdr/training/train_strategy.py`) - DELETED
   - Replaced by: LocalTrainingOrchestrator and HostTrainingOrchestrator
   - Reason: Both orchestrators now use TrainingPipeline directly (zero duplication)

2. **MultiSymbolMLPTradingModel** and **MultiSymbolMLP** (`ktrdr/neural/models/mlp.py`) - DELETED
   - Reason: Contradicts symbol-agnostic architecture (Phase 2 TASK-2.0)
   - Architecture decision: Strategies operate on patterns, not symbol names
   - Multi-symbol training uses sequential concatenation, not embeddings
   - Uses regular MLPTradingModel (same as single-symbol)

3. **TrainingAdapter Local Training Code** (`ktrdr/training/training_adapter.py`) - DELETED
   - Lines removed: Local trainer initialization (82-92), local execution path (273-292)
   - Reason: Dead code bypassing orchestrators
   - TrainingAdapter is now HOST-SERVICE-ONLY
   - Local training uses LocalTrainingOrchestrator directly

4. **result_aggregator.py** - DEFERRED to Task 3.3
   - Will be deleted after host service harmonization (Task 3.3)
   - Reason: Host service will store and return TrainingPipeline result format directly
   - No transformation needed when both paths return same format

### Current Architecture

- **TrainingPipeline**: Single source of truth for training logic (shared by both orchestrators)
- **LocalTrainingOrchestrator**: Handles local training with in-process coordination
- **HostTrainingOrchestrator**: Handles host service training with session-based coordination
- **TrainingAdapter**: HOST-SERVICE-ONLY communication layer (no local training code)

### Symbol-Agnostic Design

Multi-symbol training follows symbol-agnostic principles:
- Strategies learn patterns from technical indicators and fuzzy memberships
- NO symbol names, indices, or embeddings in training
- Multi-symbol data concatenated sequentially (AAPL all → MSFT all → etc.)
- Temporal order preserved within each symbol
- Model uses regular MLPTradingModel (not MultiSymbolMLPTradingModel)
- Strategy can be trained on any symbols and used on any data

---

**Status**: Phase 2 Task 3.2 Complete - Deprecated Code Removed
**Next**: Phase 2 Task 3.3 - Host Service Result Harmonization
