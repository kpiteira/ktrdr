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

import typer
from rich.console import Console

from ktrdr import get_logger

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

# All commands have been migrated to subcommand modules
# This file now only contains the main CLI app definition
# Individual commands are registered in __init__.py via add_typer()
