"""Backtesting commands using AsyncCLIClient.execute_operation() pattern.

This module provides backtesting commands using the unified async operations
pattern with AsyncCLIClient and BacktestingOperationAdapter.
"""

import asyncio
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from ktrdr.cli.client import AsyncCLIClient, CLIClientError
from ktrdr.cli.operation_adapters import BacktestingOperationAdapter
from ktrdr.cli.telemetry import trace_cli_command
from ktrdr.config.validation import InputValidator
from ktrdr.errors import ValidationError
from ktrdr.logging import get_logger

# Setup logging and console
logger = get_logger(__name__)
console = Console()
error_console = Console(stderr=True)

# Create the CLI app for backtest commands
backtest_app = typer.Typer(
    name="backtest",
    help="Backtesting commands for trading strategies",
    no_args_is_help=True,
)


@backtest_app.command("run")
@trace_cli_command("backtest_run")
def run_backtest(
    strategy: str = typer.Argument(..., help="Strategy name (without .yaml extension)"),
    symbol: str = typer.Argument(
        ..., help="Trading symbol to backtest (e.g., AAPL, EURUSD)"
    ),
    timeframe: str = typer.Argument(
        ..., help="Timeframe for backtest data (e.g., 1h, 4h, 1d)"
    ),
    start_date: str = typer.Option(
        ..., "--start-date", help="Start date for backtest (YYYY-MM-DD)"
    ),
    end_date: str = typer.Option(
        ..., "--end-date", help="End date for backtest (YYYY-MM-DD)"
    ),
    capital: float = typer.Option(
        100000, "--capital", "-c", help="Initial capital for backtest"
    ),
    commission: float = typer.Option(
        0.001, "--commission", help="Commission rate (default: 0.001)"
    ),
    slippage: float = typer.Option(
        0.001, "--slippage", help="Slippage rate (default: 0.001)"
    ),
    model_path: Optional[str] = typer.Option(
        None, "--model-path", "-m", help="Path to trained model (optional)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
) -> None:
    """
    Run a backtest on a trained trading strategy.

    This command uses the async API to simulate trading and provides real-time
    progress updates. The backtest can be cancelled with Ctrl+C.

    Examples:
        ktrdr backtest run neuro_mean_reversion AAPL 1d --start-date 2024-01-01 --end-date 2024-12-31

        ktrdr backtest run momentum EURUSD 1h --start-date 2024-07-01 --end-date 2024-12-31 --capital 50000

        ktrdr backtest run test_strategy MSFT 4h --start-date 2023-01-01 --end-date 2024-01-01 --model-path models/mlp_v1.pt
    """
    try:
        # Validate inputs
        symbol = InputValidator.validate_string(
            symbol, min_length=1, max_length=10, pattern=r"^[A-Za-z0-9\-\.]+$"
        )
        timeframe = InputValidator.validate_string(
            timeframe, min_length=1, max_length=5, pattern=r"^[0-9]+[dhm]$"
        )
        capital = InputValidator.validate_numeric(capital, min_value=1.0)
        commission = InputValidator.validate_numeric(
            commission, min_value=0.0, max_value=0.1
        )
        slippage = InputValidator.validate_numeric(
            slippage, min_value=0.0, max_value=0.1
        )

        # Run async operation
        asyncio.run(
            _run_backtest_async_impl(
                strategy=strategy,
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                capital=capital,
                commission=commission,
                slippage=slippage,
                model_path=model_path,
                verbose=verbose,
            )
        )

    except ValidationError as e:
        error_console.print(f"[bold red]Validation error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Validation error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)


async def _run_backtest_async_impl(
    strategy: str,
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    capital: float,
    commission: float,
    slippage: float,
    model_path: Optional[str],
    verbose: bool,
) -> None:
    """Async implementation of run backtest command using AsyncCLIClient.execute_operation()."""
    # Reduce HTTP logging noise unless verbose mode
    if not verbose:
        import logging

        httpx_logger = logging.getLogger("httpx")
        httpx_logger.setLevel(logging.WARNING)

    # Use AsyncCLIClient for connection reuse and performance
    async with AsyncCLIClient() as cli:
        # Check API connection using AsyncCLIClient
        if not await cli.health_check():
            error_console.print(
                "[bold red]Error:[/bold red] Could not connect to KTRDR API server"
            )
            error_console.print(
                "Make sure the API server is running at the configured URL"
            )
            sys.exit(1)

        if verbose:
            console.print(f"🔬 Running backtest for {symbol} ({timeframe})")
            console.print(f"📋 Strategy: {strategy}")
            console.print(f"📅 Period: {start_date} to {end_date}")
            console.print(f"💰 Initial capital: ${capital:,.2f}")

        # Display backtest parameters
        console.print("🚀 [cyan]Starting backtest via async API...[/cyan]")
        console.print("📋 Backtest parameters:")
        console.print(f"   Strategy: {strategy}")
        console.print(f"   Symbol: {symbol}")
        console.print(f"   Timeframe: {timeframe}")
        console.print(f"   Period: {start_date} to {end_date}")
        console.print(f"   Initial capital: ${capital:,.2f}")
        console.print(f"   Commission: {commission * 100:.2f}%")
        console.print(f"   Slippage: {slippage * 100:.2f}%")
        if model_path:
            console.print(f"   Model: {model_path}")

        # Create adapter with backtesting-specific parameters
        adapter = BacktestingOperationAdapter(
            strategy_name=strategy,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=capital,
            commission=commission,
            slippage=slippage,
            model_path=model_path,
        )

        # Set up progress display using Rich Progress
        progress_bar = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        )
        task_id = None

        def on_progress(percentage: int, message: str) -> None:
            """Progress callback for Rich progress display."""
            nonlocal task_id
            if task_id is not None:
                progress_bar.update(task_id, completed=percentage, description=message)

        # Execute the operation with progress display
        try:
            with progress_bar:
                task_id = progress_bar.add_task("Running backtest...", total=100)
                result = await cli.execute_operation(
                    adapter,
                    on_progress=on_progress,
                    poll_interval=0.3,
                )
        except CLIClientError as e:
            console.print(f"❌ [red]Failed to start backtest: {str(e)}[/red]")
            return

        # Handle result based on final status
        status = result.get("status", "unknown")
        operation_id = result.get("operation_id", "")

        if status == "completed":
            console.print("✅ [green]Backtest completed successfully![/green]")
            console.print(f"   Operation ID: [bold]{operation_id}[/bold]")

            # Display backtest results from result_summary
            _display_backtest_results(result, console)

        elif status == "failed":
            error_msg = result.get(
                "error_message", result.get("error", "Unknown error")
            )
            console.print(f"❌ [red]Backtest failed: {error_msg}[/red]")

        elif status == "cancelled":
            console.print("✅ [yellow]Backtest cancelled successfully[/yellow]")

        else:
            console.print(f"⚠️ [yellow]Backtest ended with status: {status}[/yellow]")


def _display_backtest_results(result: dict, console: Console) -> None:
    """Display backtest performance results.

    If no metrics are present in the result, a notice is printed and the function
    returns without displaying detailed metrics.
    """
    result_summary = result.get("result_summary", {})
    metrics = result_summary.get("metrics", {})

    if not metrics:
        console.print(
            "[yellow]No performance metrics were returned for this backtest.[/yellow]"
        )
        return

    console.print("📊 [bold green]Backtest Results:[/bold green]")

    # Performance metrics
    total_return_pct = metrics.get("total_return_pct", 0.0)
    console.print(f"   Total Return: {total_return_pct:.2%}")

    sharpe_ratio = metrics.get("sharpe_ratio", 0.0)
    console.print(f"   Sharpe Ratio: {sharpe_ratio:.2f}")

    max_drawdown_pct = metrics.get("max_drawdown_pct", 0.0)
    console.print(f"   Max Drawdown: {max_drawdown_pct:.2%}")

    # Trade statistics
    total_trades = metrics.get("total_trades", 0)
    console.print(f"   Total Trades: {total_trades}")

    win_rate = metrics.get("win_rate", 0.0)
    console.print(f"   Win Rate: {win_rate:.2%}")
