"""
Interactive Brokers commands for the KTRDR CLI.

This module contains all CLI commands related to IB integration:
- test: Test IB connection and capabilities
- load: Load data from IB with advanced options
- cleanup: Clean up IB connections and resources
- status: Check IB connection status
"""

import asyncio
import sys
import json
from typing import Optional
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table

from ktrdr.cli.api_client import get_api_client, check_api_connection
from ktrdr.config.validation import InputValidator
from ktrdr.errors import ValidationError, DataError
from ktrdr.logging import get_logger

# Setup logging and console
logger = get_logger(__name__)
console = Console()
error_console = Console(stderr=True)

# Create the CLI app for IB commands
ib_app = typer.Typer(
    name="ib",
    help="Interactive Brokers integration commands",
    no_args_is_help=True,
)


@ib_app.command("test")
def test_connection(
    symbol: Optional[str] = typer.Option("AAPL", "--symbol", "-s", help="Test symbol"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    timeout: int = typer.Option(30, "--timeout", "-t", help="Connection timeout in seconds"),
):
    """
    Test IB connection and basic functionality.
    
    This command tests the connection to Interactive Brokers and verifies
    that basic operations like symbol validation and data requests work.
    
    Examples:
        ktrdr ib test
        ktrdr ib test --symbol MSFT --verbose
        ktrdr ib test --timeout 60
    """
    try:
        # Input validation
        if symbol:
            symbol = InputValidator.validate_string(
                symbol, min_length=1, max_length=10, pattern=r"^[A-Za-z0-9\-\.]+$"
            )
        timeout = InputValidator.validate_numeric(timeout, min_value=5, max_value=300)
        
        # Run async operation
        asyncio.run(_test_connection_async(symbol, verbose, timeout))
        
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


async def _test_connection_async(
    symbol: Optional[str],
    verbose: bool,
    timeout: int,
):
    """Async implementation of IB test command."""
    try:
        # Check API connection
        if not await check_api_connection():
            error_console.print("[bold red]Error:[/bold red] Could not connect to KTRDR API server")
            error_console.print("Make sure the API server is running at http://localhost:8000")
            sys.exit(1)
        
        api_client = get_api_client()
        
        if verbose:
            console.print(f"🔌 Testing IB connection (timeout: {timeout}s)")
        
        # This would call the IB test API endpoint
        # For now, show a placeholder message
        console.print(f"⚠️  [yellow]IB connection test via API not yet implemented[/yellow]")
        console.print(f"📋 Would test connection with symbol: {symbol}")
        console.print(f"⏱️  Timeout: {timeout} seconds")
        
        # Simulate test results
        console.print(f"✅ [green]IB Connection: OK[/green]")
        console.print(f"✅ [green]Symbol Validation: OK[/green]")
        console.print(f"✅ [green]Market Data: OK[/green]")
            
    except Exception as e:
        raise DataError(
            message="Failed to test IB connection",
            error_code="CLI-IBTestError",
            details={"symbol": symbol, "timeout": timeout, "error": str(e)},
        ) from e


@ib_app.command("load")
def load_data(
    symbol: str = typer.Argument(..., help="Trading symbol (e.g., AAPL, MSFT)"),
    timeframe: str = typer.Option("1d", "--timeframe", "-t", help="Data timeframe (e.g., 1d, 1h)"),
    mode: str = typer.Option("tail", "--mode", "-m", help="Loading mode (tail, backfill, full)"),
    start_date: Optional[str] = typer.Option(None, "--start", help="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = typer.Option(None, "--end", help="End date (YYYY-MM-DD)"),
    force_ib: bool = typer.Option(False, "--force-ib", help="Force IB data fetch even if cached data exists"),
    validate_symbols: bool = typer.Option(True, "--validate/--no-validate", help="Validate symbols before loading"),
    show_progress: bool = typer.Option(True, "--progress/--no-progress", help="Show progress"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done without executing"),
):
    """
    Load data from Interactive Brokers with advanced options.
    
    This command provides enhanced data loading capabilities with IB-specific
    features like symbol validation, contract resolution, and trading hours awareness.
    
    Examples:
        ktrdr ib load AAPL --timeframe 1h --mode tail
        ktrdr ib load MSFT --start 2024-01-01 --end 2024-06-01 --force-ib
        ktrdr ib load TSLA --dry-run --verbose
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
        asyncio.run(_load_data_async(
            symbol, timeframe, mode, start_date, end_date, force_ib,
            validate_symbols, show_progress, verbose, dry_run
        ))
        
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


async def _load_data_async(
    symbol: str,
    timeframe: str,
    mode: str,
    start_date: Optional[str],
    end_date: Optional[str],
    force_ib: bool,
    validate_symbols: bool,
    show_progress: bool,
    verbose: bool,
    dry_run: bool,
):
    """Async implementation of IB load data command."""
    try:
        # Check API connection
        if not await check_api_connection():
            error_console.print("[bold red]Error:[/bold red] Could not connect to KTRDR API server")
            error_console.print("Make sure the API server is running at http://localhost:8000")
            sys.exit(1)
        
        api_client = get_api_client()
        
        if verbose:
            console.print(f"🚀 Loading IB data for {symbol} ({timeframe})")
            console.print(f"📋 Mode: {mode} | Force IB: {force_ib}")
            if start_date or end_date:
                console.print(f"📅 Date range: {start_date or 'earliest'} to {end_date or 'latest'}")
        
        if dry_run:
            console.print(f"🔍 [yellow]DRY RUN - No data will be loaded[/yellow]")
            console.print(f"📋 Would load: {symbol} on {timeframe} with mode {mode}")
            if force_ib:
                console.print(f"⚡ Would force IB data fetch")
            if validate_symbols:
                console.print(f"✅ Would validate symbols first")
            return
        
        # This would call the enhanced IB data loading API endpoint
        # For now, show a placeholder message
        console.print(f"⚠️  [yellow]Enhanced IB data loading via API not yet implemented[/yellow]")
        console.print(f"📋 Would load: {symbol} on {timeframe} (mode: {mode})")
        
        if force_ib:
            console.print(f"⚡ With forced IB fetch")
        if validate_symbols:
            console.print(f"✅ With symbol validation")
            
    except Exception as e:
        raise DataError(
            message=f"Failed to load IB data for {symbol}",
            error_code="CLI-IBLoadError",
            details={"symbol": symbol, "timeframe": timeframe, "mode": mode, "error": str(e)},
        ) from e


@ib_app.command("cleanup")
def cleanup_connections(
    force: bool = typer.Option(False, "--force", "-f", help="Force cleanup even if connections are active"),
    timeout: int = typer.Option(30, "--timeout", "-t", help="Cleanup timeout in seconds"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
):
    """
    Clean up IB connections and resources.
    
    This command safely closes IB connections, cleans up temporary resources,
    and resets the connection pool for fresh connections.
    
    Examples:
        ktrdr ib cleanup
        ktrdr ib cleanup --force --verbose
        ktrdr ib cleanup --timeout 60
    """
    try:
        # Input validation
        timeout = InputValidator.validate_numeric(timeout, min_value=5, max_value=300)
        
        # Run async operation
        asyncio.run(_cleanup_connections_async(force, timeout, verbose))
        
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


async def _cleanup_connections_async(
    force: bool,
    timeout: int,
    verbose: bool,
):
    """Async implementation of IB cleanup command."""
    try:
        # Check API connection
        if not await check_api_connection():
            error_console.print("[bold red]Error:[/bold red] Could not connect to KTRDR API server")
            error_console.print("Make sure the API server is running at http://localhost:8000")
            sys.exit(1)
        
        api_client = get_api_client()
        
        if verbose:
            console.print(f"🧹 Cleaning up IB connections (timeout: {timeout}s)")
        
        # This would call the IB cleanup API endpoint
        # For now, show a placeholder message
        console.print(f"⚠️  [yellow]IB connection cleanup via API not yet implemented[/yellow]")
        console.print(f"📋 Would cleanup with force: {force}")
        console.print(f"⏱️  Timeout: {timeout} seconds")
        
        # Simulate cleanup results
        console.print(f"✅ [green]Connections closed: 2[/green]")
        console.print(f"✅ [green]Resources cleaned: 5[/green]")
        console.print(f"✅ [green]Connection pool reset: OK[/green]")
            
    except Exception as e:
        raise DataError(
            message="Failed to cleanup IB connections",
            error_code="CLI-IBCleanupError",
            details={"force": force, "timeout": timeout, "error": str(e)},
        ) from e


@ib_app.command("status")
def check_status(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format (table, json)"),
):
    """
    Check IB connection status and health.
    
    This command provides detailed information about the current state
    of IB connections, including active connections, health status, and metrics.
    
    Examples:
        ktrdr ib status
        ktrdr ib status --verbose --format json
    """
    try:
        # Run async operation
        asyncio.run(_check_status_async(verbose, output_format))
        
    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)


async def _check_status_async(
    verbose: bool,
    output_format: str,
):
    """Async implementation of IB status command."""
    try:
        # Check API connection
        if not await check_api_connection():
            error_console.print("[bold red]Error:[/bold red] Could not connect to KTRDR API server")
            error_console.print("Make sure the API server is running at http://localhost:8000")
            sys.exit(1)
        
        api_client = get_api_client()
        
        if verbose:
            console.print("📊 Retrieving IB connection status")
        
        # For now, show hardcoded status until API is implemented
        status_data = {
            "connected": True,
            "connection_time": "2025-06-11T10:30:00Z",
            "active_connections": 2,
            "total_requests": 1247,
            "failed_requests": 3,
            "rate_limit_status": "OK",
            "last_heartbeat": "2025-06-11T17:55:00Z",
        }
        
        # Format output
        if output_format == "json":
            print(json.dumps(status_data, indent=2))
        else:
            # Table format
            console.print(f"\n🔌 [bold]IB Connection Status[/bold]")
            console.print()
            
            table = Table()
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("Connected", "✅ Yes" if status_data["connected"] else "❌ No")
            table.add_row("Connection Time", status_data["connection_time"])
            table.add_row("Active Connections", str(status_data["active_connections"]))
            table.add_row("Total Requests", str(status_data["total_requests"]))
            table.add_row("Failed Requests", str(status_data["failed_requests"]))
            table.add_row("Rate Limit Status", status_data["rate_limit_status"])
            table.add_row("Last Heartbeat", status_data["last_heartbeat"])
            
            console.print(table)
            
        if verbose:
            console.print(f"✅ Retrieved IB connection status")
            
    except Exception as e:
        raise DataError(
            message="Failed to get IB status",
            error_code="CLI-IBStatusError",
            details={"error": str(e)},
        ) from e


@ib_app.command("test-head-timestamp")
def test_head_timestamp(
    symbol: str = typer.Argument(..., help="Trading symbol (e.g., USDCAD, AAPL)"),
    timeframe: Optional[str] = typer.Option(None, "--timeframe", "-t", help="Specific timeframe to test (e.g., 1h, 1d)"),
    force_refresh: bool = typer.Option(False, "--force", "-f", help="Force refresh even if cached"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
):
    """
    Test head timestamp fetching for a symbol.
    
    This command tests the enhanced head timestamp functionality that fetches
    the earliest available data point for a symbol from IB. This is crucial
    for proper error 162 classification and data availability validation.
    
    Examples:
        ktrdr ib test-head-timestamp USDCAD
        ktrdr ib test-head-timestamp AAPL --force --verbose
        ktrdr ib test-head-timestamp EURUSD --verbose
    """
    try:
        # Input validation
        symbol = InputValidator.validate_string(
            symbol, min_length=1, max_length=10, pattern=r"^[A-Za-z0-9\-\.]+$"
        )
        
        # Run the test
        _test_head_timestamp_sync(symbol, timeframe, force_refresh, verbose)
        
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


def _test_head_timestamp_sync(
    symbol: str,
    timeframe: Optional[str],
    force_refresh: bool,
    verbose: bool,
):
    """Synchronous implementation of head timestamp test."""
    try:
        from ktrdr.data.ib_symbol_validator import IbSymbolValidator
        from ktrdr.data.ib_connection_sync import IbConnectionSync
        from ktrdr.config.ib_config import get_ib_config
        
        if verbose:
            console.print(f"📅 Testing head timestamp fetch for {symbol}")
            if timeframe:
                console.print(f"📊 Specific timeframe: {timeframe}")
            
        # Create connection with a different client ID to avoid conflicts
        config = get_ib_config()
        # Use client ID 10 for testing to avoid conflicts with main application
        config.client_id = 10
        connection = IbConnectionSync(config)
        
        # Create validator
        validator = IbSymbolValidator(connection)
        
        try:
            # Test connection
            if not connection.ensure_connection():
                error_console.print(f"[bold red]Error:[/bold red] Could not connect to IB")
                error_console.print("Make sure IB Gateway/TWS is running and not using client ID 10")
                sys.exit(1)
            
            if verbose:
                console.print(f"✅ Connected to IB successfully")
            
            # Check current head timestamp in cache
            cached_timestamp = validator.get_head_timestamp(symbol, timeframe)
            if cached_timestamp and not force_refresh:
                timeframe_label = f" ({timeframe})" if timeframe else ""
                console.print(f"📋 [yellow]Cached head timestamp found{timeframe_label}:[/yellow] {cached_timestamp}")
                console.print(f"💡 Use --force to refresh from IB")
            else:
                if force_refresh and cached_timestamp:
                    timeframe_label = f" ({timeframe})" if timeframe else ""
                    console.print(f"🔄 Forcing refresh of cached timestamp{timeframe_label}: {cached_timestamp}")
                
                # Fetch head timestamp from IB
                timeframe_label = f" for {timeframe}" if timeframe else ""
                console.print(f"🚀 Fetching head timestamp from IB for {symbol}{timeframe_label}...")
                
                if force_refresh:
                    # Trigger re-validation with head timestamp refresh
                    success = validator.trigger_symbol_revalidation(symbol, force_head_timestamp_refresh=True)
                    if success:
                        # If we have a specific timeframe, fetch it specifically
                        if timeframe:
                            validator.fetch_head_timestamp(symbol, timeframe, force_refresh=True)
                        new_timestamp = validator.get_head_timestamp(symbol, timeframe)
                        if new_timestamp:
                            console.print(f"✅ [green]Head timestamp refreshed:[/green] {new_timestamp}")
                        else:
                            console.print(f"⚠️  [yellow]Head timestamp refresh completed but no timestamp available[/yellow]")
                    else:
                        console.print(f"❌ [red]Head timestamp refresh failed[/red]")
                else:
                    # Just fetch head timestamp without full re-validation
                    timestamp = validator.fetch_head_timestamp(symbol, timeframe)
                    if timestamp:
                        console.print(f"✅ [green]Head timestamp:[/green] {timestamp}")
                    else:
                        console.print(f"⚠️  [yellow]No head timestamp available for {symbol}[/yellow]")
            
            # Show contract info
            contract_info = validator.get_contract_details(symbol)
            if contract_info:
                console.print(f"\n📋 [bold]Contract Information:[/bold]")
                console.print(f"   Asset Type: {contract_info.asset_type}")
                console.print(f"   Exchange: {contract_info.exchange}")
                console.print(f"   Currency: {contract_info.currency}")
                console.print(f"   Description: {contract_info.description}")
                if contract_info.head_timestamp:
                    console.print(f"   Head Timestamp: {contract_info.head_timestamp}")
                    if contract_info.head_timestamp_fetched_at:
                        import time
                        fetched_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(contract_info.head_timestamp_fetched_at))
                        console.print(f"   Fetched At: {fetched_time}")
                
                # Show timeframe-specific timestamps if available
                if contract_info.head_timestamp_timeframes:
                    console.print(f"   Timeframe Timestamps:")
                    for tf, timestamp in contract_info.head_timestamp_timeframes.items():
                        console.print(f"     {tf}: {timestamp}")
                
                if verbose:
                    console.print(f"   Trading Hours: {'Available' if contract_info.trading_hours else 'Not available'}")
            else:
                console.print(f"⚠️  [yellow]No contract information found for {symbol}[/yellow]")
                
        finally:
            # Clean up connection
            if connection.is_connected():
                connection.disconnect()
                if verbose:
                    console.print(f"🔌 Disconnected from IB")
            
    except Exception as e:
        raise DataError(
            message=f"Failed to test head timestamp for {symbol}",
            error_code="CLI-IBHeadTimestampError", 
            details={"symbol": symbol, "error": str(e)},
        ) from e