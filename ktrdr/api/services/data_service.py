"""
Data service for the KTRDR API.

This module provides services for accessing OHLCV data and related functionality,
bridging the API endpoints with the core KTRDR data modules.
"""

import asyncio
import time
from datetime import datetime
from typing import Any, Optional, Union

import pandas as pd

from ktrdr import get_logger, log_entry_exit, log_performance
from ktrdr.api.models.operations import (
    OperationMetadata,
    OperationType,
)
from ktrdr.api.services.base import BaseService
from ktrdr.api.services.operations_service import get_operations_service
from ktrdr.data import DataManager
from ktrdr.errors import DataError, DataNotFoundError, RetryConfig, retry_with_backoff

# Setup module-level logger
logger = get_logger(__name__)


class DataService(BaseService):
    """
    Service for accessing and managing OHLCV data.

    This service adapts the core DataManager functionality for API use,
    providing data loading, symbol listing, and related operations.
    """

    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize the DataService.

        Args:
            data_dir: Optional path to the data directory
        """
        super().__init__()  # Initialize BaseService
        self.data_manager = DataManager(data_dir=data_dir)
        self.operations_service = get_operations_service()
        self.logger.info("DataService initialized")

    @log_entry_exit(logger=logger, log_args=True)
    @log_performance(threshold_ms=500, logger=logger)
    @retry_with_backoff(
        retryable_exceptions=[DataError],
        config=RetryConfig(max_retries=3, base_delay=1.0, backoff_factor=2.0),
        logger=logger,
        is_retryable=lambda e: isinstance(e, DataError)
        and not isinstance(e, DataNotFoundError),
    )
    async def load_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        mode: str = "local",
        include_metadata: bool = True,
        filters: Optional[dict[str, Any]] = None,
        periodic_save_minutes: float = 2.0,
    ) -> dict[str, Any]:
        """
        Load OHLCV data for a symbol and timeframe.

        Args:
            symbol: Trading symbol (e.g., 'AAPL', 'EURUSD')
            timeframe: Data timeframe (e.g., '1d', '1h')
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            include_metadata: Whether to include metadata in the response

        Returns:
            Dictionary with loaded data in API format

        Raises:
            DataNotFoundError: If data is not found
            DataError: For other data-related errors
        """
        import time

        start_time = time.time()
        logger.info(f"Loading data for {symbol} ({timeframe}) - mode: {mode}")

        try:
            # Load data using the DataManager with mode support
            df = self.data_manager.load_data(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                mode=mode,  # Pass through the mode - DataManager decides whether to use IB
                validate=True,
                repair=False,
                periodic_save_minutes=periodic_save_minutes,
                # Note: No progress callback for sync operations
            )

            # Apply trading hours filtering if requested
            if (
                filters
                and filters.get("trading_hours_only")
                and df is not None
                and not df.empty
            ):
                df = self._filter_trading_hours(
                    df, symbol, filters.get("include_extended", False)
                )

            execution_time = time.time() - start_time

            # Return enhanced format with metrics
            result = {
                "status": "success",
                "fetched_bars": len(df) if df is not None and not df.empty else 0,
                "cached_before": True,  # Will be enhanced when DataManager provides this info
                "merged_file": f"data/{symbol}_{timeframe}.csv",
                "gaps_analyzed": 0,  # Using intelligent gap classification - only unexpected gaps are reported
                "segments_fetched": 0,  # Will be enhanced when DataManager provides this info
                "ib_requests_made": (
                    0 if mode == "local" else 0
                ),  # Will be enhanced when DataManager provides this info
                "execution_time_seconds": execution_time,
                "error_message": None,
            }

            logger.info(
                f"Successfully loaded {result['fetched_bars']} bars for {symbol}"
            )
            return result

        except DataNotFoundError as e:
            logger.error(f"Data not found for {symbol} ({timeframe}): {str(e)}")
            raise
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Error loading data for {symbol} ({timeframe}): {str(e)}")

            # Return failed status in enhanced format
            return {
                "status": "failed",
                "fetched_bars": 0,
                "cached_before": False,
                "merged_file": f"data/{symbol}_{timeframe}.csv",
                "gaps_analyzed": 0,
                "segments_fetched": 0,
                "ib_requests_made": 0,
                "execution_time_seconds": execution_time,
                "error_message": str(e),
            }

    async def start_data_loading_operation(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        mode: str = "tail",
        filters: Optional[dict[str, Any]] = None,
        periodic_save_minutes: float = 2.0,
    ) -> str:
        """
        Start a data loading operation that can be tracked and cancelled.

        This method creates an operation, registers it with the operations service,
        and starts the data loading process in the background.

        Args:
            symbol: Trading symbol (e.g., 'AAPL', 'EURUSD')
            timeframe: Data timeframe (e.g., '1d', '1h')
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            mode: Loading mode (tail, backfill, full)
            filters: Optional filters (trading_hours_only, include_extended)

        Returns:
            Operation ID for tracking the operation
        """
        # Create operation metadata
        metadata = OperationMetadata(
            symbol=symbol,
            timeframe=timeframe,
            mode=mode,
            start_date=start_date if isinstance(start_date, datetime) else None,
            end_date=end_date if isinstance(end_date, datetime) else None,
            parameters=filters or {},
        )

        # Create operation
        operation = await self.operations_service.create_operation(
            operation_type=OperationType.DATA_LOAD,
            metadata=metadata,
        )

        operation_id = operation.operation_id
        logger.info(f"Created data loading operation: {operation_id}")

        # Start the data loading task
        task = asyncio.create_task(
            self._run_data_loading_operation(
                operation_id,
                symbol,
                timeframe,
                start_date,
                end_date,
                mode,
                filters,
                periodic_save_minutes,
            )
        )

        # Register task with operations service
        await self.operations_service.start_operation(operation_id, task)

        return operation_id

    async def _run_data_loading_operation(
        self,
        operation_id: str,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]],
        end_date: Optional[Union[str, datetime]],
        mode: str,
        filters: Optional[dict[str, Any]],
        periodic_save_minutes: float,
    ) -> None:
        """
        Run the actual data loading operation with progress tracking.

        This method performs the data loading while updating operation progress
        and handling cancellation requests.
        """
        try:
            logger.info(f"Starting data loading operation: {operation_id}")
            start_time = time.time()

            # Call the actual data loading method with real progress tracking
            try:
                result = await self._cancellable_data_load(
                    operation_id=operation_id,
                    symbol=symbol,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date,
                    mode=mode,
                    filters=filters,
                    periodic_save_minutes=periodic_save_minutes,
                )

                # Complete the operation with real results
                execution_time = time.time() - start_time
                result_summary = {
                    "status": result.get("status", "success"),
                    "fetched_bars": result.get("fetched_bars", 0),
                    "execution_time_seconds": execution_time,
                    "mode": mode,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "cached_before": result.get("cached_before", False),
                    "merged_file": result.get("merged_file", ""),
                    "gaps_analyzed": result.get("gaps_analyzed", 0),
                    "segments_fetched": result.get("segments_fetched", 0),
                    "ib_requests_made": result.get("ib_requests_made", 0),
                }

                await self.operations_service.complete_operation(
                    operation_id, result_summary
                )

                logger.info(f"Completed data loading operation: {operation_id}")

            except Exception as e:
                # Handle operation failure
                await self.operations_service.fail_operation(
                    operation_id, f"Data loading failed: {str(e)}"
                )
                logger.error(
                    f"Data loading operation failed: {operation_id} - {str(e)}"
                )

        except asyncio.CancelledError:
            # Handle task cancellation
            logger.info(f"Data loading operation cancelled: {operation_id}")
            # The operations service will have already marked it as cancelled
            raise
        except Exception as e:
            # Handle unexpected errors
            await self.operations_service.fail_operation(
                operation_id, f"Unexpected error: {str(e)}"
            )
            logger.error(
                f"Unexpected error in data loading operation: {operation_id} - {str(e)}"
            )

    async def _cancellable_data_load(
        self,
        operation_id: str,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]],
        end_date: Optional[Union[str, datetime]],
        mode: str,
        filters: Optional[dict[str, Any]],
        periodic_save_minutes: float,
    ) -> dict[str, Any]:
        """
        Run data loading with cancellation support and real progress updates.

        This method creates a progress callback that updates the operations service
        with real progress from the DataManager and runs the data loading in an executor.
        """
        import concurrent.futures
        import threading

        # Create cancellation event for worker thread
        cancel_event = threading.Event()
        last_progress = [None]  # Mutable container for thread communication

        def progress_callback_fn(progress_state):
            """Callback function to update operation progress in real-time from ProgressManager."""
            try:
                # Convert ProgressState to OperationProgress
                from ktrdr.api.models.operations import OperationProgress

                operation_progress = OperationProgress(
                    percentage=progress_state.percentage,
                    current_step=progress_state.message,
                    steps_completed=progress_state.steps_completed,
                    steps_total=progress_state.steps_total,
                    items_processed=progress_state.items_processed,
                    items_total=progress_state.expected_items,
                    current_item=progress_state.step_detail
                    or progress_state.current_step_name,
                )

                # Store for async update (no warnings/errors from ProgressManager)
                last_progress[0] = (
                    operation_progress,
                    [],  # No warnings from ProgressManager
                    [],  # No errors from ProgressManager
                )

            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

        async def update_progress_periodically():
            """Periodically update the operations service with the latest progress."""
            while not cancel_event.is_set():
                if last_progress[0] is not None:
                    try:
                        progress_data, warnings, errors = last_progress[0]
                        await self.operations_service.update_progress(
                            operation_id, progress_data, warnings, errors
                        )
                    except Exception as e:
                        logger.warning(f"Failed to update progress: {e}")
                await asyncio.sleep(0.5)  # Update every 500ms for responsive UI

        def run_data_load():
            """Run the actual data loading with real progress tracking."""
            try:
                # Check cancellation before starting
                if cancel_event.is_set():
                    return {"status": "cancelled", "error": "Operation was cancelled"}

                result = self.data_manager.load_data(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date,
                    mode=mode,
                    validate=True,
                    repair=False,
                    cancellation_token=cancel_event,  # Pass cancellation event
                    progress_callback=progress_callback_fn,  # Real progress updates
                    periodic_save_minutes=periodic_save_minutes,
                )

                # Convert result to API format
                if result is None or result.empty:
                    return {
                        "status": "success",
                        "fetched_bars": 0,
                        "cached_before": False,
                        "merged_file": "",
                        "gaps_analyzed": 0,
                        "segments_fetched": 0,
                        "ib_requests_made": 0,
                        "execution_time_seconds": 0.0,
                    }

                return {
                    "status": "success",
                    "fetched_bars": len(result),
                    "cached_before": True,  # TODO: DataManager should provide this info
                    "merged_file": f"{symbol}_{timeframe}.csv",
                    "gaps_analyzed": 1,  # TODO: DataManager should provide this info
                    "segments_fetched": 1,  # TODO: DataManager should provide this info
                    "ib_requests_made": (
                        1 if mode != "local" else 0
                    ),  # TODO: DataManager should provide this info
                    "execution_time_seconds": 0.0,  # Will be calculated by caller
                }

            except Exception as e:
                logger.error(f"Data loading failed: {e}")
                return {
                    "error": str(e),
                    "status": "failed",
                }

        # Start periodic progress updates
        progress_task = asyncio.create_task(update_progress_periodically())

        # Create a cancellation event that can be triggered externally
        cancellation_event = asyncio.Event()

        # Store the cancellation event so the operations service can signal it
        self.operations_service._cancellation_events[operation_id] = cancellation_event

        async def check_cancellation():
            """Wait for external cancellation signal via event."""
            try:
                await cancellation_event.wait()  # Block until signaled
                logger.info(f"Cancelling data loading operation: {operation_id}")
                cancel_event.set()  # Signal the worker thread to stop
            except Exception as e:
                logger.warning(f"Error in cancellation checker: {e}")

        try:
            # Run data loading in executor with real-time progress updates
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_data_load)

                # Start the cancellation checker
                cancellation_task = asyncio.create_task(check_cancellation())

                # Wait for either completion or cancellation without blocking event loop
                done, pending = await asyncio.wait(
                    [asyncio.wrap_future(future), cancellation_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # Cancel any remaining tasks
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
        finally:
            # Clean up cancellation event
            if hasattr(self.operations_service, "_cancellation_events"):
                self.operations_service._cancellation_events.pop(operation_id, None)

            # Stop progress updates
            cancel_event.set()
            try:
                await asyncio.wait_for(progress_task, timeout=1.0)
            except asyncio.TimeoutError:
                progress_task.cancel()

            # Ensure ThreadPoolExecutor future result is retrieved to prevent logging warnings
            # This prevents "Future exception was never retrieved" messages in logs
            if "future" in locals():
                try:
                    if not future.done():
                        future.cancel()
                    # Retrieve result/exception to satisfy asyncio warning prevention
                    future.result()
                except (concurrent.futures.CancelledError, Exception):
                    # Expected for cancellation - ignore silently
                    pass

        # Process the result after cleanup
        try:
            # Check if cancellation was completed
            if cancellation_event.is_set():
                logger.info(f"Data loading operation was cancelled: {operation_id}")
                raise asyncio.CancelledError("Operation was cancelled")

            # Get result from the completed future
            completed_task = next(iter(done))
            if asyncio.isfuture(completed_task) or asyncio.iscoroutine(completed_task):
                # This was the data loading future
                try:
                    result = completed_task.result()

                    # Check both error key and failed status
                    if "error" in result or result.get("status") == "failed":
                        error_msg = result.get("error", "Unknown error")
                        raise DataError(
                            message=f"Data loading failed: {error_msg}",
                            error_code="DATA-LoadError",
                            details={
                                "operation_id": operation_id,
                                "symbol": symbol,
                            },
                        )
                    return result
                except concurrent.futures.CancelledError:
                    # Future was cancelled - this is expected for cancellation
                    logger.info(f"Data loading future was cancelled: {operation_id}")
                    raise asyncio.CancelledError("Operation was cancelled") from None
            else:
                # This was the cancellation task completing
                logger.info(f"Data loading operation was cancelled: {operation_id}")
                raise asyncio.CancelledError("Operation was cancelled")

        except concurrent.futures.CancelledError:
            logger.info(f"Data loading future was cancelled: {operation_id}")
            raise asyncio.CancelledError("Operation was cancelled") from None

    def _convert_df_to_api_format(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        include_metadata: bool = True,
    ) -> dict[str, Any]:
        """
        Convert pandas DataFrame to API response format.

        Args:
            df: DataFrame with OHLCV data
            symbol: Trading symbol
            timeframe: Data timeframe
            include_metadata: Whether to include metadata

        Returns:
            Dictionary with data in API format
        """
        if df.empty:
            return {
                "dates": [],
                "ohlcv": [],
                "metadata": {"symbol": symbol, "timeframe": timeframe, "points": 0},
            }

        # Format the dates as ISO strings
        dates = pd.to_datetime(df.index).strftime("%Y-%m-%dT%H:%M:%S").tolist()

        # Extract OHLCV data as nested list
        ohlcv = df[["open", "high", "low", "close", "volume"]].values.tolist()

        # Create the result dictionary
        result = {"dates": dates, "ohlcv": ohlcv}

        # Add metadata if requested
        if include_metadata:
            result["metadata"] = {
                "symbol": symbol,
                "timeframe": timeframe,
                "start_date": df.index.min().isoformat(),
                "end_date": df.index.max().isoformat(),
                "point_count": len(df),
            }

        return result

    @log_entry_exit(logger=logger)
    @log_performance(threshold_ms=100, logger=logger)
    async def get_available_symbols(self) -> list[dict[str, Any]]:
        """
        Get list of available symbols with metadata.

        Returns:
            List of symbol information dictionaries
        """
        start_time = time.time()
        logger.info("Starting get_available_symbols (optimized method)")

        # Get available data files from the data_loader
        available_files = self.data_manager.data_loader.get_available_data_files()
        logger.debug(
            f"Processing {len(available_files)} data files to extract unique symbols"
        )

        # Extract unique symbols from the available files
        symbols = sorted({symbol for symbol, _ in available_files})
        logger.debug(
            f"Aggregated {len(available_files)} files into {len(symbols)} unique symbols"
        )

        # Create a map of symbol to timeframes
        symbol_timeframes: dict[str, list[str]] = {}
        for symbol, timeframe in available_files:
            if symbol not in symbol_timeframes:
                symbol_timeframes[symbol] = []
            symbol_timeframes[symbol].append(timeframe)

        # Load symbol metadata from symbol cache
        symbol_metadata = self._get_symbols_metadata()

        # Build result with minimal information (without loading files)
        result = []
        for symbol in symbols:
            timeframes = sorted(symbol_timeframes.get(symbol, []))

            # Get date range using the lightweight method (no full data loading)
            date_range = None
            if timeframes:
                try:
                    # Use the optimized get_data_date_range method which doesn't load full files
                    date_range = self.data_manager.data_loader.get_data_date_range(
                        symbol, timeframes[0]
                    )
                except Exception as e:
                    logger.warning(f"Error getting date range for {symbol}: {str(e)}")

            # Get metadata from symbol cache if available
            metadata = symbol_metadata.get(symbol, {})

            symbol_info = {
                "symbol": symbol,
                "name": metadata.get(
                    "description", symbol
                ),  # Use description from cache
                "type": self._map_asset_type(metadata.get("asset_type", "unknown")),
                "exchange": metadata.get("exchange", "unknown"),
                "currency": metadata.get("currency", "unknown"),
                "available_timeframes": timeframes,
            }

            # Add trading hours if available
            trading_hours = metadata.get("trading_hours")
            if trading_hours:
                symbol_info["trading_hours"] = trading_hours

            # Add date range if available
            if date_range:
                start_date, end_date = date_range
                symbol_info["start_date"] = start_date.isoformat()
                symbol_info["end_date"] = end_date.isoformat()

            result.append(symbol_info)

        elapsed = time.time() - start_time
        logger.info(
            f"Retrieved {len(result)} unique symbols (from {len(available_files)} data files) in {elapsed:.3f}s"
        )
        return result

    def _get_symbols_metadata(self) -> dict[str, dict[str, Any]]:
        """
        Get symbol metadata from the symbol validation cache.

        Returns:
            Dictionary mapping symbol to metadata
        """
        try:
            import json
            from pathlib import Path

            # Try to get data directory from settings
            try:
                from ktrdr.config.settings import get_api_settings as get_settings

                settings = get_settings()
                data_dir = (
                    Path(settings.data_dir)
                    if hasattr(settings, "data_dir")
                    else Path("data")
                )
            except Exception:
                data_dir = Path("data")

            cache_file = data_dir / "symbol_discovery_cache.json"

            if cache_file.exists():
                with open(cache_file) as f:
                    cache_data = json.load(f)

                return cache_data.get("cache", {})
        except Exception as e:
            logger.warning(f"Could not load symbol metadata from cache: {e}")

        return {}

    def _map_asset_type(self, ib_asset_type: str) -> str:
        """
        Map IB asset types to user-friendly types.

        Args:
            ib_asset_type: IB asset type (STK, CASH, FUT, etc.)

        Returns:
            User-friendly asset type
        """
        mapping = {
            "STK": "stock",
            "CASH": "forex",
            "FUT": "futures",
            "OPT": "options",
            "IND": "index",
            "unknown": "unknown",
        }
        return mapping.get(ib_asset_type, "unknown")

    def _filter_trading_hours(
        self, df: pd.DataFrame, symbol: str, include_extended: bool = False
    ) -> pd.DataFrame:
        """
        Filter dataframe to only include trading hours.

        Args:
            df: DataFrame with datetime index
            symbol: Symbol to get trading hours for
            include_extended: Whether to include extended hours

        Returns:
            Filtered DataFrame
        """
        try:
            from ktrdr.data.trading_hours import TradingHoursManager

            # Get symbol metadata for trading hours
            symbol_metadata = self._get_symbols_metadata()
            metadata = symbol_metadata.get(symbol, {})
            trading_hours = metadata.get("trading_hours")

            if not trading_hours:
                logger.warning(
                    f"No trading hours metadata for {symbol}, returning unfiltered data"
                )
                return df

            # Filter dataframe to trading hours
            mask = []
            for timestamp in df.index:
                try:
                    exchange = metadata.get("exchange", "")
                    asset_type = metadata.get("asset_type", "STK")

                    # Use TradingHoursManager to check if market is open
                    is_open = TradingHoursManager.is_market_open(
                        timestamp,
                        exchange,
                        asset_type,
                        include_extended=include_extended,
                    )
                    mask.append(is_open)
                except Exception as e:
                    logger.debug(f"Error checking market hours for {timestamp}: {e}")
                    mask.append(True)  # Include by default if check fails

            filtered_df = df[mask]

            original_count = len(df)
            filtered_count = len(filtered_df)
            logger.info(
                f"Trading hours filter: {original_count} -> {filtered_count} bars ({symbol})"
            )

            return filtered_df

        except Exception as e:
            logger.error(f"Error filtering trading hours for {symbol}: {e}")
            return df  # Return original data if filtering fails

    @log_entry_exit(logger=logger)
    async def get_available_timeframes_for_symbol(self, symbol: str) -> list[str]:
        """
        Get available timeframes for a specific symbol.

        Args:
            symbol: Trading symbol

        Returns:
            List of available timeframes for this symbol
        """
        # Get available data files from the data_loader
        available_files = self.data_manager.data_loader.get_available_data_files()

        # Filter timeframes for the specified symbol
        timeframes = sorted(
            timeframe
            for file_symbol, timeframe in available_files
            if file_symbol == symbol
        )

        logger.debug(f"Found {len(timeframes)} available timeframes for {symbol}")
        return timeframes

    @log_entry_exit(logger=logger)
    async def get_available_timeframes(self) -> list[dict[str, str]]:
        """
        Get list of available timeframes with metadata.

        Returns:
            List of timeframe information dictionaries
        """
        # Define standard timeframes with metadata
        timeframes = [
            {"id": "1m", "name": "1 Minute", "description": "One-minute interval data"},
            {
                "id": "5m",
                "name": "5 Minutes",
                "description": "Five-minute interval data",
            },
            {
                "id": "15m",
                "name": "15 Minutes",
                "description": "Fifteen-minute interval data",
            },
            {
                "id": "30m",
                "name": "30 Minutes",
                "description": "Thirty-minute interval data",
            },
            {"id": "1h", "name": "1 Hour", "description": "One-hour interval data"},
            {"id": "2h", "name": "2 Hours", "description": "Two-hour interval data"},
            {"id": "4h", "name": "4 Hours", "description": "Four-hour interval data"},
            {"id": "1d", "name": "Daily", "description": "Daily interval data"},
            {"id": "1w", "name": "Weekly", "description": "Weekly interval data"},
            {"id": "1M", "name": "Monthly", "description": "Monthly interval data"},
        ]

        logger.info(f"Retrieved {len(timeframes)} available timeframes")
        return timeframes

    @log_entry_exit(logger=logger, log_args=True)
    @log_performance(threshold_ms=500, logger=logger)
    async def get_data_range(self, symbol: str, timeframe: str) -> dict[str, Any]:
        """
        Get the available date range for a symbol and timeframe.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe

        Returns:
            Dictionary with date range information

        Raises:
            DataNotFoundError: If data is not found
        """
        try:
            # Use lightweight date range method instead of full data summary
            date_range = self.data_manager.data_loader.get_data_date_range(
                symbol, timeframe
            )

            if date_range is None:
                raise DataNotFoundError(
                    message=f"Data not found for {symbol} ({timeframe})",
                    error_code="DATA-FileNotFound",
                    details={"symbol": symbol, "timeframe": timeframe},
                )

            start_date, end_date = date_range

            # Calculate estimated point count based on timeframe and date range
            duration = end_date - start_date
            if timeframe == "1h":
                estimated_points = duration.total_seconds() / 3600
            elif timeframe == "1d":
                estimated_points = duration.days
            elif timeframe == "1m":
                estimated_points = duration.total_seconds() / 60
            else:
                # Default fallback for unknown timeframes
                estimated_points = max(1, duration.days)

            result = {
                "symbol": symbol,
                "timeframe": timeframe,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "point_count": int(estimated_points),  # Use estimated count
            }

            logger.info(f"Retrieved date range for {symbol} ({timeframe})")
            return result

        except DataNotFoundError:
            logger.error(f"Data not found for {symbol} ({timeframe})")
            raise
        except Exception as e:
            logger.error(
                f"Error getting date range for {symbol} ({timeframe}): {str(e)}"
            )
            raise DataError(
                message=f"Failed to get date range for {symbol} ({timeframe}): {str(e)}",
                error_code="DATA-RangeError",
                details={"symbol": symbol, "timeframe": timeframe},
            ) from e

    def _filter_trading_hours_advanced(
        self,
        df: pd.DataFrame,
        trading_hours: dict[str, Any],
        include_extended: bool = False,
    ) -> pd.DataFrame:
        """
        Filter DataFrame to trading hours only.

        Args:
            df: DataFrame with datetime index
            trading_hours: Trading hours configuration
            include_extended: Whether to include extended trading hours

        Returns:
            Filtered DataFrame
        """
        try:
            if df is None or df.empty:
                return df

            # Ensure we have a datetime index
            if not isinstance(df.index, pd.DatetimeIndex):
                logger.warning(
                    "DataFrame doesn't have datetime index, cannot filter trading hours"
                )
                return df

            # Get timezone and trading hours info
            timezone = trading_hours.get("timezone", "UTC")
            regular_hours = trading_hours.get("regular_hours", {})
            extended_hours = trading_hours.get("extended_hours", [])
            trading_days = trading_hours.get(
                "trading_days", [0, 1, 2, 3, 4]
            )  # Default to weekdays

            # Convert index to the exchange timezone
            df_tz = df.copy()
            if (
                hasattr(df_tz.index, "tz")
                and df_tz.index.tz is None
                and hasattr(df_tz.index, "tz_localize")
            ):
                df_tz.index = df_tz.index.tz_localize("UTC")
            if hasattr(df_tz.index, "tz_convert"):
                df_tz.index = df_tz.index.tz_convert(timezone)

            # Create boolean mask for filtering
            mask = pd.Series(False, index=df_tz.index)

            # Filter by trading days
            if hasattr(df_tz.index, "dayofweek"):
                day_mask = df_tz.index.dayofweek.isin(trading_days)
            else:
                day_mask = pd.Series(True, index=df_tz.index)

            # Add regular hours
            if regular_hours:
                start_time = regular_hours.get("start", "09:30")
                end_time = regular_hours.get("end", "16:00")

                # Parse time strings
                start_hour, start_min = map(int, start_time.split(":"))
                end_hour, end_min = map(int, end_time.split(":"))

                # Create time-based mask
                if hasattr(df_tz.index, "hour") and hasattr(df_tz.index, "minute"):
                    time_mask = (
                        (df_tz.index.hour > start_hour)
                        | (
                            (df_tz.index.hour == start_hour)
                            & (df_tz.index.minute >= start_min)
                        )
                    ) & (
                        (df_tz.index.hour < end_hour)
                        | (
                            (df_tz.index.hour == end_hour)
                            & (df_tz.index.minute <= end_min)
                        )
                    )
                else:
                    time_mask = pd.Series(True, index=df_tz.index)

                mask |= day_mask & time_mask

            # Add extended hours if requested
            if include_extended and extended_hours:
                for session in extended_hours:
                    start_time = session.get("start", "04:00")
                    end_time = session.get("end", "20:00")

                    # Parse time strings
                    start_hour, start_min = map(int, start_time.split(":"))
                    end_hour, end_min = map(int, end_time.split(":"))

                    # Create time-based mask for extended session
                    if hasattr(df_tz.index, "hour") and hasattr(df_tz.index, "minute"):
                        extended_mask = (
                            (df_tz.index.hour > start_hour)
                            | (
                                (df_tz.index.hour == start_hour)
                                & (df_tz.index.minute >= start_min)
                            )
                        ) & (
                            (df_tz.index.hour < end_hour)
                            | (
                                (df_tz.index.hour == end_hour)
                                & (df_tz.index.minute <= end_min)
                            )
                        )
                    else:
                        extended_mask = pd.Series(True, index=df_tz.index)

                    mask |= day_mask & extended_mask

            # Apply the filter
            filtered_df = df[mask]

            logger.debug(
                f"Trading hours filter: {len(df)} -> {len(filtered_df)} data points"
            )
            return filtered_df

        except Exception as e:
            logger.error(f"Error filtering trading hours: {str(e)}")
            # Return original data on error
            return df

    async def health_check(self) -> dict[str, Any]:
        """
        Perform a health check on the data service.

        Returns:
            Dict[str, Any]: Health check information
        """
        try:
            # Check if we can access the data directory
            data_dir = self.data_manager.data_loader.data_dir
            data_files = self.data_manager.data_loader.get_available_data_files()

            return {
                "status": "healthy",
                "data_directory": data_dir,
                "available_files": len(data_files),
                "message": "Data service is functioning normally",
            }
        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "message": f"Data service health check failed: {str(e)}",
            }
