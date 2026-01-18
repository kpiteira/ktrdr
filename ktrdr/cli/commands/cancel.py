"""Cancel command implementation.

Implements the `ktrdr cancel` command that cancels a running operation.
Replaces the old `ktrdr operations cancel` command with a simpler path.

Preserves behavior from operations_commands.py including reason/force options
and graceful handling of already-completed operations.

PERFORMANCE NOTE: Heavy imports (AsyncCLIClient, Console) are deferred inside
the function body to keep CLI startup fast.
"""

from typing import Optional

import typer

from ktrdr.cli.telemetry import trace_cli_command


@trace_cli_command("cancel")
def cancel(
    ctx: typer.Context,
    operation_id: str = typer.Argument(..., help="Operation ID to cancel"),
    reason: Optional[str] = typer.Option(
        None,
        "--reason",
        "-r",
        help="Reason for cancellation",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force cancellation even if operation is in critical section",
    ),
) -> None:
    """Cancel a running operation.

    Attempts to gracefully cancel an operation. Use --force for stuck operations
    that are not responding to normal cancellation.

    Examples:
        ktrdr cancel op_abc123

        ktrdr cancel op_abc123 --reason "User requested stop"

        ktrdr cancel op_abc123 --force
    """
    # Lazy imports for fast CLI startup
    import asyncio
    import json

    from rich.console import Console

    from ktrdr.cli.client import AsyncCLIClient
    from ktrdr.cli.output import print_error
    from ktrdr.cli.state import CLIState

    state: CLIState = ctx.obj
    console = Console()

    async def _cancel_operation() -> None:
        """Cancel operation via DELETE request."""
        # Build payload only if we have options to send
        payload: Optional[dict] = None
        if reason is not None or force:
            payload = {}
            if reason is not None:
                payload["reason"] = reason
            if force:
                payload["force"] = True

        async with AsyncCLIClient() as client:
            result = await client.delete(f"/operations/{operation_id}", json=payload)

        # Extract data from response
        data = result.get("data", {})
        op_id = data.get("operation_id", operation_id)
        cancelled_at = data.get("cancelled_at")
        cancellation_reason = data.get("cancellation_reason")

        if state.json_mode:
            print(json.dumps(data))
            return

        # Human-friendly output
        console.print(f"[yellow]Cancelled operation: {op_id}[/yellow]")

        if cancelled_at:
            console.print(f"  Cancelled at: {cancelled_at}")

        if cancellation_reason:
            console.print(f"  Reason: {cancellation_reason}")

    try:
        asyncio.run(_cancel_operation())
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1) from None
