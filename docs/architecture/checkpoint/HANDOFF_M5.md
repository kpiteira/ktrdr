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

## Tests Added

- 7 tests in `tests/unit/checkpoint/test_schemas.py::TestBacktestCheckpointState`
- 15 tests in `tests/unit/backtesting/test_checkpoint_builder.py`
- 14 tests in `tests/unit/backtesting/test_backtest_worker_checkpoint.py`
- 17 tests in `tests/unit/backtesting/test_checkpoint_restore.py`

All 53 tests passing.
