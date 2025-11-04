# Architecture: Backtesting Async Operations

## Document Information

**Date**: 2025-01-03 (Revised)
**Status**: DRAFT - Ready for Review
**Version**: 2.0 (Pull-Based Operations)
**Related Documents**:
- [Design Document](./01-design-backtesting-async.md) - High-level design principles
- [Implementation Plan](./03-implementation-plan-backtesting-async.md) - Step-by-step implementation
- [Pull-Based Operations Architecture](../operations/05-architecture-pull-based-operations.md) - Foundation architecture
- [Pull-Based Operations Design](../operations/04-design-pull-based-operations.md) - Design principles

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

---

## 1. Executive Summary

### 1.1 Purpose

This document defines the detailed architecture for modernizing KTRDR's backtesting system using the **pull-based operations architecture**, translating design principles into concrete specifications.

### 1.2 The Architecture

**Pull-Based Operations with Client-Driven Refresh** - Same as training and data.

**Core Pattern**:
```
Worker → ProgressBridge (sync write, <1μs)
Client → OperationsService → Cache check (TTL) → Pull from bridge/proxy if stale
NO polling, NO background tasks
```

### 1.3 Key Components

| Component | Status | Role |
|-----------|--------|------|
| **OperationsService** | ✅ Reuse (1 fix) | CRUD + cache + routing |
| **OperationServiceProxy** | ✅ Reuse (no changes) | HTTP client for remote Operations Service |
| **BacktestingService** | 🆕 Create | Orchestrator (ServiceOrchestrator subclass) |
| **BacktestingEngine** | ✅ Enhance | Worker (add ProgressBridge writes) |
| **BacktestProgressBridge** | 🆕 Create | State container (ProgressBridge subclass) |
| **Remote Container** | 🆕 Create | FastAPI app (runs BacktestingService locally) |

### 1.4 Key Architectural Decisions

| Decision | Rationale | Impact |
|----------|-----------|--------|
| **Reuse OperationsService** | Already proven for training/data | ✅ No reinventing, 1 small fix needed |
| **Reuse OperationServiceProxy** | Already generic | ✅ Zero changes |
| **Client-driven pull** | Current architecture (NO polling) | ✅ Simple, efficient, proven |
| **ProgressBridge for state** | Same as training | ✅ Fast writes (<1μs), no async issues |
| **ENV-based mode selection** | Same as training | ✅ Consistent, simple |

---

## 2. Architectural Principles

From [Pull-Based Operations Design](../operations/04-design-pull-based-operations.md):

### 2.1 Locality of Reference
**State lives where it's produced.**

Workers write to ProgressBridge in their process. No I/O, no async boundaries.

### 2.2 Lazy Evaluation (Client-Driven)
**Don't compute until needed.**

Refresh triggered by client queries when cache is stale (TTL check). **NO background polling.**

### 2.3 Cache as Contract
**Caching is explicit.**

TTL (1 second default) is visible. Clients can force refresh with `force_refresh=True`.

### 2.4 Uniform Interfaces
**Same API everywhere.**

OperationsService has identical endpoints in backend and remote containers.

### 2.5 Explicit Over Implicit
**State transitions are explicit.**

Workers call `complete_operation()` when done. No polling for completion detection.

---

## 3. System Architecture

### 3.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     CLIENT LAYER                            │
│  CLI, Web UI, MCP Client                                    │
│  GET /operations/{id}                                       │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP Query
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              OPERATIONS SERVICE (Existing)                  │
│              ktrdr/api/services/operations_service.py       │
│                                                             │
│  get_operation(op_id) → Cache check (TTL) → Pull if stale  │
│  register_local_bridge(op_id, bridge)  ← Used by local     │
│  register_remote_proxy(op_id, proxy, remote_op_id) ← Remote│
└─────────────────────────────────────────────────────────────┘
                         │
            ┌────────────┴────────────┐
            │                         │
       Local Access              Remote Access
    (same process)            (HTTP to remote)
            │                         │
            ▼                         ▼
┌─────────────────────┐    ┌─────────────────────┐
│ BacktestProgressBridge│   │ REMOTE CONTAINER   │
│ (NEW)               │    │  Port 5003         │
│                     │    │                    │
│ get_status()        │    │  OperationsService │
│ get_metrics(cursor) │    │  (same code!)      │
│ update_progress()   │    │       ↓            │
└─────────────────────┘    │  BacktestProgressBridge
         ↑                 └─────────────────────┘
         │ Writes                    ↑
         │ (<1μs)                    │ Writes
         │                           │ (<1μs)
┌─────────────────────┐    ┌─────────────────────┐
│ BacktestingEngine   │    │ BacktestingEngine   │
│ (Enhanced)          │    │ (Enhanced)          │
│                     │    │                     │
│ For each bar:       │    │ For each bar:       │
│   process()         │    │   process()         │
│   bridge.update()   │    │   bridge.update()   │
└─────────────────────┘    └─────────────────────┘

   Backend Process          Remote Container
   (Docker)                 (Different Machine)
```

### 3.2 Execution Modes

#### Local Mode (Development)
```
BacktestingService
  ├─ Create operation in OperationsService
  ├─ Create BacktestProgressBridge
  ├─ Register: ops_service.register_local_bridge(op_id, bridge)
  ├─ Run engine: asyncio.to_thread(engine.run, bridge=bridge)
  └─ Return operation_id immediately

[Worker Thread]
  engine.run(bridge):
    For each bar:
      - Process bar
      - bridge.update_progress(...) ← <1μs write

[Client Queries]
  GET /operations/{op_id}
    → OperationsService.get_operation()
    → Cache stale? → _refresh_from_bridge() → bridge.get_status()
    → Return progress
```

#### Remote Mode (Production/Distributed)
```
BacktestingService (Backend)
  ├─ Create operation in backend OperationsService
  ├─ HTTP POST to remote /backtests/start
  │   [Remote Container]
  │     ├─ Creates operation in remote OperationsService
  │     ├─ Creates BacktestProgressBridge
  │     ├─ Registers local bridge
  │     ├─ Runs BacktestingEngine (local mode)
  │     └─ Returns session_id/operation_id
  ├─ Create OperationServiceProxy(remote_url)
  ├─ Register: ops_service.register_remote_proxy(backend_op_id, proxy, remote_op_id)
  └─ Return backend operation_id immediately

[Client Queries]
  GET /operations/{backend_op_id}
    → Backend OperationsService.get_operation()
    → Cache stale? → _refresh_from_remote_proxy()
      → proxy.get_operation(remote_op_id) [HTTP]
        → Remote OperationsService.get_operation()
        → Remote cache stale? → bridge.get_status()
        → Return to backend
    → Backend caches, returns to client
```

---

## 4. Component Architecture

### 4.1 BacktestingService (NEW)

**Purpose**: Async orchestrator for backtesting operations.

**Location**: `ktrdr/backtesting/backtesting_service.py`

**Inheritance**: `ServiceOrchestrator` (existing base class)

#### Class Design

```python
from ktrdr.async_infrastructure import ServiceOrchestrator
from ktrdr.api.services.operations_service import OperationsService

class BacktestingService(ServiceOrchestrator):
    """
    Backtesting orchestration service with async operations support.

    Follows the same pattern as TrainingService:
    - Inherits from ServiceOrchestrator
    - Creates operations in OperationsService
    - Registers bridges (local) or proxies (remote)
    - Returns immediately, clients poll for progress
    """

    def __init__(self, operations_service: OperationsService):
        super().__init__()
        self.operations_service = operations_service
        self._use_remote = self._should_use_remote_service()

    def _should_use_remote_service(self) -> bool:
        """Check USE_REMOTE_BACKTEST_SERVICE env variable."""
        return os.getenv("USE_REMOTE_BACKTEST_SERVICE", "false").lower() == "true"

    def _get_remote_service_url(self) -> str:
        """Get remote backtest service URL."""
        return os.getenv("REMOTE_BACKTEST_SERVICE_URL", "http://localhost:5003")
```

#### Public Interface

```python
async def run_backtest(
    self,
    symbol: str,
    timeframe: str,
    strategy_config_path: str,
    model_path: str,
    start_date: datetime,
    end_date: datetime,
    initial_capital: float = 100000.0,
    commission: float = 0.001,
    slippage: float = 0.001,
) -> str:  # Returns operation_id
    """
    Run backtest with async operations support.

    Returns operation_id immediately. Clients poll for progress via:
      GET /operations/{operation_id}

    Flow:
    1. Create operation in OperationsService
    2. If local mode:
         - _run_local_backtest()
       Else (remote mode):
         - _run_remote_backtest()
    3. Return operation_id
    """
    # Create operation
    operation_id = await self.operations_service.create_operation(
        operation_type=OperationType.BACKTESTING,
        operation_name=f"backtest_{symbol}_{timeframe}",
        metadata={...}
    )

    # Route based on mode
    if self._use_remote:
        await self._run_remote_backtest(operation_id, ...)
    else:
        await self._run_local_backtest(operation_id, ...)

    return operation_id
```

#### Local Execution Method

```python
async def _run_local_backtest(
    self,
    operation_id: str,
    symbol: str,
    # ... other params
) -> None:
    """
    Run backtest locally (same container).

    Pattern (same as training):
    1. Create BacktestProgressBridge
    2. Register bridge with OperationsService
    3. Run engine in thread
    4. Engine completes → calls ops_service.complete_operation()
    """
    # Create bridge
    bridge = BacktestProgressBridge(
        operation_id=operation_id,
        symbol=symbol,
        timeframe=timeframe,
        total_bars=total_bars,  # Calculated from date range
    )

    # Register with OperationsService
    self.operations_service.register_local_bridge(operation_id, bridge)

    # Build engine
    engine = BacktestingEngine(config)

    # Run in thread (non-blocking)
    async def run_in_thread():
        try:
            # Run engine (blocks until complete)
            results = await asyncio.to_thread(
                engine.run,
                bridge=bridge,
                cancellation_token=self.operations_service.get_cancellation_token(operation_id)
            )

            # Complete operation
            await self.operations_service.complete_operation(
                operation_id,
                results=results.to_dict()
            )
        except Exception as e:
            await self.operations_service.fail_operation(
                operation_id,
                error=str(e)
            )

    # Start background task (returns immediately)
    asyncio.create_task(run_in_thread())
```

#### Remote Execution Method

```python
async def _run_remote_backtest(
    self,
    operation_id: str,
    symbol: str,
    # ... other params
) -> None:
    """
    Run backtest remotely (different machine).

    Pattern (same as training):
    1. HTTP POST to remote /backtests/start
    2. Create OperationServiceProxy
    3. Register proxy with OperationsService
    4. Return (remote handles execution)
    """
    from ktrdr.api.services.adapters.operation_service_proxy import OperationServiceProxy

    # (1) Start remote backtest
    remote_url = self._get_remote_service_url()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{remote_url}/backtests/start",
            json={
                "symbol": symbol,
                "timeframe": timeframe,
                "strategy_config_path": strategy_config_path,
                "model_path": model_path,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "initial_capital": initial_capital,
            }
        )
        response.raise_for_status()
        data = response.json()
        remote_operation_id = data["operation_id"]

    # (2) Create proxy
    proxy = OperationServiceProxy(base_url=remote_url)

    # (3) Register proxy
    self.operations_service.register_remote_proxy(
        backend_operation_id=operation_id,
        proxy=proxy,
        host_operation_id=remote_operation_id,
    )

    # Done! OperationsService handles all queries via proxy
    logger.info(
        f"Registered remote proxy: {operation_id} → {remote_operation_id}"
    )
```

---

### 4.2 BacktestingEngine (ENHANCED)

**Purpose**: Synchronous backtesting event loop.

**Location**: `ktrdr/backtesting/engine.py` (EXISTS)

**Changes**: Minimal - add ProgressBridge parameter and writes.

#### Enhanced Signature

```python
class BacktestingEngine:
    def run(
        self,
        bridge: Optional[ProgressBridge] = None,  # NEW
        cancellation_token: Optional[CancellationToken] = None,  # NEW
    ) -> BacktestResults:
        """
        Run backtest event loop.

        NEW: Accepts optional ProgressBridge for state reporting.
        """
```

#### Bridge Integration

```python
def run(self, bridge=None, cancellation_token=None):
    # Load data
    data = self._load_historical_data()
    total_bars = len(data)

    # Event loop
    for bar_idx, (timestamp, bar) in enumerate(data.iterrows()):
        # Existing logic
        decision = self.orchestrator.get_decision(bar, timestamp)
        self.position_manager.process_decision(decision, bar, timestamp)
        self.performance_tracker.update(...)

        # NEW: Report progress (every 50 bars)
        if bridge and bar_idx % 50 == 0:
            bridge.update_progress(
                current_bar=bar_idx,
                total_bars=total_bars,
                current_date=timestamp,
                current_pnl=self.position_manager.unrealized_pnl,
                total_trades=len(self.position_manager.closed_positions),
                win_rate=self.performance_tracker.win_rate,
            )

        # NEW: Check cancellation (every 100 bars)
        if cancellation_token and bar_idx % 100 == 0:
            if cancellation_token.is_cancelled_requested:
                raise asyncio.CancelledError("Backtest cancelled")

    # Return results
    return self._generate_results()
```

---

### 4.3 BacktestProgressBridge (NEW)

**Purpose**: State container for backtesting progress.

**Location**: `ktrdr/backtesting/progress_bridge.py`

**Inheritance**: `ProgressBridge` (existing base class)

#### Class Design

```python
from ktrdr.api.services.training.progress_bridge import ProgressBridge

class BacktestProgressBridge(ProgressBridge):
    """
    Backtesting-specific progress bridge.

    Follows same pattern as TrainingProgressBridge:
    - Subclasses ProgressBridge (base infrastructure)
    - Implements domain-specific update methods
    - Workers call update_progress(), OperationsService pulls via get_status()
    """

    def __init__(
        self,
        operation_id: str,
        symbol: str,
        timeframe: str,
        total_bars: int,
    ):
        super().__init__()  # Initialize base class
        self.operation_id = operation_id
        self.symbol = symbol
        self.timeframe = timeframe
        self.total_bars = total_bars

    # Domain-specific callback (called by BacktestingEngine)
    def update_progress(
        self,
        current_bar: int,
        total_bars: int,
        current_date: str,
        current_pnl: float,
        total_trades: int,
        win_rate: float,
    ) -> None:
        """
        Update backtest progress (called by engine every N bars).

        This is a SYNC method - fast (<1μs), no I/O.
        """
        percentage = (current_bar / max(1, total_bars)) * 100.0
        message = f"Backtesting {self.symbol} {self.timeframe} [{current_date}]"

        # Update base class state (thread-safe)
        self._update_state(
            percentage=percentage,
            message=message,
            current_bar=current_bar,
            total_bars=total_bars,
            current_date=current_date,
            current_pnl=current_pnl,
            total_trades=total_trades,
            win_rate=win_rate,
        )

    def report_trade(
        self,
        trade_type: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        timestamp: str,
    ) -> None:
        """
        Report individual trade metric (called by engine).

        Appends to metrics history for incremental reading.
        """
        self._append_metric({
            "type": "trade",
            "trade_type": trade_type,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": pnl,
            "timestamp": timestamp,
        })
```

---

### 4.4 OperationsService (FIX NEEDED)

**Purpose**: CRUD + cache + routing for operations.

**Location**: `ktrdr/api/services/operations_service.py` (EXISTS)

**Status**: ✅ Mostly generic, ⚠️ One fix needed

#### The Fix Required

**File**: `ktrdr/api/services/operations_service.py`
**Lines**: 704-707
**Issue**: Training-specific metrics storage

**Current Code**:
```python
def _refresh_from_bridge(self, operation_id: str) -> None:
    # ... pulls state, updates progress (generic) ...

    # ❌ TRAINING-SPECIFIC:
    if operation.operation_type == OperationType.TRAINING:
        if "epochs" not in operation.metrics:
            operation.metrics["epochs"] = []
        operation.metrics["epochs"].extend(new_metrics)
```

**Fixed Code** (operation-type aware):
```python
def _refresh_from_bridge(self, operation_id: str) -> None:
    # ... pulls state, updates progress (generic) ...

    # ✅ GENERIC (type-aware):
    if new_metrics:
        if operation.metrics is None:
            operation.metrics = {}

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
            # Fallback for new types
            if "history" not in operation.metrics:
                operation.metrics["history"] = []
            operation.metrics["history"].extend(new_metrics)
```

**When to Fix**: Phase 0 (before backtesting implementation) or Phase 1 (during)

**Impact**: ~15 lines, no breaking changes, makes OperationsService truly generic

---

### 4.5 OperationServiceProxy (REUSE - No Changes)

**Purpose**: Generic HTTP client for remote OperationsService.

**Location**: `ktrdr/api/services/adapters/operation_service_proxy.py` (EXISTS)

**Status**: ✅ **Already fully generic** - Shared across training, data, backtesting

**Interface** (no changes needed):
```python
class OperationServiceProxy:
    async def get_operation(operation_id: str, force_refresh: bool) -> dict
    async def get_metrics(operation_id: str, cursor: int) -> tuple[list, int]
    async def cancel_operation(operation_id: str, reason: str) -> dict
```

**Usage in Backtesting**:
```python
# BacktestingService._run_remote_backtest():
proxy = OperationServiceProxy(base_url=remote_url)
ops_service.register_remote_proxy(backend_op_id, proxy, remote_op_id)
# Done! OperationsService handles everything
```

---

### 4.6 Remote Container API (NEW)

**Purpose**: FastAPI application for remote backtest execution.

**Location**: `ktrdr/backtesting/remote_api.py` (NEW)

**Deployment**: Separate container on different machine

#### Endpoints

```python
from fastapi import FastAPI
from ktrdr.backtesting.backtesting_service import BacktestingService
from ktrdr.api.services.operations_service import OperationsService

app = FastAPI()

# Initialize services (same as backend)
operations_service = OperationsService()
backtest_service = BacktestingService(operations_service)

@app.post("/backtests/start")
async def start_backtest(request: BacktestRequest):
    """
    Start backtest on remote container.

    Runs BacktestingService in LOCAL mode (not remote!).
    Returns operation_id for tracking.
    """
    operation_id = await backtest_service.run_backtest(
        symbol=request.symbol,
        timeframe=request.timeframe,
        strategy_config_path=request.strategy_config_path,
        model_path=request.model_path,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
    )

    return {
        "operation_id": operation_id,
        "status": "started",
    }

# Operations endpoints (generic, same code as backend)
@app.get("/api/v1/operations/{operation_id}")
async def get_operation(operation_id: str):
    """Proxy to OperationsService (same as backend)."""
    return await operations_service.get_operation(operation_id)

@app.get("/api/v1/operations/{operation_id}/metrics")
async def get_metrics(operation_id: str, cursor: int = 0):
    """Proxy to OperationsService (same as backend)."""
    return await operations_service.get_operation_metrics(operation_id, cursor)

@app.delete("/api/v1/operations/{operation_id}/cancel")
async def cancel_operation(operation_id: str):
    """Proxy to OperationsService (same as backend)."""
    return await operations_service.cancel_operation(operation_id)
```

**Key Point**: Remote container runs `BacktestingService` in **LOCAL mode**. It doesn't know it's "remote" - that's the backend's concern.

---

## 5. Data Flow Patterns

### 5.1 Local Backtest - Client Query Flow

```
┌──────┐
│Client│ GET /operations/op_backtest_123
└──┬───┘
   │
   ▼
┌─────────────────────────────────────────────────┐
│ API Endpoint                                    │
│ GET /api/v1/operations/op_backtest_123          │
└───────────────────┬─────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│ OperationsService.get_operation()               │
│                                                 │
│ 1. Check cache freshness:                      │
│    last_refresh = _last_refresh[op_id]         │
│    age = now - last_refresh                    │
│                                                 │
│ 2. If age < TTL (1s):                          │
│      Return cached data (instant)              │
│                                                 │
│ 3. Else (stale):                               │
│      _refresh_from_bridge(op_id)               │
└───────────────────┬─────────────────────────────┘
                    │ Cache stale
                    ▼
┌─────────────────────────────────────────────────┐
│ OperationsService._refresh_from_bridge()        │
│                                                 │
│ 1. bridge = _local_bridges[op_id]              │
│ 2. state = bridge.get_status()  ← Memory read  │
│ 3. cursor = _metrics_cursors[op_id]            │
│ 4. metrics, new_cursor = bridge.get_metrics(cursor)│
│ 5. Update operation.progress from state        │
│ 6. Append metrics to operation.metrics["bars"] │
│ 7. _metrics_cursors[op_id] = new_cursor        │
│ 8. _last_refresh[op_id] = now()                │
└───────────────────┬─────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│ BacktestProgressBridge (in-memory)              │
│                                                 │
│ get_status() → Return _current_state copy       │
│ get_metrics(cursor) → Return _metrics[cursor:]  │
└───────────────────┬─────────────────────────────┘
                    ▲
                    │ Worker writes
┌─────────────────────────────────────────────────┐
│ BacktestingEngine (worker thread)               │
│                                                 │
│ For bar in data:                                │
│   process_bar()                                 │
│   if bar % 50 == 0:                             │
│     bridge.update_progress(...) ← <1μs write    │
└─────────────────────────────────────────────────┘
```

**Key Points**:
- Client query triggers cache check
- If stale (>1s), pull from bridge (memory read)
- Worker writes independently (<1μs, no blocking)
- **NO polling** anywhere

---

### 5.2 Remote Backtest - Client Query Flow

```
┌──────┐
│Client│ GET /operations/op_backtest_456
└──┬───┘
   │
   ▼
┌─────────────────────────────────────────────────┐
│ Backend API Endpoint                            │
│ GET /api/v1/operations/op_backtest_456          │
└───────────────────┬─────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│ Backend OperationsService.get_operation()       │
│                                                 │
│ 1. Check cache: stale? (TTL=1s)                │
│ 2. If stale:                                   │
│      _refresh_from_remote_proxy(op_id)         │
└───────────────────┬─────────────────────────────┘
                    │ Cache stale
                    ▼
┌─────────────────────────────────────────────────┐
│ Backend OperationsService._refresh_from_remote_proxy()│
│                                                 │
│ 1. proxy, remote_op_id = _remote_proxies[op_id]│
│ 2. remote_data = await proxy.get_operation(    │
│                       remote_op_id)             │
│    ↓ HTTP GET                                  │
└────┴────────────────────────────────────────────┘
     │
     │ HTTP GET to http://remote:5003/api/v1/operations/{remote_op_id}
     ▼
┌─────────────────────────────────────────────────┐
│ Remote Container (Port 5003)                    │
│                                                 │
│ GET /api/v1/operations/{remote_op_id}           │
│   → Remote OperationsService.get_operation()    │
│   → Check remote cache (TTL=1s)                │
│   → If stale: _refresh_from_bridge()           │
│      → bridge.get_status() (memory read)       │
│   → Return operation data                      │
│                                                 │
└───────────────────┬─────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────────┐
│ Remote BacktestProgressBridge (in-memory)       │
│                                                 │
│ get_status() → Return _current_state            │
└───────────────────┬─────────────────────────────┘
                    ▲
                    │ Worker writes
┌─────────────────────────────────────────────────┐
│ Remote BacktestingEngine (worker thread)        │
│                                                 │
│ For bar in data:                                │
│   bridge.update_progress(...) ← <1μs write      │
└─────────────────────────────────────────────────┘
     │
     │ HTTP Response
     ▼
┌─────────────────────────────────────────────────┐
│ Backend OperationsService                       │
│ 3. Update backend operation from remote_data    │
│ 4. _last_refresh[op_id] = now()                │
│ 5. Return to client                            │
└─────────────────────────────────────────────────┘
```

**Key Points**:
- Two-level caching (backend + remote, both TTL=1s)
- Backend pulls from remote via HTTP only when stale
- Remote pulls from its bridge only when its cache stale
- **NO polling** anywhere
- Same OperationsService code in both places

---

## 6. API Contracts

### 6.1 Backend API

#### POST /api/v1/backtests/start

**Request**:
```json
{
  "symbol": "AAPL",
  "timeframe": "1h",
  "strategy_config_path": "strategies/rsi_mean_reversion.yaml",
  "model_path": "models/rsi_mlp_v1.0.0.pt",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "initial_capital": 100000.0,
  "commission": 0.001,
  "slippage": 0.001
}
```

**Response**:
```json
{
  "operation_id": "op_backtest_20250103_abc123",
  "status": "started",
  "message": "Backtest started for AAPL 1h"
}
```

---

#### GET /api/v1/operations/{operation_id}

**Response** (running):
```json
{
  "operation_id": "op_backtest_20250103_abc123",
  "operation_type": "BACKTESTING",
  "status": "RUNNING",
  "progress": {
    "percentage": 45.2,
    "message": "Backtesting AAPL 1h [2024-06-15 14:30]",
    "current_step": 452,
    "total_steps": 1000,
    "context": {
      "symbol": "AAPL",
      "timeframe": "1h",
      "current_date": "2024-06-15 14:30:00",
      "current_pnl": 2340.50,
      "total_trades": 12,
      "win_rate": 58.3
    }
  },
  "created_at": "2025-01-03T10:00:00Z",
  "updated_at": "2025-01-03T10:05:30Z"
}
```

**Response** (completed):
```json
{
  "operation_id": "op_backtest_20250103_abc123",
  "operation_type": "BACKTESTING",
  "status": "COMPLETED",
  "progress": {
    "percentage": 100.0,
    "message": "Backtest completed",
    "current_step": 1000,
    "total_steps": 1000
  },
  "results": {
    "total_return": 0.0234,
    "sharpe_ratio": 1.23,
    "max_drawdown": 0.05,
    "total_trades": 25,
    "win_rate": 0.56,
    "avg_win": 150.25,
    "avg_loss": -82.10,
    "final_value": 102340.00
  },
  "created_at": "2025-01-03T10:00:00Z",
  "updated_at": "2025-01-03T10:10:00Z",
  "completed_at": "2025-01-03T10:10:00Z"
}
```

---

#### GET /api/v1/operations/{operation_id}/metrics?cursor={n}

**Response**:
```json
{
  "metrics": {
    "bars": [
      {
        "timestamp": "2024-06-15 14:00:00",
        "bar_index": 450,
        "pnl": 2100.50,
        "trades": 11,
        "positions": 1
      },
      {
        "timestamp": "2024-06-15 14:30:00",
        "bar_index": 452,
        "pnl": 2340.50,
        "trades": 12,
        "positions": 0
      }
    ]
  },
  "new_cursor": 452
}
```

---

### 6.2 Remote Container API

**Same endpoints as backend** (OperationsService is same code):

- `POST /backtests/start` - Domain-specific (start backtest)
- `GET /api/v1/operations/{id}` - Generic (OperationsService)
- `GET /api/v1/operations/{id}/metrics` - Generic (OperationsService)
- `DELETE /api/v1/operations/{id}/cancel` - Generic (OperationsService)

---

## 7. Deployment Architecture

### 7.1 Local Mode (Development)

```
┌─────────────────────────────────────────────────┐
│ Docker Container (ktrdr-backend)                │
│  Port: 8000                                     │
│                                                 │
│  ┌───────────────────────────────────────────┐ │
│  │ FastAPI Application                       │ │
│  │  - API endpoints                          │ │
│  │  - OperationsService (singleton)          │ │
│  │  - BacktestingService (local mode)        │ │
│  │  - BacktestingEngine (worker threads)     │ │
│  │  - BacktestProgressBridge (in-memory)     │ │
│  └───────────────────────────────────────────┘ │
│                                                 │
│  Environment:                                   │
│    USE_REMOTE_BACKTEST_SERVICE=false            │
└─────────────────────────────────────────────────┘
```

### 7.2 Remote Mode (Production)

```
┌─────────────────────────────────────────────────┐
│ Backend Container (ktrdr-backend)               │
│  Port: 8000                                     │
│                                                 │
│  ┌───────────────────────────────────────────┐ │
│  │ FastAPI Application                       │ │
│  │  - OperationsService                      │ │
│  │  - BacktestingService (remote mode)       │ │
│  │  - OperationServiceProxy                  │ │
│  └───────────────────────────────────────────┘ │
│                                                 │
│  Environment:                                   │
│    USE_REMOTE_BACKTEST_SERVICE=true             │
│    REMOTE_BACKTEST_SERVICE_URL=http://backtest-worker:5003│
└─────────────────────────────────────────────────┘
                     │
                     │ HTTP
                     ▼
┌─────────────────────────────────────────────────┐
│ Remote Backtest Container                       │
│  Port: 5003                                     │
│  (Different machine/VM/cluster node)            │
│                                                 │
│  ┌───────────────────────────────────────────┐ │
│  │ FastAPI Application                       │ │
│  │  - OperationsService (same code!)         │ │
│  │  - BacktestingService (local mode!)       │ │
│  │  - BacktestingEngine (worker threads)     │ │
│  │  - BacktestProgressBridge (in-memory)     │ │
│  └───────────────────────────────────────────┘ │
│                                                 │
│  Environment:                                   │
│    USE_REMOTE_BACKTEST_SERVICE=false (force local)│
│                                                 │
│  Filesystem (shared or copied):                 │
│    /data/*.pkl                                  │
│    /models/*.pt                                 │
│    /strategies/*.yaml                           │
└─────────────────────────────────────────────────┘
```

### 7.3 Configuration

**Backend**:
```bash
# .env
USE_REMOTE_BACKTEST_SERVICE=false  # or true
REMOTE_BACKTEST_SERVICE_URL=http://backtest-worker:5003
OPERATIONS_CACHE_TTL=1.0  # seconds
```

**Switch Script** (same pattern as training):
```bash
# scripts/switch-backtest-mode.sh
./scripts/switch-backtest-mode.sh local   # Local mode
./scripts/switch-backtest-mode.sh remote  # Remote mode
```

---

## 8. Quality Attributes

### 8.1 Performance

| Metric | Target | How Achieved |
|--------|--------|--------------|
| **Bridge write overhead** | <1μs | Sync-only, memory writes |
| **Cache hit latency** | <1ms | In-memory dict lookup |
| **Cache miss (local)** | <10ms | Memory read from bridge |
| **Cache miss (remote)** | <50ms | HTTP + remote cache |
| **Memory per operation** | <500KB | State + metrics history |

### 8.2 Reliability

**Failure Modes**:

| Component | Failure | Impact | Mitigation |
|-----------|---------|--------|------------|
| Worker crash | Exception in engine | Operation stuck | HealthService timeout detection |
| Bridge memory | Out of memory | Metrics lost | Limit metrics history size |
| Remote container down | HTTP timeout | Stale data | Retry, mark failed after N attempts |
| Network partition | Backend can't reach remote | Stale data | TTL prevents infinite staleness |

### 8.3 Maintainability

**Code Reuse**:
- OperationsService: ✅ Reuse (1 small fix)
- OperationServiceProxy: ✅ Reuse (no changes)
- ServiceOrchestrator: ✅ Reuse (inheritance)
- ProgressBridge: ✅ Reuse (subclass)

**New Code**:
- BacktestingService: ~300 LOC
- BacktestProgressBridge: ~100 LOC
- Remote API: ~150 LOC
- **Total**: ~550 LOC

**Modified Code**:
- BacktestingEngine: +50 LOC (bridge writes)
- OperationsService: +15 LOC (type-aware metrics)

---

## Appendix A: Comparison with Training

| Aspect | Training | Backtesting |
|--------|----------|-------------|
| **Base Class** | ServiceOrchestrator | ServiceOrchestrator (same) |
| **Operations** | OperationsService | OperationsService (same) |
| **Proxy** | OperationServiceProxy | OperationServiceProxy (same) |
| **Local Execution** | register_local_bridge() | register_local_bridge() (same) |
| **Remote Execution** | register_remote_proxy() | register_remote_proxy() (same) |
| **Progress** | Client-driven pull (TTL cache) | Client-driven pull (TTL cache) (same) |
| **Polling** | None | None (same) |
| **Mode Selection** | ENV + switch script | ENV + switch script (same) |
| **Remote Type** | Native host service (GPU) | Container (portable) |

---

**Document Version**: 2.0 (Pull-Based Operations)
**Last Updated**: 2025-01-03
**Next Review**: After implementation Phase 1
