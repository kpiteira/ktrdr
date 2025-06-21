"""
Strategy management commands for the KTRDR CLI.

This module contains all CLI commands related to trading strategies:
- validate: Validate strategy configurations
- upgrade: Upgrade strategy files to latest format
- list: List available strategies
- backtest: Run backtesting on strategies
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

    if not result.is_valid:
        console.print("[red]❌ Validation failed.[/red]")
        if not quiet:
            console.print(
                "[yellow]💡 Run 'ktrdr strategy-upgrade' to automatically fix issues[/yellow]"
            )
        raise typer.Exit(1)
    else:
        console.print("[green]✅ Strategy is ready for neuro-fuzzy training![/green]")


@strategies_app.command("upgrade")
def upgrade_strategy(
    strategy: str = typer.Argument(..., help="Path to strategy YAML file"),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output path for upgraded file"
    ),
    inplace: bool = typer.Option(
        False, "--inplace", "-i", help="Upgrade in place (overwrites original)"
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal output"),
):
    """
    Upgrade a strategy to neuro-fuzzy format.

    Adds missing sections with sensible defaults to make old strategies compatible
    with the new neuro-fuzzy training system.
    """
    validator = StrategyValidator()

    strategy_path = Path(strategy)
    if not strategy_path.exists():
        console.print(f"[red]❌ Error: Strategy file not found: {strategy_path}[/red]")
        raise typer.Exit(1)

    # Determine output path
    output_path = output
    if output_path is None:
        if inplace:
            output_path = str(strategy_path)
        else:
            # Default: add .upgraded before extension
            output_path = str(
                strategy_path.parent
                / f"{strategy_path.stem}.upgraded{strategy_path.suffix}"
            )

    console.print(f"🔧 Upgrading strategy: [blue]{strategy_path}[/blue]")
    if not inplace:
        console.print(f"📁 Output path: [blue]{output_path}[/blue]")
    console.print("=" * 60)

    # First validate to show current issues
    if not quiet:
        console.print("📊 Current validation status:")
        result = validator.validate_strategy(str(strategy_path))

        if result.errors:
            console.print(f"  [red]🚨 {len(result.errors)} errors[/red]")
        if result.warnings:
            console.print(f"  [yellow]⚠️  {len(result.warnings)} warnings[/yellow]")
        if result.missing_sections:
            console.print(
                f"  [blue]📋 {len(result.missing_sections)} missing sections[/blue]"
            )
        console.print()

    # Perform upgrade
    success, message = validator.upgrade_strategy(str(strategy_path), output_path)

    if success:
        console.print("[green]✅ Strategy upgrade completed![/green]")
        console.print(f"💾 {message}")

        if not quiet:
            # Validate upgraded file
            console.print("\n🔍 Validating upgraded strategy...")
            upgraded_result = validator.validate_strategy(output_path)

            if upgraded_result.is_valid:
                console.print("[green]✅ Upgraded strategy is valid![/green]")
            else:
                console.print(
                    "[yellow]⚠️  Upgraded strategy still has some issues:[/yellow]"
                )
                for error in upgraded_result.errors[:3]:  # Show first 3 errors
                    console.print(f"  • {error}")
                if len(upgraded_result.errors) > 3:
                    console.print(f"  ... and {len(upgraded_result.errors) - 3} more")

        console.print("\n" + "=" * 60)
        console.print(
            "[green]🚀 Your strategy is now ready for neuro-fuzzy training![/green]"
        )
        console.print(
            f"[cyan]💡 Use: uv run python -m ktrdr.training.cli --strategy {output_path}[/cyan]"
        )

    else:
        console.print(f"[red]❌ Upgrade failed: {message}[/red]")
        raise typer.Exit(1)


@strategies_app.command("list")
def list_strategies(
    directory: str = typer.Option(
        "strategies", "--directory", "-d", help="Strategies directory"
    ),
    validate: bool = typer.Option(
        False, "--validate", "-v", help="Validate each strategy"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="Show detailed validation results"
    ),
):
    """
    List all strategy files in a directory.

    Shows strategy names, descriptions, and optionally validates each one.
    """
    strategies_dir = Path(directory)

    if not strategies_dir.exists():
        console.print(
            f"[red]❌ Error: Strategies directory not found: {strategies_dir}[/red]"
        )
        raise typer.Exit(1)

    console.print(f"📂 Strategies in [blue]{strategies_dir}[/blue]:")
    console.print("=" * 60)

    validator = StrategyValidator()
    strategy_files = list(strategies_dir.glob("*.yaml")) + list(
        strategies_dir.glob("*.yml")
    )

    if not strategy_files:
        console.print("[yellow]📭 No strategy files found (.yaml or .yml)[/yellow]")
        return

    # Create a table for better formatting
    table = Table(title=None, show_header=True, header_style="bold cyan")
    table.add_column("File", style="blue")
    table.add_column("Name", style="white")
    table.add_column("Status", style="green")
    if validate:
        table.add_column("Issues", style="yellow")

    for strategy_file in sorted(strategy_files):
        try:
            import yaml

            with open(strategy_file, "r") as f:
                config = yaml.safe_load(f)
                name = config.get("name", "Unknown")

                if validate:
                    result = validator.validate_strategy(str(strategy_file))
                    if result.is_valid:
                        status = "✅ Valid"
                        issues = ""
                    else:
                        status = "❌ Invalid"
                        issues = f"{len(result.errors)} errors, {len(result.warnings)} warnings"
                    table.add_row(strategy_file.name, name, status, issues)
                else:
                    table.add_row(strategy_file.name, name, "Not validated", "")

        except Exception as e:
            table.add_row(strategy_file.name, "Error reading file", "❌ Error", str(e))

    console.print(table)

    if validate and verbose:
        console.print("\n[cyan]Detailed validation results:[/cyan]")
        console.print("=" * 60)

        for strategy_file in sorted(strategy_files):
            result = validator.validate_strategy(str(strategy_file))
            if not result.is_valid:
                console.print(f"\n📄 [blue]{strategy_file.name}[/blue]")
                if result.errors:
                    console.print(f"  [red]Errors:[/red]")
                    for error in result.errors[:3]:
                        console.print(f"    • {error}")
                    if len(result.errors) > 3:
                        console.print(f"    ... and {len(result.errors) - 3} more")


@strategies_app.command("backtest")
def backtest_strategy(
    strategy_file: str = typer.Argument(..., help="Path to strategy YAML file"),
    symbol: str = typer.Argument(..., help="Trading symbol (e.g., AAPL, MSFT)"),
    timeframe: str = typer.Argument(..., help="Data timeframe (e.g., 1d, 1h)"),
    start_date: str = typer.Option(
        ..., "--start-date", help="Backtest start date (YYYY-MM-DD)"
    ),
    end_date: str = typer.Option(
        ..., "--end-date", help="Backtest end date (YYYY-MM-DD)"
    ),
    initial_capital: float = typer.Option(
        100000.0, "--capital", help="Initial capital for backtesting"
    ),
    output_file: Optional[str] = typer.Option(
        None, "--output", "-o", help="Save results to file"
    ),
    data_mode: str = typer.Option(
        "local", "--data-mode", help="Data loading mode (local, ib)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show backtest plan without executing"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
):
    """
    Run backtesting on trading strategies.

    This command performs historical backtesting of trading strategies using
    market data and provides performance metrics and analysis.

    Examples:
        ktrdr strategies backtest strategies/neuro_mean_reversion.yaml AAPL 1h --start-date 2024-07-01 --end-date 2024-12-31
        ktrdr strategies backtest strategies/trend_momentum.yaml MSFT 1d --start-date 2023-01-01 --end-date 2024-01-01 --capital 50000
        ktrdr strategies backtest strategies/rsi_strategy.yaml TSLA 1h --dry-run --verbose
    """
    try:
        # Input validation
        strategy_path = Path(strategy_file)
        if not strategy_path.exists():
            raise ValidationError(
                message=f"Strategy file not found: {strategy_file}",
                error_code="VALIDATION-FileNotFound",
                details={"file": strategy_file},
            )

        symbol = InputValidator.validate_string(
            symbol, min_length=1, max_length=10, pattern=r"^[A-Za-z0-9\-\.]+$"
        )
        timeframe = InputValidator.validate_string(
            timeframe, min_length=1, max_length=5, pattern=r"^[0-9]+[dhm]$"
        )
        initial_capital = InputValidator.validate_numeric(
            initial_capital, min_value=1000.0, max_value=10000000.0
        )

        # Run async operation
        asyncio.run(
            _backtest_strategy_async(
                strategy_file,
                symbol,
                timeframe,
                start_date,
                end_date,
                initial_capital,
                output_file,
                data_mode,
                dry_run,
                verbose,
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


async def _backtest_strategy_async(
    strategy_file: str,
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    initial_capital: float,
    output_file: Optional[str],
    data_mode: str,
    dry_run: bool,
    verbose: bool,
):
    """Async implementation of backtest strategy command."""
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
                        status_result = await api_client.get_operation_status(backtest_id)
                        data = status_result.get("data", {})
                        status = data.get("status", "unknown")
                        progress_info = data.get("progress", {})
                        progress_pct = progress_info.get("percentage", 0)
                        
                        # Update progress bar with real progress
                        progress.update(task, completed=progress_pct, description=f"Status: {status}")
                        
                        if status == "completed":
                            console.print(f"✅ [green]Backtest completed successfully![/green]")
                            break
                        elif status == "failed":
                            error_msg = data.get("error_message", "Unknown error")
                            console.print(f"❌ [red]Backtest failed: {error_msg}[/red]")
                            return
                        
                        # Wait before next poll
                        await asyncio.sleep(2)
                        
                    except Exception as e:
                        console.print(f"❌ [red]Error polling backtest status: {str(e)}[/red]")
                        return
        finally:
            # Restore original httpx logging level
            httpx_logger.setLevel(original_level)

        # Get real results from API
        try:
            results = await api_client.get_backtest_results(backtest_id)
            metrics = results.get("metrics", {})
            summary = results.get("summary", {})
            
            # Display real results
            console.print(f"📊 [bold green]Backtest Results:[/bold green]")
            console.print(f"📈 Total return: {metrics.get('total_return', 0):.2f}")
            console.print(f"📊 Sharpe ratio: {metrics.get('sharpe_ratio', 0):.2f}")
            console.print(f"📉 Max drawdown: {metrics.get('max_drawdown', 0):.2f}%")
            console.print(f"🎯 Win rate: {metrics.get('win_rate', 0):.1f}%")
            console.print(f"🔢 Total trades: {metrics.get('total_trades', 0)}")
            console.print(f"💰 Final value: ${summary.get('final_value', 0):,.2f}")
            
            if output_file:
                # Save real results to file
                import json
                with open(output_file, 'w') as f:
                    json.dump(results, f, indent=2, default=str)
                console.print(f"💾 Results saved to: {output_file}")
                
        except Exception as e:
            console.print(f"❌ [red]Error retrieving results: {str(e)}[/red]")
            return

    except Exception as e:
        raise DataError(
            message=f"Failed to backtest strategy for {symbol}",
            error_code="CLI-BacktestError",
            details={
                "symbol": symbol,
                "timeframe": timeframe,
                "strategy": strategy_file,
                "error": str(e),
            },
        ) from e
