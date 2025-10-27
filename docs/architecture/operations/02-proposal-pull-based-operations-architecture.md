# Proposal: Pull-Based Operations Architecture

## Date
2025-01-20

## Status
PROPOSED - Awaiting review and implementation

## Overview

Replace the current PUSH-based operations model with a PULL-based architecture where producers write to fast local state and consumers poll/pull that state asynchronously.

## Core Principles

### 1. Producer Responsibility: Write State Only

**Producers** (training loops, data loaders, etc.) are responsible for:
- ✅ Updating local state with current progress/metrics
- ✅ Fast, synchronous operations only (dict updates)
- ✅ Zero I/O operations
- ✅ Zero blocking on consumer availability

**Producers are NOT responsible for:**
- ❌ Notifying consumers of updates
- ❌ Handling async/sync boundaries
- ❌ Persistence or I/O
- ❌ Managing event loops or threads

### 2. Consumer Responsibility: Poll and Persist

**Consumers** (orchestrators, progress monitors, persistence layers) are responsible for:
- ✅ Polling producer state periodically
- ✅ Handling all async I/O operations
- ✅ Persistence to databases/APIs
- ✅ Managing event loops and concurrency

**Consumers are NOT responsible for:**
- ❌ Being notified immediately of updates
- ❌ Blocking producer operations
- ❌ Running in producer's execution context

### 3. Bridge = State Container

The bridge component serves as a **shared state container**:
- Fast, in-memory state storage
- Thread-safe for concurrent reads/writes
- Synchronous-only interface (no async)
- No callbacks, no events, no I/O
- Producer writes, consumer reads

## Architectural Components

### Component 1: State Container (Bridge)

**Purpose:** Hold current operation state in memory

**Characteristics:**
- Synchronous-only methods
- Thread-safe data structures (no locks needed for simple dict/list appends)
- Zero I/O operations
- Properties for reading state
- Methods for writing state

**Responsibilities:**
- Store current progress (percentage, phase, message)
- Store metrics history (epochs, batches, etc.)
- Store operational metadata (start time, estimated completion)
- Provide read-only views of state

**NOT Responsible For:**
- Callbacks or notifications
- Persistence
- Async operations
- Event management

### Component 2: Producer (Training/Operations)

**Purpose:** Execute actual work and update state

**Characteristics:**
- Runs in worker thread (via asyncio.to_thread)
- Synchronous execution
- No async/await
- No event loop

**Interaction with Bridge:**
- Direct synchronous method calls: `bridge.on_epoch(...)`, `bridge.on_batch(...)`
- Fast state updates only
- Never blocks on bridge operations

**Example Producers:**
- ModelTrainer.train() - updates epoch/batch metrics
- DataLoader - updates loading progress
- IndicatorCalculator - updates calculation progress

### Component 3: Consumer Poller (Orchestrator)

**Purpose:** Poll bridge state and persist to storage

**Characteristics:**
- Runs in async context (has event loop)
- Periodically polls bridge state
- Performs async I/O to persist state
- Independent of producer execution

**Responsibilities:**
- Start background polling task before producer starts
- Poll bridge state at regular intervals (e.g., 500ms)
- Detect new metrics/progress updates
- Persist updates to OperationsService asynchronously
- Stop polling when producer completes

**Polling Strategy:**
- Track last persisted state (e.g., last_epoch_persisted)
- Compare with current bridge state
- Persist only new/changed data
- Handle errors without affecting producer

### Component 4: Persistence Layer (OperationsService)

**Purpose:** Store operation state for API consumption

**Characteristics:**
- Async methods for I/O operations
- Manages locks for concurrent access
- Handles persistence (memory, database, etc.)

**Interface:**
- Async methods: `add_metrics()`, `update_progress()`
- Called by consumer poller, not by producer
- Can be slow, perform I/O, retry, etc.

## Data Flow

### During Operation Execution

```
┌─────────────────────────────────────────┐
│ Producer (Worker Thread)                │
│  - ModelTrainer.train()                 │
│  - Synchronous execution                │
└────────────┬────────────────────────────┘
             │ Fast sync calls
             │ (on_epoch, on_batch)
             ▼
┌─────────────────────────────────────────┐
│ Bridge (State Container)                │
│  - _epoch_metrics: List[Dict]           │
│  - _current_progress: Dict              │
│  - Synchronous only                     │
└────────────┬────────────────────────────┘
             │ Periodic polling
             │ (read properties)
             ▼
┌─────────────────────────────────────────┐
│ Consumer Poller (Orchestrator Task)     │
│  - Async background task                │
│  - Polls every 500ms                    │
│  - Detects new data                     │
└────────────┬────────────────────────────┘
             │ Async I/O
             │ (add_metrics, update_progress)
             ▼
┌─────────────────────────────────────────┐
│ Persistence (OperationsService)         │
│  - Stores in operation.metrics          │
│  - Handles locks and concurrency        │
│  - Available via API                    │
└─────────────────────────────────────────┘
```

### State Read Flow

```
┌─────────────────────────────────────────┐
│ API Request: GET /operations/{id}/metrics│
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│ OperationsService.get_operation_metrics()│
│  - Returns operation.metrics            │
│  - Data was persisted by poller         │
└─────────────────────────────────────────┘
```

## Consistency Across Operation Types

### Local Training

```
LocalTrainingOrchestrator (Async Context)
    │
    ├─► Start background poller task
    │   └─► Polls bridge.epoch_metrics
    │       └─► Persists to OperationsService
    │
    └─► Run training in thread
        └─► ModelTrainer.train() (Sync)
            └─► bridge.on_epoch() (Fast state write)
```

### Host Service Training

```
HostSessionManager (Async Context)
    │
    └─► Polls remote service API
        └─► Gets metrics from host service
            └─► Persists to OperationsService
```

**Key Point:** Both use PULL model. Local polls bridge, host service polls API. Same pattern.

### Future Operations (Data Loading, etc.)

All future operations follow the same pattern:
1. Orchestrator starts background poller
2. Operation runs in thread, updates bridge
3. Poller persists bridge state to OperationsService

## Benefits

### Performance
- ✅ Producer never blocks (zero overhead beyond dict update)
- ✅ No sync/async bridging complexity in hot path
- ✅ Consumer can batch/optimize I/O independently

### Maintainability
- ✅ Clear separation of concerns
- ✅ Producer code is simple, sync-only
- ✅ Consumer code handles all complexity
- ✅ No callbacks, event loops, or queues in producer

### Consistency
- ✅ Same pattern for all operation types
- ✅ Local and host service use identical consumer pattern
- ✅ Easy to add new operation types

### Testability
- ✅ Bridge can be tested in isolation (simple state container)
- ✅ Producer can be tested without mocking async
- ✅ Consumer can be tested independently

### Real-Time Availability
- ✅ Metrics available during execution (via polling)
- ✅ Polling interval configurable (balance freshness vs. overhead)
- ✅ No blocking or waiting in producer

## Implementation Changes Required

### 1. TrainingProgressBridge

**Remove:**
- `metrics_callback` parameter
- Async callback invocation
- Event loop references

**Add:**
- `_epoch_metrics: List[Dict]` - stores epoch metrics
- `epoch_metrics` property - read-only access for consumers
- Thread-safe state storage (Python lists are thread-safe for append)

**Keep:**
- Existing progress tracking (percentage, phase, message)
- Synchronous interface
- Fast state updates

### 2. LocalTrainingOrchestrator

**Add:**
- `_poll_and_persist_metrics()` async method
- Background task management (start before training, stop after)
- Tracking of last persisted state (epoch number, etc.)

**Remove:**
- Metrics callback creation
- Callback passing to bridge

**Flow:**
- Start poller task
- Run training in thread (existing)
- Signal poller to stop
- Wait for final drain
- Return result

### 3. TrainingService

**Remove:**
- Metrics callback creation in `_run_local_training()`
- Metrics callback creation in `_run_host_training()`

**Keep:**
- Everything else (host service already polls correctly)

### 4. OperationsService

**No changes needed** - async interface is correct for consumer

## Polling Configuration

### Polling Interval
- Default: 500ms (2 updates per second)
- Configurable via environment variable: `OPERATIONS_POLL_INTERVAL_MS`
- Trade-off: Lower = more real-time, Higher = less overhead

### Drain Strategy
- On operation completion, perform final drain
- Ensure all metrics persisted before returning result
- Prevents race condition where API query happens before final persistence

## Migration Strategy

### Phase 1: Fix Local Training (Immediate)
1. Modify TrainingProgressBridge (remove callback, add storage)
2. Modify LocalTrainingOrchestrator (add poller)
3. Test with local training
4. Verify metrics appear in MCP client

### Phase 2: Validate Pattern (Short-term)
1. Verify host service training still works (should be unchanged)
2. Document pattern for future operations
3. Update architectural guidelines

### Phase 3: Apply to Other Operations (Future)
1. Data loading operations
2. Indicator calculations
3. Any new long-running operations

## Success Criteria

### Functional
- ✅ Metrics visible in MCP client during local training
- ✅ No "event loop" errors in logs
- ✅ Metrics updated within polling interval (500ms)
- ✅ All metrics persisted after training completion

### Architectural
- ✅ Producer code is sync-only
- ✅ No callbacks in bridge
- ✅ Consumer handles all async complexity
- ✅ Pattern consistent across operation types

### Performance
- ✅ Producer overhead < 1ms per update
- ✅ No blocking in producer thread
- ✅ Metrics fresh within polling interval

## Related Documents
- [01-problem-statement-producer-consumer-antipattern.md](./01-problem-statement-producer-consumer-antipattern.md) - Problem statement
- [../training/metrics-exposure/04-implementation-plan.md](../training/metrics-exposure/04-implementation-plan.md) - Original M2 plan (to be updated)
