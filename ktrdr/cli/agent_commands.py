"""Agent research system commands for the KTRDR CLI.

Simplified commands:
- status: Show current agent state
- trigger: Start a new research cycle
- cancel: Cancel active research cycle (M6 Task 6.3)
"""

import asyncio
import signal
import sys

import typer
from rich.console import Console
from rich.table import Table

from ktrdr.cli.async_cli_client import AsyncCLIClient, AsyncCLIClientError
from ktrdr.cli.telemetry import trace_cli_command
from ktrdr.logging import get_logger

logger = get_logger(__name__)
console = Console()
error_console = Console(stderr=True)

# Create the CLI app for agent commands
agent_app = typer.Typer(
    name="agent",
    help="Research agent management commands",
    no_args_is_help=True,
)


@agent_app.command("status")
@trace_cli_command("agent_status")
def show_status():
    """Show current agent research system status.

    Displays whether a cycle is active and its current phase,
    or information about the last completed cycle.

    Examples:
        ktrdr agent status
    """
    try:
        asyncio.run(_show_status_async())
    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


async def _show_status_async():
    """Async implementation of status command using API."""
    try:
        async with AsyncCLIClient() as client:
            result = await client._make_request("GET", "/agent/status")

        console.print("\n[bold]Agent Research System Status[/bold]")
        console.print()

        if result.get("status") == "active":
            console.print("[green]Status: ACTIVE[/green]")

            # Create info table
            table = Table(show_header=False, box=None)
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="white")

            table.add_row("Operation", result.get("operation_id", "unknown"))
            table.add_row("Phase", result.get("phase", "unknown").upper())
            if result.get("strategy_name"):
                table.add_row("Strategy", result["strategy_name"])
            if result.get("started_at"):
                table.add_row("Started", result["started_at"])

            console.print(table)
        else:
            console.print("[dim]Status: IDLE[/dim]")

            last_cycle = result.get("last_cycle")
            if last_cycle:
                console.print("\n[bold]Last Cycle[/bold]")

                table = Table(show_header=False, box=None)
                table.add_column("Property", style="cyan")
                table.add_column("Value", style="white")

                table.add_row("Operation", last_cycle.get("operation_id", "unknown"))
                table.add_row("Outcome", last_cycle.get("outcome", "unknown").upper())
                if last_cycle.get("strategy_name"):
                    table.add_row("Strategy", last_cycle["strategy_name"])
                if last_cycle.get("completed_at"):
                    table.add_row("Completed", last_cycle["completed_at"])

                console.print(table)
            else:
                console.print("[dim]No previous cycles.[/dim]")
                console.print()
                console.print(
                    "Use [cyan]ktrdr agent trigger[/cyan] to start a new research cycle."
                )

    except AsyncCLIClientError as e:
        logger.error(f"API error: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to get agent status: {e}")
        raise


@agent_app.command("trigger")
@trace_cli_command("agent_trigger")
def trigger_agent(
    model: str = typer.Option(
        None,
        "--model",
        "-m",
        help="Model to use: 'opus', 'sonnet', 'haiku', or full model ID",
    ),
    monitor: bool = typer.Option(
        False,
        "--monitor",
        "--follow",
        "-f",
        help="Monitor progress with real-time display until completion",
    ),
    bypass_gates: bool = typer.Option(
        False,
        "--bypass",
        "-b",
        help="Bypass quality gates (for testing)",
    ),
):
    """Start a new research cycle.

    Triggers the agent to begin a new research cycle. If a cycle
    is already running, the command will fail with a conflict message.

    Optionally specify a model to use for this cycle:
    - opus: Claude Opus (default, highest quality)
    - sonnet: Claude Sonnet (balanced)
    - haiku: Claude Haiku (fastest, cheapest)

    Use --monitor to wait and show progress:
        ktrdr agent trigger --monitor
        ktrdr agent trigger -m haiku -f

    Use --bypass to skip quality gates (for testing):
        ktrdr agent trigger -m haiku -f -b

    Examples:
        ktrdr agent trigger
        ktrdr agent trigger --model haiku
        ktrdr agent trigger -m sonnet
        ktrdr agent trigger --monitor
        ktrdr agent trigger -m haiku -f -b
    """
    try:
        asyncio.run(
            _trigger_agent_async(
                model=model, monitor=monitor, bypass_gates=bypass_gates
            )
        )
    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


async def _trigger_agent_async(
    model: str | None = None, monitor: bool = False, bypass_gates: bool = False
):
    """Async implementation of trigger command using API."""
    try:
        # Build request body with optional parameters
        json_data: dict | None = None
        if model or bypass_gates:
            json_data = {}
            if model:
                json_data["model"] = model
            if bypass_gates:
                json_data["bypass_gates"] = True

        async with AsyncCLIClient() as client:
            result = await client._make_request(
                "POST", "/agent/trigger", json_data=json_data
            )

        if result.get("triggered"):
            operation_id = result["operation_id"]

            if monitor:
                # Enter monitoring mode
                console.print("\n[green]Research cycle started![/green]")
                console.print(f"  Operation ID: {operation_id}")
                if result.get("model"):
                    console.print(f"  Model: {result['model']}")
                if bypass_gates:
                    console.print("  [yellow]Gates: BYPASSED[/yellow]")
                console.print()
                await _monitor_agent_cycle(operation_id)
            else:
                # Fire-and-forget mode
                console.print("\n[green]Research cycle started![/green]")
                console.print(f"  Operation ID: {operation_id}")
                if result.get("model"):
                    console.print(f"  Model: {result['model']}")
                if bypass_gates:
                    console.print("  [yellow]Gates: BYPASSED[/yellow]")
                console.print()
                console.print(
                    "Use [cyan]ktrdr agent status[/cyan] to monitor progress."
                )
        else:
            reason = result.get("reason", "unknown")
            message = result.get("message", f"Could not start cycle: {reason}")

            if reason == "active_cycle_exists":
                console.print("\n[yellow]Cannot trigger:[/yellow] Active cycle exists")
                if result.get("operation_id"):
                    console.print(f"  Operation ID: {result['operation_id']}")
                console.print()
                console.print("Wait for the current cycle to complete, or cancel it:")
                console.print(
                    f"  [cyan]ktrdr operations cancel {result.get('operation_id', '<op_id>')}[/cyan]"
                )
            else:
                console.print(f"\n[yellow]Could not trigger:[/yellow] {message}")

    except AsyncCLIClientError as e:
        logger.error(f"API error: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to trigger agent: {e}")
        raise


async def _monitor_agent_cycle(operation_id: str) -> dict:
    """
    Poll agent operation with nested child progress display until completion.

    Handles Ctrl+C by sending DELETE /operations/{id}.
    Shows nested progress bar for training/backtest child operations.
    Includes retry logic with exponential backoff for connection errors.
    Returns final operation data.
    """
    import logging

    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
    )

    # Suppress httpx logs during monitoring to avoid breaking Rich progress bar
    httpx_logger = logging.getLogger("httpx")
    original_httpx_level = httpx_logger.level
    httpx_logger.setLevel(logging.WARNING)

    cancelled = False
    loop = asyncio.get_running_loop()

    def signal_handler():
        nonlocal cancelled
        cancelled = True

    # Setup signal handler for Ctrl+C
    try:
        loop.add_signal_handler(signal.SIGINT, signal_handler)
        signal_handler_registered = True
    except Exception:
        signal_handler_registered = False

    # Retry configuration
    retry_delay = 1.0
    max_retry_delay = 5.0

    # Track last known child state for cancellation summary
    last_child_step: str | None = None

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
                    try:
                        # Poll parent operation
                        result = await client._make_request(
                            "GET", f"/operations/{operation_id}"
                        )
                        # Reset retry delay on success
                        retry_delay = 1.0

                        op_data = result.get("data", {})
                        status = op_data.get("status")

                        # Update parent progress display
                        prog = op_data.get("progress", {})
                        pct = prog.get("percentage", 0)
                        step = prog.get("current_step", "Working...")
                        progress.update(
                            parent_task,
                            completed=pct,
                            description=f"[bold blue]Research Cycle[/] {step}",
                        )

                        # Check for child operation based on current phase
                        params = op_data.get("metadata", {}).get("parameters", {})
                        phase = params.get("phase", "")
                        # Only show child progress for phases with active child operations
                        if phase == "training":
                            child_op_id = params.get("training_op_id")
                        elif phase == "backtesting":
                            child_op_id = params.get("backtest_op_id")
                        else:
                            child_op_id = None  # No child for design/assessment phases

                        # Handle child task lifecycle
                        if child_op_id and child_op_id != current_child_op_id:
                            # New child operation - add/replace task
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
                        if child_op_id and child_task is not None:
                            try:
                                child_result = await client._make_request(
                                    "GET", f"/operations/{child_op_id}"
                                )
                                child_data = child_result.get("data", {})
                                child_prog = child_data.get("progress", {})
                                child_pct = child_prog.get("percentage", 0)
                                child_step = child_prog.get(
                                    "current_step", "Working..."
                                )
                                last_child_step = (
                                    child_step  # Track for cancellation summary
                                )
                                progress.update(
                                    child_task,
                                    completed=child_pct,
                                    description=f"   └─ {child_step}",
                                )
                            except Exception:
                                # Child may not exist yet or may have finished
                                pass

                        # Check for terminal state
                        if status in ("completed", "failed", "cancelled"):
                            break

                    except AsyncCLIClientError as e:
                        # Check for 404 (operation not found - lost after restart)
                        if "404" in e.error_code or (
                            e.details and e.details.get("status_code") == 404
                        ):
                            console.print(
                                "\n[yellow]Operation not found — may have been lost due to restart[/yellow]"
                            )
                            return {"status": "lost"}

                        # Connection error - retry with backoff
                        if "Connection" in e.error_code or "Timeout" in e.error_code:
                            progress.update(
                                parent_task,
                                description="[bold blue]Research Cycle[/] [yellow]⚠ Connection lost, retrying...[/]",
                            )
                            await asyncio.sleep(retry_delay)
                            retry_delay = min(retry_delay * 2, max_retry_delay)
                            continue

                        # Other errors - re-raise
                        raise

                    await asyncio.sleep(0.5)

                if cancelled:
                    # Send cancellation request
                    console.print("\n[yellow]Cancelling research cycle...[/yellow]")
                    try:
                        await client._make_request(
                            "DELETE", f"/operations/{operation_id}"
                        )
                    except Exception:
                        pass  # Continue even if cancel fails
                    # Wait briefly for cancellation to process
                    await asyncio.sleep(1)
                    try:
                        result = await client._make_request(
                            "GET", f"/operations/{operation_id}"
                        )
                        op_data = result.get("data", {})
                    except Exception:
                        # If we can't get final status, use what we had
                        pass

            # Show final status (outside Progress context)
            _show_completion_summary(op_data, child_state=last_child_step)
            return op_data

    finally:
        # Restore httpx log level
        httpx_logger.setLevel(original_httpx_level)

        # Always cleanup signal handler
        if signal_handler_registered:
            try:
                loop.remove_signal_handler(signal.SIGINT)
            except Exception:
                pass


def _show_completion_summary(op_data: dict, child_state: str | None = None) -> None:
    """Display completion or cancellation summary.

    Args:
        op_data: The operation data from the API
        child_state: Optional last known child operation state (e.g., "Epoch 67/100")
    """
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
            console.print(
                f"   Sharpe: {sharpe} | Win Rate: {win_rate} | Max DD: {max_dd}"
            )
    elif status == "cancelled":
        console.print("\n[yellow]⚠ Research cycle cancelled[/yellow]")
        phase = (
            op_data.get("metadata", {}).get("parameters", {}).get("phase", "unknown")
        )
        console.print(f"   Phase: {phase}")
        if child_state:
            console.print(f"   Progress: {child_state}")
    elif status == "failed":
        console.print("\n[red]✗ Research cycle failed[/red]")
        error = op_data.get("error", op_data.get("error_message", "Unknown error"))
        console.print(f"   Error: {error}")
    elif status == "lost":
        # Already printed message in the monitor function
        pass


@agent_app.command("cancel")
@trace_cli_command("agent_cancel")
def cancel_agent():
    """Cancel the active research cycle.

    Cancels the currently running research cycle if one exists.
    Both the parent operation and any active child operation
    will be cancelled.

    Examples:
        ktrdr agent cancel
    """
    try:
        asyncio.run(_cancel_agent_async())
    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


async def _cancel_agent_async():
    """Async implementation of cancel command using API."""
    try:
        async with AsyncCLIClient() as client:
            result = await client._make_request("DELETE", "/agent/cancel")

        if result.get("success"):
            console.print("\n[green]Research cycle cancelled![/green]")
            console.print(f"  Operation: {result['operation_id']}")
            if result.get("child_cancelled"):
                console.print(f"  Child operation: {result['child_cancelled']}")
            console.print()
        else:
            reason = result.get("reason", "unknown")
            message = result.get("message", f"Could not cancel: {reason}")

            if reason == "no_active_cycle":
                console.print("\n[dim]No active research cycle to cancel.[/dim]")
                console.print()
                console.print(
                    "Use [cyan]ktrdr agent trigger[/cyan] to start a new research cycle."
                )
            else:
                console.print(f"\n[yellow]Could not cancel:[/yellow] {message}")

    except AsyncCLIClientError as e:
        # Handle 404 "no active cycle" gracefully
        if "no_active_cycle" in str(e).lower() or "no active" in str(e).lower():
            console.print("\n[dim]No active research cycle to cancel.[/dim]")
            console.print()
            console.print(
                "Use [cyan]ktrdr agent trigger[/cyan] to start a new research cycle."
            )
        else:
            logger.error(f"API error: {e}")
            raise
    except Exception as e:
        logger.error(f"Failed to cancel agent: {e}")
        raise


@agent_app.command("budget")
@trace_cli_command("agent_budget")
def show_budget():
    """Show current agent budget status.

    Displays daily limit, today's spend, remaining budget,
    and estimated number of cycles affordable.

    Examples:
        ktrdr agent budget
    """
    try:
        asyncio.run(_show_budget_async())
    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


async def _show_budget_async():
    """Async implementation of budget command using API."""
    try:
        async with AsyncCLIClient() as client:
            result = await client._make_request("GET", "/agent/budget")

        console.print("\n[bold]Agent Budget Status[/bold]")
        console.print()

        # Create info table
        table = Table(show_header=False, box=None)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Date", result.get("date", "unknown"))
        table.add_row("Daily Limit", f"${result.get('daily_limit', 0):.2f}")
        table.add_row("Today's Spend", f"${result.get('today_spend', 0):.2f}")

        remaining = result.get("remaining", 0)
        if remaining < 0.50:
            remaining_str = f"[red]${remaining:.2f}[/red]"
        elif remaining < 1.50:
            remaining_str = f"[yellow]${remaining:.2f}[/yellow]"
        else:
            remaining_str = f"[green]${remaining:.2f}[/green]"
        table.add_row("Remaining", remaining_str)

        cycles = result.get("cycles_affordable", 0)
        if cycles == 0:
            cycles_str = "[red]0 cycles[/red]"
        elif cycles < 5:
            cycles_str = f"[yellow]~{cycles} cycles[/yellow]"
        else:
            cycles_str = f"[green]~{cycles} cycles[/green]"
        table.add_row("Affordable", cycles_str)

        console.print(table)
        console.print()

    except AsyncCLIClientError as e:
        logger.error(f"API error: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to get budget status: {e}")
        raise
