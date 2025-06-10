"""
CLI commands for KTRDR application.

This module defines the CLI commands for interacting with the KTRDR application.
"""

import sys
import json
import yaml
import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

import typer
import pandas as pd
from rich.console import Console
from rich.table import Table

from ktrdr import get_logger
from ktrdr.data.local_data_loader import LocalDataLoader
from ktrdr.data.data_manager import DataManager
from ktrdr.config.validation import InputValidator
from ktrdr.config.models import IndicatorConfig, IndicatorsConfig
from ktrdr.indicators import IndicatorFactory, BaseIndicator
from ktrdr.errors import DataError, ValidationError, ConfigurationError
from ktrdr.visualization import Visualizer
from ktrdr.fuzzy.config import FuzzyConfigLoader, FuzzyConfig
from ktrdr.fuzzy.engine import FuzzyEngine
from ktrdr.config.strategy_validator import StrategyValidator

# Create a Typer application with help text
cli_app = typer.Typer(
    name="ktrdr",
    help="KTRDR - Trading analysis and automation tool",
    add_completion=False,
)

# Get module logger
logger = get_logger(__name__)

# Create a rich console for formatted output
console = Console()
error_console = Console(stderr=True)


@cli_app.command("show-data")
def show_data(
    symbol: str = typer.Argument(..., help="Trading symbol (e.g., AAPL, MSFT)"),
    timeframe: str = typer.Option(
        "1d", "--timeframe", "-t", help="Timeframe (e.g., 1d, 1h)"
    ),
    rows: int = typer.Option(10, "--rows", "-r", help="Number of rows to display"),
    data_dir: Optional[str] = typer.Option(
        None, "--data-dir", "-d", help="Data directory path"
    ),
    tail: bool = typer.Option(
        False, "--tail", help="Show the last N rows instead of the first N"
    ),
    columns: Optional[List[str]] = typer.Option(
        None, "--columns", "-c", help="Columns to display"
    ),
):
    """
    Show OHLCV data from local storage.

    This command loads and displays price data for the specified symbol and timeframe.
    """
    # Debug output
    typer.echo(
        f"DEBUG: Command received with symbol={symbol}, timeframe={timeframe}, rows={rows}",
        err=True,
    )

    try:
        # Validate inputs
        symbol = InputValidator.validate_string(
            symbol, min_length=1, max_length=10, pattern=r"^[A-Za-z0-9\-\.]+$"
        )

        timeframe = InputValidator.validate_string(
            timeframe, min_length=1, max_length=5, pattern=r"^[0-9]+[dhm]$"
        )

        rows = InputValidator.validate_numeric(rows, min_value=1, max_value=1000)

        # Create a DataManager instance (with IB integration)
        data_manager = DataManager(data_dir=data_dir)

        # Load the data
        logger.info(f"Loading data for {symbol} ({timeframe})")
        df = data_manager.load_data(symbol, timeframe, validate=False)

        if df is None or df.empty:
            typer.echo(f"No data found for {symbol} ({timeframe})")
            return

        # Filter columns if specified
        if columns:
            # Validate that the specified columns exist
            valid_columns = [col for col in columns if col in df.columns]
            if not valid_columns:
                typer.echo(
                    f"Warning: None of the specified columns exist. Available columns: {', '.join(df.columns)}"
                )
                return
            df = df[valid_columns]

        # Display information about the data
        typer.echo(f"\nData for {symbol} ({timeframe}):")
        typer.echo(f"Total rows: {len(df)}")
        typer.echo(f"Date range: {df.index.min()} to {df.index.max()}")
        typer.echo(f"Columns: {', '.join(df.columns)}\n")

        # Format the data for display
        pd.set_option("display.max_columns", None)
        pd.set_option("display.width", None)

        # Display the data
        if tail:
            typer.echo(df.tail(rows))
        else:
            typer.echo(df.head(rows))

    except ValidationError as e:
        typer.echo(f"Validation error: {e}", err=True)
        sys.exit(1)
    except DataError as e:
        typer.echo(f"Data error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli_app.command("compute-indicator")
def compute_indicator(
    symbol: str = typer.Argument(..., help="Trading symbol (e.g., AAPL, MSFT)"),
    timeframe: str = typer.Option(
        "1d", "--timeframe", "-t", help="Timeframe (e.g., 1d, 1h)"
    ),
    # Indicator configuration options
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to indicator configuration YAML file"
    ),
    indicator_type: Optional[str] = typer.Option(
        None, "--type", help="Indicator type (e.g., RSI, SMA, EMA)"
    ),
    period: Optional[int] = typer.Option(
        None, "--period", "-p", help="Period for the indicator calculation"
    ),
    source: str = typer.Option(
        "close", "--source", "-s", help="Source column for calculation (default: close)"
    ),
    # Output options
    rows: int = typer.Option(10, "--rows", "-r", help="Number of rows to display"),
    data_dir: Optional[str] = typer.Option(
        None, "--data-dir", "-d", help="Data directory path"
    ),
    tail: bool = typer.Option(
        False, "--tail", help="Show the last N rows instead of the first N"
    ),
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, csv, json)"
    ),
    output_file: Optional[str] = typer.Option(
        None, "--output", "-o", help="Save output to file (specify path)"
    ),
):
    """
    Compute and display technical indicator values.

    This command calculates technical indicators for the specified symbol and timeframe,
    based on either a configuration file or direct parameter specification.
    """
    logger.info(f"Computing indicator for {symbol} ({timeframe})")

    try:
        # Validate inputs - allow longer symbol names (up to 20 chars)
        symbol = InputValidator.validate_string(
            symbol, min_length=1, max_length=20, pattern=r"^[A-Za-z0-9\-\.]+$"
        )

        timeframe = InputValidator.validate_string(
            timeframe, min_length=1, max_length=5, pattern=r"^[0-9]+[dhm]$"
        )

        rows = InputValidator.validate_numeric(rows, min_value=1, max_value=1000)

        format = InputValidator.validate_string(
            format, allowed_values=["table", "csv", "json"]
        )

        # Create a DataManager instance (using LocalDataLoader)
        data_manager = DataManager(data_dir=data_dir)

        # Load the data
        logger.info(f"Loading data for {symbol} ({timeframe})")
        df = data_manager.load_data(symbol, timeframe)

        if df is None or df.empty:
            # For "No data found" we use console.print if it's not JSON format
            # For JSON format, we'll return an empty array with a message
            if format == "json":
                if output_file:
                    with open(output_file, "w") as f:
                        json.dump(
                            {"error": f"No data found for {symbol} ({timeframe})"}, f
                        )
                else:
                    print(
                        json.dumps(
                            {"error": f"No data found for {symbol} ({timeframe})"}
                        )
                    )
                return
            else:
                console.print(f"No data found for {symbol} ({timeframe})")
                return

        # Determine indicator configuration
        indicators = []

        # If a config file is provided, use it
        if config_file:
            logger.info(f"Loading indicator configurations from {config_file}")
            try:
                config_path = Path(config_file)
                if not config_path.exists():
                    raise ConfigurationError(
                        message=f"Configuration file not found: {config_file}",
                        error_code="CONFIG-FileNotFound",
                        details={"file_path": config_file},
                    )

                with open(config_path, "r") as f:
                    config_data = yaml.safe_load(f)

                # Create indicators from configuration
                indicators_config = IndicatorsConfig(**config_data)
                factory = IndicatorFactory(indicators_config)
                indicators = factory.build()

            except Exception as e:
                logger.error(f"Failed to load indicator configuration: {str(e)}")
                raise ConfigurationError(
                    message=f"Failed to load indicator configuration: {str(e)}",
                    error_code="CONFIG-LoadError",
                    details={"file_path": config_file, "error": str(e)},
                )
        # If indicator type is provided, create a single indicator
        elif indicator_type:
            if not period:
                raise ValidationError(
                    message="Period must be specified when using --type",
                    error_code="VALIDATION-MissingParameter",
                    details={"missing_parameter": "period"},
                )

            logger.info(
                f"Creating {indicator_type} indicator with period={period}, source={source}"
            )

            # Create an indicator config
            indicator_config = IndicatorConfig(
                type=indicator_type, params={"period": period, "source": source}
            )

            # Create the indicator
            factory = IndicatorFactory([indicator_config])
            indicators = factory.build()
        else:
            raise ValidationError(
                message="Either --config or --type must be specified",
                error_code="VALIDATION-MissingParameter",
                details={"missing_parameter": "--config or --type"},
            )

        # Compute indicators
        result_df = df.copy()
        for indicator in indicators:
            logger.info(f"Computing {indicator.name} indicator")
            column_name = indicator.get_column_name()
            try:
                result_df[column_name] = indicator.compute(df)
            except DataError as e:
                # Handle insufficient data error more gracefully
                error_console.print(
                    f"[bold red]Error computing {indicator.name}:[/bold red] {str(e)}"
                )
                logger.error(f"Error computing {indicator.name}: {str(e)}")
                # If we can't compute this indicator, continue with others
                continue

        # Check if we were able to compute any indicators
        computed_indicators = [
            ind for ind in indicators if ind.get_column_name() in result_df.columns
        ]
        if not computed_indicators:
            error_console.print(
                "[bold red]Error:[/bold red] Could not compute any indicators"
            )
            return

        # Get the data to display (head or tail)
        display_df = result_df.tail(rows) if tail else result_df.head(rows)

        # Format the output
        if format == "table":
            # Display information about the data
            console.print(
                f"\n[bold]Data for {symbol} ({timeframe}) with indicators:[/bold]"
            )
            console.print(f"Total rows: {len(result_df)}")
            console.print(
                f"Date range: {result_df.index.min()} to {result_df.index.max()}"
            )

            # Create a Rich table for better formatting
            table = Table(title=f"{symbol} ({timeframe}) with indicators")

            # Add the index column
            table.add_column("Date", style="cyan")

            # Add data columns (original OHLCV + indicators)
            for col in display_df.columns:
                # Use different styles for indicators
                if col in df.columns:
                    table.add_column(col, style="green")
                else:
                    table.add_column(col, style="yellow")

            # Add rows
            for idx, row in display_df.iterrows():
                # Convert all values to strings and round floating point numbers
                values = [idx.strftime("%Y-%m-%d")] + [
                    f"{val:.4f}" if isinstance(val, float) else str(val) for val in row
                ]
                table.add_row(*values)

            # Print the table
            console.print(table)

            # Print indicator details
            console.print("\n[bold]Indicator Details:[/bold]")
            for indicator in computed_indicators:
                console.print(f"- {indicator.name}: {indicator.params}")

        elif format == "csv":
            output = display_df.to_csv(date_format='%Y-%m-%dT%H:%M:%SZ')
            if output_file:
                with open(output_file, "w") as f:
                    f.write(output)
                console.print(f"Output saved to {output_file}")
            else:
                console.print(output)

        elif format == "json":
            # Convert to JSON - need to handle the index
            json_data = display_df.reset_index().to_json(
                orient="records", date_format="iso"
            )

            if output_file:
                with open(output_file, "w") as f:
                    f.write(json_data)
                console.print(f"Output saved to {output_file}")
            else:
                # For JSON format, we use print() instead of console.print()
                # to ensure only the JSON content is displayed with no formatting
                print(json_data)

    except ValidationError as e:
        error_console.print(f"[bold red]Validation error:[/bold red] {str(e)}")
        logger.error(f"Validation error: {str(e)}")
        sys.exit(1)
    except DataError as e:
        error_console.print(f"[bold red]Data error:[/bold red] {str(e)}")
        logger.error(f"Data error: {str(e)}")
        sys.exit(1)
    except ConfigurationError as e:
        error_console.print(f"[bold red]Configuration error:[/bold red] {str(e)}")
        logger.error(f"Configuration error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)


@cli_app.command("plot")
def plot(
    symbol: str = typer.Argument(..., help="Trading symbol (e.g., AAPL, MSFT)"),
    timeframe: str = typer.Option(
        "1d", "--timeframe", "-t", help="Timeframe (e.g., 1d, 1h)"
    ),
    # Chart options
    chart_type: str = typer.Option(
        "candlestick",
        "--chart-type",
        "-c",
        help="Chart type (candlestick, line, histogram)",
    ),
    theme: str = typer.Option("dark", "--theme", help="Chart theme (dark, light)"),
    height: int = typer.Option(500, "--height", help="Chart height in pixels"),
    # Indicator options
    indicator_type: Optional[str] = typer.Option(
        None,
        "--indicator",
        "-i",
        help="Indicator type to add (e.g., SMA, EMA, RSI, MACD)",
    ),
    period: int = typer.Option(
        20, "--period", "-p", help="Period for the indicator calculation"
    ),
    source: str = typer.Option(
        "close", "--source", "-s", help="Source column for calculation (default: close)"
    ),
    panel: bool = typer.Option(
        False, "--panel", help="Add indicator as a separate panel (default: overlay)"
    ),
    # Range slider
    range_slider: bool = typer.Option(
        True,
        "--range-slider/--no-range-slider",
        help="Add a range slider for chart navigation",
    ),
    # Additional data display options
    volume: bool = typer.Option(
        True, "--volume/--no-volume", help="Add volume panel to the chart"
    ),
    # Output options
    output_file: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Save output to file (specify path), defaults to symbol_timeframe.html",
    ),
    data_dir: Optional[str] = typer.Option(
        None, "--data-dir", "-d", help="Data directory path"
    ),
):
    """
    Create and save interactive price charts.

    This command generates interactive visualizations of price data,
    optionally including indicators and volume data.
    """
    logger.info(f"Creating chart for {symbol} ({timeframe})")

    try:
        # Validate inputs
        symbol = InputValidator.validate_string(
            symbol, min_length=1, max_length=20, pattern=r"^[A-Za-z0-9\-\.]+$"
        )

        timeframe = InputValidator.validate_string(
            timeframe, min_length=1, max_length=5, pattern=r"^[0-9]+[dhm]$"
        )

        chart_type = InputValidator.validate_string(
            chart_type, allowed_values=["candlestick", "line", "histogram"]
        )

        theme = InputValidator.validate_string(theme, allowed_values=["dark", "light"])

        height = InputValidator.validate_numeric(height, min_value=100, max_value=2000)

        # Create a DataManager instance
        data_manager = DataManager(data_dir=data_dir)

        # Load the data
        logger.info(f"Loading data for {symbol} ({timeframe})")
        df = data_manager.load_data(symbol, timeframe)

        if df is None or df.empty:
            error_console.print(
                f"[bold red]Error:[/bold red] No data found for {symbol} ({timeframe})"
            )
            return

        # Create visualizer with selected theme
        visualizer = Visualizer(theme=theme)

        # Create chart
        console.print(f"Creating {chart_type} chart for {symbol} ({timeframe})...")
        chart = visualizer.create_chart(
            data=df,
            title=f"{symbol} ({timeframe})",
            chart_type=chart_type,
            height=height,
        )

        # Add indicator if specified
        if indicator_type:
            # Create and compute the indicator
            indicator_config = IndicatorConfig(
                type=indicator_type, params={"period": period, "source": source}
            )
            factory = IndicatorFactory([indicator_config])
            indicators = factory.build()

            if not indicators:
                error_console.print(
                    f"[bold red]Error:[/bold red] Failed to create indicator {indicator_type}"
                )
            else:
                indicator = indicators[0]
                # Calculate indicator values
                try:
                    indicator_name = indicator.get_column_name()
                    df[indicator_name] = indicator.compute(df)

                    # Colors for common indicators
                    if indicator_type.lower() in ["sma", "ma"]:
                        color = "#2962FF"  # Blue
                    elif indicator_type.lower() == "ema":
                        color = "#FF6D00"  # Orange
                    elif indicator_type.lower() == "rsi":
                        color = "#9C27B0"  # Purple
                    else:
                        color = "#2962FF"  # Default blue

                    # Add indicator to chart (as panel or overlay)
                    if panel:
                        console.print(f"Adding {indicator_name} as panel...")
                        chart = visualizer.add_indicator_panel(
                            chart=chart,
                            data=df,
                            column=indicator_name,
                            color=color,
                            title=indicator_name,
                        )
                    else:
                        console.print(f"Adding {indicator_name} as overlay...")
                        chart = visualizer.add_indicator_overlay(
                            chart=chart,
                            data=df,
                            column=indicator_name,
                            color=color,
                            title=indicator_name,
                        )
                except Exception as e:
                    error_console.print(
                        f"[bold red]Error computing {indicator_type}:[/bold red] {str(e)}"
                    )
                    logger.error(f"Error computing {indicator_type}: {str(e)}")

        # Add volume if requested
        if volume:
            console.print("Adding volume panel...")
            chart = visualizer.add_indicator_panel(
                chart=chart,
                data=df,
                column="volume",
                panel_type="histogram",
                color="#00BCD4",  # Cyan
                title="Volume",
            )

        # Add range slider if requested
        if range_slider:
            console.print("Adding range slider...")
            chart = visualizer.configure_range_slider(chart, height=60, show=True)

        # Determine output path if not provided
        if not output_file:
            output_dir = Path("output")
            os.makedirs(output_dir, exist_ok=True)
            output_file = output_dir / f"{symbol.lower()}_{timeframe}_{chart_type}.html"

        # Save the chart
        output_path = visualizer.save(chart, output_file, overwrite=True)
        console.print(f"\n[green]Chart saved to:[/green] {output_path}")
        console.print(
            f"Open this file in your web browser to view the interactive chart."
        )

    except ValidationError as e:
        error_console.print(f"[bold red]Validation error:[/bold red] {str(e)}")
        logger.error(f"Validation error: {str(e)}")
        sys.exit(1)
    except DataError as e:
        error_console.print(f"[bold red]Data error:[/bold red] {str(e)}")
        logger.error(f"Data error: {str(e)}")
        sys.exit(1)
    except ConfigurationError as e:
        error_console.print(f"[bold red]Configuration error:[/bold red] {str(e)}")
        logger.error(f"Configuration error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)


@cli_app.command("plot-indicators")
def plot_indicators(
    symbol: str = typer.Argument(..., help="Trading symbol (e.g., AAPL, MSFT)"),
    timeframe: str = typer.Option(
        "1d", "--timeframe", "-t", help="Timeframe (e.g., 1d, 1h)"
    ),
    # Indicators configuration
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to indicator configuration YAML file"
    ),
    # Chart options
    theme: str = typer.Option("dark", "--theme", help="Chart theme (dark, light)"),
    separate_panels: bool = typer.Option(
        True,
        "--separate-panels/--overlays",
        help="Whether to place each indicator in a separate panel",
    ),
    # Output options
    output_file: Optional[str] = typer.Option(
        None, "--output", "-o", help="Save output to file (specify path)"
    ),
    data_dir: Optional[str] = typer.Option(
        None, "--data-dir", "-d", help="Data directory path"
    ),
):
    """
    Create multi-indicator charts with combined price and indicator plots.

    This command generates comprehensive trading visualizations with
    multiple indicators based on a configuration file.
    """
    logger.info(f"Creating multi-indicator chart for {symbol} ({timeframe})")

    try:
        # Validate inputs
        symbol = InputValidator.validate_string(
            symbol, min_length=1, max_length=20, pattern=r"^[A-Za-z0-9\-\.]+$"
        )

        timeframe = InputValidator.validate_string(
            timeframe, min_length=1, max_length=5, pattern=r"^[0-9]+[dhm]$"
        )

        theme = InputValidator.validate_string(theme, allowed_values=["dark", "light"])

        # Check that config file exists if specified
        if config_file:
            config_path = Path(config_file)
            if not config_path.exists():
                raise ConfigurationError(
                    message=f"Configuration file not found: {config_file}",
                    error_code="CONFIG-FileNotFound",
                    details={"file_path": config_file},
                )

        # Create a DataManager instance
        data_manager = DataManager(data_dir=data_dir)

        # Load the data
        logger.info(f"Loading data for {symbol} ({timeframe})")
        df = data_manager.load_data(symbol, timeframe)

        if df is None or df.empty:
            error_console.print(
                f"[bold red]Error:[/bold red] No data found for {symbol} ({timeframe})"
            )
            return

        # Load indicator configuration
        indicators = []
        if config_file:
            try:
                with open(config_path, "r") as f:
                    config_data = yaml.safe_load(f)

                indicators_config = IndicatorsConfig(**config_data)
                factory = IndicatorFactory(indicators_config)
                indicators = factory.build()
            except Exception as e:
                logger.error(f"Failed to load indicator configuration: {str(e)}")
                raise ConfigurationError(
                    message=f"Failed to load indicator configuration: {str(e)}",
                    error_code="CONFIG-LoadError",
                    details={"file_path": config_file, "error": str(e)},
                )
        else:
            # Default indicators if no config provided
            indicators_config = IndicatorsConfig(
                indicators=[
                    IndicatorConfig(
                        type="SMA", params={"period": 20, "source": "close"}
                    ),
                    IndicatorConfig(
                        type="SMA", params={"period": 50, "source": "close"}
                    ),
                    IndicatorConfig(
                        type="RSI", params={"period": 14, "source": "close"}
                    ),
                ]
            )
            factory = IndicatorFactory(indicators_config)
            indicators = factory.build()

        # Create visualizer with selected theme
        visualizer = Visualizer(theme=theme)

        # Create chart
        console.print(f"Creating chart for {symbol} ({timeframe})...")
        chart = visualizer.create_chart(
            data=df,
            title=f"{symbol} ({timeframe}) Technical Analysis",
            chart_type="candlestick",
            height=500,
        )

        # Process indicators
        result_df = df.copy()

        # Define a color palette for indicators
        color_palette = [
            "#2962FF",  # Blue
            "#FF6D00",  # Orange
            "#9C27B0",  # Purple
            "#4CAF50",  # Green
            "#F44336",  # Red
            "#00BCD4",  # Cyan
            "#FFC107",  # Amber
        ]

        # Add computed indicators to the chart
        overlay_count = 0
        panel_count = 0

        for i, indicator in enumerate(indicators):
            indicator_name = indicator.get_column_name()
            try:
                # Compute indicator
                console.print(f"Computing {indicator.name} indicator...")
                result_df[indicator_name] = indicator.compute(df)

                # Determine color (cycle through palette)
                color = color_palette[i % len(color_palette)]

                # Check if this indicator should be a separate panel
                # Use the indicator's own preference unless overridden by user
                should_use_panel = separate_panels or not indicator.display_as_overlay

                # Add indicator to chart
                if should_use_panel:
                    panel_type = (
                        "histogram" if "MACD_HIST" in indicator_name else "line"
                    )
                    console.print(f"Adding {indicator_name} as panel...")
                    chart = visualizer.add_indicator_panel(
                        chart=chart,
                        data=result_df,
                        column=indicator_name,
                        panel_type=panel_type,
                        color=color,
                        title=f"{indicator.name} ({indicator.params.get('period', '')})",
                    )
                    panel_count += 1
                else:
                    console.print(f"Adding {indicator_name} as overlay...")
                    chart = visualizer.add_indicator_overlay(
                        chart=chart,
                        data=result_df,
                        column=indicator_name,
                        color=color,
                        title=f"{indicator.name} ({indicator.params.get('period', '')})",
                    )
                    overlay_count += 1

            except Exception as e:
                error_console.print(
                    f"[bold red]Error computing {indicator.name}:[/bold red] {str(e)}"
                )
                logger.error(f"Error computing {indicator.name}: {str(e)}")

        # Add volume panel
        console.print("Adding volume panel...")
        chart = visualizer.add_indicator_panel(
            chart=chart,
            data=df,
            column="volume",
            panel_type="histogram",
            color="#00BCD4",  # Cyan
            title="Volume",
        )

        # Add range slider
        console.print("Adding range slider...")
        chart = visualizer.configure_range_slider(chart, height=60, show=True)

        # Determine output path if not provided
        if not output_file:
            output_dir = Path("output")
            os.makedirs(output_dir, exist_ok=True)
            output_file = output_dir / f"{symbol.lower()}_{timeframe}_analysis.html"

        # Save the chart
        output_path = visualizer.save(chart, output_file, overwrite=True)
        console.print(f"\n[green]Chart saved to:[/green] {output_path}")
        console.print(
            f"Open this file in your web browser to view the interactive chart."
        )
        console.print(
            f"Chart contains {overlay_count} overlay indicators and {panel_count} panel indicators."
        )

    except ValidationError as e:
        error_console.print(f"[bold red]Validation error:[/bold red] {str(e)}")
        logger.error(f"Validation error: {str(e)}")
        sys.exit(1)
    except DataError as e:
        error_console.print(f"[bold red]Data error:[/bold red] {str(e)}")
        logger.error(f"Data error: {str(e)}")
        sys.exit(1)
    except ConfigurationError as e:
        error_console.print(f"[bold red]Configuration error:[/bold red] {str(e)}")
        logger.error(f"Configuration error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)


@cli_app.command("fuzzify")
def fuzzify(
    symbol: str = typer.Argument(..., help="Trading symbol (e.g., AAPL, MSFT)"),
    timeframe: str = typer.Option(
        "1d", "--timeframe", "-t", help="Timeframe (e.g., 1d, 1h)"
    ),
    # Indicator options
    indicator_type: str = typer.Option(
        ..., "--indicator", "-i", help="Indicator type to fuzzify (e.g., RSI, MACD)"
    ),
    period: int = typer.Option(
        14, "--period", "-p", help="Period for the indicator calculation"
    ),
    source: str = typer.Option(
        "close", "--source", "-s", help="Source column for indicator calculation"
    ),
    # Fuzzy configuration options
    fuzzy_config: Optional[str] = typer.Option(
        None,
        "--fuzzy-config",
        "-f",
        help="Path to fuzzy configuration YAML file (default: config/fuzzy.yaml)",
    ),
    strategy: Optional[str] = typer.Option(
        None,
        "--strategy",
        help="Strategy name to use for fuzzy configuration overrides",
    ),
    # Output options
    rows: int = typer.Option(10, "--rows", "-r", help="Number of rows to display"),
    data_dir: Optional[str] = typer.Option(
        None, "--data-dir", "-d", help="Data directory path"
    ),
    tail: bool = typer.Option(
        False, "--tail", help="Show the last N rows instead of the first N"
    ),
    format: str = typer.Option(
        "table", "--format", help="Output format (table, csv, json)"
    ),
    output_file: Optional[str] = typer.Option(
        None, "--output", "-o", help="Save output to file (specify path)"
    ),
    show_original: bool = typer.Option(
        True,
        "--show-original/--hide-original",
        help="Include original indicator values in output",
    ),
    normalize: bool = typer.Option(
        False, "--normalize", help="Normalize membership values (sum to 1.0)"
    ),
    colorize: bool = typer.Option(
        True, "--colorize/--no-color", help="Colorize the output table"
    ),
):
    """
    Apply fuzzy membership functions to indicator values.

    This command calculates indicator values and applies fuzzy membership functions
    to transform them into fuzzy membership degrees (values between 0 and 1).
    """
    logger.info(f"Fuzzifying {indicator_type} for {symbol} ({timeframe})")

    try:
        # Validate inputs
        symbol = InputValidator.validate_string(
            symbol, min_length=1, max_length=20, pattern=r"^[A-Za-z0-9\-\.]+$"
        )

        timeframe = InputValidator.validate_string(
            timeframe, min_length=1, max_length=5, pattern=r"^[0-9]+[dhm]$"
        )

        indicator_type = InputValidator.validate_string(
            indicator_type, min_length=1, max_length=20
        )

        period = InputValidator.validate_numeric(period, min_value=1, max_value=1000)

        rows = InputValidator.validate_numeric(rows, min_value=1, max_value=1000)

        format = InputValidator.validate_string(
            format, allowed_values=["table", "csv", "json"]
        )

        # Create a DataManager instance (using LocalDataLoader)
        data_manager = DataManager(data_dir=data_dir)

        # Load the data
        logger.info(f"Loading data for {symbol} ({timeframe})")
        df = data_manager.load_data(symbol, timeframe)

        if df is None or df.empty:
            error_console.print(
                f"[bold red]Error:[/bold red] No data found for {symbol} ({timeframe})"
            )
            return

        # Create and compute the indicator
        indicator_config = IndicatorConfig(
            type=indicator_type,  # Don't convert to lowercase here
            params={"period": period, "source": source},
        )
        factory = IndicatorFactory([indicator_config])
        indicators = factory.build()

        if not indicators:
            error_console.print(
                f"[bold red]Error:[/bold red] Failed to create indicator {indicator_type}"
            )
            return

        indicator = indicators[0]
        indicator_name = indicator.get_column_name()

        # Compute indicator values
        logger.info(f"Computing {indicator_name} indicator")
        try:
            indicator_values = indicator.compute(df)
        except DataError as e:
            error_console.print(
                f"[bold red]Error computing {indicator_name}:[/bold red] {str(e)}"
            )
            return

        # Load fuzzy configuration
        logger.info("Loading fuzzy configuration")

        # Fix: Use absolute path to the config file instead of relative path
        config_dir = Path.cwd() / "config"
        fuzzy_loader = FuzzyConfigLoader(config_dir=config_dir)

        try:
            if fuzzy_config:
                # Load from specified file
                fuzzy_config_obj = fuzzy_loader.load_from_yaml(fuzzy_config)
            else:
                # Load default with optional strategy override
                fuzzy_config_obj = fuzzy_loader.load_with_strategy_override(strategy)
        except (ConfigurationError, FileNotFoundError) as e:
            error_console.print(
                f"[bold red]Error loading fuzzy configuration:[/bold red] {str(e)}"
            )
            return

        # Create fuzzy engine
        fuzzy_engine = FuzzyEngine(fuzzy_config_obj)

        # Check if the indicator is available in fuzzy configuration
        available_indicators = fuzzy_engine.get_available_indicators()
        if indicator_type.lower() not in available_indicators:
            error_console.print(
                f"[bold red]Error:[/bold red] Indicator '{indicator_type}' not found in fuzzy configuration."
            )
            error_console.print(
                f"Available indicators: {', '.join(available_indicators)}"
            )
            return

        # Apply fuzzy membership functions
        logger.info(f"Applying fuzzy membership functions to {indicator_name}")
        fuzzy_result = fuzzy_engine.fuzzify(indicator_type.lower(), indicator_values)

        # Normalize if requested
        if normalize:
            logger.info("Normalizing membership values")
            row_sums = fuzzy_result.sum(axis=1)
            row_sums = row_sums.replace(0, 1)  # Avoid division by zero
            fuzzy_result = fuzzy_result.div(row_sums, axis=0)

        # Create combined result DataFrame
        result_df = pd.DataFrame({indicator_name: indicator_values}, index=df.index)
        result_df = pd.concat([result_df, fuzzy_result], axis=1)

        # Get the data to display (head or tail)
        display_df = result_df.tail(rows) if tail else result_df.head(rows)

        # Hide original indicator values if requested
        if not show_original:
            display_df = display_df.drop(columns=[indicator_name])

        # Format the output
        if format == "table":
            # Display information about the data
            console.print(
                f"\n[bold]Fuzzy membership values for {indicator_type} ({symbol}, {timeframe}):[/bold]"
            )
            console.print(f"Total rows: {len(result_df)}")
            console.print(
                f"Date range: {result_df.index.min()} to {result_df.index.max()}"
            )
            if strategy:
                console.print(f"Using strategy: {strategy}")

            # Create a Rich table for better formatting
            table = Table(title=f"{indicator_type} Fuzzy Membership Values")

            # Add the index column
            table.add_column("Date", style="cyan")

            # Add original indicator column if requested
            if show_original:
                table.add_column(indicator_name, style="green")

            # Add fuzzy set columns
            fuzzy_sets = fuzzy_engine.get_fuzzy_sets(indicator_type.lower())

            # Define colors for fuzzy sets
            fuzzy_colors = {
                "low": "blue",
                "negative": "blue",
                "below": "blue",
                "bearish": "blue",
                "neutral": "yellow",
                "medium": "yellow",
                "high": "red",
                "positive": "red",
                "above": "red",
                "bullish": "red",
            }

            # Default color for any set not in the predefined map
            default_color = "white"

            for fuzzy_set in fuzzy_sets:
                output_name = f"{indicator_type.lower()}_{fuzzy_set}"
                # Choose color based on set name if colorize is enabled
                style = (
                    fuzzy_colors.get(fuzzy_set, default_color)
                    if colorize
                    else default_color
                )
                table.add_column(fuzzy_set, style=style)

            # Add rows
            for idx, row in display_df.iterrows():
                # Format values
                values = [idx.strftime("%Y-%m-%d")]

                if show_original:
                    orig_value = row[indicator_name]
                    values.append(
                        f"{orig_value:.4f}" if not pd.isna(orig_value) else "N/A"
                    )

                # Add formatted fuzzy membership values
                for fuzzy_set in fuzzy_sets:
                    output_name = f"{indicator_type.lower()}_{fuzzy_set}"
                    membership = row[output_name]
                    values.append(
                        f"{membership:.4f}" if not pd.isna(membership) else "N/A"
                    )

                table.add_row(*values)

            # Print the table
            console.print(table)

            # Print fuzzy set definitions
            console.print("\n[bold]Fuzzy Set Definitions:[/bold]")
            for fuzzy_set in fuzzy_sets:
                # Get the membership function parameters
                mf_config = fuzzy_config_obj.root[indicator_type.lower()].root[
                    fuzzy_set
                ]
                params = mf_config.parameters
                console.print(f"- {fuzzy_set}: [{params[0]}, {params[1]}, {params[2]}]")

        elif format == "csv":
            output = display_df.to_csv(date_format='%Y-%m-%dT%H:%M:%SZ')
            if output_file:
                with open(output_file, "w") as f:
                    f.write(output)
                console.print(f"Output saved to {output_file}")
            else:
                console.print(output)

        elif format == "json":
            # Convert to JSON - need to handle the index
            json_data = display_df.reset_index().to_json(
                orient="records", date_format="iso"
            )

            if output_file:
                with open(output_file, "w") as f:
                    f.write(json_data)
                console.print(f"Output saved to {output_file}")
            else:
                # For JSON format, we use print() instead of console.print()
                # to ensure only the JSON content is displayed with no formatting
                print(json_data)

    except ValidationError as e:
        error_console.print(f"[bold red]Validation error:[/bold red] {str(e)}")
        logger.error(f"Validation error: {str(e)}")
        sys.exit(1)
    except DataError as e:
        error_console.print(f"[bold red]Data error:[/bold red] {str(e)}")
        logger.error(f"Data error: {str(e)}")
        sys.exit(1)
    except ConfigurationError as e:
        error_console.print(f"[bold red]Configuration error:[/bold red] {str(e)}")
        logger.error(f"Configuration error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)


@cli_app.command("test-ib")
def test_ib(
    quick: bool = typer.Option(False, "--quick", "-q", help="Run quick tests only"),
    symbol: str = typer.Option("AAPL", "--symbol", "-s", help="Test symbol"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """
    Test Interactive Brokers (IB) integration.

    This command tests the complete IB integration stack:
    - Configuration loading
    - Connection establishment
    - Data fetching
    - DataManager integration

    Requires IB Gateway/TWS to be running.
    """
    from datetime import datetime, timedelta, timezone
    from ktrdr.config.ib_config import get_ib_config
    from ktrdr.data.ib_connection_sync import IbConnectionSync, ConnectionConfig
    from ktrdr.data.ib_data_fetcher_sync import IbDataFetcherSync
    from ktrdr.data.data_manager import DataManager

    def run_ib_tests():
        console.print("\n🚀 [bold blue]Testing IB Integration[/bold blue]")
        console.print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        results = {"passed": 0, "total": 0}

        def test_result(name: str, success: bool, details: str = ""):
            results["total"] += 1
            if success:
                results["passed"] += 1
                console.print(f"✅ [green]{name}[/green]")
            else:
                console.print(f"❌ [red]{name}[/red]")
            if details and verbose:
                console.print(f"   {details}")

        # Test 1: Configuration
        console.print("\n📋 Testing Configuration...")
        try:
            config = get_ib_config()
            test_result(
                "Configuration loaded",
                True,
                f"Host: {config.host}:{config.port}, Client ID: {config.client_id}",
            )
        except Exception as e:
            test_result("Configuration loaded", False, str(e))
            console.print("\n💡 [yellow]Troubleshooting:[/yellow]")
            console.print("   1. Copy .env.template to .env")
            console.print("   2. Configure IB_HOST, IB_PORT, IB_CLIENT_ID")
            return

        # Test 2: Connection
        console.print("\n🔌 Testing Connection...")
        connection = None
        try:
            # Convert to sync config
            sync_config = ConnectionConfig(
                host=config.host,
                port=config.port,
                client_id=config.client_id,
                timeout=config.timeout,
                readonly=config.readonly,
            )
            connection = IbConnectionSync(sync_config)
            # Connection is established automatically in __init__

            if connection.is_connected():
                test_result("IB connection", True, "Connected successfully")
            else:
                test_result("IB connection", False, "Connection check failed")
                return
        except Exception as e:
            test_result("IB connection", False, str(e))
            console.print("\n💡 [yellow]Troubleshooting:[/yellow]")
            console.print("   1. Start IB Gateway/TWS and login")
            console.print("   2. Enable API in settings")
            console.print("   3. Check port (7497 paper, 7496 live)")
            return

        if quick:
            # For quick test, just test connection
            connection.disconnect()
            console.print(
                f"\n📊 [bold]Quick Test Results:[/bold] {results['passed']}/{results['total']} passed"
            )
            return

        # Test 3: Data Fetcher
        console.print("\n📈 Testing Data Fetcher...")
        try:
            fetcher = IbDataFetcherSync(connection)
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=2)

            data = fetcher.fetch_historical_data(symbol, "1h", start_date, end_date)

            if data is not None and len(data) > 0:
                test_result(
                    "Data fetching", True, f"Fetched {len(data)} bars for {symbol}"
                )
                if verbose:
                    console.print(f"   Columns: {list(data.columns)}")
                    console.print(f"   Date range: {data.index[0]} to {data.index[-1]}")
            else:
                test_result("Data fetching", False, "No data returned")
        except Exception as e:
            test_result("Data fetching", False, str(e))
            if verbose:
                console.print(f"   Error details: {type(e).__name__}: {str(e)}")

        # Test 4: DataManager Integration
        console.print("\n🔄 Testing DataManager...")
        try:
            data_manager = DataManager()
            # Test if IB integration is properly configured (lazy initialization)
            has_ib_config = (
                data_manager.enable_ib and data_manager._ib_config is not None
            )
            # Try to trigger lazy initialization
            can_connect = (
                data_manager._ensure_ib_connection() if has_ib_config else False
            )

            test_result(
                "DataManager IB integration",
                has_ib_config and can_connect,
                f"IB config: {has_ib_config}, Connection: {can_connect}",
            )
        except Exception as e:
            test_result("DataManager IB integration", False, str(e))

        # Test 5: Fallback Logic
        console.print("\n⚖️ Testing Fallback Logic...")
        try:
            data = data_manager.load_data(symbol, "1d", validate=False)
            if data is not None and len(data) > 0:
                test_result("Fallback logic", True, f"Loaded {len(data)} bars")
            else:
                test_result("Fallback logic", False, "No data loaded")
        except Exception as e:
            test_result("Fallback logic", False, str(e))

        # Cleanup
        if connection:
            connection.disconnect()
            console.print("\n🔌 Disconnected from IB")

        # Summary
        console.print(
            f"\n📊 [bold]Test Results:[/bold] {results['passed']}/{results['total']} passed"
        )
        success_rate = results["passed"] / results["total"] * 100

        if results["passed"] == results["total"]:
            console.print(
                "🎉 [green]All tests passed! IB integration is working.[/green]"
            )
        elif success_rate >= 60:
            console.print("⚠️ [yellow]Most tests passed. Check failures above.[/yellow]")
        else:
            console.print("❌ [red]Many tests failed. Check IB setup.[/red]")

    # Run the tests (now synchronous)
    try:
        run_ib_tests()
    except KeyboardInterrupt:
        console.print("\n⏹️ Test interrupted by user")
    except Exception as e:
        error_console.print(f"[bold red]Test error:[/bold red] {str(e)}")
        sys.exit(1)


@cli_app.command("ib-cleanup")
def ib_cleanup():
    """
    Clean up all active IB connections.

    This command forcefully disconnects all active IB connections and cleans up
    any lingering connections that might be preventing new connections.

    Useful when:
    - IB Gateway is rejecting new connections
    - Testing left connections open
    - Connection errors are occurring
    """
    from ktrdr.data.ib_cleanup import IbConnectionCleaner

    console.print("\n🧹 [bold blue]Cleaning up IB connections[/bold blue]")

    # Show current status
    console.print("\n📊 Current connection status:")
    IbConnectionCleaner.print_connection_status()

    # Perform cleanup
    console.print("\n🔄 Starting cleanup...")
    try:
        IbConnectionCleaner.cleanup_all_sync()
        console.print("✅ [green]Cleanup completed successfully[/green]")

        # Show final status
        console.print("\n📊 Final connection status:")
        IbConnectionCleaner.print_connection_status()

    except Exception as e:
        error_console.print(f"[bold red]Cleanup error:[/bold red] {str(e)}")
        console.print(
            "\n💡 [yellow]Note:[/yellow] You may need to restart IB Gateway if connections are stuck"
        )
        sys.exit(1)


@cli_app.command("ib-load")
def ib_load(
    symbol: str = typer.Argument(..., help="Trading symbol (e.g., AAPL, MSFT)"),
    timeframe: str = typer.Argument(..., help="Timeframe (e.g., 1d, 1h, 15m)"),
    mode: str = typer.Option("tail", "--mode", "-m", help="Load mode: tail, backfill, or full"),
    start_date: Optional[str] = typer.Option(None, "--start", "-s", help="Start date (ISO format: 2024-01-01T00:00:00Z)"),
    end_date: Optional[str] = typer.Option(None, "--end", "-e", help="End date (ISO format: 2024-01-01T00:00:00Z)"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be loaded without actually loading"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress"),
):
    """
    Load OHLCV data using enhanced DataManager with IB integration.

    This command uses intelligent gap analysis to efficiently fetch data from IB.
    It leverages the enhanced DataManager for smart segmentation, trading calendar
    awareness, and optimal data fetching strategies.

    Load modes:
    - tail: Load recent data to fill gaps (default)
    - backfill: Load older data to extend history backwards
    - full: Load complete dataset (backfill + tail to fill all gaps)

    Examples:
        ktrdr ib-load AAPL 1d --mode tail
        ktrdr ib-load MSFT 1h --mode backfill --start 2023-01-01T00:00:00Z
        ktrdr ib-load NVDA 15m --mode full --dry-run
    """
    import asyncio
    import httpx
    from datetime import datetime
    from ktrdr.config.validation import InputValidator

    def format_duration(seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            return f"{seconds/60:.1f}m"
        else:
            return f"{seconds/3600:.1f}h"

    async def call_ib_load_api():
        """Call the IB load API endpoint."""
        try:
            # Validate inputs
            symbol_validated = InputValidator.validate_string(
                symbol.upper(), min_length=1, max_length=20, pattern=r"^[A-Za-z0-9\-\.]+$"
            )
            
            if mode not in ["tail", "backfill", "full"]:
                raise ValidationError(f"Invalid mode '{mode}'. Must be: tail, backfill, or full")

            # Build request payload
            payload = {
                "symbol": symbol_validated,
                "timeframe": timeframe,
                "mode": mode
            }
            
            if start_date:
                payload["start_date"] = start_date
            if end_date:
                payload["end_date"] = end_date

            console.print(f"\n🚀 [bold blue]Loading {symbol_validated} {timeframe} data from Interactive Brokers[/bold blue]")
            console.print(f"Mode: [cyan]{mode}[/cyan]")
            
            if start_date or end_date:
                console.print(f"Date range: {start_date or 'auto'} → {end_date or 'auto'}")
            
            if dry_run:
                console.print("\n[yellow]🔍 DRY RUN - No data will be actually loaded[/yellow]")
                console.print(f"Would send request: {json.dumps(payload, indent=2)}")
                return

            # Show what we're about to do
            if verbose:
                console.print(f"\nRequest payload:")
                console.print(json.dumps(payload, indent=2))

            # Make the API call
            start_time = datetime.now()
            console.print(f"\n⏳ Connecting to IB and fetching data...")
            
            async with httpx.AsyncClient(timeout=300.0) as client:  # 5 minute timeout
                response = await client.post(
                    "http://localhost:8000/api/v1/data/load",
                    json=payload
                )
                
            elapsed = (datetime.now() - start_time).total_seconds()
            
            if response.status_code == 200:
                result = response.json()
                # The API returns nested data structure: {"success": true, "data": {"fetched_bars": 250, ...}}
                data = result.get('data', {})
                fetched_bars = data.get('fetched_bars', 0)
                
                # Check if this is a successful operation
                operation_successful = (
                    data.get('status') == 'success' and 
                    data.get('error_message') is None
                )
                
                if operation_successful:
                    if fetched_bars > 0:
                        # New data was fetched
                        console.print(f"\n✅ [bold green]Data loading completed successfully![/bold green]")
                        console.print(f"⏱️  Duration: {format_duration(elapsed)}")
                        console.print(f"📊 Fetched: [cyan]{fetched_bars}[/cyan] bars")
                        
                        # Show enhanced metrics if available
                        if data.get('gaps_analyzed') is not None:
                            console.print(f"🔍 Gaps analyzed: {data.get('gaps_analyzed', 0)}")
                        if data.get('segments_fetched') is not None:
                            console.print(f"📈 Segments fetched: {data.get('segments_fetched', 0)}")
                        if data.get('ib_requests_made') is not None:
                            console.print(f"🔌 IB requests: {data.get('ib_requests_made', 0)}")
                        
                        if data.get('merged_file'):
                            console.print(f"💾 Saved to: [green]{data['merged_file']}[/green]")
                            
                        if data.get('cached_before'):
                            console.print("📁 Data was merged with existing cached data")
                    else:
                        # No new data needed - local data is already current
                        console.print(f"\n✅ [bold green]Data already up to date![/bold green]")
                        console.print(f"⏱️  Duration: {format_duration(elapsed)}")
                        console.print(f"📊 No new data needed - local data covers the requested period")
                        
                        if data.get('cached_before'):
                            console.print("📁 Using existing cached data")
                        if data.get('merged_file'):
                            console.print(f"💾 Data location: [green]{data['merged_file']}[/green]")
                    
                    # Show additional metrics if available  
                    if verbose:
                        console.print(f"\n📈 [bold]Detailed metrics:[/bold]")
                        console.print(f"   Start time: {data.get('start_time', 'N/A')}")
                        console.print(f"   End time: {data.get('end_time', 'N/A')}")
                        console.print(f"   Requests made: {data.get('requests_made', 'N/A')}")
                        console.print(f"   Execution time: {data.get('execution_time_seconds', 'N/A')}s")
                else:
                    console.print(f"\n❌ [bold red]Data loading failed![/bold red]")
                    console.print(f"⏱️  Duration: {format_duration(elapsed)}")
                    console.print(f"🚨 Error: No data fetched (0 bars)")
                    console.print(f"📊 This usually means:")
                    console.print(f"   • Symbol '{symbol_validated}' not found in IB")
                    console.print(f"   • No data available for timeframe '{timeframe}'")
                    console.print(f"   • Date range has no available data")
                    console.print(f"   • IB connection/permission issues")
                    
                    if verbose:
                        console.print(f"\nFull API response:")
                        console.print(json.dumps(result, indent=2))
                    
                    sys.exit(1)
                        
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                error_msg = error_data.get('detail', f"HTTP {response.status_code}")
                
                console.print(f"\n❌ [bold red]Loading failed![/bold red]")
                console.print(f"⏱️  Duration: {format_duration(elapsed)}")
                console.print(f"🚨 Error: {error_msg}")
                
                if verbose and error_data:
                    console.print(f"\nFull error response:")
                    console.print(json.dumps(error_data, indent=2))
                    
                sys.exit(1)
                
        except ValidationError as e:
            error_console.print(f"[bold red]Validation error:[/bold red] {str(e)}")
            sys.exit(1)
        except httpx.ConnectError:
            error_console.print("[bold red]Connection error:[/bold red] Could not connect to KTRDR API server")
            error_console.print("Make sure the API server is running at http://localhost:8000")
            sys.exit(1)
        except httpx.TimeoutException:
            error_console.print("[bold red]Timeout error:[/bold red] Request took longer than 5 minutes")
            error_console.print("Large data loads can take time. Try a smaller date range.")
            sys.exit(1)
        except Exception as e:
            error_console.print(f"[bold red]Unexpected error:[/bold red] {str(e)}")
            if verbose:
                import traceback
                error_console.print(traceback.format_exc())
            sys.exit(1)

    # Run the async function
    try:
        asyncio.run(call_ib_load_api())
    except KeyboardInterrupt:
        console.print("\n⏹️ Loading interrupted by user")
        sys.exit(1)


# ===== Strategy Management Commands =====

@cli_app.command("strategy-validate")
def strategy_validate_command(
    strategy: str = typer.Argument(..., help="Path to strategy YAML file"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal output"),
):
    """
    Validate a trading strategy configuration.
    
    Checks if a strategy YAML file has all required sections and valid configuration
    for neuro-fuzzy training.
    
    Example:
        ktrdr strategy-validate strategies/my_strategy.yaml
    """
    from .strategy_commands import validate_strategy
    validate_strategy(strategy, quiet)


@cli_app.command("strategy-upgrade")
def strategy_upgrade_command(
    strategy: str = typer.Argument(..., help="Path to strategy YAML file"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output path for upgraded file"),
    inplace: bool = typer.Option(False, "--inplace", "-i", help="Upgrade in place (overwrites original)"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal output"),
):
    """
    Upgrade a strategy to neuro-fuzzy format.
    
    Adds missing sections with sensible defaults to make old strategies compatible
    with the new neuro-fuzzy training system.
    
    Examples:
        ktrdr strategy-upgrade strategies/old_strategy.yaml
        ktrdr strategy-upgrade strategies/old_strategy.yaml --inplace
        ktrdr strategy-upgrade strategies/old_strategy.yaml -o strategies/new_strategy.yaml
    """
    from .strategy_commands import upgrade_strategy
    upgrade_strategy(strategy, output, inplace, quiet)


@cli_app.command("strategy-list")
def strategy_list_command(
    directory: str = typer.Option("strategies", "--directory", "-d", help="Strategies directory"),
    validate: bool = typer.Option(False, "--validate", "-v", help="Validate each strategy"),
    verbose: bool = typer.Option(False, "--verbose", help="Show detailed validation results"),
):
    """
    List all strategy files in a directory.
    
    Shows strategy names, descriptions, and optionally validates each one.
    
    Examples:
        ktrdr strategy-list
        ktrdr strategy-list --validate
        ktrdr strategy-list -d my_strategies --validate --verbose
    """
    from .strategy_commands import list_strategies
    list_strategies(directory, validate, verbose)


# ===== Training Commands =====

@cli_app.command("train")
def train_command(
    strategy: str = typer.Argument(..., help="Path to strategy YAML configuration file"),
    symbol: str = typer.Argument(..., help="Trading symbol to train on (e.g., AAPL, MSFT)"),
    timeframe: str = typer.Argument(..., help="Timeframe for training data (e.g., 1h, 4h, 1d)"),
    start_date: str = typer.Option(..., "--start-date", help="Start date for training data (YYYY-MM-DD)"),
    end_date: str = typer.Option(..., "--end-date", help="End date for training data (YYYY-MM-DD)"),
    models_dir: str = typer.Option("models", "--models-dir", help="Directory to store trained models"),
    validation_split: float = typer.Option(0.2, "--validation-split", help="Fraction of data for validation"),
    epochs: Optional[int] = typer.Option(None, "--epochs", help="Override number of training epochs"),
    data_mode: str = typer.Option("local", "--data-mode", help="Data loading mode: 'local', 'ib', or 'full'"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate configuration without training"),
):
    """
    Train a neuro-fuzzy trading strategy.
    
    This command trains a neural network model based on the strategy configuration,
    using historical price data and technical indicators with fuzzy logic.
    
    Examples:
        ktrdr train strategies/neuro_mean_reversion.yaml AAPL 1h --start-date 2024-01-01 --end-date 2024-06-01
        ktrdr train strategies/momentum.yaml MSFT 4h --start-date 2023-01-01 --end-date 2024-01-01 --epochs 100
    """
    from .training_commands import train_strategy
    train_strategy(strategy, symbol, timeframe, start_date, end_date, models_dir, 
                  validation_split, epochs, data_mode, verbose, dry_run)


# ===== Model Debugging Commands =====

@cli_app.command("model-test")
def model_test_command(
    strategy: str = typer.Argument(..., help="Path to strategy YAML configuration file"),
    symbol: str = typer.Argument(..., help="Trading symbol to test (e.g., AAPL, MSFT)"),
    timeframe: str = typer.Argument(..., help="Timeframe for test data (e.g., 1h, 4h, 1d)"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Path to specific trained model"),
    samples: int = typer.Option(10, "--samples", help="Number of recent data points to test"),
    data_mode: str = typer.Option("local", "--data-mode", help="Data loading mode: 'local', 'ib', or 'full'"),
):
    """
    Test a trained model on recent data to see what signals it generates.
    
    This is useful for debugging why backtests might show no trades.
    
    Examples:
        ktrdr model-test strategies/neuro_mean_reversion.yaml AAPL 1h
        ktrdr model-test strategies/momentum.yaml MSFT 4h --samples 20
    """
    from .model_testing_commands import test_model_signals
    test_model_signals(strategy, symbol, timeframe, model, samples, data_mode)


# ===== Backtesting Commands =====

@cli_app.command("backtest")
def backtest_command(
    strategy: str = typer.Argument(..., help="Path to strategy YAML configuration file"),
    symbol: str = typer.Argument(..., help="Trading symbol to backtest (e.g., AAPL, MSFT)"),
    timeframe: str = typer.Argument(..., help="Timeframe for backtest data (e.g., 1h, 4h, 1d)"),
    start_date: str = typer.Option(..., "--start-date", help="Start date for backtest (YYYY-MM-DD)"),
    end_date: str = typer.Option(..., "--end-date", help="End date for backtest (YYYY-MM-DD)"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Path to specific trained model"),
    capital: float = typer.Option(100000, "--capital", "-c", help="Initial capital for backtest"),
    commission: float = typer.Option(0.001, "--commission", help="Commission rate as decimal (0.001 = 0.1%)"),
    slippage: float = typer.Option(0.0005, "--slippage", help="Slippage rate as decimal (0.0005 = 0.05%)"),
    data_mode: str = typer.Option("local", "--data-mode", help="Data loading mode: 'local', 'ib', or 'full'"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output with progress"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file for results (JSON format)"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress all output except errors"),
):
    """
    Run a backtest on a trained trading strategy.
    
    This command simulates trading using a trained neuro-fuzzy model to evaluate
    strategy performance on historical data.
    
    Examples:
        ktrdr backtest strategies/neuro_mean_reversion.yaml AAPL 1h --start-date 2024-07-01 --end-date 2024-12-31
        ktrdr backtest strategies/momentum.yaml MSFT 4h --start-date 2023-01-01 --end-date 2024-01-01 --capital 50000
    """
    from .backtesting_commands import run_backtest
    run_backtest(strategy, symbol, timeframe, start_date, end_date, model,
                capital, commission, slippage, data_mode, verbose, output, quiet)


# ===== Gap Analysis Commands =====

# Import and register gap analysis commands
from .gap_commands import register_gap_commands
register_gap_commands(cli_app)


# ===== Data Cleanup Commands =====

@cli_app.command("cleanup-data")
def cleanup_data_command(
    confirm: bool = typer.Option(False, "--confirm", help="Skip confirmation prompt"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done without making changes"),
):
    """
    Clean up timezone-poisoned data files and reset symbol cache.
    
    This command backs up and removes data files that may contain incorrect 
    timestamps due to timezone issues present before TimestampManager fixes.
    
    The script will:
    - Create a timestamped backup of all CSV data files
    - Back up the symbol discovery cache
    - Reset failed symbols in the cache (clear for re-validation)
    - Remove the poisoned data files
    - Provide instructions for re-downloading clean data
    
    After running this command, use the data API or fetch commands to 
    re-download fresh data with proper UTC timestamps.
    
    Examples:
        ktrdr cleanup-data                    # Interactive mode with confirmation
        ktrdr cleanup-data --confirm          # Skip confirmation prompt  
        ktrdr cleanup-data --dry-run          # Show what would be done
    """
    import subprocess
    import sys
    from pathlib import Path
    
    console = Console()
    
    # Get the cleanup script path
    project_root = Path(__file__).parent.parent.parent
    cleanup_script = project_root / "scripts" / "cleanup_poisoned_data.py"
    
    if not cleanup_script.exists():
        console.print("[red]Error: Cleanup script not found at {cleanup_script}[/red]")
        raise typer.Exit(1)
    
    if dry_run:
        console.print("[yellow]DRY RUN MODE - No changes will be made[/yellow]")
        console.print(f"Would execute: {cleanup_script}")
        
        # Show what files would be affected
        data_dir = project_root / "data"
        if data_dir.exists():
            csv_files = list(data_dir.glob("*.csv"))
            cache_file = data_dir / "symbol_discovery_cache.json"
            
            console.print(f"\n📁 Data directory: {data_dir}")
            console.print(f"📄 CSV files that would be backed up and removed: {len(csv_files)}")
            for csv_file in csv_files:
                console.print(f"   - {csv_file.name}")
            
            if cache_file.exists():
                console.print(f"🗃️  Symbol cache that would be backed up and reset: {cache_file.name}")
            else:
                console.print("🗃️  No symbol cache found")
        else:
            console.print(f"📁 No data directory found at: {data_dir}")
        
        return
    
    if not confirm:
        console.print("[yellow]⚠️  This will backup and remove existing data files![/yellow]")
        console.print("The files contain timezone-poisoned data and should be re-downloaded.")
        console.print("A backup will be created before removal.")
        
        if not typer.confirm("Continue with data cleanup?"):
            console.print("Cleanup cancelled.")
            raise typer.Exit(0)
    
    # Execute the cleanup script
    try:
        console.print(f"🚀 Running cleanup script: {cleanup_script}")
        result = subprocess.run([sys.executable, str(cleanup_script)], 
                              capture_output=False, text=True)
        
        if result.returncode == 0:
            console.print("\n[green]✅ Data cleanup completed successfully![/green]")
            console.print("\n📋 Next steps:")
            console.print("1. Use 'ktrdr fetch' commands to re-download clean data")
            console.print("2. Or use the data API to load fresh data with proper timestamps")
        else:
            console.print(f"[red]❌ Cleanup script failed with exit code {result.returncode}[/red]")
            raise typer.Exit(result.returncode)
            
    except Exception as e:
        console.print(f"[red]❌ Error running cleanup script: {e}[/red]")
        raise typer.Exit(1)
