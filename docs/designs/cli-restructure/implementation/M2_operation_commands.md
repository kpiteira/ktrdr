---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 2: Operation Commands

**Goal:** User can run all operation-based commands: `backtest`, `research`, `resume`, `status`, `follow`, `ops`, `cancel`.

**Branch:** `feature/cli-restructure-m2`

**Builds on:** Milestone 1 (core infrastructure + train)

---

## Task 2.1: Implement Backtest Command

**File:** `ktrdr/cli/commands/backtest.py`
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** API Endpoint, Cross-Component

**Description:**
Implement `ktrdr backtest <strategy>` using the existing `BacktestingOperationAdapter` and `OperationRunner`.

**Implementation Notes:**
```python
from typing import Optional
import typer
from ktrdr.cli.state import CLIState
from ktrdr.cli.operation_runner import OperationRunner
from ktrdr.cli.operation_adapters import BacktestingOperationAdapter
from ktrdr.cli.output import print_error

def backtest(
    ctx: typer.Context,
    strategy: str = typer.Argument(..., help="Strategy name to backtest"),
    start_date: str = typer.Option(..., "--start", help="Backtest start date (YYYY-MM-DD)"),
    end_date: str = typer.Option(..., "--end", help="Backtest end date (YYYY-MM-DD)"),
    capital: float = typer.Option(100000.0, "--capital", help="Initial capital"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow progress until completion"),
):
    """Run a backtest for a strategy.

    Examples:
        ktrdr backtest momentum --start 2024-01-01 --end 2024-06-01
        ktrdr backtest momentum --start 2024-01-01 --end 2024-06-01 -f
    """
    state: CLIState = ctx.obj

    try:
        runner = OperationRunner(state)
        adapter = BacktestingOperationAdapter(
            strategy_name=strategy,
            symbol="AAPL",  # TODO: Get from strategy
            timeframe="1h",  # TODO: Get from strategy
            start_date=start_date,
            end_date=end_date,
            initial_capital=capital,
        )
        runner.start(adapter, follow=follow)
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1)
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_backtest_command_arguments()` — verify required args
- [ ] `test_backtest_command_defaults()` — verify capital default
- [ ] `test_backtest_command_calls_runner()` — mock runner

*Integration Tests:*
- [ ] `test_backtest_e2e()` — with backend, verify operation starts

*Smoke Test:*
```bash
ktrdr backtest momentum --start 2024-01-01 --end 2024-06-01
```

**Acceptance Criteria:**
- [ ] `ktrdr backtest <strategy> --start DATE --end DATE` works
- [ ] `--capital` option works
- [ ] `--follow` triggers progress display
- [ ] Unit tests pass

---

## Task 2.2: Implement Research Command

**File:** `ktrdr/cli/commands/research.py`
**Type:** CODING
**Estimated time:** 1.5 hours

**Task Categories:** API Endpoint, Cross-Component, Background/Async

**Description:**
Implement `ktrdr research <goal>` that wraps the existing agent trigger functionality. The `--follow` mode must preserve the existing nested progress bar UX from `agent_commands.py`.

**Implementation Notes:**
```python
import asyncio
import typer
from ktrdr.cli.state import CLIState
from ktrdr.cli.output import print_error
from ktrdr.cli.async_cli_client import AsyncCLIClient

def research(
    ctx: typer.Context,
    goal: str = typer.Argument(..., help="Research goal or brief"),
    model: str = typer.Option(None, "--model", "-m", help="Model: opus, sonnet, haiku"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow progress until completion"),
):
    """Start an AI research cycle.

    Examples:
        ktrdr research "build a momentum strategy for AAPL"
        ktrdr research "analyze volatility patterns" --follow
    """
    state: CLIState = ctx.obj

    try:
        asyncio.run(_research_async(state, goal, model, follow))
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1)

async def _research_async(state: CLIState, goal: str, model: str | None, follow: bool):
    from rich.console import Console
    from ktrdr.cli.output import print_operation_started

    console = Console()

    json_data = {"brief": goal}
    if model:
        json_data["model"] = model

    async with AsyncCLIClient(base_url=state.api_url) as client:
        result = await client._make_request("POST", "/agent/trigger", json_data=json_data)

    if not result.get("triggered"):
        reason = result.get("reason", "unknown")
        raise RuntimeError(f"Could not start research: {reason}")

    operation_id = result["operation_id"]

    if follow:
        # Reuse existing nested progress UX
        from ktrdr.cli.agent_commands import _monitor_agent_cycle
        console.print("\n[green]Research cycle started![/green]")
        console.print(f"  Operation ID: {operation_id}")
        if result.get("model"):
            console.print(f"  Model: {result['model']}")
        console.print()
        await _monitor_agent_cycle(operation_id)
    else:
        print_operation_started("research", operation_id, state)
```

**Key point:** We reuse `_monitor_agent_cycle` from `agent_commands.py` to preserve the nested progress bar UX. This is intentional — don't rewrite the monitoring logic.

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_research_command_arguments()` — verify goal is required
- [ ] `test_research_command_model_option()` — verify model passed to API

*Integration Tests:*
- [ ] `test_research_triggers_agent()` — with backend, verify agent starts
- [ ] `test_research_follow_shows_progress()` — verify nested progress

*Smoke Test:*
```bash
ktrdr research "test strategy"
```

**Acceptance Criteria:**
- [ ] `ktrdr research <goal>` works
- [ ] `--model` option passed to API
- [ ] `--follow` shows nested progress (existing UX preserved)
- [ ] Fire-and-forget returns operation ID immediately
- [ ] Unit tests pass

---

## Task 2.3: Implement Status Command

**File:** `ktrdr/cli/commands/status.py`
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** API Endpoint

**Description:**
Implement `ktrdr status [op-id]`. Without argument: show system dashboard. With argument: show specific operation status.

**Implementation Notes:**
```python
import asyncio
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from ktrdr.cli.state import CLIState
from ktrdr.cli.async_cli_client import AsyncCLIClient
from ktrdr.cli.output import print_error

console = Console()

def status(
    ctx: typer.Context,
    operation_id: Optional[str] = typer.Argument(None, help="Operation ID (optional)"),
):
    """Show system status or specific operation status.

    Examples:
        ktrdr status              # System dashboard
        ktrdr status op_abc123    # Specific operation
    """
    state: CLIState = ctx.obj

    try:
        if operation_id:
            asyncio.run(_show_operation_status(state, operation_id))
        else:
            asyncio.run(_show_dashboard(state))
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1)

async def _show_dashboard(state: CLIState):
    """Show system dashboard with operations, workers, IB status."""
    async with AsyncCLIClient(base_url=state.api_url) as client:
        # Fetch operations
        ops_result = await client._make_request("GET", "/operations")
        ops = ops_result.get("data", [])

        running = len([o for o in ops if o.get("status") == "running"])
        completed = len([o for o in ops if o.get("status") == "completed"])

        # Fetch workers
        workers_result = await client._make_request("GET", "/workers")
        workers = workers_result.get("data", {}).get("workers", [])

    if state.json_mode:
        import json
        print(json.dumps({
            "operations": {"running": running, "completed": completed},
            "workers": len(workers),
        }))
    else:
        console.print(f"Operations: {running} running, {completed} completed")
        console.print(f"Workers: {len(workers)} available")

async def _show_operation_status(state: CLIState, operation_id: str):
    """Show specific operation status."""
    async with AsyncCLIClient(base_url=state.api_url) as client:
        result = await client._make_request("GET", f"/operations/{operation_id}")

    op = result.get("data", {})

    if state.json_mode:
        import json
        print(json.dumps(op))
    else:
        console.print(f"Operation: [cyan]{op.get('operation_id')}[/cyan]")
        console.print(f"Type: {op.get('operation_type')}")
        console.print(f"Status: {op.get('status')}")
        progress = op.get("progress", {})
        if progress.get("percentage"):
            console.print(f"Progress: {progress['percentage']}%")
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_status_no_arg_shows_dashboard()` — verify dashboard path
- [ ] `test_status_with_arg_shows_operation()` — verify operation path

*Integration Tests:*
- [ ] `test_status_dashboard_e2e()` — with backend, verify data
- [ ] `test_status_operation_e2e()` — with running operation, verify details

*Smoke Test:*
```bash
ktrdr status
ktrdr status op_abc123
```

**Acceptance Criteria:**
- [ ] `ktrdr status` shows dashboard
- [ ] `ktrdr status <op-id>` shows operation details
- [ ] `--json` works for both modes
- [ ] Unit tests pass

---

## Task 2.4: Implement Follow Command

**File:** `ktrdr/cli/commands/follow.py`
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** API Endpoint, Background/Async

**Description:**
Implement `ktrdr follow <op-id>` that attaches to a running operation and shows progress until completion.

**Implementation Notes:**
```python
import asyncio
import typer
from rich.console import Console
from ktrdr.cli.state import CLIState
from ktrdr.cli.output import print_error
from ktrdr.cli.operation_executor import AsyncOperationExecutor

console = Console()

def follow(
    ctx: typer.Context,
    operation_id: str = typer.Argument(..., help="Operation ID to follow"),
):
    """Follow a running operation until completion.

    Examples:
        ktrdr follow op_abc123
    """
    state: CLIState = ctx.obj

    try:
        asyncio.run(_follow_operation(state, operation_id))
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1)

async def _follow_operation(state: CLIState, operation_id: str):
    """Poll operation and display progress until terminal state."""
    from rich.progress import (
        Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    )

    executor = AsyncOperationExecutor(base_url=state.api_url)

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        TextColumn("{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("Following...", total=100)

        import httpx
        async with httpx.AsyncClient() as client:
            final_status = await executor._poll_until_complete(
                operation_id=operation_id,
                http_client=client,
                progress=progress,
                task_id=task_id,
            )

    status = final_status.get("status")
    if status == "completed":
        console.print("[green]Operation completed successfully![/green]")
    elif status == "failed":
        console.print(f"[red]Operation failed: {final_status.get('error_message')}[/red]")
    elif status == "cancelled":
        console.print("[yellow]Operation was cancelled[/yellow]")
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_follow_requires_operation_id()` — verify required arg

*Integration Tests:*
- [ ] `test_follow_running_operation()` — with running op, verify progress shown
- [ ] `test_follow_completed_operation()` — verify immediate completion message

*Smoke Test:*
```bash
# Start an operation, then follow it
ktrdr train momentum --start 2024-01-01 --end 2024-06-01
# Note the op_id
ktrdr follow op_xxx
```

**Acceptance Criteria:**
- [ ] `ktrdr follow <op-id>` shows progress bar
- [ ] Completion/failure/cancellation handled
- [ ] Ctrl+C works gracefully
- [ ] Unit tests pass

---

## Task 2.5: Implement Ops Command

**File:** `ktrdr/cli/commands/ops.py`
**Type:** CODING
**Estimated time:** 45 min

**Task Categories:** API Endpoint

**Description:**
Implement `ktrdr ops` to list all operations in a table format.

**Implementation Notes:**
```python
import asyncio
import typer
from rich.console import Console
from rich.table import Table
from ktrdr.cli.state import CLIState
from ktrdr.cli.async_cli_client import AsyncCLIClient
from ktrdr.cli.output import print_error

console = Console()

def ops(ctx: typer.Context):
    """List all operations.

    Examples:
        ktrdr ops
        ktrdr ops --json
    """
    state: CLIState = ctx.obj

    try:
        asyncio.run(_list_operations(state))
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1)

async def _list_operations(state: CLIState):
    async with AsyncCLIClient(base_url=state.api_url) as client:
        result = await client._make_request("GET", "/operations")

    operations = result.get("data", [])

    if state.json_mode:
        import json
        print(json.dumps(operations))
    else:
        table = Table(title="Operations")
        table.add_column("ID", style="cyan")
        table.add_column("Type")
        table.add_column("Status")
        table.add_column("Progress")
        table.add_column("Started")

        for op in operations:
            progress = op.get("progress", {}).get("percentage", 0)
            table.add_row(
                op.get("operation_id", "")[:12],
                op.get("operation_type", ""),
                op.get("status", ""),
                f"{progress}%",
                op.get("created_at", "")[:19],
            )

        console.print(table)
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_ops_command_no_args()` — verify no args required

*Integration Tests:*
- [ ] `test_ops_lists_operations()` — with backend, verify list returned
- [ ] `test_ops_json_output()` — verify JSON array structure

*Smoke Test:*
```bash
ktrdr ops
ktrdr ops --json
```

**Acceptance Criteria:**
- [ ] `ktrdr ops` shows table of operations
- [ ] `--json` produces JSON array
- [ ] Empty state handled gracefully
- [ ] Unit tests pass

---

## Task 2.6: Implement Cancel Command

**File:** `ktrdr/cli/commands/cancel.py`
**Type:** CODING
**Estimated time:** 45 min

**Task Categories:** API Endpoint

**Description:**
Implement `ktrdr cancel <op-id>` to cancel a running operation.

**Implementation Notes:**
```python
import asyncio
import typer
from rich.console import Console
from ktrdr.cli.state import CLIState
from ktrdr.cli.async_cli_client import AsyncCLIClient
from ktrdr.cli.output import print_error, print_success

console = Console()

def cancel(
    ctx: typer.Context,
    operation_id: str = typer.Argument(..., help="Operation ID to cancel"),
):
    """Cancel a running operation.

    Examples:
        ktrdr cancel op_abc123
    """
    state: CLIState = ctx.obj

    try:
        asyncio.run(_cancel_operation(state, operation_id))
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1)

async def _cancel_operation(state: CLIState, operation_id: str):
    async with AsyncCLIClient(base_url=state.api_url) as client:
        result = await client._make_request("DELETE", f"/operations/{operation_id}")

    if state.json_mode:
        import json
        print(json.dumps({"operation_id": operation_id, "status": "cancelled"}))
    else:
        console.print(f"[yellow]Cancelled operation: {operation_id}[/yellow]")
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_cancel_requires_operation_id()` — verify required arg

*Integration Tests:*
- [ ] `test_cancel_running_operation()` — with running op, verify cancellation
- [ ] `test_cancel_already_completed()` — verify error handling

*Smoke Test:*
```bash
# Start an operation, then cancel it
ktrdr train momentum --start 2024-01-01 --end 2024-06-01
ktrdr cancel op_xxx
```

**Acceptance Criteria:**
- [ ] `ktrdr cancel <op-id>` cancels operation
- [ ] Already-completed operations handled gracefully
- [ ] `--json` produces JSON output
- [ ] Unit tests pass

---

## Task 2.7: Implement Resume Command

**File:** `ktrdr/cli/commands/resume.py`
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** API Endpoint, Cross-Component

**Description:**
Implement `ktrdr resume <checkpoint-id>` to restart a failed training or backtest operation from its last checkpoint. This is verb-first (not `checkpoint restore`) to match the workflow-oriented design.

**Implementation Notes:**
```python
import asyncio
import typer
from rich.console import Console
from ktrdr.cli.state import CLIState
from ktrdr.cli.async_cli_client import AsyncCLIClient
from ktrdr.cli.output import print_error, print_operation_started

console = Console()

def resume(
    ctx: typer.Context,
    checkpoint_id: str = typer.Argument(..., help="Checkpoint ID to resume from"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow progress until completion"),
):
    """Resume a failed operation from a checkpoint.

    KTRDR automatically checkpoints long-running operations (training, backtest).
    If an operation fails, you can resume it from the last checkpoint.

    Examples:
        ktrdr resume chk_abc123
        ktrdr resume chk_abc123 --follow
    """
    state: CLIState = ctx.obj

    try:
        asyncio.run(_resume_operation(state, checkpoint_id, follow))
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1)

async def _resume_operation(state: CLIState, checkpoint_id: str, follow: bool):
    """Resume operation from checkpoint via API."""
    async with AsyncCLIClient(base_url=state.api_url) as client:
        # POST to resume endpoint with checkpoint ID
        result = await client._make_request(
            "POST",
            f"/checkpoints/{checkpoint_id}/resume"
        )

    if not result.get("success"):
        raise RuntimeError(result.get("error", "Failed to resume from checkpoint"))

    operation_id = result.get("operation_id")
    operation_type = result.get("operation_type", "operation")

    if follow:
        # Use standard follow logic
        from ktrdr.cli.operation_executor import AsyncOperationExecutor
        from rich.progress import (
            Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
        )

        console.print(f"\n[green]Resumed {operation_type} from checkpoint![/green]")
        console.print(f"  Operation ID: {operation_id}")
        console.print(f"  Checkpoint: {checkpoint_id}")
        console.print()

        executor = AsyncOperationExecutor(base_url=state.api_url)

        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            BarColumn(),
            TextColumn("{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task_id = progress.add_task("Resuming...", total=100)

            import httpx
            async with httpx.AsyncClient() as http_client:
                final_status = await executor._poll_until_complete(
                    operation_id=operation_id,
                    http_client=http_client,
                    progress=progress,
                    task_id=task_id,
                )

        status = final_status.get("status")
        if status == "completed":
            console.print("[green]Operation completed successfully![/green]")
        elif status == "failed":
            console.print(f"[red]Operation failed: {final_status.get('error_message')}[/red]")
    else:
        print_operation_started(operation_type, operation_id, state)
```

**Backend dependency:** Requires `POST /api/v1/checkpoints/{id}/resume` endpoint that:
- Looks up the checkpoint
- Creates a new operation of the same type (training/backtest)
- Initializes it from the checkpoint state
- Returns the new operation_id

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_resume_requires_checkpoint_id()` — verify required arg
- [ ] `test_resume_calls_api()` — mock API, verify endpoint called

*Integration Tests:*
- [ ] `test_resume_from_checkpoint()` — with failed op + checkpoint, verify resume works
- [ ] `test_resume_invalid_checkpoint()` — verify error handling

*Smoke Test:*
```bash
# After a failed training with checkpoint
ktrdr list checkpoints
# Note checkpoint ID
ktrdr resume chk_xxx
```

**Acceptance Criteria:**
- [ ] `ktrdr resume <checkpoint-id>` starts resumed operation
- [ ] Returns new operation ID
- [ ] `--follow` shows progress
- [ ] Invalid checkpoint handled gracefully
- [ ] Unit tests pass

---

## Task 2.8: Wire Up All Commands

**File:** `ktrdr/cli/app.py`
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Wiring/DI

**Description:**
Register all M2 commands in the app entry point.

**Implementation Notes:**
```python
from ktrdr.cli.commands.train import train
from ktrdr.cli.commands.backtest import backtest
from ktrdr.cli.commands.research import research
from ktrdr.cli.commands.resume import resume
from ktrdr.cli.commands.status import status
from ktrdr.cli.commands.follow import follow
from ktrdr.cli.commands.ops import ops
from ktrdr.cli.commands.cancel import cancel

app.command()(train)
app.command()(backtest)
app.command()(research)
app.command()(resume)
app.command()(status)
app.command()(follow)
app.command()(ops)
app.command()(cancel)
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_all_commands_registered()` — verify all appear in --help

*Integration Tests:*
- [ ] Full workflow test: train → ops → follow → cancel

*Smoke Test:*
```bash
ktrdr --help
# Should show: train, backtest, research, resume, status, follow, ops, cancel
```

**Acceptance Criteria:**
- [ ] All 8 commands appear in `--help`
- [ ] All commands executable
- [ ] M1 tests still pass

---

## Milestone 2 Verification

### E2E Test Scenario

**E2E Test Recipe:** [cli/operations-workflow](../../../../.claude/skills/e2e-testing/tests/cli/operations-workflow.md)

**Purpose:** Prove all operation commands work together.

**Duration:** ~2 minutes

**Prerequisites:**
- Backend running
- Strategy exists
- No conflicting operations

**Test Steps:**

```bash
# 1. Start a backtest (fire-and-forget)
ktrdr backtest momentum --start 2024-01-01 --end 2024-06-01
# Capture op_id from output

# 2. List operations
ktrdr ops
# Should show the backtest

# 3. Check status
ktrdr status $OP_ID
# Should show running/progress

# 4. Follow the operation
ktrdr follow $OP_ID
# Should show progress bar until completion

# 5. Start a research cycle
ktrdr research "test strategy"
# Should return operation ID

# 6. Cancel it
ktrdr cancel $RESEARCH_OP_ID
# Should confirm cancellation

# 7. Test resume (if checkpoint available)
ktrdr list checkpoints
# If checkpoints exist:
ktrdr resume chk_xxx

# 8. Verify JSON output works
ktrdr ops --json | jq
```

**Success Criteria:**
- [ ] All commands execute without errors
- [ ] Resume works with valid checkpoint
- [ ] Operations tracked correctly
- [ ] Follow shows progress
- [ ] Cancel works
- [ ] JSON output valid

### Completion Checklist

- [ ] All 8 tasks complete
- [ ] Unit tests pass: `make test-unit`
- [ ] E2E test passes
- [ ] M1 E2E still passes
- [ ] Quality gates pass: `make quality`
