"""
Strategy management commands for the KTRDR CLI.

This module contains essential CLI commands related to trading strategies:
- validate: Validate strategy configurations
- list: List available strategies
- backtest: Run backtesting on strategies
- validate-all: Validate all strategies in a directory
"""

import asyncio
import shutil
import sys
from pathlib import Path
from typing import Optional

import typer
import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from ktrdr.cli.api_client import check_api_connection, get_api_client
from ktrdr.cli.commands import get_effective_api_url
from ktrdr.cli.telemetry import trace_cli_command
from ktrdr.config.strategy_loader import strategy_loader
from ktrdr.config.strategy_migration import migrate_v2_to_v3, validate_migration
from ktrdr.config.strategy_validator import StrategyValidator
from ktrdr.config.validation import InputValidator
from ktrdr.logging import get_logger

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
@trace_cli_command("strategies_validate")
def validate_strategy(
    strategy: str = typer.Argument(..., help="Path to strategy YAML file"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal output"),
):
    """
    Validate a trading strategy configuration.

    Checks if a strategy YAML file has all required sections and valid configuration
    for neuro-fuzzy training. Supports both v2 and v3 strategy formats.

    For v3 strategies, displays the resolved NN input features.
    """
    strategy_path = Path(strategy)
    if not strategy_path.exists():
        console.print(f"[red]❌ Error: Strategy file not found: {strategy_path}[/red]")
        raise typer.Exit(1)

    # Try to detect if v3 format
    try:
        import yaml

        with open(strategy_path) as f:
            raw_config = yaml.safe_load(f)

        is_v3 = (
            isinstance(raw_config, dict)
            and isinstance(raw_config.get("indicators"), dict)
            and "nn_inputs" in raw_config
        )
    except Exception as e:
        console.print(f"[red]❌ Error reading strategy file: {e}[/red]")
        raise typer.Exit(1) from e

    if is_v3:
        # Use v3 validation path
        _validate_v3_strategy(strategy_path, quiet)
    else:
        # Use v2 validation path
        _validate_v2_strategy(strategy_path, quiet)


def _validate_v3_strategy(strategy_path: Path, quiet: bool) -> None:
    """
    Validate a v3 strategy and display resolved features.

    Args:
        strategy_path: Path to v3 strategy file
        quiet: Whether to minimize output
    """
    from ktrdr.config.feature_resolver import FeatureResolver
    from ktrdr.config.strategy_loader import StrategyConfigurationLoader
    from ktrdr.config.strategy_validator import StrategyValidationError

    if not quiet:
        console.print(f"🔍 Validating v3 strategy: [blue]{strategy_path}[/blue]")
        console.print("=" * 60)

    try:
        # Load and validate
        loader = StrategyConfigurationLoader()
        config = loader.load_v3_strategy(strategy_path)

        # Resolve features
        resolver = FeatureResolver()
        features = resolver.resolve(config)

        # Display success
        if quiet:
            console.print(f"✅ {config.name}: valid ({len(features)} features)")
        else:
            console.print(
                f"[green]✅ Strategy '{config.name}' is valid (v3 format)[/green]"
            )
            console.print(f"\n[cyan]📊 Resolved features ({len(features)}):[/cyan]")
            for feature in features:
                console.print(f"  {feature.feature_id}")

            console.print("\n" + "=" * 60)
            console.print("[bold green]✅ Validation successful[/bold green]")

    except FileNotFoundError as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(1) from e
    except ValueError as e:
        # Format detection or YAML errors
        error_msg = str(e)
        console.print(f"[red]❌ Error: {error_msg}[/red]")
        raise typer.Exit(1) from e
    except StrategyValidationError as e:
        console.print("[red]❌ Strategy validation failed:[/red]")
        console.print(f"  {e}")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[red]❌ Unexpected error: {e}[/red]")
        logger.exception("Unexpected error during v3 strategy validation")
        raise typer.Exit(1) from e


def _validate_v2_strategy(strategy_path: Path, quiet: bool) -> None:
    """
    Validate a v2 strategy using the legacy validator.

    Args:
        strategy_path: Path to v2 strategy file
        quiet: Whether to minimize output
    """
    validator = StrategyValidator()

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
@trace_cli_command("strategies_list")
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
    console.print("📊 [bold]Summary:[/bold]")
    console.print(f"   [green]✅ Valid: {len(valid_strategies)}[/green]")
    console.print(f"   [red]❌ Invalid: {len(invalid_strategies)}[/red]")
    console.print(f"   Total: {len(strategy_files)}")

    if invalid_strategies:
        console.print("\n[red]❌ Invalid strategies:[/red]")
        for strategy in invalid_strategies:
            console.print(f"   • {strategy}")


@strategies_app.command("backtest")
@trace_cli_command("strategies_backtest")
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
    try:
        InputValidator.validate_string(
            symbol, min_length=1, max_length=10, pattern=r"^[A-Za-z0-9\-\.]+$"
        )
    except ValidationError as e:
        console.print(f"[red]❌ Error: Invalid symbol format: {symbol}[/red]")
        raise typer.Exit(1) from e

    try:
        InputValidator.validate_string(
            timeframe, min_length=1, max_length=5, pattern=r"^[0-9]+[dhm]$"
        )
    except ValidationError as e:
        console.print(f"[red]❌ Error: Invalid timeframe: {timeframe}[/red]")
        console.print("Valid timeframes: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w")
        raise typer.Exit(1) from e

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
                f"Make sure the API server is running at {get_effective_api_url()}"
            )
            sys.exit(1)

        api_client = get_api_client()

        if verbose:
            console.print(f"📈 Backtesting strategy for {symbol} ({timeframe})")
            console.print(f"📋 Strategy: {strategy_file}")
            console.print(f"📅 Period: {start_date} to {end_date}")
            console.print(f"💰 Initial capital: ${initial_capital:,.2f}")

        if dry_run:
            console.print("🔍 [yellow]DRY RUN - No backtest will be executed[/yellow]")
            console.print(f"📋 Would backtest: {symbol} on {timeframe}")
            console.print(f"📊 Strategy: {strategy_file}")
            console.print(f"💰 Capital: ${initial_capital:,.2f}")
            console.print(f"📅 Period: {start_date} to {end_date}")
            return

        # Call the real backtesting API endpoint
        console.print("🚀 [cyan]Starting backtest via API...[/cyan]")
        console.print("📋 Backtest parameters:")
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
                                "✅ [green]Backtest completed successfully![/green]"
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
                console.print("\n📊 [bold green]Backtest Results:[/bold green]")
                console.print(f"   Total Return: {results.get('total_return', 'N/A')}")
                console.print(f"   Sharpe Ratio: {results.get('sharpe_ratio', 'N/A')}")
                console.print(f"   Max Drawdown: {results.get('max_drawdown', 'N/A')}")
                console.print(f"   Total Trades: {results.get('total_trades', 'N/A')}")
                console.print(f"   Win Rate: {results.get('win_rate', 'N/A')}")
            else:
                console.print("[yellow]⚠️  Results not yet available[/yellow]")

        except Exception as e:
            console.print(f"[yellow]⚠️  Could not retrieve results: {str(e)}[/yellow]")

    except Exception as e:
        console.print(f"❌ [red]Backtest failed: {str(e)}[/red]")
        sys.exit(1)


@strategies_app.command("validate-all")
@trace_cli_command("strategies_validate-all")
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
                        "\n[red]💥 Stopping on first error (--fail-fast)[/red]"
                    )
                    break

        except Exception as e:
            invalid_count += 1
            if not summary_only:
                console.print(
                    f"[red]❌[/red] {file_path.name} (validation failed: {e})"
                )

            if fail_fast:
                console.print("\n[red]💥 Stopping on first error (--fail-fast)[/red]")
                break

    # Summary
    total = valid_count + invalid_count
    success_rate = (valid_count / total * 100) if total > 0 else 0

    console.print("\n" + "=" * 60)
    console.print("[bold]📊 Validation Summary:[/bold]")
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
        console.print("\n[green]🎉 All strategies are valid![/green]")


@strategies_app.command("migrate")
@trace_cli_command("strategies_migrate")
def migrate_strategy(
    path: str = typer.Argument(..., help="Path to strategy file or directory"),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output path (default: overwrite in place)"
    ),
    backup: bool = typer.Option(
        False, "--backup", help="Create .bak backup before overwriting"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would change without writing"
    ),
):
    """
    Migrate v2 strategy to v3 format.

    Converts v2 strategy configurations (list-based indicators) to v3 format
    (dict-based indicators with nn_inputs).

    Can process a single file or all YAML files in a directory.
    """
    input_path = Path(path)

    if not input_path.exists():
        console.print(f"[red]❌ Error: Path not found: {input_path}[/red]")
        raise typer.Exit(1)

    # Handle directory or file
    if input_path.is_dir():
        files = list(input_path.glob("*.yaml")) + list(input_path.glob("*.yml"))
        files = [f for f in files if not f.name.startswith(".")]
    else:
        files = [input_path]

    if not files:
        console.print(f"[yellow]📭 No strategy files found in {input_path}[/yellow]")
        return

    for file_path in files:
        _migrate_single_file(file_path, output, backup, dry_run)


def _migrate_single_file(
    file_path: Path,
    output: Optional[str],
    backup: bool,
    dry_run: bool,
) -> None:
    """
    Migrate a single strategy file from v2 to v3 format.

    Args:
        file_path: Path to the strategy file
        output: Optional output path
        backup: Whether to create backup
        dry_run: Whether to only show changes without writing
    """
    console.print(f"\n🔍 Processing: [blue]{file_path}[/blue]")

    try:
        with open(file_path) as f:
            original = yaml.safe_load(f)
    except Exception as e:
        console.print(f"  [red]❌ Error reading file: {e}[/red]")
        return

    if not isinstance(original, dict):
        console.print("  [red]❌ Invalid YAML: not a dictionary[/red]")
        return

    # Check if already v3
    if isinstance(original.get("indicators"), dict) and "nn_inputs" in original:
        console.print("  [yellow]⏭️  Already v3 format, skipping[/yellow]")
        return

    # Migrate
    migrated = migrate_v2_to_v3(original)

    # Validate migration
    issues = validate_migration(original, migrated)
    for issue in issues:
        console.print(f"  [yellow]⚠️  Warning: {issue}[/yellow]")

    if dry_run:
        console.print("  [cyan][Dry run] Would migrate to v3:[/cyan]")
        # Show diff preview
        orig_ind_count = len(original.get("indicators", []))
        migrated_ind_count = len(migrated.get("indicators", {}))
        console.print(
            f"    Indicators: list[{orig_ind_count}] -> dict[{migrated_ind_count}]"
        )
        console.print(f"    NN Inputs: {len(migrated.get('nn_inputs', []))} entries")
        return

    # Determine output path
    out_path = Path(output) if output else file_path

    # Create parent directories if needed
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Backup if requested and overwriting in place
    if backup and out_path == file_path:
        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        shutil.copy(file_path, backup_path)
        console.print(f"  📦 Backup created: {backup_path}")

    # Write migrated config
    with open(out_path, "w") as f:
        yaml.dump(migrated, f, default_flow_style=False, sort_keys=False)

    console.print(f"  ✅ Migrated to: {out_path}")

    # Validate the result
    try:
        from ktrdr.config.strategy_loader import StrategyConfigurationLoader

        loader = StrategyConfigurationLoader()
        loader.load_v3_strategy(out_path)
        console.print("  ✅ Validation: [green]PASSED[/green]")
    except Exception as e:
        console.print(f"  ⚠️  Validation: [yellow]WARNING - {e}[/yellow]")


@strategies_app.command("features")
@trace_cli_command("strategies_features")
def list_features(
    path: str = typer.Argument(..., help="Path to v3 strategy YAML file"),
    group_by: str = typer.Option(
        "none",
        "--group-by",
        help="Group features by attribute",
        case_sensitive=False,
    ),
):
    """
    List generated NN input features for a v3 strategy.

    Displays the resolved features that will be used as neural network inputs
    based on the strategy's nn_inputs configuration.

    Features can be grouped by:
    - none: Flat list of all features (default)
    - timeframe: Group features by their timeframe
    - fuzzy_set: Group features by their fuzzy set
    """
    from ktrdr.config.feature_resolver import FeatureResolver
    from ktrdr.config.strategy_loader import StrategyConfigurationLoader

    strategy_path = Path(path)
    if not strategy_path.exists():
        console.print(f"[red]❌ Error: Strategy file not found: {strategy_path}[/red]")
        raise typer.Exit(1)

    # Validate group_by option
    valid_group_options = {"none", "timeframe", "fuzzy_set"}
    if group_by.lower() not in valid_group_options:
        console.print(f"[red]❌ Error: Invalid --group-by option: {group_by}[/red]")
        console.print(f"Valid options: {', '.join(valid_group_options)}")
        raise typer.Exit(1)

    group_by = group_by.lower()

    # Load strategy - must be v3 format
    try:
        loader = StrategyConfigurationLoader()
        config = loader.load_v3_strategy(strategy_path)
    except FileNotFoundError as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(1) from e
    except ValueError as e:
        # v2 format or invalid YAML
        error_msg = str(e)
        console.print(f"[red]❌ Error: {error_msg}[/red]")
        console.print(
            "[yellow]This command requires v3 format. "
            "Use 'ktrdr strategies migrate' to convert v2 strategies.[/yellow]"
        )
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[red]❌ Error loading strategy: {e}[/red]")
        raise typer.Exit(1) from e

    # Resolve features
    resolver = FeatureResolver()
    features = resolver.resolve(config)

    # Display header
    console.print(f"Strategy: [cyan]{config.name}[/cyan]")
    console.print(f"Features ({len(features)} total):")
    console.print()

    if group_by == "none":
        _display_features_flat(features)
    elif group_by == "timeframe":
        _display_features_by_timeframe(features)
    elif group_by == "fuzzy_set":
        _display_features_by_fuzzy_set(features, config)


def _display_features_flat(features: list) -> None:
    """Display features in a flat list."""
    for f in features:
        console.print(f"  {f.feature_id}")


def _display_features_by_timeframe(features: list) -> None:
    """Display features grouped by timeframe."""
    by_tf: dict[str, list] = {}
    for f in features:
        by_tf.setdefault(f.timeframe, []).append(f)

    for tf in sorted(by_tf.keys()):
        console.print(f"  [bold][{tf}][/bold]")
        for f in by_tf[tf]:
            console.print(f"    {f.fuzzy_set_id}_{f.membership_name}")
        console.print()


def _display_features_by_fuzzy_set(features: list, config) -> None:
    """Display features grouped by fuzzy set."""
    by_fs: dict[str, list] = {}
    for f in features:
        by_fs.setdefault(f.fuzzy_set_id, []).append(f)

    for fs_id in by_fs.keys():
        indicator = config.fuzzy_sets[fs_id].indicator
        # Use escape sequences so Rich doesn't interpret brackets as markup
        console.print(f"  [bold]\\[{fs_id}][/bold] -> {indicator}")
        for f in by_fs[fs_id]:
            console.print(f"    {f.timeframe}_{f.membership_name}")
        console.print()
