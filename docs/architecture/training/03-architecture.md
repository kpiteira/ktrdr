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

**Status**: Architecture Design Approved
**Next**: Implementation Plan (Separate Document)
