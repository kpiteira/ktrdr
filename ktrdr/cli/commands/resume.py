"""Resume command implementation.

Implements the `ktrdr resume` command that resumes operations from checkpoint.
Replaces the old `ktrdr operations resume` command with a simpler path.

Preserves behavior from operations_commands.py including resumed-from info
display (epoch, checkpoint type).

Note: The M2 design doc suggested checkpoint IDs, but the actual backend
uses operation IDs for the resume endpoint. This follows the backend pattern.

PERFORMANCE NOTE: Heavy imports (AsyncCLIClient, Console, Progress) are
deferred inside the function body to keep CLI startup fast.
"""

import typer

from ktrdr.cli.telemetry import trace_cli_command


@trace_cli_command("resume")
def resume(
    ctx: typer.Context,
    operation_id: str = typer.Argument(..., help="Operation ID to resume"),
    follow: bool = typer.Option(
        False,
        "--follow",
        "-f",
        help="Follow progress until completion",
    ),
) -> None:
    """Resume a cancelled or failed operation from checkpoint.

    Operations with checkpoints can be resumed from their last saved state.
    Training operations resume from the last completed epoch.

    Examples:
        ktrdr resume op_training_20241201_123456

        ktrdr resume op_training_20241201_123456 --follow
    """
    # Lazy imports for fast CLI startup
    import asyncio
    import json

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

    async def _follow_resumed_operation(
        op_id: str,
        json_mode: bool,
    ) -> None:
        """Follow resumed operation until completion.

        Args:
            op_id: Operation to follow
            json_mode: Whether to output JSON
        """
        async with AsyncCLIClient() as client:
            if json_mode:
                # In JSON mode, just poll until done and print final state
                while True:
                    result = await client.get(f"/operations/{op_id}")
                    data = result.get("data", {})
                    op_status = data.get("status")

                    if op_status in ("completed", "failed", "cancelled"):
                        print(json.dumps(data))
                        return
                    await asyncio.sleep(0.3)
            else:
                # Human-friendly progress display
                with Progress(
                    SpinnerColumn(),
                    TextColumn("{task.description}"),
                    BarColumn(),
                    TextColumn("{task.percentage:>3.0f}%"),
                    TimeElapsedColumn(),
                    console=console,
                ) as progress:
                    task_id = progress.add_task("Resuming...", total=100)
                    final_status = ""
                    final_data: dict = {}

                    while True:
                        result = await client.get(f"/operations/{op_id}")
                        data = result.get("data", {})
                        op_status = data.get("status")
                        progress_info = data.get("progress", {})
                        progress_pct = progress_info.get("percentage", 0)
                        progress.update(task_id, completed=progress_pct)

                        if op_status in ("completed", "failed", "cancelled"):
                            final_status = op_status
                            final_data = data
                            break
                        await asyncio.sleep(0.3)

                # Final status message
                if final_status == "completed":
                    console.print("[green]Operation completed successfully![/green]")
                elif final_status == "failed":
                    error_msg = final_data.get("error_message", "Unknown error")
                    console.print(f"[red]Operation failed: {error_msg}[/red]")
                elif final_status == "cancelled":
                    console.print("[yellow]Operation was cancelled[/yellow]")

    async def _resume_operation() -> None:
        """Resume operation via POST request."""
        async with AsyncCLIClient() as client:
            result = await client.post(f"/operations/{operation_id}/resume")

        # Check for success
        if not result.get("success"):
            error_msg = result.get("error", "Failed to resume operation")
            raise RuntimeError(error_msg)

        # Extract data from response
        data = result.get("data", {})
        op_id = data.get("operation_id", operation_id)
        status = data.get("status", "running")
        resumed_from = data.get("resumed_from", {})
        epoch = resumed_from.get("epoch", "N/A")
        checkpoint_type = resumed_from.get("checkpoint_type")

        if state.json_mode:
            print(json.dumps(data))
            if follow:
                # In JSON mode with follow, poll until complete and print final state
                await _follow_resumed_operation(op_id, json_mode=True)
            return

        # Human-friendly output
        console.print(f"[green]Resumed operation: {op_id}[/green]")
        console.print(f"  Status: {status}")
        console.print(f"  Resumed from: epoch {epoch}")

        if checkpoint_type:
            console.print(f"  Checkpoint type: {checkpoint_type}")

        if follow:
            console.print()
            await _follow_resumed_operation(op_id, json_mode=False)
        else:
            console.print(f"\nUse 'ktrdr follow {op_id}' to monitor progress")

    try:
        asyncio.run(_resume_operation())
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1) from None
