# Milestone 1 Handoff

Running notes for M1 CLI restructure implementation.

---

## Task 1.1 Complete: Create CLIState Dataclass

### Gotchas
- None encountered - straightforward dataclass implementation

### Emergent Patterns
- Test imports inside test functions (`from ktrdr.cli.state import CLIState`) to avoid side effects in lightweight import tests
- Use `FrozenInstanceError` (from `dataclasses`) not `AttributeError` when testing frozen dataclass immutability

### Next Task Notes
- Task 1.2 creates `output.py` which will import `CLIState` from `state.py`
- The output helpers should follow same pattern: minimal imports at module level

---

## Task 1.2 Complete: Create Output Helpers

### Gotchas
- **Argument order:** The design showed `print_success(message, data=None, state)` which is invalid Python (non-default after default). Implementation uses valid order: `print_success(message, state, data=None)`. Use keyword args when calling.
- **JSON errors to stdout:** JSON mode prints errors to stdout (not stderr) for parsability. This is intentional for scripting.

### Emergent Patterns
- Use `pytest.CaptureFixture` with `capsys.readouterr()` to test stdout/stderr separation
- Module-level `Console()` and `Console(stderr=True)` instances follow existing CLI patterns

### Next Task Notes
- Task 1.3 creates `OperationRunner` which uses `print_operation_started` and `print_error`
- Import pattern: `from ktrdr.cli.output import print_operation_started, print_error`

---

## Task 1.3 Complete: Create OperationRunner Wrapper

### Gotchas
- **Design referenced `AsyncOperationExecutor`** which doesn't exist. The actual class is `AsyncCLIClient` with `execute_operation()` method in `ktrdr/cli/client/`.
- **`raise SystemExit(1) from None`** needed to satisfy B904 linter rule when raising SystemExit after catching exceptions.

### Emergent Patterns
- Use `AsyncCLIClient` context manager for HTTP operations (handles retries, connection reuse)
- Mock pattern for async context managers: set `__aenter__` and `__aexit__` as `AsyncMock`
- Derive operation type from adapter class name by removing "OperationAdapter" suffix

### Next Task Notes
- Task 1.4 creates `app.py` entry point which will instantiate `CLIState` and pass to commands
- Commands access state via `ctx.obj` (Typer context)

---

## Task 1.4 Complete: Create New App Entry Point

### Gotchas
- **Test command registration cleanup:** When dynamically registering test commands in Typer tests, always clean up via `app.registered_commands = [cmd for cmd in app.registered_commands if cmd.name != "test-cmd"]` in a `finally` block to avoid polluting subsequent tests.
- **Sandbox detection in tests:** Default URL tests may pick up `.env.sandbox` port (e.g., 8001 instead of 8000). Tests should check `"localhost"` presence rather than specific port 8000.
- **Typer context type hints:** Test command functions must use `typer.Context` (not `pytest.FixtureRequest`) as the type hint for the context parameter.

### Emergent Patterns
- State capture pattern: Use `nonlocal` in test commands to capture state for assertions
- Help output validation: Use `CliRunner().invoke(app, ["--help"]).output` to verify help text

### Next Task Notes
- Task 1.5 implements the `train` command which will use `ctx.obj` to get `CLIState`
- Pattern: `state: CLIState = ctx.obj`
- `OperationRunner(state)` accepts the state for API URL and output formatting

---

## Task 1.5 Complete: Implement Train Command

### Gotchas
- **Module naming conflict:** Creating `ktrdr/cli/commands/` directory shadowed the existing `ktrdr/cli/commands.py` module. Solution: Renamed `commands.py` to `_commands_base.py` and re-exported symbols from `commands/__init__.py` for backward compatibility.
- **TrainingOperationAdapter requires symbols/timeframes:** The current adapter requires explicit `symbols` and `timeframes` parameters. Implementation uses hardcoded defaults (`["AAPL"]`, `["1h"]`) with TODO comments for future strategy config lookup via API.
- **Test cleanup pattern:** Always use `finally` block to clean up registered commands: `app.registered_commands = [cmd for cmd in app.registered_commands if cmd.name != "train"]`

### Emergent Patterns
- Command functions receive state via `ctx.obj`: `state: CLIState = ctx.obj`
- Error handling: Wrap in try/except, call `print_error(str(e), state)`, then `raise typer.Exit(1) from None`
- Test mocking: Patch both `OperationRunner` and `TrainingOperationAdapter` at the command module level (`ktrdr.cli.commands.train.OperationRunner`)

### Next Task Notes
- Task 1.6 wires the train command into `app.py` and creates `commands/__init__.py`
- Wire up: `from ktrdr.cli.commands.train import train; app.command()(train)`
- The `commands/__init__.py` already exists with backward-compat exports - just add train command registration to `app.py`

---

## Task 1.6 Complete: Wire Up and Test

### Gotchas
- **Operation adapter endpoints need `/api/v1` prefix:** The `AsyncCLIClient` uses explicit URLs without auto-appending `/api/v1`. All `OperationAdapter.get_start_endpoint()` methods must return full paths like `/api/v1/trainings/start`, not relative paths like `/trainings/start`.
- **Operations polling endpoint too:** The `execute_operation()` function in `ktrdr/cli/client/operations.py` was using `/operations/{id}` - changed to `/api/v1/operations/{id}`.
- **App entry point needs `__main__` block:** Added `if __name__ == "__main__": app()` to enable `python -m ktrdr.cli.app` invocation.

### Emergent Patterns
- Command registration: `app.command()(train)` - call `command()` on app, then call the result with the function
- URL pattern: When client is instantiated with explicit base_url (from CLIState.api_url), no `/api/v1` is appended. Adapters must include full API paths.

### M1 Complete Notes
- The new CLI architecture is proven end-to-end
- Fire-and-forget mode works (immediate return with operation ID)
- Follow mode works (polls and shows progress)
- JSON output works (parseable by jq)
- ~~Training failures are due to hardcoded symbols/timeframes in adapter not matching strategy - this is documented and expected to be fixed in M2~~ **FIXED in Task 1.7**

---

## Task 1.7 Complete: Make Symbols/Timeframes Optional in Training API

### Gotchas
- **Strategy config format varies:** `training_data.symbols` can use `mode: single` (with `.symbol` field) or `mode: multi_symbol` (with `.list` field). Same for `timeframes`. The extraction helper handles both.
- **Integration test mocking issues:** Tests using `@patch("ktrdr.api.endpoints.training.get_training_service")` have pre-existing structural issues - the patch doesn't override FastAPI's dependency injection cache. These failures are unrelated to Task 1.7 changes.
- **Pydantic validation behavior:** When `symbols` is optional and not provided, extra fields like `symbol` are silently ignored. Updated tests to use empty list `[]` (still validates) rather than wrong field name.

### Emergent Patterns
- **Strategy config extraction helper:** `extract_symbols_timeframes_from_strategy()` in `context.py` - reusable for any feature needing strategy metadata without full context build
- **Payload omission for None:** In `TrainingOperationAdapter.get_start_payload()`, only include `symbols`/`timeframes` if not None - allows backend to use defaults
- **CLI CSV parsing:** `_parse_csv_list()` helper converts comma-separated string to list or None - clean pattern for multi-value options

### Implementation Notes
1. **API Layer:** `TrainingRequest` now has `symbols: Optional[list[str]] = None` - validators check non-empty only if provided
2. **Service Layer:** `TrainingService.start_training()` calls `extract_symbols_timeframes_from_strategy()` when symbols/timeframes are None
3. **CLI Adapter:** Omits symbols/timeframes from payload when None (backend fills in)
4. **CLI Command:** Removed hardcoded `["AAPL"]`, `["1h"]` - now passes None unless `--symbols`/`--timeframes` override provided

### M1 Milestone Complete
All 7 tasks complete:
- [x] Task 1.1: CLIState dataclass
- [x] Task 1.2: Output helpers
- [x] Task 1.3: OperationRunner wrapper
- [x] Task 1.4: New app entry point
- [x] Task 1.5: Train command
- [x] Task 1.6: Wire up and test
- [x] Task 1.7: Optional symbols/timeframes

**E2E Verified:**
- `ktrdr train v3_minimal --start 2024-01-01 --end 2024-06-01` works without specifying symbols
- Backend extracts `EURUSD`/`1h` from strategy config
- Training completes successfully (6.2s)
- Model saved to `models/v3_minimal/1h_v6`
