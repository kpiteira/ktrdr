"""
Data service for the KTRDR API.

This module provides services for accessing OHLCV data and related functionality,
bridging the API endpoints with the core KTRDR data modules.
"""

import logging
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
import pandas as pd
import time

from ktrdr import get_logger, log_entry_exit, log_performance, log_data_operation
from ktrdr.data import DataManager
from ktrdr.errors import DataError, DataNotFoundError, retry_with_backoff, RetryConfig
from ktrdr.api.services.base import BaseService

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
        include_metadata: bool = True,
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
        logger.info(f"Loading data for {symbol} ({timeframe})")

        try:
            # Load data using the DataManager
            df = self.data_manager.load_data(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                validate=True,
                repair=False,
            )

            # Convert DataFrame to API response format
            result = self._convert_df_to_api_format(
                df, symbol, timeframe, include_metadata
            )

            logger.info(f"Successfully loaded {len(df)} data points for {symbol}")
            return result

        except DataNotFoundError as e:
            logger.error(f"Data not found for {symbol} ({timeframe}): {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error loading data for {symbol} ({timeframe}): {str(e)}")
            raise DataError(
                message=f"Failed to load data for {symbol} ({timeframe}): {str(e)}",
                error_code="DATA-LoadError",
                details={"symbol": symbol, "timeframe": timeframe},
            ) from e

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

            symbol_info = {
                "symbol": symbol,
                "name": symbol,  # Using symbol as name for now
                "type": "unknown",  # Could be enhanced with symbol type detection
                "exchange": "unknown",  # Could be enhanced with exchange information
                "available_timeframes": timeframes,
            }

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
