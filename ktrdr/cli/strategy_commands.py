"""
Strategy management commands for the KTRDR CLI.

This module contains essential CLI commands related to trading strategies:
- validate: Validate strategy configurations
- list: List available strategies
- backtest: Run backtesting on strategies
- validate-all: Validate all strategies in a directory
"""

import asyncio
import sys
import json
from typing import Optional
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
)

from ktrdr.cli.api_client import get_api_client, check_api_connection
from ktrdr.config.validation import InputValidator
from ktrdr.errors import ValidationError, DataError
from ktrdr.logging import get_logger
from ktrdr.config.strategy_validator import StrategyValidator
from ktrdr.config.strategy_loader import strategy_loader

# Setup logging and console
logger = get_logger(__name__)
console = Console()
error_console = Console(stderr=True)

# Create the CLI app for strategy commands
strategies_app = typer.Typer(
    name="strategies",
    help="Trading strategy management commands",
    no_args_is_help=True,
)


@strategies_app.command("validate")
def validate_strategy(
    strategy: str = typer.Argument(..., help="Path to strategy YAML file"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal output"),
):
    """
    Validate a trading strategy configuration.

    Checks if a strategy YAML file has all required sections and valid configuration
    for neuro-fuzzy training.
    """
    validator = StrategyValidator()

    strategy_path = Path(strategy)
    if not strategy_path.exists():
        console.print(f"[red]❌ Error: Strategy file not found: {strategy_path}[/red]")
        raise typer.Exit(1)

    console.print(f"🔍 Validating strategy: [blue]{strategy_path}[/blue]")
    console.print("=" * 60)

    result = validator.validate_strategy(str(strategy_path))

    # Print validation results
    if result.is_valid:
        console.print("[green]✅ Strategy configuration is valid![/green]")
    else:
        console.print("[red]❌ Strategy configuration has issues:[/red]")

    if result.errors:
        console.print(f"\n[red]🚨 Errors ({len(result.errors)}):[/red]")
        for i, error in enumerate(result.errors, 1):
            console.print(f"  {i}. {error}")

    if result.warnings:
        console.print(f"\n[yellow]⚠️  Warnings ({len(result.warnings)}):[/yellow]")
        for i, warning in enumerate(result.warnings, 1):
            console.print(f"  {i}. {warning}")

    if result.missing_sections:
        console.print(
            f"\n[blue]📋 Missing sections ({len(result.missing_sections)}):[/blue]"
        )
        for i, section in enumerate(result.missing_sections, 1):
            console.print(f"  {i}. {section}")

    if result.suggestions:
        console.print(f"\n[cyan]💡 Suggestions ({len(result.suggestions)}):[/cyan]")
        for i, suggestion in enumerate(result.suggestions, 1):
            console.print(f"  {i}. {suggestion}")

    console.print("\n" + "=" * 60)

    summary_status = "[green]VALID[/green]" if result.is_valid else "[red]INVALID[/red]"
    console.print(f"📊 [bold]Validation Summary: {summary_status}[/bold]")

    if not quiet and (result.errors or result.warnings):
        console.print(
            f"   Errors: {len(result.errors)} | "
            f"Warnings: {len(result.warnings)} | "
            f"Suggestions: {len(result.suggestions)}"
        )

    if not result.is_valid:
        raise typer.Exit(1)


@strategies_app.command("list")
def list_strategies(
    directory: str = typer.Argument(
        "strategies", help="Directory containing strategy files"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed information"
    ),
):
    """
    List all available trading strategies.

    Scans the strategies directory and shows all valid strategy configurations.
    """
    strategies_dir = Path(directory)
    if not strategies_dir.exists():
        console.print(
            f"[red]❌ Error: Strategies directory not found: {strategies_dir}[/red]"
        )
        raise typer.Exit(1)

    # Find all YAML files
    strategy_files = list(strategies_dir.glob("*.yaml")) + list(
        strategies_dir.glob("*.yml")
    )
    strategy_files = [f for f in strategy_files if not f.name.startswith(".")]

    if not strategy_files:
        console.print(
            f"[yellow]📭 No strategy files found in {strategies_dir}[/yellow]"
        )
        return

    console.print(
        f"📋 Found {len(strategy_files)} strategy files in [blue]{strategies_dir}[/blue]"
    )
    console.print("=" * 80)

    validator = StrategyValidator()
    valid_strategies = []
    invalid_strategies = []

    table = Table(title="Trading Strategies")
    if verbose:
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("File", style="blue")
        table.add_column("Scope", style="green")
        table.add_column("Symbols", style="yellow")
        table.add_column("Timeframes", style="magenta")
        table.add_column("Status", style="white")
    else:
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("File", style="blue")
        table.add_column("Status", style="white")

    for strategy_file in sorted(strategy_files):
        try:
            # Load and validate strategy
            config, is_v2 = strategy_loader.load_strategy_config(str(strategy_file))
            result = validator.validate_strategy(str(strategy_file))

            status = (
                "[green]✅ Valid[/green]"
                if result.is_valid
                else "[red]❌ Invalid[/red]"
            )

            if result.is_valid:
                valid_strategies.append(strategy_file.name)
            else:
                invalid_strategies.append(strategy_file.name)

            if verbose:
                # Extract detailed info
                symbols, timeframes = (
                    strategy_loader.extract_training_symbols_and_timeframes(config)
                )
                scope = getattr(config, "scope", "unknown")
                scope_str = (
                    str(scope).split(".")[-1] if hasattr(scope, "value") else str(scope)
                )

                symbols_str = ", ".join(symbols[:2]) + (
                    "..." if len(symbols) > 2 else ""
                )
                timeframes_str = ", ".join(timeframes[:2]) + (
                    "..." if len(timeframes) > 2 else ""
                )

                table.add_row(
                    config.name,
                    strategy_file.name,
                    scope_str,
                    symbols_str,
                    timeframes_str,
                    status,
                )
            else:
                table.add_row(config.name, strategy_file.name, status)

        except Exception as e:
            invalid_strategies.append(strategy_file.name)
            status = f"[red]❌ Error: {str(e)[:50]}...[/red]"

            if verbose:
                table.add_row(
                    "Unknown",
                    strategy_file.name,
                    "Unknown",
                    "Unknown",
                    "Unknown",
                    status,
                )
            else:
                table.add_row("Unknown", strategy_file.name, status)

    console.print(table)
    console.print("\n" + "=" * 80)
    console.print(f"📊 [bold]Summary:[/bold]")
    console.print(f"   [green]✅ Valid: {len(valid_strategies)}[/green]")
    console.print(f"   [red]❌ Invalid: {len(invalid_strategies)}[/red]")
    console.print(f"   Total: {len(strategy_files)}")

    if invalid_strategies:
        console.print(f"\n[red]❌ Invalid strategies:[/red]")
        for strategy in invalid_strategies:
            console.print(f"   • {strategy}")


@strategies_app.command("backtest")
def backtest_strategy(
    strategy_file: str = typer.Argument(
        ..., help="Path to strategy configuration file"
    ),
    symbol: str = typer.Argument(..., help="Symbol to backtest (e.g., AAPL, EURUSD)"),
    timeframe: str = typer.Argument(
        ..., help="Timeframe for backtesting (e.g., 1h, 4h, 1d)"
    ),
    start_date: str = typer.Option(
        "2020-01-01", "--start", help="Start date (YYYY-MM-DD)"
    ),
    end_date: str = typer.Option("2024-01-01", "--end", help="End date (YYYY-MM-DD)"),
    initial_capital: float = typer.Option(
        100000.0, "--capital", help="Initial capital"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be done without executing"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed progress"
    ),
):
    """
    Run backtesting for a trading strategy.

    Executes a backtest for the specified strategy on the given symbol and timeframe.
    Results are stored and can be retrieved via the API.
    """
    strategy_path = Path(strategy_file)
    if not strategy_path.exists():
        console.print(f"[red]❌ Error: Strategy file not found: {strategy_path}[/red]")
        raise typer.Exit(1)

    # Validate inputs
    validator = InputValidator()
    if not validator.is_valid_symbol(symbol):
        console.print(f"[red]❌ Error: Invalid symbol format: {symbol}[/red]")
        raise typer.Exit(1)

    if not validator.is_valid_timeframe(timeframe):
        console.print(f"[red]❌ Error: Invalid timeframe: {timeframe}[/red]")
        console.print("Valid timeframes: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w")
        raise typer.Exit(1)

    # Run the backtest asynchronously
    asyncio.run(
        run_backtest_async(
            strategy_file,
            symbol,
            timeframe,
            start_date,
            end_date,
            initial_capital,
            dry_run,
            verbose,
        )
    )


async def run_backtest_async(
    strategy_file: str,
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    initial_capital: float,
    dry_run: bool,
    verbose: bool,
):
    """Async wrapper for backtest execution."""
    try:
        # Check API connection
        if not await check_api_connection():
            error_console.print(
                "[bold red]Error:[/bold red] Could not connect to KTRDR API server"
            )
            error_console.print(
                "Make sure the API server is running at http://localhost:8000"
            )
            sys.exit(1)

        api_client = get_api_client()

        if verbose:
            console.print(f"📈 Backtesting strategy for {symbol} ({timeframe})")
            console.print(f"📋 Strategy: {strategy_file}")
            console.print(f"📅 Period: {start_date} to {end_date}")
            console.print(f"💰 Initial capital: ${initial_capital:,.2f}")

        if dry_run:
            console.print(f"🔍 [yellow]DRY RUN - No backtest will be executed[/yellow]")
            console.print(f"📋 Would backtest: {symbol} on {timeframe}")
            console.print(f"📊 Strategy: {strategy_file}")
            console.print(f"💰 Capital: ${initial_capital:,.2f}")
            console.print(f"📅 Period: {start_date} to {end_date}")
            return

        # Call the real backtesting API endpoint
        console.print(f"🚀 [cyan]Starting backtest via API...[/cyan]")
        console.print(f"📋 Backtest parameters:")
        console.print(f"   Strategy: {strategy_file}")
        console.print(f"   Symbol: {symbol}")
        console.print(f"   Timeframe: {timeframe}")
        console.print(f"   Period: {start_date} to {end_date}")
        console.print(f"   Capital: ${initial_capital:,.2f}")

        # Extract strategy name from file path for API call
        strategy_name = Path(strategy_file).stem

        # Start the backtest via API
        try:
            result = await api_client.start_backtest(
                strategy_name=strategy_name,
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
            )

            backtest_id = result["backtest_id"]
            console.print(f"✅ Backtest started with ID: [bold]{backtest_id}[/bold]")

        except Exception as e:
            console.print(f"❌ [red]Failed to start backtest: {str(e)}[/red]")
            return

        # Poll for progress with real API calls
        # Temporarily suppress httpx logging to keep progress display clean
        import logging

        httpx_logger = logging.getLogger("httpx")
        original_level = httpx_logger.level
        httpx_logger.setLevel(logging.WARNING)

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Running backtest...", total=100)

                while True:
                    try:
                        # Get real status from operations API
                        status_result = await api_client.get_operation_status(
                            backtest_id
                        )
                        data = status_result.get("data", {})
                        status = data.get("status", "unknown")
                        progress_info = data.get("progress", {})
                        progress_pct = progress_info.get("percentage", 0)

                        # Update progress bar with real progress
                        progress.update(
                            task,
                            completed=progress_pct,
                            description=f"Status: {status}",
                        )

                        if status == "completed":
                            console.print(
                                f"✅ [green]Backtest completed successfully![/green]"
                            )
                            break
                        elif status == "failed":
                            error_msg = data.get("error_message", "Unknown error")
                            console.print(f"❌ [red]Backtest failed: {error_msg}[/red]")
                            return

                        # Wait before next poll
                        await asyncio.sleep(2)

                    except Exception as e:
                        console.print(
                            f"❌ [red]Error polling backtest status: {str(e)}[/red]"
                        )
                        return

        finally:
            # Restore original logging level
            httpx_logger.setLevel(original_level)

        # Get final results
        try:
            results = await api_client.get_backtest_results(backtest_id)

            if results:
                console.print(f"\n📊 [bold green]Backtest Results:[/bold green]")
                console.print(f"   Total Return: {results.get('total_return', 'N/A')}")
                console.print(f"   Sharpe Ratio: {results.get('sharpe_ratio', 'N/A')}")
                console.print(f"   Max Drawdown: {results.get('max_drawdown', 'N/A')}")
                console.print(f"   Total Trades: {results.get('total_trades', 'N/A')}")
                console.print(f"   Win Rate: {results.get('win_rate', 'N/A')}")
            else:
                console.print(f"[yellow]⚠️  Results not yet available[/yellow]")

        except Exception as e:
            console.print(f"[yellow]⚠️  Could not retrieve results: {str(e)}[/yellow]")

    except Exception as e:
        console.print(f"❌ [red]Backtest failed: {str(e)}[/red]")
        sys.exit(1)


@strategies_app.command("validate-all")
def validate_all_cmd(
    directory: str = typer.Argument(..., help="Directory containing strategy files"),
    fail_fast: bool = typer.Option(
        False, "--fail-fast", help="Stop on first validation error"
    ),
    summary_only: bool = typer.Option(
        False, "--summary", help="Show only summary statistics"
    ),
):
    """
    Validate all strategy files in a directory.

    Runs validation on all strategy files and provides a comprehensive
    report of validation results.
    """
    dir_path = Path(directory)
    if not dir_path.exists() or not dir_path.is_dir():
        console.print(f"[red]❌ Error: Directory not found: {dir_path}[/red]")
        raise typer.Exit(1)

    console.print(f"🔍 Validating all strategies in: [blue]{dir_path}[/blue]")
    console.print("=" * 60)

    validator = StrategyValidator()
    strategy_files = list(dir_path.glob("*.yaml")) + list(dir_path.glob("*.yml"))

    if not strategy_files:
        console.print("[yellow]📭 No strategy files found[/yellow]")
        return

    valid_count = 0
    invalid_count = 0
    error_details = []

    for file_path in sorted(strategy_files):
        try:
            result = validator.validate_strategy(str(file_path))

            if result.is_valid:
                valid_count += 1
                if not summary_only:
                    console.print(f"[green]✅[/green] {file_path.name}")
            else:
                invalid_count += 1
                error_details.append((file_path.name, result.errors))

                if not summary_only:
                    console.print(
                        f"[red]❌[/red] {file_path.name} ({len(result.errors)} errors)"
                    )
                    for error in result.errors[:2]:  # Show first 2 errors
                        console.print(f"    • {error}")
                    if len(result.errors) > 2:
                        console.print(f"    ... and {len(result.errors) - 2} more")

                if fail_fast:
                    console.print(
                        f"\n[red]💥 Stopping on first error (--fail-fast)[/red]"
                    )
                    break

        except Exception as e:
            invalid_count += 1
            if not summary_only:
                console.print(
                    f"[red]❌[/red] {file_path.name} (validation failed: {e})"
                )

            if fail_fast:
                console.print(f"\n[red]💥 Stopping on first error (--fail-fast)[/red]")
                break

    # Summary
    total = valid_count + invalid_count
    success_rate = (valid_count / total * 100) if total > 0 else 0

    console.print("\n" + "=" * 60)
    console.print(f"[bold]📊 Validation Summary:[/bold]")
    console.print(f"  Total files: {total}")
    console.print(f"  [green]✅ Valid: {valid_count}[/green]")
    console.print(f"  [red]❌ Invalid: {invalid_count}[/red]")
    console.print(f"  Success rate: {success_rate:.1f}%")

    if invalid_count > 0:
        console.print(f"\n[red]❌ {invalid_count} files have validation errors[/red]")
        if summary_only and error_details:
            console.print("\n[red]Files with errors:[/red]")
            for filename, errors in error_details:
                console.print(f"  • {filename} ({len(errors)} errors)")

        raise typer.Exit(1)
    else:
        console.print(f"\n[green]🎉 All strategies are valid![/green]")
