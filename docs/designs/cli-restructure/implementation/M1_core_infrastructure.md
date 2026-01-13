---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 1: Core Infrastructure + Train Command

**Goal:** User can run `ktrdr train momentum --start 2024-01-01 --end 2024-06-01` and see an operation start.

**Branch:** `feature/cli-restructure-m1`

**Why this is M1:** Proves the entire new CLI architecture works end-to-end — new entry point, state management, output abstraction, and operation runner integration.

---

## Task 1.1: Create CLIState Dataclass

**File:** `ktrdr/cli/state.py`
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Wiring/DI, Configuration

**Description:**
Create a dataclass to hold CLI-wide state that gets populated by the root Typer callback and passed to commands. This replaces the current `_cli_state` dict approach with a typed, immutable structure.

**Implementation Notes:**
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class CLIState:
    json_mode: bool = False
    verbose: bool = False
    api_url: str = "http://localhost:8000"
```

- Use `frozen=True` to make it immutable after creation
- Default `api_url` matches current behavior
- Will be instantiated in app.py callback, stored in Typer context

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_cli_state_defaults()` — verify default values
- [ ] `test_cli_state_immutable()` — verify frozen raises on modification
- [ ] `test_cli_state_custom_values()` — verify constructor accepts overrides

*Integration Tests:*
- None required (pure dataclass)

*Smoke Test:*
```bash
uv run python -c "from ktrdr.cli.state import CLIState; print(CLIState())"
```

**Acceptance Criteria:**
- [ ] `CLIState` dataclass exists with `json_mode`, `verbose`, `api_url` fields
- [ ] Frozen (immutable after creation)
- [ ] Unit tests pass
- [ ] Can be imported without heavy dependencies

---

## Task 1.2: Create Output Helpers

**File:** `ktrdr/cli/output.py`
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** Cross-Component

**Description:**
Create output abstraction that formats messages for human or JSON consumption based on `CLIState.json_mode`. This centralizes all output formatting decisions.

**Implementation Notes:**
```python
import json
import sys
from rich.console import Console
from ktrdr.cli.state import CLIState

console = Console()
error_console = Console(stderr=True)

def print_success(message: str, data: dict | None = None, state: CLIState) -> None:
    """Print success message (human) or JSON response."""
    if state.json_mode:
        output = {"status": "success", "message": message}
        if data:
            output["data"] = data
        print(json.dumps(output))
    else:
        console.print(f"[green]{message}[/green]")

def print_error(message: str, state: CLIState) -> None:
    """Print error message (human) or JSON response."""
    if state.json_mode:
        print(json.dumps({"status": "error", "message": message}))
    else:
        error_console.print(f"[red bold]Error:[/red bold] {message}")

def print_operation_started(
    operation_type: str,
    operation_id: str,
    state: CLIState,
) -> None:
    """Print operation started message with follow-up hints."""
    if state.json_mode:
        print(json.dumps({
            "operation_id": operation_id,
            "status": "started",
            "type": operation_type,
        }))
    else:
        console.print(f"Started {operation_type}: [cyan]{operation_id}[/cyan]")
        console.print(f"  Track progress: ktrdr status {operation_id}")
        console.print(f"  Follow live:    ktrdr follow {operation_id}")
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_print_success_human()` — verify Rich formatting
- [ ] `test_print_success_json()` — verify JSON output structure
- [ ] `test_print_error_human()` — verify stderr usage
- [ ] `test_print_error_json()` — verify JSON error structure
- [ ] `test_print_operation_started_human()` — verify hints included
- [ ] `test_print_operation_started_json()` — verify JSON structure

*Integration Tests:*
- None required (pure output formatting)

*Smoke Test:*
```bash
uv run python -c "
from ktrdr.cli.state import CLIState
from ktrdr.cli.output import print_success
print_success('Test', {'key': 'value'}, CLIState(json_mode=True))
"
```

**Acceptance Criteria:**
- [ ] All output helpers implemented
- [ ] JSON mode produces valid JSON to stdout
- [ ] Human mode uses Rich formatting
- [ ] Errors go to stderr in both modes
- [ ] Unit tests pass

---

## Task 1.3: Create OperationRunner Wrapper

**File:** `ktrdr/cli/operation_runner.py`
**Type:** CODING
**Estimated time:** 1.5 hours

**Task Categories:** Cross-Component, Wiring/DI, Background/Async

**Description:**
Create a simplified wrapper around `AsyncCLIClient` that provides the fire-and-follow interface. This is the unified entry point for all operation commands.

**Implementation Notes:**
```python
import asyncio
from rich.console import Console
from ktrdr.cli.client import AsyncCLIClient
from ktrdr.cli.client.operations import OperationAdapter
from ktrdr.cli.state import CLIState
from ktrdr.cli.output import print_operation_started, print_error

class OperationRunner:
    """Unified start/follow for all operation types."""

    def __init__(self, state: CLIState):
        self.state = state
        self.console = Console()

    def start(
        self,
        adapter: OperationAdapter,
        follow: bool = False,
    ) -> None:
        """
        Start operation via API.

        If follow=False: print operation ID and return immediately.
        If follow=True: use existing polling/progress UX.
        """
        asyncio.run(self._start_async(adapter, follow))

    async def _start_async(
        self,
        adapter: OperationAdapter,
        follow: bool,
    ) -> None:
        async with AsyncCLIClient(base_url=self.state.api_url) as client:
            if follow:
                # Use existing progress display via execute_operation
                result = await client.execute_operation(adapter, on_progress=...)
                if result.get("status") == "failed":
                    raise SystemExit(1)
            else:
                # Fire-and-forget: just POST and print ID
                endpoint = adapter.get_start_endpoint()
                payload = adapter.get_start_payload()
                response = await client.post(endpoint, json=payload)
                operation_id = adapter.parse_start_response(response)
                print_operation_started(
                    operation_type=...,
                    operation_id=operation_id,
                    state=self.state,
                )
```

- Reuses existing `AsyncCLIClient.execute_operation()` for `--follow` mode
- Fire-and-forget mode is simpler: just POST and print ID
- Delegates all domain logic to adapters

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_operation_runner_fire_and_forget()` — mock HTTP, verify ID printed
- [ ] `test_operation_runner_follow_mode()` — mock executor, verify it's called
- [ ] `test_operation_runner_json_output()` — verify JSON structure in fire mode

*Integration Tests:*
- [ ] `test_operation_runner_wiring()` — verify `AsyncCLIClient` integration
- [ ] `test_operation_runner_api_url_passed()` — verify state.api_url used

*Smoke Test:*
```bash
# Requires backend running
uv run python -c "
from ktrdr.cli.state import CLIState
from ktrdr.cli.operation_runner import OperationRunner
from ktrdr.cli.operation_adapters import TrainingOperationAdapter
runner = OperationRunner(CLIState())
# Don't actually run - just verify import works
print('OperationRunner initialized')
"
```

**Acceptance Criteria:**
- [ ] `OperationRunner` class with `start()` method
- [ ] Fire-and-forget mode returns immediately with operation ID
- [ ] Follow mode delegates to `AsyncCLIClient.execute_operation()`
- [ ] Respects `CLIState.json_mode` for output
- [ ] Respects `CLIState.api_url` for backend
- [ ] Unit tests pass

---

## Task 1.4: Create New App Entry Point

**File:** `ktrdr/cli/app.py`
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** Wiring/DI, Configuration

**Description:**
Create the new CLI entry point with global flags (`--json`, `--verbose`, `--url`, `--port`) that populates `CLIState` and stores it in Typer context for commands to access.

**Implementation Notes:**
```python
from typing import Optional
import typer
from ktrdr.cli.state import CLIState
from ktrdr.cli.sandbox_detect import resolve_api_url
from ktrdr.cli.commands import normalize_api_url

app = typer.Typer(
    name="ktrdr",
    help="KTRDR - Trading analysis and automation tool.",
    add_completion=False,
)

@app.callback()
def main(
    ctx: typer.Context,
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output in JSON format for scripting",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show debug output and startup logs",
    ),
    url: Optional[str] = typer.Option(
        None,
        "--url",
        "-u",
        help="API URL (overrides auto-detection)",
        envvar="KTRDR_API_URL",
    ),
    port: Optional[int] = typer.Option(
        None,
        "--port",
        "-p",
        help="API port on localhost",
    ),
):
    """KTRDR CLI - workflow-oriented trading automation."""
    resolved_url = resolve_api_url(explicit_url=url, explicit_port=port)
    normalized_url = normalize_api_url(resolved_url)

    state = CLIState(
        json_mode=json_output,
        verbose=verbose,
        api_url=normalized_url,
    )
    ctx.obj = state

# Commands will be registered here
# from ktrdr.cli.commands import train
# app.command()(train.train)
```

- Uses Typer context (`ctx.obj`) to pass state to commands
- Reuses existing `resolve_api_url` and `normalize_api_url`
- Commands access state via `ctx.obj`

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_app_default_state()` — verify default CLIState values
- [ ] `test_app_json_flag()` — verify `--json` sets `json_mode=True`
- [ ] `test_app_verbose_flag()` — verify `-v` sets `verbose=True`
- [ ] `test_app_url_override()` — verify `--url` sets `api_url`
- [ ] `test_app_port_override()` — verify `--port` builds localhost URL

*Integration Tests:*
- [ ] `test_app_state_passed_to_command()` — verify `ctx.obj` accessible in command

*Smoke Test:*
```bash
uv run python -m ktrdr.cli.app --help
```

**Acceptance Criteria:**
- [ ] New `app.py` entry point exists
- [ ] Global flags `--json`, `--verbose`, `--url`, `--port` work
- [ ] `CLIState` stored in Typer context
- [ ] Help text matches design
- [ ] Unit tests pass

---

## Task 1.5: Implement Train Command

**File:** `ktrdr/cli/commands/train.py`
**Type:** CODING
**Estimated time:** 1.5 hours

**Task Categories:** API Endpoint, Cross-Component

**Description:**
Implement the `ktrdr train <strategy>` command that uses `OperationRunner` to start a training operation. This is the first complete command implementation.

**Implementation Notes:**
```python
from typing import Optional
import typer
from ktrdr.cli.state import CLIState
from ktrdr.cli.operation_runner import OperationRunner
from ktrdr.cli.operation_adapters import TrainingOperationAdapter
from ktrdr.cli.output import print_error

def train(
    ctx: typer.Context,
    strategy: str = typer.Argument(..., help="Strategy name to train"),
    start_date: str = typer.Option(..., "--start", help="Training start date (YYYY-MM-DD)"),
    end_date: str = typer.Option(..., "--end", help="Training end date (YYYY-MM-DD)"),
    validation_split: float = typer.Option(0.2, "--validation-split", help="Validation data split"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow progress until completion"),
):
    """Train a neural network model for a strategy.

    Examples:
        ktrdr train momentum --start 2024-01-01 --end 2024-06-01
        ktrdr train momentum --start 2024-01-01 --end 2024-06-01 --follow
    """
    state: CLIState = ctx.obj

    # Strategy resolution: we just pass the name, backend resolves
    # We need to get symbols/timeframes from strategy - fetch via API
    # For now, use the existing adapter which requires these params
    # TODO: Simplify adapter to just take strategy_name once backend supports it

    try:
        runner = OperationRunner(state)
        adapter = TrainingOperationAdapter(
            strategy_name=strategy,
            symbols=["AAPL"],  # TODO: Fetch from strategy or make optional
            timeframes=["1h"],  # TODO: Fetch from strategy or make optional
            start_date=start_date,
            end_date=end_date,
            validation_split=validation_split,
        )
        runner.start(adapter, follow=follow)
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1)
```

**Note:** The existing `TrainingOperationAdapter` requires `symbols` and `timeframes`. Either:
1. Fetch them from the strategy via API first, or
2. Update the backend to accept just `strategy_name` and resolve internally

For M1, we can hardcode or fetch. Refinement can happen in M2.

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_train_command_arguments()` — verify required args
- [ ] `test_train_command_options()` — verify default values
- [ ] `test_train_command_calls_runner()` — mock runner, verify adapter params

*Integration Tests:*
- [ ] `test_train_command_e2e()` — with running backend, verify operation starts
- [ ] `test_train_command_json_output()` — verify JSON structure

*Smoke Test:*
```bash
# Requires backend + strategy
ktrdr train momentum --start 2024-01-01 --end 2024-06-01
```

**Acceptance Criteria:**
- [ ] `ktrdr train <strategy> --start DATE --end DATE` works
- [ ] `--follow` triggers progress display
- [ ] `--json` produces JSON output
- [ ] Operation visible in backend after command
- [ ] Unit tests pass

---

## Task 1.6: Wire Up and Test

**File:** `ktrdr/cli/app.py`, `ktrdr/cli/commands/__init__.py`
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** Wiring/DI

**Description:**
Wire the train command into the new app entry point. Create the commands package structure. Verify end-to-end functionality.

**Implementation Notes:**

Create `ktrdr/cli/commands/__init__.py`:
```python
"""CLI command implementations."""
```

Update `ktrdr/cli/app.py`:
```python
from ktrdr.cli.commands.train import train

app.command()(train)
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_train_command_registered()` — verify command appears in --help

*Integration Tests:*
- [ ] `test_train_e2e_fire_and_forget()` — start operation, verify ID returned
- [ ] `test_train_e2e_follow()` — start with --follow, verify completion

*Smoke Test:*
```bash
# Full E2E test
docker compose up -d
ktrdr train momentum --start 2024-01-01 --end 2024-06-01
# Should print: Started training: op_xxx
curl http://localhost:8000/api/v1/operations | jq
# Should show the operation
```

**Acceptance Criteria:**
- [ ] `ktrdr train` appears in `ktrdr --help`
- [ ] Command executes successfully against running backend
- [ ] Operation created and trackable
- [ ] All M1 tests pass

---

## Milestone 1 Verification

### E2E Test Scenario

**E2E Test Recipe:** [cli/train-command](../../../../.claude/skills/e2e-testing/tests/cli/train-command.md)

**Purpose:** Prove the new CLI architecture works end-to-end with one complete command.

**Duration:** ~30 seconds

**Prerequisites:**
- Backend running (`docker compose up`)
- Strategy "momentum" exists (or any valid strategy)

**Test Steps:**

```bash
# 1. Verify new entry point works
python -m ktrdr.cli.app --help
# Should show: train command, --json flag, --verbose flag

# 2. Test fire-and-forget mode
python -m ktrdr.cli.app train momentum --start 2024-01-01 --end 2024-06-01
# Expected output:
# Started training: op_abc123
#   Track progress: ktrdr status op_abc123
#   Follow live:    ktrdr follow op_abc123

# 3. Verify operation exists
curl -s http://localhost:8000/api/v1/operations | jq '.data[0]'
# Should show operation with type=training

# 4. Test JSON output
python -m ktrdr.cli.app --json train momentum --start 2024-01-01 --end 2024-06-01
# Expected: {"operation_id": "op_...", "status": "started", "type": "training"}

# 5. Test follow mode (optional, takes longer)
python -m ktrdr.cli.app train momentum --start 2024-01-01 --end 2024-06-01 --follow
# Should show progress bar until completion
```

**Success Criteria:**
- [ ] `--help` shows train command with correct options
- [ ] Fire-and-forget returns operation ID immediately
- [ ] Operation visible in backend API
- [ ] JSON mode produces valid JSON
- [ ] Follow mode shows progress (if tested)
- [ ] No errors in logs: `docker compose logs backend --since 5m | grep -i error`

### Completion Checklist

- [ ] All 6 tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] E2E test passes (above)
- [ ] Quality gates pass: `make quality`
- [ ] No regressions in existing CLI (old commands still work)
