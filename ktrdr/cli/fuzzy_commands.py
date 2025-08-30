"""
Fuzzy logic commands for the KTRDR CLI.

This module contains all CLI commands related to fuzzy logic operations:
- compute: Calculate fuzzy membership functions
- visualize: Generate fuzzy logic visualizations
- config: Manage fuzzy configuration
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ktrdr.cli.api_client import check_api_connection, get_api_client
from ktrdr.config.validation import InputValidator
from ktrdr.errors import DataError, ValidationError
from ktrdr.logging import get_logger

# Setup logging and console
logger = get_logger(__name__)
console = Console()
error_console = Console(stderr=True)

# Create the CLI app for fuzzy commands
fuzzy_app = typer.Typer(
    name="fuzzy",
    help="Fuzzy logic operations commands",
    no_args_is_help=True,
)


@fuzzy_app.command("compute")
def compute_fuzzy(
    symbol: str = typer.Argument(..., help="Trading symbol (e.g., AAPL, MSFT)"),
    indicator: str = typer.Option(
        ..., "--indicator", "-i", help="Indicator for fuzzy analysis (RSI, SMA, etc.)"
    ),
    period: int = typer.Option(14, "--period", "-p", help="Period for the indicator"),
    timeframe: str = typer.Option(
        "1d", "--timeframe", help="Data timeframe (e.g., 1d, 1h)"
    ),
    fuzzy_config: Optional[str] = typer.Option(
        None, "--config", help="Path to fuzzy configuration file"
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json)"
    ),
    output_file: Optional[str] = typer.Option(
        None, "--output", "-o", help="Save output to file"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
):
    """
    Calculate fuzzy membership functions for market indicators.

    This command applies fuzzy logic analysis to technical indicators,
    computing membership degrees for linguistic variables like "high", "medium", "low".

    Examples:
        ktrdr fuzzy compute AAPL --indicator RSI --period 14
        ktrdr fuzzy compute MSFT --indicator SMA --period 20 --config custom_fuzzy.yaml
        ktrdr fuzzy compute TSLA --indicator MACD --output fuzzy_results.json
    """
    try:
        # Input validation
        symbol = InputValidator.validate_string(
            symbol, min_length=1, max_length=10, pattern=r"^[A-Za-z0-9\-\.]+$"
        )
        indicator = InputValidator.validate_string(
            indicator, min_length=1, max_length=20
        )
        period = int(InputValidator.validate_numeric(period, min_value=1, max_value=1000))

        if fuzzy_config:
            config_path = Path(fuzzy_config)
            if not config_path.exists():
                raise ValidationError(
                    message=f"Fuzzy config file not found: {fuzzy_config}",
                    error_code="VALIDATION-FileNotFound",
                    details={"file": fuzzy_config},
                )

        # Run async operation
        asyncio.run(
            _compute_fuzzy_async(
                symbol,
                indicator,
                period,
                timeframe,
                fuzzy_config,
                output_format,
                output_file,
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


async def _compute_fuzzy_async(
    symbol: str,
    indicator: str,
    period: int,
    timeframe: str,
    fuzzy_config: Optional[str],
    output_format: str,
    output_file: Optional[str],
    verbose: bool,
):
    """Async implementation of compute fuzzy command."""
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
            console.print(f"🔮 Computing fuzzy values for {indicator} on {symbol}")
            console.print(f"📊 Period: {period} | Timeframe: {timeframe}")
            if fuzzy_config:
                console.print(f"⚙️  Config: {fuzzy_config}")

        # Call the fuzzy API endpoint
        request_data = {
            "symbol": symbol,
            "timeframe": timeframe,
            "indicator": {"type": indicator, "period": period},
        }

        if fuzzy_config:
            request_data["config_file"] = fuzzy_config

        result = await api_client.post("/fuzzy/calculate", json=request_data)

        if result.get("success"):
            data = result.get("data", {})

            # Format output
            if output_format == "json":
                if output_file:
                    import json

                    with open(output_file, "w") as f:
                        json.dump(result, f, indent=2)
                    console.print(f"💾 Results saved to {output_file}")
                else:
                    print(json.dumps(result, indent=2))
            else:
                # Table format
                fuzzy_values = data.get("fuzzy_values", {})
                timestamps = data.get("timestamps", [])

                console.print(f"\n🔮 [bold]Fuzzy Analysis Results for {symbol}[/bold]")
                console.print(
                    f"Indicator: {indicator}({period}) | Timeframe: {timeframe}"
                )

                if fuzzy_values:
                    table = Table()
                    table.add_column("Timestamp", style="cyan")
                    table.add_column("Indicator Value", style="blue", justify="right")

                    # Add fuzzy membership columns
                    for fuzzy_set in fuzzy_values.keys():
                        table.add_column(f"{fuzzy_set}", style="green", justify="right")

                    # Show last 20 values
                    indicator_values = data.get("indicator_values", [])
                    recent_count = min(20, len(timestamps))

                    for i in range(-recent_count, 0):
                        if i < -len(timestamps):
                            continue

                        timestamp = timestamps[i]
                        indicator_val = (
                            indicator_values[i] if i < len(indicator_values) else None
                        )

                        row = [timestamp[:19]]
                        if indicator_val is not None:
                            row.append(f"{indicator_val:.4f}")
                        else:
                            row.append("N/A")

                        # Add fuzzy membership values
                        for fuzzy_set in fuzzy_values.keys():
                            fuzzy_vals = fuzzy_values[fuzzy_set]
                            if i < len(fuzzy_vals) and fuzzy_vals[i] is not None:
                                row.append(f"{fuzzy_vals[i]:.3f}")
                            else:
                                row.append("N/A")

                        table.add_row(*row)

                    console.print(table)

                    if len(timestamps) > 20:
                        console.print(
                            f"\n[dim]Showing last 20 of {len(timestamps)} values[/dim]"
                        )

                    if output_file:
                        # Save to CSV
                        import pandas as pd

                        df_data = {"timestamp": timestamps}
                        if indicator_values:
                            df_data[f"{indicator}_{period}"] = indicator_values
                        for fuzzy_set, values in fuzzy_values.items():
                            df_data[f"fuzzy_{fuzzy_set}"] = values

                        df = pd.DataFrame(df_data)
                        df.to_csv(output_file, index=False)
                        console.print(f"💾 Results saved to {output_file}")
                else:
                    console.print("[yellow]⚠️  No fuzzy values returned[/yellow]")
        else:
            error_msg = result.get("message", "Unknown error")
            console.print(f"[red]❌ Error: {error_msg}[/red]")
            sys.exit(1)

    except Exception as e:
        raise DataError(
            message=f"Failed to compute fuzzy values for {symbol}",
            error_code="CLI-ComputeFuzzyError",
            details={"symbol": symbol, "indicator": indicator, "error": str(e)},
        ) from e


@fuzzy_app.command("visualize")
def visualize_fuzzy(
    symbol: str = typer.Argument(..., help="Trading symbol (e.g., AAPL, MSFT)"),
    indicator: str = typer.Option(
        ..., "--indicator", "-i", help="Indicator for fuzzy visualization"
    ),
    period: int = typer.Option(14, "--period", "-p", help="Period for the indicator"),
    timeframe: str = typer.Option(
        "1d", "--timeframe", help="Data timeframe (e.g., 1d, 1h)"
    ),
    fuzzy_config: Optional[str] = typer.Option(
        None, "--config", help="Path to fuzzy configuration file"
    ),
    output_file: Optional[str] = typer.Option(
        None, "--output", "-o", help="Save chart to file"
    ),
    show: bool = typer.Option(
        True, "--show/--no-show", help="Display chart in browser"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
):
    """
    Generate fuzzy logic visualizations.

    This command creates interactive charts showing fuzzy membership functions,
    rule evaluations, and fuzzy inference results overlaid on market data.

    Examples:
        ktrdr fuzzy visualize AAPL --indicator RSI --period 14
        ktrdr fuzzy visualize MSFT --indicator SMA --config custom_fuzzy.yaml --output fuzzy_chart.html
        ktrdr fuzzy visualize TSLA --indicator MACD --no-show
    """
    try:
        # Input validation
        symbol = InputValidator.validate_string(
            symbol, min_length=1, max_length=10, pattern=r"^[A-Za-z0-9\-\.]+$"
        )
        indicator = InputValidator.validate_string(
            indicator, min_length=1, max_length=20
        )
        period = int(InputValidator.validate_numeric(period, min_value=1, max_value=1000))

        if fuzzy_config:
            config_path = Path(fuzzy_config)
            if not config_path.exists():
                raise ValidationError(
                    message=f"Fuzzy config file not found: {fuzzy_config}",
                    error_code="VALIDATION-FileNotFound",
                    details={"file": fuzzy_config},
                )

        # Run async operation
        asyncio.run(
            _visualize_fuzzy_async(
                symbol,
                indicator,
                period,
                timeframe,
                fuzzy_config,
                output_file,
                show,
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


async def _visualize_fuzzy_async(
    symbol: str,
    indicator: str,
    period: int,
    timeframe: str,
    fuzzy_config: Optional[str],
    output_file: Optional[str],
    show: bool,
    verbose: bool,
):
    """Async implementation of visualize fuzzy command."""
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

        get_api_client()

        if verbose:
            console.print(f"📈 Generating fuzzy visualization for {symbol}")
            console.print(
                f"📊 Indicator: {indicator}({period}) | Timeframe: {timeframe}"
            )
            if fuzzy_config:
                console.print(f"⚙️  Config: {fuzzy_config}")

        # This would call the fuzzy visualization API endpoint
        # For now, show a placeholder message
        console.print(
            "⚠️  [yellow]Fuzzy visualization via API not yet implemented[/yellow]"
        )
        console.print("📋 Would generate fuzzy chart for:")
        console.print(f"   Symbol: {symbol}")
        console.print(f"   Indicator: {indicator}({period})")
        console.print(f"   Timeframe: {timeframe}")

        if fuzzy_config:
            console.print(f"   Config: {fuzzy_config}")

        if output_file:
            console.print(f"💾 Would save chart to: {output_file}")

        if show:
            console.print("🌐 Would open chart in browser")

    except Exception as e:
        raise DataError(
            message=f"Failed to generate fuzzy visualization for {symbol}",
            error_code="CLI-FuzzyVisualizeError",
            details={"symbol": symbol, "indicator": indicator, "error": str(e)},
        ) from e


@fuzzy_app.command("config")
def manage_config(
    action: str = typer.Argument(
        ..., help="Action to perform (validate, generate, upgrade)"
    ),
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to fuzzy config file"
    ),
    output_file: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file for generated config"
    ),
    template: str = typer.Option(
        "default", "--template", help="Template for config generation"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
):
    """
    Manage fuzzy logic configuration files.

    This command provides utilities for validating, generating, and upgrading
    fuzzy logic configuration files used by the KTRDR fuzzy engine.

    Examples:
        ktrdr fuzzy config validate --config config/fuzzy.yaml
        ktrdr fuzzy config generate --template advanced --output my_fuzzy.yaml
        ktrdr fuzzy config upgrade --config old_fuzzy.yaml --output upgraded_fuzzy.yaml
    """
    try:
        valid_actions = ["validate", "generate", "upgrade"]
        if action not in valid_actions:
            raise ValidationError(
                message=f"Invalid action '{action}'. Must be one of: {', '.join(valid_actions)}",
                error_code="VALIDATION-InvalidAction",
                details={"action": action, "valid_actions": valid_actions},
            )

        if action in ["validate", "upgrade"] and not config_file:
            raise ValidationError(
                message=f"Config file is required for action '{action}'",
                error_code="VALIDATION-MissingConfig",
                details={"action": action},
            )

        if config_file:
            config_path = Path(config_file)
            if not config_path.exists():
                raise ValidationError(
                    message=f"Config file not found: {config_file}",
                    error_code="VALIDATION-FileNotFound",
                    details={"file": config_file},
                )

        # Run async operation
        asyncio.run(
            _manage_config_async(action, config_file, output_file, template, verbose)
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


async def _manage_config_async(
    action: str,
    config_file: Optional[str],
    output_file: Optional[str],
    template: str,
    verbose: bool,
):
    """Async implementation of manage config command."""
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

        get_api_client()

        if verbose:
            console.print(f"⚙️  Managing fuzzy config: {action}")
            if config_file:
                console.print(f"📋 Config file: {config_file}")

        if action == "validate":
            console.print(
                "✅ [green]Fuzzy config validation would be performed[/green]"
            )
            console.print(f"📋 Config file: {config_file}")

        elif action == "generate":
            console.print(
                "🔧 [yellow]Fuzzy config generation not yet implemented[/yellow]"
            )
            console.print(f"📋 Would generate config with template: {template}")
            if output_file:
                console.print(f"💾 Would save to: {output_file}")

        elif action == "upgrade":
            console.print(
                "⬆️  [yellow]Fuzzy config upgrade not yet implemented[/yellow]"
            )
            console.print(f"📋 Would upgrade: {config_file}")
            if output_file:
                console.print(f"💾 Would save to: {output_file}")

    except Exception as e:
        raise DataError(
            message="Failed to manage fuzzy config",
            error_code="CLI-FuzzyConfigError",
            details={"action": action, "config_file": config_file, "error": str(e)},
        ) from e
