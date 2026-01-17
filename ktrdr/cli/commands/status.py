"""Status command implementation.

Implements the `ktrdr status [op-id]` command that shows either a system
dashboard (no argument) or specific operation details (with operation ID).
"""

import asyncio
import json
from typing import Optional

import typer
from rich.console import Console

from ktrdr.cli.client import AsyncCLIClient
from ktrdr.cli.output import print_error
from ktrdr.cli.state import CLIState
from ktrdr.cli.telemetry import trace_cli_command

console = Console()


@trace_cli_command("status")
def status(
    ctx: typer.Context,
    operation_id: Optional[str] = typer.Argument(None, help="Operation ID (optional)"),
) -> None:
    """Show system status or specific operation status.

    Without an operation ID, shows a system dashboard with counts of
    running/completed operations and available workers.

    With an operation ID, shows detailed status for that specific operation.

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
        raise typer.Exit(1) from None


async def _show_dashboard(state: CLIState) -> None:
    """Show system dashboard with operations and workers summary."""
    async with AsyncCLIClient() as client:
        # Fetch operations
        ops_result = await client.get("/operations")
        ops = ops_result.get("data", [])

        running = len([o for o in ops if o.get("status") == "running"])
        completed = len([o for o in ops if o.get("status") == "completed"])

        # Fetch workers
        workers_result = await client.get("/workers")
        workers = workers_result.get("data", {}).get("workers", [])

    if state.json_mode:
        print(
            json.dumps(
                {
                    "operations": {"running": running, "completed": completed},
                    "workers": len(workers),
                }
            )
        )
    else:
        console.print(f"Operations: {running} running, {completed} completed")
        console.print(f"Workers: {len(workers)} available")


async def _show_operation_status(state: CLIState, operation_id: str) -> None:
    """Show specific operation status."""
    async with AsyncCLIClient() as client:
        result = await client.get(f"/operations/{operation_id}")

    op = result.get("data", {})

    if state.json_mode:
        print(json.dumps(op))
    else:
        console.print(f"Operation: [cyan]{op.get('operation_id')}[/cyan]")
        console.print(f"Type: {op.get('operation_type')}")
        console.print(f"Status: {op.get('status')}")
        progress = op.get("progress", {})
        if progress.get("percentage"):
            console.print(f"Progress: {progress['percentage']}%")
