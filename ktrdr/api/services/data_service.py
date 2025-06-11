"""
Data service for the KTRDR API.

This module provides services for accessing OHLCV data and related functionality,
bridging the API endpoints with the core KTRDR data modules.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
import pandas as pd
import time

from ktrdr import get_logger, log_entry_exit, log_performance, log_data_operation
from ktrdr.data import DataManager
from ktrdr.errors import DataError, DataNotFoundError, retry_with_backoff, RetryConfig
from ktrdr.api.services.base import BaseService
from ktrdr.api.services.operations_service import get_operations_service
from ktrdr.api.models.operations import OperationType, OperationMetadata, OperationProgress

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
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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
            )

            # Apply trading hours filtering if requested
            if filters and filters.get("trading_hours_only") and df is not None and not df.empty:
                df = self._filter_trading_hours(df, symbol, filters.get("include_extended", False))
            
            execution_time = time.time() - start_time
            
            # Return enhanced format with metrics
            result = {
                "status": "success",
                "fetched_bars": len(df) if df is not None and not df.empty else 0,
                "cached_before": True,  # Will be enhanced when DataManager provides this info
                "merged_file": f"data/{symbol}_{timeframe}.csv",
                "gaps_analyzed": 0,  # Using intelligent gap classification - only unexpected gaps are reported
                "segments_fetched": 0,  # Will be enhanced when DataManager provides this info
                "external_requests_made": 0 if mode == "local" else 0,  # Will be enhanced when DataManager provides this info
                "execution_time_seconds": execution_time,
                "error_message": None,
            }

            logger.info(f"Successfully loaded {result['fetched_bars']} bars for {symbol}")
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
                "external_requests_made": 0,
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
        filters: Optional[Dict[str, Any]] = None,
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
        task = asyncio.create_task(self._run_data_loading_operation(
            operation_id, symbol, timeframe, start_date, end_date, mode, filters
        ))
        
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
        filters: Optional[Dict[str, Any]],
    ) -> None:
        """
        Run the actual data loading operation with progress tracking.
        
        This method performs the data loading while updating operation progress
        and handling cancellation requests.
        """
        try:
            logger.info(f"Starting data loading operation: {operation_id}")
            
            # Update progress - starting
            await self.operations_service.update_progress(
                operation_id,
                OperationProgress(
                    percentage=0.0,
                    current_step="Initializing data loading",
                    steps_completed=0,
                    steps_total=10,  # Estimated steps
                )
            )
            
            # Check for cancellation before starting heavy work
            operation = await self.operations_service.get_operation(operation_id)
            if operation and operation.is_cancelled_requested:
                logger.info(f"Operation {operation_id} was cancelled before starting")
                return
            
            # Update progress - analyzing requirements
            await self.operations_service.update_progress(
                operation_id,
                OperationProgress(
                    percentage=10.0,
                    current_step="Analyzing data requirements",
                    steps_completed=1,
                    steps_total=10,
                )
            )
            
            # Simulate some work (this would be the actual DataManager call)
            start_time = time.time()
            
            # Update progress - loading data
            await self.operations_service.update_progress(
                operation_id,
                OperationProgress(
                    percentage=30.0,
                    current_step=f"Loading {symbol} data ({mode} mode)",
                    steps_completed=3,
                    steps_total=10,
                )
            )
            
            # Check for cancellation during operation
            operation = await self.operations_service.get_operation(operation_id)
            if operation and operation.is_cancelled_requested:
                logger.info(f"Operation {operation_id} was cancelled during execution")
                return
            
            # Call the actual data loading method with cancellation support
            try:
                # Run data loading in executor with periodic cancellation checks
                result = await self._cancellable_data_load(
                    operation_id=operation_id,
                    symbol=symbol,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date,
                    mode=mode,
                    filters=filters,
                )
                
                # Update progress - processing results
                await self.operations_service.update_progress(
                    operation_id,
                    OperationProgress(
                        percentage=80.0,
                        current_step="Processing loaded data",
                        steps_completed=8,
                        steps_total=10,
                        items_processed=result.get("fetched_bars", 0),
                        items_total=result.get("fetched_bars", 0),
                    )
                )
                
                # Check for cancellation before completing
                operation = await self.operations_service.get_operation(operation_id)
                if operation and operation.is_cancelled_requested:
                    logger.info(f"Operation {operation_id} was cancelled before completion")
                    return
                
                # Complete the operation
                execution_time = time.time() - start_time
                result_summary = {
                    "status": result.get("status", "success"),
                    "fetched_bars": result.get("fetched_bars", 0),
                    "execution_time_seconds": execution_time,
                    "mode": mode,
                    "symbol": symbol,
                    "timeframe": timeframe,
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
                logger.error(f"Data loading operation failed: {operation_id} - {str(e)}")
                
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
            logger.error(f"Unexpected error in data loading operation: {operation_id} - {str(e)}")

    async def _cancellable_data_load(
        self,
        operation_id: str,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]],
        end_date: Optional[Union[str, datetime]],
        mode: str,
        filters: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Run data loading with cancellation support and progress updates.
        
        This method runs the synchronous data loading in an executor
        and periodically checks for cancellation requests while providing
        simulated progress updates.
        """
        import concurrent.futures
        import threading
        import time
        
        # Create a flag to signal cancellation to the worker thread
        cancel_event = threading.Event()
        progress_counter = [0]  # Mutable container for thread communication
        
        def run_data_load():
            """Run the actual data loading in a separate thread."""
            try:
                # Check cancellation flag periodically during execution
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
                )
                
                # Convert to API format
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
                
                # For now, return basic metrics
                # In a full implementation, DataManager would return these metrics
                return {
                    "status": "success",
                    "fetched_bars": len(result),
                    "cached_before": True,  # Assume some data existed
                    "merged_file": f"{symbol}_{timeframe}.csv",
                    "gaps_analyzed": 1,  # Simplified
                    "segments_fetched": 1,  # Simplified  
                    "ib_requests_made": 1 if mode != "local" else 0,
                    "execution_time_seconds": 0.0,  # Will be calculated by caller
                }
                
            except Exception as e:
                # Convert exception to dict for async handling
                return {
                    "error": str(e),
                    "status": "failed",
                }
        
        # Run in executor with periodic cancellation checks and progress simulation
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            # Submit the task
            future = executor.submit(run_data_load)
            
            # Track progress simulation
            start_time = time.time()
            last_progress_update = 30.0  # Start where we left off
            
            # Poll for completion or cancellation with progress updates
            while not future.done():
                # Check if operation was cancelled
                operation = await self.operations_service.get_operation(operation_id)
                if operation and operation.is_cancelled_requested:
                    logger.info(f"Cancelling data loading operation: {operation_id}")
                    
                    # Set cancellation flag for worker thread
                    cancel_event.set()
                    
                    # Cancel the future immediately
                    future.cancel()
                    
                    # Don't wait - just raise cancellation
                    logger.info(f"Data loading operation cancelled: {operation_id}")
                    raise asyncio.CancelledError("Operation was cancelled")
                
                # Simulate progress updates based on elapsed time
                elapsed_time = time.time() - start_time
                # Increase progress more gradually: 30% + (elapsed_seconds * 5%)
                simulated_progress = min(30.0 + (elapsed_time * 5.0), 95.0)
                
                if simulated_progress > last_progress_update + 5.0:  # Update every 5%
                    await self.operations_service.update_progress(
                        operation_id,
                        OperationProgress(
                            percentage=simulated_progress,
                            current_step=f"Loading {symbol} data segment {int(elapsed_time/5)+1}",
                            steps_completed=int(simulated_progress/10),
                            steps_total=10,
                            items_processed=int(elapsed_time * 100),  # Simulate items processed
                        )
                    )
                    last_progress_update = simulated_progress
                
                # Sleep briefly before checking again
                await asyncio.sleep(1.0)  # Check every second
            
            # Get the result
            try:
                result = future.result()
                if "error" in result:
                    raise DataError(
                        message=f"Data loading failed: {result['error']}",
                        error_code="DATA-LoadError",
                        details={"operation_id": operation_id, "symbol": symbol}
                    )
                return result
            except concurrent.futures.CancelledError:
                logger.info(f"Data loading future was cancelled: {operation_id}")
                raise asyncio.CancelledError("Operation was cancelled")

    def _convert_df_to_api_format(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        include_metadata: bool = True,
    ) -> Dict[str, Any]:
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
        dates = df.index.strftime("%Y-%m-%dT%H:%M:%S").tolist()

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
    async def get_available_symbols(self) -> List[Dict[str, Any]]:
        """
        Get list of available symbols with metadata.

        Returns:
            List of symbol information dictionaries
        """
        start_time = time.time()
        logger.info("Starting get_available_symbols (optimized method)")

        # Get available data files from the data_loader
        available_files = self.data_manager.data_loader.get_available_data_files()
        logger.debug(f"Processing {len(available_files)} data files to extract unique symbols")

        # Extract unique symbols from the available files
        symbols = sorted(set(symbol for symbol, _ in available_files))
        logger.debug(f"Aggregated {len(available_files)} files into {len(symbols)} unique symbols")

        # Create a map of symbol to timeframes
        symbol_timeframes = {}
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
                "name": metadata.get("description", symbol),  # Use description from cache
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
    
    def _get_symbols_metadata(self) -> Dict[str, Dict[str, Any]]:
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
                from ktrdr.config.settings import get_settings
                settings = get_settings()
                data_dir = Path(settings.data_dir) if hasattr(settings, 'data_dir') else Path("data")
            except:
                data_dir = Path("data")
            
            cache_file = data_dir / "symbol_discovery_cache.json"
            
            if cache_file.exists():
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                return cache_data.get('cache', {})
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
            "unknown": "unknown"
        }
        return mapping.get(ib_asset_type, "unknown")
    
    def _filter_trading_hours(self, df: pd.DataFrame, symbol: str, include_extended: bool = False) -> pd.DataFrame:
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
            from ktrdr.utils.timezone_utils import TimestampManager
            from ktrdr.data.trading_hours import TradingHoursManager
            
            # Get symbol metadata for trading hours
            symbol_metadata = self._get_symbols_metadata()
            metadata = symbol_metadata.get(symbol, {})
            trading_hours = metadata.get("trading_hours")
            
            if not trading_hours:
                logger.warning(f"No trading hours metadata for {symbol}, returning unfiltered data")
                return df
            
            # Filter dataframe to trading hours
            mask = []
            for timestamp in df.index:
                try:
                    exchange = metadata.get("exchange", "")
                    asset_type = metadata.get("asset_type", "STK")
                    
                    # Use TradingHoursManager to check if market is open
                    is_open = TradingHoursManager.is_market_open(
                        timestamp, exchange, asset_type, include_extended=include_extended
                    )
                    mask.append(is_open)
                except Exception as e:
                    logger.debug(f"Error checking market hours for {timestamp}: {e}")
                    mask.append(True)  # Include by default if check fails
            
            filtered_df = df[mask]
            
            original_count = len(df)
            filtered_count = len(filtered_df)
            logger.info(f"Trading hours filter: {original_count} -> {filtered_count} bars ({symbol})")
            
            return filtered_df
            
        except Exception as e:
            logger.error(f"Error filtering trading hours for {symbol}: {e}")
            return df  # Return original data if filtering fails

    @log_entry_exit(logger=logger)
    async def get_available_timeframes_for_symbol(self, symbol: str) -> List[str]:
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
    async def get_available_timeframes(self) -> List[Dict[str, str]]:
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
    async def get_data_range(self, symbol: str, timeframe: str) -> Dict[str, Any]:
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

    def _filter_trading_hours(self, df: pd.DataFrame, trading_hours: Dict[str, Any], include_extended: bool = False) -> pd.DataFrame:
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
                logger.warning("DataFrame doesn't have datetime index, cannot filter trading hours")
                return df
                
            # Get timezone and trading hours info
            timezone = trading_hours.get('timezone', 'UTC')
            regular_hours = trading_hours.get('regular_hours', {})
            extended_hours = trading_hours.get('extended_hours', [])
            trading_days = trading_hours.get('trading_days', [0, 1, 2, 3, 4])  # Default to weekdays
            
            # Convert index to the exchange timezone
            df_tz = df.copy()
            if df_tz.index.tz is None:
                df_tz.index = df_tz.index.tz_localize('UTC')
            df_tz.index = df_tz.index.tz_convert(timezone)
            
            # Create boolean mask for filtering
            mask = pd.Series(False, index=df_tz.index)
            
            # Filter by trading days
            day_mask = df_tz.index.dayofweek.isin(trading_days)
            
            # Add regular hours
            if regular_hours:
                start_time = regular_hours.get('start', '09:30')
                end_time = regular_hours.get('end', '16:00')
                
                # Parse time strings
                start_hour, start_min = map(int, start_time.split(':'))
                end_hour, end_min = map(int, end_time.split(':'))
                
                # Create time-based mask
                time_mask = (
                    (df_tz.index.hour > start_hour) | 
                    ((df_tz.index.hour == start_hour) & (df_tz.index.minute >= start_min))
                ) & (
                    (df_tz.index.hour < end_hour) | 
                    ((df_tz.index.hour == end_hour) & (df_tz.index.minute <= end_min))
                )
                
                mask |= day_mask & time_mask
            
            # Add extended hours if requested
            if include_extended and extended_hours:
                for session in extended_hours:
                    start_time = session.get('start', '04:00')
                    end_time = session.get('end', '20:00')
                    
                    # Parse time strings  
                    start_hour, start_min = map(int, start_time.split(':'))
                    end_hour, end_min = map(int, end_time.split(':'))
                    
                    # Create time-based mask for extended session
                    extended_mask = (
                        (df_tz.index.hour > start_hour) | 
                        ((df_tz.index.hour == start_hour) & (df_tz.index.minute >= start_min))
                    ) & (
                        (df_tz.index.hour < end_hour) | 
                        ((df_tz.index.hour == end_hour) & (df_tz.index.minute <= end_min))
                    )
                    
                    mask |= day_mask & extended_mask
            
            # Apply the filter
            filtered_df = df[mask]
            
            logger.debug(f"Trading hours filter: {len(df)} -> {len(filtered_df)} data points")
            return filtered_df
            
        except Exception as e:
            logger.error(f"Error filtering trading hours: {str(e)}")
            # Return original data on error
            return df

    async def health_check(self) -> Dict[str, Any]:
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
