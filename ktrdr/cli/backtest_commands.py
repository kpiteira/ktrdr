"""Backtesting commands using unified AsyncOperationExecutor pattern.

This module provides backtesting commands using the unified async operations
pattern with AsyncOperationExecutor and BacktestingOperationAdapter.
"""

import asyncio
import sys
from typing import Optional

import typer
from rich.console import Console

from ktrdr.cli.operation_adapters import BacktestingOperationAdapter
from ktrdr.cli.operation_executor import AsyncOperationExecutor
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


@trace_cli_command("backtest_run")
@backtest_app.command("run")
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
    """Async implementation of run backtest command using unified executor pattern."""
    # Reduce HTTP logging noise unless verbose mode
    if not verbose:
        import logging

        httpx_logger = logging.getLogger("httpx")
        httpx_logger.setLevel(logging.WARNING)

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

    # Create executor for unified async operation handling
    executor = AsyncOperationExecutor()

    # Define backtesting-specific progress message formatter
    def format_backtest_progress(operation_data: dict) -> str:
        """Format progress message with backtesting-specific details."""
        status = operation_data.get("status", "unknown")
        progress_info = operation_data.get("progress") or {}

        # Try to use pre-formatted message from backend
        rendered_message = progress_info.get("current_step")
        if rendered_message and rendered_message != "Status: running":
            return f"Status: {status} - {rendered_message}"

        # Fallback: extract context and build message manually
        progress_context = (
            progress_info.get("context") if progress_info else None
        ) or {}

        # Build status message with bar/trade info
        status_msg = f"Status: {status}"

        # Get current bar information
        current_bar = progress_context.get("current_bar", 0)
        total_bars = progress_context.get("total_bars", 0)
        if current_bar > 0 and total_bars > 0:
            status_msg += f" (Bar: {current_bar}/{total_bars})"

        # Get current trade statistics
        total_trades = progress_context.get("total_trades", 0)
        current_pnl = progress_context.get("current_pnl")
        if total_trades > 0:
            status_msg += f", Trades: {total_trades}"
        if current_pnl is not None:
            status_msg += f", PnL: ${current_pnl:,.2f}"

        return status_msg

    # Execute operation - executor handles progress bar
    success = await executor.execute_operation(
        adapter=adapter,
        console=console,
        progress_callback=format_backtest_progress,
        show_progress=True,
    )

    # Exit with appropriate code
    sys.exit(0 if success else 1)
