# CLI Client Consolidation: Implementation Milestones

## Validation Summary

**Constraint:** External behavior must remain unchanged. Users see no difference.

**Approach:** Incremental migration — new client exists alongside old ones, commands migrate one at a time, old clients deleted when empty.

---

## Milestone 1: Create New Client Module

**Outcome:** New `ktrdr/cli/client/` module exists and passes tests. No commands use it yet.

**Scope:**
- `core.py` — URL resolution, retry logic, error parsing, IB diagnostics
- `sync_client.py` — SyncCLIClient
- `async_client.py` — AsyncCLIClient
- `operations.py` — Operation execution (ported from AsyncOperationExecutor)
- `errors.py` — Exception hierarchy
- `__init__.py` — Public exports

**Tests:**
- Unit tests for core logic (URL priority, retry decisions, backoff calculation)
- Unit tests for both clients (mocked httpx)
- Integration test against running API

**Verification:** `pytest tests/unit/cli/client/` passes

**Risk:** Low — purely additive, nothing changes yet

---

## Milestone 2: Migrate Sync Commands

**Outcome:** All commands using `KtrdrApiClient` now use `SyncCLIClient`. Behavior unchanged.

**Commands to migrate:**
- `indicator_commands.py`
- `checkpoints_commands.py`
- `strategy_commands.py`
- `ib_commands.py`
- `fuzzy_commands.py`
- `operations_commands.py`

**Migration pattern:**
```python
# Before
api_client = get_api_client()
result = api_client.get_request("/indicators")

# After
with SyncCLIClient() as client:
    result = client.get("/indicators")
```

**Verification per command:**
1. Run command, confirm same output
2. Run command with `--url`, confirm override works
3. Run command with server down, confirm same error message

**Risk:** Low — mechanical replacement, same external behavior

---

## Milestone 3: Migrate Async Commands

**Outcome:** All commands using `AsyncCLIClient` now use new `AsyncCLIClient`. Behavior unchanged.

**Commands to migrate:**
- `agent_commands.py`
- `async_data_commands.py`
- `data_commands.py` (async parts)
- `model_commands.py` (async parts)

**Migration pattern:**
```python
# Before
async with AsyncCLIClient() as client:
    result = await client._make_request("GET", "/symbols")

# After
async with AsyncCLIClient() as client:
    result = await client.get("/symbols")
```

**Verification:** Same as Milestone 2

**Risk:** Low — similar mechanical replacement

---

## Milestone 4: Migrate Operation Commands

**Outcome:** Commands using `AsyncOperationExecutor` now use `AsyncCLIClient.execute_operation()`. Behavior unchanged.

**Commands to migrate:**
- `model_commands.py` (training)
- `backtest_commands.py`

**Migration pattern:**
```python
# Before
executor = AsyncOperationExecutor()
result = await executor.execute(adapter)

# After
async with AsyncCLIClient() as client:
    result = await client.execute_operation(adapter)
```

**Verification:**
1. Run training command, confirm progress displays correctly
2. Cancel with Ctrl+C, confirm cancellation works
3. Confirm same error handling on failure

**Risk:** Medium — operation polling is more complex, needs careful testing

---

## Milestone 5: Cleanup

**Outcome:** Old client code deleted. Single source of truth.

**Delete:**
- `ktrdr/cli/async_cli_client.py`
- `ktrdr/cli/api_client.py`
- `ktrdr/cli/operation_executor.py`
- `get_api_client()` helper function

**Verification:**
1. `make test-unit` passes
2. `make quality` passes
3. Grep for old imports finds nothing

**Risk:** Low — if previous milestones work, this is just deletion

---

## Success Criteria

1. Single `ktrdr/cli/client/` module handles all CLI HTTP needs
2. All existing CLI tests pass
3. No user-facing behavior changes
4. ~500-700 lines of code removed
5. URL handling in exactly one place
