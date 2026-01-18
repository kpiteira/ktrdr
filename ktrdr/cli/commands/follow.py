"""Follow command implementation.

Implements the `ktrdr follow <op-id>` command that attaches to a running
operation and shows progress until completion.

PERFORMANCE NOTE: Heavy imports (AsyncCLIClient, Console, Progress) are
deferred inside the function body to keep CLI startup fast.
"""

import typer

from ktrdr.cli.telemetry import trace_cli_command


@trace_cli_command("follow")
def follow(
    ctx: typer.Context,
    operation_id: str = typer.Argument(..., help="Operation ID to follow"),
) -> None:
    """Follow a running operation until completion.

    Attaches to an existing operation and displays progress until it
    reaches a terminal state (completed, failed, or cancelled).

    Note: Ctrl+C detaches from the operation (does not cancel it)
    since you did not start the operation.

    Examples:
        ktrdr follow op_abc123
    """
    # Lazy imports for fast CLI startup
    import asyncio

    from rich.console import Console
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
    )

    from ktrdr.cli.client import AsyncCLIClient
    from ktrdr.cli.output import print_error
    from ktrdr.cli.state import CLIState

    state: CLIState = ctx.obj
    console = Console()

    async def _follow_operation() -> None:
        """Poll operation and display progress until terminal state."""
        async with AsyncCLIClient() as client:
            with Progress(
                SpinnerColumn(),
                TextColumn("{task.description}"),
                BarColumn(),
                TextColumn("{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task_id = progress.add_task("Following...", total=100)

                # Initialize final_status before loop (will be set when terminal state reached)
                final_status: dict = {}

                # Poll until terminal state
                while True:
                    result = await client.get(f"/operations/{operation_id}")
                    op_data = result.get("data", {})
                    status = op_data.get("status")
                    progress_pct = op_data.get("progress", {}).get("percentage", 0)
                    progress.update(task_id, completed=progress_pct)

                    if status in ("completed", "failed", "cancelled"):
                        final_status = op_data
                        break
                    await asyncio.sleep(0.3)

        # Display final status
        status = final_status.get("status")
        if status == "completed":
            console.print("[green]Operation completed successfully![/green]")
        elif status == "failed":
            error_msg = final_status.get("error_message", "Unknown error")
            console.print(f"[red]Operation failed: {error_msg}[/red]")
        elif status == "cancelled":
            console.print("[yellow]Operation was cancelled[/yellow]")

    try:
        asyncio.run(_follow_operation())
    except KeyboardInterrupt:
        # Ctrl+C detaches (not cancels) since user didn't start the operation
        console.print("\n[yellow]Detached from operation[/yellow]")
        console.print(f"  Operation continues running: {operation_id}")
        console.print(f"  Re-attach: ktrdr follow {operation_id}")
        raise typer.Exit(0) from None
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1) from None
