# KTRDR Async Infrastructure Deep Dive
## Comprehensive Analysis of Patterns for Distributed System Migration

---

## Executive Summary

The KTRDR async infrastructure consists of **5 core interconnected components** that work together to manage long-running operations with progress tracking, cancellation support, and status monitoring. This infrastructure must be preserved and adapted when moving to a distributed system.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│ API Layer (FastAPI)                                             │
│ ├─ Endpoints create/query operations via OperationsService    │
│ └─ Operations registry (global singleton)                      │
└─────────────────────────────────────────────────────────────────┘
         ↓ HTTP + Direct calls
┌─────────────────────────────────────────────────────────────────┐
│ ServiceOrchestrator Base Class                                  │
│ ├─ Manages adapter initialization (local vs host service)      │
│ ├─ Provides execute_with_progress() and execute_with_cancellation()
│ ├─ Integrates with GenericProgressManager                      │
│ └─ Manages cancellation tokens from global coordinator          │
└─────────────────────────────────────────────────────────────────┘
         ↓ Progress callbacks + Cancellation checks
┌─────────────────────────────────────────────────────────────────┐
│ Operations Service                                              │
│ ├─ Global operation registry (_operations dict)               │
│ ├─ Tracks status: PENDING → RUNNING → COMPLETED/FAILED        │
│ ├─ Stores progress via OperationProgress model                │
│ ├─ Manages cancellation tokens from coordinator               │
│ └─ Supports pull-based metrics from bridges/proxies           │
└─────────────────────────────────────────────────────────────────┘
         ↕ Pull-based refresh (cache-aware)
┌──────────────────────────────────────────────────────────────────┐
│ Progress Infrastructure                                         │
│ ├─ GenericProgressManager (thread-safe with RLock)            │
│ ├─ GenericProgressState (domain-agnostic data structure)       │
│ ├─ ProgressRenderer (domain-specific formatting)              │
│ └─ Progress callbacks to OperationsService                    │
└──────────────────────────────────────────────────────────────────┘
         ↓ Cancellation signals
┌──────────────────────────────────────────────────────────────────┐
│ Cancellation System                                             │
│ ├─ CancellationCoordinator (global singleton)                  │
│ ├─ AsyncCancellationToken (thread-safe protocol)              │
│ ├─ CancellationState (atomic state management)                │
│ └─ Integration with ServiceOrchestrator                        │
└──────────────────────────────────────────────────────────────────┘
```

---

## 1. ServiceOrchestrator Base Class

**Location**: `/home/user/ktrdr/ktrdr/async_infrastructure/service_orchestrator.py`

### Core Responsibilities

1. **Adapter Management** - Routes operations between local and host service implementations
2. **Progress Tracking** - Unified progress management across all service types
3. **Cancellation Support** - Integrated cancellation token lifecycle
4. **Error Handling** - Standardized error context and propagation
5. **Configuration Management** - Environment-based service configuration

### Key Design Patterns

#### 1. Environment-Based Adapter Routing
```python
class ServiceOrchestrator(ABC, Generic[T]):
    """
    - _initialize_adapter(): Abstract method, checks environment variables
    - is_using_host_service(): Determines execution mode
    - get_host_service_url(): Returns configured endpoint
    """
```

**Environment Variables**:
- `USE_{PREFIX}_HOST_SERVICE` - Boolean toggle (e.g., USE_IB_HOST_SERVICE, USE_TRAINING_HOST_SERVICE)
- `{PREFIX}_HOST_SERVICE_URL` - Endpoint URL (e.g., IB_HOST_SERVICE_URL=http://localhost:5001)

#### 2. Unified Async Operation Execution

**Method**: `execute_with_progress(operation, progress_callback, timeout, ...)`

Features:
- Wraps async operations with enhanced progress tracking
- Creates GenericProgressManager for each operation
- Backward compatible with legacy dict-based progress callbacks
- Supports operation naming, total steps, and context passing
- Timeout support with proper cancellation

**Execution Flow**:
```
1. Create GenericProgressManager with renderer and callback
2. Start operation tracking (operation_id, total_steps, context)
3. Execute wrapped operation with timeout
4. On completion: call complete_operation()
5. On error: update with error context
6. Finally: clear operation reference
```

#### 3. Unified Cancellation Execution

**Method**: `execute_with_cancellation(operation, token, check_interval, ...)`

Features:
- Integrates with global CancellationCoordinator
- Bridges legacy tokens to unified protocol
- Thread-safe operation cancellation
- Automatic cleanup on completion

**Cancellation Flow**:
```
1. Check if token already cancelled before start
2. Create unified token from coordinator
3. For legacy tokens: spawn bridge task to check periodically
4. Execute wrapped operation with coordinator integration
5. On cancellation: raise asyncio.CancelledError
6. Clean up: remove token reference and bridge task
```

#### 4. Managed Operation Pattern

**Method**: `start_managed_operation(operation_name, operation_type, operation_func, ...)`

**This is the PRIMARY integration point for distributed systems!**

Features:
- Creates operation record in OperationsService
- Handles background task execution in separate thread
- Cross-thread progress callback communication via `call_soon_threadsafe()`
- Supports remote operations (doesn't auto-complete if result has status="started")
- Returns API response format: `{"operation_id": "...", "status": "started"}`

**Critical Implementation Details**:
```python
# Thread handling:
def run_wrapper_in_thread():
    """Run async wrapper in a new event loop in a separate thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_managed_operation_wrapper())
    finally:
        loop.close()

background_task = asyncio.create_task(asyncio.to_thread(run_wrapper_in_thread))

# Progress callback (cross-thread communication):
def progress_callback(state):
    """Thread-safe progress callback using main loop"""
    def update_progress_in_main_loop():
        asyncio.create_task(
            operations_service.update_progress(
                operation_id,
                self._convert_progress_state_to_operation_progress(state)
            )
        )
    try:
        main_loop.call_soon_threadsafe(update_progress_in_main_loop)
    except Exception:
        pass  # Graceful failure if main loop gone
```

#### 5. Configuration & Validation

**Methods**:
- `get_configuration_info()` - Returns service config (mode, URL, env vars, adapter stats)
- `validate_configuration()` - Validates environment variables and adapter setup
- `get_configuration_schema()` - Returns expected configuration structure

### Abstract Methods Subclasses Must Implement

```python
def _initialize_adapter(self) -> T:
    """Create adapter based on environment configuration"""
    
def _get_service_name(self) -> str:
    """Return human-readable service name (e.g., "Data/IB", "Training")"""
    
def _get_default_host_url(self) -> str:
    """Return default host service URL (e.g., "http://localhost:5001")"""
    
def _get_env_var_prefix(self) -> str:
    """Return environment variable prefix (e.g., "IB", "TRAINING")"""
```

---

## 2. OperationsService

**Location**: `/home/user/ktrdr/ktrdr/api/services/operations_service.py`

### Core Purpose

Central registry for ALL long-running operations across the system. Provides:
- Operation creation and lifecycle management
- Progress tracking and updates
- Cancellation coordination
- Metrics aggregation
- Pull-based refresh from local bridges and remote proxies

### Key Design Patterns

#### 1. Operation Lifecycle

**Status Progression**:
```
PENDING → RUNNING → {COMPLETED | FAILED | CANCELLED}
```

**State Storage**:
- Global registry: `_operations: dict[str, OperationInfo]`
- Each operation has: id, type, status, metadata, progress, metrics, timestamps
- Thread-safe with `asyncio.Lock()` for state mutations

#### 2. Operation Registration Flow

```python
async def create_operation(operation_type, metadata, operation_id=None):
    """
    1. Generate unique operation_id (timestamp + UUID)
    2. Create OperationInfo record (status=PENDING)
    3. Add to registry
    4. Return operation info
    """
    # ID format: op_{operation_type}_{timestamp}_{unique_id}
    # Example: op_training_20250120_120000_abc123

async def start_operation(operation_id, task):
    """
    1. Set status → RUNNING
    2. Set started_at timestamp
    3. Register asyncio.Task for cancellation
    """

async def complete_operation(operation_id, result_summary):
    """
    1. Pull final metrics from bridge if registered
    2. Set status → COMPLETED
    3. Set completed_at timestamp
    4. Set result_summary
    5. Unregister task
    """

async def fail_operation(operation_id, error_message):
    """
    1. Set status → FAILED
    2. Set completed_at timestamp
    3. Store error_message
    4. Unregister task
    """
```

#### 3. Progress Updates (Lock-Free)

**Method**: `update_progress(operation_id, progress, warnings, errors)`

**Design**:
- NO lock - atomic assignment for performance
- Progress is read-only after update (Pydantic immutability)
- Warnings/errors are concatenated (not replaced)
- Non-blocking: callbacks can hammer progress updates

**Progress Structure** (OperationProgress):
```python
percentage: float              # 0-100
current_step: Optional[str]    # Current step description
steps_completed: int           # Number of completed steps
steps_total: int               # Total number of steps
items_processed: int           # Number of items processed
items_total: Optional[int]     # Total items to process
current_item: Optional[str]    # Current item being processed
context: dict[str, Any]        # Domain-specific data (epochs, segments, etc.)
```

#### 4. Pull-Based Refresh Architecture (CRITICAL FOR DISTRIBUTED SYSTEMS)

**The Problem Being Solved**:
- Worker threads can't use `asyncio.create_task()` (no event loop)
- Host services run independently, need polling
- Solution: OperationsService PULLS updates instead of waiting for PUSH

**Two Types of Pullable Sources**:

**A. Local Bridges** (e.g., TrainingProgressBridge):
```python
def register_local_bridge(operation_id, bridge):
    """Bridge is a local object that has get_status() and get_metrics(cursor)"""
    self._local_bridges[operation_id] = bridge
    self._metrics_cursors[operation_id] = 0

def _refresh_from_bridge(operation_id):
    """
    Cache-aware refresh:
    1. Check if cache fresh (age < TTL, default 1 second)
    2. If fresh: skip (cache hit)
    3. If stale: pull from bridge
       - Call bridge.get_status() → progress dict
       - Call bridge.get_metrics(cursor) → (new_metrics, new_cursor)
       - Update operation progress
       - Append new metrics to operation.metrics
       - Update cursor for next incremental read
       - Update cache timestamp
    """
```

**B. Remote Proxies** (e.g., OperationServiceProxy for host services):
```python
def register_remote_proxy(backend_operation_id, proxy, host_operation_id):
    """
    Proxy enables transparent querying of host service operations
    Maps: backend_id → (proxy, host_id)
    """
    self._remote_proxies[backend_operation_id] = (proxy, host_operation_id)

async def _refresh_from_remote_proxy(operation_id):
    """
    Cache-aware async refresh from host service:
    1. Check if cache fresh (age < TTL)
    2. If fresh: skip
    3. If stale: query host service via proxy
       - Call proxy.get_operation(host_id) → host data
       - Update backend operation status/progress
       - Call proxy.get_metrics(host_id, cursor) → (metrics, new_cursor)
       - Append new metrics
       - Update cursor and cache timestamp
    """
```

**Cache Strategy**:
- Prevents thundering herd (multiple clients querying same operation)
- TTL configurable: `OPERATIONS_CACHE_TTL` (default 1.0 second)
- Force refresh bypasses cache: `get_operation(id, force_refresh=True)`

#### 5. Cancellation Integration

**Method**: `cancel_operation(operation_id, reason, force)`

**Flow**:
```
1. Check operation exists and is cancellable
2. Use CancellationCoordinator to cancel operation
   - Creates/gets AsyncCancellationToken for operation_id
   - Marks token as cancelled with reason
3. Cancel asyncio.Task if exists
4. If remote proxy registered: propagate cancellation to host service
5. Update status → CANCELLED
6. Set completed_at and error_message
```

**Remote Cancellation**:
```python
remote_proxy_info = self._get_remote_proxy(operation_id)
if remote_proxy_info:
    proxy, host_operation_id = remote_proxy_info
    await proxy.cancel_operation(host_operation_id, reason)
```

#### 6. Metrics Management

**Method**: `add_operation_metrics(operation_id, metrics_data)`

**Type-Aware Storage**:
```python
if operation.operation_type == OperationType.TRAINING:
    # Append to epochs list, compute trend analysis
    if "epochs" not in operation.metrics:
        operation.metrics["epochs"] = []
    operation.metrics["epochs"].append(epoch_metrics)
    self._update_training_metrics_analysis(operation.metrics)

elif operation.operation_type == OperationType.BACKTESTING:
    # Store bar-by-bar metrics
    if "bars" not in operation.metrics:
        operation.metrics["bars"] = []
    operation.metrics["bars"].extend(new_metrics)

elif operation.operation_type == OperationType.DATA_LOAD:
    # Store segment metrics
    if "segments" not in operation.metrics:
        operation.metrics["segments"] = []
    operation.metrics["segments"].extend(new_metrics)
```

**Training Trend Analysis**:
Automatically computes:
- `best_epoch`: Index of epoch with lowest validation loss
- `best_val_loss`: Lowest validation loss achieved
- `epochs_since_improvement`: How many epochs since best epoch
- `is_overfitting`: Train loss ↓ while val loss ↑ (>5% divergence)
- `is_plateaued`: No improvement for 10+ epochs

### Data Models

**OperationInfo** (complete operation record):
```python
operation_id: str                          # Unique identifier
operation_type: OperationType              # data_load, training, backtesting, etc.
status: OperationStatus                    # pending, running, completed, failed, cancelled
created_at: datetime                       # When created
started_at: Optional[datetime]             # When execution started
completed_at: Optional[datetime]           # When finished
progress: OperationProgress                # Current progress snapshot
metadata: OperationMetadata                # Operation parameters (symbol, timeframe, etc.)
error_message: Optional[str]               # Error if failed
warnings: list[str]                        # Non-fatal warnings
errors: list[str]                          # Error messages
result_summary: Optional[dict]             # Results summary
metrics: Optional[dict]                    # Domain-specific metrics (training epochs, etc.)
```

**OperationMetadata**:
```python
symbol: Optional[str]                      # Trading symbol (e.g., "AAPL")
timeframe: Optional[str]                   # Timeframe (e.g., "1h", "1d")
mode: Optional[str]                        # Operation mode (e.g., "tail", "batch")
start_date: Optional[datetime]             # Start date for operation
end_date: Optional[datetime]               # End date for operation
parameters: dict[str, Any]                 # Additional parameters
```

---

## 3. Cancellation System

**Location**: `/home/user/ktrdr/ktrdr/async_infrastructure/cancellation.py`

### Core Components

#### 1. CancellationToken (Protocol)

Interface that all tokens must implement:
```python
def is_cancelled() -> bool:                # Check cancellation status
def cancel(reason: str) -> None:           # Request cancellation
async def wait_for_cancellation() -> None: # Async wait for signal
@property
def is_cancelled_requested() -> bool:      # Alias for ServiceOrchestrator
```

#### 2. CancellationState (Thread-Safe State)

Manages atomic cancellation state:
```python
_cancelled: bool                           # Individual operation cancelled
_global_cancelled: bool                    # Global cancellation active
_reason: Optional[str]                     # Cancellation reason
_lock: threading.RLock()                   # Thread-safe mutual exclusion
_event: asyncio.Event()                    # Async notification
```

**Key Methods**:
- `cancel(reason)` - Mark individual operation cancelled, notify async waiters
- `set_global_cancelled(reason)` - Mark global cancellation active
- `is_cancelled` - Check either individual OR global (OR logic)
- `wait()` - Async wait for cancellation signal

#### 3. AsyncCancellationToken (Unified Implementation)

Thread-safe cancellation token for all operations:

```python
class AsyncCancellationToken:
    operation_id: str                      # Unique operation ID
    _state: CancellationState               # Thread-safe state
    
    def is_cancelled() -> bool:             # Query cancellation
    def cancel(reason) -> None:             # Request cancellation
    async def wait_for_cancellation():      # Async wait
    def check_cancellation(context=""):     # Check and raise if cancelled
```

**Thread-Safety Design**:
- Uses `threading.RLock()` for synchronized access
- `asyncio.Event()` for async notification
- `loop.call_soon_threadsafe()` bridges sync → async cancellation signals
- Works from both sync (thread) and async (event loop) contexts

#### 4. CancellationCoordinator (Global Singleton)

Centralized management of all operation cancellations:

```python
class CancellationCoordinator:
    _tokens: dict[str, AsyncCancellationToken]      # All tokens
    _global_state: CancellationState                # Global cancellation state
    _lock: threading.RLock()                        # Thread safety
    
    def create_token(operation_id) -> AsyncCancellationToken:
        """Create token, apply global cancellation if active"""
        
    def cancel_operation(operation_id, reason) -> bool:
        """Cancel specific operation, return True if found"""
        
    def cancel_all_operations(reason) -> None:
        """Global cancellation - cancels all existing and future operations"""
        
    async def execute_with_cancellation(operation_id, operation_func, name):
        """Execute with enhanced cancellation support"""
        
    def get_status() -> dict:
        """Get coordinator status: active_operations, global state, etc."""
```

### Integration Points

#### 1. ServiceOrchestrator Integration

**Execution Patterns**:
```python
# Pattern 1: Simple operation with unified cancellation
token = create_cancellation_token()
await orchestrator.execute_with_cancellation(
    operation_func(),
    cancellation_token=token,
    operation_name="my_operation"
)

# Pattern 2: Managed operation with automatic token handling
await orchestrator.start_managed_operation(
    operation_type=OperationType.TRAINING,
    operation_name="train_model",
    operation_func=async_function,
    # ServiceOrchestrator creates token automatically
)
```

#### 2. OperationsService Integration

**Token Creation**:
```python
def get_cancellation_token(operation_id) -> AsyncCancellationToken:
    """Get token from coordinator for operation"""
    return self._cancellation_coordinator.create_token(operation_id)
```

**Cancellation Propagation**:
```python
async def cancel_operation(operation_id, reason):
    # 1. Cancel in coordinator
    self._cancellation_coordinator.cancel_operation(operation_id, reason)
    
    # 2. Cancel asyncio.Task if exists
    if operation_id in self._operation_tasks:
        task = self._operation_tasks[operation_id]
        task.cancel()
    
    # 3. Propagate to host service if remote
    if operation_id in self._remote_proxies:
        proxy, host_id = self._remote_proxies[operation_id]
        await proxy.cancel_operation(host_id, reason)
```

#### 3. CLI Integration

```python
def setup_cli_cancellation_handler():
    """Register Ctrl+C handler for graceful cancellation"""
    
    def handle_interrupt(signum, frame):
        logger.info("KeyboardInterrupt - cancelling all operations...")
        cancel_all_operations("User requested cancellation (Ctrl+C)")
    
    signal.signal(signal.SIGINT, handle_interrupt)
```

### Cancellation Propagation Flow

**Local Operation**:
```
User presses Ctrl+C
  ↓
CLI cancellation handler triggered
  ↓
cancel_all_operations() called on coordinator
  ↓
All tokens marked cancelled
  ↓
Operations check token: is_cancelled() → True
  ↓
Operations raise CancellationError
  ↓
OperationsService catches, updates status → CANCELLED
```

**Remote Operation** (via host service):
```
User calls cancel API endpoint
  ↓
OperationsService.cancel_operation(operation_id)
  ↓
1. Coordinator.cancel_operation(operation_id)  ← Local token cancelled
  ↓
2. proxy.cancel_operation(host_operation_id)  ← Remote operation cancelled
  ↓
Host service cancels its operation
  ↓
Next status poll sees CANCELLED status
```

---

## 4. Progress Management System

**Location**: `/home/user/ktrdr/ktrdr/async_infrastructure/progress.py`

### Core Components

#### 1. GenericProgressState (Data Structure)

Domain-agnostic progress snapshot:

```python
@dataclass
class GenericProgressState:
    # Core progress fields
    operation_id: str              # Unique operation identifier
    current_step: int              # Current step number
    total_steps: int               # Total steps
    percentage: float              # Overall progress 0-100
    message: str                   # Progress message
    
    # Timing
    start_time: datetime           # When operation started
    estimated_remaining: Optional[timedelta]  # ETA
    
    # Items tracking
    items_processed: int           # Items processed so far
    total_items: Optional[int]     # Total items to process
    
    # Hierarchical progress (for complex multi-step ops)
    step_start_percentage: float   # Step's start % in range (e.g., 10%)
    step_end_percentage: float     # Step's end % in range (e.g., 96%)
    step_current: int              # Current sub-step within step
    step_total: int                # Total sub-steps in step
    
    # Domain context
    context: dict[str, Any]        # Domain-specific data
```

**Example Context Values**:
```python
# For data loading
context = {
    "symbol": "AAPL",
    "timeframe": "1h",
    "segment_index": 5,
    "total_segments": 50,
    "current_item": "AAPL_1h_20250115"
}

# For training
context = {
    "epoch": 5,
    "total_epochs": 100,
    "batch": 32,
    "learning_rate": 0.001,
    "gpu_utilization": 85.5
}
```

#### 2. ProgressRenderer (Abstract Base)

Domain-specific progress formatting:

```python
class ProgressRenderer(ABC):
    def render_message(state: GenericProgressState) -> str:
        """Render progress message with domain context"""
        # Each domain implements custom formatting
        # Example: Data domain shows symbol/timeframe
        # Example: Training domain shows epoch/loss
        
    def enhance_state(state: GenericProgressState) -> GenericProgressState:
        """Optional: enhance state with domain calculations"""
        # Can add time estimations, predictions, etc.
```

**Concrete Implementations**:
- `DefaultServiceProgressRenderer` (ServiceOrchestrator) - Generic rendering
- `DataProgressRenderer` (Data module) - Symbol/timeframe context
- `TrainingProgressRenderer` (Training module) - Epoch/loss context

#### 3. GenericProgressManager (Thread-Safe Manager)

Manages progress state with callbacks:

```python
class GenericProgressManager:
    _state: Optional[GenericProgressState]  # Current state snapshot
    _lock: threading.RLock()                # Thread safety (same as existing ProgressManager)
    callback: Optional[Callable]            # Progress callback
    renderer: Optional[ProgressRenderer]    # Domain-specific renderer
    
    def start_operation(operation_id, total_steps, context=None):
        """Initialize operation tracking"""
        
    def start_step(step_name, step_number, step_percentage=None, ...):
        """Start new step with percentage range support (hierarchical)"""
        
    def update_step_progress(current, total, items_processed, detail):
        """Update progress within step's percentage range"""
        
    def update_progress(step, message, items_processed, context):
        """Simplified progress update"""
        
    def complete_operation():
        """Mark operation complete (100%)"""
        
    def _trigger_callback():
        """Call callback with current state"""
```

### Hierarchical Progress Pattern

**Problem**: Complex operations (like data loading) have multiple phases with different importance:
- Gap analysis: 0% → 5%
- Job creation: 5% → 10%
- **Segment fetching: 10% → 96%** ← Most time spent here
- Data assembly: 96% → 100%

**Solution**: Percentage ranges per step:

```python
progress_manager.start_step(
    "Gap Analysis",
    step_number=1,
    step_percentage=0.0,
    step_end_percentage=5.0
)

# As gap analysis proceeds, progress is 0% → 5%

progress_manager.start_step(
    "Segment Fetching",
    step_number=3,
    step_percentage=10.0,
    step_end_percentage=96.0
)

# As segments are fetched, progress interpolates to 10% → 96%
# Segment 1/50 → 10% + (1/50) * 86 = 11.72%
# Segment 25/50 → 10% + (25/50) * 86 = 53%
# Segment 50/50 → 96%
```

### Callback Pattern

**Synchronous Callback**:
```python
def progress_callback(state: GenericProgressState):
    """Called when progress updates"""
    print(f"{state.message}: {state.percentage:.1f}%")
    if state.context:
        print(f"  Context: {state.context}")
```

**Backward Compatibility** (ServiceOrchestrator):
```python
# Old dict-based callbacks still work
old_callback = lambda data: print(f"{data['message']}: {data['percentage']}%")

# ServiceOrchestrator wraps GenericProgressState
# Tries passing GenericProgressState first
# Falls back to dict format for old callbacks
```

---

## 5. Async Operation Lifecycle

### Complete Flow from Creation to Completion

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 1: Operation Creation                                    │
└─────────────────────────────────────────────────────────────────┘

1. User calls API endpoint (e.g., POST /api/train)
   
2. Endpoint calls ServiceOrchestrator.start_managed_operation()
   
3. ServiceOrchestrator:
   a. Calls OperationsService.create_operation()
      - Creates OperationInfo record
      - Sets status = PENDING
      - Generates operation_id
      - Returns to caller
   
   b. Creates AsyncCancellationToken via coordinator
   
   c. Creates GenericProgressManager with:
      - Progress callback (cross-thread via call_soon_threadsafe)
      - Domain-specific ProgressRenderer
   
   d. Spawns background task:
      - Runs in asyncio.to_thread() (separate worker thread)
      - Calls operation_func (user's async function)
      - Receives operation_id from operations_service
   
   e. Registers task with OperationsService.start_operation()
      - Sets status = RUNNING
      - Stores Task reference for cancellation
      - Records started_at timestamp

┌─────────────────────────────────────────────────────────────────┐
│ PHASE 2: Execution with Progress Tracking                      │
└─────────────────────────────────────────────────────────────────┘

4. Background task executes in worker thread:
   - Calls operation_func (e.g., training, data loading)
   - Has access to:
     * operation_id (passed as kwarg)
     * cancellation_token (from orchestrator)
     * Can update progress via orchestrator
   
5. During execution:
   a. Check cancellation:
      token.check_cancellation()  ← Raises if cancelled
   
   b. Update progress:
      orchestrator.update_operation_progress(
          step=5,
          message="Processing batch 5/100",
          context={"batch": 5, "loss": 0.45}
      )
      ↓
      GenericProgressManager.update_progress()
      ↓
      progress_callback(GenericProgressState)
      ↓
      main_loop.call_soon_threadsafe()  ← Cross-thread communication
      ↓
      Main loop: asyncio.create_task(
          operations_service.update_progress()
      )
   
   c. For bridge-based operations (training):
      - Bridge captures training callbacks
      - Bridge stores state internally
      - During polling: OperationsService pulls from bridge
      - For remote: OperationsService queries host service
   
6. Status polling (from client/CLI):
   
   GET /api/operations/{operation_id}
   ↓
   OperationsService.get_operation(operation_id)
   ↓
   If operation RUNNING and has bridge:
     - Cache check: is_fresh()?
     - If stale: _refresh_from_bridge() or _refresh_from_remote_proxy()
     - Pull progress state and incremental metrics
     - Update operation.progress
     - Update operation.metrics
   ↓
   Return OperationInfo to client

┌─────────────────────────────────────────────────────────────────┐
│ PHASE 3: Cancellation (if requested)                           │
└─────────────────────────────────────────────────────────────────┘

7. User requests cancellation:
   
   DELETE /api/operations/{operation_id}
   ↓
   OperationsService.cancel_operation(operation_id, reason)
   ↓
   a. CancellationCoordinator.cancel_operation(operation_id)
      - Marks token as cancelled
      - Broadcasts reason
   
   b. Cancel asyncio.Task if exists
   
   c. If remote proxy exists:
      - Call proxy.cancel_operation(host_id, reason)
      - Host service cancels its operation
   
   d. Update operation status → CANCELLED
      - Set completed_at timestamp
      - Set error_message = reason

8. Operation detects cancellation:
   
   token.is_cancelled() → True
   ↓
   Operations check periodically
   ↓
   Raise CancellationError or asyncio.CancelledError
   ↓
   Background task catches exception
   ↓
   Calls operations_service.fail_operation()
      - Sets status → FAILED
      - Sets error_message

┌─────────────────────────────────────────────────────────────────┐
│ PHASE 4: Completion                                             │
└─────────────────────────────────────────────────────────────────┘

9. Operation completes:
   
   a. Normal completion:
      - GenericProgressManager.complete_operation()
        * Sets percentage = 100%
        * Calls callback with final state
      
      - OperationsService.complete_operation()
        * Pulls final metrics from bridge
        * Sets status → COMPLETED
        * Sets result_summary
        * Sets completed_at timestamp
        * Unregisters Task reference
   
   b. Error completion:
      - OperationsService.fail_operation()
        * Sets status → FAILED
        * Sets error_message
        * Sets completed_at timestamp

10. Status polling after completion:
    
    GET /api/operations/{operation_id}
    ↓
    OperationsService.get_operation(operation_id)
    ↓
    Status is COMPLETED/FAILED/CANCELLED
    → Returns final operation info (no refresh needed)

11. Cleanup:
    
    - Operations can be cleaned up after max age (default 24 hours)
    - cleanup_old_operations(max_age_hours)
    - Removes from registry only if COMPLETED/FAILED/CANCELLED
```

---

## 6. Status Polling & Progress Delivery

### Pull-Based Architecture (Key for Distributed Systems)

**Problem**: 
- Sync worker threads (asyncio.to_thread) can't use asyncio.create_task()
- Host services run independently, metrics aren't auto-pushed
- Solution: Operations Service PULLS updates

**Polling Mechanism**:

```
Client polls every 500ms - 1s:
    ↓
GET /api/operations/{operation_id}
    ↓
OperationsService.get_operation(operation_id, force_refresh=False)
    ↓
Is operation RUNNING?
    ├─ YES:
    │   ├─ Has local bridge?
    │   │   └─ _refresh_from_bridge(operation_id)
    │   │       - Check cache (TTL 1s default)
    │   │       - If fresh: skip (performance)
    │   │       - If stale: pull from bridge
    │   │           * state = bridge.get_status()
    │   │           * metrics, cursor = bridge.get_metrics(old_cursor)
    │   │           * Update operation.progress
    │   │           * Update operation.metrics (incremental)
    │   │           * Store new cursor for next read
    │   │
    │   ├─ Has remote proxy?
    │   │   └─ _refresh_from_remote_proxy(operation_id)
    │   │       - Check cache (TTL 1s default)
    │   │       - If fresh: skip
    │   │       - If stale: query host service
    │   │           * data = await proxy.get_operation(host_id)
    │   │           * metrics, cursor = await proxy.get_metrics(host_id, old_cursor)
    │   │           * Update operation.progress and metrics
    │   │
    │   └─ Return updated operation
    │
    └─ NO:
        └─ Return operation as-is (no refresh)
        ↓
Return OperationInfo with current progress/metrics
```

**Cache Strategy Reasoning**:
- TTL prevents repeated bridge reads for fast clients
- Reduces contention on operations_service lock
- Typical: 10 concurrent clients polling same operation
  - Without cache: 10 reads/sec from bridge
  - With 1s cache: 1 read/sec to bridge
  - 10x reduction in overhead!

### Incremental Metrics Retrieval

**Pattern**: Cursor-based incremental reads

**Benefits**:
- Only send NEW metrics to client
- Avoids resending all metrics each poll
- Scales to millions of metrics (training epochs, backtest bars)

**Implementation**:
```python
# First read
metrics, cursor = bridge.get_metrics(cursor=0)  # Returns first 100 metrics, cursor=100

# Second read (1 second later)
metrics, cursor = bridge.get_metrics(cursor=100)  # Returns metrics 100-150, cursor=150

# Third read (no new metrics)
metrics, cursor = bridge.get_metrics(cursor=150)  # Returns [], cursor=150
```

---

## 7. Integration with Distributed Systems

### Key Considerations for Containerization

#### 1. Operation ID Generation

Currently: `op_{operation_type}_{timestamp}_{unique_id}`

For distributed systems:
- Include node/service identifier
- Ensure uniqueness across distributed backends
- Example: `op_{service_name}_{operation_type}_{timestamp}_{uuid}`

#### 2. Registry Persistence

Currently: In-memory dictionary `_operations: dict[str, OperationInfo]`

For distributed systems:
- Move to persistent store (Redis, PostgreSQL, etc.)
- Implement cache layer for performance
- Support queries: by status, type, date range
- TTL-based cleanup

#### 3. Cancellation Token Distribution

Currently: Global coordinator in memory

For distributed systems:
- Store cancellation state in persistent store
- Propagate cancellation across service boundaries
- Use pub/sub for real-time cancellation broadcasts
- Fallback to polling if pub/sub unavailable

#### 4. Progress Bridges

Currently: Direct Python object references

For distributed systems:
- For local operations: Keep current bridge approach
- For remote operations: Use OperationServiceProxy pattern
- Implement adapter pattern for different storage backends

#### 5. Metrics Aggregation

Currently: Per-operation dict, type-aware storage

For distributed systems:
- Time-series database for metrics (InfluxDB, Prometheus)
- Hierarchical metrics (epochs → batches → samples)
- Real-time aggregation queries
- Historical retention policies

#### 6. Status Synchronization

Currently: Pull with 1s TTL cache

For distributed systems:
- Use pub/sub for immediate status updates (best case)
- Fall back to polling with longer TTL (10-30s)
- Implement eventual consistency model
- Handle stale reads gracefully

### Architecture Migration Pattern

```
Current (Single Container):
┌──────────────────────┐
│ API (FastAPI)        │
├─ OperationsService   │
├─ ServiceOrchestrator │
├─ Progress Manager    │
└─ Cancellation Token  │
│ All in memory        │
└──────────────────────┘

Distributed (Multiple Containers):
┌──────────────────────────────────────────┐
│ Load Balancer / API Gateway              │
└──────────────────────────────────────────┘
  │                  │                  │
  ↓                  ↓                  ↓
┌────────────┐  ┌────────────┐  ┌────────────┐
│ API Server │  │ API Server │  │ API Server │
│ (Replica)  │  │ (Replica)  │  │ (Replica)  │
├────────────┤  ├────────────┤  ├────────────┤
│ Operations │  │ Operations │  │ Operations │
│ Service    │  │ Service    │  │ Service    │
│(Redis)     │  │(Redis)     │  │(Redis)     │
└────────────┘  └────────────┘  └────────────┘
  │                  │                  │
  └──────────────────┼──────────────────┘
                     ↓
         ┌──────────────────────────┐
         │ Persistent Store         │
         │ - Operation Registry     │
         │ - Cancellation Tokens    │
         │ - Metrics History        │
         │ (PostgreSQL/Redis/etc)   │
         └──────────────────────────┘
```

---

## Summary: Patterns to Preserve in Distributed Migration

### Must-Keep Patterns

1. **ServiceOrchestrator as abstraction layer**
   - Environment-based routing (local vs host service)
   - Unified progress and cancellation APIs
   - Should remain unchanged in distributed version

2. **OperationsService as operation registry**
   - Central authority for operation lifecycle
   - Status transitions and timestamps
   - Move to persistent store but keep API contracts

3. **Pull-based progress updates**
   - Avoid PUSH callbacks across service boundaries
   - Cache-aware refreshes to prevent thundering herd
   - Cursor-based incremental metrics

4. **Cancellation token protocol**
   - Unified CancellationToken interface
   - Global coordinator pattern
   - Atomic cancellation state

5. **GenericProgressManager**
   - Domain-agnostic progress tracking
   - ProgressRenderer pattern for customization
   - Thread-safe with RLock

6. **Type-aware metrics storage**
   - Different fields for training vs data vs backtesting
   - Trend analysis for training operations
   - Hierarchical structures (epochs → batches)

### Must-Change for Distribution

1. **In-memory registries** → Persistent stores
2. **Direct object references** → HTTP proxies or RPC
3. **Thread-local event loops** → Distributed async coordination
4. **Single-node timestamps** → Clock synchronization
5. **Single-point operation IDs** → Distributed unique ID generation
6. **Synchronous callbacks** → Async pub/sub or polling

### New Patterns Needed

1. **Operation state synchronization** across nodes
2. **Metric aggregation** from multiple sources
3. **Cancellation broadcast** across service mesh
4. **Progress aggregation** for composite operations
5. **Health checks** for dependent services
6. **Failure recovery** and automatic retries

