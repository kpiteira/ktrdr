# M9: Agent Progress Monitoring

**Goal:** User can run `ktrdr agent trigger --monitor` and see real-time nested progress through completion or cancellation.

**Branch:** `feature/agent-mvp`

---

## E2E Test Scenario

```bash
# 1. Ensure no active cycle
ktrdr agent status

# 2. Trigger with monitoring
ktrdr agent trigger --monitor

# Expected output progression:
# 🔬 Research Cycle [5%] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 00:12
#    Designing strategy...
#
# 🔬 Research Cycle [20%] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 01:45
#    Training model...
#    └─ Epoch 45/100 [45%] ━━━━━━━━━━━━━━━━━━━━━━━━━━━ 01:32
#
# ...eventually...
#
# ✓ Research cycle complete!
#    Strategy: momentum_breakout_20251220
#    Verdict: promising
#    Sharpe: 1.24 | Win Rate: 58% | Max DD: 12%

# 3. Verify Ctrl+C cancellation (separate test)
ktrdr agent trigger --monitor
# Press Ctrl+C during training phase
# Expected: Clean cancellation message with epoch info
```

---

## Task 9.1: Backend Progress Updates

**File:** `ktrdr/agents/workers/research_worker.py`
**Type:** CODING
**Estimated time:** 30 minutes

### Description

Add `update_progress()` calls when transitioning between phases. The worker already tracks phase in metadata; this adds the standard progress format that CLI can poll.

### Implementation Notes

Add calls at the start of each phase handler. Use `OperationProgress` from `ktrdr/api/models/operations.py`.

**Phase-to-progress mapping:**

| Phase | Percentage | current_step |
|-------|------------|--------------|
| designing | 5% | "Designing strategy..." |
| training | 20% | "Training model..." |
| backtesting | 65% | "Running backtest..." |
| assessing | 90% | "Assessing results..." |
| completed | 100% | "Complete" |

### Code Sketch

```python
# At the start of _start_design():
from ktrdr.api.models.operations import OperationProgress

await self.ops.update_progress(
    operation_id,
    OperationProgress(percentage=5.0, current_step="Designing strategy...")
)

# At the start of _start_training():
await self.ops.update_progress(
    operation_id,
    OperationProgress(percentage=20.0, current_step="Training model...")
)

# At the start of _start_backtest():
await self.ops.update_progress(
    operation_id,
    OperationProgress(percentage=65.0, current_step="Running backtest...")
)

# At the start of _start_assessment():
await self.ops.update_progress(
    operation_id,
    OperationProgress(percentage=90.0, current_step="Assessing results...")
)

# On completion (in _handle_assessing_phase when returning result):
await self.ops.update_progress(
    operation_id,
    OperationProgress(percentage=100.0, current_step="Complete")
)
```

### Testing Requirements

**Unit Tests:** `tests/unit/agent_tests/test_research_worker_progress.py`

- [ ] `update_progress()` called with 5% when entering designing phase
- [ ] `update_progress()` called with 20% when entering training phase
- [ ] `update_progress()` called with 65% when entering backtesting phase
- [ ] `update_progress()` called with 90% when entering assessing phase
- [ ] `update_progress()` called with 100% on completion

### Acceptance Criteria

- [ ] `GET /operations/{agent_op_id}` returns `progress.percentage` and `progress.current_step`
- [ ] Percentage matches phase (5%, 20%, 65%, 90%, 100%)
- [ ] `current_step` describes current phase
- [ ] Existing metadata (phase, training_op_id, etc.) still present

---

## Task 9.2: CLI Monitor Flag + Polling

**File:** `ktrdr/cli/agent_commands.py`
**Type:** CODING
**Estimated time:** 1 hour

### Description

Add `--monitor`/`--follow`/`-f` flags to `trigger_agent` command. When set, enter a polling loop that displays progress until completion or cancellation.

### Implementation Notes

- Follow pattern from `AsyncOperationExecutor._signal_handler()` for Ctrl+C handling
- Use Rich `Progress` for display (same as `operation_executor.py:452`)
- Poll interval: 500ms (same as `AsyncOperationExecutor.poll_interval`)
- On Ctrl+C: send `DELETE /operations/{id}`, wait for cancellation, show summary

### Code Sketch

```python
@agent_app.command("trigger")
@trace_cli_command("agent_trigger")
def trigger_agent(
    model: str = typer.Option(None, "--model", "-m", help="Model to use"),
    monitor: bool = typer.Option(False, "--monitor", "--follow", "-f", help="Monitor progress"),
):
    """Start a new research cycle."""
    try:
        asyncio.run(_trigger_agent_async(model=model, monitor=monitor))
    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


async def _trigger_agent_async(model: str | None = None, monitor: bool = False):
    """Async implementation of trigger command using API."""
    # ... existing trigger logic ...

    if result.get("triggered") and monitor:
        operation_id = result["operation_id"]
        await _monitor_agent_cycle(operation_id)


async def _monitor_agent_cycle(operation_id: str) -> dict[str, Any]:
    """
    Poll agent operation with progress display until completion.

    Handles Ctrl+C by sending DELETE /operations/{id}.
    """
    import signal
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn

    cancelled = False

    def signal_handler(signum, frame):
        nonlocal cancelled
        cancelled = True

    # Setup signal handler
    old_handler = signal.signal(signal.SIGINT, signal_handler)

    try:
        async with AsyncCLIClient() as client:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]Research Cycle"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Research", total=100)

                while not cancelled:
                    # Poll parent operation
                    result = await client._make_request("GET", f"/operations/{operation_id}")
                    op_data = result.get("data", {})
                    status = op_data.get("status")

                    # Update progress display
                    prog = op_data.get("progress", {})
                    pct = prog.get("percentage", 0)
                    step = prog.get("current_step", "Working...")
                    progress.update(task, completed=pct, description=f"[bold blue]Research Cycle[/] {step}")

                    # Check for terminal state
                    if status in ("completed", "failed", "cancelled"):
                        break

                    await asyncio.sleep(0.5)

                if cancelled:
                    # Send cancellation request
                    console.print("\n[yellow]Cancelling research cycle...[/yellow]")
                    await client._make_request("DELETE", f"/operations/{operation_id}")
                    # Wait briefly for cancellation to process
                    await asyncio.sleep(1)
                    result = await client._make_request("GET", f"/operations/{operation_id}")
                    op_data = result.get("data", {})

                # Show final status
                _show_completion_summary(op_data)
                return op_data
    finally:
        signal.signal(signal.SIGINT, old_handler)


def _show_completion_summary(op_data: dict[str, Any]) -> None:
    """Display completion or cancellation summary."""
    status = op_data.get("status")
    result = op_data.get("result", {})

    if status == "completed":
        console.print("\n[green]✓ Research cycle complete![/green]")
        if result.get("strategy_name"):
            console.print(f"   Strategy: {result['strategy_name']}")
        if result.get("verdict"):
            console.print(f"   Verdict: {result['verdict']}")
        metrics = result.get("metrics", {})
        if metrics:
            sharpe = metrics.get("sharpe_ratio", "N/A")
            win_rate = metrics.get("win_rate", "N/A")
            max_dd = metrics.get("max_drawdown", "N/A")
            console.print(f"   Sharpe: {sharpe} | Win Rate: {win_rate} | Max DD: {max_dd}")
    elif status == "cancelled":
        console.print("\n[yellow]⚠ Research cycle cancelled[/yellow]")
        phase = op_data.get("metadata", {}).get("parameters", {}).get("phase", "unknown")
        console.print(f"   Phase: {phase}")
    elif status == "failed":
        console.print("\n[red]✗ Research cycle failed[/red]")
        error = op_data.get("error", "Unknown error")
        console.print(f"   Error: {error}")
```

### Testing Requirements

**Unit Tests:** `tests/unit/cli_tests/test_agent_commands_monitor.py`

- [ ] `--monitor` flag parsed correctly
- [ ] `--follow` and `-f` work as aliases
- [ ] Polling loop exits on "completed" status
- [ ] Polling loop exits on "failed" status
- [ ] Polling loop exits on "cancelled" status
- [ ] Signal handler sets cancelled flag

### Acceptance Criteria

- [ ] `ktrdr agent trigger --monitor` shows progress bar
- [ ] `ktrdr agent trigger -f` works (short form)
- [ ] Progress updates as operation progresses
- [ ] Ctrl+C triggers cancellation request
- [ ] Completion shows summary with strategy name and metrics
- [ ] Without `--monitor`, behavior unchanged (fire-and-forget)

---

## Task 9.3: Nested Child Progress

**File:** `ktrdr/cli/agent_commands.py`
**Type:** CODING
**Estimated time:** 45 minutes

### Description

When the agent is in training or backtesting phase, also poll the child operation and display nested progress.

### Implementation Notes

- Read `training_op_id` or `backtest_op_id` from parent's `metadata.parameters`
- Poll child operation in parallel with parent
- Use Rich's ability to add/remove tasks dynamically
- Child task only shown when child_op_id exists

### Code Sketch

```python
async def _monitor_agent_cycle(operation_id: str) -> dict[str, Any]:
    """Poll agent operation with nested child progress display."""
    # ... signal handler setup ...

    try:
        async with AsyncCLIClient() as client:
            with Progress(
                SpinnerColumn(),
                TextColumn("{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                parent_task = progress.add_task("[bold blue]Research Cycle", total=100)
                child_task = None
                current_child_op_id = None

                while not cancelled:
                    # Poll parent operation
                    result = await client._make_request("GET", f"/operations/{operation_id}")
                    op_data = result.get("data", {})
                    status = op_data.get("status")

                    # Update parent progress
                    prog = op_data.get("progress", {})
                    pct = prog.get("percentage", 0)
                    step = prog.get("current_step", "Working...")
                    progress.update(parent_task, completed=pct, description=f"[bold blue]Research Cycle[/] {step}")

                    # Check for child operation
                    params = op_data.get("metadata", {}).get("parameters", {})
                    phase = params.get("phase", "")
                    child_op_id = params.get("training_op_id") or params.get("backtest_op_id")

                    if child_op_id and child_op_id != current_child_op_id:
                        # New child operation - add task
                        if child_task is not None:
                            progress.remove_task(child_task)
                        child_task = progress.add_task("   └─ Child", total=100)
                        current_child_op_id = child_op_id
                    elif not child_op_id and child_task is not None:
                        # No more child - remove task
                        progress.remove_task(child_task)
                        child_task = None
                        current_child_op_id = None

                    # Poll child operation if exists
                    if child_op_id:
                        try:
                            child_result = await client._make_request("GET", f"/operations/{child_op_id}")
                            child_data = child_result.get("data", {})
                            child_prog = child_data.get("progress", {})
                            child_pct = child_prog.get("percentage", 0)
                            child_step = child_prog.get("current_step", "Working...")
                            progress.update(child_task, completed=child_pct, description=f"   └─ {child_step}")
                        except Exception:
                            # Child may not exist yet or may have finished
                            pass

                    # Check for terminal state
                    if status in ("completed", "failed", "cancelled"):
                        break

                    await asyncio.sleep(0.5)

                # ... cancellation and summary handling ...
```

### Testing Requirements

**Unit Tests:** `tests/unit/cli_tests/test_agent_commands_monitor.py`

- [ ] Child task added when `training_op_id` present
- [ ] Child task added when `backtest_op_id` present
- [ ] Child task removed when child_op_id cleared
- [ ] Child progress displayed correctly
- [ ] Missing child operation handled gracefully (no crash)

### Acceptance Criteria

- [ ] During training phase, nested progress bar shows epoch info
- [ ] During backtesting phase, nested progress bar shows backtest progress
- [ ] During design/assessment, only parent progress shown
- [ ] Child progress bar appears/disappears as phases change

---

## Task 9.4: Error Handling + Polish

**File:** `ktrdr/cli/agent_commands.py`
**Type:** CODING
**Estimated time:** 30 minutes

### Description

Add graceful handling for connection errors, 404 responses (operation lost after restart), and polish the cancellation summary.

### Implementation Notes

- Connection errors: retry with exponential backoff (1s, 2s, 4s, max 5s)
- Show "Connection lost, retrying..." during retry
- 404 on parent operation: exit with "Operation not found" message
- Cancellation summary: include child operation state if available

### Code Sketch

```python
async def _monitor_agent_cycle(operation_id: str) -> dict[str, Any]:
    """Poll agent operation with error handling."""
    # ... setup ...

    retry_delay = 1.0
    max_retry_delay = 5.0

    while not cancelled:
        try:
            result = await client._make_request("GET", f"/operations/{operation_id}")
            retry_delay = 1.0  # Reset on success

            # Check for 404 (operation not found)
            if not result.get("success"):
                console.print("\n[yellow]Operation not found — may have been lost due to restart[/yellow]")
                return {"status": "lost"}

            # ... normal processing ...

        except httpx.ConnectError:
            # Connection lost - show message and retry
            progress.update(parent_task, description="[bold blue]Research Cycle[/] [yellow]⚠ Connection lost, retrying...[/]")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_retry_delay)
            continue
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                console.print("\n[yellow]Operation not found — may have been lost due to restart[/yellow]")
                return {"status": "lost"}
            raise


def _show_completion_summary(op_data: dict[str, Any], child_state: str | None = None) -> None:
    """Display completion or cancellation summary."""
    status = op_data.get("status")

    if status == "cancelled":
        console.print("\n[yellow]⚠ Research cycle cancelled[/yellow]")
        phase = op_data.get("metadata", {}).get("parameters", {}).get("phase", "unknown")
        console.print(f"   Phase: {phase}")
        if child_state:
            console.print(f"   {child_state}")
    # ... rest of summary logic ...
```

### Testing Requirements

**Unit Tests:** `tests/unit/cli_tests/test_agent_commands_monitor.py`

- [ ] Connection error triggers retry with backoff
- [ ] "Connection lost" message shown during retry
- [ ] 404 response exits with appropriate message
- [ ] Cancellation summary includes child state when available
- [ ] Retry delay resets after successful request

### Acceptance Criteria

- [ ] Network blip doesn't crash the monitor
- [ ] Backend restart shows clear "operation lost" message
- [ ] Ctrl+C cancellation shows phase and child progress in summary
- [ ] No hanging or zombie processes after errors

---

## Completion Checklist

- [ ] All 4 tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] E2E test passes (manual verification)
- [ ] Quality gates pass: `make quality`
- [ ] `ktrdr agent trigger` without `--monitor` still works (no regression)
- [ ] Ctrl+C cancellation works cleanly
