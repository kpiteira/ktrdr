"""Train command implementation.

Implements the `ktrdr train <strategy>` command that starts a training
operation using the OperationRunner wrapper. Supports fire-and-forget
(default) or follow mode with --follow flag.
"""

import typer
from rich.console import Console

from ktrdr.cli.operation_adapters import TrainingOperationAdapter
from ktrdr.cli.operation_runner import OperationRunner
from ktrdr.cli.output import print_error
from ktrdr.cli.state import CLIState
from ktrdr.cli.telemetry import trace_cli_command

console = Console()


@trace_cli_command("train")
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
    models_dir: str = typer.Option(
        "models",
        "--models-dir",
        help="Directory to save trained models (default: models)",
    ),
    data_mode: str = typer.Option(
        "local",
        "--data-mode",
        help="Data loading mode: local, ib (default: local)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show training plan without executing",
    ),
    detailed_analytics: bool = typer.Option(
        False,
        "--detailed-analytics",
        help="Enable detailed training analytics with CSV/JSON export",
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

        ktrdr train momentum --start 2024-01-01 --end 2024-06-01 --dry-run

        ktrdr --json train momentum --start 2024-01-01 --end 2024-06-01
    """
    state: CLIState = ctx.obj

    # Handle dry run - show what would happen without executing
    if dry_run:
        console.print("🔍 [yellow]DRY RUN - No model will be trained[/yellow]")
        console.print(f"📋 Strategy: {strategy}")
        console.print(f"📅 Period: {start_date} to {end_date}")
        console.print(f"📊 Validation split: {validation_split}")
        console.print(f"💾 Models directory: {models_dir}")
        console.print(f"📂 Data mode: {data_mode}")
        if detailed_analytics:
            console.print("📈 Detailed analytics: enabled")
        return

    try:
        runner = OperationRunner(state)

        # Display training parameters
        if not state.json_mode:
            console.print("🚀 [cyan]Starting model training...[/cyan]")
            console.print("📋 Training parameters:")
            console.print(f"   Strategy: {strategy}")
            console.print(f"   Period: {start_date} to {end_date}")
            console.print(f"   Validation split: {validation_split}")
            if detailed_analytics:
                console.print(
                    "   Analytics: [green]✅ Detailed analytics enabled[/green]"
                )
            console.print()

        # Create training adapter with parameters
        # Note: symbols and timeframes are fetched from strategy config by backend
        adapter = TrainingOperationAdapter(
            strategy_name=strategy,
            symbols=["AAPL"],  # Backend will override from strategy config
            timeframes=["1h"],  # Backend will override from strategy config
            start_date=start_date,
            end_date=end_date,
            validation_split=validation_split,
            detailed_analytics=detailed_analytics,
        )

        runner.start(adapter, follow=follow)

    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1) from None
