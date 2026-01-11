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
