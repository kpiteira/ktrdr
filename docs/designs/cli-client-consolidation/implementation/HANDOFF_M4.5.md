# Handoff: M4.5 — Remaining Migrations

## Task 4.5.1 Complete: Migrate async_model_commands.py

### Migration Applied

Changed `async_model_commands.py` from `AsyncOperationExecutor` to `AsyncCLIClient.execute_operation()` pattern.

Old pattern:
```python
from ktrdr.cli.operation_executor import AsyncOperationExecutor

executor = AsyncOperationExecutor()
success = await executor.execute_operation(
    adapter=adapter,
    console=console,
    progress_callback=format_training_progress,
    show_progress=True,
)
sys.exit(0 if success else 1)
```

New pattern:
```python
from ktrdr.cli.client import AsyncCLIClient, CLIClientError

async with AsyncCLIClient() as cli:
    if not await cli.health_check():
        # Handle connection error
        sys.exit(1)

    result = await cli.execute_operation(
        adapter,
        on_progress=on_progress,
        poll_interval=0.3,
    )

    status = result.get("status", "unknown")
    if status == "completed":
        sys.exit(0)
    elif status == "failed":
        sys.exit(1)
```

### Key Differences from Old Pattern

1. **Progress callback signature changed**:
   - Old: `progress_callback(operation_data: dict) -> str`
   - New: `on_progress(percentage: int, message: str) -> None`

2. **Return value changed**:
   - Old: Returns boolean (`True`/`False`)
   - New: Returns dict with `status` field (`completed`, `failed`, `cancelled`)

3. **Error handling**:
   - Old: No health check, failure indicated by return value
   - New: Explicit `health_check()` before operation, `CLIClientError` on start failure

4. **Progress display**:
   - Old: Executor manages Rich Progress internally
   - New: Command manages Rich Progress, passes callback to `execute_operation()`

### Gotcha: Rich Progress + async context manager

The `async with AsyncCLIClient()` must wrap the entire progress bar context:
```python
async with AsyncCLIClient() as cli:
    progress_bar = Progress(...)
    task_id = None

    def on_progress(percentage: int, message: str) -> None:
        nonlocal task_id
        if task_id is not None:
            progress_bar.update(task_id, completed=percentage, description=message)

    with progress_bar:
        task_id = progress_bar.add_task("Training...", total=100)
        result = await cli.execute_operation(adapter, on_progress=on_progress)
```

### Test Updates Required

Updated `test_training_command_refactored.py` to use new pattern. Tests must:
- Mock `AsyncCLIClient` instead of `AsyncOperationExecutor`
- Handle `SystemExit` since `_train_model_async_impl` calls `sys.exit()`
- Verify `on_progress` callback in kwargs (not `progress_callback`)

### Next Task Notes

For Task 4.5.2 (`data_commands.py`), the migration is simpler:
- Only uses `api_client.py` (not operations)
- Replace `check_api_connection()` with `cli.health_check()`
- Replace `get_api_client()` calls with `cli.get/post()` methods
- Param is `json=` not `json_data=`

---

## Task 4.5.2 Complete: Migrate data_commands.py (data load)

### Migration Applied

Migrated `_load_data_async` and `_get_data_range_async` from old `api_client.py` to new `AsyncCLIClient`.

**Key changes:**
1. Removed imports: `check_api_connection`, `get_api_client` from `api_client.py`
2. Wrapped function body in `async with AsyncCLIClient() as cli:`
3. Replaced `check_api_connection()` → `cli.health_check()`
4. Replaced `api_client.load_data()` → `cli.post("/data/acquire/download", json=payload, params=params)`
5. Replaced `api_client.get_operation_status()` → `cli.get(f"/operations/{operation_id}")`
6. Replaced `api_client.cancel_operation()` → `cli.delete(f"/operations/{operation_id}", json=cancel_payload)`
7. Replaced `api_client.get_data_range()` → `cli.post("/data/range", json=payload)` with success check
8. Added local `_format_duration()` helper (was method on KtrdrApiClient)

### Payload Construction

The old `KtrdrApiClient` methods built payloads internally. Now the command builds them:

```python
# Build payload for load request
payload: dict[str, Any] = {
    "symbol": symbol,
    "timeframe": timeframe,
    "mode": mode,
}
if start_date:
    payload["start_date"] = start_date
if end_date:
    payload["end_date"] = end_date
if trading_hours_only or include_extended:
    payload["filters"] = {
        "trading_hours_only": trading_hours_only,
        "include_extended": include_extended,
    }
params = {"async_mode": "true"} if async_mode else {}
```

### Test Update Required

The existing `test_data_commands_endpoint_fix.py` tests were mocking `_make_request` but `_show_data_async` uses `cli.get()`. Updated tests to mock `get` method directly with proper `AsyncMock` return values.

### Next Task Notes

For Task 4.5.3 (`dummy_commands.py`):
- Uses BOTH `api_client.py` and `operation_executor.py`
- Replace `check_api_connection()` with `cli.health_check()`
- Replace `AsyncOperationExecutor()` with `cli.execute_operation(adapter)`
- Need to check what operation adapter is used

---

## Task 4.5.3 Complete: Migrate dummy_commands.py

### Migration Applied

Migrated `dummy_commands.py` from dual old clients to new unified `AsyncCLIClient`.

**Old imports removed:**
```python
from ktrdr.cli.api_client import check_api_connection
from ktrdr.cli.operation_executor import AsyncOperationExecutor
```

**New imports:**
```python
from ktrdr.cli.client import AsyncCLIClient, CLIClientError
from rich.progress import (
    BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
)
```

### Key Changes

1. **Wrapped in `async with AsyncCLIClient() as cli:`** context manager
2. **Replaced `check_api_connection()`** → `cli.health_check()`
3. **Replaced `AsyncOperationExecutor.execute_operation()`** → `cli.execute_operation(adapter)`
4. **Progress display** now managed by command (Rich Progress + callback)
5. **Result handling** changed from boolean to dict with `status` field

### Progress Display Pattern

The dummy command follows the same pattern as training:
```python
progress_bar = Progress(...)
task_id = None

def on_progress(percentage: int, message: str) -> None:
    nonlocal task_id
    if task_id is not None:
        progress_bar.update(task_id, completed=percentage, description=message)

if show_progress and not quiet:
    with progress_bar:
        task_id = progress_bar.add_task("Running dummy...", total=100)
        result = await cli.execute_operation(adapter, on_progress=on_progress)
else:
    result = await cli.execute_operation(adapter)
```

### Test Updates

Updated both test files to mock `AsyncCLIClient` instead of old clients:
- `test_dummy_commands.py` — basic functionality tests
- `test_dummy_command_refactored.py` — comprehensive pattern tests

### Next Task Notes

For Task 4.5.4 (`model_commands.py` cleanup):
- This file is NOT wired to the CLI (`async_model_commands.py` is used instead)
- Check if any code is imported from it before deleting
- `grep -r "from ktrdr.cli.model_commands" ktrdr/` should return nothing

---

## Task 4.5.4 Complete: Clean up model_commands.py

### Decision: Delete model_commands.py

**Rationale:**
1. `async_model_commands.py` is the active implementation (wired in `ktrdr/cli/__init__.py`)
2. `model_commands.py` was NOT imported anywhere in production code
3. `model_commands.py` contained dead `list`, `test`, `predict` commands (unimplemented stubs)
4. Mixed old/new imports would need cleanup anyway

### Files Deleted
- `ktrdr/cli/model_commands.py` — 871 lines of dead code
- `tests/unit/cli/test_model_commands_training.py` — redundant with `test_async_model_commands_migration.py`

### Test Updates

Updated tests to import from `async_model_commands` instead of `model_commands`:
- `tests/unit/cli/test_train_dry_run_v3.py`
- `tests/integration/test_performance_benchmarks.py`
- `tests/integration/test_migration_performance_validation.py`
- `tests/integration/test_unified_cli_migration.py`

### Gotcha: Single-Command Typer App

`async_models_app` only has one command (`train`), so Typer treats it as a single-command app:
- When invoking with CliRunner, don't include "train" as first arg
- The command name is implicit when there's only one command

```python
# Old (model_commands.py with multiple commands):
result = runner.invoke(models_app, ["train", strategy_path, ...])

# New (async_model_commands.py with single command):
result = runner.invoke(models_app, [strategy_path, ...])
```

---

## Task 4.5.5 Complete: Final Verification

### Verification Results

**1. No old client imports in production code:**
```bash
grep -r "from ktrdr.cli.async_cli_client" ktrdr/  # No matches
grep -r "from ktrdr.cli.api_client" ktrdr/         # No matches
grep -r "from ktrdr.cli.operation_executor" ktrdr/ # No matches
```

**2. Unit tests:** 3836 passed, 76 skipped (39.53s)

**3. Quality checks:** All passed (ruff, black, mypy)

**4. E2E tests:** All migrated commands reach API correctly:
- `ktrdr dummy dummy` — Started, polled, handled result
- `ktrdr data load AAPL ...` — Started, polled, handled result
- `ktrdr models train ...` — Started, polled, handled result

### Test Cleanup Performed

Deleted obsolete tests that were testing old client infrastructure:
- `tests/integration/cli/test_unified_operations.py` — tested `AsyncOperationExecutor`
- `tests/unit/cli/test_operation_executor.py` — tested `AsyncOperationExecutor`
- Removed `TestKtrdrApiClientResumeOperation` class from `test_resume_command.py`

### Migration Complete

All CLI command files now use the unified `AsyncCLIClient` pattern:
- `ktrdr/cli/client/` — New unified client implementation
- No imports from `api_client.py` or `operation_executor.py` in production code
- Old client files can be deleted in M5 (cleanup phase)
