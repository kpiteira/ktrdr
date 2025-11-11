"""
Operations management commands for the KTRDR CLI.

This module contains CLI commands for managing long-running operations:
- list: List all operations
- status: Get operation status
- cancel: Cancel running operations
- retry: Retry failed operations
"""

import asyncio
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ktrdr.cli.api_client import check_api_connection, get_api_client
from ktrdr.cli.telemetry import trace_cli_command
from ktrdr.config.validation import InputValidator
from ktrdr.errors import DataError, ValidationError
from ktrdr.logging import get_logger

# Setup logging and console
logger = get_logger(__name__)
console = Console()
error_console = Console(stderr=True)

# Create the CLI app for operations commands
operations_app = typer.Typer(
    name="operations",
    help="Operations management commands",
    no_args_is_help=True,
)


@trace_cli_command("operations_list")
@operations_app.command("list")
def list_operations(
    status: Optional[str] = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status (running, completed, failed, cancelled)",
    ),
    operation_type: Optional[str] = typer.Option(
        None,
        "--type",
        "-t",
        help="Filter by operation type (data_load, training, etc.)",
    ),
    limit: int = typer.Option(
        50, "--limit", "-l", help="Maximum number of operations to show"
    ),
    active_only: bool = typer.Option(
        False, "--active", "-a", help="Show only active (running/pending) operations"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed information"
    ),
):
    """
    List operations with optional filtering.

    Shows all operations in the system with their current status, progress,
    and other metadata. Useful for monitoring and debugging.

    Examples:
        ktrdr operations list
        ktrdr operations list --active
        ktrdr operations list --status running
        ktrdr operations list --type data_load --limit 10
    """
    try:
        # Run async operation
        asyncio.run(
            _list_operations_async(status, operation_type, limit, active_only, verbose)
        )

    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)


async def _list_operations_async(
    status: Optional[str],
    operation_type: Optional[str],
    limit: int,
    active_only: bool,
    verbose: bool,
):
    """Async implementation of list operations command."""
    try:
        # Check API connection
        if not await check_api_connection():
            error_console.print(
                "[bold red]Error:[/bold red] Could not connect to KTRDR API server"
            )
            error_console.print(
                "Make sure the API server is running at http://localhost:8000"
            )
            sys.exit(1)

        api_client = get_api_client()

        if verbose:
            console.print(
                f"🔍 Listing operations (status: {status}, type: {operation_type}, active_only: {active_only})"
            )

        # List operations via API
        response = await api_client.list_operations(
            status=status,
            operation_type=operation_type,
            limit=limit,
            active_only=active_only,
        )

        operations = response.get("data", [])
        total_count = response.get("total_count", 0)
        active_count = response.get("active_count", 0)

        # Display results
        if not operations:
            if active_only:
                console.print("ℹ️  No active operations found")
            else:
                console.print("ℹ️  No operations found")
            return

        # Show summary
        console.print("\n📋 [bold]Operations Summary[/bold]")
        console.print(f"Showing: {len(operations)} operations")
        console.print(f"Total: {total_count} | Active: {active_count}")
        console.print()

        # Create table
        table = Table()
        table.add_column("Operation ID", style="cyan", max_width=30)
        table.add_column("Type", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("Progress", style="blue")
        table.add_column("Symbol", style="magenta")
        table.add_column("Duration", style="white")

        if verbose:
            table.add_column("Created", style="dim")
            table.add_column("Current Step", style="dim", max_width=40)

        for op in operations:
            # Format status with colors
            status_display = op["status"].upper()
            if op["status"] == "running":
                status_display = f"[green]{status_display}[/green]"
            elif op["status"] == "completed":
                status_display = f"[bright_green]{status_display}[/bright_green]"
            elif op["status"] == "failed":
                status_display = f"[red]{status_display}[/red]"
            elif op["status"] == "cancelled":
                status_display = f"[yellow]{status_display}[/yellow]"

            # Format progress
            progress = f"{op.get('progress_percentage', 0):.0f}%"

            # Format duration
            duration = "N/A"
            if op.get("duration_seconds"):
                duration = api_client.format_duration(op["duration_seconds"])

            # Basic row
            row = [
                (
                    op["operation_id"][-20:] + "..."
                    if len(op["operation_id"]) > 23
                    else op["operation_id"]
                ),  # Truncate long IDs
                op["operation_type"],
                status_display,
                progress,
                op.get("symbol", "N/A"),
                duration,
            ]

            # Add verbose columns
            if verbose:
                created = op["created_at"][:16].replace("T", " ")  # Truncate datetime
                current_step = op.get("current_step", "N/A")
                if current_step and len(current_step) > 40:
                    current_step = current_step[:37] + "..."
                row.extend([created, current_step])

            table.add_row(*row)

        console.print(table)

        if verbose:
            console.print(f"\n✅ Retrieved {len(operations)} operations")

    except Exception as e:
        raise DataError(
            message="Failed to list operations",
            error_code="CLI-ListOperationsError",
            details={"error": str(e)},
        ) from e


@trace_cli_command("operations_status")
@operations_app.command("status")
def get_operation_status(
    operation_id: str = typer.Argument(..., help="Operation ID to check"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed information"
    ),
):
    """
    Get detailed status for a specific operation.

    Shows complete information about an operation including progress,
    metadata, and results (if completed).

    Examples:
        ktrdr operations status op_data_load_20241201_123456
        ktrdr operations status op_training_20241201_789012 --verbose
    """
    try:
        # Input validation
        operation_id = InputValidator.validate_string(
            operation_id, min_length=1, max_length=100
        )

        # Run async operation
        asyncio.run(_get_operation_status_async(operation_id, verbose))

    except ValidationError as e:
        error_console.print(f"[bold red]Validation error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Validation error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)


async def _get_operation_status_async(operation_id: str, verbose: bool):
    """Async implementation of get operation status command."""
    try:
        # Check API connection
        if not await check_api_connection():
            error_console.print(
                "[bold red]Error:[/bold red] Could not connect to KTRDR API server"
            )
            error_console.print(
                "Make sure the API server is running at http://localhost:8000"
            )
            sys.exit(1)

        api_client = get_api_client()

        if verbose:
            console.print(f"🔍 Getting status for operation: {operation_id}")

        # Get operation status via API
        try:
            response = await api_client.get_operation_status(operation_id)
            operation = response.get("data", {})
        except DataError as e:
            if "404" in str(e) or "not found" in str(e).lower():
                error_console.print(f"❌ Operation not found: {operation_id}")
                sys.exit(1)
            else:
                raise

        # Display operation details
        console.print(f"\n📊 [bold]Operation Status: {operation_id}[/bold]")

        # Main info table
        table = Table()
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Operation ID", operation.get("operation_id", "N/A"))
        table.add_row("Type", operation.get("operation_type", "N/A"))
        table.add_row("Status", operation.get("status", "N/A").upper())
        table.add_row("Created", str(operation.get("created_at", "N/A")))
        table.add_row("Started", str(operation.get("started_at", "N/A")))
        table.add_row("Completed", str(operation.get("completed_at", "N/A")))

        # Duration
        duration = "N/A"
        if operation.get("duration_seconds"):
            duration = api_client.format_duration(operation["duration_seconds"])
        table.add_row("Duration", duration)

        console.print(table)

        # Progress info
        progress = operation.get("progress", {})
        if progress:
            console.print("\n📈 [bold]Progress Information[/bold]")
            progress_table = Table()
            progress_table.add_column("Property", style="cyan")
            progress_table.add_column("Value", style="blue")

            progress_table.add_row(
                "Percentage", f"{progress.get('percentage', 0):.1f}%"
            )
            progress_table.add_row("Current Step", progress.get("current_step", "N/A"))
            progress_table.add_row(
                "Steps",
                f"{progress.get('steps_completed', 0)}/{progress.get('steps_total', 0)}",
            )
            progress_table.add_row(
                "Items",
                f"{progress.get('items_processed', 0)}/{progress.get('items_total', 'N/A')}",
            )
            progress_table.add_row("Current Item", progress.get("current_item", "N/A"))

            console.print(progress_table)

        # Metadata
        metadata = operation.get("metadata", {})
        if metadata and verbose:
            console.print("\n🏷️  [bold]Metadata[/bold]")
            metadata_table = Table()
            metadata_table.add_column("Property", style="cyan")
            metadata_table.add_column("Value", style="magenta")

            for key, value in metadata.items():
                if value is not None:
                    metadata_table.add_row(key.title(), str(value))

            console.print(metadata_table)

        # Error or result info
        if operation.get("error_message"):
            console.print("\n❌ [bold red]Error Message[/bold red]")
            console.print(f"[red]{operation['error_message']}[/red]")

        if operation.get("result_summary") and verbose:
            console.print("\n✅ [bold green]Result Summary[/bold green]")
            result_table = Table()
            result_table.add_column("Property", style="cyan")
            result_table.add_column("Value", style="green")

            for key, value in operation["result_summary"].items():
                result_table.add_row(key.title(), str(value))

            console.print(result_table)

        if verbose:
            console.print("\n✅ Retrieved operation status")

    except Exception as e:
        raise DataError(
            message=f"Failed to get operation status for {operation_id}",
            error_code="CLI-GetOperationStatusError",
            details={"operation_id": operation_id, "error": str(e)},
        ) from e


@trace_cli_command("operations_cancel")
@operations_app.command("cancel")
def cancel_operation(
    operation_id: str = typer.Argument(..., help="Operation ID to cancel"),
    reason: Optional[str] = typer.Option(
        None, "--reason", "-r", help="Reason for cancellation"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force cancellation even if operation is in critical section",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed information"
    ),
):
    """
    Cancel a running or pending operation.

    Attempts to gracefully cancel an operation. Use --force for stuck operations
    that are not responding to normal cancellation.

    Examples:
        ktrdr operations cancel op_data_load_20241201_123456
        ktrdr operations cancel op_training_20241201_789012 --reason "User request"
        ktrdr operations cancel op_stuck_20241201_999999 --force
    """
    try:
        # Input validation
        operation_id = InputValidator.validate_string(
            operation_id, min_length=1, max_length=100
        )

        # Run async operation
        asyncio.run(_cancel_operation_async(operation_id, reason, force, verbose))

    except ValidationError as e:
        error_console.print(f"[bold red]Validation error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Validation error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)


async def _cancel_operation_async(
    operation_id: str,
    reason: Optional[str],
    force: bool,
    verbose: bool,
):
    """Async implementation of cancel operation command."""
    try:
        # Check API connection
        if not await check_api_connection():
            error_console.print(
                "[bold red]Error:[/bold red] Could not connect to KTRDR API server"
            )
            error_console.print(
                "Make sure the API server is running at http://localhost:8000"
            )
            sys.exit(1)

        api_client = get_api_client()

        if verbose:
            console.print(f"🛑 Cancelling operation: {operation_id}")
            if reason:
                console.print(f"Reason: {reason}")
            if force:
                console.print("⚠️  Force cancellation enabled")

        # Cancel operation via API
        try:
            response = await api_client.cancel_operation(
                operation_id=operation_id,
                reason=reason,
                force=force,
            )
            result = response.get("data", {})
        except DataError as e:
            if "404" in str(e) or "not found" in str(e).lower():
                error_console.print(f"❌ Operation not found: {operation_id}")
                sys.exit(1)
            elif "400" in str(e) or "cannot be cancelled" in str(e).lower():
                error_console.print(f"❌ Operation cannot be cancelled: {operation_id}")
                error_console.print(
                    "The operation may already be completed, failed, or cancelled."
                )
                sys.exit(1)
            else:
                raise

        # Display results
        if result.get("success"):
            console.print(
                f"✅ [green]Successfully cancelled operation: {operation_id}[/green]"
            )

            if result.get("cancelled_at"):
                console.print(f"🕐 Cancelled at: {result['cancelled_at']}")

            if result.get("cancellation_reason"):
                console.print(f"📝 Reason: {result['cancellation_reason']}")

            if result.get("task_cancelled"):
                console.print("🔄 Background task was cancelled")
            else:
                console.print("ℹ️  Operation was already stopping")

        else:
            error_console.print(f"❌ Failed to cancel operation: {operation_id}")
            if result.get("error"):
                error_console.print(f"Error: {result['error']}")
            sys.exit(1)

        if verbose:
            console.print("\n✅ Operation cancellation completed")

    except Exception as e:
        raise DataError(
            message=f"Failed to cancel operation {operation_id}",
            error_code="CLI-CancelOperationError",
            details={"operation_id": operation_id, "error": str(e)},
        ) from e


@trace_cli_command("operations_retry")
@operations_app.command("retry")
def retry_operation(
    operation_id: str = typer.Argument(..., help="Failed operation ID to retry"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed information"
    ),
):
    """
    Retry a failed operation with the same parameters.

    Creates a new operation with the same configuration as the failed operation.
    The new operation gets a new operation ID for tracking.

    Examples:
        ktrdr operations retry op_data_load_20241201_123456
        ktrdr operations retry op_training_20241201_789012 --verbose
    """
    try:
        # Input validation
        operation_id = InputValidator.validate_string(
            operation_id, min_length=1, max_length=100
        )

        # Run async operation
        asyncio.run(_retry_operation_async(operation_id, verbose))

    except ValidationError as e:
        error_console.print(f"[bold red]Validation error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Validation error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)


async def _retry_operation_async(operation_id: str, verbose: bool):
    """Async implementation of retry operation command."""
    try:
        # Check API connection
        if not await check_api_connection():
            error_console.print(
                "[bold red]Error:[/bold red] Could not connect to KTRDR API server"
            )
            error_console.print(
                "Make sure the API server is running at http://localhost:8000"
            )
            sys.exit(1)

        api_client = get_api_client()

        if verbose:
            console.print(f"🔄 Retrying failed operation: {operation_id}")

        # Retry operation via API
        try:
            response = await api_client.retry_operation(operation_id)
            new_operation = response.get("data", {})
        except DataError as e:
            if "404" in str(e) or "not found" in str(e).lower():
                error_console.print(f"❌ Operation not found: {operation_id}")
                sys.exit(1)
            elif "400" in str(e) or "not failed" in str(e).lower():
                error_console.print(f"❌ Operation cannot be retried: {operation_id}")
                error_console.print("Only failed operations can be retried.")
                sys.exit(1)
            else:
                raise

        # Display results
        new_operation_id = new_operation.get("operation_id")
        console.print("✅ [green]Successfully created retry operation[/green]")
        console.print(f"Original: {operation_id}")
        console.print(f"New: {new_operation_id}")
        console.print(f"Status: {new_operation.get('status', 'N/A').upper()}")

        console.print(
            f"\n💡 Use 'ktrdr operations status {new_operation_id}' to monitor progress"
        )

        if verbose:
            console.print("\n✅ Operation retry completed")

    except Exception as e:
        raise DataError(
            message=f"Failed to retry operation {operation_id}",
            error_code="CLI-RetryOperationError",
            details={"operation_id": operation_id, "error": str(e)},
        ) from e
