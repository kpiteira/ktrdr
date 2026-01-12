"""
Dummy CLI commands using unified AsyncCLIClient pattern.

This module demonstrates the unified async operations pattern with
AsyncCLIClient.execute_operation() and DummyOperationAdapter.
"""

import asyncio
import sys

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from ktrdr.cli.client import AsyncCLIClient, CLIClientError
from ktrdr.cli.error_handler import (
    display_ib_connection_required_message,
    handle_cli_error,
)
from ktrdr.cli.operation_adapters import DummyOperationAdapter
from ktrdr.logging import get_logger

# Setup logging and console
logger = get_logger(__name__)
console = Console()
error_console = Console(stderr=True)

# Create the CLI app for dummy commands
dummy_app = typer.Typer(
    name="dummy",
    help="Dummy service commands with unified operations pattern",
    no_args_is_help=True,
)


@dummy_app.command("dummy")
def dummy_task(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal output"),
    show_progress: bool = typer.Option(
        True, "--progress/--no-progress", help="Show progress"
    ),
):
    """
    Run the most awesome dummy task ever!

    Features:
    - Perfect progress reporting via unified pattern
    - Instant cancellation with Ctrl+C
    - AsyncCLIClient handles ALL complexity
    - Same pattern as all KTRDR async operations

    Simple: no parameters, just runs 200s (100 iterations)
    """
    try:
        # Run async operation
        asyncio.run(_run_dummy_async(verbose, quiet, show_progress))

    except KeyboardInterrupt:
        if not quiet:
            error_console.print("\n[red]Cancelled by user[/red]")
        sys.exit(1)
    except Exception as e:
        handle_cli_error(e, verbose, quiet)
        sys.exit(1)


async def _run_dummy_async(verbose: bool, quiet: bool, show_progress: bool):
    """Async implementation using AsyncCLIClient.execute_operation() pattern."""
    # Reduce HTTP logging noise unless verbose mode
    if not verbose:
        import logging

        httpx_logger = logging.getLogger("httpx")
        original_level = httpx_logger.level
        httpx_logger.setLevel(logging.WARNING)

    try:
        # Use AsyncCLIClient for connection reuse and performance
        async with AsyncCLIClient() as cli:
            # Check API connection
            if not await cli.health_check():
                display_ib_connection_required_message()
                sys.exit(1)

            if not quiet:
                console.print("[bold]Running awesome dummy task![/bold]")
                console.print("Duration: 200s (100 iterations of 2s each)")
                console.print()

            # Create adapter for dummy operation
            adapter = DummyOperationAdapter(duration=200, iterations=100)

            # Set up progress display using Rich Progress
            progress_bar = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=console,
            )
            task_id = None

            def on_progress(percentage: int, message: str) -> None:
                """Progress callback for Rich progress display."""
                nonlocal task_id
                if task_id is not None:
                    progress_bar.update(
                        task_id, completed=percentage, description=message
                    )

            # Execute operation with progress display
            try:
                if show_progress and not quiet:
                    with progress_bar:
                        task_id = progress_bar.add_task("Running dummy...", total=100)
                        result = await cli.execute_operation(
                            adapter,
                            on_progress=on_progress,
                            poll_interval=0.3,
                        )
                else:
                    result = await cli.execute_operation(
                        adapter,
                        poll_interval=0.3,
                    )
            except CLIClientError as e:
                if not quiet:
                    console.print(f"[red]Failed to start dummy operation: {e}[/red]")
                sys.exit(1)

            # Handle result based on final status
            status = result.get("status", "unknown")

            if status == "completed":
                if not quiet:
                    console.print("[green]Dummy task completed successfully![/green]")

            elif status == "failed":
                if not quiet:
                    error_msg = result.get(
                        "error_message", result.get("error", "Unknown error")
                    )
                    console.print(f"[red]Dummy task failed: {error_msg}[/red]")

            elif status == "cancelled":
                if not quiet:
                    console.print("[yellow]Dummy task cancelled[/yellow]")

            else:
                if not quiet:
                    console.print(
                        f"[yellow]Dummy task ended with status: {status}[/yellow]"
                    )

    except Exception:
        if not verbose:
            httpx_logger.setLevel(original_level)
        raise
    finally:
        # Restore HTTP logging level
        if not verbose:
            httpx_logger.setLevel(original_level)
