"""
DataRepository - Local cache management for market data.

This module provides fast, synchronous local cache operations for OHLCV data.
It composes LocalDataLoader for file I/O and DataQualityValidator for data validation.

Key characteristics:
- Pure synchronous operations (no async)
- No IB dependencies
- No Operations service dependencies
- Fast file I/O with validation
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd

from ktrdr import get_logger
from ktrdr.data.local_data_loader import LocalDataLoader
from ktrdr.data.repository.data_quality_validator import DataQualityValidator
from ktrdr.errors import DataNotFoundError

logger = get_logger(__name__)


class DataRepository:
    """
    Local cache repository for market data.

    Fast, synchronous operations for local cache CRUD.
    Composes LocalDataLoader and DataQualityValidator.

    No IB dependencies, no Operations tracking, no async overhead.
    """

    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize DataRepository.

        Args:
            data_dir: Directory for cache files. If None, uses environment
                     variable DATA_DIR or default './data'
        """
        # Determine data directory
        if data_dir is None:
            data_dir = os.getenv("DATA_DIR", "./data")

        logger.info(f"Initializing DataRepository with data_dir={data_dir}")

        # Compose LocalDataLoader for file I/O
        self.loader = LocalDataLoader(data_dir=data_dir)

        # Compose DataQualityValidator for validation
        # Use auto_correct=True to handle minor issues automatically
        self.validator = DataQualityValidator(auto_correct=True)

        logger.info("DataRepository initialized successfully")

    @property
    def data_dir(self) -> Path:
        """Get the data directory path from the loader."""
        return self.loader.data_dir

    def load_from_cache(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
    ) -> pd.DataFrame:
        """
        Load data from local cache.

        Fast, synchronous file read with validation.

        Args:
            symbol: Trading symbol (e.g., 'AAPL', 'EURUSD')
            timeframe: Timeframe (e.g., '1d', '1h', '5m')
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering

        Returns:
            DataFrame with OHLCV data

        Raises:
            DataNotFoundError: If cache file doesn't exist
            DataValidationError: If data validation fails
            DataError: For other data-related errors
        """
        logger.info(
            f"Loading data from cache: {symbol} {timeframe} "
            f"(start={start_date}, end={end_date})"
        )

        # Delegate to LocalDataLoader for file I/O
        # LocalDataLoader will raise DataNotFoundError if file doesn't exist
        df = self.loader.load(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
        )

        if df is None or df.empty:
            raise DataNotFoundError(
                message=f"No data found in cache for {symbol} {timeframe}",
                error_code="DATA-EmptyCache",
                details={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "start_date": str(start_date) if start_date else None,
                    "end_date": str(end_date) if end_date else None,
                },
            )

        logger.info(
            f"Successfully loaded {len(df)} rows from cache for {symbol} {timeframe}"
        )
        return df

    def save_to_cache(
        self,
        symbol: str,
        timeframe: str,
        data: pd.DataFrame,
    ) -> None:
        """
        Save data to local cache.

        Validates data before saving.
        Creates parent directories if needed.

        Args:
            symbol: Trading symbol (e.g., 'AAPL', 'EURUSD')
            timeframe: Timeframe (e.g., '1d', '1h', '5m')
            data: DataFrame with OHLCV data to save

        Raises:
            DataValidationError: If data fails validation
            DataError: For other save errors
        """
        logger.info(f"Saving {len(data)} rows to cache: {symbol} {timeframe}")

        try:
            # Validate data before saving
            # LocalDataLoader already validates, but we do explicit check here
            self.loader._validate_dataframe(data)

            # Delegate to LocalDataLoader for file I/O
            file_path = self.loader.save(
                df=data,
                symbol=symbol,
                timeframe=timeframe,
            )

            logger.info(f"Successfully saved data to cache: {file_path}")

        except Exception as e:
            logger.error(f"Error saving to cache: {e}")
            raise

    def get_data_range(
        self,
        symbol: str,
        timeframe: str,
    ) -> dict[str, Any]:
        """
        Get date range and metadata for cached data.

        Fast operation that doesn't load entire file.

        Args:
            symbol: Trading symbol (e.g., 'AAPL', 'EURUSD')
            timeframe: Timeframe (e.g., '1d', '1h', '5m')

        Returns:
            Dictionary with:
            - symbol: str
            - timeframe: str
            - start_date: datetime
            - end_date: datetime
            - rows: int (requires loading file)
            - exists: bool

        Raises:
            DataNotFoundError: If cache file doesn't exist
        """
        logger.info(f"Getting data range for {symbol} {timeframe}")

        try:
            # Get date range from LocalDataLoader (fast, doesn't load full file)
            date_range = self.loader.get_data_date_range(symbol, timeframe)

            if date_range is None:
                raise DataNotFoundError(
                    message=f"Data not found for {symbol} ({timeframe})",
                    error_code="DATA-FileNotFound",
                    details={"symbol": symbol, "timeframe": timeframe},
                )

            start_date, end_date = date_range

            # For row count, we need to load the file
            # This is acceptable as get_data_range is not called frequently
            df = self.loader.load(symbol, timeframe)

            result = {
                "symbol": symbol,
                "timeframe": timeframe,
                "start_date": start_date,
                "end_date": end_date,
                "rows": len(df),
                "exists": True,
            }

            logger.info(
                f"Data range for {symbol} {timeframe}: "
                f"{start_date.date()} to {end_date.date()} ({len(df)} rows)"
            )
            return result

        except DataNotFoundError:
            # Re-raise as-is
            raise
        except Exception as e:
            logger.error(f"Error getting data range: {e}")
            raise

    def get_available_symbols(self) -> list[str]:
        """
        Get list of unique symbols with cached data.

        Returns:
            List of symbol strings
        """
        logger.debug("Getting available symbols")

        try:
            # Get all available data files from LocalDataLoader
            files = self.loader.get_available_data_files()

            # Extract unique symbols (first element of each tuple)
            symbols = sorted({symbol for symbol, _ in files})

            logger.info(f"Found {len(symbols)} unique symbols in cache")
            return symbols

        except Exception as e:
            logger.error(f"Error getting available symbols: {e}")
            return []

    def delete_from_cache(self, symbol: str, timeframe: str) -> bool:
        """
        Delete cached data for symbol and timeframe.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe

        Returns:
            True if file was deleted, False if it didn't exist
        """
        logger.info(f"Deleting cached data: {symbol} {timeframe}")

        try:
            file_path = self.loader._build_file_path(symbol, timeframe)

            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted cache file: {file_path}")
                return True
            else:
                logger.warning(f"Cache file not found, nothing to delete: {file_path}")
                return False

        except Exception as e:
            logger.error(f"Error deleting from cache: {e}")
            return False

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get statistics about the cache.

        Returns:
            Dictionary with cache statistics:
            - total_files: int
            - unique_symbols: int
            - data_directory: str
        """
        logger.debug("Getting cache statistics")

        try:
            files = self.loader.get_available_data_files()
            symbols = {symbol for symbol, _ in files}

            stats = {
                "total_files": len(files),
                "unique_symbols": len(symbols),
                "data_directory": str(self.data_dir),
            }

            logger.info(f"Cache stats: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {
                "total_files": 0,
                "unique_symbols": 0,
                "data_directory": str(self.data_dir),
            }

    def validate_data(
        self,
        data: pd.DataFrame,
        symbol: str,
        timeframe: str,
        validation_type: str = "local",
    ) -> tuple[pd.DataFrame, Any]:
        """
        Validate cached data quality.

        Performs comprehensive data quality checks including:
        - Basic structure validation
        - Duplicate detection and removal
        - OHLC relationship validation
        - Missing value detection and handling
        - Timestamp gap detection
        - Price outlier detection
        - Volume pattern validation

        Args:
            data: DataFrame with OHLCV data to validate
            symbol: Trading symbol
            timeframe: Timeframe of the data
            validation_type: Type of validation ("local", "ib", "general")
                           Default is "local" for cached data

        Returns:
            Tuple of (corrected_dataframe, quality_report)
            - corrected_dataframe: DataFrame with auto-corrections applied
            - quality_report: DataQualityReport with validation results

        Example:
            >>> repo = DataRepository()
            >>> df = repo.load_from_cache("AAPL", "1d")
            >>> corrected_df, report = repo.validate_data(df, "AAPL", "1d")
            >>> if not report.is_healthy():
            ...     print(f"Found {len(report.issues)} issues")
        """
        logger.info(f"Validating data for {symbol} {timeframe} ({len(data)} rows)")

        try:
            # Delegate to DataQualityValidator
            corrected_df, quality_report = self.validator.validate_data(
                df=data,
                symbol=symbol,
                timeframe=timeframe,
                validation_type=validation_type,
            )

            # Log summary
            summary = quality_report.get_summary()
            logger.info(
                f"Validation complete: {summary['total_issues']} issues found, "
                f"{summary['corrections_made']} auto-corrected"
            )

            if not quality_report.is_healthy():
                logger.warning(
                    f"Data quality issues detected for {symbol} {timeframe}. "
                    f"Review the quality report for details."
                )

            return corrected_df, quality_report

        except Exception as e:
            logger.error(f"Error validating data: {e}")
            raise

    def get_available_data_files(self) -> list[tuple[str, str]]:
        """
        Get list of available data files.

        Delegates to LocalDataLoader to discover cached data files.

        Returns:
            List of (symbol, timeframe) tuples for cached data

        Example:
            >>> repository = DataRepository()
            >>> files = repository.get_available_data_files()
            >>> files
            [('AAPL', '1d'), ('GOOGL', '1h'), ('MSFT', '5m')]
        """
        return self.loader.get_available_data_files()
