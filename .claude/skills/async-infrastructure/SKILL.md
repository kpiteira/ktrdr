---
name: async-infrastructure
description: Use when working on ServiceOrchestrator, operation tracking, progress reporting, cancellation tokens, worker infrastructure, or async service adapters.
---

# Async Infrastructure

**When this skill is loaded, announce it to the user by outputting:**
`🛠️✅ SKILL async-infrastructure loaded!`

Load this skill when working on:

- ServiceOrchestrator base class or subclasses
- Operation lifecycle (create, start, complete, fail, cancel)
- Progress tracking (GenericProgressManager, bridges, renderers)
- Cancellation tokens and coordination
- Worker infrastructure (WorkerAPIBase, WorkerRegistry)
- OperationServiceProxy (backend-to-worker communication)
- Async service adapters (HTTP clients to host services)

---

## Architecture Overview

```
CLI (OperationRunner)
    │ POST /api/v1/{type}/start
    ▼
Backend Service (extends ServiceOrchestrator)
    ├─ Creates operation (OperationsService)
    ├─ Selects worker (WorkerRegistry)
    ├─ Dispatches via HTTP to worker
    └─ Creates OperationServiceProxy for status polling
    │
    ▼ POST {worker_url}/{type}/start
    │
Worker (extends WorkerAPIBase)
    ├─ Creates local operation
    ├─ Registers ProgressBridge
    ├─ Executes task in thread pool
    └─ Reports progress via bridge
    │
    ▼ CLI polls backend → backend polls worker via proxy
    │
CLI ProgressDisplay ← ProgressRenderer ← GenericProgressManager
```

---

## Key Files

| File | Purpose |
|------|---------|
| `ktrdr/async_infrastructure/service_orchestrator.py` | ServiceOrchestrator base class |
| `ktrdr/async_infrastructure/progress.py` | GenericProgressManager, GenericProgressState, ProgressRenderer |
| `ktrdr/async_infrastructure/cancellation.py` | CancellationToken, AsyncCancellationToken, CancellationCoordinator |
| `ktrdr/async_infrastructure/progress_bridge.py` | ProgressBridge (pull-based local progress) |
| `ktrdr/async_infrastructure/service_adapter.py` | AsyncServiceAdapter base for HTTP clients |
| `ktrdr/async_infrastructure/async_host_service.py` | Host service communication |
| `ktrdr/async_infrastructure/time_estimation.py` | TimeEstimationEngine for progress |
| `ktrdr/api/services/operations_service.py` | OperationsService (operation CRUD + lifecycle) |
| `ktrdr/api/models/operations.py` | OperationInfo, OperationStatus, OperationType, OperationProgress |
| `ktrdr/api/repositories/operations_repository.py` | Database persistence for operations |
| `ktrdr/api/services/adapters/operation_service_proxy.py` | OperationServiceProxy (HTTP bridge) |
| `ktrdr/workers/base.py` | WorkerAPIBase (shared worker foundation) |
| `ktrdr/api/services/worker_registry.py` | WorkerRegistry (discovery + health) |
| `ktrdr/api/models/workers.py` | WorkerEndpoint, WorkerStatus, WorkerType |
| `ktrdr/cli/operation_runner.py` | CLI operation execution and tracking |
| `ktrdr/cli/progress_display_enhanced.py` | CLI progress display |
| `ktrdr/api/endpoints/operations.py` | Operation query/management endpoints |
| `ktrdr/api/endpoints/workers.py` | Worker registration/health endpoints |

---

## ServiceOrchestrator

**Location:** `ktrdr/async_infrastructure/service_orchestrator.py`

Base class for all service managers. Generic over adapter type `T`.

### Abstract Methods

Subclasses must implement:

```python
_initialize_adapter() -> T              # Create adapter (IbDataProvider, None, etc.)
_get_service_name() -> str              # Human-readable name ("Data/IB", "Training")
_get_default_host_url() -> str          # Default host service URL
_get_env_var_prefix() -> str            # Env var prefix ("IB", "TRAINING", etc.)
```

### Subclass Implementations

| Subclass | Generic Type | Location |
|----------|-------------|----------|
| `DataAcquisitionService` | `ServiceOrchestrator[IbDataProvider]` | `ktrdr/data/acquisition/acquisition_service.py` |
| `TrainingService` | `ServiceOrchestrator[None]` | `ktrdr/api/services/training_service.py` |
| `BacktestingService` | `ServiceOrchestrator[None]` | `ktrdr/backtesting/backtesting_service.py` |

### Key Methods

**Configuration:**

```python
is_using_host_service() -> bool
get_host_service_url() -> Optional[str]
get_configuration_info() -> dict[str, Any]
async health_check() -> dict[str, Any]
```

**Managed Operations:**

```python
async start_managed_operation(
    operation_name: str,
    operation_type: str,
    operation_func: Callable,
    *args, **kwargs
) -> dict[str, Any]  # Returns {operation_id, status, message}

def update_operation_progress(
    step: Optional[int] = None,
    message: Optional[str] = None,
    items_processed: Optional[int] = None,
    **kwargs
) -> None
```

**Execution Helpers:**

```python
async execute_with_progress(
    operation: Awaitable[T],
    progress_callback: Optional[ProgressCallback] = None,
    timeout: Optional[float] = None,
    operation_name: str = "operation",
    total_steps: int = 0
) -> T

async execute_with_cancellation(
    operation: Awaitable[T],
    cancellation_token: Optional[CancellationToken] = None,
    check_interval: float = 0.1,
    operation_name: str = "operation"
) -> T

async retry_with_backoff(
    operation: Callable[[], Awaitable[T]],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_factor: float = 2.0
) -> T
```

---

## Operations Service

**Location:** `ktrdr/api/services/operations_service.py`

Singleton service for operation lifecycle management.

### Operation Status Enum

```python
class OperationStatus(str, Enum):
    PENDING = "pending"
    RESUMING = "resuming"      # Checkpoint loaded, worker starting
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

### Operation Type Enum

```python
class OperationType(str, Enum):
    DATA_LOAD = "data_load"
    TRAINING = "training"
    BACKTESTING = "backtesting"
    INDICATOR_COMPUTE = "indicator_compute"
    FUZZY_ANALYSIS = "fuzzy_analysis"
    DUMMY = "dummy"
    AGENT_RESEARCH = "agent_research"
    AGENT_DESIGN = "agent_design"
    AGENT_ASSESSMENT = "agent_assessment"
```

### Core Methods

```python
# Creation
async create_operation(
    operation_type: OperationType,
    metadata: OperationMetadata,
    operation_id: Optional[str] = None,
    parent_operation_id: Optional[str] = None,
    is_backend_local: bool = False
) -> OperationInfo

# Lifecycle
async start_operation(operation_id: str, task: Optional[asyncio.Task] = None) -> None
async complete_operation(operation_id: str, result_summary: Optional[dict] = None) -> None
async fail_operation(operation_id: str, error_message: str, fail_parent: bool = False) -> None
async cancel_operation(operation_id: str, reason: Optional[str] = None, force: bool = False) -> dict

# Progress (LOCK-FREE for performance)
async update_progress(
    operation_id: str,
    progress: OperationProgress,
    warnings: Optional[list[str]] = None,
    errors: Optional[list[str]] = None
) -> None

# Resume
async try_resume(operation_id: str) -> bool  # Atomic DB-level update
async adopt_operation(operation_id: str) -> OperationInfo

# Querying
async get_operation(operation_id: str, force_refresh: bool = False) -> Optional[OperationInfo]
async list_operations(
    status: Optional[OperationStatus] = None,
    operation_type: Optional[OperationType] = None,
    limit: int = 100,
    offset: int = 0,
    active_only: bool = False
) -> tuple[list[OperationInfo], int, int]  # (operations, total, active)

# Metrics (cursor-based incremental reads)
async get_operation_metrics(operation_id: str, cursor: int = 0) -> tuple[list[dict], int]
async add_operation_metrics(operation_id: str, metrics_data: dict) -> None

# Parent-child operations
async get_children(parent_operation_id: str) -> list[OperationInfo]
async get_aggregated_progress(parent_operation_id: str) -> OperationProgress
```

### OperationServiceProxy

**Location:** `ktrdr/api/services/adapters/operation_service_proxy.py`

HTTP client that bridges backend to worker/host service operations:

```python
class OperationServiceProxy:
    async get_operation(operation_id: str, force_refresh: bool = False) -> dict
    async get_metrics(operation_id: str, cursor: int = 0) -> tuple[list, int]
    async cancel_operation(operation_id: str, reason: Optional[str] = None) -> dict
    async close()
```

**Pattern:** Backend creates proxy when dispatching to worker. CLI polls backend, backend polls worker via proxy, transparent to the caller.

---

## Progress Tracking

### GenericProgressManager

**Location:** `ktrdr/async_infrastructure/progress.py`

Thread-safe (RLock) progress tracking with hierarchical step support.

```python
class GenericProgressManager:
    def __init__(self, callback=None, renderer=None)

    def start_operation(operation_id: str, total_steps: int, context=None) -> None

    def start_step(
        step_name: str,
        step_number: int,
        step_percentage: Optional[float] = None,      # Start of percentage range
        step_end_percentage: Optional[float] = None,   # End of percentage range
        expected_items: Optional[int] = None
    ) -> None

    def update_step_progress(
        current: int, total: int,
        items_processed: int = 0,
        detail: str = ""
    ) -> None

    def update_progress(step: int, message=None, items_processed=0, context=None) -> None
    def complete_operation() -> None
```

**Hierarchical Progress:** Supports step-specific percentage ranges. Example: Step 6 occupies 10%-96% of total progress, with sub-progress calculated within that range.

### GenericProgressState

```python
@dataclass
class GenericProgressState:
    operation_id: str
    current_step: int
    total_steps: int
    percentage: float
    message: str
    start_time: datetime
    context: dict[str, Any]         # Domain-specific data
    estimated_remaining: Optional[timedelta]
    items_processed: int
    total_items: Optional[int]
    step_start_percentage: float    # For hierarchical progress
    step_end_percentage: float
    step_current: int
    step_total: int
```

### ProgressRenderer

```python
class ProgressRenderer(ABC):
    @abstractmethod
    def render_message(self, state: GenericProgressState) -> str
    @abstractmethod
    def enhance_state(self, state: GenericProgressState) -> GenericProgressState
```

**Domain-specific implementations:**
- `TrainingProgressRenderer` at `ktrdr/api/services/training/training_progress_renderer.py`
- `DataProgressRenderer` at `ktrdr/data/async_infrastructure/data_progress_renderer.py`

### ProgressBridge

**Location:** `ktrdr/async_infrastructure/progress_bridge.py`

Thread-safe, synchronous pull interface for workers:

```python
class ProgressBridge:
    def get_status() -> dict[str, Any]           # Current state snapshot
    def get_metrics(cursor: int = 0) -> tuple[list[dict], int]  # Incremental metrics

    # Protected helpers (called by subclasses)
    def _update_state(percentage: float, message: str, **kwargs) -> None
    def _append_metric(metric: dict) -> None
```

**Usage:** Workers write via `_update_state()`/`_append_metric()`. OperationsService reads via `get_status()`/`get_metrics()` with cursor-based incremental reads.

---

## Cancellation System

**Location:** `ktrdr/async_infrastructure/cancellation.py`

### CancellationToken Protocol

```python
class CancellationToken(Protocol):
    def is_cancelled() -> bool
    def cancel(reason: str = "Operation cancelled") -> None
    async def wait_for_cancellation() -> None
    @property
    def is_cancelled_requested() -> bool
```

### AsyncCancellationToken

Thread-safe implementation:

```python
class AsyncCancellationToken:
    def __init__(self, operation_id: str)
    def is_cancelled() -> bool
    def cancel(reason: str) -> None
    async def wait_for_cancellation() -> None
    def check_cancellation(context: str = "") -> None  # Raises CancellationError
```

### CancellationCoordinator

Centralized token management:

```python
class CancellationCoordinator:
    def create_token(operation_id: str) -> AsyncCancellationToken
    def cancel_operation(operation_id: str, reason: str = "") -> bool
    def cancel_all_operations(reason: str = "Global cancellation") -> None
    async def execute_with_cancellation(operation_id: str, operation: Awaitable, name: str) -> Any
```

### Cancellation Flow

```
CLI (Ctrl+C or cancel command)
    │ DELETE /api/v1/operations/{id}
    ▼
Backend OperationsService.cancel_operation()
    │
    ▼ CancellationCoordinator.cancel_operation()
    │
    ▼ AsyncCancellationToken.cancel()
    │
Worker checks token.is_cancelled() (every ~5-100 iterations)
    │
    ▼ Saves checkpoint if applicable
    │
    ▼ Returns partial result or CancellationError
```

### SessionCancellationToken

Used by host services (training-host-service) for SIGTERM lifecycle management. Extends AsyncCancellationToken with session-level awareness.

---

## Worker Infrastructure

### WorkerAPIBase

**Location:** `ktrdr/workers/base.py`

Foundation for all worker types. Provides:

```python
class WorkerAPIBase:
    def __init__(
        self,
        worker_type: WorkerType,
        operation_type: OperationType,
        worker_port: int,
        backend_url: str
    )
```

**Built-in endpoints:**
- `GET /api/v1/operations/{operation_id}` — Query operation status
- `GET /api/v1/operations/{operation_id}/metrics?cursor=0` — Incremental metrics
- `POST /api/v1/operations/{operation_id}/cancel` — Cancel operation
- `GET /health` — Health check
- `POST /workers/register` — Self-registration

**Key features:**
- OperationsService singleton shared by all worker code
- FastAPI app with lifespan context manager
- CORS middleware
- Self-registration on startup

### WorkerOperationMixin

```python
class WorkerOperationMixin(BaseModel):
    task_id: Optional[str] = Field(default=None)
```

**Pattern:** Backend sends its operation_id as `task_id`. Worker uses `operation_id = request.task_id or generate_id()`. Ensures both sides track the same operation ID.

### WorkerRegistry

**Location:** `ktrdr/api/services/worker_registry.py`

```python
class WorkerRegistry:
    def register_worker(worker: WorkerEndpoint) -> RegistrationResult
    def list_workers(
        worker_type: Optional[WorkerType] = None,
        status: Optional[WorkerStatus] = None
    ) -> list[WorkerEndpoint]
    def get_worker(worker_id: str) -> Optional[WorkerEndpoint]
    async def health_check_all() -> dict[str, dict]
```

### Worker Types

```python
class WorkerType(str, Enum):
    BACKTESTING = "backtesting"
    TRAINING = "training"
    CPU_TRAINING = "cpu_training"  # Deprecated — use TRAINING with capabilities
    GPU_HOST = "gpu_host"
```

### GracefulShutdownError

Raised by `run_with_graceful_shutdown()` on SIGTERM. Signals checkpoint save, not failure.

---

## Data Models

### OperationInfo

```python
class OperationInfo(BaseModel):
    operation_id: str
    parent_operation_id: Optional[str]
    operation_type: OperationType
    status: OperationStatus
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    progress: OperationProgress
    metadata: OperationMetadata
    error_message: Optional[str]
    warnings: list[str]
    errors: list[str]
    result_summary: Optional[dict]
    metrics: Optional[dict]
    is_backend_local: bool
```

### OperationProgress

```python
class OperationProgress(BaseModel):
    percentage: float          # 0-100
    current_step: Optional[str]
    steps_completed: int
    steps_total: int
    items_processed: int
    items_total: Optional[int]
    current_item: Optional[str]
    context: dict[str, Any]    # Domain-specific
```

### OperationMetadata

```python
class OperationMetadata(BaseModel):
    symbol: Optional[str]
    timeframe: Optional[str]
    mode: Optional[str]
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    parameters: dict[str, Any]
```

---

## Gotchas

### Progress updates are LOCK-FREE

`OperationsService.update_progress()` is lock-free for performance. Don't expect strict ordering guarantees on concurrent updates.

### Parent-child progress uses phase-weighted aggregation

Aggregated progress for parent operations uses phase weights: design 0-5%, training 5-80%, backtest 80-100%.

### Cancellation is not instant

Workers check cancellation tokens periodically (every ~5 batches for training, ~100 bars for backtesting). There's a delay between requesting cancellation and the operation actually stopping.

### OperationServiceProxy bridges backend to workers

The backend never directly queries worker OperationsService. It creates an OperationServiceProxy that translates backend operation IDs to worker operation IDs via HTTP.

### Workers self-register on startup

Workers call `POST /workers/register` on the backend during lifespan startup. No manual registration needed.

### Cursor-based metrics are incremental

`get_metrics(cursor=N)` returns only metrics added after position N. The returned cursor should be passed to the next call for efficient incremental reads.
