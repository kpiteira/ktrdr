"""
CLI commands for KTRDR application.

This module defines the main CLI application entry point.
All specific commands have been migrated to dedicated subcommand modules:
- data_commands.py - Data management commands
- operations_commands.py - Operation management commands
- indicator_commands.py - Technical indicator commands
- ib_commands.py - Interactive Brokers integration commands
- model_commands.py - Neural network model management commands
- strategy_commands.py - Trading strategy management commands
- fuzzy_commands.py - Fuzzy logic operations commands
"""

from typing import Optional

import typer
from rich.console import Console

from ktrdr import get_logger

# Global CLI state for URL override
# This allows --url at root level to affect all subcommands
_cli_state: dict[str, Optional[str]] = {"api_url": None}


def get_api_url_override() -> Optional[str]:
    """Get the global API URL override if set via --url."""
    return _cli_state["api_url"]


# Create a Typer application with help text
cli_app = typer.Typer(
    name="ktrdr",
    help="KTRDR - Trading analysis and automation tool",
    add_completion=False,
)

# Get module logger
logger = get_logger(__name__)

# Create a rich console for formatted output
console = Console()
error_console = Console(stderr=True)


@cli_app.callback()
def main(
    url: Optional[str] = typer.Option(
        None,
        "--url",
        "-u",
        help="API URL override (e.g., http://backend.ktrdr.home.mynerd.place:8000)",
        envvar="KTRDR_API_URL",
    ),
):
    """KTRDR - Trading analysis and automation tool."""
    if url:
        _cli_state["api_url"] = url

        # Reconfigure telemetry to send traces to the same host as the API
        # This enables distributed tracing when targeting remote servers
        from ktrdr.cli import reconfigure_telemetry_for_url

        reconfigure_telemetry_for_url(url)


# All commands have been migrated to subcommand modules
# This file now only contains the main CLI app definition
# Individual commands are registered in __init__.py via add_typer()
