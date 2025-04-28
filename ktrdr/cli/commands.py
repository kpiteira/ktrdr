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

# Create a Typer application with help text
cli_app = typer.Typer(
    name="ktrdr",
    help="KTRDR - Trading analysis and automation tool",
    add_completion=False
)

# Get module logger
logger = get_logger(__name__)

# Create a rich console for formatted output
console = Console()
error_console = Console(stderr=True)


@cli_app.command("show-data")
def show_data(
    symbol: str = typer.Argument(..., help="Trading symbol (e.g., AAPL, MSFT)"),
    timeframe: str = typer.Option("1d", "--timeframe", "-t", help="Timeframe (e.g., 1d, 1h)"),
    rows: int = typer.Option(10, "--rows", "-r", help="Number of rows to display"),
    data_dir: Optional[str] = typer.Option(None, "--data-dir", "-d", help="Data directory path"),
    tail: bool = typer.Option(False, "--tail", help="Show the last N rows instead of the first N"),
    columns: Optional[List[str]] = typer.Option(None, "--columns", "-c", help="Columns to display")
):
    """
    Show OHLCV data from local storage.
    
    This command loads and displays price data for the specified symbol and timeframe.
    """
    # Debug output
    typer.echo(f"DEBUG: Command received with symbol={symbol}, timeframe={timeframe}, rows={rows}", err=True)
    
    try:
        # Validate inputs
        symbol = InputValidator.validate_string(
            symbol, 
            min_length=1, 
            max_length=10,
            pattern=r'^[A-Za-z0-9\-\.]+$'
        )
        
        timeframe = InputValidator.validate_string(
            timeframe, 
            min_length=1, 
            max_length=5,
            pattern=r'^[0-9]+[dhm]$'
        )
        
        rows = InputValidator.validate_numeric(
            rows, 
            min_value=1, 
            max_value=1000
        )
        
        # Create a LocalDataLoader instance
        loader = LocalDataLoader(data_dir=data_dir)
        
        # Load the data
        logger.info(f"Loading data for {symbol} ({timeframe})")
        df = loader.load(symbol, timeframe)
        
        if df is None or df.empty:
            typer.echo(f"No data found for {symbol} ({timeframe})")
            return
        
        # Filter columns if specified
        if columns:
            # Validate that the specified columns exist
            valid_columns = [col for col in columns if col in df.columns]
            if not valid_columns:
                typer.echo(f"Warning: None of the specified columns exist. Available columns: {', '.join(df.columns)}")
                return
            df = df[valid_columns]
        
        # Display information about the data
        typer.echo(f"\nData for {symbol} ({timeframe}):")
        typer.echo(f"Total rows: {len(df)}")
        typer.echo(f"Date range: {df.index.min()} to {df.index.max()}")
        typer.echo(f"Columns: {', '.join(df.columns)}\n")
        
        # Format the data for display
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        
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
    timeframe: str = typer.Option("1d", "--timeframe", "-t", help="Timeframe (e.g., 1d, 1h)"),
    
    # Indicator configuration options
    config_file: Optional[str] = typer.Option(
        None, 
        "--config", 
        "-c", 
        help="Path to indicator configuration YAML file"
    ),
    indicator_type: Optional[str] = typer.Option(
        None, 
        "--type", 
        help="Indicator type (e.g., RSI, SMA, EMA)"
    ),
    period: Optional[int] = typer.Option(
        None, 
        "--period", 
        "-p", 
        help="Period for the indicator calculation"
    ),
    source: str = typer.Option(
        "close", 
        "--source", 
        "-s", 
        help="Source column for calculation (default: close)"
    ),
    
    # Output options
    rows: int = typer.Option(10, "--rows", "-r", help="Number of rows to display"),
    data_dir: Optional[str] = typer.Option(None, "--data-dir", "-d", help="Data directory path"),
    tail: bool = typer.Option(False, "--tail", help="Show the last N rows instead of the first N"),
    format: str = typer.Option(
        "table", 
        "--format", 
        "-f", 
        help="Output format (table, csv, json)"
    ),
    output_file: Optional[str] = typer.Option(
        None, 
        "--output",
        "-o",
        help="Save output to file (specify path)"
    )
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
            symbol, 
            min_length=1, 
            max_length=20,
            pattern=r'^[A-Za-z0-9\-\.]+$'
        )
        
        timeframe = InputValidator.validate_string(
            timeframe, 
            min_length=1, 
            max_length=5,
            pattern=r'^[0-9]+[dhm]$'
        )
        
        rows = InputValidator.validate_numeric(
            rows, 
            min_value=1, 
            max_value=1000
        )
        
        format = InputValidator.validate_string(
            format,
            allowed_values=["table", "csv", "json"]
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
                    with open(output_file, 'w') as f:
                        json.dump({"error": f"No data found for {symbol} ({timeframe})"}, f)
                else:
                    print(json.dumps({"error": f"No data found for {symbol} ({timeframe})"}))
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
                        details={"file_path": config_file}
                    )
                
                with open(config_path, 'r') as f:
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
                    details={"file_path": config_file, "error": str(e)}
                )
        # If indicator type is provided, create a single indicator
        elif indicator_type:
            if not period:
                raise ValidationError(
                    message="Period must be specified when using --type",
                    error_code="VALIDATION-MissingParameter",
                    details={"missing_parameter": "period"}
                )
            
            logger.info(f"Creating {indicator_type} indicator with period={period}, source={source}")
            
            # Create an indicator config
            indicator_config = IndicatorConfig(
                type=indicator_type,
                params={"period": period, "source": source}
            )
            
            # Create the indicator
            factory = IndicatorFactory([indicator_config])
            indicators = factory.build()
        else:
            raise ValidationError(
                message="Either --config or --type must be specified",
                error_code="VALIDATION-MissingParameter",
                details={"missing_parameter": "--config or --type"}
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
                error_console.print(f"[bold red]Error computing {indicator.name}:[/bold red] {str(e)}")
                logger.error(f"Error computing {indicator.name}: {str(e)}")
                # If we can't compute this indicator, continue with others
                continue
        
        # Check if we were able to compute any indicators
        computed_indicators = [ind for ind in indicators if ind.get_column_name() in result_df.columns]
        if not computed_indicators:
            error_console.print("[bold red]Error:[/bold red] Could not compute any indicators")
            return
        
        # Get the data to display (head or tail)
        display_df = result_df.tail(rows) if tail else result_df.head(rows)
        
        # Format the output
        if format == "table":
            # Display information about the data
            console.print(f"\n[bold]Data for {symbol} ({timeframe}) with indicators:[/bold]")
            console.print(f"Total rows: {len(result_df)}")
            console.print(f"Date range: {result_df.index.min()} to {result_df.index.max()}")
            
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
                values = [idx.strftime('%Y-%m-%d')] + [
                    f"{val:.4f}" if isinstance(val, float) else str(val)
                    for val in row
                ]
                table.add_row(*values)
            
            # Print the table
            console.print(table)
            
            # Print indicator details
            console.print("\n[bold]Indicator Details:[/bold]")
            for indicator in computed_indicators:
                console.print(f"- {indicator.name}: {indicator.params}")
        
        elif format == "csv":
            output = display_df.to_csv()
            if output_file:
                with open(output_file, 'w') as f:
                    f.write(output)
                console.print(f"Output saved to {output_file}")
            else:
                console.print(output)
                
        elif format == "json":
            # Convert to JSON - need to handle the index
            json_data = display_df.reset_index().to_json(
                orient="records", 
                date_format="iso"
            )
            
            if output_file:
                with open(output_file, 'w') as f:
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
    timeframe: str = typer.Option("1d", "--timeframe", "-t", help="Timeframe (e.g., 1d, 1h)"),
    
    # Chart options
    chart_type: str = typer.Option(
        "candlestick", 
        "--chart-type", 
        "-c",
        help="Chart type (candlestick, line, histogram)"
    ),
    theme: str = typer.Option(
        "dark",
        "--theme", 
        help="Chart theme (dark, light)"
    ),
    height: int = typer.Option(
        500,
        "--height",
        help="Chart height in pixels"
    ),
    
    # Indicator options
    indicator_type: Optional[str] = typer.Option(
        None,
        "--indicator", 
        "-i",
        help="Indicator type to add (e.g., SMA, EMA, RSI, MACD)"
    ),
    period: int = typer.Option(
        20,
        "--period", 
        "-p",
        help="Period for the indicator calculation"
    ),
    source: str = typer.Option(
        "close",
        "--source", 
        "-s",
        help="Source column for calculation (default: close)"
    ),
    panel: bool = typer.Option(
        False,
        "--panel",
        help="Add indicator as a separate panel (default: overlay)"
    ),
    
    # Range slider
    range_slider: bool = typer.Option(
        True,
        "--range-slider/--no-range-slider",
        help="Add a range slider for chart navigation"
    ),
    
    # Additional data display options
    volume: bool = typer.Option(
        True,
        "--volume/--no-volume",
        help="Add volume panel to the chart"
    ),
    
    # Output options
    output_file: Optional[str] = typer.Option(
        None,
        "--output", 
        "-o",
        help="Save output to file (specify path), defaults to symbol_timeframe.html"
    ),
    data_dir: Optional[str] = typer.Option(
        None,
        "--data-dir", 
        "-d",
        help="Data directory path"
    )
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
            symbol,
            min_length=1,
            max_length=20,
            pattern=r'^[A-Za-z0-9\-\.]+$'
        )
        
        timeframe = InputValidator.validate_string(
            timeframe,
            min_length=1,
            max_length=5,
            pattern=r'^[0-9]+[dhm]$'
        )
        
        chart_type = InputValidator.validate_string(
            chart_type,
            allowed_values=["candlestick", "line", "histogram"]
        )
        
        theme = InputValidator.validate_string(
            theme,
            allowed_values=["dark", "light"]
        )
        
        height = InputValidator.validate_numeric(
            height,
            min_value=100,
            max_value=2000
        )
        
        # Create a DataManager instance
        data_manager = DataManager(data_dir=data_dir)
        
        # Load the data
        logger.info(f"Loading data for {symbol} ({timeframe})")
        df = data_manager.load_data(symbol, timeframe)
        
        if df is None or df.empty:
            error_console.print(f"[bold red]Error:[/bold red] No data found for {symbol} ({timeframe})")
            return
        
        # Create visualizer with selected theme
        visualizer = Visualizer(theme=theme)
        
        # Create chart
        console.print(f"Creating {chart_type} chart for {symbol} ({timeframe})...")
        chart = visualizer.create_chart(
            data=df,
            title=f"{symbol} ({timeframe})",
            chart_type=chart_type,
            height=height
        )
        
        # Add indicator if specified
        if indicator_type:
            # Create and compute the indicator
            indicator_config = IndicatorConfig(
                type=indicator_type,
                params={"period": period, "source": source}
            )
            factory = IndicatorFactory([indicator_config])
            indicators = factory.build()
            
            if not indicators:
                error_console.print(f"[bold red]Error:[/bold red] Failed to create indicator {indicator_type}")
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
                            title=indicator_name
                        )
                    else:
                        console.print(f"Adding {indicator_name} as overlay...")
                        chart = visualizer.add_indicator_overlay(
                            chart=chart,
                            data=df,
                            column=indicator_name,
                            color=color,
                            title=indicator_name
                        )
                except Exception as e:
                    error_console.print(f"[bold red]Error computing {indicator_type}:[/bold red] {str(e)}")
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
                title="Volume"
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
        console.print(f"Open this file in your web browser to view the interactive chart.")
        
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
    timeframe: str = typer.Option("1d", "--timeframe", "-t", help="Timeframe (e.g., 1d, 1h)"),
    
    # Indicators configuration
    config_file: Optional[str] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to indicator configuration YAML file"
    ),
    
    # Chart options
    theme: str = typer.Option(
        "dark",
        "--theme",
        help="Chart theme (dark, light)"
    ),
    separate_panels: bool = typer.Option(
        True,
        "--separate-panels/--overlays",
        help="Whether to place each indicator in a separate panel"
    ),
    
    # Output options
    output_file: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Save output to file (specify path)"
    ),
    data_dir: Optional[str] = typer.Option(
        None,
        "--data-dir", 
        "-d",
        help="Data directory path"
    )
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
            symbol,
            min_length=1,
            max_length=20,
            pattern=r'^[A-Za-z0-9\-\.]+$'
        )
        
        timeframe = InputValidator.validate_string(
            timeframe,
            min_length=1,
            max_length=5,
            pattern=r'^[0-9]+[dhm]$'
        )
        
        theme = InputValidator.validate_string(
            theme,
            allowed_values=["dark", "light"]
        )
        
        # Check that config file exists if specified
        if config_file:
            config_path = Path(config_file)
            if not config_path.exists():
                raise ConfigurationError(
                    message=f"Configuration file not found: {config_file}",
                    error_code="CONFIG-FileNotFound",
                    details={"file_path": config_file}
                )
        
        # Create a DataManager instance
        data_manager = DataManager(data_dir=data_dir)
        
        # Load the data
        logger.info(f"Loading data for {symbol} ({timeframe})")
        df = data_manager.load_data(symbol, timeframe)
        
        if df is None or df.empty:
            error_console.print(f"[bold red]Error:[/bold red] No data found for {symbol} ({timeframe})")
            return
        
        # Load indicator configuration
        indicators = []
        if config_file:
            try:
                with open(config_path, 'r') as f:
                    config_data = yaml.safe_load(f)
                
                indicators_config = IndicatorsConfig(**config_data)
                factory = IndicatorFactory(indicators_config)
                indicators = factory.build()
            except Exception as e:
                logger.error(f"Failed to load indicator configuration: {str(e)}")
                raise ConfigurationError(
                    message=f"Failed to load indicator configuration: {str(e)}",
                    error_code="CONFIG-LoadError",
                    details={"file_path": config_file, "error": str(e)}
                )
        else:
            # Default indicators if no config provided
            indicators_config = IndicatorsConfig(
                indicators=[
                    IndicatorConfig(type="SMA", params={"period": 20, "source": "close"}),
                    IndicatorConfig(type="SMA", params={"period": 50, "source": "close"}),
                    IndicatorConfig(type="RSI", params={"period": 14, "source": "close"})
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
            height=500
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
                
                # For some indicators, always use a separate panel
                force_panel = indicator.name.upper() in ["RSI", "MACD", "STOCH", "ADX", "CCI", "ATR"]
                
                # Add indicator to chart
                if separate_panels or force_panel:
                    panel_type = "histogram" if "MACD_HIST" in indicator_name else "line"
                    console.print(f"Adding {indicator_name} as panel...")
                    chart = visualizer.add_indicator_panel(
                        chart=chart,
                        data=result_df,
                        column=indicator_name,
                        panel_type=panel_type,
                        color=color,
                        title=f"{indicator.name} ({indicator.params.get('period', '')})"
                    )
                    panel_count += 1
                else:
                    console.print(f"Adding {indicator_name} as overlay...")
                    chart = visualizer.add_indicator_overlay(
                        chart=chart,
                        data=result_df,
                        column=indicator_name,
                        color=color,
                        title=f"{indicator.name} ({indicator.params.get('period', '')})"
                    )
                    overlay_count += 1
                    
            except Exception as e:
                error_console.print(f"[bold red]Error computing {indicator.name}:[/bold red] {str(e)}")
                logger.error(f"Error computing {indicator.name}: {str(e)}")
        
        # Add volume panel
        console.print("Adding volume panel...")
        chart = visualizer.add_indicator_panel(
            chart=chart,
            data=df,
            column="volume",
            panel_type="histogram",
            color="#00BCD4",  # Cyan
            title="Volume"
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
        console.print(f"Open this file in your web browser to view the interactive chart.")
        console.print(f"Chart contains {overlay_count} overlay indicators and {panel_count} panel indicators.")
        
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


def main():
    """Entry point for the CLI application."""
    cli_app()


if __name__ == "__main__":
    main()