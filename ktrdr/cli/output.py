"""CLI output helpers.

Provides output abstraction that formats messages for human or JSON
consumption based on CLIState.json_mode. This centralizes all output
formatting decisions.

Human mode uses Rich formatting for colored, readable output.
JSON mode produces valid JSON to stdout for scripting/automation.
"""

import json

from rich.console import Console

from ktrdr.cli.state import CLIState

# Console instances for stdout and stderr
console = Console()
error_console = Console(stderr=True)


def print_success(
    message: str,
    state: CLIState,
    data: dict | None = None,
) -> None:
    """Print success message (human) or JSON response.

    Args:
        message: The success message to display.
        state: CLI state with json_mode flag.
        data: Optional data dict to include (JSON mode only).
    """
    if state.json_mode:
        output: dict = {"status": "success", "message": message}
        if data is not None:
            output["data"] = data
        print(json.dumps(output))
    else:
        console.print(f"[green]{message}[/green]")


def print_error(message: str, state: CLIState, error: Exception | None = None) -> None:
    """Print error message (human) or JSON response with optional exception context.

    In human mode, prints to stderr with red formatting and additional context if available.
    In JSON mode, prints to stdout for parsability.

    Args:
        message: The error message to display.
        state: CLI state with json_mode flag.
        error: Optional exception object with additional context.
    """
    if state.json_mode:
        # JSON goes to stdout for easy parsing
        output = {"status": "error", "message": message}

        # Add operation context if available from exception
        if error and isinstance(error, Exception):
            if hasattr(error, "operation_id") and error.operation_id:
                output["operation_id"] = error.operation_id
            if hasattr(error, "operation_type") and error.operation_type:
                output["operation_type"] = error.operation_type
            if hasattr(error, "stage") and error.stage:
                output["stage"] = error.stage
            if hasattr(error, "error_code") and error.error_code:
                output["error_code"] = error.error_code
            if hasattr(error, "suggestion") and error.suggestion:
                output["suggestion"] = error.suggestion

        print(json.dumps(output))
    else:
        # Build human-readable error message with context
        parts = []

        # Add operation context if available
        if error and isinstance(error, Exception):
            if hasattr(error, "operation_type") and error.operation_type:
                if hasattr(error, "operation_id") and error.operation_id:
                    parts.append(
                        f"Operation: {error.operation_type} ({error.operation_id})"
                    )
                else:
                    parts.append(f"Operation: {error.operation_type}")

            if hasattr(error, "stage") and error.stage:
                parts.append(f"Stage: {error.stage}")

        # Main error message
        error_prefix = "[red bold]Error:[/red bold]"
        if parts:
            error_console.print(error_prefix)
            for part in parts:
                error_console.print(f"  [yellow]{part}[/yellow]")
            error_console.print(f"  {message}")
        else:
            error_console.print(f"{error_prefix} {message}")

        # Add suggestion if available
        if error and isinstance(error, Exception):
            if hasattr(error, "suggestion") and error.suggestion:
                error_console.print(f"\n[cyan]💡 Suggestion:[/cyan] {error.suggestion}")


def print_operation_started(
    operation_type: str,
    operation_id: str,
    state: CLIState,
) -> None:
    """Print operation started message with follow-up hints.

    In human mode, includes hints for status and follow commands.
    In JSON mode, returns structured data without hints.

    Args:
        operation_type: Type of operation (e.g., "training", "backtest").
        operation_id: The operation ID for tracking.
        state: CLI state with json_mode flag.
    """
    if state.json_mode:
        print(
            json.dumps(
                {
                    "operation_id": operation_id,
                    "status": "started",
                    "type": operation_type,
                }
            )
        )
    else:
        console.print(f"Started {operation_type}: [cyan]{operation_id}[/cyan]")
        console.print(f"  Track progress: ktrdr status {operation_id}")
        console.print(f"  Follow live:    ktrdr follow {operation_id}")
