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

## Task 4.2 Complete: Migrate backtest_commands.py

### Migration Applied

Identical pattern to model_commands.py:
```python
from ktrdr.cli.client import AsyncCLIClient, CLIClientError

async with AsyncCLIClient() as cli:
    result = await cli.execute_operation(
        adapter,
        on_progress=on_progress,
        poll_interval=0.3,
    )
```

### Changes Made

1. **Replaced imports** - `AsyncOperationExecutor` → `AsyncCLIClient, CLIClientError`
2. **Added Rich Progress imports** - `Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn`
3. **Refactored `_run_backtest_async_impl`** - Now uses `async with AsyncCLIClient()` context manager
4. **Added health check** - Uses `cli.health_check()` before operation
5. **Added progress callback** - Uses `nonlocal task_id` pattern for Rich Progress updates
6. **Added result handling** - Handles completed/failed/cancelled statuses
7. **Extracted results display** - New `_display_backtest_results()` function for cleaner code

### Gotcha: Result Summary Field

Backtest results are in `result.get("result_summary", {}).get("metrics", {})` - not `result.get("results")`.

---

## M4 Milestone Complete

All operation commands now use `AsyncCLIClient.execute_operation()`:
- ✅ model_commands.py (Task 4.1)
- ✅ backtest_commands.py (Task 4.2)

**No remaining imports from `operation_executor.py` in:**
- ktrdr/cli/model_commands.py
- ktrdr/cli/backtest_commands.py
