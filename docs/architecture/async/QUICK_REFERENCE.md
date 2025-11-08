# Async Infrastructure - Quick Reference Guide

## The 5 Core Components

### 1. ServiceOrchestrator
**File**: `/ktrdr/async_infrastructure/service_orchestrator.py`

**Purpose**: Base class for all services (Training, Data, etc.)

**Key Methods**:
```python
# Execute operation with progress tracking
await execute_with_progress(
    operation,
    progress_callback=callback_func,
    operation_name="my_op",
    total_steps=100
)

# Execute operation with cancellation support
await execute_with_cancellation(
    operation,
    cancellation_token=token,
    operation_name="my_op"
)

# Start long-running operation (PRIMARY PATTERN)
await start_managed_operation(
    operation_type=OperationType.TRAINING,
    operation_name="train_model",
    operation_func=async_func,  # Your async function
    total_steps=100,
    metadata=OperationMetadata(symbol="AAPL")
)
```

**Key Concept**: Environment-based routing
- `USE_TRAINING_HOST_SERVICE=true` → Routes to host service
- `TRAINING_HOST_SERVICE_URL=http://localhost:5002` → Host URL

### 2. OperationsService
**File**: `/ktrdr/api/services/operations_service.py`

**Purpose**: Central registry for all long-running operations

**Key Methods**:
```python
# Create operation
operation = await operations_service.create_operation(
    operation_type=OperationType.TRAINING,
    metadata=metadata
)

# Start operation
await operations_service.start_operation(operation_id, task)

# Update progress (lock-free, fast)
await operations_service.update_progress(
    operation_id,
    OperationProgress(percentage=45.5, current_step="Epoch 5/10")
)

# Get operation status (with auto-refresh from bridges)
operation = await operations_service.get_operation(operation_id)

# Cancel operation
result = await operations_service.cancel_operation(
    operation_id,
    reason="User requested cancellation"
)
```

**Key Concept**: Pull-based architecture
- Operations don't push progress
- Clients pull status via API
- OperationsService pulls from bridges/proxies when needed
- Cache prevents thundering herd (1s TTL default)

### 3. CancellationSystem
**File**: `/ktrdr/async_infrastructure/cancellation.py`

**Purpose**: Unified cancellation across all operations

**Key Interfaces**:
```python
# Get cancellation token for operation
token = operations_service.get_cancellation_token(operation_id)

# Check if cancelled
if token.is_cancelled():
    raise CancellationError("Operation was cancelled")

# Wait for cancellation (async)
await token.wait_for_cancellation()

# Global cancellation (Ctrl+C)
cancel_all_operations("User pressed Ctrl+C")
```

**Key Concept**: Thread-safe coordination
- Works from both sync threads and async contexts
- Uses RLock + asyncio.Event
- Integrates with OperationsService

### 4. ProgressManagement
**File**: `/ktrdr/async_infrastructure/progress.py`

**Purpose**: Unified progress tracking system

**Key Components**:
```python
# Progress state (domain-agnostic)
state = GenericProgressState(
    operation_id="training_op",
    current_step=5,
    total_steps=100,
    percentage=50.0,
    message="Training epoch 5",
    context={"epoch": 5, "loss": 0.45}
)

# Progress manager (thread-safe)
progress_manager = GenericProgressManager(
    callback=my_callback,
    renderer=my_renderer  # Domain-specific
)

progress_manager.start_operation("train", total_steps=100)
progress_manager.update_progress(step=5, message="Epoch 5")
progress_manager.complete_operation()
```

**Key Concept**: Hierarchical progress
- Steps can have percentage ranges
- Enables 10% → 96% for long phases
- Sub-progress interpolates within range

### 5. Data Models
**File**: `/ktrdr/api/models/operations.py`

**Key Types**:
```python
# Status: PENDING → RUNNING → COMPLETED/FAILED/CANCELLED
status = OperationStatus.RUNNING

# Progress snapshot
progress = OperationProgress(
    percentage=45.5,
    current_step="Loading segment 7/50",
    steps_completed=7,
    steps_total=50,
    items_processed=250,
    items_total=500,
    context={"segment": 7, "symbol": "AAPL"}
)

# Complete operation info
operation = OperationInfo(
    operation_id="op_training_20250120_abc123",
    operation_type=OperationType.TRAINING,
    status=OperationStatus.RUNNING,
    progress=progress,
    metrics={"epochs": [...]}
)
```

---

## Integration Patterns

### Pattern 1: Simple Async Operation with Progress

```python
from ktrdr.async_infrastructure.service_orchestrator import ServiceOrchestrator

class MyService(ServiceOrchestrator):
    async def do_work(self) -> dict:
        """Example operation with progress tracking"""
        return await self.start_managed_operation(
            operation_type=OperationType.DATA_LOAD,
            operation_name="load_data",
            operation_func=self._load_data,
            total_steps=100,
            metadata=OperationMetadata(symbol="AAPL", timeframe="1h")
        )
    
    async def _load_data(self, operation_id: str, **kwargs) -> dict:
        """Your async operation"""
        for i in range(100):
            # Update progress
            self.update_operation_progress(
                step=i+1,
                message=f"Loading segment {i+1}/100",
                context={"segment": i+1}
            )
            
            # Check cancellation
            token = self.get_current_cancellation_token()
            if token and token.is_cancelled():
                raise CancellationError("Operation cancelled")
            
            # Do work
            await asyncio.sleep(0.1)
        
        return {"status": "completed", "items_loaded": 100}
```

### Pattern 2: With Progress Callback (Direct)

```python
async def my_operation(progress_callback):
    for i in range(100):
        progress_callback({
            "percentage": (i+1) * 100 / 100,
            "message": f"Step {i+1}/100",
            "operation": "my_op"
        })
        await asyncio.sleep(0.1)

# Execute with callback
progress_manager = GenericProgressManager(callback=my_operation_callback)
await orchestrator.execute_with_progress(
    my_operation(my_operation_callback),
    operation_name="my_op"
)
```

### Pattern 3: Cancellation Handling

```python
async def cancellable_operation(operation_id: str, **kwargs):
    token = get_cancellation_token(operation_id)
    
    for i in range(100):
        # Periodic checks
        if token.is_cancelled():
            raise CancellationError(f"Cancelled at step {i}: {token.reason}")
        
        # Long operations: break into chunks for responsiveness
        await do_work_chunk(i)
    
    return {"status": "completed"}

# Cleanup is automatic via try/finally in ServiceOrchestrator
```

---

## Status Polling Flow

**Client (CLI/Frontend)**:
```
1. User initiates operation
   POST /api/operations/train
   ← Response: {"operation_id": "op_training_...", "status": "started"}

2. Start polling for status
   GET /api/operations/op_training_... (poll every 500ms)
   
3. OperationsService.get_operation() handles:
   - If RUNNING and has bridge: pull fresh progress
   - If RUNNING and remote: query host service
   - Cache ensures no thundering herd
   
4. Return current progress
   {"status": "running", "progress": {"percentage": 45.5, ...}, "metrics": {...}}

5. When complete:
   {"status": "completed", "progress": {"percentage": 100.0}, "result_summary": {...}}
```

---

## Critical Patterns for Distributed Migration

### 1. Pull-Based Progress (NOT Push)
✅ **DO**: Client polls for progress
❌ **DON'T**: Server pushes progress via callbacks

### 2. Incremental Metrics (Cursor-Based)
✅ **DO**: `get_metrics(cursor=100)` returns new metrics since cursor 100
❌ **DON'T**: Return all metrics every time

### 3. Cache-Aware Queries
✅ **DO**: Check cache freshness, skip refresh if fresh
❌ **DON'T**: Always hit bridge/host service

### 4. Operation Registry as Authority
✅ **DO**: OperationsService is source of truth
❌ **DON'T**: Trust operation state from multiple sources

### 5. Type-Aware Metrics
✅ **DO**: Different storage for training vs data vs backtesting
❌ **DON'T**: Generic "metrics" dict for everything

---

## File Locations Reference

| Component | File |
|-----------|------|
| ServiceOrchestrator | `/ktrdr/async_infrastructure/service_orchestrator.py` |
| OperationsService | `/ktrdr/api/services/operations_service.py` |
| Cancellation System | `/ktrdr/async_infrastructure/cancellation.py` |
| Progress System | `/ktrdr/async_infrastructure/progress.py` |
| Data Models | `/ktrdr/api/models/operations.py` |
| Progress Bridge | `/ktrdr/api/services/training/progress_bridge.py` |
| Example: Training | `/ktrdr/api/services/training/local_orchestrator.py` |
| Example: Data | `/ktrdr/data/acquisition/acquisition_service.py` |

---

## Common Mistakes to Avoid

❌ **Don't**: Call `asyncio.create_task()` from worker thread
✅ **Do**: Use `loop.call_soon_threadsafe()` to schedule in main loop

❌ **Don't**: Store references to bridges without clearing
✅ **Do**: Let OperationsService manage bridge lifecycle

❌ **Don't**: Push metrics from worker threads
✅ **Do**: Store in bridge, let OperationsService pull on poll

❌ **Don't**: Forget to pass `operation_id` to operation_func
✅ **Do**: Include it in signature: `async def my_op(operation_id: str, **kwargs)`

❌ **Don't**: Ignore cancellation tokens
✅ **Do**: Check periodically: `if token.is_cancelled(): raise CancellationError()`

---

## Testing Checklist

- [ ] Operation creates with PENDING status
- [ ] Start transitions to RUNNING with started_at timestamp
- [ ] Progress updates are thread-safe (lock-free for updates)
- [ ] Cancellation token is created automatically
- [ ] Cancellation propagates to host service if remote
- [ ] Completion pulls final metrics from bridge
- [ ] Metrics are type-aware (epochs for training, segments for data)
- [ ] Cache prevents thundering herd (1s TTL)
- [ ] Cursor-based metrics work (new_cursor > old_cursor)
- [ ] Cleanup removes old operations (24h default)

