"""
Data management commands for the KTRDR CLI.

This module contains all CLI commands related to data operations:
- show-data: Display cached data
- load-data: Load data with API integration
- data-status: Show status of operations
- cancel-data: Cancel running operations
"""

import asyncio
import json
import sys
from typing import Optional, cast

import pandas as pd
import typer
from rich.console import Console
from rich.table import Table

from ktrdr.cli.api_client import check_api_connection, get_api_client
from ktrdr.cli.async_cli_client import AsyncCLIClient, AsyncCLIClientError
from ktrdr.cli.error_handler import (
    display_ib_connection_required_message,
    handle_cli_error,
)
from ktrdr.cli.progress_display_enhanced import create_enhanced_progress_callback
from ktrdr.config.validation import InputValidator
from ktrdr.errors import DataError, ValidationError
from ktrdr.logging import get_logger

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
    Uses AsyncCLIClient for improved performance through connection reuse.

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

        # Run async operation with improved performance
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
                data = await cli._make_request(
                    "GET", f"/data/{symbol}/{timeframe}", params=params
                )
            except AsyncCLIClientError as e:
                if e.error_code == "CLI-ConnectionError":
                    display_ib_connection_required_message()
                    sys.exit(1)
                elif e.error_code.startswith("CLI-404"):
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

            # Extract data from API response
            api_data = data.get("data", {})

            # Check if we got data
            if not api_data or not api_data.get("dates"):
                console.print(f"ℹ️  No cached data found for {symbol} ({timeframe})")
                if start_date or end_date:
                    console.print(
                        "💡 Try adjusting the date range or loading data first with 'ktrdr data load'"
                    )
                else:
                    console.print("💡 Try loading data first with 'ktrdr data load'")
                return

            # Convert API response back to DataFrame for display
            dates = api_data["dates"]
            ohlcv = api_data["ohlcv"]
            metadata = api_data.get("metadata", {})

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
                        cast(pd.Timestamp, date).strftime("%Y-%m-%d %H:%M:%S"),
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

    except AsyncCLIClientError:
        # Re-raise CLI errors without wrapping
        raise
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
    periodic_save_minutes: float = typer.Option(
        2.0,
        "--save-interval",
        help="Save progress every N minutes during long downloads (default: 2.0)",
    ),
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

        # Run async operation with proper signal handling
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
                periodic_save_minutes,
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
    periodic_save_minutes: float,
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

        # Set up async signal handling
        import signal

        cancelled = False
        operation_id = None

        # Set up signal handler using asyncio
        loop = asyncio.get_running_loop()

        def signal_handler():
            """Handle Ctrl+C for graceful cancellation."""
            nonlocal cancelled
            cancelled = True
            console.print(
                "\\n[yellow]🛑 Cancellation requested... stopping operation[/yellow]"
            )
            # Debug output
            import sys

            sys.stderr.write(
                "\\n[DEBUG] Async signal handler called, cancelled flag set to True\\n"
            )
            sys.stderr.flush()

        # Register signal handler with the event loop
        loop.add_signal_handler(signal.SIGINT, signal_handler)

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
                periodic_save_minutes=periodic_save_minutes,
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

            # Monitor operation progress with enhanced display
            if show_progress and not quiet:
                # Create enhanced progress display
                from datetime import datetime

                from ktrdr.data.components.progress_manager import ProgressState

                enhanced_callback, display = create_enhanced_progress_callback(
                    console=console, show_details=True
                )

                operation_started = False

                # Poll operation status with enhanced display
                while True:
                    try:
                        # Check for cancellation and send cancel request immediately
                        if cancelled:
                            console.print(
                                "[yellow]🛑 Sending cancellation to server...[/yellow]"
                            )
                            try:
                                cancel_response = await api_client.cancel_operation(
                                    operation_id=operation_id,
                                    reason="User requested cancellation via CLI",
                                )
                                if cancel_response.get("success"):
                                    console.print(
                                        "✅ [yellow]Cancellation sent successfully[/yellow]"
                                    )
                                else:
                                    console.print(
                                        f"[red]Cancel failed: {cancel_response}[/red]"
                                    )
                            except Exception as e:
                                console.print(
                                    f"[red]Cancel request failed: {str(e)}[/red]"
                                )
                            break  # Exit the polling loop

                        status_response = await api_client.get_operation_status(
                            operation_id
                        )
                        operation_data = status_response.get("data", {})

                        status = operation_data.get("status")
                        progress_info = operation_data.get("progress", {})
                        progress_percentage = progress_info.get("percentage", 0)
                        current_step = progress_info.get("current_step", "Loading...")

                        # Display warnings if any
                        warnings = operation_data.get("warnings", [])
                        if warnings:
                            for warning in warnings[-2:]:  # Show last 2 warnings
                                console.print(f"[yellow]⚠️  {warning}[/yellow]")

                        # Display errors if any
                        errors = operation_data.get("errors", [])
                        if errors:
                            for error in errors[-2:]:  # Show last 2 errors
                                console.print(f"[red]❌ {error}[/red]")

                        # Create ProgressState for enhanced display
                        progress_state = ProgressState(
                            operation_id=operation_id,
                            current_step=progress_info.get("steps_completed", 0),
                            total_steps=progress_info.get("steps_total", 10),
                            message=current_step,
                            percentage=progress_percentage,
                            start_time=datetime.now(),  # Approximate - could be improved
                            steps_completed=progress_info.get("steps_completed", 0),
                            steps_total=progress_info.get("steps_total", 10),
                            items_processed=progress_info.get("items_processed", 0),
                            expected_items=progress_info.get("items_total", None),
                        )

                        # Start operation on first callback
                        if not operation_started:
                            display.start_operation(
                                operation_name=f"load_data_{symbol}_{timeframe}",
                                total_steps=progress_state.total_steps,
                                context={
                                    "symbol": symbol,
                                    "timeframe": timeframe,
                                    "mode": mode,
                                },
                            )
                            operation_started = True

                        # Update enhanced progress display
                        display.update_progress(progress_state)

                        # Check if operation completed
                        if status in ["completed", "failed", "cancelled"]:
                            display.complete_operation(success=(status == "completed"))
                            break

                        # Poll every 300ms for responsive updates
                        await asyncio.sleep(0.3)

                    except Exception as e:
                        if not quiet:
                            console.print(
                                f"[yellow]Warning: Failed to get operation status: {str(e)}[/yellow]"
                            )
                        # Continue polling instead of breaking - temporary status errors shouldn't kill the loop
                        await asyncio.sleep(1.0)
                        continue
            else:
                # Simple polling without progress display
                while True:
                    try:
                        # Check for cancellation and send cancel request immediately
                        if cancelled:
                            if not quiet:
                                console.print("🛑 Sending cancellation to server...")
                            try:
                                cancel_response = await api_client.cancel_operation(
                                    operation_id=operation_id,
                                    reason="User requested cancellation via CLI",
                                )
                                if cancel_response.get("success"):
                                    if not quiet:
                                        console.print(
                                            "✅ Cancellation sent successfully"
                                        )
                                else:
                                    if not quiet:
                                        console.print(
                                            f"Cancel failed: {cancel_response}"
                                        )
                            except Exception as e:
                                if not quiet:
                                    console.print(f"Cancel request failed: {str(e)}")
                            break  # Exit the polling loop

                        status_response = await api_client.get_operation_status(
                            operation_id
                        )
                        operation_data = status_response.get("data", {})
                        status = operation_data.get("status")

                        # Check if operation completed
                        if status in ["completed", "failed", "cancelled"]:
                            break

                        await asyncio.sleep(2.0)

                    except Exception as e:
                        if not quiet:
                            console.print(
                                f"[yellow]Warning: Failed to get operation status: {str(e)}[/yellow]"
                            )
                        # Continue polling instead of breaking - temporary status errors shouldn't kill the loop
                        await asyncio.sleep(2.0)
                        continue

            # If we reach here and cancelled is True, the operation was cancelled
            if cancelled:
                if not quiet:
                    console.print("🛑 [yellow]Operation cancelled by user[/yellow]")
                return

            # Get final operation status
            try:
                final_response = await api_client.get_operation_status(operation_id)

                # Handle None response
                if final_response is None:
                    if not quiet:
                        console.print(
                            "[red]❌ No response from API when getting operation status[/red]"
                        )
                    return

                operation_data = final_response.get("data", {})

                # Process final response using common handler
                return await _process_data_load_response(
                    final_response,
                    symbol,
                    timeframe,
                    mode,
                    output_format,
                    verbose,
                    quiet,
                    api_client,
                )

            except Exception as e:
                if not quiet:
                    console.print(
                        f"[red]❌ Error getting final operation status: {str(e)}[/red]"
                    )
                return

        finally:
            # Remove signal handler to avoid issues with event loop
            try:
                loop.remove_signal_handler(signal.SIGINT)
            except (ValueError, NotImplementedError):
                # Signal handling not supported on this platform, ignore
                pass

    except KeyboardInterrupt:
        if not quiet:
            console.print("\\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        if not verbose:
            httpx_logger.setLevel(original_level)
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
                console.print("\n📊 [bold]Detailed metrics:[/bold]")
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
            console.print("❌ [bold red]Data loading failed![/bold red]")

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
                console.print("\n🔍 [bold]Error details:[/bold]")
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
            console.print("✅ Retrieved data range information")

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
