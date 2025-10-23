# Implementation Plan: Pull-Based Operations Architecture

## Document Information
- **Date**: 2025-01-20
- **Status**: APPROVED
- **Timeline**: 4-5 weeks
- **Related Documents**:
  - [Problem Statement](./01-problem-statement-producer-consumer-antipattern.md) - WHY
  - [Design](./04-design-pull-based-operations.md) - WHAT (solution approach)
  - [Architecture](./05-architecture-pull-based-operations.md) - WHAT (structure)
  - **This Document** - DETAILED WHAT + WHEN + ACCEPTANCE CRITERIA

---

## Executive Summary

This plan sequences the work required to implement the pull-based operations architecture, transitioning from the current broken push-based model where sync workers try to call async callbacks.

**Sequencing Strategy**: Local Training → Host Training → Data Loading
- **Local first**: Proves the pattern, fixes M2 metrics bug immediately
- **Host second**: Extends to distributed operations, removes internal polling
- **Data third**: Generalizes the pattern to other operation types

**Critical Path**: M1 → M2 → M3 (M4 can run parallel with M3)

---

## Table of Contents

1. [Milestone Overview](#milestone-overview)
2. [M1: Local Training Pull Architecture](#m1-local-training-pull-architecture)
3. [M2: Host Service Operations API](#m2-host-service-operations-api)
4. [M3: Host Training Pull Architecture](#m3-host-training-pull-architecture)
5. [M4: Data Loading Progress](#m4-data-loading-progress)
6. [M5: Production Readiness](#m5-production-readiness)
7. [Dependencies & Risks](#dependencies--risks)

---

## Milestone Overview

| Milestone | Duration | Deliverable | Blocked By | Risk |
|-----------|----------|-------------|------------|------|
| M1: Local Pull | 5-6 days | Local training with pull-based ops (MVP, no cache) | None | Medium |
| M2: Host OpsAPI | 3-4 days | Host services expose /operations/* | M1 | Low |
| M3: Host Pull | 4-6 days | Host training with pull-based ops | M2 | Medium |
| M4: Data Pull | 3-4 days | Data loading with progress | M1 | Low |
| M5: Production | 2-3 days | Optimized, documented, monitored | M3, M4 | Low |

**Total**: 17-23 days (3.4-4.6 weeks)

**Note**: Caching optimization deferred to future milestone (post-M5) to focus on MVP and faster delivery.

---

## M1: Local Training Pull Architecture (5-6 days)

### Goal
Implement pull-based operations for local training, fixing the broken metrics callback pattern (lines 148-164 in `progress_bridge.py`).

### Context
**Current Problem**: Worker thread calls `asyncio.create_task(self._metrics_callback(...))` which fails with "no running event loop" because it's running in `asyncio.to_thread()` context.

**Solution**: Workers write to bridge synchronously (<1μs). OperationsService pulls from bridge on-demand (client-driven).

**Why This First**:
- Fixes critical M2 metrics bug immediately
- Proves pull pattern works before extending to host services
- Simpler (same process, no HTTP) so easier to validate

**Strategy**:
- Implement pull-only architecture from the start (no dual push/pull mechanisms)
- Defer caching optimization to future milestone (focus on MVP)
- Registry is essential infrastructure (not optional)

### Tasks

#### TASK 1.1: Create ProgressBridge Concrete Class

**Objective**: Create fully-implemented, scenario-independent progress bridge with pull interface.

**Scope**:
- Create **concrete class** (not abstract) with complete implementation
- Provide generic state storage (percentage, message, timestamp, etc.)
- Provide generic metrics storage (append-only list with cursor-based retrieval)
- Thread-safe with RLock
- Protected helpers for subclasses to update state and append metrics

**Files Created**:
- `ktrdr/async_infrastructure/progress_bridge.py`

**Implementation**:
```python
class ProgressBridge:
    """Concrete pull-based progress bridge - scenario-independent."""

    def __init__(self):
        self._current_state: dict[str, Any] = {}
        self._metrics_history: list[dict] = []
        self._lock = threading.RLock()

    # Public pull interface
    def get_status(self) -> dict[str, Any]:
        """Get current state snapshot (pull interface)."""
        with self._lock:
            return self._current_state.copy()

    def get_metrics(self, cursor: int = 0) -> tuple[list[dict], int]:
        """Get metrics since cursor (pull interface)."""
        with self._lock:
            new_metrics = self._metrics_history[cursor:]
            new_cursor = len(self._metrics_history)
            return new_metrics, new_cursor

    # Protected helpers for subclasses
    def _update_state(self, percentage: float, message: str, **kwargs):
        """Update current state (called by subclass on_* methods)."""
        with self._lock:
            self._current_state = {
                "percentage": percentage,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                **kwargs
            }

    def _append_metric(self, metric: dict):
        """Append metric to history (called by subclass)."""
        with self._lock:
            self._metrics_history.append(metric)
```

**Acceptance Criteria**:
- [ ] Concrete class (not abstract) - fully implemented
- [ ] `get_status()` returns snapshot of current state
- [ ] `get_metrics(cursor)` returns incremental metrics + new cursor
- [ ] Thread-safe with RLock
- [ ] Protected `_update_state()` helper for subclasses
- [ ] Protected `_append_metric()` helper for subclasses
- [ ] State storage is generic (dict with percentage, message, timestamp, custom fields)
- [ ] Metrics storage is generic (list of dicts, cursor-based retrieval)
- [ ] Unit tests: `test_get_status_returns_snapshot()`
- [ ] Unit tests: `test_get_metrics_incremental_cursor_based()`
- [ ] Unit tests: `test_thread_safety_concurrent_access()`
- [ ] Code review approved

---

#### TASK 1.2: Integrate ProgressBridge in TrainingProgressBridge

**Objective**: Make TrainingProgressBridge inherit from ProgressBridge and use pull-only mechanism (remove push).

**Scope**:
- Inherit from ProgressBridge (concrete class from 1.1)
- Update all `on_*()` methods to call `self._update_state()` instead of push callbacks
- Update `on_epoch()` to call `self._append_metric()` for epoch metrics
- **Remove push mechanism entirely**: Delete `metrics_callback` parameter and all async callback code
- All methods remain synchronous (no async/await)

**Files Modified**:
- `ktrdr/api/services/training/progress_bridge.py`

**Existing Code to Remove**:
- Lines 29-31: `metrics_callback` parameter from `__init__`
- Line 42: `self._metrics_callback = metrics_callback`
- Lines 148-164: Entire `asyncio.create_task(self._metrics_callback(...))` block and try/except wrapper

**Code Changes**:

1. **Inheritance**: Change from standalone class to inherit from ProgressBridge
2. **Constructor**: Remove `metrics_callback` parameter
3. **Update `on_epoch()`**:
   ```python
   def on_epoch(self, epoch, total_epochs, metrics):
       # Calculate percentage, message, etc. (existing logic)
       percentage = self._derive_percentage(items_processed, epoch_index)
       message = f"Epoch {epoch_index}/{self._total_epochs}"

       # Update state via base class helper
       self._update_state(
           percentage=percentage,
           message=message,
           current_step=epoch_index,
           items_processed=items_processed,
           epoch_index=epoch_index,
           total_epochs=self._total_epochs,
       )

       # Append metric if epoch-level progress
       if metrics.get("progress_type") == "epoch":
           epoch_metric = {
               "epoch": metrics.get("epoch"),
               "train_loss": metrics.get("train_loss"),
               "train_accuracy": metrics.get("train_accuracy"),
               "val_loss": metrics.get("val_loss"),
               "val_accuracy": metrics.get("val_accuracy"),
               "learning_rate": metrics.get("learning_rate"),
               "duration": metrics.get("duration"),
               "timestamp": metrics.get("timestamp"),
           }
           self._append_metric(epoch_metric)
   ```

4. **Update `on_batch()`, `on_phase()`, etc.**: Similar pattern - call `self._update_state()` with appropriate fields

**Acceptance Criteria**:
- [ ] Bridge inherits from ProgressBridge (concrete class)
- [ ] `__init__` no longer accepts `metrics_callback` parameter
- [ ] All `on_*()` methods call `self._update_state()` to update progress
- [ ] `on_epoch()` calls `self._append_metric()` when progress_type="epoch"
- [ ] No `metrics_callback` field in the class
- [ ] No `asyncio.create_task()` calls anywhere in the file
- [ ] No async/await in any `on_*()` methods (must be sync for worker threads)
- [ ] All existing `on_*()` methods still work (same external API)
- [ ] Unit tests: `test_on_epoch_updates_state()`
- [ ] Unit tests: `test_on_epoch_appends_metric()`
- [ ] Unit tests: `test_get_status_returns_current_progress()`
- [ ] Unit tests: `test_get_metrics_returns_epoch_metrics()`
- [ ] Unit tests: `test_on_epoch_is_synchronous()`
- [ ] Performance test: `on_epoch()` completes in <1μs average (10k iterations)
- [ ] Code review approved

---

#### TASK 1.3: Wire OperationsService to Pull from Bridges + Register in TrainingService

**Objective**: Enable OperationsService to discover and pull from bridges, then integrate with TrainingService to register bridges. This task combines registry infrastructure + wiring + registration to enable end-to-end pull flow.

**Scope**:

**Part A - Add Bridge Registry to OperationsService**:
- Add bridge registry (dict mapping operation_id to bridge)
- Add cursor tracking for incremental metrics pull
- Add registration method
- Add refresh method that pulls from bridge

**Part B - Modify get_operation() to Pull from Bridge**:
- Check if bridge registered for operation
- If yes and operation still running, refresh from bridge
- If completed/failed/cancelled, skip refresh (immutable state)

**Part C - Register Bridge in TrainingService**:
- Remove metrics_callback creation in `_run_local_training()`
- Create bridge without callback parameter
- Register bridge with operations service

**Files Modified**:
- `ktrdr/api/services/operations_service.py` (Parts A & B)
- `ktrdr/api/services/training_service.py` (Part C)

**New State to Add (OperationsService)**:
- `self._local_bridges: dict[str, ProgressBridge] = {}` (operation_id → bridge)
- `self._metrics_cursors: dict[str, int] = {}` (operation_id → cursor for incremental metrics)
- `self._remote_proxies: dict[str, OperationServiceProxy] = {}` (empty until M2, for symmetry)

**New Methods to Add (OperationsService)**:
```python
def register_local_bridge(self, operation_id: str, bridge: ProgressBridge) -> None:
    """Register a local bridge for pull-based progress updates."""
    self._local_bridges[operation_id] = bridge
    self._metrics_cursors[operation_id] = 0  # Start cursor at 0
    logger.info(f"Registered local bridge for operation {operation_id}")

def _refresh_from_bridge(self, operation_id: str) -> None:
    """Pull state and metrics from registered bridge and update operation."""
    bridge = self._local_bridges.get(operation_id)
    if not bridge:
        return

    # Pull current state
    state = bridge.get_status()

    # Pull incremental metrics
    cursor = self._metrics_cursors.get(operation_id, 0)
    new_metrics, new_cursor = bridge.get_metrics(cursor)

    # Update operation with fresh data
    operation = self._operations.get(operation_id)
    if operation:
        operation.progress = {
            "percentage": state.get("percentage", 0.0),
            "message": state.get("message", ""),
            "current_step": state.get("current_step", 0),
            "items_processed": state.get("items_processed", 0),
            **state  # Include all other fields from state
        }

        # Append new metrics to operation
        if new_metrics:
            if not hasattr(operation, 'metrics'):
                operation.metrics = []
            operation.metrics.extend(new_metrics)

        # Update cursor
        self._metrics_cursors[operation_id] = new_cursor

    logger.debug(f"Refreshed operation {operation_id} from bridge (cursor {cursor} → {new_cursor})")
```

**Modify Existing Method (OperationsService)**:
```python
async def get_operation(self, operation_id: str) -> OperationInfo:
    """Get operation, refreshing from bridge if registered."""
    operation = self._operations.get(operation_id)
    if not operation:
        raise KeyError(f"Operation {operation_id} not found")

    # Only refresh if operation is still running and bridge is registered
    if operation.status == OperationStatus.RUNNING and operation_id in self._local_bridges:
        self._refresh_from_bridge(operation_id)

    return operation
```

**Changes to TrainingService**:

**Remove**:
- Lines 208-220: Entire `metrics_callback` async function definition
- Line 223: `metrics_callback=metrics_callback` parameter to bridge

**Add**:
- After bridge creation (around line 225):
  ```python
  # Register bridge for pull-based progress
  self.operations_service.register_local_bridge(context.operation_id, bridge)
  logger.info(f"Registered progress bridge for operation {context.operation_id}")
  ```

**Acceptance Criteria**:

**Part A - Registry**:
- [ ] `_local_bridges` dict added to OperationsService
- [ ] `_metrics_cursors` dict added to OperationsService
- [ ] `register_local_bridge()` stores bridge reference and initializes cursor=0
- [ ] `_refresh_from_bridge()` calls `bridge.get_status()` and updates operation
- [ ] `_refresh_from_bridge()` calls `bridge.get_metrics(cursor)` and appends to operation
- [ ] Cursor increments after each successful metrics pull

**Part B - Wiring**:
- [ ] `get_operation()` checks if bridge registered
- [ ] `get_operation()` calls `_refresh_from_bridge()` if operation is running
- [ ] Completed/Failed/Cancelled operations never refresh (immutable state)
- [ ] No cache logic yet (direct pull every time)

**Part C - Registration**:
- [ ] TrainingService no longer creates `metrics_callback` function
- [ ] Bridge created without `metrics_callback` parameter
- [ ] Bridge registered with operations service before training starts
- [ ] Operation ID matches between bridge and operations service

**Testing**:
- [ ] Unit tests: `test_register_local_bridge()`
- [ ] Unit tests: `test_refresh_from_bridge_updates_operation()`
- [ ] Unit tests: `test_get_operation_pulls_from_bridge()`
- [ ] Unit tests: `test_immutable_operations_never_refresh()`
- [ ] Unit tests: `test_metrics_cursor_increments()`
- [ ] Integration test: Start training, query operation, verify progress updated from bridge
- [ ] Integration test: Query operation multiple times, verify metrics accumulate
- [ ] Integration test: No "no running event loop" errors in logs
- [ ] Code review approved

---

#### TASK 1.4: Add Simple TTL Cache to OperationsService

**Objective**: Add minimal cache infrastructure to prevent redundant bridge reads when multiple clients poll the same operation.

**Context**:
- **Level 1 Cache**: ProgressBridge holds state in memory (fast, <1μs writes)
- **Level 2 Cache**: Backend TTL cache prevents redundant bridge reads (avoids unnecessary `get_status()` calls)

**Scope**:
- Add cache timestamp tracking (`_last_refresh`)
- Add configurable TTL (default 1 second)
- Implement cache freshness check in `_refresh_from_bridge()`
- Support `force_refresh` parameter to bypass cache

**Files Modified**:
- `ktrdr/api/services/operations_service.py`

**New State to Add**:
```python
class OperationsService:
    def __init__(self):
        self._operations: dict[str, OperationInfo] = {}
        self._local_bridges: dict[str, ProgressBridge] = {}
        self._metrics_cursors: dict[str, int] = {}
        self._remote_proxies: dict[str, tuple[OperationServiceProxy, str]] = {}

        # NEW: Cache infrastructure
        self._last_refresh: dict[str, float] = {}  # operation_id → timestamp
        self._cache_ttl: float = float(os.getenv("OPERATIONS_CACHE_TTL", "1.0"))

        self._lock = asyncio.Lock()
```

**Implementation**:
```python
def _refresh_from_bridge(self, operation_id: str) -> None:
    """Pull state and metrics from registered bridge with cache awareness."""
    bridge = self._local_bridges.get(operation_id)
    if not bridge:
        return

    # Check cache freshness
    last_refresh = self._last_refresh.get(operation_id, 0)
    age = time.time() - last_refresh

    if age < self._cache_ttl:
        logger.debug(f"Cache hit for operation {operation_id} (age={age:.3f}s)")
        return  # Skip refresh, data is still fresh

    # Cache miss or stale - pull from bridge
    logger.debug(f"Cache miss for operation {operation_id} (age={age:.3f}s) - refreshing")

    # Pull current state
    state = bridge.get_status()

    # Pull incremental metrics
    cursor = self._metrics_cursors.get(operation_id, 0)
    new_metrics, new_cursor = bridge.get_metrics(cursor)

    # Update operation with fresh data
    operation = self._operations.get(operation_id)
    if operation:
        operation.progress = {
            "percentage": state.get("percentage", 0.0),
            "message": state.get("message", ""),
            "current_step": state.get("current_step", 0),
            "items_processed": state.get("items_processed", 0),
            **state  # Include all other fields from state
        }
        operation.updated_at = datetime.now(UTC)

        # Append new metrics to operation
        if new_metrics:
            if not hasattr(operation, 'metrics'):
                operation.metrics = []
            operation.metrics.extend(new_metrics)

        # Update cursor
        self._metrics_cursors[operation_id] = new_cursor

    # Update cache timestamp
    self._last_refresh[operation_id] = time.time()
    logger.debug(f"Refreshed operation {operation_id} from bridge (cursor {cursor} → {new_cursor})")
```

**Update `get_operation()` to support force_refresh**:
```python
async def get_operation(self, operation_id: str, force_refresh: bool = False) -> OperationInfo:
    """Get operation, refreshing from bridge if registered and cache stale."""
    operation = self._operations.get(operation_id)
    if not operation:
        raise KeyError(f"Operation {operation_id} not found")

    # Only refresh if operation is still running and bridge is registered
    if operation.status == OperationStatus.RUNNING and operation_id in self._local_bridges:
        if force_refresh:
            # Force bypass cache
            self._last_refresh[operation_id] = 0  # Invalidate cache
            logger.debug(f"Force refresh requested for operation {operation_id}")

        self._refresh_from_bridge(operation_id)

    return operation
```

**Acceptance Criteria**:
- [ ] `_last_refresh` dict tracks refresh timestamps per operation
- [ ] `_cache_ttl` defaults to 1.0 seconds and is configurable via env var `OPERATIONS_CACHE_TTL`
- [ ] `_refresh_from_bridge()` checks cache age before pulling from bridge
- [ ] Cache hit logs with age (debug level)
- [ ] Cache miss logs with refresh action (debug level)
- [ ] `force_refresh=True` parameter bypasses cache
- [ ] Multiple clients polling within TTL window only trigger one bridge read
- [ ] Cursor still increments correctly with cache (no duplicate metrics)
- [ ] Unit tests: `test_cache_prevents_redundant_refresh()`
- [ ] Unit tests: `test_force_refresh_bypasses_cache()`
- [ ] Unit tests: `test_cache_respects_ttl()`
- [ ] Integration test: Start training, poll from 3 clients within 1s, verify only 1 bridge read
- [ ] Performance: Cache hit response <1ms, cache miss <10ms
- [ ] Code review approved

**Note**: This is a simple in-memory cache. No persistence, no distributed cache, no cache invalidation beyond TTL.

---

#### TASK 1.5: E2E Test Guide for Local Training (HUMAN EXECUTES)

**⚠️ HUMAN RESPONSIBILITY: This task is executed by human, not AI**

**Objective**: Document test scenarios and expected outcomes for human to validate complete local training flow with pull-based operations.

**Scope**:
- Document **scenarios** to test (not specific code implementation)
- Document **expected outcomes** (what should happen)
- Document **how to verify** outcomes (check logs, API responses, etc.)
- Document **troubleshooting steps** (if X fails, check Y)

**Files Created**:
- `docs/testing/e2e-local-training-pull.md` (test guide for human)

**Example Scenario Format**:
```markdown
## Scenario: Progress Updates During Training

**Setup**:
- Ensure backend API is running
- Have test strategy YAML ready

**Actions**:
1. Start training: `ktrdr models train --strategy test_strategy.yaml --symbols AAPL --timeframes 1d`
2. Note the operation_id from response
3. Query progress every 5 seconds: `GET /operations/{operation_id}`

**Expected Outcome**:
- Progress percentage increases from 0% → 100%
- Message shows current epoch: "Epoch X/Y"
- Items_processed increases (batch count)
- No errors in logs

**How to Verify**:
- Check API responses show increasing percentage
- Check backend logs for "Refreshed operation from bridge" debug messages
- Verify NO "no running event loop" errors in logs
- Verify operation.progress fields match bridge state

**If It Fails**:
- Check bridge was registered (search logs for "Registered local bridge for operation")
- Check bridge is being called (add debug logging to `_refresh_from_bridge`)
- Verify operation status is still 'running' (completed ops don't refresh)
- Check that bridge `get_status()` is returning data
```

**Scenarios to Document**:

1. **Start Training and Verify Operation Created**
   - Start training command
   - Verify operation created with status=running
   - Verify operation_id returned

2. **Progress Updates via Pull**
   - Query operation periodically during training
   - Verify progress increases (percentage, current_step)
   - Verify no "event loop" errors

3. **Metrics Collection**
   - Query operation or metrics endpoint
   - Verify epoch metrics are being stored
   - Verify metrics include train_loss, val_loss, accuracy fields

4. **Training Completion**
   - Wait for training to complete
   - Query operation
   - Verify status=completed, percentage=100.0
   - Verify no further refreshes after completion

5. **Bridge Registration Verification**
   - Check logs for bridge registration message
   - Verify registration happens before training starts
   - Verify operation_id matches

6. **Metrics Cursor Behavior**
   - Query operation multiple times
   - Verify metrics accumulate (not duplicated)
   - Verify cursor increments in logs

7. **Error-Free Execution**
   - Scan all logs for errors
   - Verify NO "no running event loop" errors
   - Verify NO async callback failures
   - Verify NO metrics storage warnings

**Troubleshooting Section**:

**Problem**: Progress not updating
- Check: Is bridge registered? (search logs)
- Check: Is `get_operation()` calling `_refresh_from_bridge()`? (debug logs)
- Check: Is bridge `get_status()` returning data? (add logging)

**Problem**: Metrics not stored
- Check: Is `on_epoch()` being called? (training logs)
- Check: Is `_append_metric()` being called? (add logging)
- Check: Is cursor incrementing? (operations service logs)

**Problem**: "No running event loop" error
- This should NOT happen in pull architecture
- If it appears, push mechanism not fully removed
- Check: No `asyncio.create_task()` in TrainingProgressBridge
- Check: No `metrics_callback` parameter

**Acceptance Criteria**:
- [ ] Test guide document created with scenarios (not code)
- [ ] Each scenario describes **what to do** and **what to expect**
- [ ] Verification steps explain **how to check** outcomes
- [ ] Troubleshooting section covers common failure modes
- [ ] No specific test code or pytest fixtures (human executes manually)
- [ ] Document reviewed by tech lead
- [ ] **HUMAN executes test and confirms all scenarios pass**

---

---

### M1 Key Architectural Decisions

**✅ What We're Doing**:
1. **Concrete ProgressBridge** - Fully implemented base class (not abstract), scenario-independent
2. **Pull-Only from Start** - No dual push/pull mechanisms, clean cutover
3. **Registry is Essential** - Not optional, needed for concurrent operations
4. **Simple TTL Cache** - In-memory cache with 1s TTL to prevent redundant bridge reads

**❌ What We're NOT Doing**:
1. **No Dual Mechanisms** - Push code removed in Task 1.2, not kept alongside pull
2. **No Abstract Base** - ProgressBridge is concrete with protected helpers for subclasses
3. **No Complex Caching** - No distributed cache, no persistence, simple TTL only

**Why This Approach**:
- **Faster to MVP**: Simple cache (~50 LOC), essential for performance
- **Cleaner Architecture**: One data flow path (pull-only), no ambiguity
- **Better Testing**: Can't have conflicts between push and pull
- **Performance**: Cache prevents excessive bridge reads with multiple clients

---

### M1 Exit Criteria

**✅ MILESTONE COMPLETED: 2025-01-23**

**Code Deliverables**:
- [x] ProgressBridge concrete class created (scenario-independent)
- [x] TrainingProgressBridge inherits from ProgressBridge
- [x] TrainingProgressBridge uses pull-only mechanism (no push)
- [x] No `metrics_callback` in TrainingProgressBridge
- [x] No `asyncio.create_task()` anywhere in progress bridge
- [x] OperationsService has bridge registry (`_local_bridges`)
- [x] OperationsService has cursor tracking (`_metrics_cursors`)
- [x] OperationsService has TTL cache (`_last_refresh`, `_cache_ttl`)
- [x] OperationsService `get_operation()` pulls from bridge with cache awareness
- [x] `force_refresh` parameter bypasses cache
- [x] TrainingService registers bridges (not callbacks)

**Testing**:
- [x] All unit tests passing (>80% coverage on new code)
- [x] Integration tests passing (start training → query operation → verify progress)
- [x] Performance benchmark: `on_epoch()` < 1μs average (10k iterations)
- [x] E2E test guide created (scenarios, outcomes, verification, troubleshooting)
- [x] **HUMAN has executed E2E test and confirmed all scenarios pass**

**Quality Gates**:
- [x] No "no running event loop" errors in logs
- [x] M2 metrics bug FIXED (metrics stored during training via pull)
- [x] Cache hit rate >80% with multiple concurrent clients (measured in integration tests)
- [x] Code review approved for all tasks

**Success Indicators**:
- ✅ Pull-based architecture working end-to-end for local training
- ✅ Metrics visible via `GET /operations/{id}`
- ✅ No async callback failures
- ✅ Clean separation: worker writes to bridge, OperationsService pulls from bridge
- ✅ Foundation ready for M2 (host services)

**E2E Test Results** (Executed: 2025-01-23):
- **Test Dataset**: EURUSD 1h (2006-2024), 106,732 samples
- **Training Duration**: 49.5 seconds (10 epochs)
- **Final Accuracy**: Train 59.05%, Val 56.07%, Test 56.20%
- **Scenario 1 (Operation Created)**: ✅ PASS
- **Scenario 2 (Progress Updates)**: ✅ PASS - Updates working via MCP
- **Scenario 3 (Metrics Collection)**: ✅ PASS - All 10 epochs captured
- **Scenario 4 (Training Completion)**: ✅ PASS - 100% complete, all metrics stored
- **Scenario 5 (Bridge Registration)**: ✅ PASS - Logs confirm: "Registered local bridge for operation..."
- **Scenario 6 (Cursor Behavior)**: ⚠️ SKIP - Training too fast (49.5s), acceptable
- **Scenario 7 (Error-Free Execution)**: ✅ PASS - **ZERO "no running event loop" errors**

**Key Validation**:
- ✅ NO async/sync boundary violations detected
- ✅ Metrics successfully stored during training (M2 bug confirmed fixed)
- ✅ Bridge registration confirmed in logs before training starts
- ✅ Client-driven pull architecture functioning correctly
- ✅ Training completed successfully with full metrics history

**Commits**:
- `7527d0c` - Task 1.1: ProgressBridge base class
- `510d95b` - Task 1.2: TrainingProgressBridge integration
- `11cd512` - Task 1.3: OperationsService wiring
- `1bc79fb` - Task 1.4: TTL cache implementation
- `1ac18ed` - Task 1.5: E2E test guide creation
- `87a11ec` - Task 1.5: Strategy configuration fix

---

## M2: Host Service Operations API (3-4 days)

### Goal
Deploy OperationsService to host services and expose standard `/operations/*` endpoints, enabling backend to query operations via HTTP.

### Context
**Current**: Host services have custom endpoints (`/training/status/{session_id}`) and custom session management.

**New**: Host services expose standard `/operations/*` API matching backend API, with same OperationsService code.

**Why This Now**:
- Enables M3 (host training pull pattern)
- Proves OperationsService is reusable across services
- Establishes standard operations API contract

### Tasks

#### TASK 2.1: Add OperationsService to Training Host Service

**Objective**: Deploy OperationsService singleton in training host service.

**Scope**:
- Import and initialize OperationsService in host service
- Ensure host service can create operations and register bridges
- Verify no conflicts with existing session management

**Files Modified**:
- `training-host-service/main.py`
- `training-host-service/training/session_manager.py`

**Files Created**:
- `training-host-service/services/operations.py` (wrapper importing from ktrdr)

**New Imports**:
```python
from ktrdr.api.services.operations_service import (
    OperationsService,
    get_operations_service
)
```

**Acceptance Criteria**:
- [ ] Training host service has singleton OperationsService instance
- [ ] `get_operations_service()` returns same instance across calls
- [ ] Host service can import without errors
- [ ] No dependency conflicts with existing code
- [ ] Service starts successfully with OperationsService initialized
- [ ] Code review approved

---

#### TASK 2.2: Add /operations/* Endpoints to Training Host Service

**Objective**: Expose operations API in training host service matching backend API contract.

**Scope**:
- Create FastAPI router with operations endpoints
- Implement: GET /operations/{operation_id}
- Implement: GET /operations/{operation_id}/metrics
- Implement: GET /operations/ (list)
- Register router in host service app

**Files Created**:
- `training-host-service/endpoints/operations.py`

**Files Modified**:
- `training-host-service/main.py` (register router)

**Endpoints to Implement**:
1. `GET /api/v1/operations/{operation_id}?force_refresh=false`
   - Returns: OperationInfo (same format as backend)
   - Calls: `ops_service.get_operation(operation_id, force_refresh)`

2. `GET /api/v1/operations/{operation_id}/metrics?cursor=0`
   - Returns: `{"metrics": [...], "new_cursor": int}`
   - If operation has local bridge, calls `bridge.get_metrics(cursor)` directly
   - Otherwise returns stored metrics from operation

3. `GET /api/v1/operations/?status=&operation_type=`
   - Returns: `{"operations": [...], "total": int, "active_count": int}`
   - Calls: `ops_service.list_operations(...)`

**Acceptance Criteria**:
- [ ] All three endpoints respond successfully
- [ ] Endpoints return same data format as backend operations API
- [ ] `GET /operations/{id}` respects force_refresh parameter
- [ ] `GET /operations/{id}/metrics` returns incremental metrics with cursor
- [ ] 404 returned for non-existent operation_id
- [ ] Endpoints appear in host service Swagger docs
- [ ] Unit tests for each endpoint (mock OperationsService)
- [ ] Integration test: Hit endpoints with real OperationsService
- [ ] Code review approved

---

#### TASK 2.3: Update Training Worker to Create Operations

**Objective**: Modify training host service worker to create operation and register bridge when training starts.

**Scope**:
- When `POST /training/start` is called, create operation in host's OperationsService
- Create ProgressBridge for the training session
- Register bridge with host's OperationsService
- Pass bridge to training worker for progress updates

**Files Modified**:
- `training-host-service/training/session_manager.py`

**Workflow Changes**:
1. **Start training** (`POST /training/start`):
   - Generate session_id
   - Create operation with ID = `f"host_training_{session_id}"`
   - Create TrainingProgressBridge
   - Register bridge with operations service
   - Start training worker with bridge (not callback)
   - Return session_id to client

2. **Training worker**:
   - Receives bridge reference
   - Calls `bridge.on_epoch()`, `bridge.on_batch()`, etc. during training
   - On completion: Call `ops_service.complete_operation(operation_id, result)`
   - On failure: Call `ops_service.fail_operation(operation_id, error)`

**Acceptance Criteria**:
- [ ] Training start creates operation in host's OperationsService
- [ ] Operation ID format: `host_training_{session_id}` (consistent naming)
- [ ] Bridge created and registered before worker starts
- [ ] Worker calls bridge methods (not async callback)
- [ ] Operation marked complete/failed when training ends
- [ ] Integration test: Start training, query `/operations/{id}`, verify progress
- [ ] Integration test: Query `/operations/{id}/metrics`, verify epoch metrics
- [ ] Code review approved

---

#### TASK 2.4: Create OperationServiceProxy

**Objective**: Create HTTP client for querying OperationsService on host services from backend.

**Scope**:
- Create proxy class wrapping httpx client
- Implement methods matching operations API endpoints
- Handle errors (404, timeouts, connection failures)
- Ensure proxy can be shared across adapters (training, data, etc.)

**Files Created**:
- `ktrdr/api/services/adapters/operation_service_proxy.py`

**Methods to Implement**:
- `__init__(base_url: str)` - Initialize with host service URL
- `async def get_operation(operation_id: str, force_refresh: bool = False) -> dict`
- `async def get_metrics(operation_id: str, cursor: int = 0) -> tuple[list[dict], int]`
- `async def list_operations(...) -> dict` (optional, may not be needed)
- `async def close()` - Cleanup HTTP client

**Error Handling**:
- 404 → Raise KeyError (operation not found)
- Connection errors → Log and raise
- Timeouts → Log and raise
- Invalid JSON → Log and raise

**Acceptance Criteria**:
- [ ] Proxy uses httpx.AsyncClient for HTTP requests
- [ ] Proxy constructs correct URLs: `{base_url}/api/v1/operations/...`
- [ ] `get_operation()` includes force_refresh query param
- [ ] `get_metrics()` includes cursor query param
- [ ] Errors translated to appropriate exceptions
- [ ] Unit tests with mocked HTTP responses (using respx)
- [ ] Unit test: Successful GET operation
- [ ] Unit test: Successful GET metrics
- [ ] Unit test: 404 handling
- [ ] Unit test: Connection error handling
- [ ] Code review approved

---

#### TASK 2.5: Implement Remote Refresh in OperationsService

**Objective**: Enable backend OperationsService to refresh operations from host services via proxy.

**Scope**:
- Implement `_refresh_from_remote_proxy()` method (stub in M1)
- Query host service for operation state
- Query host service for incremental metrics
- Update backend operation with remote data

**Files Modified**:
- `ktrdr/api/services/operations_service.py`

**Method Implementation**:

**Cursor Management**:
- Backend (consumer) tracks cursor per operation
- Backend passes cursor to host when querying metrics
- Host/bridge returns delta (metrics since cursor)
- Backend updates cursor with new value from response

`_refresh_from_remote_proxy(operation_id: str)`:
```python
async def _refresh_from_remote_proxy(self, operation_id: str) -> None:
    """Pull state from host service via proxy."""
    if operation_id not in self._remote_proxies:
        return

    proxy, host_operation_id = self._remote_proxies[operation_id]

    # (1) Query host service with HOST's operation ID
    host_data = await proxy.get_operation(host_operation_id)

    # (2) Update backend operation with host's data
    operation = self._operations.get(operation_id)
    if operation:
        operation.status = OperationStatus(host_data["status"])
        operation.progress = host_data["progress"]
        operation.updated_at = datetime.fromisoformat(host_data["updated_at"])

        # (3) Get incremental metrics from host (backend tracks cursor)
        cursor = self._metrics_cursors.get(operation_id, 0)
        host_metrics = await proxy.get_metrics(host_operation_id, cursor)

        # (4) Append new metrics
        if host_metrics["metrics"]:
            if not hasattr(operation, 'metrics'):
                operation.metrics = []
            operation.metrics.extend(host_metrics["metrics"])

            # (5) Update cursor to new value
            self._metrics_cursors[operation_id] = host_metrics["new_cursor"]

        # (6) Update cache timestamp
        self._last_refresh[operation_id] = time.time()

        logger.debug(
            f"Refreshed operation {operation_id} from host {host_operation_id} "
            f"(cursor {cursor} → {host_metrics.get('new_cursor', cursor)})"
        )
```

**Key Point**: Backend maintains cursor and passes it to host. Host service queries bridge with cursor and returns delta.

**Acceptance Criteria**:
- [ ] Method calls proxy to fetch operation state
- [ ] Method calls proxy to fetch incremental metrics
- [ ] Operation status and progress updated from remote data
- [ ] Metrics cursor incremented after each fetch
- [ ] Two-level caching works: backend cache → host service cache → bridge
- [ ] Unit tests with mocked proxy
- [ ] Unit test: Successful remote refresh updates operation
- [ ] Unit test: New metrics appended correctly
- [ ] Unit test: Cursor tracking works correctly
- [ ] Code review approved

---

#### TASK 2.6: Repeat for IB Host Service

**Objective**: Deploy same operations API to IB host service (copy of 2.1-2.3 for IB).

**Scope**: Same as 2.1-2.3 but for IB host service instead of training host service.

**Files Created**:
- `ib-host-service/endpoints/operations.py`
- `ib-host-service/services/operations.py`

**Files Modified**:
- `ib-host-service/main.py`
- `ib-host-service/data/session_manager.py` (or equivalent)

**Acceptance Criteria**:
- [ ] IB host service exposes `/operations/*` endpoints
- [ ] IB host service creates operations for data loading
- [ ] IB host service registers bridges
- [ ] Endpoints tested and working
- [ ] Code review approved

---

### M2 Exit Criteria
- [ ] Training host service exposes `/operations/*` endpoints
- [ ] IB host service exposes `/operations/*` endpoints
- [ ] Both host services create operations and register bridges
- [ ] OperationServiceProxy implemented and tested
- [ ] Backend OperationsService can refresh from remote proxies
- [ ] Two-level caching working (backend + host service)
- [ ] Integration tests: Backend queries host service operations successfully
- [ ] Same OperationsService code runs in backend and both host services
- [ ] No breaking changes to existing APIs (custom endpoints still work)

---

## M3: Host Training Pull Architecture - Convergence (4-6 days)

### Goal
Achieve **code convergence**: Make host training use the SAME orchestrator as local training. Eliminate all internal polling.

### Context
**Current Problem**:
- `HostSessionManager.poll_session()` has internal `while True` loop (line 130-192 in `host_session.py`) that polls every 2-10 seconds
- Different orchestration code for local vs host training
- Backend tries to orchestrate remote training (architectural smell)

**Solution**:
- Host service runs **same TrainingOrchestrator** as local training (convergence!)
- Backend registers OperationServiceProxy for client-driven queries
- Completion discovered when clients query (no background monitor)

**Key Insight**: After M3, local and host training differ ONLY in location. Same code, different process.

**Why This Now**: M2 provides the infrastructure (/operations/* API), now we converge the implementations and eliminate polling.

### Tasks

#### TASK 3.1: Use Same Orchestrator Code for Host Training

**Objective**: Make host training use the SAME TrainingOrchestrator as local training, running in host service. Backend simply registers proxy for client-driven progress queries.

**Key Architectural Change**:
- **Before**: Different orchestration for local vs host (HostSessionManager polling)
- **After**: SAME orchestrator code runs in both places (local: backend process, host: host service process)

**Scope**:

**Part A - Host Service Uses TrainingOrchestrator**:
- Host service already has TrainingOrchestrator available (shared code)
- When `POST /training/start` is called on host service:
  - Create operation in host's OperationsService
  - Create ProgressBridge
  - Register bridge with host's OperationsService
  - Run **same TrainingOrchestrator** as local training
  - Worker calls `bridge.on_epoch()`, `bridge.on_batch()`, etc.
  - On completion: Orchestrator calls `host_ops_service.complete_operation()`

**Part B - Backend Acts as Pure Proxy for Host Training**:

**Key Principle**: When in host training mode, backend is a **transparent proxy** - it creates a local operation record but all state lives on the host.

**Backend Operation Creation**:
```python
async def _run_host_training(self, *, context: TrainingOperationContext) -> dict[str, Any]:
    """
    Run host training - backend acts as proxy.

    Backend does NOT run orchestrator, does NOT create bridge.
    Host service runs orchestrator and creates bridge.
    Backend only proxies requests.
    """
    # (1) Start training on host service
    response = await self.adapter.train_multi_symbol_strategy(
        symbols=context.symbols,
        config=context.config,
        # HTTP POST to host service /training/start
    )
    session_id = response["session_id"]

    # (2) Derive host's operation ID (known naming convention)
    host_operation_id = f"host_training_{session_id}"

    # (3) Register proxy with BOTH IDs
    proxy = OperationServiceProxy(
        base_url=os.getenv("TRAINING_HOST_SERVICE_URL")
    )

    # Store mapping: backend_operation_id → (proxy, host_operation_id)
    self.operations_service.register_remote_proxy(
        backend_operation_id=context.operation_id,  # e.g., "op_training_20250120_abc123"
        proxy=proxy,
        host_operation_id=host_operation_id,  # e.g., "host_training_xyz789"
    )

    # (4) Store metadata for cancellation and debugging
    operation = self.operations_service._operations[context.operation_id]
    operation.metadata["session_id"] = session_id
    operation.metadata["host_operation_id"] = host_operation_id
    operation.metadata["host_service_url"] = os.getenv("TRAINING_HOST_SERVICE_URL")

    # (5) Backend returns IMMEDIATELY (no orchestrator, no waiting)
    logger.info(
        f"Registered proxy for operation {context.operation_id} → host {host_operation_id}"
    )

    return {"session_id": session_id}
```

**Backend Query Flow**:
```python
# When client queries backend:
GET /operations/op_training_20250120_abc123

# Backend's get_operation():
async def get_operation(self, operation_id: str, force_refresh: bool = False):
    operation = self._operations[operation_id]

    # Check if this is a remote operation
    if operation_id in self._remote_proxies:
        # YES - refresh from host service
        proxy, host_op_id = self._remote_proxies[operation_id]

        # Query host service using HOST's operation ID
        host_operation = await proxy.get_operation(host_op_id)  # ← Uses host ID

        # Update backend's operation record with host's data
        operation.status = host_operation["status"]
        operation.progress = host_operation["progress"]
        operation.updated_at = host_operation["updated_at"]

        # If host says COMPLETED, mark backend operation complete too
        if operation.status == OperationStatus.COMPLETED:
            # Fetch final results from host
            results = await proxy.get_results(host_op_id)
            await self.complete_operation(operation_id, results)

    return operation
```

**Update OperationsService to Support ID Mapping**:

```python
class OperationsService:
    def __init__(self):
        # ...
        # Store mapping: backend_op_id → (proxy, host_op_id)
        self._remote_proxies: dict[str, tuple[OperationServiceProxy, str]] = {}

    def register_remote_proxy(
        self,
        backend_operation_id: str,
        proxy: OperationServiceProxy,
        host_operation_id: str,
    ) -> None:
        """
        Register proxy for remote operation tracking.

        Args:
            backend_operation_id: Operation ID in backend (e.g., "op_training_abc123")
            proxy: HTTP client for host service
            host_operation_id: Operation ID on host service (e.g., "host_training_xyz789")
        """
        self._remote_proxies[backend_operation_id] = (proxy, host_operation_id)
        logger.info(
            f"Registered remote proxy: {backend_operation_id} → {host_operation_id}"
        )
```

**Part C - Client-Driven Completion Discovery**:
- Clients (CLI, Web UI) query: `GET /operations/{backend_op_id}`
- Backend's `get_operation()` calls `proxy.get_operation(host_op_id)` → HTTP to host
- Host returns operation with current status
- If status = COMPLETED:
  - Backend fetches results: `proxy.get_results(host_op_id)`
  - Backend calls `ops_service.complete_operation(backend_op_id, results)`
  - Backend operation marked complete
- No polling task needed!

**Explicit Lifecycle Acceptance Criteria**:
- [ ] Host service DOES NOT push completion notification to backend
- [ ] Host service DOES NOT poll backend to notify completion
- [ ] Backend DOES NOT poll host service for completion
- [ ] Completion discovered ONLY when client queries backend
- [ ] Backend's `get_operation()` queries host, discovers status=COMPLETED
- [ ] Backend fetches results from host when completion detected
- [ ] Backend marks its own operation complete
- [ ] Zero background tasks running (verified with async task inspection)
- [ ] Integration test: Complete training on host, DON'T query backend for 5 minutes, verify operation stays RUNNING (not auto-completed)
- [ ] Integration test: Complete training on host, query backend once, verify operation marked COMPLETED

**Part D - HealthService (DEFERRED TO POST-M5)**:
- HealthService implementation deferred
- Stuck/timeout operations may remain RUNNING indefinitely
- Acceptable for M1-M5 scope
- Doctor service will handle this later

**Part E - Backend Routing Logic** (CRITICAL):
Backend's initialization differs based on local vs host training:

**Local Training Path**:
```python
# Backend runs orchestrator in-process
operation_id = ops_service.create_operation(...)
bridge = ProgressBridge()
ops_service.register_local_bridge(operation_id, bridge)

orchestrator = TrainingOrchestrator(config, symbols, bridge, ...)
await orchestrator.run()  # Blocks until complete
return operation_id
```

**Host Training Path**:
```python
# Backend proxies requests to host service
operation_id = ops_service.create_operation(...)

# (1) Proxy training START to host
session_id = await adapter.train_multi_symbol_strategy(...)  # HTTP

# (2) Register proxy for OPERATIONS
host_op_id = f"host_training_{session_id}"
proxy = OperationServiceProxy(host_url)
ops_service.register_remote_proxy(operation_id, proxy)

return operation_id  # Returns immediately (no orchestrator!)
```

**Key Difference**:
- **Local**: Backend creates orchestrator, bridge, runs training
- **Host**: Backend proxies (1) training start AND (2) operations queries
- **Host orchestrator runs on host service**, not backend

**Files Modified**:
- `ktrdr/api/services/training_service.py` (backend - add routing logic)
- `training-host-service/training/session_manager.py` (host service)

**Existing Code to Remove**:
- Backend: Lines 233-276: Entire HostSessionManager flow
- Backend: Bridge creation for host training (lines 246-257)

**Acceptance Criteria**:

**Part A - Host Service**:
- [ ] Host service uses TrainingOrchestrator (same as local)
- [ ] Host service creates ProgressBridge and registers with host's OperationsService
- [ ] Host worker calls `bridge.on_epoch()`, `bridge.on_batch()` (same as local)
- [ ] Host orchestrator calls `host_ops_service.complete_operation()` on finish

**Part B - Backend**:
- [ ] `_run_host_training()` no longer creates HostSessionManager
- [ ] `_run_host_training()` no longer creates TrainingProgressBridge
- [ ] `_run_host_training()` no longer creates orchestrator
- [ ] Backend stores BOTH operation IDs (backend's + host's)
- [ ] `register_remote_proxy()` takes three parameters: backend_id, proxy, host_id
- [ ] Backend uses HOST's operation ID when querying host service
- [ ] Backend's operation ID remains stable (clients use backend ID)
- [ ] Metadata includes session_id, host_operation_id, host_service_url
- [ ] Backend returns immediately after registration (no waiting, no monitoring)
- [ ] Logging shows mapping: "backend_op → host_op"

**Part C - Completion Discovery**:
- [ ] Backend `get_operation()` pulls from host via proxy
- [ ] When host operation completed, backend detects and marks complete
- [ ] Backend fetches results from host
- [ ] No background polling task exists

**Part E - Backend Routing**:
- [ ] Backend has routing logic to decide local vs host
- [ ] Local path: Creates orchestrator, bridge, runs in-process
- [ ] Host path: Proxies training start (HTTP), registers proxy (no orchestrator)
- [ ] Local path: Backend returns after orchestrator completes
- [ ] Host path: Backend returns immediately after proxy registration
- [ ] Routing decision based on environment variable or config

**Part F - Testing**:
- [ ] Integration test: Local training uses orchestrator in backend
- [ ] Integration test: Host training proxies to host service (no backend orchestrator)
- [ ] Integration test: Start host training, verify orchestrator runs on HOST
- [ ] Integration test: Query from client, verify progress pulled from host
- [ ] Integration test: Verify completion detected when client queries
- [ ] Integration test: Backend ID ≠ Host ID, queries still work
- [ ] Integration test: Client uses backend ID, never needs to know host ID
- [ ] Integration test: Logging shows operation ID mapping
- [ ] Verify NO polling tasks in backend (no HealthService, no monitors)
- [ ] Code review approved

---

#### TASK 3.2: Deprecate Custom Status Endpoint

**Objective**: Mark `/training/status/{session_id}` as deprecated, redirect to `/operations/*`.

**Scope**:
- Keep endpoint functional but add deprecation warning
- Internally query OperationsService instead of custom logic
- Return response in old format for compatibility
- Add `deprecated: true` flag and migration guidance in response

**Files Modified**:
- `training-host-service/endpoints/training.py`

**Endpoint Changes**:
`GET /training/status/{session_id}`:
- Map session_id to operation_id: `f"host_training_{session_id}"`
- Query: `ops_service.get_operation(operation_id)`
- Convert OperationInfo to old status format
- Add fields: `"deprecated": true`, `"use_instead": "/operations/{operation_id}"`

**Response Format** (backward compatible):
```json
{
  "session_id": "abc123",
  "status": "running",
  "progress": {"percentage": 45.0, "current_step": "Epoch 45/100"},
  "deprecated": true,
  "use_instead": "/api/v1/operations/host_training_abc123"
}
```

**Acceptance Criteria**:
- [ ] Endpoint still functional (no breaking changes)
- [ ] Endpoint queries OperationsService internally
- [ ] Response includes deprecation warning
- [ ] Response includes migration path to new API
- [ ] Integration test: Old endpoint works as before
- [ ] Integration test: New `/operations/*` endpoint returns same data
- [ ] Code review approved

---

#### TASK 3.3: Remove TrainingAdapter.get_training_status()

**Objective**: Mark method as deprecated since custom status endpoint is being phased out.

**Scope**:
- Add deprecation warning to method
- Update docstring with migration guidance
- Method still works (calls old endpoint) for compatibility

**Files Modified**:
- `ktrdr/training/training_adapter.py`

**Changes**:
- Add decorator: `@deprecated("Use OperationServiceProxy.get_operation() instead")`
- Update docstring explaining migration
- Keep implementation (still calls `/training/status/{session_id}`)

**Acceptance Criteria**:
- [ ] Method has deprecation warning
- [ ] Method still functional (no breaking changes)
- [ ] Deprecation warning appears in logs when called
- [ ] Documentation updated with migration guide
- [ ] Code review approved

---

#### TASK 3.4: E2E Test Guide for Host Training (HUMAN EXECUTES)

**⚠️ HUMAN RESPONSIBILITY: This task is executed by human, not AI**

**Objective**: Provide test guide for human to validate host training with pull-based architecture.

**Scope**:
- Document test scenarios for human to execute manually
- Document what to verify at each step
- Document how to verify two-level caching
- Document how to verify no internal polling

**Files Created**:
- `docs/testing/e2e-host-training-pull.md` (test guide for human)

**Test Scenarios to Document**:
1. **Start Host Training**:
   - Ensure training host service is running
   - Command: `ktrdr models train --strategy test_strategy.yaml --symbols AAPL --timeframes 1d`
   - Verify: Operation created, session_id returned, status=running

2. **Verify Proxy Registration (Not Bridge)**:
   - Check backend logs for "Registered remote proxy for operation {id}"
   - Verify: NO log message about "Registered local bridge"
   - How to check: `grep "Registered.*proxy" backend.log`

3. **Verify Host Service Bridge**:
   - Check host service logs for "Registered local bridge for operation host_training_{session_id}"
   - Verify: Host service has bridge, backend has proxy
   - This proves distributed architecture working

4. **Query Operation (Two-Level Cache)**:
   - Command: `GET /operations/{operation_id}`
   - Verify backend cache hit: Check backend logs for cache decision
   - Verify host service cache hit: Check host service logs
   - Document how to trace request flow: backend → proxy → host → bridge

5. **Progress Updates via Proxy**:
   - Query operation every 5 seconds
   - Verify: Progress percentage increasing
   - Check backend logs: "Refreshed operation {id} from remote proxy"
   - Check host service logs: "Refreshed operation {host_id} from local bridge"

6. **Verify No Internal Polling**:
   - Check backend async tasks: Should NOT have ANY polling loops
   - Command to check: `grep "HostSessionManager" backend.log` (should be empty)
   - Command to check: `grep "monitor.*completion" backend.log` (should be empty)
   - Verify: ONLY HealthService queries periodically (external monitoring, 60s interval)
   - Backend should have NO background tasks for this operation

7. **Completion via Client-Driven Discovery**:
   - Wait for training to complete on host service
   - Query backend operation: `GET /operations/{operation_id}`
   - Verify: Backend pulls from host, discovers status=COMPLETED
   - Verify: Backend fetches results from host
   - Verify: Backend operation marked complete
   - Check logs: "Completed operation {id} with results" (no monitor logs)

8. **Metrics Storage in Backend**:
   - Command: `GET /operations/{operation_id}/metrics`
   - Verify: Metrics pulled from host service and stored in backend
   - Verify: Metrics match host service metrics
   - Command to compare: Query host `/operations/host_training_{session_id}/metrics`

9. **Deprecated Endpoint Verification**:
   - Command: `GET /training/status/{session_id}` on host service
   - Verify: Still works (backward compatibility)
   - Verify: Response includes `"deprecated": true`
   - Verify: Response includes migration guidance

**Acceptance Criteria**:
- [ ] Test guide document created with all scenarios
- [ ] Each scenario has clear commands and log checks
- [ ] Document explains two-level caching flow
- [ ] Document shows how to verify no internal polling
- [ ] Troubleshooting section included
- [ ] Document reviewed by tech lead
- [ ] **HUMAN executes test and confirms all scenarios pass**

---

### M3 Exit Criteria

**Code Convergence**:
- [ ] Host service uses **same TrainingOrchestrator** as local training
- [ ] Host service uses **same ProgressBridge** as local training
- [ ] Host service uses **same worker code** (calls bridge.on_epoch(), etc.)
- [ ] Host orchestrator calls `host_ops_service.complete_operation()` on finish
- [ ] Local and host differ ONLY in location (backend process vs host service process)

**Backend Changes**:
- [ ] HostSessionManager no longer used (deleted)
- [ ] `_run_host_training()` registers OperationServiceProxy (not orchestrator)
- [ ] `_run_host_training()` returns immediately (no waiting, no monitoring)
- [ ] Backend has NO orchestrator for host training (runs on host)
- [ ] Backend has NO completion monitor (client-driven discovery)

**Completion Flow**:
- [ ] Client queries trigger completion discovery (no background polling)
- [ ] Backend detects completion when pulling from host via proxy
- [ ] Backend fetches results from host when complete
- [ ] HealthService is ONLY background task (external monitoring, 60s interval)

**Deprecation**:
- [ ] Custom `/training/status/{session_id}` deprecated but functional
- [ ] `TrainingAdapter.get_training_status()` deprecated but functional

**Quality Gates**:
- [ ] No internal polling loops anywhere (verified via async task inspection)
- [ ] Backend queries host service via OperationServiceProxy
- [ ] Two-level caching working (backend → host → bridge)
- [ ] Integration tests passing
- [ ] E2E test guide created
- [ ] **HUMAN has executed E2E test and confirmed all scenarios pass**

**Success Indicators**:
- Same code, different location (convergence achieved)
- Client-driven progress and completion (no polling)
- Clean separation: host runs orchestrator, backend registers proxy

---

## M4: Data Loading Progress (3-4 days)

### Goal
Extend pull-based pattern to data loading operations (generalize the architecture).

### Context
**Current**: Data loading may not have consistent progress reporting.

**New**: Apply same pull-based pattern using DataLoadingProgressBridge.

**Why Now**: Pattern is proven (M1) and generalized (M3), easy to apply to data loading.

**Note**: This can run in parallel with M3 since it depends only on M1.

### Tasks

#### TASK 4.1: Create DataLoadingProgressBridge

**Objective**: Create progress bridge for data loading domain using same pull interface.

**Scope**:
- Create bridge implementing ProgressBridgeBase
- Define data loading specific progress events (symbol_progress, rows_loaded, etc.)
- Store state and metrics for data loading

**Files Created**:
- `ktrdr/data/data_loading_progress_bridge.py`

**Progress Events to Support**:
- `on_symbol_started(symbol, symbol_index, total_symbols)`
- `on_symbol_progress(symbol, rows_loaded, total_rows_estimate)`
- `on_symbol_completed(symbol, rows_loaded, duration)`
- `on_validation(step, message)` (e.g., "Validating symbol format")

**State Fields**:
- percentage (based on symbols completed / total symbols)
- current_step (e.g., "Loading AAPL (2/5)")
- rows_loaded (cumulative)
- current_symbol

**Metrics to Store**:
- Per-symbol metrics: symbol, rows_loaded, duration, validation_time
- Aggregate metrics: total_rows_loaded, symbols_completed

**Acceptance Criteria**:
- [ ] Bridge inherits from ProgressBridgeBase
- [ ] `get_state()` returns current data loading state
- [ ] `get_metrics(cursor)` returns per-symbol metrics incrementally
- [ ] All `on_*()` methods are synchronous (<1μs overhead)
- [ ] State includes data-loading-specific fields
- [ ] Unit tests for all progress events
- [ ] Unit tests for state/metrics pull interface
- [ ] Code review approved

---

#### TASK 4.2: Update DataManager to Register Bridge

**Objective**: Modify data loading flow to create operation and register bridge.

**Scope**:
- When data loading starts, create operation
- Create DataLoadingProgressBridge
- Register bridge with OperationsService
- Pass bridge to data loading worker
- Mark operation complete/failed when done

**Files Modified**:
- `ktrdr/data/data_manager.py`
- `ktrdr/data/data_loader.py` (or wherever loading logic lives)

**Workflow**:
1. `load_historical_data()` called
2. Create operation (type=DATA_LOADING)
3. Create DataLoadingProgressBridge
4. Register bridge with operations service
5. Call data loading worker with bridge reference
6. Worker calls bridge methods during loading
7. Mark operation complete with result summary (rows loaded, duration, etc.)

**Acceptance Criteria**:
- [ ] Data loading creates operation before starting
- [ ] Bridge created and registered with operations service
- [ ] Worker receives bridge reference (not callback)
- [ ] Worker calls bridge methods during loading
- [ ] Operation marked complete/failed when done
- [ ] Result summary includes rows_loaded, symbols_loaded, duration
- [ ] Integration test: Start data loading, query operation, verify progress
- [ ] Integration test: Query metrics, verify per-symbol metrics stored
- [ ] Code review approved

---

#### TASK 4.3: E2E Test Guide for Data Loading (HUMAN EXECUTES)

**⚠️ HUMAN RESPONSIBILITY: This task is executed by human, not AI**

**Objective**: Provide test guide for human to validate data loading with pull-based progress.

**Scope**:
- Document test scenarios for human to execute manually
- Document what to verify for data loading progress
- Document metrics verification

**Files Created**:
- `docs/testing/e2e-data-loading-pull.md` (test guide for human)

**Test Scenarios to Document**:
1. **Start Data Loading**:
   - Command: `ktrdr data load AAPL 1d --start-date 2024-01-01 --end-date 2024-12-31`
   - Verify: Operation created, operation_id returned, status=running

2. **Query During Loading**:
   - Command: `GET /operations/{operation_id}` while loading
   - Verify: Progress percentage increasing (0% → 100%)
   - Verify: current_step shows "Loading AAPL (1/1)" or similar

3. **Verify Symbol Progress**:
   - If loading multiple symbols, verify current_step updates per symbol
   - Example: "Loading AAPL (1/3)" → "Loading MSFT (2/3)" → "Loading GOOGL (3/3)"

4. **Query Metrics**:
   - Command: `GET /operations/{operation_id}/metrics`
   - Verify: Per-symbol metrics stored
   - Expected fields: symbol, rows_loaded, duration, validation_time

5. **Completion**:
   - Wait for loading to complete
   - Verify: status=completed, percentage=100.0
   - Verify: result_summary includes total rows_loaded, symbols_loaded, duration

6. **Data Verification**:
   - Command: `ktrdr data show AAPL 1d --start-date 2024-01-01 --limit 10`
   - Verify: Data loaded correctly, matches expected date range
   - Verify: OHLCV columns present

7. **Error Checks**:
   - Check logs for errors during loading
   - Verify no "no running event loop" errors
   - Verify bridge overhead is low (worker performance)

**Acceptance Criteria**:
- [ ] Test guide document created with all scenarios
- [ ] Each scenario has clear commands
- [ ] Document explains data loading specific progress fields
- [ ] Troubleshooting section included
- [ ] Document reviewed by tech lead
- [ ] **HUMAN executes test and confirms all scenarios pass**

---

### M4 Exit Criteria
- [ ] DataLoadingProgressBridge created
- [ ] DataManager creates operations and registers bridges
- [ ] Data loading progress visible to clients
- [ ] Metrics stored for data loading operations
- [ ] Integration test passing
- [ ] E2E test guide created
- [ ] **HUMAN has executed E2E test and confirmed all scenarios pass**
- [ ] Pattern consistent with training (same ProgressBridgeBase)

---

## M5: Production Readiness (2-3 days)

### Goal
Optimize, clean up, document, and prepare for production deployment.

### Context
All functionality working. Now focus on:
- Performance optimization
- Code cleanup (remove deprecated code)
- Documentation
- Monitoring

### Tasks

#### TASK 5.1: Performance Optimization

**Objective**: Validate performance targets and optimize if needed.

**Scope**:
- Benchmark worker overhead (on_epoch, on_batch, etc.)
- Benchmark cache hit latency
- Benchmark cache miss latency (local and remote)
- Tune cache TTL based on measurements
- Optimize hot paths if needed

**Performance Targets**:
- Worker callback overhead: <1μs average
- Cache hit query: <1ms
- Cache miss local query: <10ms
- Cache miss remote query: <50ms
- Cache hit rate: >90% (measure with real workload)

**Files Created**:
- `tests/performance/test_bridge_overhead.py`
- `tests/performance/test_cache_performance.py`

**Acceptance Criteria**:
- [ ] Benchmark tests written and passing
- [ ] Worker overhead measured: <1μs confirmed
- [ ] Cache hit latency measured: <1ms confirmed
- [ ] Cache miss latencies within targets
- [ ] Cache hit rate measured with simulated workload
- [ ] If targets not met: optimization performed and re-measured
- [ ] Performance report document created
- [ ] Code review approved

---

#### TASK 5.2: Remove Deprecated Code

**Objective**: Remove old polling code and deprecated endpoints.

**Scope**:
- Remove HostSessionManager class (replaced by proxy pattern)
- Remove broken metrics_callback code
- Remove custom host service polling logic
- Keep deprecated endpoints for now (full removal later)

**Files to Delete**:
- `ktrdr/api/services/training/host_session.py`

**Files to Modify** (remove sections):
- `ktrdr/api/services/operations_service.py`:
  - Remove `_update_training_operation_from_host_service()` (lines 561-723)
  - Remove any custom polling logic

**Files to Verify Clean**:
- `ktrdr/api/services/training/progress_bridge.py` - no metrics_callback references
- `ktrdr/api/services/training_service.py` - no HostSessionManager imports

**Acceptance Criteria**:
- [ ] HostSessionManager file deleted
- [ ] No imports of HostSessionManager anywhere
- [ ] No references to `_update_training_operation_from_host_service`
- [ ] `grep -r "metrics_callback"` finds nothing (except in tests for old behavior)
- [ ] All tests still passing after deletion
- [ ] Code review approved

---

#### TASK 5.3: Documentation

**Objective**: Document the new architecture for developers and operators.

**Scope**:
- Update CLAUDE.md with pull-based architecture
- Create architecture diagrams
- Document operations API
- Create migration guide

**Documents to Create/Update**:

1. **Update CLAUDE.md**:
   - Add section on pull-based operations
   - Update flow diagrams
   - Document OperationsService cache behavior
   - Document bridge registration pattern

2. **Create Architecture Diagrams**:
   - `docs/architecture/operations/diagrams/local-training-flow.svg`
   - `docs/architecture/operations/diagrams/host-training-flow.svg`
   - `docs/architecture/operations/diagrams/cache-behavior.svg`

3. **API Documentation**:
   - Document `/operations/*` endpoints
   - Document OperationServiceProxy usage
   - Document ProgressBridgeBase interface

4. **Migration Guide**:
   - `docs/architecture/operations/migration-guide.md`
   - How to add new operation types
   - How to create custom progress bridges
   - How to add progress tracking to existing operations

**Acceptance Criteria**:
- [ ] CLAUDE.md updated with pull-based architecture
- [ ] Architecture diagrams created
- [ ] API documentation complete
- [ ] Migration guide complete
- [ ] Documentation reviewed by team
- [ ] No broken links or outdated references

---

#### TASK 5.4: Monitoring and Metrics

**Objective**: Add monitoring for operations service health and performance.

**Scope**:
- Add metrics collection to OperationsService
- Add logging for cache behavior
- Add performance warnings for slow queries
- Create monitoring dashboard (optional)

**Metrics to Collect**:
- Cache hits / cache misses (per operation type)
- Cache hit rate percentage
- Refresh duration (local vs remote)
- Operations created / completed / failed (per type)
- Active operations count
- Metrics pull size (bytes per cursor increment)

**Logging to Add**:
- Cache refresh events (debug level)
- Slow queries (>100ms - warning level)
- Proxy errors (error level)

**Files Modified**:
- `ktrdr/api/services/operations_service.py`

**Acceptance Criteria**:
- [ ] Metrics class created with counters
- [ ] OperationsService updates metrics on each operation
- [ ] Cache hit rate calculation available
- [ ] Logging added for key events
- [ ] Metrics exposed via health endpoint or Prometheus
- [ ] Optional: Grafana dashboard created
- [ ] Code review approved

---

### M5 Exit Criteria

**Code Quality**:
- [ ] Performance benchmarks passing
- [ ] Deprecated code removed
- [ ] Documentation complete and reviewed
- [ ] Monitoring in place
- [ ] All tests passing (unit + integration + e2e + performance)
- [ ] Production deployment plan ready
- [ ] Code review complete
- [ ] Ready for production rollout

**Known Limitations** (Post-M5 Roadmap):
- [ ] No automatic timeout detection - operations may stay RUNNING indefinitely if not queried
- [ ] No stuck detection - Doctor service will handle this later
- [ ] No alerting - monitoring is observability only (logs, metrics)
- [ ] NO polling tasks exist anywhere in backend (verified)

**Acceptance**:
- [ ] Team acknowledges operations can stay RUNNING forever without client queries
- [ ] Doctor service implementation planned for post-M5 milestone
- [ ] HealthService deferred to post-M5

---

## Dependencies & Risks

### Critical Path
```
M1 (Local Pull) → M2 (Host API) → M3 (Host Pull) → M5 (Production)
       ↓
   M4 (Data Pull) → M5 (Production)
```

**Parallel Work**:
- M4 can start after M1 completes (doesn't need M2/M3)
- M2 tasks 2.1-2.3 (training) and 2.6 (IB) can be done in parallel

### Dependencies

**M1 depends on**:
- None (starting point)

**M2 depends on**:
- M1 complete (ProgressBridgeBase and pull pattern proven)

**M3 depends on**:
- M2 complete (/operations/* API available on host services)

**M4 depends on**:
- M1 complete (pull pattern proven)
- Does NOT depend on M2/M3 (can run in parallel)

**M5 depends on**:
- M3 complete (host training working)
- M4 complete (data loading working)

### Risks

#### Risk 1: Performance Regression
**Impact**: High
**Probability**: Medium
**Mitigation**:
- Benchmark in M1 before proceeding
- Performance tests in M5
- Rollback plan ready

#### Risk 2: Unexpected Code Differences
**Impact**: Medium
**Probability**: Medium
**Mitigation**:
- M0 analysis identifies actual code structure
- Developer has flexibility in HOW to implement
- Acceptance criteria focus on outcomes, not implementation

#### Risk 3: Host Service Downtime During Deployment
**Impact**: Medium
**Probability**: Low
**Mitigation**:
- M2 adds new endpoints without removing old ones
- Gradual cutover in M3
- Deprecated endpoints kept functional temporarily

#### Risk 4: Cache Bugs
**Impact**: High (stale data)
**Probability**: Low
**Mitigation**:
- Extensive unit tests for cache logic (M1)
- TTL configurable
- Force refresh available for debugging

#### Risk 5: Two-Level Cache Complexity
**Impact**: Medium (debugging difficulty)
**Probability**: Medium
**Mitigation**:
- Clear logging at both levels
- Monitoring metrics for cache behavior
- Documentation with troubleshooting guide

---

## Success Criteria

### Functional Success
- [ ] No "no running event loop" errors in logs
- [ ] Metrics stored correctly during training (M2 bug fixed)
- [ ] Local and host training have same client experience
- [ ] Data loading has progress reporting
- [ ] All operations queryable via standard /operations/* API

### Architectural Success
- [ ] NO internal polling loops anywhere
- [ ] NO async callbacks from worker threads
- [ ] NO custom status endpoints (all use /operations/*)
- [ ] Same OperationsService code in backend and host services
- [ ] ProgressBridgeBase pattern reusable for all operation types

### Performance Success
- [ ] Worker overhead <1μs per callback
- [ ] Cache hit queries <1ms
- [ ] Cache miss local <10ms
- [ ] Cache miss remote <50ms
- [ ] Cache hit rate >90%

### Operational Success
- [ ] All tests passing (100% pass rate)
- [ ] No regression in existing functionality
- [ ] Monitoring and alerting in place
- [ ] Documentation complete
- [ ] Team trained on new architecture
- [ ] Production deployment successful with no rollbacks

---

**Document Version**: 8.0 (Cache + ID Mapping + Lifecycle)
**Last Updated**: 2025-01-23
**Next Review**: After M1 completion

**Version 8.0 Changes (Consistency + Completeness)**:

**M1 Revisions**:
- **NEW Task 1.4**: Added simple TTL cache implementation (was deferred, now included in M1)
- Task renumbering: E2E test guide moved from 1.4 to 1.5
- M1 Key Decisions: Updated to reflect cache inclusion
- M1 Exit Criteria: Added cache deliverables and quality gates
- Rationale: Cache is essential for performance with multiple clients, simple to implement (~50 LOC)

**Architecture Alignment**:
- Design Doc §4.1: Removed thread safety implementation details (moved to Architecture)
- Architecture Doc §4.1: Updated ProgressBridge from abstract to concrete class
- Architecture Doc §4.1: Updated thread safety model to use RLock (explicit locking)
- Architecture Doc §4.2: Added metrics cursor strategy section
- Architecture Doc §5.4: Added two-level caching explanation (bridge=L1, TTL=L2)

**M2 Revisions**:
- Task 2.5: Added cursor management implementation details
- Clarified: Backend tracks cursor, passes to host/bridge for delta queries

**M3 Revisions**:
- **Task 3.1 Part B**: Complete rewrite with operation ID mapping details
- Added: Backend stores BOTH operation IDs (backend + host)
- Added: `register_remote_proxy()` signature with three parameters
- Added: Backend query flow using host's operation ID
- Added: OperationsService ID mapping support
- **Part C**: Added explicit lifecycle acceptance criteria
- **Part D**: Marked HealthService as deferred to post-M5
- **Part F**: Added integration tests for ID mapping

**M5 Revisions**:
- Added "Known Limitations" section to exit criteria
- Documented: No timeout detection, no stuck detection (deferred to Doctor service)
- Acceptance: Team acknowledges operations may stay RUNNING indefinitely

**Version 7.0 Changes (M1 + M3 Revisions)**:

**M1 Revisions**:
- Task 1.1: Changed from abstract ProgressBridgeBase to concrete ProgressBridge class (scenario-independent)
- Task 1.2: Removed push mechanism immediately (no dual push/pull), pull-only from start
- Task 1.3: Combined old tasks 1.3 (cache) + 1.4 (registration) into single task focused on registry + wiring
- Task 1.4: Renumbered from 1.5, improved E2E test guide format (scenarios/outcomes, not code)
- Cache: Deferred to future milestone (post-M5) to focus on MVP
- Duration: Reduced from 6-8 days to 5-6 days
- Strategy: Pull-only architecture from day one, cleaner implementation, faster to MVP

**M3 Revisions**:
- **DELETED Task 3.2**: Removed completion monitor (violated "no polling" principle)
- **Task 3.1 Rewritten**: Focus on convergence - host uses SAME orchestrator as local
- **Completion Discovery**: Client-driven (no background polling), backend discovers when pulling from host
- **HealthService**: Clarified role as external monitoring (not completion detection)
- **Convergence**: Emphasized that local and host training use same code, different location only
- Renumbered tasks: 3.3→3.2, 3.4→3.3, 3.5→3.4
- Updated exit criteria to reflect convergence and no-polling requirements

**Note on HealthService**: Implementation deferred to post-M5 milestone. For M1-M5, stuck/timeout detection can be manual or deferred.

---

## Important Notes

### E2E Testing Responsibility
**⚠️ HUMAN EXECUTES ALL E2E TESTS**

This plan includes E2E test guide tasks where the AI creates documentation for the human to execute tests manually. The AI does NOT write or execute E2E tests. Each E2E test guide task is clearly marked with:

```
⚠️ HUMAN RESPONSIBILITY: This task is executed by human, not AI
```

The AI's responsibility is to:
1. Create test guide documentation (`docs/testing/e2e-*.md`)
2. Document test scenarios with clear commands
3. Document verification steps
4. Document expected outcomes
5. Document troubleshooting

The human's responsibility is to:
1. Read the test guide
2. Execute the test scenarios
3. Verify outcomes match expectations
4. Report any failures back to AI for fixes
5. Confirm milestone exit criteria met
