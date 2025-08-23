"""
Enhanced error handling utilities for CLI commands.

This module provides centralized error handling for CLI commands with
special support for IB Gateway diagnostic messages.
"""

import sys
from typing import Any, Dict

from rich.console import Console

from ktrdr.cli.ib_diagnosis import (
    IBProblemType,
    detect_ib_issue_from_api_response,
    get_ib_recovery_suggestions,
    should_show_ib_diagnosis,
)
from ktrdr.errors import DataError, ValidationError
from ktrdr.logging import get_logger

logger = get_logger(__name__)
error_console = Console(stderr=True)


def handle_cli_error(e: Exception, verbose: bool = False, quiet: bool = False) -> None:
    """
    Enhanced error handling for CLI commands that detects IB Gateway issues.

    Args:
        e: Exception that occurred
        verbose: Whether to show verbose error information
        quiet: Whether to suppress non-essential output
    """
    if quiet:
        # In quiet mode, just log and exit
        logger.error(f"CLI error: {str(e)}")
        sys.exit(1)

    # Check if this is a DataError with API response details
    if isinstance(e, DataError) and hasattr(e, "details"):
        details = e.details

        # Check if there's an API response in the details
        if "error_detail" in details:
            api_response = details["error_detail"]

            # Try to detect IB issues from the API response
            if should_show_ib_diagnosis(api_response):
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

    # Check for validation errors
    if isinstance(e, ValidationError):
        error_console.print(f"[bold red]Validation error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Validation error: {str(e)}")
        return

    # Fallback to standard error handling
    error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
    if verbose:
        logger.error(f"CLI command error: {str(e)}", exc_info=True)


def handle_api_response_error(
    response: dict[str, Any],
    context: str = "operation",
    verbose: bool = False,
    quiet: bool = False,
) -> bool:
    """
    Handle API response errors with IB diagnosis support.

    Args:
        response: API response dictionary
        context: Context description for the operation
        verbose: Whether to show verbose error information
        quiet: Whether to suppress non-essential output

    Returns:
        True if an error was handled, False if response was successful
    """
    if response.get("success", True):
        return False

    if quiet:
        return True

    error_info = response.get("error", {})

    # Check for IB diagnosis
    if "ib_diagnosis" in error_info:
        ib_diagnosis = error_info["ib_diagnosis"]
        error_console.print(f"❌ [bold red]{context.title()} failed![/bold red]")
        error_console.print(f"\n{ib_diagnosis['clear_message']}")

        if verbose:
            try:
                problem_type = IBProblemType(ib_diagnosis["problem_type"])
                error_console.print(f"\n{get_ib_recovery_suggestions(problem_type)}")
            except ValueError:
                pass
    else:
        # Standard error message
        error_msg = error_info.get("message", "Unknown error")
        error_console.print(f"❌ [bold red]{context.title()} failed![/bold red]")
        error_console.print(f"🚨 Error: {error_msg}")

        if verbose and error_info:
            error_console.print(f"\n🔍 [bold]Error details:[/bold]")
            for key, value in error_info.items():
                if key != "ib_diagnosis":  # Skip IB diagnosis in raw details
                    error_console.print(f"   {key}: {value}")

    return True


def display_ib_connection_required_message() -> None:
    """Display message when IB connection is required but not available."""
    error_console.print(
        "[bold red]Error:[/bold red] Could not connect to KTRDR API server"
    )
    error_console.print("Make sure the API server is running at http://localhost:8000")


def create_enhanced_exception_handler(verbose: bool = False, quiet: bool = False):
    """
    Create an exception handler function with the given settings.

    Args:
        verbose: Whether to show verbose error information
        quiet: Whether to suppress non-essential output

    Returns:
        Exception handler function
    """

    def exception_handler(e: Exception) -> None:
        handle_cli_error(e, verbose, quiet)
        sys.exit(1)

    return exception_handler
