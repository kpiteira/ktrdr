"""
Dummy CLI commands using unified AsyncOperationExecutor pattern.

This module demonstrates the unified async operations pattern with
AsyncOperationExecutor and DummyOperationAdapter.
"""

import asyncio
import sys

import typer
from rich.console import Console

from ktrdr.cli.api_client import check_api_connection
from ktrdr.cli.error_handler import (
    display_ib_connection_required_message,
    handle_cli_error,
)
from ktrdr.cli.operation_adapters import DummyOperationAdapter
from ktrdr.cli.operation_executor import AsyncOperationExecutor
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
    - 🎯 Perfect progress reporting via unified pattern
    - 🛑 Instant cancellation with Ctrl+C
    - 🚀 AsyncOperationExecutor handles ALL complexity
    - ✨ Same pattern as all KTRDR async operations

    Simple: no parameters, just runs 200s (100 iterations)
    """
    try:
        # Run async operation
        asyncio.run(_run_dummy_async(verbose, quiet, show_progress))

    except KeyboardInterrupt:
        if not quiet:
            error_console.print("\n🛑 Cancelled by user")
        sys.exit(1)
    except Exception as e:
        handle_cli_error(e, verbose, quiet)
        sys.exit(1)


async def _run_dummy_async(verbose: bool, quiet: bool, show_progress: bool):
    """Async implementation using unified executor pattern."""
    # Reduce HTTP logging noise unless verbose mode
    if not verbose:
        import logging

        httpx_logger = logging.getLogger("httpx")
        original_level = httpx_logger.level
        httpx_logger.setLevel(logging.WARNING)

    try:
        # Check API connection
        if not await check_api_connection():
            display_ib_connection_required_message()
            sys.exit(1)

        if not quiet:
            console.print("🚀 [bold]Running awesome dummy task![/bold]")
            console.print("📋 Duration: 200s (100 iterations of 2s each)")
            console.print()

        # Create adapter for dummy operation
        adapter = DummyOperationAdapter(duration=200, iterations=100)

        # Create executor for unified async operation handling
        executor = AsyncOperationExecutor()

        # Optional: Define custom progress message formatter
        def format_progress(operation_data: dict) -> str:
            """Format progress message for dummy operation."""
            status = operation_data.get("status", "unknown")
            progress_info = operation_data.get("progress", {})
            current_step = progress_info.get("current_step", "Working...")
            return f"Status: {status} - {current_step}"

        # Execute operation - executor handles progress bar
        success = await executor.execute_operation(
            adapter=adapter,
            console=console,
            progress_callback=format_progress if show_progress else None,
            show_progress=show_progress and not quiet,
        )

        # Handle unsuccessful completion
        if not success and not quiet:
            console.print(
                "[yellow]⚠️  Dummy task did not complete successfully[/yellow]"
            )

    except Exception:
        if not verbose:
            httpx_logger.setLevel(original_level)
        raise
    finally:
        # Restore HTTP logging level
        if not verbose:
            httpx_logger.setLevel(original_level)
