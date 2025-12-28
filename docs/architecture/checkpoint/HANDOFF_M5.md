# Handoff: Milestone 5 (Backtesting Checkpoint)

## Task 5.1 Complete

**Implemented:** BacktestCheckpointState dataclass and checkpoint builder

### Files Created/Modified

| File | Action | Purpose |
|------|--------|---------|
| [ktrdr/checkpoint/schemas.py](ktrdr/checkpoint/schemas.py) | Modified | Added `BacktestCheckpointState` dataclass |
| [ktrdr/backtesting/checkpoint_builder.py](ktrdr/backtesting/checkpoint_builder.py) | Created | Builder function to extract state from engine |

### BacktestCheckpointState Fields

```python
@dataclass
class BacktestCheckpointState:
    bar_index: int                          # Resume point
    current_date: str                       # ISO format
    cash: float                             # Portfolio cash
    operation_type: str = "backtesting"     # For backend dispatch
    positions: list[dict] = []              # Open positions
    trades: list[dict] = []                 # Trade history
    equity_samples: list[dict] = []         # Sampled equity curve
    original_request: dict = {}             # For data reload
```

### Key Gotchas

**1. PerformanceTracker.equity_curve is a list, not DataFrame**

The internal `equity_curve` attribute is `list[dict[str, Any]]`, not `pd.DataFrame`. The `get_equity_curve()` method converts it to DataFrame, but for checkpointing we use the raw list directly.

```python
# Correct
engine.performance_tracker.equity_curve  # list[dict]

# This returns DataFrame but we don't use it for checkpointing
engine.performance_tracker.get_equity_curve()  # pd.DataFrame
```

**2. No filesystem artifacts for backtesting**

Unlike training checkpoints which save model.pt/optimizer.pt to disk, backtesting checkpoints have NO artifacts. All state fits in the database JSONB column.

```python
# Training: has artifacts
await checkpoint_service.save_checkpoint(op_id, "periodic", state, artifacts=artifacts_dict)

# Backtesting: no artifacts
await checkpoint_service.save_checkpoint(op_id, "periodic", state.to_dict(), artifacts=None)
```

**3. Builder requires explicit bar_index and timestamp**

The builder function doesn't extract these from the engine - they must be passed explicitly by the caller (the backtest worker loop):

```python
state = build_backtest_checkpoint_state(
    engine=engine,
    bar_index=current_bar_index,      # Caller provides
    current_timestamp=current_time,    # Caller provides
    original_request=request_dict,     # Optional, extracted from config if not provided
)
```

### Equity Curve Sampling

Equity is sampled every 100 bars (configurable via `equity_sample_interval` parameter). This prevents checkpoint bloat for long backtests (35,000+ bars).

```python
DEFAULT_EQUITY_SAMPLE_INTERVAL = 100  # Every 100 bars
```

### Usage Pattern for Task 5.2

```python
from ktrdr.backtesting.checkpoint_builder import build_backtest_checkpoint_state
from ktrdr.checkpoint.checkpoint_policy import CheckpointPolicy

# In backtest worker
checkpoint_policy = CheckpointPolicy(unit_interval=10000)

for bar_index in range(total_bars):
    # ... process bar ...

    if checkpoint_policy.should_checkpoint(bar_index):
        state = build_backtest_checkpoint_state(
            engine=engine,
            bar_index=bar_index,
            current_timestamp=current_bar.name,
            original_request=original_request,
        )
        await checkpoint_service.save_checkpoint(
            operation_id,
            "periodic",
            state.to_dict(),
            artifacts=None,  # No artifacts!
        )
        checkpoint_policy.record_checkpoint(bar_index)
```

---

## Task 5.2 Complete

**Implemented:** Checkpoint save integration in BacktestWorker

### Files Modified

| File | Action | Purpose |
|------|--------|---------|
| [ktrdr/backtesting/engine.py](ktrdr/backtesting/engine.py) | Modified | Added `checkpoint_callback` parameter to `run()` |
| [ktrdr/backtesting/backtest_worker.py](ktrdr/backtesting/backtest_worker.py) | Modified | Added checkpoint infrastructure and callback |

### Key Changes

**1. BacktestingEngine.run() now accepts checkpoint_callback**

```python
def run(
    self,
    bridge: Optional[ProgressBridge] = None,
    cancellation_token: Optional[CancellationToken] = None,
    checkpoint_callback: Optional[Callable[..., None]] = None,  # NEW
) -> BacktestResults:
```

The callback is called every 100 bars with `(bar_index, timestamp, engine)`.

**2. BacktestWorker now has checkpoint support**

```python
class BacktestWorker(WorkerAPIBase):
    DEFAULT_CHECKPOINT_BAR_INTERVAL = 10000  # Default: checkpoint every 10k bars

    def __init__(self, ..., checkpoint_bar_interval=DEFAULT_CHECKPOINT_BAR_INTERVAL):
        self.checkpoint_bar_interval = checkpoint_bar_interval
        self._checkpoint_service = None  # Lazy initialization
```

**3. Checkpoint callback pattern**

The callback runs in a thread pool (via `asyncio.to_thread`), so it creates a new event loop for async checkpoint saves:

```python
def checkpoint_callback(**kwargs):
    bar_index = kwargs["bar_index"]
    # ...
    if checkpoint_policy.should_checkpoint(bar_index):
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                checkpoint_service.save_checkpoint(
                    operation_id=operation_id,
                    checkpoint_type="periodic",
                    state=state.to_dict(),
                    artifacts=None,  # No artifacts for backtesting
                )
            )
        finally:
            loop.close()
```

**4. Cancellation checkpoints**

Both `CancellationError` and `asyncio.CancelledError` handlers save a cancellation checkpoint using the latest tracked state.

**5. Checkpoint deleted on success**

After successful completion, checkpoint is deleted to avoid orphans.

### Acceptance Criteria Verified

- [x] Periodic checkpoint every N bars
- [x] Cancellation checkpoint saves
- [x] No filesystem artifacts (artifacts=None)
- [x] Portfolio state captured correctly

---

## Task 5.3 Complete

**Implemented:** Backtest checkpoint restore functionality

### Files Created/Modified

| File | Action | Purpose |
|------|--------|---------|
| [ktrdr/backtesting/checkpoint_restore.py](ktrdr/backtesting/checkpoint_restore.py) | Created | `BacktestResumeContext` dataclass and `restore_from_checkpoint` function |
| [ktrdr/backtesting/backtest_worker.py](ktrdr/backtesting/backtest_worker.py) | Modified | Added `restore_from_checkpoint` method |

### BacktestResumeContext Fields

```python
@dataclass
class BacktestResumeContext:
    start_bar: int                      # Bar to resume from (checkpoint bar + 1)
    cash: float                         # Portfolio cash at checkpoint
    original_request: dict[str, Any]    # For data reload
    positions: list[dict[str, Any]] = []     # Open positions (optional)
    trades: list[dict[str, Any]] = []        # Trade history (optional)
    equity_samples: list[dict[str, Any]] = []  # Sampled equity (optional)
```

### Key Design Decisions

**1. Resume from NEXT bar (Decision D7)**

Resume from `bar_index + 1`, not `bar_index`. The checkpoint bar is already processed.

```python
start_bar = state.get("bar_index", 0) + 1
```

**2. No artifact validation needed**

Unlike training restore which validates model.pt/optimizer.pt, backtesting has no artifacts:

```python
# Training: load_artifacts=True, validates model.pt exists
checkpoint = await checkpoint_service.load_checkpoint(op_id, load_artifacts=True)

# Backtesting: load_artifacts=False, no artifact validation
checkpoint = await checkpoint_service.load_checkpoint(op_id, load_artifacts=False)
```

### Usage Pattern for Tasks 5.4/5.5

```python
from ktrdr.backtesting.checkpoint_restore import (
    BacktestResumeContext,
    CheckpointNotFoundError,
    restore_from_checkpoint,
)

# In resume endpoint or worker
try:
    context = await worker.restore_from_checkpoint(operation_id)

    # Resume backtest from context
    # - Load data for full range (context.original_request)
    # - Compute indicators
    # - Restore portfolio: context.cash, context.positions, context.trades
    # - Start from: context.start_bar
except CheckpointNotFoundError:
    # Handle no checkpoint case
    pass
```

### Acceptance Criteria Verified

- [x] Checkpoint loaded
- [x] Portfolio state restored (cash, positions)
- [x] Trade history restored
- [x] Original request extracted for data reload

---

## Task 5.4 Complete

**Implemented:** Indicator recomputation on resume in BacktestingEngine

### Files Modified

| File | Action | Purpose |
|------|--------|---------|
| [ktrdr/backtesting/engine.py](ktrdr/backtesting/engine.py) | Modified | Added `resume_from_context()` and `resume_start_bar` param to `run()` |

### New Engine Methods

**1. resume_from_context(context: BacktestResumeContext) -> pd.DataFrame**

Prepares the engine to resume from a checkpoint:

```python
def resume_from_context(self, context: BacktestResumeContext) -> pd.DataFrame:
    # 1. Load data for full range
    data = self._load_historical_data()

    # 2. Compute indicators for full range (needed for lookback)
    self.orchestrator.prepare_feature_cache(data)

    # 3. Restore portfolio state
    self._restore_portfolio_state(context)

    # 4. Restore equity curve samples
    if context.equity_samples:
        self.performance_tracker.equity_curve = list(context.equity_samples)

    return data
```

**2. run() now accepts resume_start_bar parameter**

```python
def run(
    self,
    bridge: Optional[ProgressBridge] = None,
    cancellation_token: Optional[CancellationToken] = None,
    checkpoint_callback: Optional[Callable[..., None]] = None,
    resume_start_bar: Optional[int] = None,  # NEW
) -> BacktestResults:
```

When `resume_start_bar` is provided, the loop starts from `resume_start_bar + 50` (accounting for warmup bars).

### Helper Methods

- `_restore_portfolio_state(context)` - Restores cash, positions, trades, and next_trade_id
- `_dict_to_trade(trade_data)` - Converts trade dict back to Trade object

### Key Design Decisions

**1. Bar index conversion**

`resume_start_bar` is in processed bar space (0-indexed from start of processing).
Raw index = `resume_start_bar + 50` (50 = warmup bars skipped).

**2. Data loaded once via engine config**

`resume_from_context()` uses `_load_historical_data()` which reads from `self.config`.
The original_request in context contains the same date range info.

**3. Indicators computed for full range**

Even when resuming, indicators are computed for the full data range so lookback works correctly.

### Usage Pattern for Task 5.5

```python
# In worker's run_resumed_backtest
context = await self.restore_from_checkpoint(operation_id)

# Update engine config with original request dates
# (if not already matching)

# Resume engine
data = engine.resume_from_context(context)
results = engine.run(
    bridge=bridge,
    cancellation_token=cancellation_token,
    checkpoint_callback=checkpoint_callback,
    resume_start_bar=context.start_bar,  # Continue from checkpoint bar
)
```

### Acceptance Criteria Verified

- [x] Full data loaded on resume
- [x] Indicators computed for full range
- [x] Portfolio restored from checkpoint
- [x] Processing continues from checkpoint bar
- [x] Previous bars not re-processed

---

## Task 5.5 Complete

**Implemented:** Resume endpoint for backtest worker API

### Files Modified

| File | Action | Purpose |
|------|--------|---------|
| [ktrdr/backtesting/backtest_worker.py](ktrdr/backtesting/backtest_worker.py) | Modified | Added `/backtests/resume` endpoint and `_execute_resumed_backtest_work` method |

### New Endpoint

**POST /backtests/resume**

Called by backend's `POST /operations/{id}/resume` endpoint. Follows M4's RESUMING status pattern:

```python
@self.app.post("/backtests/resume")
async def resume_backtest(request: BacktestResumeRequest):
    # 1. Load checkpoint context
    context = await self.restore_from_checkpoint(operation_id)

    # 2. Start resumed backtest in background
    asyncio.create_task(self._execute_resumed_backtest_work(operation_id, context))

    # 3. Return immediately
    return {"success": True, "operation_id": operation_id, "status": "started"}
```

### Key Implementation Details

**1. BacktestResumeRequest model**

```python
class BacktestResumeRequest(WorkerOperationMixin):
    operation_id: str
```

**2. Worker status transition (RESUMING → RUNNING)**

The `_execute_resumed_backtest_work` method calls `start_operation()` to transition from RESUMING to RUNNING:

```python
await self._operations_service.start_operation(operation_id, dummy_task)
logger.info(f"Marked resumed operation {operation_id} as RUNNING")
```

**3. CheckpointService initialization fix**

Fixed `_get_checkpoint_service()` to properly initialize with `session_factory`:

```python
self._checkpoint_service = CheckpointService(
    session_factory=get_session_factory(),
    # Uses default artifacts_dir - backtesting doesn't use artifacts
)
```

### Usage Pattern for Task 5.6

The backend's resume endpoint should dispatch to this worker endpoint:

```python
elif op_type == "backtesting":
    worker = worker_registry.select_worker(WorkerType.BACKTESTING)
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{worker.endpoint_url}/backtests/resume",
            json={"operation_id": operation_id},
            timeout=30.0,
        )
```

### Acceptance Criteria Verified

- [x] Endpoint accepts operation_id
- [x] Loads checkpoint via restore_from_checkpoint
- [x] Worker calls start_operation() to set status to RUNNING
- [x] Starts resumed backtest in background
- [x] Returns success

---

## Task 5.6 Complete

**Implemented:** Backend resume endpoint integration for backtesting operations

### Files Modified

| File | Action | Purpose |
|------|--------|---------|
| [ktrdr/api/endpoints/operations.py](ktrdr/api/endpoints/operations.py) | Modified | Added backtesting dispatch in `resume_operation` endpoint |
| [tests/unit/api/endpoints/test_resume_operation.py](tests/unit/api/endpoints/test_resume_operation.py) | Modified | Added 4 tests for backtesting resume dispatch |

### Key Implementation Details

**1. Backtesting dispatch follows training pattern**

The existing resume endpoint checks `operation_type` from checkpoint state and dispatches to the appropriate worker. Added `elif op_type == "backtesting":` block:

```python
elif op_type == "backtesting":
    worker = worker_registry.select_worker(WorkerType.BACKTESTING)
    if worker is None:
        await operations_service.update_status(operation_id, status="CANCELLED")
        raise HTTPException(status_code=503, detail="No backtest worker available")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{worker.endpoint_url}/backtests/resume",
            json={"operation_id": operation_id},
            timeout=30.0,
        )
```

**2. Error handling reverts status to CANCELLED**

All error paths (no worker, HTTP error, connection error) revert status back to CANCELLED so the operation can be retried.

### Acceptance Criteria Verified

- [x] Resume endpoint handles `operation_type == "backtesting"`
- [x] Selects backtesting worker from registry
- [x] Dispatches to worker's `/backtests/resume` endpoint
- [x] Reverts status to CANCELLED on dispatch failure
- [x] Returns success with `status: "resuming"`

---

## Task 5.7 Complete

**Implemented:** Integration test for backtest checkpoint and resume

### Files Created

| File | Action | Purpose |
|------|--------|---------|
| [tests/integration/test_m5_backtesting_checkpoint.py](tests/integration/test_m5_backtesting_checkpoint.py) | Created | Integration test suite for backtest resume flow |

### Test Coverage (19 tests, all passing in 4.48s)

**Full Resume Flow (1 test)**
- Complete start → checkpoint → cancel → resume → complete flow
- Verifies checkpoint exists, portfolio restored, resumed from correct bar

**Resume From Correct Bar (3 tests)**
- `test_resume_starts_from_checkpoint_bar_plus_one` - Validates resume from `bar_index + 1`
- `test_resume_from_bar_zero_checkpoint` - Edge case: resume from bar 0
- `test_equity_samples_preserved_on_resume` - Equity curve preservation

**Portfolio Restoration (3 tests)**
- `test_cash_restored_on_resume` - Cash balance restoration
- `test_positions_restored_on_resume` - Open positions restoration
- `test_trades_restored_on_resume` - Trade history restoration

**Checkpoint Cleanup (3 tests)**
- Checkpoint deleted after successful completion
- Checkpoint preserved on resume failure (per design D6)
- Delete non-existent checkpoint returns false

**Edge Cases (5 tests)**
- Resume already running operation (fails)
- Resume completed operation (fails)
- Resume cancelled operation (succeeds → RESUMING)
- Resume failed operation (succeeds → RESUMING)
- Resume without checkpoint (detectable)

**Resume Context Integration (2 tests)**
- Full context creation from checkpoint
- Minimal context with empty optional fields

**Operation Type Verification (2 tests)**
- Checkpoint has `operation_type='backtesting'`
- Operation type used for worker dispatch

### Key Implementation Details

**1. In-memory mock services (following M4 pattern)**

```python
class IntegrationCheckpointService:
    """No artifacts for backtesting - all state in DB JSONB."""

    async def save_checkpoint(..., artifacts: Optional[dict[str, bytes]] = None):
        # Always artifacts=None for backtesting
        await self._mock_repo.save(..., artifacts_path=None, artifacts_size_bytes=None)
```

**2. Portfolio state helpers**

```python
def create_portfolio_state(bar_index: int, ...) -> tuple[float, list[dict], list[dict]]:
    """Generates realistic portfolio state with positions and trades."""

def create_equity_samples(bar_index: int, ...) -> list[dict]:
    """Generates sampled equity curve (every 100 bars)."""
```

**3. Status transition: RESUMING (not RUNNING)**

Unlike M4 training tests, backtest resume sets status to `RESUMING`:

```python
async def try_resume(self, operation_id: str) -> bool:
    if op and op["status"] in ("cancelled", "failed"):
        op["status"] = "resuming"  # Not "running" - worker will transition
        return True
```

This matches the M5 worker resume pattern where the worker calls `start_operation()` to transition RESUMING → RUNNING.

### Acceptance Criteria Verified

- [x] Test covers save and resume
- [x] Test verifies correct resume bar (checkpoint_bar + 1)
- [x] Test verifies portfolio restoration (cash, positions, trades)
- [x] Tests pass: `pytest tests/integration/test_m5_backtesting_checkpoint.py` (19 tests, 4.48s)

---

## Tests Added

- 7 tests in `tests/unit/checkpoint/test_schemas.py::TestBacktestCheckpointState`
- 15 tests in `tests/unit/backtesting/test_checkpoint_builder.py`
- 14 tests in `tests/unit/backtesting/test_backtest_worker_checkpoint.py`
- 17 tests in `tests/unit/backtesting/test_checkpoint_restore.py`
- 14 tests in `tests/unit/backtesting/test_engine_resume.py`
- 11 tests in `tests/unit/backtesting/test_backtest_worker_resume.py`
- 4 tests in `tests/unit/api/endpoints/test_resume_operation.py::TestBacktestResumeDispatch`
- **19 tests in `tests/integration/test_m5_backtesting_checkpoint.py`** (NEW)

**Total: 101 tests passing.**
