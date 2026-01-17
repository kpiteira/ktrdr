"""Ops command implementation.

Implements the `ktrdr ops` command that lists all operations in a table format.
Replaces the old `ktrdr operations list` command with a simpler path.

Preserves all behavior from operations_commands.py:list_operations including
checkpoint fetching, all columns, and all filter options.
"""

import asyncio
import json
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ktrdr.cli.client import AsyncCLIClient, CLIClientError
from ktrdr.cli.output import print_error
from ktrdr.cli.state import CLIState
from ktrdr.cli.telemetry import trace_cli_command

console = Console()


def _format_duration(seconds: float) -> str:
    """Format duration in human-readable format.

    Copied from operations_commands.py to preserve behavior.
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}m"
    else:
        return f"{seconds / 3600:.1f}h"


def _format_checkpoint_summary(state: dict) -> str:
    """Format checkpoint state into a brief summary string.

    Copied from operations_commands.py to preserve behavior.

    Args:
        state: Checkpoint state dictionary

    Returns:
        Brief summary like "epoch 29" or "bar 7000"
    """
    # Training checkpoint
    if "epoch" in state:
        return f"epoch {state['epoch']}"

    # Backtesting checkpoint
    if "bar_index" in state:
        return f"bar {state['bar_index']}"

    # Agent checkpoint
    if "step" in state:
        return f"step {state['step']}"

    # Fallback to first numeric key
    for key, value in state.items():
        if isinstance(value, (int, float)) and not key.startswith("_"):
            return f"{key} {value}"

    return "saved"


@trace_cli_command("ops")
def ops(
    ctx: typer.Context,
    status_filter: Optional[str] = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status (running, completed, failed, cancelled)",
    ),
    type_filter: Optional[str] = typer.Option(
        None,
        "--type",
        "-t",
        help="Filter by operation type (training, backtest, etc.)",
    ),
    limit: int = typer.Option(
        50,
        "--limit",
        "-l",
        help="Maximum number of operations to show",
    ),
    active_only: bool = typer.Option(
        False,
        "--active",
        "-a",
        help="Show only active (running/pending) operations",
    ),
    resumable: bool = typer.Option(
        False,
        "--resumable",
        "-r",
        help="Show only operations with checkpoints",
    ),
) -> None:
    """List all operations.

    Shows operations in a table with ID, type, status, progress, checkpoint,
    symbol, and duration. Use filtering options to narrow results.

    Examples:
        ktrdr ops

        ktrdr ops --active

        ktrdr ops --status running

        ktrdr ops --resumable

        ktrdr ops --type training --limit 10

        ktrdr --json ops
    """
    state: CLIState = ctx.obj

    try:
        asyncio.run(
            _list_operations(
                state, status_filter, type_filter, limit, active_only, resumable
            )
        )
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1) from None


async def _list_operations(
    state: CLIState,
    status_filter: Optional[str],
    type_filter: Optional[str],
    limit: int,
    active_only: bool,
    resumable: bool,
) -> None:
    """Fetch and display operations list.

    Preserves behavior from operations_commands.py:list_operations including
    checkpoint fetching for each operation.
    """
    # Build query params
    params: dict[str, str] = {
        "limit": str(limit),
        "offset": "0",
    }
    if status_filter:
        params["status"] = status_filter
    if type_filter:
        params["operation_type"] = type_filter
    if active_only:
        params["active_only"] = "true"

    async with AsyncCLIClient() as client:
        result = await client.get("/operations", params=params)
        operations = result.get("data", [])

        # Fetch checkpoint info for each operation (preserves existing behavior)
        for op in operations:
            try:
                checkpoint_response = await client.get(
                    f"/checkpoints/{op['operation_id']}"
                )
                op["has_checkpoint"] = checkpoint_response.get("success", False)
                if op["has_checkpoint"]:
                    checkpoint_data = checkpoint_response.get("data", {})
                    op["checkpoint_summary"] = _format_checkpoint_summary(
                        checkpoint_data.get("state", {})
                    )
                else:
                    op["checkpoint_summary"] = None
            except CLIClientError:
                # Checkpoint fetch failed - operation is not resumable
                op["has_checkpoint"] = False
                op["checkpoint_summary"] = None
            except Exception:
                # Any other error - treat as no checkpoint
                op["has_checkpoint"] = False
                op["checkpoint_summary"] = None

    # Filter to resumable only if requested
    if resumable:
        operations = [op for op in operations if op.get("has_checkpoint")]

    if state.json_mode:
        print(json.dumps(operations))
        return

    if not operations:
        if resumable:
            console.print("No resumable operations found")
        elif active_only:
            console.print("No active operations found")
        else:
            console.print("No operations found")
        return

    # Create table with all columns from original implementation
    table = Table(title="Operations")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Type", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Progress", style="blue")
    table.add_column("Checkpoint", style="magenta")
    table.add_column("Symbol", style="white")
    table.add_column("Duration", style="dim")

    for op in operations:
        # Format status with colors (same pattern as operations_commands.py)
        status = op.get("status", "unknown")
        status_display = status.upper()
        if status == "running":
            status_display = f"[green]{status_display}[/green]"
        elif status == "completed":
            status_display = f"[bright_green]{status_display}[/bright_green]"
        elif status == "failed":
            status_display = f"[red]{status_display}[/red]"
        elif status == "cancelled":
            status_display = f"[yellow]{status_display}[/yellow]"

        # Format progress
        progress_pct = op.get("progress_percentage", 0)
        # Also check nested progress object
        if not progress_pct:
            progress = op.get("progress", {})
            if isinstance(progress, dict):
                progress_pct = progress.get("percentage", 0)
        progress_display = f"{progress_pct:.0f}%"

        # Format checkpoint
        checkpoint = op.get("checkpoint_summary") or "-"

        # Format duration
        duration = "-"
        if op.get("duration_seconds"):
            duration = _format_duration(op["duration_seconds"])

        # Format symbol
        symbol = op.get("symbol", "-")

        table.add_row(
            op.get("operation_id", ""),
            op.get("operation_type", ""),
            status_display,
            progress_display,
            checkpoint,
            symbol,
            duration,
        )

    console.print(table)
