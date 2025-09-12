"""
Dummy CLI commands using real data loading progress pattern.

This module demonstrates the beautiful CLI UX using the actual existing
progress system from data_commands.py - not fictional AsyncOperationManager.
"""

import asyncio
import sys

import typer
from rich.console import Console

from ktrdr.async_infrastructure.cancellation import setup_cli_cancellation_handler
from ktrdr.cli.api_client import check_api_connection, get_api_client
from ktrdr.cli.error_handler import (
    display_ib_connection_required_message,
    handle_cli_error,
)
from ktrdr.cli.progress_display_enhanced import create_enhanced_progress_callback
from ktrdr.errors import DataError
from ktrdr.logging import get_logger

# Setup logging and console
logger = get_logger(__name__)
console = Console()
error_console = Console(stderr=True)

# Create the CLI app for dummy commands
dummy_app = typer.Typer(
    name="dummy",
    help="Dummy service commands with beautiful UX",
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
    - 🎯 Perfect progress reporting - exactly like data loading
    - 🛑 Instant cancellation with Ctrl+C
    - 🚀 ServiceOrchestrator handles ALL complexity
    - ✨ Same beautiful UX as all KTRDR operations

    Simple: no parameters, just runs 200s (100 iterations)
    """
    # Setup unified CLI cancellation handler (same as data loading)
    setup_cli_cancellation_handler()

    try:
        # Run async operation with proper signal handling (same pattern as data loading)
        asyncio.run(_run_dummy_async(verbose, quiet, show_progress))

    except KeyboardInterrupt:
        if not quiet:
            error_console.print("\n🛑 Cancelled by user")
        sys.exit(1)
    except Exception as e:
        handle_cli_error(e, verbose, quiet)
        sys.exit(1)


async def _run_dummy_async(verbose: bool, quiet: bool, show_progress: bool):
    """Async implementation using real data loading pattern."""
    # Reduce HTTP logging noise unless verbose mode (same as data loading)
    if not verbose:
        import logging

        httpx_logger = logging.getLogger("httpx")
        original_level = httpx_logger.level
        httpx_logger.setLevel(logging.WARNING)

    try:
        # Check API connection (same as data loading)
        if not await check_api_connection():
            display_ib_connection_required_message()
            sys.exit(1)

        api_client = get_api_client()

        if not quiet:
            console.print("🚀 [bold]Running awesome dummy task![/bold]")
            console.print("📋 Duration: 200s (100 iterations of 2s each)")
            console.print()

        # Set up async signal handling (same as data loading)
        import signal

        cancelled = False
        operation_id = None
        loop = asyncio.get_running_loop()

        def signal_handler():
            """Handle Ctrl+C for graceful cancellation."""
            nonlocal cancelled
            cancelled = True
            console.print(
                "\n[yellow]🛑 Cancellation requested... stopping operation[/yellow]"
            )

        # Register signal handler with the event loop
        loop.add_signal_handler(signal.SIGINT, signal_handler)

        try:
            # Start async operation (need to add this to api_client)
            response = await api_client.start_dummy_task()

            # Get operation ID from response (same pattern as data loading)
            if response.get("success") and response.get("data", {}).get("operation_id"):
                operation_id = response["data"]["operation_id"]
                if not quiet:
                    console.print(f"⚡ Started operation: {operation_id}")
            else:
                # Handle sync fallback if needed
                if not quiet:
                    console.print("❌ Failed to start dummy operation")
                return

            # Monitor operation progress with enhanced display (REAL system!)
            if show_progress and not quiet:
                from datetime import datetime

                from ktrdr.async_infrastructure.progress import GenericProgressState

                # Use the REAL enhanced progress display system
                enhanced_callback, display = create_enhanced_progress_callback(
                    console=console, show_details=True
                )

                operation_started = False

                # Poll operation status with enhanced display (same as data loading)
                while True:
                    try:
                        # Check for cancellation and send cancel request immediately
                        if cancelled:
                            console.print(
                                "[yellow]🛑 Sending cancellation to server...[/yellow]"
                            )
                            try:
                                cancel_response = await api_client.cancel_operation(
                                    operation_id=operation_id,
                                    reason="User requested cancellation via CLI",
                                )
                                if cancel_response.get("success"):
                                    console.print(
                                        "✅ [yellow]Cancellation sent successfully[/yellow]"
                                    )
                                else:
                                    console.print(
                                        f"[red]Cancel failed: {cancel_response}[/red]"
                                    )
                            except Exception as e:
                                console.print(
                                    f"[red]Cancel request failed: {str(e)}[/red]"
                                )
                            break  # Exit the polling loop

                        status_response = await api_client.get_operation_status(
                            operation_id
                        )
                        operation_data = status_response.get("data", {})

                        status = operation_data.get("status")
                        progress_info = operation_data.get("progress", {})
                        progress_percentage = progress_info.get("percentage", 0)
                        current_step = progress_info.get("current_step", "Working...")

                        # Create GenericProgressState for enhanced display (same as data loading)
                        progress_state = GenericProgressState(
                            operation_id=operation_id,
                            current_step=progress_info.get("steps_completed", 0),
                            total_steps=progress_info.get("steps_total", 100),
                            message=current_step,
                            percentage=progress_percentage,
                            start_time=datetime.now(),  # Approximate
                            items_processed=progress_info.get("items_processed", 0),
                            total_items=progress_info.get("items_total", None),
                            step_current=progress_info.get("steps_completed", 0),
                            step_total=progress_info.get("steps_total", 100),
                        )

                        # Start operation on first callback
                        if not operation_started:
                            display.start_operation(
                                operation_name="dummy_task",
                                total_steps=progress_state.total_steps,
                                context={
                                    "type": "dummy",
                                    "description": "Awesome demo task",
                                },
                            )
                            operation_started = True

                        # Update enhanced progress display
                        display.update_progress(progress_state)

                        # Check if operation completed
                        if status in ["completed", "failed", "cancelled"]:
                            display.complete_operation(success=(status == "completed"))
                            break

                        # Poll every 300ms for responsive updates (same as data loading)
                        await asyncio.sleep(0.3)

                    except Exception as e:
                        if not quiet:
                            console.print(
                                f"[yellow]Warning: Failed to get operation status: {str(e)}[/yellow]"
                            )
                        # Continue polling instead of breaking
                        await asyncio.sleep(1.0)
                        continue
            else:
                # Simple polling without progress display (same as data loading)
                while True:
                    try:
                        # Check for cancellation and send cancel request immediately
                        if cancelled:
                            if not quiet:
                                console.print("🛑 Sending cancellation to server...")
                            try:
                                cancel_response = await api_client.cancel_operation(
                                    operation_id=operation_id,
                                    reason="User requested cancellation via CLI",
                                )
                                if cancel_response.get("success"):
                                    if not quiet:
                                        console.print(
                                            "✅ Cancellation sent successfully"
                                        )
                            except Exception as e:
                                if not quiet:
                                    console.print(f"Cancel request failed: {str(e)}")
                            break  # Exit the polling loop

                        status_response = await api_client.get_operation_status(
                            operation_id
                        )
                        operation_data = status_response.get("data", {})
                        status = operation_data.get("status")

                        # Check if operation completed
                        if status in ["completed", "failed", "cancelled"]:
                            break

                        await asyncio.sleep(2.0)

                    except Exception as e:
                        if not quiet:
                            console.print(
                                f"[yellow]Warning: Failed to get operation status: {str(e)}[/yellow]"
                            )
                        await asyncio.sleep(2.0)
                        continue

            # If we reach here and cancelled is True, the operation was cancelled
            if cancelled:
                if not quiet:
                    console.print("🛑 [yellow]Operation cancelled by user[/yellow]")
                return

            # Get final operation status (same as data loading)
            try:
                final_response = await api_client.get_operation_status(operation_id)

                if final_response is None:
                    if not quiet:
                        console.print(
                            "[red]❌ No response from API when getting operation status[/red]"
                        )
                    return

                operation_data = final_response.get("data", {})
                result_summary = operation_data.get("result_summary", {})

                # Beautiful result reporting (same style as data loading)
                if result_summary and result_summary.get("status") == "success":
                    iterations = result_summary.get("iterations_completed", 0)
                    console.print(f"✅ Completed {iterations} iterations")
                elif result_summary and result_summary.get("status") == "cancelled":
                    iterations = result_summary.get("iterations_completed", 0)
                    console.print(f"🛑 Cancelled after {iterations} iterations")
                else:
                    console.print("❌ Task failed")

            except Exception as e:
                if not quiet:
                    console.print(
                        f"[red]❌ Error getting final operation status: {str(e)}[/red]"
                    )
                return

        finally:
            # Remove signal handler to avoid issues with event loop
            try:
                loop.remove_signal_handler(signal.SIGINT)
            except (ValueError, NotImplementedError):
                # Signal handling not supported on this platform, ignore
                pass

    except KeyboardInterrupt:
        if not quiet:
            console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        if not verbose:
            httpx_logger.setLevel(original_level)
        raise DataError(
            message="Failed to run dummy task",
            error_code="CLI-DummyTaskError",
            details={"error": str(e)},
        ) from e
    finally:
        # Restore HTTP logging level
        if not verbose:
            httpx_logger.setLevel(original_level)
