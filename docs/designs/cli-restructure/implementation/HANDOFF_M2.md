# Milestone 2 Handoff

Running notes for M2 CLI restructure implementation.

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
