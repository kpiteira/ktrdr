"""Backtest command implementation.

Implements the `ktrdr backtest <strategy>` command that starts a backtesting
operation using the OperationRunner wrapper. Supports fire-and-forget
(default) or follow mode with --follow flag.

PERFORMANCE NOTE: Heavy imports (operation_runner, operation_adapters) are
deferred inside the function body to keep CLI startup fast.
"""

import typer

from ktrdr.cli.telemetry import trace_cli_command


@trace_cli_command("backtest")
def backtest(
    ctx: typer.Context,
    strategy: str = typer.Argument(..., help="Strategy name to backtest"),
    start_date: str = typer.Option(
        ...,
        "--start",
        help="Backtest start date (YYYY-MM-DD)",
    ),
    end_date: str = typer.Option(
        ...,
        "--end",
        help="Backtest end date (YYYY-MM-DD)",
    ),
    capital: float = typer.Option(
        100000.0,
        "--capital",
        "-c",
        help="Initial capital for backtest (default: 100000)",
    ),
    commission: float = typer.Option(
        0.001,
        "--commission",
        help="Commission rate (default: 0.001)",
    ),
    slippage: float = typer.Option(
        0.001,
        "--slippage",
        help="Slippage rate (default: 0.001)",
    ),
    model_path: str = typer.Option(
        None,
        "--model-path",
        "-m",
        help="Path to trained model (optional)",
    ),
    follow: bool = typer.Option(
        False,
        "--follow",
        "-f",
        help="Follow progress until completion",
    ),
) -> None:
    """Run a backtest for a strategy.

    Starts a backtesting operation for the specified strategy. By default,
    returns immediately with the operation ID. Use --follow to watch
    progress until completion.

    Symbol and timeframe are read from the strategy config.

    Examples:
        ktrdr backtest momentum --start 2024-01-01 --end 2024-06-01

        ktrdr backtest momentum --start 2024-01-01 --end 2024-06-01 --follow

        ktrdr backtest momentum --start 2024-01-01 --end 2024-06-01 --capital 50000

        ktrdr --json backtest momentum --start 2024-01-01 --end 2024-06-01
    """
    # Lazy imports for fast CLI startup
    from rich.console import Console

    from ktrdr.cli.operation_adapters import BacktestingOperationAdapter
    from ktrdr.cli.operation_runner import OperationRunner
    from ktrdr.cli.output import print_error
    from ktrdr.cli.state import CLIState

    state: CLIState = ctx.obj
    console = Console()

    try:
        # Display backtest parameters
        if not state.json_mode:
            console.print("[cyan]Starting backtest...[/cyan]")
            console.print("Backtest parameters:")
            console.print(f"   Strategy: {strategy}")
            console.print(f"   Period: {start_date} to {end_date}")
            console.print(f"   Initial capital: ${capital:,.2f}")
            console.print(f"   Commission: {commission * 100:.2f}%")
            console.print(f"   Slippage: {slippage * 100:.2f}%")
            if model_path:
                console.print(f"   Model: {model_path}")
            console.print()

        runner = OperationRunner(state)

        # Create backtesting adapter
        # Symbol/timeframe are placeholders - backend should read from strategy config
        # TODO: Update BacktestingOperationAdapter to make symbol/timeframe optional
        #       like TrainingOperationAdapter, then remove hardcoded values
        adapter = BacktestingOperationAdapter(
            strategy_name=strategy,
            symbol="AAPL",  # TODO: Get from strategy config via API
            timeframe="1h",  # TODO: Get from strategy config via API
            start_date=start_date,
            end_date=end_date,
            initial_capital=capital,
            commission=commission,
            slippage=slippage,
            model_path=model_path,
        )

        runner.start(adapter, follow=follow)

    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1) from None
