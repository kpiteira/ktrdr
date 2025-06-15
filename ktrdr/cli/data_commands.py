"""
Data management commands for the KTRDR CLI.

This module contains all CLI commands related to data operations:
- show-data: Display cached data
- load-data: Load data with API integration
- data-status: Show status of operations
- cancel-data: Cancel running operations
"""

import asyncio
import signal
import sys
import json
from typing import Optional
from pathlib import Path

import typer
import pandas as pd
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
from ktrdr.cli.ib_diagnosis import (
    detect_ib_issue_from_api_response,
    format_ib_diagnostic_message,
    get_ib_recovery_suggestions,
    should_show_ib_diagnosis,
)
from ktrdr.cli.error_handler import (
    handle_cli_error,
    handle_api_response_error,
    display_ib_connection_required_message,
)

# Setup logging and console
logger = get_logger(__name__)
console = Console()
error_console = Console(stderr=True)

# Create the CLI app for data commands
data_app = typer.Typer(
    name="data",
    help="Data management commands",
    no_args_is_help=True,
)


@data_app.command("show")
def show_data(
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
):
    """
    Display cached OHLCV data for a symbol and timeframe.

    This command retrieves and displays data that has been previously loaded
    and cached locally. It's fast since it doesn't trigger any external API calls.

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
        rows = InputValidator.validate_numeric(rows, min_value=1, max_value=1000)

        # Run async operation
        asyncio.run(
            _show_data_async(
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


async def _show_data_async(
    symbol: str,
    timeframe: str,
    rows: int,
    start_date: Optional[str],
    end_date: Optional[str],
    trading_hours_only: bool,
    include_extended: bool,
    output_format: str,
    verbose: bool,
):
    """Async implementation of show-data command."""
    try:
        # Check API connection
        if not await check_api_connection():
            display_ib_connection_required_message()
            sys.exit(1)

        api_client = get_api_client()

        if verbose:
            console.print(f"🔍 Retrieving cached data for {symbol} ({timeframe})")

        # Get cached data via API
        data = await api_client.get_cached_data(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            trading_hours_only=trading_hours_only,
            include_extended=include_extended,
        )

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
                date_range = (
                    f"{metadata.get('start', 'N/A')} to {metadata.get('end', 'N/A')}"
                )
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
                    date.strftime("%Y-%m-%d %H:%M:%S"),
                    f"{row['Open']:.4f}",
                    f"{row['High']:.4f}",
                    f"{row['Low']:.4f}",
                    f"{row['Close']:.4f}",
                    f"{int(row['Volume']):,}",
                )

            console.print(table)

        if verbose:
            console.print(f"✅ Retrieved {len(df)} data points from cache")

    except Exception as e:
        raise DataError(
            message=f"Failed to show data for {symbol} ({timeframe})",
            error_code="CLI-ShowDataError",
            details={"symbol": symbol, "timeframe": timeframe, "error": str(e)},
        ) from e


@data_app.command("load")
def load_data(
    symbol: str = typer.Argument(..., help="Trading symbol (e.g., AAPL, MSFT)"),
    timeframe: str = typer.Option(
        "1d", "--timeframe", "-t", help="Timeframe (e.g., 1d, 1h)"
    ),
    mode: str = typer.Option(
        "tail", "--mode", "-m", help="Loading mode (tail, backfill, full)"
    ),
    start_date: Optional[str] = typer.Option(
        None, "--start", help="Start date (YYYY-MM-DD)"
    ),
    end_date: Optional[str] = typer.Option(None, "--end", help="End date (YYYY-MM-DD)"),
    trading_hours_only: bool = typer.Option(
        False, "--trading-hours", help="Filter to trading hours only"
    ),
    include_extended: bool = typer.Option(
        False, "--include-extended", help="Include extended hours when filtering"
    ),
    show_progress: bool = typer.Option(
        True, "--progress/--no-progress", help="Show progress"
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal output"),
):
    """
    Load data via the KTRDR API with intelligent gap analysis.

    This command uses the enhanced DataManager through the API to load data
    efficiently with IB integration, gap analysis, and trading calendar awareness.

    Loading modes:
    - tail: Load recent data from last available timestamp to now
    - backfill: Load historical data before earliest available timestamp
    - full: Load both historical (backfill) and recent (tail) data

    Examples:
        ktrdr data load AAPL
        ktrdr data load MSFT --timeframe 1h --mode tail
        ktrdr data load TSLA --start 2024-01-01 --end 2024-06-01
    """
    try:
        # Input validation
        symbol = InputValidator.validate_string(
            symbol, min_length=1, max_length=10, pattern=r"^[A-Za-z0-9\-\.]+$"
        )
        timeframe = InputValidator.validate_string(
            timeframe, min_length=1, max_length=5, pattern=r"^[0-9]+[dhm]$"
        )

        valid_modes = ["tail", "backfill", "full"]
        if mode not in valid_modes:
            raise ValidationError(
                message=f"Invalid mode '{mode}'. Must be one of: {', '.join(valid_modes)}",
                error_code="VALIDATION-InvalidMode",
                details={"mode": mode, "valid_modes": valid_modes},
            )

        # Run async operation
        asyncio.run(
            _load_data_async(
                symbol,
                timeframe,
                mode,
                start_date,
                end_date,
                trading_hours_only,
                include_extended,
                show_progress,
                output_format,
                verbose,
                quiet,
            )
        )

    except ValidationError as e:
        error_console.print(f"[bold red]Validation error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Validation error: {str(e)}")
        sys.exit(1)
    except KeyboardInterrupt:
        if not quiet:
            error_console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        handle_cli_error(e, verbose, quiet)
        sys.exit(1)


async def _load_data_async(
    symbol: str,
    timeframe: str,
    mode: str,
    start_date: Optional[str],
    end_date: Optional[str],
    trading_hours_only: bool,
    include_extended: bool,
    show_progress: bool,
    output_format: str,
    verbose: bool,
    quiet: bool,
):
    """Async implementation of load-data command using API."""
    # Reduce HTTP logging noise unless verbose mode
    if not verbose:
        import logging

        httpx_logger = logging.getLogger("httpx")
        original_level = httpx_logger.level
        httpx_logger.setLevel(logging.WARNING)

    try:
        # Check API connection
        if not await check_api_connection():
            display_ib_connection_required_message()
            sys.exit(1)

        api_client = get_api_client()

        if not quiet:
            console.print(f"🚀 [bold]Loading data for {symbol} ({timeframe})[/bold]")
            console.print(
                f"📋 Mode: {mode} | Trading hours filter: {trading_hours_only}"
            )
            if start_date or end_date:
                console.print(
                    f"📅 Date range: {start_date or 'earliest'} to {end_date or 'latest'}"
                )
            console.print()

        # Show progress if requested
        # Use async mode for cancellable operations
        async_mode = True  # Always use async mode for cancellation support

        # Set up cancellation handling
        cancelled = False
        operation_id = None

        def signal_handler(signum, frame):
            """Handle Ctrl+C for graceful cancellation."""
            nonlocal cancelled
            cancelled = True
            console.print(
                "\n[yellow]🛑 Cancellation requested... stopping operation[/yellow]"
            )

        # Set up signal handler for Ctrl+C
        signal.signal(signal.SIGINT, signal_handler)

        try:
            # Start async operation
            response = await api_client.load_data(
                symbol=symbol,
                timeframe=timeframe,
                mode=mode,
                start_date=start_date,
                end_date=end_date,
                trading_hours_only=trading_hours_only,
                include_extended=include_extended,
                async_mode=async_mode,
            )

            # Get operation ID from response
            if response.get("success") and response.get("data", {}).get("operation_id"):
                operation_id = response["data"]["operation_id"]
                if not quiet:
                    console.print(f"⚡ Started operation: {operation_id}")
            else:
                # Fallback to sync mode if async not supported
                if not quiet:
                    console.print("ℹ️  Using synchronous mode")
                # Process sync response directly
                return await _process_data_load_response(
                    response,
                    symbol,
                    timeframe,
                    mode,
                    output_format,
                    verbose,
                    quiet,
                    api_client,
                )

            # Monitor operation progress
            if show_progress and not quiet:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    TimeElapsedColumn(),
                    console=console,
                    transient=False,  # Keep progress visible
                    refresh_per_second=2,  # Reduce refresh rate
                ) as progress:
                    task = progress.add_task("Loading data...", total=100)

                    # Poll operation status
                    while not cancelled:
                        try:
                            status_response = await api_client.get_operation_status(
                                operation_id
                            )
                            operation_data = status_response.get("data", {})

                            status = operation_data.get("status")
                            progress_info = operation_data.get("progress", {})
                            progress_percentage = progress_info.get("percentage", 0)
                            current_step = progress_info.get(
                                "current_step", "Loading..."
                            )

                            # Update progress display
                            progress.update(
                                task,
                                completed=progress_percentage,
                                description=(
                                    current_step[:50] + "..."
                                    if len(current_step) > 50
                                    else current_step
                                ),
                            )

                            # Check if operation completed
                            if status in ["completed", "failed", "cancelled"]:
                                progress.update(
                                    task, completed=100, description="Completed"
                                )
                                break

                            # Sleep before next poll
                            await asyncio.sleep(1.0)

                        except Exception as e:
                            if not quiet:
                                console.print(
                                    f"[yellow]Warning: Failed to get operation status: {str(e)}[/yellow]"
                                )
                            break
            else:
                # Simple polling without progress display
                while not cancelled:
                    try:
                        status_response = await api_client.get_operation_status(
                            operation_id
                        )
                        operation_data = status_response.get("data", {})
                        status = operation_data.get("status")

                        if status in ["completed", "failed", "cancelled"]:
                            break

                        await asyncio.sleep(2.0)

                    except Exception as e:
                        if not quiet:
                            console.print(
                                f"[yellow]Warning: Failed to get operation status: {str(e)}[/yellow]"
                            )
                        break

            # Handle cancellation
            if cancelled and operation_id:
                try:
                    cancel_response = await api_client.cancel_operation(
                        operation_id=operation_id,
                        reason="User requested cancellation via CLI",
                    )
                    if not quiet:
                        console.print(
                            "✅ [yellow]Operation cancelled successfully[/yellow]"
                        )
                    return
                except Exception as e:
                    if not quiet:
                        console.print(
                            f"[red]Failed to cancel operation: {str(e)}[/red]"
                        )
                    return

            # Get final operation status
            try:
                final_response = await api_client.get_operation_status(operation_id)
                operation_data = final_response.get("data", {})

                # Convert operation data to load response format
                result_summary = operation_data.get("result_summary", {})
                response = {
                    "success": operation_data.get("status") == "completed",
                    "data": {
                        "status": result_summary.get(
                            "status", operation_data.get("status")
                        ),
                        "fetched_bars": result_summary.get("fetched_bars", 0),
                        "execution_time_seconds": result_summary.get(
                            "execution_time_seconds", 0
                        ),
                        "operation_id": operation_id,
                    },
                    "error": (
                        {"message": operation_data.get("error_message")}
                        if operation_data.get("error_message")
                        else None
                    ),
                }

            except Exception as e:
                if not quiet:
                    console.print(
                        f"[red]Failed to get final operation status: {str(e)}[/red]"
                    )
                return

        finally:
            # Restore default signal handler
            signal.signal(signal.SIGINT, signal.SIG_DFL)

        # Process the final response using the helper function
        await _process_data_load_response(
            response, symbol, timeframe, mode, output_format, verbose, quiet, api_client
        )

    except Exception as e:
        raise DataError(
            message=f"Failed to load data for {symbol} ({timeframe})",
            error_code="CLI-LoadDataError",
            details={
                "symbol": symbol,
                "timeframe": timeframe,
                "mode": mode,
                "error": str(e),
            },
        ) from e
    finally:
        # Restore HTTP logging level
        if not verbose:
            httpx_logger.setLevel(original_level)


async def _process_data_load_response(
    response: dict,
    symbol: str,
    timeframe: str,
    mode: str,
    output_format: str,
    verbose: bool,
    quiet: bool,
    api_client,
) -> None:
    """Process and display data load response."""
    # Process response
    success = response.get("success", False)
    data = response.get("data", {})
    error_info = response.get("error")

    # Check for IB diagnosis in the response
    ib_diagnosis = None
    if error_info and "ib_diagnosis" in error_info:
        ib_diagnosis = error_info["ib_diagnosis"]

    if success:
        # Success or partial success
        status = data.get("status", "unknown")
        fetched_bars = data.get("fetched_bars", 0)
        execution_time = data.get("execution_time_seconds", 0)

        if not quiet:
            if status == "success":
                console.print(
                    f"✅ [bold green]Successfully loaded {fetched_bars} bars[/bold green]"
                )
            elif status == "partial":
                console.print(
                    f"⚠️  [yellow]Partially loaded {fetched_bars} bars[/yellow]"
                )
                if ib_diagnosis:
                    # Show IB diagnostic message for partial loads
                    console.print(f"\n{ib_diagnosis['clear_message']}")
                    if verbose:
                        from ktrdr.cli.ib_diagnosis import (
                            IBProblemType,
                            get_ib_recovery_suggestions,
                        )

                        try:
                            problem_type = IBProblemType(ib_diagnosis["problem_type"])
                            console.print(
                                f"\n{get_ib_recovery_suggestions(problem_type)}"
                            )
                        except ValueError:
                            pass
                elif error_info:
                    console.print(
                        f"⚠️  Warning: {error_info.get('message', 'Unknown issue')}"
                    )
            else:
                console.print(f"ℹ️  Data loading completed with status: {status}")

            if execution_time:
                console.print(
                    f"⏱️  Duration: {api_client.format_duration(execution_time)}"
                )

            # Show additional metrics if available
            if verbose and data:
                console.print(f"\n📊 [bold]Detailed metrics:[/bold]")
                for key, value in data.items():
                    if key not in ["status", "fetched_bars", "execution_time_seconds"]:
                        console.print(f"   {key}: {value}")

        # Format output
        if output_format == "json":
            result = {
                "symbol": symbol,
                "timeframe": timeframe,
                "mode": mode,
                "success": success,
                "status": status,
                "bars_loaded": fetched_bars,
                "execution_time_seconds": execution_time,
                "details": data,
            }
            if error_info:
                result["warning"] = error_info
            print(json.dumps(result, indent=2))
    else:
        # Failed
        error_msg = (
            error_info.get("message", "Unknown error")
            if error_info
            else "Unknown error"
        )

        if not quiet:
            console.print(f"❌ [bold red]Data loading failed![/bold red]")

            if ib_diagnosis:
                # Show IB diagnostic message for failures
                console.print(f"\n{ib_diagnosis['clear_message']}")
                if verbose:
                    from ktrdr.cli.ib_diagnosis import (
                        IBProblemType,
                        get_ib_recovery_suggestions,
                    )

                    try:
                        problem_type = IBProblemType(ib_diagnosis["problem_type"])
                        console.print(f"\n{get_ib_recovery_suggestions(problem_type)}")
                    except ValueError:
                        pass
            else:
                console.print(f"🚨 Error: {error_msg}")

            if verbose and error_info and not ib_diagnosis:
                console.print(f"\n🔍 [bold]Error details:[/bold]")
                for key, value in error_info.items():
                    if key != "ib_diagnosis":  # Skip IB diagnosis in raw details
                        console.print(f"   {key}: {value}")

        if output_format == "json":
            result = {
                "symbol": symbol,
                "timeframe": timeframe,
                "mode": mode,
                "success": False,
                "error": error_info or {"message": error_msg},
            }
            print(json.dumps(result, indent=2))

        sys.exit(1)


@data_app.command("range")
def get_data_range(
    symbol: str = typer.Argument(..., help="Trading symbol (e.g., AAPL, MSFT)"),
    timeframe: str = typer.Option(
        "1d", "--timeframe", "-t", help="Timeframe (e.g., 1d, 1h)"
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
):
    """
    Get available date range for cached data.

    Shows the earliest and latest available dates for the specified symbol
    and timeframe, along with the total number of data points.

    Examples:
        ktrdr data range AAPL
        ktrdr data range MSFT --timeframe 1h --format json
    """
    try:
        # Input validation
        symbol = InputValidator.validate_string(
            symbol, min_length=1, max_length=10, pattern=r"^[A-Za-z0-9\-\.]+$"
        )
        timeframe = InputValidator.validate_string(
            timeframe, min_length=1, max_length=5, pattern=r"^[0-9]+[dhm]$"
        )

        # Run async operation
        asyncio.run(_get_data_range_async(symbol, timeframe, output_format, verbose))

    except Exception as e:
        handle_cli_error(e, verbose)
        sys.exit(1)


async def _get_data_range_async(
    symbol: str,
    timeframe: str,
    output_format: str,
    verbose: bool,
):
    """Async implementation of data range command."""
    try:
        # Check API connection
        if not await check_api_connection():
            display_ib_connection_required_message()
            sys.exit(1)

        api_client = get_api_client()

        if verbose:
            console.print(f"🔍 Getting data range for {symbol} ({timeframe})")

        # Get data range via API
        data = await api_client.get_data_range(symbol=symbol, timeframe=timeframe)

        # Format output
        if output_format == "json":
            result = {
                "symbol": symbol,
                "timeframe": timeframe,
                "range": data,
            }
            print(json.dumps(result, indent=2, default=str))
        else:
            # Table format
            console.print(f"\n📅 [bold]{symbol} ({timeframe}) - Data Range[/bold]")

            table = Table()
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Symbol", data.get("symbol", "N/A"))
            table.add_row("Timeframe", data.get("timeframe", "N/A"))
            table.add_row("Start Date", str(data.get("start_date", "N/A")))
            table.add_row("End Date", str(data.get("end_date", "N/A")))
            table.add_row("Data Points", str(data.get("point_count", "N/A")))

            console.print(table)

        if verbose:
            console.print(f"✅ Retrieved data range information")

    except Exception as e:
        if "404" in str(e) or "not found" in str(e).lower():
            console.print(f"ℹ️  No cached data found for {symbol} ({timeframe})")
            console.print("💡 Try loading data first with 'ktrdr data load'")
        else:
            raise DataError(
                message=f"Failed to get data range for {symbol} ({timeframe})",
                error_code="CLI-GetDataRangeError",
                details={"symbol": symbol, "timeframe": timeframe, "error": str(e)},
            ) from e


# Note: data-status and cancel-data commands will be added when we have
# proper async operation tracking API endpoints
