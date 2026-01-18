"""Agent monitoring helpers for CLI commands.

This module contains helper functions for monitoring agent research cycles,
moved from agent_commands.py during the M5 CLI restructure.
"""

import asyncio
import signal

from rich.console import Console

from ktrdr.cli.client import (
    APIError,
    AsyncCLIClient,
    CLIClientError,
    ConnectionError,
    TimeoutError,
)

console = Console()


async def monitor_agent_cycle(operation_id: str) -> dict:
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
                        result = await client.get(f"/operations/{operation_id}")
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
                                child_result = await client.get(
                                    f"/operations/{child_op_id}"
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

                    except CLIClientError as e:
                        # Check for 404 (operation not found - lost after restart)
                        if isinstance(e, APIError) and e.status_code == 404:
                            console.print(
                                "\n[yellow]Operation not found — may have been lost due to restart[/yellow]"
                            )
                            return {"status": "lost"}

                        # Connection error - retry with backoff
                        if isinstance(e, (ConnectionError, TimeoutError)):
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
                        await client.delete(f"/operations/{operation_id}")
                    except Exception:
                        pass  # Continue even if cancel fails
                    # Wait briefly for cancellation to process
                    await asyncio.sleep(1)
                    try:
                        result = await client.get(f"/operations/{operation_id}")
                        op_data = result.get("data", {})
                    except Exception:
                        # If we can't get final status, use what we had
                        pass

            # Show final status (outside Progress context)
            show_completion_summary(op_data, child_state=last_child_step)
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


def show_completion_summary(op_data: dict, child_state: str | None = None) -> None:
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


# Aliases for backwards compatibility with existing imports
# (Note: These are the old function names from agent_commands.py)
_monitor_agent_cycle = monitor_agent_cycle
_show_completion_summary = show_completion_summary
