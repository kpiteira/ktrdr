---
design: docs/architecture/checkpoint/DESIGN.md
architecture: docs/architecture/checkpoint/ARCHITECTURE.md
---

# Milestone 5: Backtesting Checkpoint + Resume

**Branch:** `feature/checkpoint-m5-backtesting-checkpoint`
**Depends On:** M4 (Training Resume)
**Estimated Tasks:** 8

---

## Important: RESUMING Status Pattern (from M4)

M4 introduced a `RESUMING` transitional status to fix a race condition during resume.
This pattern MUST be followed for backtest resume:

1. **Backend** sets status to `RESUMING` (not `RUNNING`) when resume is requested
2. **Backend** dispatches to backtest worker's `/backtests/resume` endpoint
3. **Worker** updates status to `RUNNING` when it actually starts
4. **Worker** updates status to `COMPLETED` when done
5. `get_operation()` syncs status from worker for `RESUMING` operations

The resume is initiated via the existing `POST /operations/{id}/resume` endpoint,
which checks `operation_type` from checkpoint state to dispatch to the correct worker.

---

## Capability

When M5 is complete:
- Backtesting saves periodic checkpoints (every N bars)
- Backtesting saves checkpoint on cancellation
- User can resume cancelled/failed backtests
- Portfolio state (cash, positions, trades) restored
- Indicators recomputed on resume
- Final results match uninterrupted run

---

## E2E Test Scenario

```bash
#!/bin/bash
# M5 E2E Test: Backtesting Checkpoint + Resume

set -e

echo "=== M5 E2E Test: Backtesting Checkpoint + Resume ==="

# 1. Start long backtest
echo "Step 1: Start backtest..."
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/backtests/start \
    -H "Content-Type: application/json" \
    -d '{
        "strategy_name": "test_strategy",
        "symbol": "EURUSD",
        "timeframe": "1h",
        "start_date": "2020-01-01",
        "end_date": "2024-01-01",
        "checkpoint_interval": 5000
    }')
OP_ID=$(echo $RESPONSE | jq -r '.data.operation_id')
echo "Started operation: $OP_ID"

# 2. Wait for progress (5000+ bars)
echo "Step 2: Waiting for progress..."
for i in {1..60}; do
    sleep 2
    PROGRESS=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.progress_message')
    echo "  Progress: $PROGRESS"
    BAR=$(echo $PROGRESS | grep -oP 'bar \K[0-9]+' || echo "0")
    if [ "$BAR" -gt 5000 ]; then
        break
    fi
done

# 3. Cancel backtest
echo "Step 3: Cancel backtest..."
curl -s -X DELETE http://localhost:8000/api/v1/operations/$OP_ID/cancel
sleep 3

# 4. Check checkpoint
CHECKPOINT=$(curl -s http://localhost:8000/api/v1/checkpoints/$OP_ID)
CP_BAR=$(echo $CHECKPOINT | jq -r '.data.state.bar_index')
CP_CASH=$(echo $CHECKPOINT | jq -r '.data.state.cash')
echo "Checkpoint at bar $CP_BAR, cash: $CP_CASH"

# 5. Resume backtest
echo "Step 5: Resume backtest..."
RESUME_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/operations/$OP_ID/resume)
RESUMED_BAR=$(echo $RESUME_RESPONSE | jq -r '.data.resumed_from.bar_index')
echo "Resumed from bar $RESUMED_BAR"

# 6. Wait for completion
echo "Step 6: Waiting for completion..."
for i in {1..180}; do
    sleep 2
    STATUS=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.status')
    if [ "$STATUS" == "COMPLETED" ]; then
        break
    fi
    if [ "$STATUS" == "FAILED" ]; then
        echo "FAIL: Backtest failed after resume"
        exit 1
    fi
done

# 7. Verify results
echo "Step 7: Verify results..."
RESULT=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq '.data.result')
TOTAL_TRADES=$(echo $RESULT | jq -r '.total_trades')
FINAL_EQUITY=$(echo $RESULT | jq -r '.final_equity')

echo "Total trades: $TOTAL_TRADES"
echo "Final equity: $FINAL_EQUITY"

if [ "$STATUS" == "COMPLETED" ] && [ "$TOTAL_TRADES" != "null" ]; then
    echo ""
    echo "=== M5 E2E TEST PASSED ==="
else
    echo ""
    echo "=== M5 E2E TEST FAILED ==="
    exit 1
fi
```

---

## Tasks

### Task 5.1: Define Backtesting Checkpoint State Shape

**File(s):**
- `ktrdr/checkpointing/schemas.py` (modify)
- `ktrdr/backtesting/checkpoint_builder.py` (new)

**Type:** CODING

**Description:**
Define the data structure for backtesting checkpoint state.

**State Shape:**
```python
@dataclass
class BacktestCheckpointState:
    # REQUIRED: Operation type for resume dispatch
    operation_type: str = "backtesting"  # Backend uses this to select worker

    # Resume point
    bar_index: int
    current_date: str  # ISO format

    # Portfolio state
    cash: float
    positions: list[dict]  # [{symbol, quantity, entry_price, entry_date}]

    # Trade history
    trades: list[dict]  # [{symbol, side, quantity, price, date, pnl}]

    # Performance tracking (sampled)
    equity_samples: list[dict]  # [{bar_index, equity}] every N bars

    # Original request for resume
    original_request: dict
```

**Notes:**

- `operation_type` is REQUIRED - the backend resume endpoint uses this to dispatch to the correct worker
- No filesystem artifacts for backtesting (all state fits in DB)
- Equity curve is sampled, not full (to limit size)
- Original request needed to reload data on resume

**Acceptance Criteria:**

- [ ] State dataclass defined with `operation_type: "backtesting"`
- [ ] Builder can extract state from BacktestEngine
- [ ] No artifacts (artifacts=None)
- [ ] Equity sampled at reasonable intervals

---

### Task 5.2: Integrate Checkpoint Save into Backtest Worker

**File(s):**
- `ktrdr/backtesting/backtest_worker.py` (modify)
- `ktrdr/backtesting/engine.py` (modify if needed)

**Type:** CODING

**Task Categories:** Persistence, Cross-Component, Wiring/DI

**Description:**
Integrate checkpoint saving into backtest worker.

**Implementation Notes:**
- CheckpointPolicy with bar_interval (e.g., 10000 bars)
- Save checkpoint on cancellation
- No artifacts (state only)

**Integration:**
```python
class BacktestWorker(WorkerAPIBase):
    async def _run_backtest(self, operation_id: str, request: BacktestRequest):
        engine = BacktestEngine(...)
        checkpoint_policy = CheckpointPolicy(unit_interval=10000)

        for bar_index in range(total_bars):
            await engine.process_bar(bar_index)

            # Periodic checkpoint
            if checkpoint_policy.should_checkpoint(bar_index):
                state = build_backtest_checkpoint_state(engine, request)
                await self.checkpoint_service.save_checkpoint(
                    operation_id, "periodic", state.to_dict(), artifacts=None
                )
                checkpoint_policy.record_checkpoint(bar_index)

            # Check cancellation
            if self._cancellation_token.is_cancelled():
                state = build_backtest_checkpoint_state(engine, request)
                await self.checkpoint_service.save_checkpoint(
                    operation_id, "cancellation", state.to_dict(), artifacts=None
                )
                raise CancellationError("Backtest cancelled")

        # Success - delete checkpoint
        await self.checkpoint_service.delete_checkpoint(operation_id)
```

**Acceptance Criteria:**
- [ ] Periodic checkpoint every N bars
- [ ] Cancellation checkpoint saves
- [ ] No filesystem artifacts
- [ ] Portfolio state captured correctly

**Integration Tests (based on categories):**
- [ ] **Wiring:** `assert backtest_worker.checkpoint_service is not None`
- [ ] **DB Verification:** After checkpoint interval, query DB to verify checkpoint exists
- [ ] **Cross-Component:** Checkpoint state matches engine state (bar_index, cash, positions)

**Smoke Test:**
```bash
# Start backtest, wait for checkpoint interval, then:
docker compose exec db psql -U ktrdr -d ktrdr -c \
  "SELECT operation_id, state->>'bar_index' as bar FROM operation_checkpoints"
```

---

### Task 5.3: Implement Backtest Restore

**File(s):**
- `ktrdr/backtesting/backtest_worker.py` (modify)
- `ktrdr/backtesting/checkpoint_restore.py` (new)

**Type:** CODING

**Task Categories:** Cross-Component, Persistence

**Description:**
Implement restore logic for backtesting.

**Implementation Notes:**
- Load checkpoint state
- Reload data for full range (need lookback for indicators)
- Restore portfolio state
- Restore trade history
- Continue from checkpoint bar

**Code:**
```python
async def restore_backtest_from_checkpoint(self, operation_id: str) -> BacktestResumeContext:
    checkpoint = await self.checkpoint_service.load_checkpoint(operation_id)

    if checkpoint is None:
        raise ValueError(f"No checkpoint for {operation_id}")

    state = checkpoint.state
    original_request = state["original_request"]

    return BacktestResumeContext(
        start_bar=state["bar_index"],  # Resume from this bar
        cash=state["cash"],
        positions=state["positions"],
        trades=state["trades"],
        equity_samples=state["equity_samples"],
        original_request=original_request,
    )
```

**Acceptance Criteria:**
- [ ] Checkpoint loaded
- [ ] Portfolio state restored
- [ ] Trade history restored
- [ ] Original request extracted for data reload

---

### Task 5.4: Implement Indicator Recomputation on Resume

**File(s):**
- `ktrdr/backtesting/engine.py` (modify)

**Type:** CODING

**Description:**
On backtest resume, reload data and recompute indicators before continuing.

**Implementation Notes:**
- Load full data range (start_date to end_date from original request)
- Compute all indicators
- Seek to checkpoint bar
- Continue processing from there

**Code:**
```python
async def resume_from_context(self, context: BacktestResumeContext):
    """Resume backtesting from checkpoint."""
    # 1. Load data for full range
    data = await self.data_service.load_data(
        symbol=context.original_request["symbol"],
        timeframe=context.original_request["timeframe"],
        start_date=context.original_request["start_date"],
        end_date=context.original_request["end_date"],
    )

    # 2. Compute indicators for full range
    self._compute_indicators(data)

    # 3. Restore portfolio state
    self.portfolio.cash = context.cash
    self.portfolio.positions = context.positions
    self.portfolio.trades = context.trades

    # 4. Set starting bar
    self._current_bar = context.start_bar

    # Note: Bars 0 to start_bar-1 are NOT re-processed
    # Indicators are available for lookback, but no trades executed
```

**Acceptance Criteria:**
- [ ] Full data loaded on resume
- [ ] Indicators computed for full range
- [ ] Portfolio restored from checkpoint
- [ ] Processing continues from checkpoint bar
- [ ] Previous bars not re-processed

---

### Task 5.5: Add Resume Endpoint to Backtest Worker API

**File(s):**

- `ktrdr/backtesting/remote_api.py` (modify)

**Type:** CODING

**Description:**
Add worker endpoint that the backend's resume endpoint dispatches to.

**Endpoint:**
```python
@app.post("/backtests/resume")
async def resume_backtest(request: BacktestResumeRequest):
    """Resume backtest from checkpoint.

    Called by backend's POST /operations/{id}/resume endpoint.
    Worker must update status to RUNNING when starting.
    """
    operation_id = request.operation_id

    context = await worker.restore_backtest_from_checkpoint(operation_id)

    asyncio.create_task(
        worker.run_resumed_backtest(operation_id, context)
    )

    return {"success": True, "operation_id": operation_id, "status": "started"}
```

**Worker Status Update:**
```python
async def run_resumed_backtest(self, operation_id: str, context: BacktestResumeContext):
    # Update status to RUNNING (worker is responsible for this transition)
    await self._operations_service.start_operation(operation_id, asyncio.current_task())

    # ... run backtest ...

    # On completion, update to COMPLETED
    await self._operations_service.complete_operation(operation_id, result)
```

**Acceptance Criteria:**

- [ ] Endpoint accepts operation_id
- [ ] Loads checkpoint
- [ ] Worker calls `start_operation()` to set status to RUNNING
- [ ] Starts resumed backtest in background
- [ ] Returns success

---

### Task 5.6: Integrate Backtest Resume into Backend Endpoint

**File(s):**

- `ktrdr/api/endpoints/operations.py` (modify)

**Type:** CODING

**Description:**
Extend the existing `POST /operations/{id}/resume` endpoint to handle backtest operations.

**Implementation:**
The resume endpoint already:

1. Calls `try_resume()` to set status to RESUMING
2. Loads checkpoint
3. Checks `operation_type` from checkpoint state
4. Dispatches to the appropriate worker

Add backtest dispatch logic:

```python
# In resume_operation endpoint (after training dispatch)
elif op_type == "backtesting":
    from ktrdr.api.models.workers import WorkerType

    worker = worker_registry.select_worker(WorkerType.BACKTESTING)
    if worker is None:
        logger.error(f"No backtest worker available for resume: {operation_id}")
        await operations_service.update_status(operation_id, status="CANCELLED")
        raise HTTPException(
            status_code=503,
            detail="No backtest worker available to resume operation",
        )

    # Dispatch to worker's /backtests/resume endpoint
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{worker.endpoint_url}/backtests/resume",
            json={"operation_id": operation_id},
            timeout=30.0,
        )
        response.raise_for_status()
```

**Acceptance Criteria:**

- [ ] Resume endpoint handles `operation_type == "backtesting"`
- [ ] Selects backtesting worker from registry
- [ ] Dispatches to worker's `/backtests/resume` endpoint
- [ ] Reverts status to CANCELLED on dispatch failure
- [ ] Returns success with `status: "resuming"`

---

### Task 5.7: Integration Test for Backtest Resume

**File(s):**
- `tests/integration/test_m5_backtesting_checkpoint.py` (new)

**Type:** CODING

**Description:**
Integration test for backtest checkpoint and resume.

**Test Scenarios:**
1. Start backtest, wait for periodic checkpoint
2. Cancel backtest
3. Resume backtest
4. Verify continues from correct bar
5. Verify final results are valid
6. Optional: Compare results to uninterrupted run

**Acceptance Criteria:**
- [ ] Test covers save and resume
- [ ] Test verifies correct resume bar
- [ ] Test verifies portfolio restoration
- [ ] Tests pass: `make test-integration`

---

### Task 5.8: Fix Event Loop Conflict in Backtest Checkpoint Callback

**File(s):**
- `ktrdr/backtesting/backtest_worker.py` (modify)

**Type:** CODING

**Task Categories:** Cross-Component, Async Infrastructure

**Description:**
Fix the event loop conflict that causes intermittent checkpoint save failures during backtesting.

**Problem:**
The checkpoint callback runs in a thread pool (via `asyncio.to_thread`) and creates a new event loop
to save checkpoints. However, the database connection's Future was created in the main event loop,
causing the error:
```
Failed to save periodic checkpoint: Task got Future attached to a different loop
```

**Current Behavior:**
- First checkpoint attempt often fails with event loop error
- Time-based retry (every 5 minutes) eventually succeeds
- Checkpoints are saved, but reliability is questionable

**Solution Options:**

1. **Use `asyncio.run_coroutine_threadsafe()`** - Pass main event loop reference to callback,
   schedule checkpoint save on main loop instead of creating new loop

2. **Thread-safe queue pattern** - Callback pushes state to queue, main async context polls
   and saves checkpoints

3. **Sync database wrapper** - Create synchronous checkpoint save using a separate
   connection pool configured for thread access

**Recommended Approach:** Option 1 (run_coroutine_threadsafe) as it's least invasive.

**Implementation:**
```python
# In _execute_backtest_work, before creating callback:
main_loop = asyncio.get_running_loop()

def checkpoint_callback(**kwargs):
    # ... build state ...

    if checkpoint_policy.should_checkpoint(bar_index):
        try:
            # Schedule on main event loop instead of creating new one
            future = asyncio.run_coroutine_threadsafe(
                checkpoint_service.save_checkpoint(
                    operation_id=operation_id,
                    checkpoint_type="periodic",
                    state=state.to_dict(),
                    artifacts=None,
                ),
                main_loop,
            )
            # Wait for completion with timeout
            future.result(timeout=30.0)
            checkpoint_policy.record_checkpoint(bar_index)
            logger.info(f"Periodic checkpoint saved for {operation_id} at bar {bar_index}")
        except Exception as e:
            logger.warning(f"Failed to save periodic checkpoint: {e}")
```

**Acceptance Criteria:**
- [ ] Checkpoint callback uses main event loop for async operations
- [ ] No "attached to a different loop" errors in logs
- [ ] Periodic checkpoints save reliably on first attempt
- [ ] Cancellation checkpoints still save correctly
- [ ] Unit tests pass: `make test-unit`

---

### Task 5.9: Fix Resume to Different Worker Bug

**File(s):**
- `ktrdr/api/services/operations_service.py` (modify)
- `ktrdr/backtesting/backtest_worker.py` (modify)
- `ktrdr/training/training_worker.py` (modify - same fix needed)

**Type:** CODING

**Task Categories:** Cross-Component, Infrastructure

**Description:**
Fix the bug where resume fails if dispatched to a different worker than the original operation.

**Root Cause:**
`_execute_resumed_backtest_work` incorrectly calls `create_operation`, but the operation already exists in the **database**:

1. Original backtest creates operation in DB
2. Cancellation happens, operation stays in DB with status=CANCELLED
3. Resume is dispatched (to any worker)
4. `_execute_resumed_backtest_work` calls `create_operation`
5. `create_operation` checks DB → finds existing operation → fails

The `create_operation` method checks both local cache AND database:
```python
# In create_operation (line 151-158):
if self._repository:
    existing = await self._repository.get(operation_id)
    if existing:
        raise DataError("Operation ID already exists...")
```

**This fails regardless of which worker receives the resume** because the operation exists in the shared database.

**Training's different issue:** Training calls `start_operation` (correct - doesn't create). But `start_operation` requires the operation to be in local cache, which fails if dispatched to a different worker

**Evidence:**
```
DataError: Operation ID already exists: op_backtesting_20251228_153705_c9e7639a
```

**Training Has Same Latent Bug:**
Training's `_execute_resumed_training` calls `start_operation` without ensuring the operation is in the local cache:
```python
# Training worker (line 576-577)
await self._operations_service.start_operation(operation_id, dummy_task)
```
This would fail if resume goes to a different worker.

**Solution Options:**

1. **Add `ensure_in_cache()` method to OperationsService**
   - Before `start_operation`, check if operation is in cache
   - If not, load from database into cache
   - Pros: Minimal changes, clear semantics
   - Cons: Adds another method

2. **Make `start_operation` auto-load from DB if not in cache**
   - Modify `start_operation` to load from repository if not in cache
   - Pros: Simplest fix, transparent
   - Cons: Changes existing semantics

3. **Use `get_or_create_operation` pattern for resume**
   - Create operation if it doesn't exist locally, skip if it does
   - Pros: Explicit handling
   - Cons: More complex

**Recommended Approach:** Option 2 - Auto-load from DB

The resume pattern should be:
```python
# Modified start_operation (auto-loads from DB if not in cache)
async def start_operation(self, operation_id: str, task: asyncio.Task) -> None:
    async with self._lock:
        if operation_id not in self._cache:
            # Try to load from repository (for resume-to-different-worker case)
            if self._repository:
                op_data = await self._repository.get(operation_id)
                if op_data:
                    # Create Operation from DB data and add to cache
                    self._cache[operation_id] = Operation.from_db_model(op_data)
                    logger.info(f"Loaded operation {operation_id} from DB for resume")

            # If still not in cache after DB check, it truly doesn't exist
            if operation_id not in self._cache:
                raise DataError(...)

        # Proceed with existing logic...
```

**Why This Wasn't Caught:**
- Integration tests use mock services where workers share in-memory state
- E2E tests need multiple workers with load balancing to trigger this
- The refactoring in Task 5.7 notes should have caught this pattern mismatch

**Acceptance Criteria:**
- [ ] `start_operation` auto-loads from DB if not in cache
- [ ] Backtest resume works when dispatched to different worker
- [ ] Training resume works when dispatched to different worker
- [ ] Remove `create_operation` call from `_execute_resumed_backtest_work`
- [ ] Unit tests verify the auto-load behavior
- [ ] Integration test with explicit cross-worker resume

---

## Milestone 5 Verification Checklist

Before marking M5 complete:

- [ ] All 9 tasks complete
- [ ] Unit tests pass: `make test-unit`
- [ ] Integration tests pass: `make test-integration`
- [ ] E2E test script passes
- [ ] M1-M4 E2E tests still pass
- [ ] Quality gates pass: `make quality`

---

## Files Changed Summary

| File | Action | Task |
|------|--------|------|
| `ktrdr/checkpointing/schemas.py` | Modify | 5.1 |
| `ktrdr/backtesting/checkpoint_builder.py` | Create | 5.1 |
| `ktrdr/backtesting/backtest_worker.py` | Modify | 5.2, 5.3, 5.8, 5.9 |
| `ktrdr/backtesting/checkpoint_restore.py` | Create | 5.3 |
| `ktrdr/backtesting/engine.py` | Modify | 5.4 |
| `ktrdr/backtesting/remote_api.py` | Modify | 5.5 |
| `ktrdr/api/endpoints/operations.py` | Modify | 5.6 |
| `tests/integration/test_m5_backtesting_checkpoint.py` | Create | 5.7 |
| `ktrdr/api/services/operations_service.py` | Modify | 5.9 |
| `ktrdr/training/training_worker.py` | Modify | 5.9 |
