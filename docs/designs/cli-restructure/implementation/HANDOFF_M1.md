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
