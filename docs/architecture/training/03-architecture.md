# Training Service Unified Architecture

**Date**: 2025-01-05
**Status**: Design Approved
**Architect**: System Architect
**Previous**: [02-requirements.md](./02-requirements.md)
**Next**: Implementation Plan (TBD)

---

## Executive Summary

This architecture unifies the KTRDR training system into a single, coherent design that eliminates code duplication while supporting multiple execution environments. The core principle is **separation of concerns**: training logic, execution orchestration, and environment-specific adapters are cleanly separated into distinct architectural layers.

**Key Design Decisions**:
1. **Single Source of Truth**: All training logic consolidated into one reusable component
2. **Environment Agnostic Core**: Training logic independent of execution environment
3. **Flexible Orchestration**: Runtime selection of execution environment with intelligent fallback
4. **Asynchronous Result Transfer**: Host services post results back to primary backend
5. **Compression by Default**: All model transfers use gzip compression

---

## Architectural Principles

### 1. Separation of Concerns

The system is organized into three distinct layers:

```
┌─────────────────────────────────────────────────────────┐
│ Presentation Layer (API, CLI)                           │
│ - User-facing interfaces                                │
│ - Request validation and response formatting            │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ Orchestration Layer                                     │
│ - Execution mode selection                              │
│ - Progress tracking                                     │
│ - Operation lifecycle management                        │
│ - Environment routing                                   │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ Execution Layer                                         │
│ - Core training logic (environment-agnostic)            │
│ - Environment-specific adapters                         │
│ - Model persistence                                     │
└─────────────────────────────────────────────────────────┘
```

### 2. Single Responsibility

Each component has exactly one reason to change:

- **TrainingExecutor**: Changes when training algorithm changes
- **ExecutionModeSelector**: Changes when selection criteria change
- **TrainingAdapter**: Changes when communication protocol changes
- **ModelStorage**: Changes when persistence requirements change

### 3. Dependency Inversion

High-level orchestration does not depend on low-level execution details. All dependencies point inward through well-defined interfaces.

### 4. Open/Closed Principle

The system is open for extension (new execution modes) but closed for modification (existing modes don't change when adding new ones).

### 5. Separation of Concerns: Environment vs Hardware

**Critical Distinction**: The architecture separates two orthogonal concerns:

**Execution Environment** (Where code runs):
- Local (Docker container, CPU-only)
- Host Service (Native macOS, MPS-capable)
- Future: Cloud (Remote server, CUDA-capable)

**Hardware Environment** (What resources are available):
- CPU-only
- Apple Silicon (MPS)
- NVIDIA GPU (CUDA)

**Key Insight**: TrainingExecutor is agnostic to **execution environment** but aware of **hardware environment**.

```
┌─────────────────────────────────────────────────────┐
│ Execution Environment (Orchestration Concern)       │
│ - Local vs Host vs Cloud                            │
│ - HTTP vs In-process                                │
│ - Progress routing                                  │
│ - Result transfer                                   │
└─────────────────────────────────────────────────────┘
                      ▲
                      │ Orthogonal to
                      ▼
┌─────────────────────────────────────────────────────┐
│ Hardware Environment (Training Concern)             │
│ - PyTorch device detection                          │
│ - CPU vs GPU configuration                          │
│ - Memory management                                 │
│ - Batch size adaptation                             │
└─────────────────────────────────────────────────────┘
```

**Why This Matters**:
- Same TrainingExecutor code runs in ANY execution environment
- TrainingExecutor automatically uses BEST available hardware in EACH environment
- Docker (local) finds CPU → uses CPU
- Host Service finds MPS → uses MPS
- Cloud finds CUDA → uses CUDA
- **No conditional logic based on execution environment needed**

---

## System Architecture

### Conceptual Model

```
                    ┌─────────────────────┐
                    │   User Request      │
                    │  (API or CLI)       │
                    └──────────┬──────────┘
                               │
                               ↓
                    ┌─────────────────────┐
                    │  Training Service   │
                    │  (Orchestrator)     │
                    └──────────┬──────────┘
                               │
                   ┌───────────┴───────────┐
                   │                       │
                   ↓                       ↓
        ┌──────────────────┐    ┌──────────────────┐
        │ Execution Mode   │    │ Execution Mode   │
        │   Selector       │    │   Coordinator    │
        └────────┬─────────┘    └────────┬─────────┘
                 │                       │
        ┌────────┴─────────┐    ┌────────┴─────────┐
        ↓                  ↓    ↓                  ↓
   ┌─────────┐      ┌──────────┐      ┌──────────────┐
   │  Local  │      │   Host   │      │   Future:    │
   │  Runner │      │  Session │      │   Cloud/GPU  │
   └────┬────┘      └────┬─────┘      └──────────────┘
        │                │
        └────────┬───────┘
                 │
                 ↓
        ┌──────────────────┐
        │ Training Executor│
        │  (Core Logic)    │
        └────────┬─────────┘
                 │
                 ↓
        ┌──────────────────┐
        │  Model Storage   │
        │  (Persistence)   │
        └──────────────────┘
```

### Logical Architecture

#### Layer 1: Presentation (API/CLI)

**Responsibility**: Interface with external systems and users

**Components**:
- REST API endpoints (`/api/v1/trainings/*`)
- CLI commands (`ktrdr models train`)
- Request/response models (Pydantic schemas)

**Key Design**: Thin layer that delegates immediately to orchestration layer

#### Layer 2: Orchestration

**Responsibility**: Coordinate training operations across environments

**Components**:

1. **TrainingService** (ServiceOrchestrator)
   - Manages operation lifecycle
   - Coordinates with OperationsService
   - Handles background task execution

2. **ExecutionModeSelector**
   - Environment health checking
   - Mode selection logic
   - Fallback strategy

3. **ProgressCoordinator**
   - Unified progress tracking interface
   - Environment-specific progress handlers
   - Real-time status updates

**Key Design**: No direct knowledge of training algorithms or environment specifics

#### Layer 3: Execution

**Responsibility**: Execute training and manage environment-specific concerns

**Components**:

1. **TrainingExecutor** (Core)
   - Environment-agnostic training logic
   - Data loading, transformation, training, evaluation
   - Model creation and training loop
   - **Does NOT know about execution environment**

2. **LocalTrainingRunner** (Adapter)
   - Wraps TrainingExecutor for in-process execution
   - Manages async/sync boundary
   - Direct access to backend services

3. **HostSessionManager** (Adapter)
   - Wraps TrainingExecutor for remote execution
   - Manages HTTP communication
   - Handles result transfer

4. **ModelStorage** (Persistence)
   - Model versioning
   - Metadata management
   - File system abstraction

---

## Key Architectural Patterns

### Pattern 1: Strategy Pattern (Execution Modes)

**Problem**: Need to switch between different execution environments at runtime

**Solution**: Define a common interface for execution, implement different strategies

```
┌──────────────────────────────────────────────┐
│          TrainingRunner (Interface)          │
│  - async run() -> TrainingResult             │
└───────────────────┬──────────────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ↓                       ↓
┌──────────────┐        ┌──────────────┐
│LocalRunner   │        │HostSession   │
│              │        │  Manager     │
│- In-process  │        │- Remote HTTP │
│- Thread pool │        │- Polling     │
│- Direct save │        │- POST results│
└──────────────┘        └──────────────┘
```

**Benefit**: Add new execution modes without changing orchestration layer

### Pattern 2: Adapter Pattern (Environment Bridging)

**Problem**: TrainingExecutor is synchronous, API is async; environments differ

**Solution**: Adapters translate between executor and environment

**Local Adapter**:
- Async → Sync: Uses `asyncio.to_thread()`
- Progress: Direct OperationsService updates
- Results: Immediate return

**Host Adapter**:
- Async → HTTP: POST request, poll for status
- Progress: HTTP polling, local state updates
- Results: Callback POST to backend

### Pattern 3: Repository Pattern (Model Storage)

**Problem**: Decouple model persistence from business logic

**Solution**: ModelStorage acts as repository with consistent interface

**Responsibilities**:
- Abstract file system details
- Manage versioning strategy
- Provide query interface
- Handle metadata

### Pattern 4: Observer Pattern (Progress Tracking)

**Problem**: Multiple consumers need training progress updates

**Solution**: Callback-based progress notifications

```
TrainingExecutor
       │
       │ progress_callback(phase, message, **details)
       │
       ├─────────────┬─────────────┐
       │             │             │
       ↓             ↓             ↓
OperationsService  Session    Future: WebSocket
   (backend)       (host)        (real-time)
```

**Benefit**: Add new progress consumers without changing executor

### Pattern 5: Template Method Pattern (Training Pipeline)

**Problem**: Training has fixed steps but configurable implementations

**Solution**: TrainingExecutor defines pipeline structure, steps are pluggable

**Fixed Pipeline**:
1. Data loading
2. Indicator calculation
3. Fuzzy membership generation
4. Feature engineering
5. Label generation
6. Dataset preparation
7. Model creation
8. Training execution
9. Evaluation
10. Feature importance
11. Model persistence
12. Result aggregation

**Variable Implementations**: Each step uses injected components (DataManager, IndicatorEngine, etc.)

---

## Data Flow Architecture

### Local Execution Data Flow

```
User Request
    ↓
API validates request
    ↓
TrainingService.start_training()
    ↓
ExecutionModeSelector → "local"
    ↓
Create LocalTrainingRunner
    ↓
Queue background task
    ↓
Response to user (operation_id)


[Background Task]
    ↓
asyncio.to_thread(executor.execute)
    ↓
TrainingExecutor runs (sync)
    ├─ progress_callback → OperationsService
    ├─ Loads data, trains model
    └─ ModelStorage.save_model()
    ↓
Returns results
    ↓
OperationsService.complete_operation()
    ↓
User polls /operations/{id} → "completed"
```

**Characteristics**:
- Synchronous execution in thread pool
- Direct backend service access
- Immediate model persistence
- No network latency
- **Hardware**: Uses CPU (Docker cannot access MPS)

### Host Service Execution Data Flow

```
User Request
    ↓
API validates request
    ↓
TrainingService.start_training()
    ↓
ExecutionModeSelector → "host"
    ↓
Create HostSessionManager
    ↓
Queue background task
    ↓
Response to user (operation_id)


[Background Task]
    ↓
POST to host service /training/start
    (includes callback_url)
    ↓
Host service creates session
    ↓
Backend starts polling loop


[On Host Service]
    ↓
Start TrainingExecutor (sync)
    ├─ progress_callback → Session.update_progress()
    ├─ Loads data, trains model
    └─ Serialize model + compress (gzip)
    ↓
POST results to callback_url
    (retry with exponential backoff)


[Backend Receives Results]
    ↓
TrainingService.receive_training_results()
    ↓
Decompress + deserialize model
    ↓
ModelStorage.save_model()
    ↓
OperationsService.complete_operation()
    ↓
User polls /operations/{id} → "completed"
```

**Characteristics**:
- Asynchronous, distributed execution
- Network communication overhead
- **Hardware**: Uses MPS on Mac (native access to Metal)
- GPU acceleration capability
- Deferred model persistence
- Retry resilience

---

## Component Responsibilities

### TrainingExecutor

**Type**: Core Business Logic
**Lifecycle**: Created per training operation
**Dependencies**: DataManager, IndicatorEngine, FuzzyEngine, ModelTrainer, ModelStorage

**Responsibilities**:
- Execute complete training pipeline
- Coordinate data processing components
- **Detect and use available compute resources (CPU/GPU)**
- Report progress via callback
- Save trained models
- Aggregate results

**Environment Agnostic Means**:
- Does NOT know whether it's running in Docker container or host service (execution location)
- Does NOT know whether it was invoked via HTTP or in-process (invocation method)
- Does NOT handle communication with orchestration layer (HTTP, async boundaries)
- Does NOT manage operation lifecycle (OperationsService, session state)

**Hardware Aware Means**:
- DOES detect available hardware (CPU, MPS, CUDA)
- DOES configure PyTorch to use best available device
- DOES adapt training to available resources

**Why Synchronous**: Training is inherently sequential and compute-bound. Async adds complexity without benefit.

**GPU Detection Strategy**:
```
On initialization:
1. Check PyTorch backends (torch.backends.mps.is_available(), torch.cuda.is_available())
2. Select device: CUDA > MPS > CPU
3. Configure model and data loaders for selected device
4. Log selected device for observability
```

This is standard PyTorch practice - the same code works on CPU, MPS (Mac), or CUDA (Linux/Windows) without modification.

### ExecutionModeSelector

**Type**: Decision Component
**Lifecycle**: Singleton (one per TrainingService)
**Dependencies**: HTTP client (for health checks)

**Responsibilities**:
- Evaluate execution mode requests
- Check environment health/availability
- Apply fallback logic
- Manage default mode configuration

**Decision Criteria**:
- Requested mode (user preference)
- GPU requirements
- Host service availability
- System default configuration

**Output**: Concrete execution mode ("local" or "host")

### ModelStorage

**Type**: Repository
**Lifecycle**: Singleton
**Dependencies**: File system

**Responsibilities**:
- Version management (incremental versioning)
- Metadata persistence (config, metrics, features)
- Model serialization (PyTorch state dicts)
- Query interface (list, load, delete)
- Symlink management (latest version)

**Storage Structure**:
```
models/
└── {strategy_name}/
    ├── {symbol}_{timeframe}_v1/
    │   ├── model.pt
    │   ├── model_full.pt
    │   ├── config.json
    │   ├── metrics.json
    │   ├── features.json
    │   └── metadata.json
    ├── {symbol}_{timeframe}_v2/
    │   └── ...
    └── {symbol}_{timeframe}_latest → v2/
```

### ProgressCoordinator

**Type**: Mediator
**Lifecycle**: Created per operation
**Dependencies**: OperationsService (local) or TrainingSession (host)

**Responsibilities**:
- Provide unified callback interface to TrainingExecutor
- Route progress updates to appropriate destination
- Transform progress data to environment-specific format

**Implementation Variants**:

**Local Mode**:
- Directly updates OperationsService
- Synchronous, in-process communication
- Real-time progress available to API

**Host Mode**:
- Updates TrainingSession state
- Polled by backend via GET /status
- Eventual consistency

---

## Interface Contracts

### TrainingRunner Interface

**Purpose**: Abstraction for different execution environments

**Contract**:
- Input: Training configuration, symbols, timeframes, date range
- Output: Training results (model path, metrics, artifacts)
- Behavior: Execute training to completion or raise exception
- Guarantees: Model saved if execution succeeds

**Implementations**: LocalTrainingRunner, HostSessionManager, Future: CloudGPURunner

### ProgressCallback Interface

**Purpose**: Decouple progress reporting from training logic

**Contract**:
- Input: Phase name, message, optional structured details
- Output: None (fire-and-forget)
- Behavior: Report progress without blocking training
- Guarantees: Non-blocking, exception-safe

### ResultTransfer Interface

**Purpose**: Standardize model transfer from host services to backend

**Contract**:
- Protocol: HTTP POST with JSON payload
- Compression: Gzip (required)
- Encoding: Base64
- Retry: Exponential backoff (3 attempts)
- Response: Success confirmation with model_path

---

## Design Decisions

### Decision 1: Synchronous Training Core

**Question**: Should TrainingExecutor be async or sync?

**Decision**: Synchronous

**Rationale**:
- Training is CPU/GPU-bound, not I/O-bound
- Sequential pipeline with no concurrency within training
- Async adds complexity without performance benefit
- Wrapped by async adapters when needed (LocalTrainingRunner)

**Trade-offs**:
- ✅ Simpler code, easier to reason about
- ✅ Can run in thread pool or separate process
- ❌ Blocks thread during execution (mitigated by thread pool)

### Decision 2: Host Service Posts Results Back

**Question**: How should host service return trained models?

**Options Considered**:
- A) Backend polls and retrieves model when complete
- B) Host service posts results to backend callback
- C) Shared filesystem

**Decision**: Option B (callback POST)

**Rationale**:
- **Scalability**: Works with remote host services (future: cloud GPU)
- **Simplicity**: Host service controls when to send results
- **Reliability**: Retry logic handles transient failures
- **Separation**: Backend is source of truth for model storage

**Trade-offs**:
- ✅ Works remotely, not tied to localhost
- ✅ Clear ownership (backend stores, host executes)
- ✅ Retry resilience built-in
- ❌ Requires callback URL configuration
- ❌ HTTP payload size limits (mitigated by compression)

### Decision 3: Gzip Compression

**Question**: How to handle large model transfers?

**Decision**: Gzip compression (3-5x reduction)

**Rationale**:
- Simple, widely supported
- Effective compression ratio for PyTorch models
- Negligible CPU overhead compared to training time
- No special infrastructure needed

**Alternatives Considered**:
- Streaming: Complex, unclear benefit
- No compression: May hit HTTP limits
- Shared filesystem: Doesn't work remotely

### Decision 4: Execution Mode Selection Strategy

**Question**: How should system choose between local and host execution?

**Decision**: Three-tier selection with fallback

1. **Per-Request Override**: User can specify mode for each request
2. **System Default**: Configurable default (env var or API)
3. **Intelligent Auto**: Based on requirements and availability

**Auto Mode Logic**:
- If GPU required AND host available → "host"
- If GPU required AND host unavailable → ERROR
- If GPU not required → "local" (prefer local for faster startup)

**Fallback Logic**:
- If requested "host" AND host unavailable AND !require_gpu → WARN + fallback to "local"
- If requested "host" AND host unavailable AND require_gpu → ERROR

**Rationale**:
- **Flexibility**: Users control when needed
- **Simplicity**: Sensible defaults for common cases
- **Resilience**: Automatic fallback when possible
- **Transparency**: Always log selected mode

### Decision 5: Progress Tracking Separation

**Question**: Should progress updates and logging be unified?

**Decision**: Separate concerns

**Logging**:
- Purpose: Debugging, audit trail
- Destination: Log files
- Format: Structured, numbered steps
- Audience: Developers, operators

**Progress**:
- Purpose: User feedback, monitoring
- Destination: OperationsService or Session state
- Format: Phase + message + metrics
- Audience: End users, monitoring systems

**Rationale**: Different consumers, different requirements, different lifecycles

---

## Quality Attributes

### Performance

**Target**: Training throughput unaffected by architecture

**Strategy**:
- Training logic runs in native Python (no async overhead)
- No unnecessary data serialization until results transfer
- Thread pool for local execution (non-blocking API)
- GPU acceleration via host service when available

**Measurement**: Training time should be ≤ 5% slower than direct execution

### Scalability

**Horizontal**: Multiple host services can be registered (future)

**Vertical**: Training workload scales with hardware (GPU)

**Constraints**: Model size limited by HTTP payload (mitigated by compression)

### Reliability

**Failure Modes**:

1. **Host Service Down**:
   - Detection: Health check failure
   - Response: Fallback to local (if GPU not required)
   - Recovery: Automatic when service returns

2. **Network Failure During Result Transfer**:
   - Detection: HTTP timeout/error
   - Response: Exponential backoff retry (3 attempts)
   - Recovery: Results remain in session state for manual retrieval

3. **Training Failure**:
   - Detection: Exception in TrainingExecutor
   - Response: Mark operation as failed, preserve error details
   - Recovery: User retry with corrected configuration

**Availability Target**: 99.9% (excluding planned maintenance)

### Maintainability

**Code Duplication**: Eliminated (single TrainingExecutor)

**Change Impact**:
- Algorithm changes: Only TrainingExecutor
- New execution mode: Add new adapter, no core changes
- API changes: Only presentation layer
- Storage changes: Only ModelStorage

**Testing**:
- Unit tests: Each component independently
- Integration tests: Adapter + executor combinations
- E2E tests: Full flow local and host

### Security

**Trust Boundary**: Backend trusts host service (same deployment)

**Future Considerations** (when adding remote services):
- API key authentication for callback endpoint
- TLS for model transfer
- Input validation for all external data

---

## Future Extensibility

### Cloud GPU Integration

**Design Support**: Architecture already supports remote execution

**Required Changes**:
- New adapter: CloudGPUSessionManager
- Authentication/authorization
- Longer timeout values
- Cost tracking

**No Changes Needed**:
- TrainingExecutor (environment-agnostic)
- ModelStorage (same interface)
- API contracts (same endpoints)

### Real-time Progress Streaming

**Design Support**: Progress callback pattern allows multiple consumers

**Required Changes**:
- Add WebSocket endpoint
- New progress handler: WebSocketProgressPublisher
- Subscribe users to operation updates

**No Changes Needed**:
- TrainingExecutor (same callback)
- Existing polling mechanism (backward compatible)

### Multi-Model Training

**Design Support**: TrainingExecutor processes one strategy at a time

**Required Changes**:
- Batch orchestration layer
- Resource allocation
- Dependency management

**No Changes Needed**:
- TrainingExecutor (single responsibility)
- Execution mode selection

---

## Risks and Mitigations

### Risk 1: HTTP Payload Size Limits

**Risk**: Very large models may exceed HTTP limits even with compression

**Likelihood**: Low (gzip provides 3-5x compression)

**Impact**: High (training succeeds but results lost)

**Mitigation**:
- Primary: Gzip compression (implemented)
- Secondary: Chunked transfer encoding (if needed)
- Tertiary: Fallback to shared volume for large models (future)

**Monitoring**: Track compressed payload sizes, alert if approaching limits

### Risk 2: Host Service Unavailability

**Risk**: Host service down when GPU required

**Likelihood**: Medium (depends on infrastructure)

**Impact**: High (GPU training blocked)

**Mitigation**:
- Primary: Health check with fallback (implemented)
- Secondary: Multiple host services (future)
- Tertiary: Queue requests for retry (future)

**Monitoring**: Host service uptime, fallback frequency

### Risk 3: Model Corruption During Transfer

**Risk**: Network issues corrupt model during POST

**Likelihood**: Very Low (HTTP includes checksums)

**Impact**: High (model unusable)

**Mitigation**:
- Primary: HTTP transport reliability
- Secondary: Model validation on backend (load state dict before saving)
- Tertiary: Retry on deserialization failure

**Monitoring**: Deserialization error rate

---

## Appendix: Terminology

**Training Operation**: Complete workflow from user request to saved model

**Execution Mode**: Environment where training runs (local or host)

**Session**: Host service's internal tracking of a training operation

**Operation ID**: Backend's identifier for a training operation

**Callback URL**: Endpoint where host service sends results

**Progress Phase**: Logical step in training pipeline (e.g., "data_loading")

**Model Artifact**: Trained model plus metadata (config, metrics, features)

---

## Battle-Tested Code Preservation

### Principle

When refactoring working code, we follow the **Preserve-Then-Reorganize** principle:

1. **Map exactly how current code works** (signatures, flows, patterns, threading)
2. **Document the exact patterns** in this architecture document
3. **New code MUST preserve these patterns exactly**
4. **Only change: location, organization, naming**
5. **DO NOT change: signatures, logic, threading model, call patterns**

### Red Flags You're Violating This Principle

- Creating new wrappers/adapters around working code
- Changing signatures "for consistency"
- "Improving" working logic without understanding why it works
- Introducing abstraction layers that weren't there before
- Changing threading/async model without deep analysis

### Battle-Tested Patterns from StrategyTrainer

These patterns MUST be preserved in TrainingExecutor:

#### 1. Progress Callback Signature

**Pattern**: ModelTrainer callback uses `(epoch, total_epochs, metrics)` signature

**Why**: This signature is used throughout the training codebase, has proven stable, and supports both epoch and batch-level progress with rich metrics.

**Preservation Rule**: TrainingExecutor MUST pass callbacks through to ModelTrainer unchanged. Do not create adapter/wrapper functions that change the signature.

**Example**:
```python
# ✅ CORRECT - Pass through unchanged
trainer = ModelTrainer(
    training_config,
    progress_callback=self.progress_callback,  # Direct pass-through
    cancellation_token=self.cancellation_token,
)

# ❌ WRONG - Creating wrapper that changes signature
def wrapper_callback(epoch, total_epochs, metrics):
    self.progress_callback("training", f"Epoch {epoch}", epoch=epoch, ...)
trainer = ModelTrainer(training_config, progress_callback=wrapper_callback)
```

#### 2. Logging for Step Visibility

**Pattern**: StrategyTrainer used `print()` statements for pipeline steps

**Why**: Simple, worked reliably for developer visibility during execution

**Preservation Rule**: Replace `print()` with `logger.info()` for step logging. Progress callbacks are ONLY for ModelTrainer's epoch/batch updates, NOT for pipeline steps.

**Key Distinction**:

- **Logging** (`logger.info()`): Developer visibility, what step we're on, diagnostics
- **Progress callbacks**: Programmatic feature ONLY used by ModelTrainer for epoch/batch metrics

**Example**:
```python
# ✅ CORRECT - Logging for developer visibility
def _load_data(...):
    logger.info("Step 1: Loading market data for %s", symbols)  # Just logging
    data = load_market_data(symbols, timeframes, start_date, end_date)
    logger.info("Loaded %d rows of data", len(data))
    return data

def _train_model(...):
    logger.info("Step 7: Training neural network model")
    # ModelTrainer INTERNALLY uses progress_callback for epoch/batch updates
    trainer = ModelTrainer(
        training_config,
        progress_callback=self.progress_callback,  # ONLY ModelTrainer calls this
    )
    metrics = trainer.train(X_train, y_train, X_test, y_test)
    return metrics

# ❌ WRONG - Using progress callback for pipeline steps
def _load_data(...):
    self.progress_callback("data_loading", "Loading data", step=1)  # NO!
    # Progress callbacks are NOT for pipeline steps!
```

**Why This Matters**:

- Progress callbacks have specific signature: `(epoch, total_epochs, metrics)`
- They're for training loop progress (epochs, batches, loss/accuracy)
- Pipeline steps (loading data, calculating indicators) just need logging
- Mixing these concepts causes signature mismatches and confusion

#### 3. Direct Execution (No Threading in Executor)

**Pattern**: StrategyTrainer executes synchronously, caller handles threading

**Why**: Training logic should be simple sync code, async/threading is orchestration concern

**Preservation Rule**: TrainingExecutor.execute() is synchronous, host service uses `asyncio.to_thread()`

**Example**:
```python
# ✅ CORRECT - Executor is synchronous
class TrainingExecutor:
    def execute(self, symbols, timeframes, ...):  # Synchronous method
        # Direct calls, no async
        data = self._load_data(...)
        indicators = self._calculate_indicators(...)
        return results

# Host service handles threading
result = await asyncio.to_thread(executor.execute, ...)

# ❌ WRONG - Making executor async
class TrainingExecutor:
    async def execute(self, ...):  # Async adds complexity
        data = await self._load_data(...)  # All methods need to be async
```

---

## Critical Distinctions

### Progress vs Logging

**These are TWO SEPARATE CONCEPTS that must never be conflated:**

#### Progress (Programmatic Status Updates)

**Purpose**: Real-time UI updates for user feedback

**Mechanism**:
- `progress_callback(epoch, total_epochs, metrics)`
- Routes to Operations Service → Progress Renderer → CLI/UI
- Updates session state in host service

**Hierarchical Structure** (Steps / Epochs / Batches):

- **Step level**: Major pipeline phases (12 steps total)
  - Step 1: Loading market data
  - Step 2: Calculating technical indicators
  - Step 3: Generating fuzzy membership values
  - Step 4: Engineering features
  - Step 5: Generating labels
  - Step 6: Splitting train/test data
  - Step 7: Training neural network model
  - Step 8: Evaluating model performance
  - Step 9: Calculating feature importance
  - Step 10: Saving model
  - Step 11: Building results
  - Step 12: Complete

- **Epoch level** (within Step 7 only): Training iterations
  - Update once per epoch (~every 30 seconds)
  - Progress: current_epoch / total_epochs
  - Includes metrics: train_loss, train_accuracy, val_loss, val_accuracy

- **Batch level** (within each epoch of Step 7): Training batches
  - Adaptive throttling targeting ~300ms intervals
  - Progress: current_batch / total_batches_per_epoch
  - Includes metrics: batch_loss, batch_accuracy

**Frequency**:

- **Step updates**: 12 total (once per major phase)
- **Epoch updates**: Once per epoch (~every 30 seconds, only in Step 7)
- **Batch updates**: Adaptive throttling ~300ms intervals (only in Step 7)

**Implementation Pattern** (using GenericProgressManager):

```python
from ktrdr.async_infrastructure.progress import GenericProgressManager

# Initialize with 12 total steps
progress_manager = GenericProgressManager(
    operation_id=operation_id,
    total_steps=12,
    renderer=TrainingProgressRenderer(),
    callback=operations_service.send_progress_update,
)

# Step 1: Data loading
with progress_manager.step(1, "Loading market data"):
    data = self._load_data(symbols, timeframes, start_date, end_date)
    # progress_manager automatically reports step completion

# Step 2: Indicators
with progress_manager.step(2, "Calculating technical indicators"):
    indicators = self._calculate_indicators(data, strategy_config)

# Steps 3-6: Continue pattern...

# Step 7: Training (with nested epoch/batch progress)
with progress_manager.step(7, "Training neural network model"):
    # ModelTrainer internally calls progress_callback for epoch/batch updates
    trainer = ModelTrainer(
        training_config,
        progress_callback=self._create_training_callback(progress_manager),
        cancellation_token=self.cancellation_token,
    )
    metrics = trainer.train(X_train, y_train, X_test, y_test)

# Steps 8-12: Continue pattern...

def _create_training_callback(self, progress_manager):
    """Create callback that integrates ModelTrainer progress with step progress."""
    def callback(epoch: int, total_epochs: int, metrics: dict[str, float]):
        # This is called by ModelTrainer - preserve exact signature!
        # Report nested progress within Step 7
        progress_manager.update_step_progress(
            step_current=epoch,
            step_total=total_epochs,
            message=f"Epoch {epoch}/{total_epochs}",
            context={
                "epoch": epoch,
                "total_epochs": total_epochs,
                "metrics": metrics,
            },
        )
    return callback
```

**Content**: Structured data with metrics

```python
# Step-level progress
{
    "operation_id": "train-123",
    "current_step": 7,
    "total_steps": 12,
    "percentage": 58.3,  # Overall progress across all 12 steps
    "message": "Training neural network model",
    "context": {...},
}

# Epoch-level progress (nested within Step 7)
{
    "operation_id": "train-123",
    "current_step": 7,
    "total_steps": 12,
    "percentage": 58.3,  # Overall progress
    "step_percentage": 5.0,  # Progress within Step 7 (epoch 5/100)
    "message": "Training neural network model - Epoch 5/100",
    "context": {
        "epoch": 5,
        "total_epochs": 100,
        "train_loss": 0.234,
        "train_accuracy": 0.89,
        "val_loss": 0.245,
        "val_accuracy": 0.87,
    },
}

# Batch-level progress (nested within epoch within Step 7)
{
    "operation_id": "train-123",
    "current_step": 7,
    "total_steps": 12,
    "percentage": 58.3,  # Overall progress
    "step_percentage": 5.0,  # Progress within Step 7
    "batch_percentage": 30.0,  # Progress within current epoch (batch 30/100)
    "message": "Training neural network model - Epoch 5/100 - Batch 30/100",
    "context": {
        "epoch": 5,
        "total_epochs": 100,
        "batch": 30,
        "total_batches": 100,
        "batch_loss": 0.240,
        "batch_accuracy": 0.88,
    },
}
```

**Pattern Consistency with Data Loading**:

This hierarchical pattern mirrors the Data Loading progress structure:

| Component | Data Loading | Training |
|-----------|-------------|----------|
| **Level 1** | Steps (load, validate, repair) | Steps (12 pipeline phases) |
| **Level 2** | Segments (date ranges) | Epochs (training iterations) |
| **Level 3** | Items (individual bars) | Batches (training batches) |

**Example parallel**:
```python
# Data Loading: Steps / Segments / Items
progress_manager.step(1, "Loading data")
  → progress_manager.update_segment(segment=1, total_segments=10)
    → progress_manager.update_items(items_processed=1000, total_items=10000)

# Training: Steps / Epochs / Batches
progress_manager.step(7, "Training model")
  → progress_manager.update_step_progress(epoch=5, total_epochs=100)
    → (ModelTrainer internally reports batch progress via callback)
```

This consistency makes progress reporting predictable and intuitive across all KTRDR operations.

**Adaptive Throttling**:

- Start with 10-batch stride
- Measure time between updates
- If < 150ms → double stride (less frequent)
- If > 450ms → halve stride (more frequent)
- Target: ~300ms between progress updates

#### Logging (Developer/Admin Visibility)

**Purpose**: Debugging and operational monitoring

**Mechanism**:
- `logger.info()`, `logger.debug()`, `logger.warning()`
- Written to log files
- Viewed by developers/admins, not users

**Frequency**: Sparse - only significant events
- Pipeline step completion
- Epoch milestones (every 10th epoch)
- Errors and warnings
- Adaptive stride changes (debug level)

**Content**: Human-readable messages
```python
logger.info("Step 1: Loading market data for EURUSD")
logger.debug("Batch updates too fast (0.08s), increasing stride 10 → 20")
logger.warning("Training taking longer than expected")
```

**RULE**: Progress and logging are SEPARATE systems. Never use `logger.info()` for progress updates. Never use `progress_callback()` for logging.

---

## Threading and Async Model

### Critical: Event Loop Blocking Prevention

**Problem**: Training runs for hours and is CPU-bound. If executed directly in async context, it blocks the event loop.

**Impact**: No status checks, no cancellation, service appears hung

**Solution**: Host service MUST use `asyncio.to_thread()`

**Architecture**:
```
FastAPI Server (async event loop on main thread)
  ↓
BackgroundTasks.add_task(...)
  ↓
_run_training_session() (async function, runs in event loop)
  ↓
await asyncio.to_thread(executor.execute, ...)  ← CRITICAL
  ↓
executor.execute() (sync function, runs in thread pool thread)
  ↓
ModelTrainer.train() (sync, CPU-bound, runs for hours)
  ↓
progress_callback() (called from thread pool thread)
  ↓
session.update_progress() (thread-safe)
```

**Why asyncio.to_thread() is Safe**:
- ModelTrainer uses `DataLoader(num_workers=0)` (default)
- No subprocess spawning from thread
- No conflict with PyTorch multiprocessing

**Why NOT Using asyncio.to_thread() Fails**:
- Training blocks event loop for hours
- Status check requests timeout (cannot be processed)
- Cancellation requests ignored (cannot be processed)
- Service appears completely hung

### Thread Safety Requirements

**Components Called from Thread Pool**:
- `progress_callback()` - called from training thread
- `session.update_progress()` - must be thread-safe
- `session.stop_requested` - must be thread-safe read

**Thread Safety Guarantees**:
```python
# TrainingSession attributes accessed from training thread
class TrainingSession:
    stop_requested: bool  # Read from thread - must be atomic
    message: str  # Written from thread
    last_updated: datetime  # Written from thread

    def update_progress(self, epoch, batch, metrics):
        # Called from thread - must be thread-safe
        # Simple attribute assignment is atomic in Python
        self.epoch = epoch
        self.batch = batch
        self.last_updated = datetime.utcnow()
```

### Async/Sync Boundaries

**Boundary Map**:
```
Layer                   Context         Why
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
API Endpoints          async           FastAPI requirement
TrainingService        async           Orchestration, I/O-bound
LocalTrainingRunner    async           Orchestration
HostServiceAdapter     async           HTTP calls
─────────────────────────────────────────────────────
asyncio.to_thread()    ← BOUNDARY →
─────────────────────────────────────────────────────
TrainingExecutor       sync            CPU-bound, long-running
ModelTrainer           sync            PyTorch operations
DataManager.load_data  sync            I/O but blocking OK in thread
```

**Rule**: Everything above the boundary is async. Everything below is sync and runs in thread pool.

---

## Cancellation Architecture

### Latency Requirements

**Target**: < 100ms from user clicking "Cancel" to training stopping

**Why**: Users expect near-instant response to cancellation

### Cancellation Propagation

**Flow**:
```
User clicks Cancel (CLI/UI)
  ↓ < 10ms
POST /api/v1/operations/{id}/cancel
  ↓ < 10ms
OperationsService.cancel_operation()
  ↓ < 5ms
cancellation_token.cancel()
  ↓ < 5ms
TrainingService checks token (async polling)
  ↓ < 50ms
Host service session.stop_requested = True
  ↓ < 10ms (next batch iteration)
ModelTrainer._check_cancelled() raises CancellationError
  ↓ immediate
Training stops
```

**Total Latency**: ~90ms worst case

### Check Frequency

**Critical**: Cancellation MUST be checked frequently enough for < 100ms latency

**Check Points** (in order of frequency):
1. **Every batch** in ModelTrainer (~10-50ms intervals on GPU)
2. **Every epoch** in ModelTrainer
3. **Before progress callbacks** in ModelTrainer
4. **Between pipeline steps** in TrainingExecutor

**Implementation**:
```python
# ModelTrainer - checked EVERY batch
for batch_idx, (batch_X, batch_y) in enumerate(train_loader):
    self._check_cancelled()  # < 100ms guaranteed
    # Training operations
```

**Thread Safety**:
```python
class SessionCancellationToken:
    def is_cancelled(self) -> bool:
        return session.stop_requested  # Atomic read, thread-safe
```

---

## Interface Contracts

### TrainingExecutor.execute()

**Signature**:
```python
def execute(
    self,
    symbols: List[str],
    timeframes: List[str],
    start_date: str,
    end_date: str,
    validation_split: float = 0.2,
    data_mode: str = "local",
    **kwargs,
) -> dict[str, Any]:
```

**Context**: Synchronous, runs in thread pool (via asyncio.to_thread)

**Returns**:
```python
{
    "model_path": "models/strategy_name/EURUSD_5m_v1",
    "training_metrics": {
        "final_train_loss": 0.234,
        "final_train_accuracy": 0.89,
        ...
    },
    "test_metrics": {
        "accuracy": 0.87,
        "precision": 0.88,
        ...
    },
    "feature_importance": {...},
    "data_summary": {...}
}
```

**Preservation Rule**: This signature matches StrategyTrainer exactly. DO NOT CHANGE.

### Progress Callback

**Signature**:
```python
def progress_callback(epoch: int, total_epochs: int, metrics: dict) -> None:
```

**Called by**: ModelTrainer (from training thread)

**Call Frequency**:
- Epoch completion: ~every 30 seconds
- Batch progress: controlled by stride (adaptive, ~300ms intervals)

**Example Metrics Dict**:
```python
{
    "progress_type": "epoch",  # or "batch"
    "epoch": 5,
    "total_epochs": 100,
    "batch": 120,  # if batch update
    "total_batches_per_epoch": 500,
    "train_loss": 0.234,
    "train_accuracy": 0.89,
    "val_loss": 0.245,
    "val_accuracy": 0.87,
    "learning_rate": 0.001,
}
```

**Threading**: Called from thread pool thread, must be thread-safe

**Preservation Rule**: This is ModelTrainer's established signature. DO NOT create wrappers that change it.

### CancellationToken Protocol

**Required Methods**:
```python
class CancellationToken(Protocol):
    def is_cancelled(self) -> bool: ...
    def cancel(self, reason: str = "Operation cancelled") -> None: ...
    async def wait_for_cancellation(self) -> None: ...

    @property
    def is_cancelled_requested(self) -> bool: ...
```

**Implementation for Host Service**:
```python
class SessionCancellationToken:
    def is_cancelled(self) -> bool:
        return session.stop_requested  # Atomic, thread-safe

    def cancel(self, reason: str = "Operation cancelled") -> None:
        session.stop_requested = True

    async def wait_for_cancellation(self) -> None:
        while not session.stop_requested:
            await asyncio.sleep(0.1)

    @property
    def is_cancelled_requested(self) -> bool:
        return session.stop_requested
```

---

## Common Pitfalls

### 1. Event Loop Blocking

**Symptom**: Host service appears hung, status checks timeout

**Cause**: Running CPU-bound training directly in async function

**Solution**: Use `asyncio.to_thread(executor.execute, ...)`

**Detection**: Monitor request latency - if status checks timeout, event loop is blocked

### 2. Progress Callback Flooding

**Symptom**: Thousands of progress updates per second, log files fill up

**Cause**: Calling progress callback on every batch without throttling

**Solution**: Use adaptive stride (check time since last update, adjust frequency)

**Detection**: Monitor callback frequency - should be ~3-5 per second, not hundreds

### 3. Signature Mismatch

**Symptom**: TypeError about unexpected arguments

**Cause**: Creating wrappers that change callback signatures

**Solution**: Pass callbacks through unchanged from StrategyTrainer pattern

**Detection**: Stack traces showing signature mismatches in callback invocations

### 4. Progress vs Logging Conflation

**Symptom**: `logger.info()` calls for every batch, or missing UI progress updates

**Cause**: Using logging for progress or callbacks for logging

**Solution**: Keep them separate - logging for devs, callbacks for UI

**Detection**: Log files with excessive entries, or UI not updating

### 5. Cancellation Not Propagating

**Symptom**: Training continues after cancel request

**Cause**: Not passing cancellation token to TrainingExecutor/ModelTrainer

**Solution**: Create SessionCancellationToken and pass to executor

**Detection**: Monitor cancellation latency - should be < 100ms

### 6. Thread Safety Violations

**Symptom**: Race conditions, occasional crashes, inconsistent state

**Cause**: Modifying shared state from training thread without synchronization

**Solution**: Use thread-safe operations (atomic reads/writes, locks if needed)

**Detection**: Intermittent failures, especially under load

---

**Status**: Architecture Design Approved - Updated with Battle-Tested Patterns
**Next**: [Migration Strategy](./05-migration-strategy.md) | [Interface Contracts](./06-interface-contracts.md) | [Implementation Plan](./04-implementation-plan.md)
