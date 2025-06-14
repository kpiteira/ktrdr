"""
Command Line Interface for KTRDR.

This module provides a CLI for interacting with the KTRDR application,
including commands for data inspection, indicator calculation, and visualization.
"""

from ktrdr.cli.commands import cli_app
from ktrdr.cli.data_commands import data_app
from ktrdr.cli.operations_commands import operations_app
from ktrdr.cli.indicator_commands import indicators_app
from ktrdr.cli.ib_commands import ib_app
from ktrdr.cli.model_commands import models_app
from ktrdr.cli.strategy_commands import strategies_app
from ktrdr.cli.fuzzy_commands import fuzzy_app

# Register command subgroups following industry best practices
cli_app.add_typer(data_app, name="data", help="Data management commands")
cli_app.add_typer(
    operations_app, name="operations", help="Operations management commands"
)
cli_app.add_typer(
    indicators_app, name="indicators", help="Technical indicator commands"
)
cli_app.add_typer(ib_app, name="ib", help="Interactive Brokers integration commands")
cli_app.add_typer(
    models_app, name="models", help="Neural network model management commands"
)
cli_app.add_typer(
    strategies_app, name="strategies", help="Trading strategy management commands"
)
cli_app.add_typer(fuzzy_app, name="fuzzy", help="Fuzzy logic operations commands")

# Export the app for the CLI entry point
app = cli_app

__all__ = ["cli_app", "app"]
