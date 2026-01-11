"""Async data commands using AsyncCLIClient pattern for improved performance.

This module provides the migrated data commands that use the AsyncCLIClient
base class for connection reuse and performance optimization.
"""

import json
import sys
from typing import Optional

import pandas as pd
import typer
from rich.console import Console
from rich.table import Table

from ktrdr.cli.client import APIError, AsyncCLIClient, CLIClientError, ConnectionError
from ktrdr.cli.error_handler import handle_cli_error
from ktrdr.config.validation import InputValidator
from ktrdr.errors import DataError
from ktrdr.logging import get_logger

# Setup logging and console
logger = get_logger(__name__)
console = Console()
error_console = Console(stderr=True)

# Create the CLI app for async data commands
async_data_app = typer.Typer(
    name="data",
    help="Async data management commands with improved performance",
    no_args_is_help=True,
)


@async_data_app.command("show")
def show_data_async(
    symbol: str = typer.Argument(..., help="Trading symbol (e.g., AAPL, MSFT)"),
    timeframe: str = typer.Option(
        "1d", "--timeframe", "-t", help="Timeframe (e.g., 1d, 1h)"
    ),
    rows: int = typer.Option(10, "--rows", "-r", help="Number of rows to display"),
    start_date: Optional[str] = typer.Option(
        None, "--start", help="Start date (YYYY-MM-DD)"
    ),
    end_date: Optional[str] = typer.Option(None, "--end", help="End date (YYYY-MM-DD)"),
    trading_hours_only: bool = typer.Option(
        False, "--trading-hours", help="Show only trading hours data"
    ),
    include_extended: bool = typer.Option(
        False, "--include-extended", help="Include extended hours when filtering"
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, csv)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
) -> None:
    """
    Display cached OHLCV data for a symbol and timeframe using async architecture.

    This command retrieves and displays data that has been previously loaded
    and cached locally. It uses the AsyncCLIClient pattern for improved performance
    through HTTP client connection reuse.

    Examples:
        ktrdr data show AAPL
        ktrdr data show MSFT --timeframe 1h --rows 20
        ktrdr data show TSLA --start 2024-01-01 --format json
    """
    try:
        # Input validation
        symbol = InputValidator.validate_string(
            symbol, min_length=1, max_length=10, pattern=r"^[A-Za-z0-9\-\.]+$"
        )
        timeframe = InputValidator.validate_string(
            timeframe, min_length=1, max_length=5, pattern=r"^[0-9]+[dhm]$"
        )
        rows = int(InputValidator.validate_numeric(rows, min_value=1, max_value=1000))

        # Use AsyncCLIClient for improved performance
        import asyncio

        asyncio.run(
            _show_data_async_impl(
                symbol,
                timeframe,
                rows,
                start_date,
                end_date,
                trading_hours_only,
                include_extended,
                output_format,
                verbose,
            )
        )

    except Exception as e:
        handle_cli_error(e, verbose)
        sys.exit(1)


async def _show_data_async_impl(
    symbol: str,
    timeframe: str,
    rows: int,
    start_date: Optional[str],
    end_date: Optional[str],
    trading_hours_only: bool,
    include_extended: bool,
    output_format: str,
    verbose: bool,
) -> None:
    """Async implementation of show-data command using AsyncCLIClient."""
    try:
        # Use AsyncCLIClient for connection reuse and performance
        async with AsyncCLIClient() as cli:
            if verbose:
                console.print(f"🔍 Retrieving cached data for {symbol} ({timeframe})")

            # Build query parameters
            params = {
                "symbol": symbol,
                "timeframe": timeframe,
            }

            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date
            if trading_hours_only:
                params["trading_hours_only"] = "true"
            if include_extended:
                params["include_extended"] = "true"

            # Get cached data via async API call
            try:
                data = await cli.get("/data/cached", params=params)
            except CLIClientError as e:
                if isinstance(e, ConnectionError):
                    console.print(
                        "[red]❌ Error: Could not connect to KTRDR API server[/red]"
                    )
                    console.print(
                        "Make sure the API server is running at the configured URL"
                    )
                    sys.exit(1)
                elif isinstance(e, APIError) and e.status_code == 404:
                    console.print(f"ℹ️  No cached data found for {symbol} ({timeframe})")
                    if start_date or end_date:
                        console.print(
                            "💡 Try adjusting the date range or loading data first with 'ktrdr data load'"
                        )
                    else:
                        console.print(
                            "💡 Try loading data first with 'ktrdr data load'"
                        )
                    return
                else:
                    raise

            # Check if we got data
            if not data or not data.get("dates"):
                console.print(f"ℹ️  No cached data found for {symbol} ({timeframe})")
                if start_date or end_date:
                    console.print(
                        "💡 Try adjusting the date range or loading data first with 'ktrdr data load'"
                    )
                else:
                    console.print("💡 Try loading data first with 'ktrdr data load'")
                return

            # Convert API response back to DataFrame for display
            dates = data["dates"]
            ohlcv = data["ohlcv"]
            metadata = data.get("metadata", {})

            if not dates or not ohlcv:
                console.print(f"ℹ️  No data points available for {symbol} ({timeframe})")
                return

            # Create DataFrame from API response
            df = pd.DataFrame(
                ohlcv,
                columns=["Open", "High", "Low", "Close", "Volume"],
                index=pd.to_datetime(dates),
            )

            # Limit rows for display
            display_df = df.tail(rows) if len(df) > rows else df

            # Format output
            if output_format == "json":
                result = {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "total_rows": len(df),
                    "displayed_rows": len(display_df),
                    "metadata": metadata,
                    "data": display_df.reset_index().to_dict("records"),
                }
                print(json.dumps(result, indent=2, default=str))

            elif output_format == "csv":
                print(display_df.to_csv())

            else:  # table format
                console.print(f"\n📊 [bold]{symbol} ({timeframe}) - Cached Data[/bold]")
                console.print(f"Total rows: {len(df)} | Showing: {len(display_df)}")

                if metadata:
                    date_range = f"{metadata.get('start', 'N/A')} to {metadata.get('end', 'N/A')}"
                    console.print(f"Date range: {date_range}")

                if trading_hours_only:
                    console.print("🕐 Filtered to trading hours only")
                    if include_extended:
                        console.print("  (including extended hours)")

                console.print()

                # Create rich table
                table = Table()
                table.add_column("Date", style="cyan")
                table.add_column("Open", style="green", justify="right")
                table.add_column("High", style="bright_green", justify="right")
                table.add_column("Low", style="red", justify="right")
                table.add_column("Close", style="bright_red", justify="right")
                table.add_column("Volume", style="blue", justify="right")

                for date, row in display_df.iterrows():
                    table.add_row(
                        (
                            str(date.strftime("%Y-%m-%d %H:%M:%S"))
                            if hasattr(date, "strftime")
                            else str(date)
                        ),
                        f"{row['Open']:.4f}",
                        f"{row['High']:.4f}",
                        f"{row['Low']:.4f}",
                        f"{row['Close']:.4f}",
                        f"{int(row['Volume']):,}",
                    )

                console.print(table)

            if verbose:
                console.print(
                    f"✅ Retrieved {len(df)} data points from cache via AsyncCLIClient"
                )

    except CLIClientError:
        # Re-raise CLI errors without wrapping
        raise
    except Exception as e:
        raise DataError(
            message=f"Failed to show data for {symbol} ({timeframe})",
            error_code="CLI-ShowDataError",
            details={"symbol": symbol, "timeframe": timeframe, "error": str(e)},
        ) from e


def check_api_connection_async() -> bool:
    """Check API connection using AsyncCLIClient pattern."""
    import asyncio

    async def _check() -> bool:
        try:
            async with AsyncCLIClient() as cli:
                return await cli.health_check()
        except CLIClientError:
            return False

    return asyncio.run(_check())


# Helper function to display IB connection message
def display_ib_connection_required_message() -> None:
    """Display message when IB connection is required."""
    error_console.print(
        "[bold red]Error:[/bold red] Could not connect to KTRDR API server"
    )
    error_console.print("Make sure the API server is running at the configured URL")
