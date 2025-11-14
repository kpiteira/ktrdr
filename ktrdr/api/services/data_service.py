"""
Data service for the KTRDR API.

This module provides services for accessing OHLCV data and related functionality,
bridging the API endpoints with the core KTRDR data modules.
"""

import time
from datetime import datetime
from typing import Any, Optional, Union

import pandas as pd

from ktrdr import get_logger, log_entry_exit, log_performance
from ktrdr.api.services.base import BaseService
from ktrdr.data.repository import DataRepository
from ktrdr.errors import DataError, DataNotFoundError
from ktrdr.monitoring.service_telemetry import trace_service_method

# Setup module-level logger
logger = get_logger(__name__)


class DataService(BaseService):
    """
    Service for accessing and managing OHLCV data.

    This service provides access to cached data via DataRepository,
    offering symbol listing, data retrieval, and metadata operations.
    For data downloads, use DataAcquisitionService.
    """

    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize the DataService.

        Args:
            data_dir: Optional path to the data directory
        """
        super().__init__()  # Initialize BaseService
        self.repository = DataRepository(data_dir=data_dir)
        self.logger.info("DataService initialized with DataRepository")

    @trace_service_method("data.load_cache")
    @log_entry_exit(logger=logger, log_args=True)
    @log_performance(threshold_ms=200, logger=logger)
    def load_cached_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        validate: bool = True,
        repair: bool = False,
    ) -> Optional[pd.DataFrame]:
        """
        Load cached data from local storage for frontend visualization.

        This method uses DataRepository for fast, synchronous cache reads,
        returning a DataFrame for API endpoints that need to apply additional
        processing like trading hours filtering and format conversion.

        Args:
            symbol: Trading symbol (e.g., 'AAPL', 'MSFT')
            timeframe: Data timeframe (e.g., '1d', '1h')
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            validate: Whether to validate the data (not used - Repository always validates)
            repair: Whether to repair the data (not used - Repository handles repair)

        Returns:
            DataFrame with OHLCV data or None if no data found

        Raises:
            DataError: For data-related errors
            DataNotFoundError: If data not found in cache
        """
        # Delegate to DataRepository for fast, synchronous cache reads
        return self.repository.load_from_cache(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
        )

    def _convert_df_to_api_format(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        include_metadata: bool = True,
    ) -> dict[str, Any]:
        """Convert pandas DataFrame to API response format."""
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

    @trace_service_method("data.list_symbols")
    @log_entry_exit(logger=logger)
    @log_performance(threshold_ms=100, logger=logger)
    async def get_available_symbols(self) -> list[dict[str, Any]]:
        """
        Get list of available symbols with metadata.

        Uses DataRepository to get cached symbols, then enriches with metadata.

        Returns:
            List of symbol information dictionaries
        """
        start_time = time.time()
        logger.info("Starting get_available_symbols (using DataRepository)")

        # Get available symbols from repository
        symbols = self.repository.get_available_symbols()
        logger.debug(f"Retrieved {len(symbols)} unique symbols from repository")

        # Get available data files for timeframe mapping
        available_files = self.repository.get_available_data_files()

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

            # Get date range using repository
            date_range = None
            if timeframes:
                try:
                    # Use repository to get date range
                    range_info = self.repository.get_data_range(symbol, timeframes[0])
                    if range_info.get("exists"):
                        date_range = (
                            range_info["start_date"],
                            range_info["end_date"],
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
                # Handle both datetime and string formats
                if isinstance(start_date, str):
                    symbol_info["start_date"] = start_date
                else:
                    symbol_info["start_date"] = start_date.isoformat()
                if isinstance(end_date, str):
                    symbol_info["end_date"] = end_date
                else:
                    symbol_info["end_date"] = end_date.isoformat()

            result.append(symbol_info)

        elapsed = time.time() - start_time
        logger.info(
            f"Retrieved {len(result)} unique symbols (from repository) in {elapsed:.3f}s"
        )
        return result

    def _get_symbols_metadata(self) -> dict[str, dict[str, Any]]:
        """Get symbol metadata from cache."""
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
        """Map IB asset types to user-friendly types."""
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
        """Filter dataframe to trading hours."""
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

    @trace_service_method("data.list_timeframes_for_symbol")
    @log_entry_exit(logger=logger)
    async def get_available_timeframes_for_symbol(self, symbol: str) -> list[str]:
        """
        Get available timeframes for a specific symbol.

        Args:
            symbol: Trading symbol

        Returns:
            List of available timeframes for this symbol
        """
        # Get available data files from repository
        available_files = self.repository.get_available_data_files()

        # Filter timeframes for the specified symbol
        timeframes = sorted(
            timeframe
            for file_symbol, timeframe in available_files
            if file_symbol == symbol
        )

        logger.debug(f"Found {len(timeframes)} available timeframes for {symbol}")
        return timeframes

    @trace_service_method("data.list_timeframes")
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

    @trace_service_method("data.get_range")
    @log_entry_exit(logger=logger, log_args=True)
    @log_performance(threshold_ms=500, logger=logger)
    async def get_data_range(self, symbol: str, timeframe: str) -> dict[str, Any]:
        """
        Get the available date range for a symbol and timeframe.

        Uses DataRepository to get date range information from cache.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe

        Returns:
            Dictionary with date range information

        Raises:
            DataNotFoundError: If data is not found
        """
        try:
            # Use repository to get date range
            range_info = self.repository.get_data_range(symbol, timeframe)

            # Repository returns dict with start_date, end_date, rows, exists
            if not range_info.get("exists"):
                raise DataNotFoundError(
                    message=f"Data not found for {symbol} ({timeframe})",
                    error_code="DATA-FileNotFound",
                    details={"symbol": symbol, "timeframe": timeframe},
                )

            # Extract dates (may be datetime or string)
            start_date = range_info["start_date"]
            end_date = range_info["end_date"]

            # Convert to ISO format if needed
            if not isinstance(start_date, str):
                start_date = start_date.isoformat()
            if not isinstance(end_date, str):
                end_date = end_date.isoformat()

            result = {
                "symbol": symbol,
                "timeframe": timeframe,
                "start_date": start_date,
                "end_date": end_date,
                "point_count": range_info.get("rows", 0),
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

    @trace_service_method("data.health_check")
    async def health_check(self) -> dict[str, Any]:
        """
        Perform a health check on the data service.

        Returns:
            Dict[str, Any]: Health check information
        """
        try:
            # Check if we can access the data directory
            data_dir = self.repository.data_dir
            data_files = self.repository.get_available_data_files()

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
