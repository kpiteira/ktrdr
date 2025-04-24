"""
CLI commands for KTRDR application.

This module defines the CLI commands for interacting with the KTRDR application.
"""

import sys
from pathlib import Path
from typing import Optional, List

import typer
import pandas as pd

from ktrdr import get_logger
from ktrdr.data.local_data_loader import LocalDataLoader
from ktrdr.config.validation import InputValidator
from ktrdr.errors import DataError, ValidationError

# Create a Typer application with help text
cli_app = typer.Typer(
    name="ktrdr",
    help="KTRDR - Trading analysis and automation tool",
    add_completion=False
)

# Get module logger
logger = get_logger(__name__)


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


def main():
    """Entry point for the CLI application."""
    cli_app()


if __name__ == "__main__":
    main()