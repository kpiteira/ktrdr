# Architecture: Pull-Based Operations System

## Document Information

**Date**: 2025-01-20
**Status**: DRAFT - Ready for Review
**Version**: 2.0
**Related Documents**:
- [Problem Statement](./01-problem-statement-producer-consumer-antipattern.md) - Why we need this change
- [Design Document](./04-design-pull-based-operations.md) - High-level design principles and patterns
- [Implementation Plan](./06-implementation-plan-pull-based-operations.md) - Step-by-step implementation guide

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architectural Principles](#2-architectural-principles)
3. [System Architecture](#3-system-architecture)
4. [Component Architecture](#4-component-architecture)
5. [Data Flow Patterns](#5-data-flow-patterns)
6. [API Contracts](#6-api-contracts)
7. [Deployment Architecture](#7-deployment-architecture)
8. [Quality Attributes](#8-quality-attributes)
9. [Migration Strategy](#9-migration-strategy)

---

## 1. Executive Summary

### 1.1 Purpose

This document defines the detailed architecture for the pull-based operations system in KTRDR, translating the design principles from [04-design-pull-based-operations.md](./04-design-pull-based-operations.md) into concrete component specifications, interfaces, and implementation guidance.

### 1.2 The Problem

The current operations system violates Python's threading model by attempting to call async methods from worker threads, causing "no running event loop" errors. See [Problem Statement](./01-problem-statement-producer-consumer-antipattern.md) for details.

### 1.3 The Solution

**Client-Driven Pull Architecture** where:
- **Workers** write to fast, synchronous ProgressBridge objects (no I/O, <1μs)
- **Clients** trigger refresh when querying OperationsService
- **TTL-based cache** prevents redundant refreshes (1-second freshness)
- **Same OperationsService** deployed in backend and host services
- **NO background polling tasks** - clients drive all refresh operations

### 1.4 Key Architectural Decisions

| Decision | Rationale | Reference |
|----------|-----------|-----------|
| **Client-driven refresh** | Work scales with demand, not time | [Design §3 Principle 2](./04-design-pull-based-operations.md#principle-2-lazy-evaluation) |
| **TTL cache** | Prevents redundant refresh when multiple clients poll | [Design §6](./04-design-pull-based-operations.md#why-cache-with-ttl) |
| **NO background polling** | Simpler, more predictable, less resource usage | [Design §7 Trade-off 5](./04-design-pull-based-operations.md#trade-off-5-client-driven-refresh-vs-internal-polling) |
| **Same code everywhere** | OperationsService identical in backend and host services | [Design §6](./04-design-pull-based-operations.md#why-same-code-everywhere) |
| **Sync-only bridge** | Workers in threads have no event loop | [Design §4.1](./04-design-pull-based-operations.md#41-progressbridge) |

---

## 2. Architectural Principles

These principles (from [Design Document §3](./04-design-pull-based-operations.md#3-core-principles)) govern all architectural decisions:

### 2.1 Locality of Reference
**State lives where it's produced.**

Workers write to ProgressBridge in their own process. No network calls, no I/O, no blocking.

```
Worker Thread → ProgressBridge (local memory, <1μs)
```

### 2.2 Lazy Evaluation
**Don't compute until needed.**

No background tasks polling "just in case." Refresh only happens when a client queries and cache is stale.

```
Client Query → Check Cache → If Stale: Refresh → Return Data
```

### 2.3 Cache as Contract
**Caching is explicit, not hidden.**

TTL (1 second default) is visible and configurable. Clients can force refresh with `force_refresh=True`.

### 2.4 Uniform Interfaces
**Same API works everywhere.**

OperationsService has identical endpoints whether in backend or host service. Same request, same response, same behavior.

### 2.5 Explicit Over Implicit
**Make state transitions visible.**

Workers explicitly call `complete_operation()`. HealthService explicitly checks timeouts. No background magic.

### 2.6 Separation of Concerns
**Each component has one job.**

- **ProgressBridge**: Hold state
- **OperationsService**: CRUD + cache operations
- **Adapters**: Route requests (local vs remote)
- **HealthService**: Monitor health

---

## 3. System Architecture

### 3.1 Layered Architecture

**Two execution contexts with identical pattern:**

#### Local Execution (Backend Docker Container)

```
┌──────────────────────────────────────────────────────┐
│ CLIENT LAYER                                         │
│  - CLI, MCP Client, Web UI, HealthService            │
└───────────────────┬──────────────────────────────────┘
                    │ HTTP: GET /operations/{id}
                    ▼
┌──────────────────────────────────────────────────────┐
│ API LAYER                                            │
│  FastAPI endpoints (/operations/*)                   │
└───────────────────┬──────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────┐
│ OPERATIONS SERVICE (Async)                           │
│  - Registry + Cache (TTL=1s)                         │
│  - Client query → Check cache → Refresh if stale     │
└───────────────────┬──────────────────────────────────┘
                    │ (same process)
                    ▼
┌──────────────────────────────────────────────────────┐
│ PROGRESS BRIDGE (Sync)                               │
│  - In-memory state                                   │
│  - get_state(), get_metrics(cursor)                  │
└───────────────────┬──────────────────────────────────┘
                    ▲ write (<1μs)
                    │
┌──────────────────────────────────────────────────────┐
│ WORKER (Thread)                                      │
│  Training loop, backtesting, etc.                    │
└──────────────────────────────────────────────────────┘
```

#### Remote Execution (Host Service Process)

```
┌──────────────────────────────────────────────────────┐
│ BACKEND                                              │
│  OperationsService                                   │
└───────────────────┬──────────────────────────────────┘
                    │ HTTP: GET localhost:5002/operations/{id}
                    ▼
┌──────────────────────────────────────────────────────┐
│ HOST SERVICE (Port 5001/5002)                        │
│  FastAPI + OperationsService (SAME CODE)             │
│  - Registry + Cache (TTL=1s)                         │
│  - Client query → Check cache → Refresh if stale     │
└───────────────────┬──────────────────────────────────┘
                    │ (same process)
                    ▼
┌──────────────────────────────────────────────────────┐
│ PROGRESS BRIDGE (Sync)                               │
│  - In-memory state                                   │
│  - get_state(), get_metrics(cursor)                  │
└───────────────────┬──────────────────────────────────┘
                    ▲ write (<1μs)
                    │
┌──────────────────────────────────────────────────────┐
│ WORKER (Thread)                                      │
│  GPU training, IB data loading                       │
└──────────────────────────────────────────────────────┘
```

**Key Insight**: Same architecture in both contexts. Backend's OperationsService queries host service's OperationsService, creating two-level cache.

### 3.2 Key Characteristics

**Backend (Docker)**:
- Manages operations for local training, backtesting, analysis
- Proxies requests to host services for IB data and GPU training
- Single OperationsService instance (singleton)

**Host Services (Ports 5001, 5002)**:
- IB Host Service (5001): Data loading operations
- Training Host Service (5002): GPU training operations
- Each runs identical OperationsService code
- Isolated operation registries (no shared state)

---

## 4. Component Architecture

### 4.1 ProgressBridge (State Container)

**Purpose**: Fast, synchronous state container that decouples workers from consumers.

**Architecture Pattern**: **Concrete Base Class** with protected helper methods for subclasses.

**Current Implementation**: `ktrdr/api/services/training/progress_bridge.py` (will be refactored to base + subclass)

#### Class Design

**ProgressBridge** is a **concrete class** (not abstract) providing:

1. **Consumer Interface** (public methods for OperationsService):
   - `get_status()` → returns current progress snapshot
   - `get_metrics(cursor)` → returns incremental metrics since cursor

2. **Producer Helpers** (protected methods for subclasses):
   - `_update_state(percentage, message, **kwargs)` → updates progress state
   - `_append_metric(metric_dict)` → appends metric to history

3. **State Storage** (internal):
   - `_current_state: dict` → latest progress snapshot
   - `_metrics_history: list[dict]` → append-only metrics
   - `_lock: threading.RLock` → thread safety

**Key Characteristics**:
- **Concrete, not abstract**: Can be instantiated directly (though typically subclassed)
- **Pure sync**: No `async`, no `await`, no event loops
- **No I/O**: All operations are memory-only
- **No callbacks outbound**: Bridge never calls external code
- **Thread-safe**: Uses RLock for all state access
- **Single writer, multiple readers**: Worker writes, OperationsService reads

#### Base Class Interface

```python
class ProgressBridge:
    """Concrete base class for pull-based progress tracking."""

    def __init__(self):
        """Initialize state storage and thread safety."""
        self._lock = threading.RLock()
        self._current_state: dict[str, Any] = {}
        self._metrics_history: list[dict] = []

    # PUBLIC INTERFACE (called by OperationsService)

    def get_status(self) -> dict[str, Any]:
        """Get current progress snapshot (thread-safe)."""
        with self._lock:
            return self._current_state.copy()

    def get_metrics(self, cursor: int = 0) -> tuple[list[dict], int]:
        """
        Get metrics since cursor (thread-safe, incremental).

        Args:
            cursor: Position in metrics history (0 = from beginning)

        Returns:
            (new_metrics, new_cursor) tuple
        """
        with self._lock:
            new_metrics = self._metrics_history[cursor:]
            new_cursor = len(self._metrics_history)
            return new_metrics, new_cursor

    # PROTECTED HELPERS (called by subclasses)

    def _update_state(self, percentage: float, message: str, **kwargs):
        """
        Update current state (called by subclass on_* methods).

        Thread-safe. Always includes timestamp.
        """
        with self._lock:
            self._current_state = {
                "percentage": percentage,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                **kwargs  # Domain-specific fields
            }

    def _append_metric(self, metric: dict):
        """
        Append metric to history (called by subclass).

        Thread-safe. Metric should include timestamp.
        """
        with self._lock:
            self._metrics_history.append(metric)
```

#### Subclass Pattern (Example: TrainingProgressBridge)

```python
class TrainingProgressBridge(ProgressBridge):
    """Training-specific progress bridge."""

    def __init__(self, context: TrainingOperationContext, ...):
        super().__init__()  # Initialize base class
        self._context = context
        self._total_epochs = context.total_epochs
        # ... training-specific state

    # DOMAIN-SPECIFIC CALLBACKS (called by training worker)

    def on_epoch(self, epoch: int, total: int, metrics: dict) -> None:
        """Report epoch completion."""
        percentage = (epoch / total) * 100.0
        message = f"Epoch {epoch}/{total}"

        # Update base class state
        self._update_state(
            percentage=percentage,
            message=message,
            epoch=epoch,
            total_epochs=total,
            # ... other training-specific fields
        )

        # Append epoch metric
        if metrics.get("progress_type") == "epoch":
            self._append_metric({
                "type": "epoch",
                "epoch": epoch,
                "train_loss": metrics.get("train_loss"),
                "val_loss": metrics.get("val_loss"),
                "timestamp": datetime.now().isoformat(),
            })

    def on_batch(self, epoch: int, batch: int, total: int, metrics: dict) -> None:
        """Report batch completion."""
        # Similar pattern: calculate state, call _update_state()
        # Optionally call _append_metric() for batch-level metrics
        pass

    def on_phase(self, phase: str, message: str = None) -> None:
        """Report phase change."""
        self._update_state(
            percentage=self._last_percentage,  # Keep current percentage
            message=message or phase,
            phase=phase,
        )
```

#### Why Concrete (Not Abstract)?

**Rationale**:
1. **Reusability**: Base class provides complete implementation, subclasses just add domain logic
2. **Simplicity**: No abstract methods to implement, just call protected helpers
3. **Flexibility**: Can instantiate base class directly for simple use cases
4. **Testing**: Base class can be tested independently

**NOT using ABC/abstractmethod because**:
- No methods are truly "abstract" (all have concrete implementations)
- Subclasses don't override base methods, they call protected helpers
- This is composition via protected methods, not template method pattern

#### State Model

```python
# State snapshot (returned by get_state())
{
    "percentage": float,       # 0-100
    "current_step": str,       # "Epoch 55/100"
    "phase": str,              # "training" | "validation" | "setup"
    "timestamp": float,        # time.time()
    "items_processed": int,    # Total items completed
}

# Metrics record (appended to _metrics_history)
{
    "timestamp": float,
    "metric_type": str,        # "epoch" | "batch" | "phase"
    # ... domain-specific fields
}
```

#### Thread Safety Model

**Single-Writer, Multiple-Reader with RLock**:

- **Writer (Worker Thread)**:
  ```python
  bridge.on_epoch(5, 100, metrics)  # Acquires lock, updates state, releases
  ```

- **Readers (OperationsService, multiple queries)**:
  ```python
  state = bridge.get_status()  # Acquires lock, copies state, releases
  metrics, cursor = bridge.get_metrics(cursor)  # Same
  ```

- **Guarantee**: Readers never see partial updates, all operations are atomic

**Performance**: RLock overhead is negligible (<0.1μs per acquire/release), far below the <1μs target for worker callbacks

---

### 4.2 OperationsService (CRUD + Cache)

**Purpose**: Central registry for operations with client-driven TTL-based refresh.

**Current Implementation**: `ktrdr/api/services/operations_service.py`

**Architecture Role**: Coordinator between clients (API consumers) and state sources (bridges/adapters).

#### Responsibilities

1. **Operation Registry**: CRUD operations for OperationInfo records
2. **Cache Management**: TTL-based freshness tracking per operation
3. **Refresh Coordination**: Routes refresh requests to appropriate source (bridge or adapter)
4. **Bridge/Adapter Registry**: Maintains references to state sources for active operations

#### Client-Driven Refresh Pattern

```
Client Query → Cache Check → [Stale?] → Refresh from Source → Update Cache → Return
                              ↓ Fresh
                          Return Cached ←─────────────────────────────┘
```

**Key Principle**: NO background polling. Refresh triggered ONLY by client queries when cache exceeds TTL.

#### State Management

**Operation States**:
```python
class OperationInfo:
    operation_id: str
    status: OperationStatus  # PENDING | RUNNING | COMPLETED | FAILED
    progress: OperationProgress
    metrics: dict
    metadata: dict  # Includes metrics_cursor for incremental reads
```

**Cache Metadata**:
```python
_last_refresh: dict[str, float]  # operation_id → last_refresh_timestamp
_cache_ttl: float = 1.0          # Default: 1 second
```

#### Source Registry

**Local Operations** (same process):
```python
_local_bridges: dict[str, ProgressBridge]
# operation_id → bridge reference
# Refresh: Direct memory read via bridge.get_state()
```

**Remote Operations** (host services):
```python
_remote_adapters: dict[str, OperationServiceProxy]
# operation_id → adapter (HTTP client)
# Refresh: HTTP GET to host service's OperationsService
```

#### Refresh Decision Logic

```python
async def get_operation(operation_id: str, force_refresh: bool = False) -> OperationInfo:
    """
    Refresh Logic:
    1. Completed/Failed operations → Never refresh (immutable)
    2. RUNNING operations:
       - force_refresh=True → Refresh immediately
       - Cache age > TTL → Refresh
       - Cache fresh → Return cached
    """
```

#### Interface Signatures

```python
class OperationsService:
    # Existing CRUD
    async def create_operation(...) -> OperationInfo
    async def get_operation(operation_id, force_refresh=False) -> OperationInfo
    async def list_operations(status=None, type=None) -> list[OperationInfo]
    async def complete_operation(operation_id, results) -> None

    # NEW: Source registration
    def register_local_bridge(operation_id, bridge: ProgressBridge) -> None
    def register_remote_adapter(operation_id, adapter: OperationServiceProxy) -> None

    # NEW: Refresh coordination (private)
    async def _refresh_operation(operation_id) -> None
    async def _refresh_from_bridge(operation_id, bridge) -> None
    async def _refresh_from_adapter(operation_id, adapter) -> None
```

#### Metrics Cursor Strategy

**Purpose**: Avoid returning ALL metrics on every query - only return delta since last query.

**Who Tracks Cursor**: Backend (consumer) tracks cursor per operation.

**Flow**:

1. **First Query** (backend has cursor=0):
   ```python
   # Backend to Host
   GET /operations/host_training_xyz/metrics?cursor=0

   # Host returns
   {
       "metrics": [metric_0, metric_1, ..., metric_99],  # All 100 metrics
       "new_cursor": 100
   }

   # Backend stores cursor=100 for this operation
   ```

2. **Second Query** (backend has cursor=100):
   ```python
   # Backend to Host
   GET /operations/host_training_xyz/metrics?cursor=100

   # Host returns ONLY new metrics since cursor 100
   {
       "metrics": [metric_100, metric_101, ..., metric_109],  # Only 10 new metrics
       "new_cursor": 110
   }

   # Backend stores cursor=110
   ```

3. **No New Metrics** (cursor unchanged):
   ```python
   # Backend to Host
   GET /operations/host_training_xyz/metrics?cursor=110

   # Host returns empty (no new metrics)
   {
       "metrics": [],
       "new_cursor": 110  # Cursor unchanged
   }
   ```

**Implementation**:
- **Bridge**: Implements `get_metrics(cursor)` → returns `metrics[cursor:]`
- **Host Service**: Passes cursor to bridge, returns delta
- **Backend**: Tracks cursor per operation, passes to host/bridge

**Benefit**: With 100 epochs, first query transfers 100 metrics, subsequent queries transfer ~1 metric each (99% reduction).

#### Deployment Invariant

**Same code deployed in**:
- Backend API (Docker port 8000)
- IB Host Service (port 5001)
- Training Host Service (port 5002)

**Effect**: Two-level caching
- Backend cache: Prevents redundant HTTP calls
- Host service cache: Prevents redundant bridge reads

---

### 4.3 OperationServiceProxy (HTTP Client)

**Purpose**: Generic HTTP client for OperationsService API on host services.

**Location**: `ktrdr/api/services/adapters/operation_service_proxy.py` (new file)

**Architecture Role**: Provides unified HTTP interface to remote OperationsService instances, shared across all service adapters.

#### Design Pattern

**Composition over duplication**: TrainingAdapter, IbDataAdapter, etc. compose OperationServiceProxy rather than implementing HTTP calls independently.

```
TrainingAdapter
  ├─ Domain methods: start_training(), get_result()
  └─ Operations queries: Delegates to OperationServiceProxy

IbDataAdapter
  ├─ Domain methods: fetch_data(), validate_symbol()
  └─ Operations queries: Delegates to SAME OperationServiceProxy
```

#### Interface

```python
class OperationServiceProxy:
    """HTTP client for OperationsService API."""

    async def get_operation(operation_id, force_refresh=False) -> OperationInfo
    async def get_metrics(operation_id, cursor) -> tuple[list[dict], int]
    async def complete_operation(operation_id, results) -> None
```

#### Behavior

**Transparent pass-through**:
- Backend calls `proxy.get_operation()`
- Proxy makes HTTP GET to host service
- Host service's OperationsService checks ITS cache
- Host service refreshes from ITS local bridge if stale
- Response returned to backend

**Effect**: Two-level caching without coordination.

---

### 4.4 HealthService (Monitoring Client)

**Purpose**: External monitoring service that detects operation failures via timeout.

**Location**: `ktrdr/api/services/health_service.py` (new file)

**Architecture Role**: Consumer of OperationsService API (not internal component).

#### Key Architectural Point

**HealthService polling ≠ OperationsService internal polling**

```
❌ WRONG: OperationsService polls bridges internally
✅ CORRECT: HealthService polls OperationsService API (as external client)
```

#### Monitoring Strategy

**Periodic queries** (every 60 seconds):
1. `list_operations(status=RUNNING)` → triggers refresh of stale operations
2. Check each operation for:
   - **Timeout**: `updated_at` older than threshold (30 min)
   - **Stuck**: Progress percentage unchanged for 10 min

**Failure actions**:
- Timeout → `fail_operation()` with timeout message
- Stuck → Log warning (operations may be legitimately slow)

#### Interface

```python
class HealthService:
    async def start_monitoring() -> None
    async def stop_monitoring() -> None
```

#### Separation of Concerns

- **OperationsService**: Has no knowledge of health monitoring
- **HealthService**: Uses public OperationsService API only
- **Configuration**: Health thresholds independent of cache TTL

---

## 5. Data Flow Patterns

### 5.1 Local Operation - Worker Progress Update

**Scenario**: Training loop completes an epoch.

```
┌─────────────────────────────────────────────────────────────┐
│ WORKER THREAD (Sync Context)                               │
│                                                             │
│  for epoch in range(total_epochs):                         │
│      train_one_epoch()                                      │
│      # Report progress                                      │
│      bridge.on_epoch(epoch, total, metrics)  <─────┐       │
│          │                                          │       │
│          │ <1μs (dict update + list append)        │       │
│          ▼                                          │       │
│      Bridge Memory:                                 │       │
│      - _state: {"percentage": 50, ...}              │       │
│      - _metrics_history: [metric1, metric2, ...]   │       │
│                                                             │
│  # Worker continues immediately (not blocked)               │
└─────────────────────────────────────────────────────────────┘
```

**Key Points**:
- Worker writes to local memory (fast, <1μs)
- NO async/await in worker code
- NO I/O operations
- Bridge just stores state passively

---

### 5.2 Local Operation - Client Query (Cache Hit)

**Scenario**: Multiple clients poll the same operation within 1 second.

```
Time: 10:00:00.000
┌──────┐
│Client│ GET /operations/op_123
└──┬───┘
   ├──> API Endpoint
   │    └──> operations_service.get_operation("op_123")
   │         ├─ Check cache: last_refresh = 10:00:00.000
   │         ├─ now = 10:00:00.000
   │         ├─ staleness = 0s < 1s (fresh!)
   │         └─ Return cached data (instant)
   │
   └─── 200 OK (data from cache)

Time: 10:00:00.500 (500ms later)
┌──────┐
│Client│ GET /operations/op_123
└──┬───┘
   ├──> API Endpoint
   │    └──> operations_service.get_operation("op_123")
   │         ├─ Check cache: last_refresh = 10:00:00.000
   │         ├─ now = 10:00:00.500
   │         ├─ staleness = 0.5s < 1s (still fresh!)
   │         └─ Return cached data (instant)
   │
   └─── 200 OK (data from cache, no refresh)
```

**Key Points**:
- First client refreshes cache
- Subsequent clients hit cache (fast)
- No redundant bridge reads within TTL window

---

### 5.3 Local Operation - Client Query (Cache Miss / Stale)

**Scenario**: Client queries after cache TTL expired.

```
Time: 10:00:01.200 (1.2s after last refresh)
┌──────┐
│Client│ GET /operations/op_123
└──┬───┘
   ├──> API Endpoint
   │    └──> operations_service.get_operation("op_123")
   │         ├─ Check cache: last_refresh = 10:00:00.000
   │         ├─ now = 10:00:01.200
   │         ├─ staleness = 1.2s > 1s (stale!)
   │         │
   │         ├─ Trigger refresh:
   │         │  └──> _refresh_from_bridge(op_123, bridge)
   │         │       ├─ state = bridge.get_state()  ──┐
   │         │       │   (read from local memory)     │
   │         │       │                                │
   │         │       ├─ cursor = 5                    │
   │         │       ├─ metrics, new_cursor =         │
   │         │       │      bridge.get_metrics(5) ────┤
   │         │       │   (incremental read)           │
   │         │       │                                │
   │         │       ├─ update_progress(state)        │
   │         │       ├─ add_metrics(metrics)          │
   │         │       └─ cursor = new_cursor           │
   │         │                                         │
   │         ├─ Update cache: last_refresh = now      │
   │         └─ Return refreshed data                 │
   │                                                   │
   └─── 200 OK (fresh data)                          │
                                                      │
┌──────────────────────────────────────────────────┐ │
│ ProgressBridge (Same Process)                   │◄┘
│                                                  │
│  _state = {                                      │
│      "percentage": 55.0,  # Fresh value         │
│      "current_step": "Epoch 55/100",            │
│      "timestamp": 10:00:01.150                  │
│  }                                               │
│                                                  │
│  _metrics_history = [                            │
│      {epoch: 0, loss: 2.5, ...},  # cursor=0    │
│      {epoch: 1, loss: 2.3, ...},  # cursor=1    │
│      ...                                         │
│      {epoch: 5, loss: 1.8, ...},  # cursor=5    │
│      {epoch: 6, loss: 1.7, ...},  # cursor=6 ← new
│  ]                                               │
└──────────────────────────────────────────────────┘
```

**Key Points**:
- Cache staleness triggers refresh
- Refresh reads from bridge (local memory, fast)
- Incremental metrics (cursor-based, efficient)
- Cache updated, next query hits cache

---

### 5.4 Remote Operation - Client Query

**Scenario**: Client queries training running in host service.

```
┌──────┐
│Client│ GET /operations/op_456
└──┬───┘
   ├──> Backend API Endpoint
   │    └──> backend_ops_service.get_operation("op_456")
   │         ├─ Check cache: stale (or force_refresh)
   │         │
   │         ├─ Trigger refresh:
   │         │  └──> _refresh_from_adapter(op_456, adapter)
   │         │       └──> adapter.get_operation("op_456")
   │         │            │
   │         │            ├─ HTTP GET localhost:5002/operations/op_456
   │         │            │
   ┌─────────────────────────────────────────────────────────┐
   │ Host Service (Port 5002)                                │
   │                                                          │
   │  FastAPI Endpoint                                       │
   │  └──> host_ops_service.get_operation("op_456")          │
   │       ├─ Check ITS cache: stale                         │
   │       ├─ Trigger ITS refresh:                           │
   │       │  └──> _refresh_from_bridge(op_456, bridge) ──┐  │
   │       │       ├─ state = bridge.get_state()          │  │
   │       │       │   (local memory in host)             │  │
   │       │       └─ metrics = bridge.get_metrics(...)   │  │
   │       │                                               │  │
   │       ├─ Update host cache                           │  │
   │       └─ Return OperationInfo (HTTP 200)             │  │
   │            │                                          │  │
   │       ┌────────────────────┐                          │  │
   │       │ ProgressBridge     │◄─────────────────────────┘  │
   │       │ (Host Process)     │                             │
   │       │ - _state: {...}    │                             │
   │       │ - _metrics: [...]  │                             │
   │       └────────────────────┘                             │
   │            ▲                                              │
   │            │ Worker writes (local, fast)                 │
   │       ┌────────────────────┐                             │
   │       │ Training Worker    │                             │
   │       │ (GPU Thread)       │                             │
   │       └────────────────────┘                             │
   └──────────────────────────────────────────────────────────┘
                │
                │ HTTP Response: OperationInfo
                ▼
   │         │  Backend receives OperationInfo
   │         ├─ Update backend cache
   │         └─ Return to client
   │
   └─── 200 OK
```

**Two-Level Caching Explained**:

**Level 1 - Bridge Memory (Nanosecond Access)**:
- Worker writes to ProgressBridge in-memory state
- Bridge holds current snapshot + metrics history
- This IS a cache - avoids recomputing progress

**Level 2 - TTL Cache (Millisecond Savings)**:
- Backend caches last bridge read with timestamp
- Prevents redundant bridge reads when multiple clients poll
- TTL=1s means: If queried within 1 second, return cached data
- Host service has its own TTL cache for the same reason

**Why Two Levels?**:
- **Level 1 (Bridge)**: Eliminates worker computation overhead
- **Level 2 (TTL)**: Eliminates redundant bridge reads + HTTP calls

**Performance Impact**:
- No cache: Every client query → HTTP → bridge read (>50ms)
- Level 2 cache: First client → HTTP (50ms), next 3 clients → instant (<1ms)
- With 4 clients polling every 5s: 75% reduction in HTTP calls

**Key Points**:
- Two-level caching (bridge memory + backend/host TTL)
- Both use same OperationsService code
- Host service refresh is local (fast)
- Network only when backend cache stale

---

### 5.5 Worker Completion

**Scenario**: Training finishes successfully.

**Local Operation**:
```
┌─────────────────────────────────────────────────┐
│ LocalTrainingOrchestrator                       │
│                                                 │
│  async def run_training():                      │
│      bridge = ProgressBridge(...)               │
│      ops_service.register_local_bridge(op_id, bridge)
│                                                 │
│      # Run training in thread                   │
│      result = await asyncio.to_thread(          │
│          train_strategy, bridge                 │
│      )                                          │
│                                                 │
│      # Worker returned - training complete      │
│      await ops_service.complete_operation(      │
│          op_id, results=result                  │
│      )                                          │
│                                                 │
│      ops_service.unregister_local_bridge(op_id) │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Host Service Operation** (NEW - Pull Architecture):
```
┌─────────────────────────────────────────────────┐
│ Host Service                                    │
│                                                 │
│  HostTrainingOrchestrator (SAME CODE AS LOCAL!) │
│                                                 │
│  async def run_training():                      │
│      bridge = ProgressBridge(...)               │
│      host_ops_service.register_local_bridge(    │
│          host_op_id, bridge                     │
│      )                                          │
│                                                 │
│      # Run training in thread                   │
│      result = await asyncio.to_thread(          │
│          train_strategy, bridge                 │
│      )                                          │
│                                                 │
│      # Worker returned - training complete      │
│      await host_ops_service.complete_operation( │
│          host_op_id, results=result             │
│      )                                          │
│                                                 │
│      host_ops_service.unregister_local_bridge(  │
│          host_op_id                             │
│      )                                          │
│                                                 │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Backend                                         │
│                                                 │
│  # On training start                            │
│  proxy = OperationServiceProxy(host_url)        │
│  backend_ops_service.register_remote_proxy(     │
│      backend_op_id, proxy                       │
│  )                                              │
│                                                 │
│  # Client queries progress                      │
│  GET /operations/{backend_op_id}                │
│    → backend_ops_service.get_operation()        │
│    → proxy.get_operation(host_op_id) [HTTP]    │
│    → host returns status=COMPLETED              │
│    → backend sees completion, fetches results   │
│    → backend_ops_service.complete_operation()   │
│    → backend operation status = COMPLETED       │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Key Architectural Point: CONVERGENCE**

After pull architecture, local and host training use **THE SAME ORCHESTRATOR CODE**:

| Aspect | Local Training | Host Training |
|--------|---------------|---------------|
| **Orchestrator** | TrainingOrchestrator | **SAME TrainingOrchestrator** |
| **Bridge** | ProgressBridge | **SAME ProgressBridge** |
| **Worker** | Calls `bridge.on_epoch()` | **SAME** calls `bridge.on_epoch()` |
| **Completion** | Calls `ops_service.complete_operation()` | **SAME** calls `host_ops_service.complete_operation()` |
| **Location** | Backend process | Host service process |
| **Access** | Direct bridge reference | HTTP proxy to host service |

**Completion Detection** (NO POLLING):
- ❌ **NOT**: Background task polls for completion
- ✅ **YES**: Client queries trigger completion discovery
- ✅ **YES**: HealthService (external monitor) queries periodically for stuck/timeout detection
- **Flow**: Host worker completes → client queries → backend discovers → marks complete

**Key Points**:
- Local and Host: **Same code, different location**
- Completion is explicit (worker calls `complete_operation()`), not inferred
- Backend discovers completion **when clients query** (client-driven)
- No background polling tasks (only HealthService external monitoring)

---

## 5.5 Backend Routing Logic: Local vs Host

**Critical Architectural Detail**: Backend initialization differs based on training location.

### Routing Decision

Backend's `TrainingService.train()` method routes based on configuration:

```python
def should_use_host_service(request: TrainingRequest) -> bool:
    """Determine if training should run on host service."""
    # Environment variable controls routing
    use_host = os.getenv("USE_TRAINING_HOST_SERVICE", "false").lower() == "true"

    # Or: decision based on request properties (GPU needed, etc.)
    # requires_gpu = request.config.get("use_gpu", False)
    # return use_host and requires_gpu

    return use_host
```

### Local Training Path

**Backend runs orchestrator in-process**:

```python
async def train_local(request: TrainingRequest) -> str:
    # Create operation
    operation_id = ops_service.create_operation(
        operation_type=OperationType.TRAINING,
        ...
    )

    # Create bridge for this operation
    bridge = ProgressBridge()
    ops_service.register_local_bridge(operation_id, bridge)

    # Create and run orchestrator IN BACKEND PROCESS
    orchestrator = TrainingOrchestrator(
        config=request.config,
        symbols=request.symbols,
        bridge=bridge,
        ops_service=ops_service,
        ...
    )

    # Run training (blocks until complete)
    result = await orchestrator.run()

    # Orchestrator calls ops_service.complete_operation() on finish
    return operation_id
```

**Flow**:
1. Backend creates operation
2. Backend creates bridge
3. Backend registers local bridge
4. **Backend runs orchestrator**
5. Orchestrator completes operation
6. Return operation_id to client

### Host Training Path

**Backend proxies requests to host service**:

```python
async def train_host(request: TrainingRequest) -> str:
    # Create operation in BACKEND
    operation_id = ops_service.create_operation(
        operation_type=OperationType.TRAINING,
        ...
    )

    # (1) PROXY TRAINING START REQUEST to host service
    host_response = await training_adapter.train_multi_symbol_strategy(
        symbols=request.symbols,
        config=request.config,
        # HTTP POST to host service /training/start
    )
    session_id = host_response["session_id"]

    # (2) REGISTER PROXY FOR OPERATIONS QUERIES
    host_op_id = f"host_training_{session_id}"
    proxy = OperationServiceProxy(
        base_url=os.getenv("TRAINING_HOST_SERVICE_URL")
    )
    ops_service.register_remote_proxy(operation_id, proxy)

    # Store mapping for later queries
    operation.metadata["session_id"] = session_id
    operation.metadata["host_operation_id"] = host_op_id

    # BACKEND RETURNS IMMEDIATELY (no orchestrator here!)
    return operation_id
```

**Flow**:
1. Backend creates operation
2. **Backend proxies training start to host** (HTTP call)
3. Host service creates its own operation + bridge + orchestrator
4. Backend registers proxy (not bridge!)
5. **Backend returns immediately**
6. Host runs orchestrator (backend has no orchestrator)
7. Clients query backend → backend pulls from host via proxy

### Key Architectural Differences

| Aspect | Local Training | Host Training |
|--------|---------------|---------------|
| **Training Request** | Process in backend | **Proxy to host service (HTTP)** |
| **Orchestrator Creation** | Backend creates | **Host service creates** |
| **Orchestrator Execution** | Backend runs | **Host service runs** |
| **Bridge Creation** | Backend creates | **Host service creates** |
| **Bridge Location** | Backend memory | **Host service memory** |
| **Registration** | `register_local_bridge(op_id, bridge)` | `register_remote_proxy(op_id, proxy)` |
| **Backend Returns** | After orchestrator completes | **Immediately after proxy registration** |
| **Completion** | Direct (orchestrator calls complete) | **Discovered via client query** |

### Unified Client Experience

**Despite different initialization, clients see identical API**:

```python
# Client doesn't know if local or host
operation_id = await client.post("/training/start", json=request)

# Same query API for both
while True:
    operation = await client.get(f"/operations/{operation_id}")
    if operation["status"] == "COMPLETED":
        break
    await asyncio.sleep(5)
```

**Backend handles routing transparently**:
- Local: `get_operation()` → direct bridge access
- Host: `get_operation()` → proxy → HTTP → host service → host bridge

---

## 6. API Contracts

### 6.1 OperationsService API (Backend & Host Services)

**Same endpoints in both backend and host services.**

#### GET /operations/{operation_id}

**Request**:
```
GET /api/v1/operations/op_training_20250120_abc123?force_refresh=false
```

**Response**:
```json
{
  "operation_id": "op_training_20250120_abc123",
  "status": "RUNNING",
  "operation_type": "TRAINING",
  "created_at": "2025-01-20T10:00:00Z",
  "updated_at": "2025-01-20T10:05:30Z",
  "progress": {
    "percentage": 55.0,
    "current_step": "Epoch 55/100",
    "message": "Training in progress",
    "items_processed": 55000,
    "total_items": 100000
  },
  "metadata": {
    "symbol": "AAPL",
    "timeframe": "1d"
  }
}
```

**Behavior**:
1. Check cache freshness
2. If stale or `force_refresh=true`: Refresh from source (bridge or adapter)
3. Return data

#### GET /operations

**Request**:
```
GET /api/v1/operations?status=RUNNING&operation_type=TRAINING
```

**Response**:
```json
{
  "operations": [
    {
      "operation_id": "op_training_20250120_abc123",
      "status": "RUNNING",
      ...
    },
    ...
  ],
  "count": 3
}
```

**Behavior**:
1. Refresh all stale RUNNING operations
2. Filter by status/type
3. Return list

#### GET /operations/{operation_id}/metrics

**Request**:
```
GET /api/v1/operations/op_training_123/metrics?cursor=5
```

**Response**:
```json
{
  "metrics": [
    {
      "timestamp": 1705756815.456,
      "metric_type": "epoch",
      "epoch": 6,
      "train_loss": 1.7,
      "val_loss": 1.8,
      "train_acc": 0.65,
      "val_acc": 0.63
    },
    {
      "epoch": 7,
      ...
    }
  ],
  "new_cursor": 8
}
```

**Behavior**:
1. Refresh operation if stale
2. Return metrics since cursor
3. Return new cursor for next incremental read

#### POST /operations/{operation_id}/complete

**Request**:
```json
{
  "results": {
    "final_loss": 0.42,
    "best_epoch": 87,
    "model_path": "/models/model_v1.pkl"
  }
}
```

**Response**:
```json
{
  "status": "success",
  "operation_id": "op_training_123"
}
```

**Behavior**:
1. Mark operation as COMPLETED
2. Store results
3. Set completed_at timestamp

---

## 7. Deployment Architecture

### 7.1 Process Layout

```
┌─────────────────────────────────────────────────────────────┐
│ Docker Container (ktrdr-backend)                            │
│  Port: 8000                                                 │
│                                                             │
│  ┌─────────────────────────────────────────┐               │
│  │ FastAPI Application                     │               │
│  │  - API endpoints                        │               │
│  │  - OperationsService (singleton)        │               │
│  │  - HealthService                        │               │
│  │  - LocalTrainingOrchestrator            │               │
│  │  - Service adapters (training, ib)      │               │
│  └─────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────┘
                     │
                     │ HTTP (host.docker.internal)
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌──────────────────┐     ┌──────────────────┐
│ IB Host Service  │     │Training Host Svc │
│  Port: 5001      │     │  Port: 5002      │
│  (Native macOS)  │     │  (Native macOS)  │
│                  │     │                  │
│  FastAPI App     │     │  FastAPI App     │
│  - OperationsService   │  - OperationsService
│  - /operations/* │     │  - /operations/* │
│  - /data/*       │     │  - /training/*   │
│                  │     │                  │
│  IB Gateway      │     │  PyTorch + MPS   │
│  (Port 4002)     │     │  (GPU)           │
└──────────────────┘     └──────────────────┘
```

### 7.2 Configuration

**Backend (Docker)**:
```python
# Environment variables
USE_IB_HOST_SERVICE=true
USE_TRAINING_HOST_SERVICE=true
IB_HOST_SERVICE_URL=http://host.docker.internal:5001
TRAINING_HOST_SERVICE_URL=http://host.docker.internal:5002

OPERATIONS_CACHE_TTL=1.0  # seconds
```

**Host Services**:
```python
# training-host-service/config.py
HOST=0.0.0.0
PORT=5002
OPERATIONS_CACHE_TTL=1.0  # same as backend
```

---

## 8. Quality Attributes

### 8.1 Performance

| Metric | Target | How Achieved |
|--------|--------|--------------|
| Worker overhead | <1μs per update | Sync-only bridge, memory writes only |
| Cache hit latency | <1ms | In-memory dict lookup |
| Cache miss (local) | <10ms | Fast memory read from bridge |
| Cache miss (remote) | <50ms | HTTP + host service local refresh |
| Memory per operation | <500KB | State + metrics history |

**Validation Strategy**:
```python
def benchmark_bridge():
    bridge = ProgressBridge(context)

    start = time.perf_counter()
    for i in range(10000):
        bridge.on_epoch(i, 100, {"loss": 1.5})
    end = time.perf_counter()

    avg = (end - start) / 10000
    assert avg < 0.000001  # <1μs
```

### 8.2 Reliability

**Failure Modes**:

| Component | Failure | Impact | Mitigation |
|-----------|---------|--------|------------|
| Worker crash | Exception in training | Operation stuck in RUNNING | HealthService timeout detection |
| Bridge memory | Out of memory | Operation fails | Limit metrics history size |
| Host service down | HTTP timeout | Stale data in backend | Retry with backoff, mark failed after N attempts |
| Network partition | Backend can't reach host | Stale data | Cache TTL prevents infinite staleness |

**Health Monitoring**:
- HealthService checks RUNNING operations every 60s
- Timeout threshold: 30 minutes
- Stuck detection: Progress unchanged for 10 minutes

### 8.3 Maintainability

**Code Complexity Reduction**:
- **Before**: Dual callback paths (sync PUSH → async), 15 files, ~3000 LOC
- **After**: Unified client-driven pull, 8 files, ~1500 LOC
- **Reduction**: 50% fewer lines, 47% fewer files

**Testing Strategy**:

```python
# Unit Tests (Fast)
class TestProgressBridge:
    def test_on_epoch_updates_state(self):
        bridge = ProgressBridge(context)
        bridge.on_epoch(5, 100, {"loss": 1.5})

        state = bridge.get_state()
        assert state["percentage"] == 5.0

    def test_get_metrics_incremental(self):
        bridge = ProgressBridge(context)
        bridge.on_epoch(0, 10, {"loss": 2.5})
        bridge.on_epoch(1, 10, {"loss": 2.3})

        metrics, cursor = bridge.get_metrics(0)
        assert len(metrics) == 2
        assert cursor == 2

        # Next read (incremental)
        metrics, cursor = bridge.get_metrics(cursor)
        assert len(metrics) == 0

# Integration Tests
class TestOperationsServiceRefresh:
    async def test_refresh_from_bridge(self):
        ops_service = OperationsService()
        bridge = ProgressBridge(context)

        # Create operation
        op = await ops_service.create_operation(...)
        ops_service.register_local_bridge(op.operation_id, bridge)

        # Worker updates bridge
        bridge.on_epoch(5, 100, {"loss": 1.5})

        # Client queries (triggers refresh)
        await asyncio.sleep(1.1)  # Exceed TTL
        result = await ops_service.get_operation(op.operation_id)

        assert result.progress.percentage == 5.0
```

### 8.4 Scalability

**Concurrent Operations**:
- Single OperationsService handles all operations
- No per-operation background tasks
- Memory: O(active operations)
- CPU: O(client queries), not O(time)

**Limits**:
- 100 concurrent operations: ~50MB memory
- 1000 client queries/second: Cache prevents redundant refresh

---

## 9. Migration Strategy

### 9.1 Phased Implementation

**Phase 1: Foundation** (No Breaking Changes)
- [ ] Create new `get_state()` and `get_metrics()` methods on ProgressBridge
- [ ] Add cache management to OperationsService (`_last_refresh`, `_cache_ttl`)
- [ ] Add bridge registration methods
- [ ] NO changes to existing behavior (coexist)

**Phase 2: Enable Client-Driven Refresh** (Feature Flag)
- [ ] Implement `_refresh_from_bridge()` logic
- [ ] Modify `get_operation()` to check cache and refresh
- [ ] Add `force_refresh` parameter
- [ ] Feature flag: `USE_CLIENT_DRIVEN_REFRESH=false` (default off)

**Phase 3: Testing & Validation**
- [ ] Integration tests with flag enabled
- [ ] Performance benchmarks
- [ ] Enable flag in dev environment
- [ ] Monitor for 1 week

**Phase 4: Cutover**
- [ ] Set `USE_CLIENT_DRIVEN_REFRESH=true` by default
- [ ] Remove old callback-based code
- [ ] Deploy to production
- [ ] Monitor for 1 week

**Phase 5: Cleanup**
- [ ] Remove feature flag
- [ ] Remove deprecated code paths
- [ ] Update documentation

### 9.2 Rollback Plan

If issues discovered:
1. **Immediate**: Set `USE_CLIENT_DRIVEN_REFRESH=false`
2. **Investigation**: Analyze logs, metrics
3. **Fix**: Address architecture issues
4. **Re-enable**: After validation

**Rollback Metrics**:
- Operation completion rate drops >10% → rollback
- Metrics missing from >1% operations → rollback
- Unhandled exceptions increase → immediate rollback

---

## Appendix A: Comparison with Current Architecture

| Aspect | Current (PUSH + Internal Polling) | New (Client-Driven PULL) |
|--------|-----------------------------------|--------------------------|
| **Worker Progress** | Calls async callback from sync thread ❌ | Writes to sync bridge ✅ |
| **Worker Overhead** | 870μs (if it worked) | <1μs (measured) |
| **Background Tasks** | Per-operation polling tasks | None (only HealthService) |
| **Refresh Trigger** | Time-based (polling interval) | Client query (on-demand) |
| **Cache** | Implicit (polling updates registry) | Explicit (TTL-based) |
| **Local vs Remote** | Different code paths | Same code path |
| **OperationsService** | Backend only | Backend + host services (same code) |
| **Metrics Storage** | Callback-based (broken) | Pull-based (working) |
| **Code Complexity** | 3000 LOC, 15 files | 1500 LOC, 8 files |

---

## Appendix B: References

1. [Problem Statement](./01-problem-statement-producer-consumer-antipattern.md) - Threading issues
2. [Design Document](./04-design-pull-based-operations.md) - High-level design
3. [Implementation Plan](./06-implementation-plan-pull-based-operations.md) - Tasks
4. Current Code:
   - `ktrdr/api/services/operations_service.py` - OperationsService
   - `ktrdr/api/services/training/progress_bridge.py` - ProgressBridge
   - `ktrdr/api/services/training/local_orchestrator.py` - Orchestrator

---

**Document Version**: 2.0
**Last Updated**: 2025-01-20
**Next Review**: After implementation Phase 1
