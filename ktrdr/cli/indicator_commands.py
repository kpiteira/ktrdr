"""
Indicator commands for the KTRDR CLI.

This module contains all CLI commands related to technical indicators:
- compute: Calculate indicators for market data
- plot: Generate charts with indicators
- list: Show available indicators
"""

import json
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ktrdr.cli.client import CLIClientError, SyncCLIClient
from ktrdr.cli.telemetry import trace_cli_command
from ktrdr.config.validation import InputValidator
from ktrdr.errors import ValidationError
from ktrdr.logging import get_logger

# Setup logging and console
logger = get_logger(__name__)
console = Console()
error_console = Console(stderr=True)

# Create the CLI app for indicator commands
indicators_app = typer.Typer(
    name="indicators",
    help="Technical indicator commands",
    no_args_is_help=True,
)


@indicators_app.command("compute")
@trace_cli_command("indicators_compute")
def compute_indicator(
    symbol: str = typer.Argument(..., help="Trading symbol (e.g., AAPL, MSFT)"),
    indicator_type: str = typer.Option(
        ..., "--type", "-t", help="Indicator type (RSI, SMA, EMA, etc.)"
    ),
    period: int = typer.Option(14, "--period", "-p", help="Period for the indicator"),
    timeframe: str = typer.Option(
        "1d", "--timeframe", help="Data timeframe (e.g., 1d, 1h)"
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, csv)"
    ),
    output_file: Optional[str] = typer.Option(
        None, "--output", "-o", help="Save output to file"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
):
    """
    Compute technical indicators for market data.

    This command calculates various technical indicators using the KTRDR API
    and displays the results in the specified format.

    Examples:
        ktrdr indicators compute AAPL --type RSI --period 14
        ktrdr indicators compute MSFT --type SMA --period 20 --format json
        ktrdr indicators compute TSLA --type MACD --output results.csv
    """
    try:
        # Input validation
        symbol = InputValidator.validate_string(
            symbol, min_length=1, max_length=10, pattern=r"^[A-Za-z0-9\-\.]+$"
        )
        indicator_type = InputValidator.validate_string(
            indicator_type, min_length=1, max_length=20
        )
        period = int(
            InputValidator.validate_numeric(period, min_value=1, max_value=1000)
        )

        with SyncCLIClient() as client:
            # Check API connection
            if not client.health_check():
                error_console.print(
                    "[bold red]Error:[/bold red] Could not connect to KTRDR API server"
                )
                error_console.print(
                    f"Make sure the API server is running at {client.config.base_url}"
                )
                sys.exit(1)

            if verbose:
                console.print(
                    f"🔢 Computing {indicator_type} for {symbol} (period={period})"
                )

            # Map user-friendly names to API indicator IDs
            indicator_mapping = {
                "RSI": "RSIIndicator",
                "SMA": "SimpleMovingAverage",
                "EMA": "ExponentialMovingAverage",
                "MACD": "MACDIndicator",
                "ZIGZAG": "ZigZagIndicator",
            }

            # Get the actual indicator ID
            indicator_id = indicator_mapping.get(indicator_type.upper())
            if not indicator_id:
                # Try the original name with "Indicator" suffix
                indicator_id = f"{indicator_type}Indicator"

            # Call the indicators API endpoint
            request_data = {
                "symbol": symbol,
                "timeframe": timeframe,
                "indicators": [
                    {
                        "id": indicator_id,
                        "parameters": {"period": period, "source": "close"},
                        "output_name": f"{indicator_type}_{period}",
                    }
                ],
            }

            result = client.post("/indicators/calculate", json=request_data)

            if verbose:
                console.print(f"[dim]Request: {request_data}[/dim]")

            if result.get("success"):
                # API returns indicators directly, not nested in 'data'
                indicator_data = result.get("indicators", {})
                timestamps = result.get("dates", [])

                if indicator_data:
                    # Format output
                    if output_format == "json":
                        if output_file:
                            with open(output_file, "w") as f:
                                json.dump(result, f, indent=2)
                            console.print(f"💾 Results saved to {output_file}")
                        else:
                            print(json.dumps(result, indent=2))
                    elif output_format == "csv":
                        # Convert to CSV format
                        import pandas as pd

                        # Extract the indicator values (API uses lowercase with underscore)
                        indicator_name = f"{indicator_type.lower()}_{period}"
                        if indicator_name in indicator_data:
                            values = indicator_data[indicator_name]

                            df = pd.DataFrame(
                                {"timestamp": timestamps, indicator_name: values}
                            )

                            if output_file:
                                df.to_csv(output_file, index=False)
                                console.print(f"💾 Results saved to {output_file}")
                            else:
                                print(df.to_csv(index=False))
                    else:
                        # Table format (API uses lowercase with underscore)
                        indicator_name = f"{indicator_type.lower()}_{period}"
                        if indicator_name in indicator_data:
                            values = indicator_data[indicator_name]

                            console.print(
                                f"\n📊 [bold]{indicator_type} Results for {symbol}[/bold]"
                            )
                            console.print(f"Period: {period} | Timeframe: {timeframe}")
                            console.print(f"Total points: {len(values)}")
                            console.print()

                            table = Table()
                            table.add_column("Timestamp", style="cyan")
                            table.add_column(
                                indicator_name, style="green", justify="right"
                            )

                            # Show last 20 values
                            recent_data = list(zip(timestamps[-20:], values[-20:]))
                            for timestamp, value in recent_data:
                                if value is not None:
                                    table.add_row(timestamp[:19], f"{value:.4f}")
                                else:
                                    table.add_row(timestamp[:19], "N/A")

                            console.print(table)

                            if len(values) > 20:
                                console.print(
                                    f"\n[dim]Showing last 20 of {len(values)} values[/dim]"
                                )

                            if output_file:
                                # Also save to file if requested
                                import pandas as pd

                                df = pd.DataFrame(
                                    {"timestamp": timestamps, indicator_name: values}
                                )
                                df.to_csv(output_file, index=False)
                                console.print(f"💾 Full results saved to {output_file}")
                else:
                    console.print("[yellow]⚠️  No indicator data returned[/yellow]")
            else:
                error_msg = result.get("message", "Unknown error")
                console.print(f"[red]❌ Error: {error_msg}[/red]")
                sys.exit(1)

    except ValidationError as e:
        error_console.print(f"[bold red]Validation error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Validation error: {str(e)}")
        sys.exit(1)
    except CLIClientError as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Client error: {str(e)}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)


@indicators_app.command("plot")
@trace_cli_command("indicators_plot")
def plot_chart(
    symbol: str = typer.Argument(..., help="Trading symbol (e.g., AAPL, MSFT)"),
    timeframe: str = typer.Option(
        "1d", "--timeframe", "-t", help="Data timeframe (e.g., 1d, 1h)"
    ),
    indicator: Optional[str] = typer.Option(
        None, "--indicator", "-i", help="Indicator to overlay"
    ),
    period: int = typer.Option(14, "--period", "-p", help="Period for the indicator"),
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
    Generate charts with technical indicators.

    This command creates interactive charts using the KTRDR visualization system
    with optional technical indicator overlays.

    Examples:
        ktrdr indicators plot AAPL --indicator SMA --period 20
        ktrdr indicators plot MSFT --timeframe 1h --output chart.html
        ktrdr indicators plot TSLA --indicator RSI --period 14 --no-show
    """
    try:
        # Input validation
        symbol = InputValidator.validate_string(
            symbol, min_length=1, max_length=10, pattern=r"^[A-Za-z0-9\-\.]+$"
        )
        period = int(
            InputValidator.validate_numeric(period, min_value=1, max_value=1000)
        )

        with SyncCLIClient() as client:
            # Check API connection
            if not client.health_check():
                error_console.print(
                    "[bold red]Error:[/bold red] Could not connect to KTRDR API server"
                )
                error_console.print(
                    f"Make sure the API server is running at {client.config.base_url}"
                )
                sys.exit(1)

            if verbose:
                console.print(f"📈 Generating chart for {symbol} ({timeframe})")
                if indicator:
                    console.print(f"📊 Including indicator: {indicator}({period})")

            # This would call the visualization API endpoint
            # For now, show a placeholder message
            console.print(
                "⚠️  [yellow]Chart generation via API not yet implemented[/yellow]"
            )
            console.print(f"📋 Would generate chart for: {symbol} on {timeframe}")

            if indicator:
                console.print(f"📊 With indicator: {indicator}({period})")

            if output_file:
                console.print(f"💾 Would save chart to: {output_file}")

            if show:
                console.print("🌐 Would open chart in browser")

    except ValidationError as e:
        error_console.print(f"[bold red]Validation error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Validation error: {str(e)}")
        sys.exit(1)
    except CLIClientError as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Client error: {str(e)}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)


@indicators_app.command("list")
@trace_cli_command("indicators_list")
def list_indicators(
    category: Optional[str] = typer.Option(
        None, "--category", "-c", help="Filter by category"
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
):
    """
    List available technical indicators.

    Shows all available indicators that can be used with the compute and plot commands,
    including their parameters and descriptions.

    Examples:
        ktrdr indicators list
        ktrdr indicators list --category trend
        ktrdr indicators list --format json
    """
    try:
        with SyncCLIClient() as client:
            # Check API connection
            if not client.health_check():
                error_console.print(
                    "[bold red]Error:[/bold red] Could not connect to KTRDR API server"
                )
                error_console.print(
                    f"Make sure the API server is running at {client.config.base_url}"
                )
                sys.exit(1)

            if verbose:
                console.print("📋 Retrieving available indicators")

            # Call the indicators API endpoint
            result = client.get("/indicators/")

            if result.get("success"):
                data_obj = result.get("data", {})
                if isinstance(data_obj, list):
                    # API returns a list directly
                    indicators_data = data_obj
                else:
                    # API returns an object with indicators key
                    indicators_data = data_obj.get("indicators", [])

                # Transform API response to simpler format for display
                indicators = []
                for ind in indicators_data:
                    # Convert parameters list to dict for easier handling
                    params_dict = {}
                    for param in ind.get("parameters", []):
                        params_dict[param.get("name", "")] = {
                            "type": param.get("type", ""),
                            "default": param.get("default", "N/A"),
                            "description": param.get("description", ""),
                        }

                    indicators.append(
                        {
                            "name": ind.get("name", "").replace(
                                "Indicator", ""
                            ),  # Remove "Indicator" suffix
                            "category": ind.get(
                                "type", "unknown"
                            ),  # API uses "type" not "category"
                            "description": ind.get(
                                "description", ""
                            ).strip(),  # Clean whitespace
                            "parameters": params_dict,
                        }
                    )

                # Filter by category if specified
                if category:
                    indicators = [
                        ind
                        for ind in indicators
                        if ind["category"].lower() == category.lower()
                    ]

                # Format output
                if output_format == "json":
                    result_data = {
                        "indicators": indicators,
                        "total_count": len(indicators),
                        "category_filter": category,
                    }
                    print(json.dumps(result_data, indent=2))
                else:
                    # Table format
                    console.print("\n📊 [bold]Available Technical Indicators[/bold]")
                    if category:
                        console.print(f"Category: {category}")
                    console.print(f"Total: {len(indicators)}")
                    console.print()

                    table = Table()
                    table.add_column("Name", style="cyan")
                    table.add_column("Category", style="green")
                    table.add_column("Description", style="white")
                    if verbose:
                        table.add_column("Parameters", style="dim")

                    for indicator in indicators:
                        row = [
                            indicator["name"],
                            indicator["category"],
                            indicator["description"],
                        ]
                        if verbose:
                            params = indicator.get("parameters", {})
                            param_str = ", ".join(
                                [
                                    f"{k}: {v.get('default', 'N/A')}"
                                    for k, v in params.items()
                                ]
                            )
                            row.append(
                                param_str[:50] + "..."
                                if len(param_str) > 50
                                else param_str
                            )

                        table.add_row(*row)

                    console.print(table)

                if verbose:
                    console.print(f"✅ Listed {len(indicators)} indicators")
            else:
                error_msg = result.get("message", "Failed to retrieve indicators")
                console.print(f"[red]❌ Error: {error_msg}[/red]")
                sys.exit(1)

    except CLIClientError as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Client error: {str(e)}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)
