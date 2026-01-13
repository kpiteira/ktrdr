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


def print_error(message: str, state: CLIState) -> None:
    """Print error message (human) or JSON response.

    In human mode, prints to stderr with red formatting.
    In JSON mode, prints to stdout for parsability.

    Args:
        message: The error message to display.
        state: CLI state with json_mode flag.
    """
    if state.json_mode:
        # JSON goes to stdout for easy parsing
        print(json.dumps({"status": "error", "message": message}))
    else:
        error_console.print(f"[red bold]Error:[/red bold] {message}")


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
