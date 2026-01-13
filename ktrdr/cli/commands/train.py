"""Train command implementation.

Implements the `ktrdr train <strategy>` command that starts a training
operation using the OperationRunner wrapper. Supports fire-and-forget
(default) or follow mode with --follow flag.
"""

import typer

from ktrdr.cli.operation_adapters import TrainingOperationAdapter
from ktrdr.cli.operation_runner import OperationRunner
from ktrdr.cli.output import print_error
from ktrdr.cli.state import CLIState


def train(
    ctx: typer.Context,
    strategy: str = typer.Argument(..., help="Strategy name to train"),
    start_date: str = typer.Option(
        ...,
        "--start",
        help="Training start date (YYYY-MM-DD)",
    ),
    end_date: str = typer.Option(
        ...,
        "--end",
        help="Training end date (YYYY-MM-DD)",
    ),
    validation_split: float = typer.Option(
        0.2,
        "--validation-split",
        help="Validation data split ratio (default: 0.2)",
    ),
    follow: bool = typer.Option(
        False,
        "--follow",
        "-f",
        help="Follow progress until completion",
    ),
) -> None:
    """Train a neural network model for a strategy.

    Starts a training operation for the specified strategy. By default,
    returns immediately with the operation ID. Use --follow to watch
    progress until completion.

    Examples:
        ktrdr train momentum --start 2024-01-01 --end 2024-06-01

        ktrdr train momentum --start 2024-01-01 --end 2024-06-01 --follow

        ktrdr --json train momentum --start 2024-01-01 --end 2024-06-01
    """
    state: CLIState = ctx.obj

    try:
        runner = OperationRunner(state)

        # Create training adapter with parameters
        # Note: symbols and timeframes are required by the current adapter but
        # will be fetched from strategy config in the future.
        adapter = TrainingOperationAdapter(
            strategy_name=strategy,
            symbols=["AAPL"],  # TODO: Fetch from strategy config via API
            timeframes=["1h"],  # TODO: Fetch from strategy config via API
            start_date=start_date,
            end_date=end_date,
            validation_split=validation_split,
        )

        runner.start(adapter, follow=follow)

    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1) from None
