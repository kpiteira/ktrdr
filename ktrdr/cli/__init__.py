"""
Command Line Interface for KTRDR.

This module provides a CLI for interacting with the KTRDR application,
including commands for data inspection, indicator calculation, and visualization.
"""

from ktrdr.cli.commands import cli_app
from ktrdr.cli.data_commands import data_app

# Register data commands as subcommand group
cli_app.add_typer(data_app, name="data", help="Data management commands")

# Export the app for the CLI entry point
app = cli_app

__all__ = ["cli_app", "app"]
