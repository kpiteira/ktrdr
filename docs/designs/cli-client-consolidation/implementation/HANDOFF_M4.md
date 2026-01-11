# Handoff: M4 — Migrate Operation Commands

## Task 4.1 Complete: Migrate model_commands.py (training)

### Migration Pattern Applied

Old pattern (inline polling with ~200 lines):
```python
# Manual signal handling
loop = asyncio.get_running_loop()
loop.add_signal_handler(signal.SIGINT, signal_handler)

# Start operation via POST
result = await cli.post("/trainings/start", json={...})
task_id = result["task_id"]

# Inline polling loop
while True:
    status_result = await cli.get(f"/operations/{task_id}/status")
    # Parse progress, update display, check terminal states...
    await asyncio.sleep(3)
```

New pattern (single execute_operation call):
```python
from ktrdr.cli.operation_adapters import TrainingOperationAdapter

# Create adapter with parameters
adapter = TrainingOperationAdapter(
    strategy_name=strategy_name,
    symbols=symbols,
    timeframes=timeframes,
    start_date=start_date,
    end_date=end_date,
    validation_split=validation_split,
    detailed_analytics=detailed_analytics,
)

# Execute with progress callback
result = await cli.execute_operation(
    adapter,
    on_progress=on_progress,
    poll_interval=0.3,
)
```

### Progress Display Integration

The on_progress callback updates Rich Progress:
```python
progress_bar = Progress(...)
task_id = None

def on_progress(percentage: int, message: str) -> None:
    nonlocal task_id
    if task_id is not None:
        progress_bar.update(task_id, completed=percentage, description=message)

with progress_bar:
    task_id = progress_bar.add_task("Training model...", total=100)
    result = await cli.execute_operation(adapter, on_progress=on_progress)
```

### Cancellation Handling

Ctrl+C is now handled automatically by execute_operation via asyncio.CancelledError:
- No manual signal handler registration needed
- execute_operation sends DELETE to cancel on backend
- Returns result with status="cancelled"

### Gotcha: Rich Progress Context

Progress callback references a `task_id` that's set after Progress context starts. Use `nonlocal` and None check:
```python
task_id = None  # Set after progress_bar context starts

def on_progress(percentage: int, message: str) -> None:
    nonlocal task_id
    if task_id is not None:  # Only update if context is active
        progress_bar.update(task_id, ...)
```

---

## Next Task Notes (4.2: backtest_commands.py)

**Pattern is identical** - look at model_commands.py as reference.

**Key imports:**
```python
from ktrdr.cli.operation_adapters import BacktestingOperationAdapter
```

**Check backtest_commands.py for:**
- Uses of `AsyncOperationExecutor` → replace with `execute_operation`
- Manual signal handler setup → remove
- Inline polling loops → replace with single execute_operation call

**BacktestingOperationAdapter already exists** in operation_adapters.py with proper endpoints and payload handling.
