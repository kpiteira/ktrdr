# Design Document: Backtesting Async Operations Architecture

## Document Information
- **Date**: 2025-01-03 (Revised)
- **Version**: 2.0
- **Status**: PROPOSED
- **Related Documents**:
  - [docs/architecture/operations/04-design-pull-based-operations.md](../operations/04-design-pull-based-operations.md) - Foundation pull-based architecture
  - [docs/architecture/operations/05-architecture-pull-based-operations.md](../operations/05-architecture-pull-based-operations.md) - Operations Service architecture
  - [docs/architecture/async/ARCHITECTURE.md](../async/ARCHITECTURE.md) - Async infrastructure patterns

---

## Executive Summary

This document describes the modernization of KTRDR's backtesting system to use the **pull-based operations architecture**, matching the patterns established for data loading and training.

**The Core Architecture**: Client-driven pull with Operations Service coordination (NO polling).

**The Result**: BacktestingService inherits from ServiceOrchestrator, uses ProgressBridge for state, and supports two execution modes:
1. **Local**: In-container execution with ProgressBridge
2. **Remote**: Container on different machine with OperationServiceProxy

**Key Distinction**: Unlike training (native host service for GPU), backtesting's remote mode is a **containerized service** enabling distributed backtesting across machines.

---

## Table of Contents

1. [The Design](#the-design)
2. [Architecture Overview](#architecture-overview)
3. [Core Principles](#core-principles)
4. [Component Design](#component-design)
5. [Execution Modes](#execution-modes)
6. [Design Rationale](#design-rationale)
7. [Trade-offs and Decisions](#trade-offs-and-decisions)
8. [Success Criteria](#success-criteria)

---

## 1. The Design

### The Big Picture

Imagine a simple world where:

1. **Workers just work**: BacktestingEngine runs event loop, writes progress to ProgressBridge. Pure synchronous work. No I/O, no async.

2. **State lives with workers**: Every worker has a ProgressBridge—a lightweight state container. Workers write to it (<1μs), and it just holds the latest state.

3. **Clients pull when they need**: When a client asks "how's my backtest doing?", OperationsService checks: "Do I have fresh data (TTL check)? Yes → return cached. No → pull from bridge/proxy, cache it, return it."

4. **Same pattern everywhere**: Whether backtesting runs locally (same container) or remotely (different machine), the pattern is identical. The only difference is whether we read the bridge from memory (local) or over HTTP (remote).

5. **No background magic**: No polling loops. No background tasks. Clients drive everything via OperationsService. When no one's watching, the system does nothing.

That's it. That's the whole design.

### The Key Innovation

**Pull-Based Operations with Client-Driven Refresh** (from `docs/architecture/operations/04-design-pull-based-operations.md`):

```
Traditional (PUSH + Polling):
Worker → Callback → Async boundary issues ❌
Background task polls → Redundant work ❌

Pull Architecture (CURRENT):
Worker → ProgressBridge (local write, <1μs) ✅
Client query → OperationsService → Check cache (TTL) → Pull if stale ✅
(Worker never blocked, no redundant work)
```

### Why This Works

**For Local Execution** (backtesting in Docker):
- Worker thread writes to ProgressBridge in same process (memory write, <1μs)
- Client queries trigger Operations Service cache check
- If stale (>TTL), pull from bridge (memory read)
- Fast, simple, no threading issues

**For Remote Execution** (backtesting on different machine):
- Worker thread writes to ProgressBridge in remote process (memory write, <1μs)
- Client queries backend Operations Service
- Backend pulls from remote Operations Service via OperationServiceProxy (HTTP)
- Remote Operations Service checks ITS cache, pulls from ITS bridge if stale
- Slightly slower (network), but same pattern

**The Beauty**: Same code, same logic, same API—everywhere. **NO polling, anywhere.**

---

## 2. Architecture Overview

### Component Map

```
┌─────────────────────────────────────────────────────────────┐
│                     THE CLIENT LAYER                        │
│                                                             │
│  "How's my backtest?"                                       │
│  GET /operations/{id}                                       │
└─────────────────────────────────────────────────────────────┘
                         │
                         ↓ HTTP Query
┌─────────────────────────────────────────────────────────────┐
│              OPERATIONS SERVICE (Smart Cache)               │
│                                                             │
│  "Is my cache fresh (TTL check)?"                           │
│  ├─ Fresh (< 1 second old) → Return cached data            │
│  └─ Stale → Pull fresh data from source (bridge or proxy)  │
└─────────────────────────────────────────────────────────────┘
                         │
            ┌────────────┴────────────┐
            │                         │
       Local Access              Remote Access
    (same process)            (HTTP to remote)
            │                         │
            ▼                         ▼
┌─────────────────────┐    ┌─────────────────────┐
│   PROGRESS BRIDGE   │    │  REMOTE CONTAINER   │
│   (State Container) │    │  Port 5003          │
│                     │    │                     │
│  "I hold state"     │    │  OperationsService  │
│  get_status()       │    │  (same code!)       │
│  get_metrics(cur)   │    │       ↓             │
└─────────────────────┘    │  ProgressBridge     │
         ↑                 └─────────────────────┘
         │                          ↑
         │ Fast writes              │ Fast writes
         │ (<1μs)                   │ (<1μs)
         │                          │
┌─────────────────────┐    ┌─────────────────────┐
│   WORKER LAYER      │    │  WORKER LAYER       │
│  (Thread)           │    │  (Remote Thread)    │
│                     │    │                     │
│  BacktestingEngine  │    │  BacktestingEngine  │
│  "I do the work"    │    │  "I do the work"    │
└─────────────────────┘    └─────────────────────┘

      Backend Process          Remote Container
      (Docker)                 (Different Machine)
```

### The Data Flow (Simplified)

**Worker updates state:**
```
Worker: "I processed bar 500/1000"
  ↓ (memory write, <1μs)
Bridge: "Noted. State now: 50.0% complete"
```

**Client queries:**
```
Client: "What's the status?"
  ↓
OperationsService: "Let me check my cache..."
  ├─ Cache: "I have data from 0.3 seconds ago" (fresh!)
  └─ Return cached data immediately

OR (if stale):
  ├─ Cache: "I have data from 2 seconds ago" (stale!)
  ├─ Pull from source:
  │   Local: bridge.get_status() (memory read)
  │   Remote: HTTP GET to remote OperationsService
  ├─ Update cache
  └─ Return fresh data
```

**NO polling anywhere:**
- ❌ NO background tasks polling bridges
- ❌ NO polling loops for completion detection
- ✅ Client queries trigger refresh (when cache stale)
- ✅ HealthService (external monitor) queries periodically (it's just another client)

### The Unification

**Same OperationsService everywhere:**
```
Backend API (Docker)
  └─ OperationsService
      └─ Manages all operations (local + remote)

Remote Backtest Container (Port 5003)
  └─ OperationsService (SAME code!)
      └─ Manages backtest operations
```

When backend needs remote backtest status:
```
Backend OperationsService
  ↓ (cache stale, pull via proxy)
  HTTP GET to remote /operations/{id}
  ↓
Remote OperationsService
  ↓ (check ITS cache, pull from ITS bridge if stale)
  bridge.get_status()
  ↓
Return to backend
```

**Same code, same pattern, no translation layer needed.**

---

## 3. Core Principles

These principles guide every decision (from pull-based operations architecture):

### Principle 1: Locality of Reference
**State lives where it's produced.**

Workers write to ProgressBridge in their own process. No network calls, no I/O, no blocking.

### Principle 2: Lazy Evaluation (Client-Driven Pull)
**Don't compute until needed.**

NO background tasks. Refresh only happens when:
1. Client queries OperationsService AND
2. Cache is stale (age > TTL)

Work scales with demand, not with time.

### Principle 3: Cache as Contract
**Caching is explicit, not hidden.**

TTL (1 second) is visible and configurable. Clients can force refresh with `force_refresh=True`.

### Principle 4: Uniform Interfaces
**Same API works everywhere.**

OperationsService has identical endpoints in backend and remote containers. Same behavior.

### Principle 5: Explicit Over Implicit
**Make state transitions visible.**

Workers explicitly call `complete_operation()` when done. No polling for completion.

### Principle 6: Separation of Concerns
**Each component has one job.**

- **ProgressBridge**: Hold state (sync, fast)
- **BacktestingEngine**: Do work (sync, blocking)
- **BacktestingService**: Orchestrate operations (async, non-blocking)
- **OperationsService**: CRUD + cache + routing (async)

---

## 4. Component Design

### 4.1 BacktestingService

**Purpose**: Async orchestrator for backtesting operations.

**Architecture Pattern**: ServiceOrchestrator subclass with ProgressBridge composition.

**Responsibilities**:
1. Create operations in OperationsService
2. Execute backtest (local OR remote)
3. Register state source (bridge for local, proxy for remote)
4. Operations Service handles all progress tracking via cache + pull

**Key Characteristics**:
- **Async by nature**: Inherits from ServiceOrchestrator
- **Composes BacktestingEngine**: Uses engine for work
- **Registers with Operations**: Bridge (local) or Proxy (remote)
- **NO polling**: Client-driven via OperationsService
- **Returns immediately**: Doesn't wait for completion

**Location**: `ktrdr/backtesting/backtesting_service.py` (NEW)

**Interface** (conceptual):
```python
class BacktestingService(ServiceOrchestrator):
    def __init__(self, operations_service: OperationsService):
        super().__init__()
        self.operations_service = operations_service

    async def run_backtest(
        symbol: str,
        timeframe: str,
        strategy_config_path: str,
        model_path: str,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float = 100000.0,
        remote: bool = False,  # Controlled by ENV, not request
    ) -> str:  # Returns operation_id
        """
        Run backtest with async operations support.

        Flow:
        1. Create operation in OperationsService
        2. If local mode:
             - Create ProgressBridge
             - Register bridge with OperationsService
             - Run engine in thread (asyncio.to_thread)
             - Engine writes to bridge, OperationsService pulls
           Else (remote mode):
             - HTTP POST to remote /backtests/start
             - Create OperationServiceProxy
             - Register proxy with OperationsService
             - Return immediately (remote runs independently)
        3. Return operation_id (client tracks via queries)
        """
```

**Design Decision**: Service is pure coordination. Engine does work. OperationsService handles all state tracking.

---

### 4.2 BacktestingEngine (Existing - Minimal Changes)

**Purpose**: Synchronous backtesting event loop.

**Current State**: Fully functional, synchronous, blocking.

**Changes Needed** (minimal):
1. Accept ProgressBridge parameter (optional)
2. Write progress to bridge (if provided)
3. Periodic progress reporting (every N bars)
4. Periodic cancellation checks (via bridge or token)

**What Stays**: Everything else. Event loop, position management, performance tracking all unchanged.

**Location**: `ktrdr/backtesting/engine.py` (EXISTS)

**Enhanced Interface**:
```python
class BacktestingEngine:
    def run(
        self,
        bridge: Optional[ProgressBridge] = None,  # NEW
        cancellation_token: Optional[CancellationToken] = None,  # NEW
    ) -> BacktestResults:
        """
        Run backtest event loop.

        NEW: Optional ProgressBridge for state reporting.

        Changes:
        - Every N bars, write to bridge: bridge.update_progress(...)
        - Every M iterations, check cancellation
        - Raise CancelledError if cancellation requested
        """
```

**Design Decision**: Minimal changes to engine. Add bridge writes, don't refactor internals.

---

### 4.3 Existing Infrastructure: OperationServiceProxy & OperationsService

**IMPORTANT**: We are **NOT creating new infrastructure**. Backtesting will reuse the existing, proven components from training/data.

#### 4.3.1 OperationServiceProxy (REUSE - No Changes)

**Purpose**: Generic HTTP client for remote OperationsService.

**Status**: ✅ **Already fully generic** - Shared across training, data, and backtesting.

**Location**: `ktrdr/api/services/adapters/operation_service_proxy.py` (EXISTS)

**From the code documentation** (lines 36-42):
```python
"""
HTTP client for querying OperationsService on host services.
This proxy wraps httpx.AsyncClient to provide a clean interface for
operations queries. It's designed to be shared across multiple adapters
(training, data, backtesting) that need to query operations on host services.
"""
```

**Interface** (already implemented):
```python
class OperationServiceProxy:
    """Generic HTTP client for OperationsService API."""

    async def get_operation(operation_id: str, force_refresh: bool) -> dict:
        """GET /operations/{operation_id}?force_refresh={bool}"""

    async def get_metrics(operation_id: str, cursor: int) -> tuple[list, int]:
        """GET /operations/{operation_id}/metrics?cursor={cursor}"""

    async def cancel_operation(operation_id: str, reason: str) -> dict:
        """DELETE /operations/{operation_id}/cancel"""
```

**What Backtesting Does**: Simply instantiate and use:
```python
# In BacktestingService when starting remote backtest:
proxy = OperationServiceProxy(base_url=remote_url)
ops_service.register_remote_proxy(backend_op_id, proxy, remote_op_id)
# Done! OperationsService handles all queries via this proxy
```

---

#### 4.3.2 OperationsService Registration (REUSE - No Changes)

**Purpose**: Generic registration methods for local/remote state sources.

**Status**: ✅ **Already fully generic** - Takes `Any` for bridge/proxy types.

**Location**: `ktrdr/api/services/operations_service.py` (EXISTS)

**Registration Methods** (lines 584-625):
```python
def register_local_bridge(self, operation_id: str, bridge: Any) -> None:
    """
    Register a local bridge for pull-based progress updates.
    Generic - works with any bridge type (training, data, backtesting).
    """
    self._local_bridges[operation_id] = bridge
    self._metrics_cursors[operation_id] = 0

def register_remote_proxy(
    self,
    backend_operation_id: str,
    proxy: Any,  # Generic OperationServiceProxy
    host_operation_id: str,
) -> None:
    """
    Register a remote proxy for pull-based progress updates.
    Generic - works with any OperationServiceProxy instance.
    """
    self._remote_proxies[backend_operation_id] = (proxy, host_operation_id)
    self._metrics_cursors[backend_operation_id] = 0
```

**What Backtesting Does**: Call these methods exactly like training does:
```python
# Local mode:
bridge = BacktestProgressBridge(...)
ops_service.register_local_bridge(operation_id, bridge)

# Remote mode:
proxy = OperationServiceProxy(remote_url)
ops_service.register_remote_proxy(backend_op_id, proxy, remote_op_id)
```

---

#### 4.3.3 OperationsService Refresh (NEEDS ONE FIX)

**Purpose**: Pull state from bridges/proxies when cache is stale.

**Status**: ⚠️ **Has one training-specific section** - Needs to be made generic.

**Location**: `ktrdr/api/services/operations_service.py` lines 644-718

**The Issue** (lines 704-707):
```python
def _refresh_from_bridge(self, operation_id: str) -> None:
    # ... pulls state from bridge (generic) ...
    # ... updates progress (generic) ...

    # ❌ TRAINING-SPECIFIC CODE:
    if operation.operation_type == OperationType.TRAINING:
        if "epochs" not in operation.metrics:
            operation.metrics["epochs"] = []
        operation.metrics["epochs"].extend(new_metrics)
```

**The Fix** (make it type-aware):
```python
# After pulling new_metrics from bridge:
if new_metrics:
    if operation.metrics is None:
        operation.metrics = {}

    # Type-aware storage
    if operation.operation_type == OperationType.TRAINING:
        if "epochs" not in operation.metrics:
            operation.metrics["epochs"] = []
        operation.metrics["epochs"].extend(new_metrics)

    elif operation.operation_type == OperationType.BACKTESTING:
        if "bars" not in operation.metrics:
            operation.metrics["bars"] = []
        operation.metrics["bars"].extend(new_metrics)

    elif operation.operation_type == OperationType.DATA_LOADING:
        if "segments" not in operation.metrics:
            operation.metrics["segments"] = []
        operation.metrics["segments"].extend(new_metrics)

    else:
        # Generic fallback for new operation types
        if "history" not in operation.metrics:
            operation.metrics["history"] = []
        operation.metrics["history"].extend(new_metrics)
```

**When to Fix**: Phase 0 (before implementing backtesting) or early Phase 1.

**Impact**: Small change (~10 lines), no breaking changes, makes OperationsService truly generic.

---

**Design Decision**:

- ✅ **Reuse** OperationServiceProxy (no changes)
- ✅ **Reuse** OperationsService registration (no changes)
- ⚠️ **Fix** `_refresh_from_bridge()` to be operation-type aware (small change)

---

### 4.4 Remote Container API

**Purpose**: FastAPI application for remote backtest container.

**Responsibilities**:
1. Accept backtest requests (POST /backtests/start)
2. Run BacktestingService in local mode
3. Expose OperationsService API (/operations/*)

**Key Characteristics**:
- **Runs OperationsService**: Same code as backend
- **Runs BacktestingService**: In local mode (not remote!)
- **Bridge registration**: Registers local bridge
- **Client queries**: Via OperationsService endpoints

**Location**: Remote container (separate deployment)

**Endpoints**:
```python
# Domain-specific
POST /backtests/start → Create operation, run backtest

# Operations (generic, same as backend)
GET /operations/{id} → OperationsService.get_operation()
GET /operations/{id}/metrics → OperationsService.get_metrics()
POST /operations/{id}/complete → OperationsService.complete_operation()
```

**Design Decision**: Remote container uses LOCAL mode internally. Backend doesn't know or care.

---

## 5. Execution Modes

### 5.1 Local Execution Mode

**When to Use**:
- Development and testing
- Single backtest on same machine as API
- Fast iteration without network overhead

**Characteristics**:
- In-process execution (same container)
- BacktestingEngine runs in thread pool via asyncio.to_thread()
- ProgressBridge in same process (memory writes)
- OperationsService pulls from bridge when cache stale
- Same pattern as training local mode

**Flow**:
```
BacktestingService.run_backtest(remote=False)
  ↓
1. Create operation in OperationsService
  ↓
2. Create ProgressBridge
  ↓
3. Register bridge: ops_service.register_local_bridge(op_id, bridge)
  ↓
4. Run engine in thread:
     asyncio.to_thread(engine.run, bridge=bridge)
     [Worker Thread]
       For each bar:
         - Process bar
         - bridge.update_progress(...) ← <1μs write
  ↓
5. Return operation_id immediately
  ↓
[Client queries]
  GET /operations/{op_id}
    → OperationsService.get_operation()
    → Cache stale? → bridge.get_status() (memory read)
    → Return progress
```

**Progress Latency**: Cache-dependent (up to 1s staleness)

**Cancellation Latency**: <50ms (in-memory check)

---

### 5.2 Remote Execution Mode

**When to Use**:
- Distributed backtesting (different machines)
- Resource-intensive backtests (offload to dedicated machine)
- Parallel backtesting (multiple remotes)
- Production deployments

**Characteristics**:
- HTTP-based communication
- Remote container runs BacktestingService in local mode
- OperationServiceProxy for backend queries
- Two-level caching (backend + remote)
- Same pattern as training host service

**Flow**:
```
BacktestingService.run_backtest(remote=True)
  ↓
1. Create operation in backend OperationsService
  ↓
2. HTTP POST to remote /backtests/start
  ↓
   [Remote Container]
     - Creates operation in remote OperationsService
     - Creates ProgressBridge
     - Registers local bridge
     - Runs BacktestingEngine (local mode)
     - Returns session_id
  ↓
3. Create OperationServiceProxy(remote_url)
  ↓
4. Register proxy: ops_service.register_remote_proxy(backend_op_id, proxy, remote_op_id)
  ↓
5. Return backend operation_id immediately
  ↓
[Client queries]
  GET /operations/{backend_op_id}
    → Backend OperationsService.get_operation()
    → Cache stale? → proxy.get_operation(remote_op_id)
      → HTTP GET to remote /operations/{remote_op_id}
        → Remote OperationsService.get_operation()
        → Remote cache stale? → bridge.get_status()
        → Return to backend
    → Backend caches, returns to client
```

**Progress Latency**: Up to 1s + network (two caches with 1s TTL)

**Cancellation Latency**: <2.5s (poll + HTTP request)

---

### 5.3 Mode Selection

**Environment-Based ONLY** (at startup):
```bash
# Set in environment
export USE_REMOTE_BACKTEST_SERVICE=true
export REMOTE_BACKTEST_SERVICE_URL=http://backtest-worker:5003

# OR use switch script
./scripts/switch-backtest-mode.sh local   # Local mode
./scripts/switch-backtest-mode.sh remote  # Remote mode
```

**NO request-based mode selection**. Why:
1. Future orchestrator will manage multiple remote instances
2. Client shouldn't control routing (architectural decision)
3. Simpler: One mode per deployment
4. Matches training pattern exactly

**Decision Priority**:
1. Environment variable (`USE_REMOTE_BACKTEST_SERVICE`)
2. Default: local mode

---

## 6. Design Rationale

### Why Pull-Based Operations?

**The current architecture (training, data) uses pull-based operations because**:
- Workers write to local ProgressBridge (fast, <1μs, no I/O)
- NO async/sync boundary issues
- NO polling loops consuming resources
- Client-driven: Work happens when clients query
- Proven: Already working for training and data

### Why NOT Polling?

**Polling was completely removed because**:
- Redundant: Client polls, why poll internally too?
- Wasteful: Polling every N seconds even when no clients watching
- Complex: Managing background tasks, shutdown, errors
- Unnecessary: Client-driven pull + TTL cache solves it elegantly

### Why Same Code Everywhere?

Deploying identical OperationsService in backend and remote containers:
- **DRY**: Write once, test once, maintain once
- **Consistency**: Same behavior guaranteed
- **Simplicity**: No translation layers
- **Proven**: Already working for training host service

---

## 7. Trade-offs and Decisions

### Trade-off 1: Minimal Engine Changes vs Full Async Refactor

**Decision**: Minimal changes to BacktestingEngine (add ProgressBridge writes).

**Rationale**:
- Engine is synchronous by nature (event loop)
- Async engine adds complexity without benefit
- ProgressBridge writes are fast (<1μs)
- Proven pattern from training

**Impact**:
- Positive: Low risk, fast implementation
- Negative: Engine stays synchronous (acceptable)

---

### Trade-off 2: Client-Driven Pull vs Background Polling

**Decision**: Client-driven pull (NO polling).

**Rationale**:
- Already implemented and working for training/data
- Simpler: No background task management
- More efficient: Work scales with demand
- Proven: training has been using this successfully

**Impact**:
- Positive: Simple, efficient, proven
- Negative: None (this is the current architecture!)

---

### Trade-off 3: Environment-Based vs Request-Based Mode Selection

**Decision**: Environment-based ONLY.

**Rationale**:
- Future orchestrator will manage routing (not client)
- Simpler configuration (one mode per deployment)
- Matches training pattern exactly
- Prevents client from making architectural decisions

**Impact**:
- Positive: Simple, consistent, forward-compatible
- Negative: Can't switch per-request (not needed)

---

### Trade-off 4: Container vs Host Service for Remote

**Decision**: Container (not native host service).

**Rationale**:
- Backtesting doesn't need GPU (unlike training)
- Containers are portable (any machine, cloud, cluster)
- Containers are isolated (resource control)
- Containers are reproducible

**Impact**:
- Positive: Portable, scalable, isolated
- Negative: Slight overhead vs native (negligible)

---

## 8. Success Criteria

### Functional Requirements

**FR1: Operations Service Integration**
- ✅ Backtests tracked in Operations service
- ✅ Status queryable via /operations/{operation_id}
- ✅ Progress pulled via client-driven refresh (TTL cache)

**FR2: Progress Reporting**
- ✅ Local mode: Workers write to bridge, OperationsService pulls
- ✅ Remote mode: Two-level pull (backend → remote → bridge)
- ✅ Progress includes: % complete, current bar, PnL, trades

**FR3: Cancellation Support**
- ✅ Local mode: Token-based (<50ms latency)
- ✅ Remote mode: Proxy-based (<2.5s latency)
- ✅ Graceful cleanup

**FR4: Remote Execution**
- ✅ Remote container accepts HTTP backtest requests
- ✅ OperationServiceProxy for backend queries
- ✅ Results retrievable after completion

**FR5: Backwards Compatibility**
- ✅ BacktestingEngine.run() still works synchronously
- ✅ Existing tests pass unchanged

### Architectural Requirements

**AR1: Pull-Based Operations**
- ✅ BacktestingService uses OperationsService
- ✅ ProgressBridge for state (sync, fast)
- ✅ NO polling anywhere (client-driven only)

**AR2: Composition**
- ✅ BacktestingService composes BacktestingEngine
- ✅ Engine can be used standalone
- ✅ Clear dependency direction

**AR3: Mode Support**
- ✅ Local execution mode works
- ✅ Remote execution mode works
- ✅ Mode selection via environment (switch script)

### Performance Requirements

**PR1: Local Mode Performance**
- ✅ Bridge write overhead: <1% of execution time (<1μs per write)
- ✅ No performance regression vs current engine

**PR2: Remote Mode Performance**
- ✅ HTTP overhead: <5ms per request
- ✅ Two-level caching: Prevents redundant HTTP calls

---

## Next Steps

1. **Review and Approval**: Team review of this design document
2. **Architecture Document**: Detailed component interfaces and API contracts
3. **Implementation Plan**: Phased implementation with tasks and acceptance criteria
4. **Prototype**: Proof-of-concept for local mode
5. **Implementation**: Incremental implementation and testing

---

## Appendix A: Comparison with Training Architecture

| Aspect | Training (Current) | Backtesting (Proposed) |
|--------|-------------------|------------------------|
| **Base Class** | ServiceOrchestrator | ServiceOrchestrator (same) |
| **Local Execution** | ProgressBridge + register_local_bridge() | ProgressBridge + register_local_bridge() (same) |
| **Remote Execution** | OperationServiceProxy + register_remote_proxy() | OperationServiceProxy + register_remote_proxy() (same) |
| **Progress Tracking** | Client-driven pull via OperationsService | Client-driven pull via OperationsService (same) |
| **Polling** | None (client-driven) | None (client-driven) (same) |
| **Mode Selection** | ENV (USE_TRAINING_HOST_SERVICE) + switch script | ENV (USE_REMOTE_BACKTEST_SERVICE) + switch script (same) |
| **Remote Type** | Native host service (GPU) | Container (portable) (different) |

**Conclusion**: Same architecture, same patterns, proven and working.

---

**Document Version**: 2.0 (Revised - Pull-Based Operations)
**Last Updated**: 2025-01-03
**Next Review**: After architecture document completion
