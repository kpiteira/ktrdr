# Handoff: M2 — Migrate Sync Commands

## Task 2.1 Complete: Migrate indicator_commands.py

### Migration Pattern Applied

Commands used async helpers wrapped in `asyncio.run()`. Simplified to sync:

```python
# Before
asyncio.run(_compute_indicator_async(...))

# After
with SyncCLIClient() as client:
    result = client.get("/indicators/")
```

### Gotchas

**health_check() replaces check_api_connection()**: The old `check_api_connection()` was async and required a separate import. Now use `client.health_check()` directly on the client instance.

**Error URL display**: Access `client.config.base_url` to show the URL in error messages (was `get_effective_api_url()` before).

**CLIClientError for client errors**: Import and catch `CLIClientError` to handle connection/timeout/API errors consistently.

### Next Task Notes

Task 2.2 (checkpoints_commands.py) follows the same pattern. Look for:
- `from ktrdr.cli.api_client import` → replace with `from ktrdr.cli.client import`
- `asyncio.run(_xxx_async(...))` → inline the logic in sync with SyncCLIClient
- `await check_api_connection()` → `client.health_check()`
- `await api_client.get/post(...)` → `client.get/post(...)`

---

## Task 2.2 Complete: Migrate checkpoints_commands.py

### Test Update Required

Tests for async helpers need rewriting to test sync commands directly. Pattern:
```python
# Old (testing async helper)
await _show_checkpoint_async("op_123", verbose=False)

# New (testing sync command with mocked client)
with patch("...SyncCLIClient") as mock_client_class:
    mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_sync_client)
    mock_client_class.return_value.__exit__ = MagicMock(return_value=False)
    show_checkpoint("op_123", verbose=False)
```

### Gotcha: sys.exit() in nested try/except

When `sys.exit(1)` is called inside a nested try block, it raises `SystemExit`. If the outer exception handler catches it, `sys.exit(1)` runs twice. Add `return` after `sys.exit(1)` to prevent test failures:
```python
sys.exit(1)
return  # For test mocking
```

### Next Task Notes

Task 2.3 (strategy_commands.py) - same migration pattern.

---

## Task 2.3 Complete: Migrate strategy_commands.py

### Partial Migration

Only `backtest_strategy` command uses API client. Other commands (`validate`, `list`, `validate-all`, `migrate`, `features`) work with local files only - no changes needed.

### API Method Replacement

Old `KtrdrApiClient` had convenience methods. With `SyncCLIClient`, use raw HTTP:
```python
# Old
result = await api_client.start_backtest(strategy_name=..., ...)
status = await api_client.get_operation_status(backtest_id)
results = await api_client.get_backtest_results(backtest_id)

# New
result = client.post("/backtests/run", json=payload)
status = client.get(f"/operations/{backtest_id}")
results = client.get(f"/backtests/{backtest_id}/results")
```

### Sync Sleep for Polling

Replace `await asyncio.sleep(2)` with `time.sleep(2)` for polling loops.

### Next Task Notes

Task 2.4 (ib_commands.py) - same pattern.
