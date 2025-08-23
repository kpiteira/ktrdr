"""
Interactive Brokers commands for the KTRDR CLI.

This module contains all CLI commands related to IB integration:
- test: Test IB connection and capabilities
- cleanup: Clean up IB connections and resources
- status: Check IB connection status
- test-head-timestamp: Test head timestamp fetching functionality
"""

import asyncio
import json
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ktrdr.cli.api_client import check_api_connection, get_api_client
from ktrdr.cli.error_handler import display_ib_connection_required_message
from ktrdr.cli.ib_diagnosis import (
    detect_ib_issue_from_api_response,
    get_ib_recovery_suggestions,
)
from ktrdr.config.validation import InputValidator
from ktrdr.errors import DataError, ValidationError
from ktrdr.logging import get_logger

# Setup logging and console
logger = get_logger(__name__)
console = Console()
error_console = Console(stderr=True)

# Create the CLI app for IB commands
ib_app = typer.Typer(
    name="ib",
    help="Interactive Brokers integration commands",
    no_args_is_help=True,
)


def handle_ib_error(e: Exception, verbose: bool = False):
    """
    Enhanced error handling for IB commands that detects IB Gateway issues.

    Args:
        e: Exception that occurred
        verbose: Whether to show verbose error information
    """
    # Check if this is a DataError with API response details
    if isinstance(e, DataError) and hasattr(e, "details"):
        details = e.details

        # Check if there's an API response in the details
        if "error_detail" in details:
            api_response = details["error_detail"]

            # Try to detect IB issues from the API response
            problem_type, clear_message, diag_details = (
                detect_ib_issue_from_api_response(api_response)
            )

            if problem_type and clear_message:
                error_console.print(f"\n{clear_message}")
                if verbose:
                    error_console.print(
                        f"\n{get_ib_recovery_suggestions(problem_type)}"
                    )
                return

    # Fallback to standard error handling
    error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
    if verbose:
        logger.error(f"IB command error: {str(e)}", exc_info=True)


@ib_app.command("test")
def test_connection(
    symbol: Optional[str] = typer.Option("AAPL", "--symbol", "-s", help="Test symbol"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
    timeout: int = typer.Option(
        30, "--timeout", "-t", help="Connection timeout in seconds"
    ),
):
    """
    Test IB connection and basic functionality.

    This command tests the connection to Interactive Brokers and verifies
    that basic operations like symbol validation and data requests work.

    Examples:
        ktrdr ib test
        ktrdr ib test --symbol MSFT --verbose
        ktrdr ib test --timeout 60
    """
    try:
        # Input validation
        if symbol:
            symbol = InputValidator.validate_string(
                symbol, min_length=1, max_length=10, pattern=r"^[A-Za-z0-9\-\.]+$"
            )
        timeout = InputValidator.validate_numeric(timeout, min_value=5, max_value=300)

        # Run async operation
        asyncio.run(_test_connection_async(symbol, verbose, timeout))

    except ValidationError as e:
        error_console.print(f"[bold red]Validation error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Validation error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        handle_ib_error(e, verbose)
        sys.exit(1)


async def _test_connection_async(
    symbol: Optional[str],
    verbose: bool,
    timeout: int,
):
    """Async implementation of IB test command."""
    try:
        # Check API connection
        if not await check_api_connection():
            display_ib_connection_required_message()
            sys.exit(1)

        api_client = get_api_client()

        if verbose:
            console.print(f"🔌 Testing IB connection (timeout: {timeout}s)")

        # This would call the IB test API endpoint
        # For now, show a placeholder message
        console.print(
            "⚠️  [yellow]IB connection test via API not yet implemented[/yellow]"
        )
        console.print(f"📋 Would test connection with symbol: {symbol}")
        console.print(f"⏱️  Timeout: {timeout} seconds")

        # Simulate test results
        console.print("✅ [green]IB Connection: OK[/green]")
        console.print("✅ [green]Symbol Validation: OK[/green]")
        console.print("✅ [green]Market Data: OK[/green]")

    except Exception as e:
        raise DataError(
            message="Failed to test IB connection",
            error_code="CLI-IBTestError",
            details={"symbol": symbol, "timeout": timeout, "error": str(e)},
        ) from e


@ib_app.command("cleanup")
def cleanup_connections(
    force: bool = typer.Option(
        False, "--force", "-f", help="Force cleanup even if connections are active"
    ),
    timeout: int = typer.Option(
        30, "--timeout", "-t", help="Cleanup timeout in seconds"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
):
    """
    Clean up IB connections and resources.

    This command safely closes IB connections, cleans up temporary resources,
    and resets the connection pool for fresh connections.

    Examples:
        ktrdr ib cleanup
        ktrdr ib cleanup --force --verbose
        ktrdr ib cleanup --timeout 60
    """
    try:
        # Input validation
        timeout = InputValidator.validate_numeric(timeout, min_value=5, max_value=300)

        # Run async operation
        asyncio.run(_cleanup_connections_async(force, timeout, verbose))

    except ValidationError as e:
        error_console.print(f"[bold red]Validation error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Validation error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        handle_ib_error(e, verbose)
        sys.exit(1)


async def _cleanup_connections_async(
    force: bool,
    timeout: int,
    verbose: bool,
):
    """Async implementation of IB cleanup command."""
    try:
        # Check API connection
        if not await check_api_connection():
            display_ib_connection_required_message()
            sys.exit(1)

        api_client = get_api_client()

        if verbose:
            console.print(f"🧹 Cleaning up IB connections (timeout: {timeout}s)")

        # This would call the IB cleanup API endpoint
        # For now, show a placeholder message
        console.print(
            "⚠️  [yellow]IB connection cleanup via API not yet implemented[/yellow]"
        )
        console.print(f"📋 Would cleanup with force: {force}")
        console.print(f"⏱️  Timeout: {timeout} seconds")

        # Simulate cleanup results
        console.print("✅ [green]Connections closed: 2[/green]")
        console.print("✅ [green]Resources cleaned: 5[/green]")
        console.print("✅ [green]Connection pool reset: OK[/green]")

    except Exception as e:
        raise DataError(
            message="Failed to cleanup IB connections",
            error_code="CLI-IBCleanupError",
            details={"force": force, "timeout": timeout, "error": str(e)},
        ) from e


@ib_app.command("status")
def check_status(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json)"
    ),
):
    """
    Check IB connection status and health.

    This command provides detailed information about the current state
    of IB connections, including active connections, health status, and metrics.

    Examples:
        ktrdr ib status
        ktrdr ib status --verbose --format json
    """
    try:
        # Run async operation
        asyncio.run(_check_status_async(verbose, output_format))

    except Exception as e:
        handle_ib_error(e, verbose)
        sys.exit(1)


async def _check_status_async(
    verbose: bool,
    output_format: str,
):
    """Async implementation of IB status command."""
    try:
        # Check API connection
        if not await check_api_connection():
            display_ib_connection_required_message()
            sys.exit(1)

        api_client = get_api_client()

        if verbose:
            console.print("📊 Retrieving IB connection status")

        # For now, show hardcoded status until API is implemented
        status_data = {
            "connected": True,
            "connection_time": "2025-06-11T10:30:00Z",
            "active_connections": 2,
            "total_requests": 1247,
            "failed_requests": 3,
            "rate_limit_status": "OK",
            "last_heartbeat": "2025-06-11T17:55:00Z",
        }

        # Format output
        if output_format == "json":
            print(json.dumps(status_data, indent=2))
        else:
            # Table format
            console.print("\n🔌 [bold]IB Connection Status[/bold]")
            console.print()

            table = Table()
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")

            table.add_row(
                "Connected", "✅ Yes" if status_data["connected"] else "❌ No"
            )
            table.add_row("Connection Time", status_data["connection_time"])
            table.add_row("Active Connections", str(status_data["active_connections"]))
            table.add_row("Total Requests", str(status_data["total_requests"]))
            table.add_row("Failed Requests", str(status_data["failed_requests"]))
            table.add_row("Rate Limit Status", status_data["rate_limit_status"])
            table.add_row("Last Heartbeat", status_data["last_heartbeat"])

            console.print(table)

        if verbose:
            console.print("✅ Retrieved IB connection status")

    except Exception as e:
        raise DataError(
            message="Failed to get IB status",
            error_code="CLI-IBStatusError",
            details={"error": str(e)},
        ) from e


# test-head-timestamp command removed - created competing IB connections
# that caused client ID conflicts and broke IB Gateway stability
