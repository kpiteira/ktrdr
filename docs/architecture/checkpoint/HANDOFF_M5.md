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

## Tests Added

- 7 tests in `tests/unit/checkpoint/test_schemas.py::TestBacktestCheckpointState`
- 15 tests in `tests/unit/backtesting/test_checkpoint_builder.py`

All 22 tests passing.
