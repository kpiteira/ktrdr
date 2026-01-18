# Milestone 2 Handoff

Running notes for M2 CLI restructure implementation.

---

## ⚠️ Known Technical Debt

**Dual Command Registration:** Commands are registered in both `ktrdr/cli/__init__.py` and `ktrdr/cli/app.py`. See HANDOFF_M3.md "Known Technical Debt" section for details. This will be resolved in M5 Task 5.3.

---

## ⚠️ CRITICAL: Do NOT Reimplement From Scratch

**Before writing any new command, READ the existing working code first:**

1. **Find existing code that does similar things:**
   - `agent_commands.py` - async API calls with `AsyncCLIClient`
   - `operations_commands.py` - sync API calls with `SyncCLIClient`
   - `sandbox_gate.py` - defensive response handling patterns

2. **Copy patterns exactly from working code, not from design docs:**
   - Design docs show idealized patterns that may not match reality
   - Existing code has battle-tested handling for edge cases
   - Check actual API endpoint implementations for response formats

3. **Key patterns to copy:**
   - `AsyncCLIClient()` without `base_url` parameter
   - Public methods `get()`, `post()` not private `_make_request()`
   - Response handling that matches actual API (some wrap in `{"data": ...}`, some don't)

4. **Verify with real backend, not just unit tests:**
   - Unit tests with mocks can both be wrong
   - Run `ktrdr <command>` against running backend to confirm

---

## Task 2.1 Complete: Implement Backtest Command

### Gotchas
- **BacktestingOperationAdapter still requires symbol/timeframe:** Unlike TrainingOperationAdapter (which was updated in M1 Task 1.7 to make symbols/timeframes optional), `BacktestingOperationAdapter` still requires explicit `symbol` and `timeframe` parameters. The implementation uses hardcoded placeholders (`"AAPL"`, `"1h"`) with TODO comments. This should be addressed when the backend supports reading symbol/timeframe from strategy config for backtests.

### Emergent Patterns
- **Follow train.py pattern exactly:** The backtest command closely mirrors train.py structure - state from `ctx.obj`, OperationRunner instantiation, adapter creation, `runner.start(adapter, follow=follow)`, and error handling with `print_error()` followed by `raise typer.Exit(1) from None`.
- **Capital option has `-c` shorthand:** Preserved from old command (`--capital`, `-c`).
- **Test pattern for shorthand options:** Use `mock_adapter.call_args[1]` to verify parameter values when testing shorthand flags like `-c`.

### Next Task Notes
- Task 2.2 (research command) has different async pattern - uses `asyncio.run()` internally rather than OperationRunner since agent trigger has special nested progress UX.
- The command should be wired up in Task 2.8 along with all other M2 commands.

---

## Task 2.2 Complete: Implement Research Command

### Gotchas
- **CRITICAL: Use `AsyncCLIClient()` without base_url:** Do NOT pass `base_url=state.api_url`. The `resolve_url()` function auto-appends `/api/v1` only when no explicit URL is passed to the client. Passing `base_url` bypasses this and causes 404 errors.
- **CRITICAL: Use public methods `get()` and `post()`, not `_make_request()`:** The existing CLI code uses the public convenience methods, not the private method. Copy existing patterns from `agent_commands.py` and `operations_commands.py`.
- **AsyncCLIClient uses `json=` not `json_data=`:** The `post()` method takes `json` as keyword argument, not `json_data`. MyPy caught this type error.
- **Import from agent_commands.py for monitoring:** The `_monitor_agent_cycle` function is reused directly from `ktrdr.cli.agent_commands` to preserve the nested progress bar UX.

### Emergent Patterns
- **Different pattern than train/backtest:** Research command uses async pattern (`asyncio.run()`) + direct API calls instead of OperationRunner. This is because agent operations have special nested progress display that's already implemented in `_monitor_agent_cycle()`.
- **Fire-and-forget uses `print_operation_started()`:** The output module provides standardized operation start messages with follow-up hints.
- **Test mocking for async context managers:** Tests use `AsyncMock()` and set up `__aenter__` / `__aexit__` returns on mock client.
- **Test assertions for client methods:** When testing `client.get()` calls, assert on `calls[0][0] == ("/endpoint",)` not `calls[0][0] == ("GET", "/endpoint")` since the HTTP method is implicit.

### Next Task Notes
- Task 2.3 (status command) will follow similar async pattern with `asyncio.run()`.
- Status command has dual mode: no argument shows dashboard, with argument shows specific operation.

---

## Task 2.3 Complete: Implement Status Command

### Gotchas
- **Commands must be registered on `cli_app`, not just in `app.py`:** The entry point `ktrdr.cli:app` resolves to `cli_app` from `_commands_base.py`, not `app.py`. Commands need to be imported and registered in `ktrdr/cli/__init__.py` with `cli_app.command()(func)`.
- **Callback must set `ctx.obj = CLIState`:** The legacy callback in `_commands_base.py` didn't set `ctx.obj`. New commands expect `ctx.obj` to be a `CLIState` object, so the callback was updated to set this.

### Emergent Patterns
- **Dual-mode command pattern:** Status command branches on optional argument - no arg shows dashboard, with arg shows operation details. Same pattern can be used for future commands that have both list/summary and detail views.
- **Dashboard fetches multiple endpoints:** Dashboard mode makes two parallel-capable API calls (`/operations` and `/workers`). Currently sequential but could be parallelized with `asyncio.gather()` if performance matters.
- **JSON output uses `json.dumps()` directly:** For simple JSON output, `print(json.dumps(data))` is sufficient rather than using output module helpers.

### Additional Gotchas (post-review)
- **CRITICAL: Workers endpoint returns list directly:** The `/workers` endpoint returns `[...]` not `{"data": {"workers": [...]}}`. Use `workers_result if isinstance(workers_result, list) else []` to handle correctly. See `sandbox_gate.py:235-236` for reference.
- **Different API response formats:** Operations endpoint uses `{"success": ..., "data": ...}` wrapper. Agent endpoints and workers endpoint return data directly. Always check actual API implementation.

### Next Task Notes
- Task 2.4 (follow command) is similar to status but with polling loop and Rich progress display.
- Follow command should handle Ctrl+C gracefully (detach, not cancel - user didn't start the operation).

---

## Task 2.4 Complete: Implement Follow Command

### Gotchas
- **Ctrl+C detaches, not cancels:** Unlike train/backtest where `--follow` + Ctrl+C cancels the operation (because user started it), the follow command detaches cleanly. User didn't start the operation, so they shouldn't be able to cancel it just by pressing Ctrl+C.
- **KeyboardInterrupt handling at command level:** The `KeyboardInterrupt` is caught in the main `follow()` function, not in the async helper. This ensures clean exit with friendly message.

### Emergent Patterns
- **Polling loop with terminal state check:** The pattern `while True: ... if status in ("completed", "failed", "cancelled"): break` is reusable for any operation polling.
- **Rich Progress with asyncio:** Use `with Progress(...) as progress:` inside async function, then `await asyncio.sleep()` for polling interval. Progress updates work fine with async code.
- **Three terminal states:** Operations end in one of: `completed`, `failed`, `cancelled`. Each gets distinct user-facing message style (green/red/yellow).

### Next Task Notes
- Task 2.5 (ops command) lists all operations in a table. Similar async pattern, but no polling - single fetch + table render.
- Task 2.6 (cancel command) is a simple DELETE request, similar to status operation mode but with DELETE verb.
- Task 2.7 (resume command) requires checkpoint API endpoint - may need backend verification.

---

## Task 2.5 Complete: Implement Ops Command

### Gotchas
- **CRITICAL: Preserve all behavior from operations_commands.py:** The M2 spec explicitly lists columns to preserve: ID, type, status, progress, checkpoint, symbol, duration. Don't simplify.
- **Checkpoint fetching is per-operation:** For each operation returned, the command must fetch `/checkpoints/{operation_id}` to get checkpoint info. This adds N+1 API calls but preserves existing behavior.
- **Progress can be in two formats:** Check both `op.get("progress_percentage")` (flat) and `op.get("progress", {}).get("percentage")` (nested).
- **CLIClientError vs Exception:** Checkpoint fetch may fail with `CLIClientError` (404) or general `Exception`. Handle both gracefully - just mark as no checkpoint.

### Emergent Patterns
- **Copy helper functions from existing code:** `_format_duration()` and `_format_checkpoint_summary()` were copied directly from `operations_commands.py`.
- **Filter params as strings:** API expects query params as strings, so use `"true"` not `True` for boolean filters like `active_only`.
- **Status color coding:** Consistent pattern: running=green, completed=bright_green, failed=red, cancelled=yellow.
- **All 5 filter options preserved:** `--status`, `--type`, `--limit`, `--active`, `--resumable` - all from original command.

### Next Task Notes
- Task 2.6 (cancel command) is straightforward DELETE request. Pattern similar to status but with `client.delete()` instead of `client.get()`.
- Task 2.7 (resume command) takes a checkpoint ID, not operation ID - different from other commands.

---

## Task 2.6 Complete: Implement Cancel Command

### Gotchas
- **Payload only sent when options provided:** The DELETE request only includes a JSON body when `--reason` or `--force` is specified. Without options, the payload is `None`.
- **API returns `{"success": True, "data": {...}}`:** The cancellation endpoint wraps response in standard format. Extract data with `result.get("data", {})`.

### Emergent Patterns
- **Same async pattern as other M2 commands:** Uses `asyncio.run()` + `AsyncCLIClient().delete()` for consistency with ops/status/follow.
- **Options preserved from old command:** `--reason/-r` and `--force/-f` with same shorthands as `operations_commands.py`.
- **Simple success output:** Yellow message "Cancelled operation: {op_id}" plus optional cancelled_at and reason display.

### Next Task Notes
- Task 2.7 (resume command) takes a checkpoint ID, not operation ID. Check if `/checkpoints/{id}/resume` endpoint exists in backend.
- Task 2.8 wires up all commands - cancel needs to be registered in `ktrdr/cli/__init__.py`.

---

## Task 2.7 Complete: Implement Resume Command

### Gotchas
- **CRITICAL: Design doc vs backend mismatch:** The M2 design says `ktrdr resume <checkpoint-id>` with endpoint `/checkpoints/{id}/resume`, but this endpoint doesn't exist. The actual backend uses `/operations/{operation_id}/resume`. Implementation follows actual backend.
- **Response includes `resumed_from` dict:** API returns `{"data": {..., "resumed_from": {"epoch": N, "checkpoint_type": "..."}}}`. Extract epoch and checkpoint type from this.

### Emergent Patterns
- **Same async pattern as other M2 commands:** Uses `asyncio.run()` + `AsyncCLIClient().post()` for consistency.
- **Follow option reuses polling pattern:** The `--follow` option reuses the same Progress display + polling loop from follow.py.
- **Green success message:** "Resumed operation: {op_id}" with epoch/checkpoint type details below.

### Next Task Notes
- Task 2.8 wires up ALL M2 commands. Need to register: backtest, research, status, follow, ops, cancel, resume.
- Commands register in `ktrdr/cli/__init__.py` with `cli_app.command()(func)`.

---

## Task 2.8 Complete: Wire Up All Commands

### Gotchas
- **Two CLI apps exist:** `ktrdr/cli/__init__.py` registers on `cli_app` (legacy entry point), while `ktrdr/cli/app.py` has its own `app` (new entry point). Task 2.8 updates BOTH to ensure tests and runtime work.
- **Tests import from `ktrdr.cli.app`:** The test file imports `from ktrdr.cli.app import app`, so commands must be registered in `app.py`, not just `__init__.py`.

### Emergent Patterns
- **Alphabetical import ordering:** Commands are imported in alphabetical order (backtest, cancel, follow, ops, research, resume, status, train) for consistency.
- **Registration matches import order:** Same alphabetical order for `app.command()` calls.

### Next Task Notes
- M2 is complete. All 8 commands (train, backtest, research, status, follow, ops, cancel, resume) are registered and accessible via `ktrdr --help`.
- Ready for M2 E2E validation (Task 2.9 if it exists, or milestone-level validation).
