# Training Service Architecture - Shared Pipeline, Separate Orchestration

**Date**: 2025-01-07
**Status**: Architecture Design
**Previous**: [02-requirements.md](./02-requirements.md)
**Next**: Implementation Plan (TBD)

---

## Executive Summary

This architecture eliminates code duplication in the KTRDR training system by extracting shared training logic into a reusable `TrainingPipeline` component, while keeping orchestration concerns (progress reporting, cancellation, async boundaries) separate and environment-specific.

**Core Principle**: Share the work, separate the coordination.

**Key Insight from Previous Failed Attempt**: We tried to unify orchestration (progress callbacks, cancellation tokens, async/sync boundaries) into a single flow. This failed because local and host service coordination are fundamentally different. The correct approach is to extract the **pure training logic** (identical) while keeping **orchestration** (different) separate.

**Key Design Decisions**:
1. **TrainingPipeline**: Pure, synchronous training logic - no callbacks, no cancellation checks
2. **DeviceManager**: Centralized GPU/device detection and configuration (shared by all)
3. **LocalTrainingOrchestrator**: Coordinates pipeline using callback-based progress + in-memory cancellation token
4. **HostTrainingOrchestrator**: Coordinates pipeline using session-based progress + HTTP cancellation flag
5. **Zero duplication**: Both orchestrators use the exact same training logic

---

## Problem Statement

### Current State

**Both execution paths work correctly today**:
- Local (Docker container): Training executes, saves models, reports progress
- Host Service (Native macOS): Training executes, saves models, reports progress

**The problem is code duplication**: ~80% of training logic exists in two places, leading to:
- Bugs fixed in one place but not the other
- Feature additions requiring duplicate work
- Divergent behavior over time
- Testing overhead

### Previous Failed Attempt

**What we tried**: Create a unified `TrainingExecutor` that works for both local and host execution with a single orchestration layer.

**Why it failed**:
1. **Progress mechanisms are fundamentally different**:
   - Local: Synchronous callback → immediate `GenericProgressManager` update
   - Host: Update session state → polled via HTTP

2. **Cancellation mechanisms are fundamentally different**:
   - Local: In-memory `CancellationToken` checked synchronously
   - Host: `session.stop_requested` flag set via HTTP, checked asynchronously

3. **Async boundaries are different**:
   - Local: `asyncio.to_thread()` wraps entire training execution
   - Host: Already running in async context

**Attempting to unify these created complexity without benefit.**

### The Right Approach

**Extract what's identical (the work), keep what's different (the coordination):**

```
❌ Previous Approach:
   One TrainingExecutor with unified orchestration
   → Failed because orchestration is fundamentally different

✅ New Approach:
   Shared TrainingPipeline (pure work functions)
   + Shared DeviceManager (GPU detection/config)
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
│ - asyncio.to_thread()  │  │ - asyncio.to_thread()  │
│   wraps entire run     │  │   per step (see note)  │
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
              │ Uses DeviceManager  │
              │ for GPU detection   │
              └─────────────────────┘
```

**Note on Host Service async boundaries**: Currently uses `asyncio.to_thread()` per step to allow cancellation checks between steps. Could be unified with local (entire run in thread) if we pass cancellation mechanism differently. **This is a design question to explore.**

### Key Components

1. **TrainingPipeline** (New - Shared)
   - Pure, synchronous work functions
   - No callbacks, no cancellation checks, no async
   - Used by both orchestrators

2. **DeviceManager** (New - Shared)
   - Centralized GPU/device detection (MPS, CUDA, CPU)
   - Configuration and capability checking
   - Used by all training code

3. **LocalTrainingOrchestrator** (Refactored from `LocalTrainingRunner`)
   - Uses `TrainingPipeline` for work
   - Manages local progress callbacks
   - Checks local cancellation token
   - Wraps execution in `asyncio.to_thread()`

4. **HostTrainingOrchestrator** (Refactored from `training_service._run_real_training`)
   - Uses `TrainingPipeline` for work
   - Updates session state for progress
   - Checks `session.stop_requested` for cancellation
   - **Design question**: Per-step vs entire-run threading

---

## Execution Mode Selection

### How Backend Decides Execution Mode

**Current Implementation** (at startup):
```python
# TrainingManager.__init__()
env_enabled = os.getenv("USE_TRAINING_HOST_SERVICE", "").lower()

if env_enabled in ("true", "1", "yes"):
    use_host_service = True
    host_service_url = os.getenv("TRAINING_HOST_SERVICE_URL", "http://localhost:5002")
else:
    use_host_service = False
```

**Flow**:
1. Environment variable `USE_TRAINING_HOST_SERVICE` read at TrainingManager initialization
2. TrainingAdapter created with `use_host_service` flag
3. TrainingService checks `is_using_host_service()` when building context
4. Context includes `use_host_service` flag
5. `_legacy_operation_entrypoint()` routes based on flag:
   - `True` → `_run_host_training()` → HostSessionManager
   - `False` → `_run_local_training()` → LocalTrainingRunner

**Characteristics**:
- **Static**: Set at process startup, cannot change without restart
- **Global**: All training requests use same mode
- **Simple**: No health checks or fallback logic

### How Host Service is Triggered

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
Host service runs _run_real_training() in background
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
- Backend **does** poll host service every 2 seconds (configurable via `poll_interval`)
- Poll interval has exponential backoff (2s → 3s → 4.5s up to max 10s)
- Polling continues until training reaches terminal state
- Progress updates retrieved from session state during each poll

---

## Device Detection and GPU Usage

### Problem: Inconsistent Device Management

Currently device detection is scattered:
- `LocalTrainingRunner`: Uses simple `torch.device("cuda" if torch.cuda.is_available() else "cpu")`
- Host service: Has complex MPS/CUDA detection with configuration
- No shared logic for device capabilities

### Solution: Centralized DeviceManager

**New Component**: `ktrdr/training/device_manager.py`

```python
@dataclass
class DeviceCapabilities:
    """Describes what a compute device can do."""
    device_type: str  # "cuda", "mps", "cpu"
    device: torch.device
    supports_mixed_precision: bool
    supports_memory_profiling: bool
    max_batch_size: int
    memory_available_gb: float

class DeviceManager:
    """Centralized device detection and configuration."""

    def detect_best_device(self) -> DeviceCapabilities:
        """Detect best available device and its capabilities.

        Priority: CUDA > MPS > CPU

        Returns capabilities for the selected device.
        """
        if torch.cuda.is_available():
            return self._configure_cuda()
        elif torch.backends.mps.is_available():
            return self._configure_mps()
        else:
            return self._configure_cpu()

    def _configure_cuda(self) -> DeviceCapabilities:
        """Configure CUDA device with full capabilities."""
        device = torch.device("cuda")
        memory_gb = torch.cuda.get_device_properties(0).total_memory / 1e9

        return DeviceCapabilities(
            device_type="cuda",
            device=device,
            supports_mixed_precision=True,
            supports_memory_profiling=True,
            max_batch_size=self._estimate_max_batch_size(memory_gb),
            memory_available_gb=memory_gb
        )

    def _configure_mps(self) -> DeviceCapabilities:
        """Configure Apple Silicon MPS with limited capabilities."""
        device = torch.device("mps")

        # MPS has limitations compared to CUDA
        return DeviceCapabilities(
            device_type="mps",
            device=device,
            supports_mixed_precision=False,  # Not reliable on MPS
            supports_memory_profiling=False,  # Not available on MPS
            max_batch_size=128,  # Conservative default
            memory_available_gb=0.0  # Can't query MPS memory reliably
        )

    def _configure_cpu(self) -> DeviceCapabilities:
        """Configure CPU fallback."""
        return DeviceCapabilities(
            device_type="cpu",
            device=torch.device("cpu"),
            supports_mixed_precision=False,
            supports_memory_profiling=False,
            max_batch_size=64,  # Small for CPU
            memory_available_gb=0.0
        )
```

**Usage in TrainingPipeline**:

```python
class TrainingPipeline:
    def __init__(self):
        self.device_manager = DeviceManager()
        self.device_capabilities = self.device_manager.detect_best_device()
        logger.info(
            "TrainingPipeline using device: %s (mixed_precision=%s)",
            self.device_capabilities.device_type,
            self.device_capabilities.supports_mixed_precision
        )

    def train_model(self, ...):
        # Use detected device
        trainer = ModelTrainer(
            device=self.device_capabilities.device,
            enable_mixed_precision=self.device_capabilities.supports_mixed_precision,
            ...
        )
```

**Benefits**:
- **Single source of truth** for device detection
- **Capability-aware**: Training adapts to device limitations
- **Consistent**: Same logic in local and host service
- **Testable**: Easy to mock device capabilities

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

**Key Methods** (signatures only, implementation in separate doc):

```python
class TrainingPipeline:
    def __init__(self):
        self.data_manager = DataManager()
        self.indicator_engine = IndicatorEngine()
        self.fuzzy_engine = None  # Initialized with config
        self.model_storage = ModelStorage()
        self.device_manager = DeviceManager()
        self.device_capabilities = self.device_manager.detect_best_device()

    def load_price_data(...) -> dict[str, dict[str, pd.DataFrame]]:
        """Load price data for all symbols and timeframes."""

    def calculate_indicators(...) -> dict[str, dict[str, pd.DataFrame]]:
        """Calculate technical indicators for all symbols."""

    def generate_fuzzy_memberships(...) -> dict[str, dict[str, pd.DataFrame]]:
        """Generate fuzzy memberships for all symbols."""

    def engineer_features(...) -> tuple[dict[str, np.ndarray], dict[str, list[str]]]:
        """Engineer features for all symbols."""

    def generate_labels(...) -> dict[str, np.ndarray]:
        """Generate training labels for all symbols."""

    def combine_multi_symbol_data(...) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Combine data from multiple symbols with balanced sampling."""

    def split_data(...) -> tuple[tuple, tuple, tuple]:
        """Split data into train/val/test sets."""

    def create_model(...) -> MLPTradingModel:
        """Create neural network model."""

    def train_model(
        self,
        model: MLPTradingModel,
        train_data: tuple,
        val_data: tuple,
        training_config: dict,
        progress_callback=None,
        cancellation_token=None
    ) -> dict[str, Any]:
        """Train the model.

        Note: This is the ONLY function that accepts callbacks/tokens,
        because ModelTrainer's interface requires them.

        Uses self.device_capabilities for device selection.
        """

    def evaluate_model(...) -> dict[str, float]:
        """Evaluate model on test set."""

    def save_model(...) -> str:
        """Save model to disk."""
```

**Key Characteristics**:
- Each function is **pure**: deterministic, no hidden state changes
- Returns data instead of mutating state
- Only `train_model()` accepts callbacks/tokens (ModelTrainer requires them)
- Uses `DeviceManager` for consistent device handling
- All other functions: pure transformations

---

### LocalTrainingOrchestrator (Refactored Component)

**Location**: `ktrdr/api/services/training/local_runner.py`

**Responsibility**: Coordinate training with local (in-process) progress/cancellation.

**Orchestration Pattern**:

```python
async def run(self) -> dict[str, Any]:
    """Execute training with local coordination."""
    # Wrap ENTIRE execution in thread pool
    return await asyncio.to_thread(self._execute_training)

def _execute_training(self) -> dict[str, Any]:
    """Synchronous orchestration of training steps."""

    # Pattern for each step:
    self._check_cancellation()  # Check token
    self._bridge.on_phase("step_name", message="...")  # Report progress
    result = self._pipeline.step_method(...)  # Do work

    # Training step passes callbacks through:
    training_results = self._pipeline.train_model(
        ...,
        progress_callback=self._create_training_callback(),
        cancellation_token=self._token
    )
```

**Key Characteristics**:
- **Single async boundary**: `asyncio.to_thread()` at top level
- **Synchronous execution**: All work in worker thread
- **Direct callbacks**: Progress updates immediate
- **Token-based cancellation**: Checks in-memory flag

---

### HostTrainingOrchestrator (Refactored Component)

**Location**: `training-host-service/orchestrator.py`

**Responsibility**: Coordinate training with host service (session-based) progress/cancellation.

**Current Orchestration Pattern** (per-step threading):

```python
async def run(self) -> dict[str, Any]:
    """Execute training with host service coordination."""

    # Each step:
    if self._check_stop_requested():
        return self._cancelled_result()

    self._update_progress(phase="step_name", message="...")

    # Run in thread pool
    result = await asyncio.to_thread(
        self._pipeline.step_method,
        ...
    )
```

**Alternative Pattern** (entire-run threading, like local):

```python
async def run(self) -> dict[str, Any]:
    """Execute training with host service coordination."""
    return await asyncio.to_thread(self._execute_training)

def _execute_training(self) -> dict[str, Any]:
    """Synchronous orchestration of training steps."""

    # Same pattern as local, but different coordination:
    if self._check_stop_requested():
        raise CancellationError()

    self._update_progress(...)
    result = self._pipeline.step_method(...)
```

**Design Question**: Which pattern is better?

**Per-step threading (current)**:
- ✅ Can check cancellation between async steps
- ✅ Host service remains responsive
- ❌ More complex async boundaries
- ❌ Different from local pattern

**Entire-run threading (alternative)**:
- ✅ Matches local pattern (simpler)
- ✅ Single async boundary
- ✅ Could use same cancellation mechanism as local
- ❌ Must ensure session.stop_requested check works from thread
- ❌ Slightly less responsive to cancellation

**Recommendation**: Explore unifying with local pattern if cancellation can be bridged.

---

## Progress Communication

### How Progress Works Today

#### Local Flow (Callback-Based)

```
ModelTrainer.train()
  └─> progress_callback(epoch, total_epochs, metrics)
      └─> LocalTrainingOrchestrator._create_training_callback()
          └─> TrainingProgressBridge.on_epoch()
              └─> GenericProgressManager.update()
                  └─> ProgressRenderer displays
```

**Characteristics**:
- **Direct**: Callback invoked synchronously from training loop
- **Immediate**: Updates appear instantly
- **Granularity**: Batch-level (throttled to ~300ms)

#### Host Flow (Polling-Based)

```
ModelTrainer.train()
  └─> progress_callback(epoch, total_epochs, metrics)
      └─> HostTrainingOrchestrator._create_training_callback()
          └─> session.update_progress(epoch, batch, metrics)
              └─> Updates TrainingSession state

[Separate async loop in backend]
HostSessionManager.poll_session() runs every 2s:
  └─> GET /training/status/{session_id}
      └─> Returns session.get_progress_dict()
          └─> TrainingProgressBridge.on_remote_snapshot()
              └─> GenericProgressManager.update()
                  └─> ProgressRenderer displays
```

**Characteristics**:
- **Indirect**: Progress polled, not pushed
- **Delayed**: Up to 2s latency (poll interval)
- **Granularity**: Same as local (batch-level), but delayed

### Why These Stay Different

**We accept these are fundamentally different mechanisms**:
- Local: Same process, can use direct callbacks
- Host: Different process, requires state + polling

**Both use same TrainingPipeline**, just route progress differently.

**Design question**: Could we use WebSockets for real-time progress? Out of scope for this refactoring.

---

## Cancellation Propagation

### How Cancellation Works Today

#### Local Flow (Token-Based)

```
User clicks Cancel (CLI/UI)
  ↓
POST /api/v1/operations/{id}/cancel
  ↓
OperationsService.cancel_operation()
  ↓
cancellation_token.cancel()  # Sets in-memory flag
  ↓
LocalTrainingOrchestrator._check_cancellation()
  ↓
Raises CancellationError
  ↓
Training stops
```

**Latency**: < 50ms (next cancellation check in loop)

#### Host Flow (HTTP-Based)

```
User clicks Cancel (CLI/UI)
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
session.stop_requested = True  # Host service flag
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

**Latency**: < 2.5s (poll interval + batch check)

### Design Question: Can We Unify Cancellation?

**Current approach**: Two separate mechanisms
- Local: CancellationToken (in-memory)
- Host: SessionCancellationToken (wraps session flag)

**Alternative**: Pass cancellation token to host service
- POST /training/start includes cancellation_token_id
- Host service polls backend for token status
- More complex, but potentially more responsive

**Recommendation**: Keep current approach for simplicity. Cancellation latency is acceptable.

---

## Data Flow Diagrams

### Local Execution Flow

```
API Request
  ↓
TrainingService.start_training()
  ↓
Check is_using_host_service() → False
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
  ├─> ...
  ├─> pipeline.train_model(
  │     device=pipeline.device_capabilities.device,
  │     progress_callback=local_callback,
  │     cancellation_token=token
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
Check is_using_host_service() → True
  ↓
Create HostSessionManager
  ↓
HostSessionManager.start_session()
  ↓
POST /training/start to host service
  ↓
Host service creates TrainingSession
  ↓
Host service creates HostTrainingOrchestrator
  ↓
Host service runs orchestrator.run() in background
  ↓
Returns session_id to backend
  ↓
[Backend Polling Loop]
while not terminal:
  GET /training/status/{session_id} (every 2s)
  ↓
  session.get_progress_dict()
  ↓
  TrainingProgressBridge.on_remote_snapshot()
  ↓
  Update operation status
  ↓
User polls /operations/{id}

[Meanwhile on Host Service]
HostTrainingOrchestrator.run():
  ├─> Check session.stop_requested
  ├─> session.update_progress("data_loading")
  ├─> asyncio.to_thread(pipeline.load_price_data)  [or entire run]
  ├─> ...
  ├─> pipeline.train_model(
  │     device=pipeline.device_capabilities.device,
  │     progress_callback=session_callback,
  │     cancellation_token=SessionCancellationToken(session)
  │   )
  ├─> pipeline.save_model()
  └─> session.status = "completed"
```

---

## Design Decisions

### Decision 1: Extract Pure Pipeline, Not Unified Orchestrator

**Question**: How do we eliminate duplication while supporting different coordination?

**Decision**: Extract pure TrainingPipeline, keep orchestration separate

**Rationale**:
- Previous attempt to unify orchestration failed - they're fundamentally different
- Progress/cancellation ARE different, don't force unification
- 80% duplication is in the work, not coordination

**Trade-offs**:
- ✅ Eliminates duplication in training logic
- ✅ Preserves working behavior
- ✅ Clear separation of concerns
- ⚠️ Two orchestrators (but they're simple and different by nature)

### Decision 2: Centralize Device Management

**Question**: How do we handle GPU detection consistently?

**Decision**: Create shared DeviceManager component

**Rationale**:
- Device detection logic is scattered and inconsistent
- MPS has different capabilities than CUDA
- Training should adapt to device capabilities

**Trade-offs**:
- ✅ Single source of truth
- ✅ Capability-aware training
- ✅ Easier to test
- ✅ Same logic everywhere

### Decision 3: Keep Execution Mode Selection Simple

**Question**: Should we add health checks and fallback logic?

**Decision**: Keep current env-var-based selection for now

**Rationale**:
- Current system works reliably
- Adding complexity requires careful design
- Can enhance later without changing architecture

**Trade-offs**:
- ✅ Simple and predictable
- ✅ No runtime complexity
- ❌ No automatic fallback
- ❌ Requires restart to change mode

### Decision 4: Accept Different Progress Mechanisms

**Question**: Should we try to unify progress reporting?

**Decision**: No - accept they're different

**Rationale**:
- Local can use direct callbacks (same process)
- Host must use polling (different process)
- Both mechanisms work well for their context

**Trade-offs**:
- ✅ Each uses optimal mechanism
- ✅ No artificial abstraction
- ⚠️ Different latency characteristics (documented)

---

## Testing Strategy

### What We're Testing

The testing strategy validates three critical properties:

1. **Functional Equivalence**: Both orchestrators produce identical training results
2. **Coordination Correctness**: Progress and cancellation work in each environment
3. **Integration Stability**: End-to-end flows work as expected

### Unit Testing (TrainingPipeline)

**Objective**: Verify each pipeline step works correctly in isolation

**Approach**:
- Test each method independently with mocked dependencies
- Verify input/output contracts
- Test edge cases (empty data, invalid configs)

**Example Coverage**:
```python
test_load_price_data_success()
test_load_price_data_missing_symbol()
test_calculate_indicators_with_config()
test_generate_fuzzy_memberships_empty_data()
test_combine_multi_symbol_data_balanced_sampling()
```

**Why This Matters**: Pipeline is shared by both orchestrators - bugs here affect everything.

### Integration Testing (Orchestrators)

**Objective**: Verify coordination logic works correctly with real pipeline

**Approach**:
- Test with real TrainingPipeline instance
- Verify progress callbacks are invoked correctly
- Test cancellation at various points in execution
- Compare local vs host results for equivalence

**Example Coverage**:
```python
test_local_orchestrator_full_training_flow()
test_local_orchestrator_progress_updates()
test_local_orchestrator_cancellation_before_training()
test_local_orchestrator_cancellation_during_training()

test_host_orchestrator_session_management()
test_host_orchestrator_progress_polling()
test_host_orchestrator_http_cancellation()
```

**Why This Matters**: Ensures coordination differences don't break training.

### Equivalence Testing

**Objective**: Prove both paths produce identical results

**Approach**:
- Run same training job through local and host orchestrators
- Compare final model weights (within numerical tolerance)
- Compare training metrics (loss, accuracy)
- Verify saved model artifacts are identical

**Example Coverage**:
```python
test_local_and_host_produce_same_model_weights()
test_local_and_host_produce_same_metrics()
test_local_and_host_save_identical_artifacts()
```

**Why This Matters**: This is the PRIMARY validation that refactoring succeeded.

### End-to-End Testing

**Objective**: Verify complete user flows work

**Approach**:
- Test via API endpoints (not internal components)
- Verify progress updates reach UI correctly
- Test cancellation from user perspective
- Verify model can be loaded and used

**Example Coverage**:
```python
test_api_train_via_local_complete_flow()
test_api_train_via_host_with_polling()
test_api_cancel_local_training()
test_api_cancel_host_training()
test_trained_model_loads_and_predicts()
```

**Why This Matters**: Tests what users actually experience.

### Device Detection Testing

**Objective**: Verify DeviceManager works correctly in all environments

**Approach**:
- Mock torch.cuda/backends.mps availability
- Verify correct device selected
- Verify capabilities set correctly for each device type
- Test on actual hardware where possible

**Example Coverage**:
```python
test_device_manager_selects_cuda_when_available()
test_device_manager_selects_mps_on_mac()
test_device_manager_falls_back_to_cpu()
test_mps_capabilities_disable_mixed_precision()
test_cuda_capabilities_enable_all_features()
```

**Why This Matters**: Device misdetection can cause training failures or suboptimal performance.

### Performance Testing

**Objective**: Ensure refactoring doesn't degrade performance

**Approach**:
- Benchmark training time before/after refactoring
- Measure function call overhead
- Profile hot paths
- Accept < 2% overhead from architecture

**Why This Matters**: Training is expensive - we can't add significant overhead.

### Testing Philosophy

**Key Principles**:
1. **Test behavior, not implementation**: Focus on what the system does, not how
2. **Test at appropriate level**: Unit for logic, integration for coordination, E2E for flows
3. **Equivalence is critical**: Both paths must produce identical results
4. **Real hardware matters**: Mock for unit tests, use real GPU/CPU for integration tests

**What We Don't Test**:
- Internal implementation details of existing components (already tested)
- Exact log messages (too brittle)
- Performance micro-optimizations (premature)

---

## Open Design Questions

These questions should be resolved during implementation:

### 1. Host Service Async Boundaries

**Question**: Should host orchestrator use per-step `asyncio.to_thread()` or wrap entire execution like local?

**Current**: Per-step threading
**Alternative**: Entire-run threading (matches local)

**Trade-offs to consider**:
- Responsiveness to cancellation
- Code similarity between orchestrators
- Complexity of cancellation mechanism

### 2. Cancellation Token Passing

**Question**: Can we pass cancellation token from backend to host service for more direct cancellation?

**Current**: Separate mechanisms (token vs session flag)
**Alternative**: Token ID passed in request, host polls backend

**Trade-offs to consider**:
- Latency improvement
- Added complexity
- Network dependency

### 3. Progress Streaming

**Question**: Should we explore WebSocket-based progress streaming from host service?

**Current**: HTTP polling every 2s
**Alternative**: WebSocket real-time updates

**Trade-offs to consider**:
- Real-time vs eventual progress
- Infrastructure complexity
- Backward compatibility

### 4. Execution Mode Selection

**Question**: Should we add health checking and automatic fallback?

**Current**: Static env var at startup
**Alternative**: Dynamic health-checked selection with fallback

**Trade-offs to consider**:
- Reliability vs complexity
- Predictability vs flexibility
- Testing overhead

---

## Risks and Mitigations

### Risk 1: Extraction Introduces Bugs

**Risk**: Moving code from StrategyTrainer to TrainingPipeline changes behavior

**Likelihood**: Medium
**Impact**: High (broken training)

**Mitigation**:
- Extract methods one at a time with tests
- Run equivalence tests after each extraction
- Keep StrategyTrainer working until pipeline validated
- Gradual rollout (local first, then host)

### Risk 2: Device Detection Edge Cases

**Risk**: DeviceManager doesn't handle all hardware configurations correctly

**Likelihood**: Medium
**Impact**: Medium (training fails or uses wrong device)

**Mitigation**:
- Test on all supported hardware (CUDA, MPS, CPU)
- Provide manual override for device selection
- Extensive logging of device detection decisions
- Fallback to CPU on any detection error

### Risk 3: Progress/Cancellation Edge Cases

**Risk**: Subtle differences in coordination cause confusing behavior

**Likelihood**: Medium
**Impact**: Medium (user confusion, not data loss)

**Mitigation**:
- Extensive testing of progress updates at each step
- Test cancellation at every pipeline stage
- Manual testing with real UI/CLI
- Clear documentation of latency differences

### Risk 4: Performance Regression

**Risk**: Additional abstraction layers slow down training

**Likelihood**: Low
**Impact**: Low (training is hours, overhead is microseconds)

**Mitigation**:
- Benchmark before/after migration
- Profile hot paths
- Accept < 2% overhead as acceptable
- Optimize only if overhead exceeds threshold

---

## Success Criteria

This architecture is successful when:

1. **Zero Duplication**: No training logic exists in multiple places
2. **Functional Equivalence**: Both orchestrators produce identical results (proven by tests)
3. **Working Coordination**: Progress and cancellation work correctly in both modes
4. **Maintainability**: Future changes only touch one place (pipeline or specific orchestrator)
5. **Device Consistency**: GPU detection and usage is consistent across all code
6. **Test Coverage**: Comprehensive tests validate correctness and equivalence
7. **No Performance Regression**: Training time within 2% of current implementation

---

**Status**: Architecture Design Approved
**Next**: Implementation Plan (separate document)
