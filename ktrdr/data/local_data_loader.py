"""
LocalDataLoader for loading and saving OHLCV data from/to CSV files.

This module provides functionality to load and save price data from CSV files
with a configurable data directory.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd

# Import the new logging system
from ktrdr import (
    get_logger, 
    log_entry_exit, 
    log_performance, 
    log_data_operation, 
    log_error,
    with_context
)

from ktrdr.config import ConfigLoader
from ktrdr.errors import (
    DataError,
    DataFormatError,
    DataNotFoundError,
    DataCorruptionError,
    DataValidationError,
    ErrorHandler,
    retry_with_backoff,
    fallback,
    FallbackStrategy,
    with_partial_results
)

# Get module logger
logger = get_logger(__name__)


class LocalDataLoader:
    """
    Handles loading and saving OHLCV data from/to CSV files.
    
    This class provides functionality for:
    - Loading price data from CSV files with configurable parameters
    - Saving price data to CSV files with standard naming conventions
    - Handling errors for corrupt or missing files
    
    Attributes:
        data_dir: Path to the directory containing data files
        default_format: Default file format (csv)
    """
    
    # Required columns for OHLCV data
    REQUIRED_COLUMNS = ['open', 'high', 'low', 'close', 'volume']
    
    # Standard datetime format for file names
    DATE_FORMAT = "%Y%m%d"
    
    def __init__(self, data_dir: Optional[str] = None, default_format: str = 'csv'):
        """
        Initialize the LocalDataLoader.
        
        Args:
            data_dir: Path to the directory containing data files.
                      If None, will use the path from configuration.
            default_format: Default file format (default: 'csv')
                
        Raises:
            DataError: If the data directory path exists but is not a directory
        """
        if data_dir is None:
            # Load from configuration
            try:
                config_loader = ConfigLoader()
                config = config_loader.load('config/settings.yaml')
                data_dir = config.data.directory
                logger.info(f"Using data directory from config: {data_dir}")
            except Exception as e:
                logger.warning(f"Failed to load configuration: {e}")
                data_dir = "./data"  # Fallback to default
                logger.info(f"Using fallback data directory: {data_dir}")
        
        self.data_dir = Path(data_dir)
        self.default_format = default_format
        
        # Create data directory if it doesn't exist
        try:
            if not self.data_dir.exists():
                logger.info(f"Creating data directory: {self.data_dir}")
                self.data_dir.mkdir(parents=True)
                logger.debug(f"Data directory created successfully")
            elif not self.data_dir.is_dir():
                raise DataError(
                    message=f"Data path exists but is not a directory: {self.data_dir}",
                    error_code="DATA-InvalidPath",
                    details={"path": str(self.data_dir)}
                )
        except PermissionError as e:
            log_error(e, logger=logger)
            raise DataError(
                message=f"Permission denied when creating data directory: {self.data_dir}",
                error_code="DATA-PermissionDenied",
                details={"path": str(self.data_dir)}
            ) from e
    
    def _build_file_path(self, 
                         symbol: str, 
                         timeframe: str, 
                         file_format: Optional[str] = None) -> Path:
        """
        Build the file path for a given symbol and timeframe.
        
        Args:
            symbol: The trading symbol (e.g., 'EURUSD', 'AAPL')
            timeframe: The timeframe of the data (e.g., '1h', '1d')
            file_format: The file format (default: None, uses self.default_format)
            
        Returns:
            Path object representing the file path
        """
        if file_format is None:
            file_format = self.default_format
            
        # Create a standardized file name: symbol_timeframe.format
        file_name = f"{symbol}_{timeframe}.{file_format}"
        return self.data_dir / file_name
    
    @retry_with_backoff(
        retryable_exceptions=[IOError, OSError],
        config=None,
        logger=logger
    )
    @fallback(
        strategy=FallbackStrategy.LAST_KNOWN_GOOD,
        logger=logger
    )
    @log_data_operation(operation="load", data_type="price data", logger=logger)
    @log_entry_exit(logger=logger, log_args=True)
    def load(self, 
             symbol: str, 
             timeframe: str, 
             start_date: Optional[Union[str, datetime]] = None,
             end_date: Optional[Union[str, datetime]] = None,
             file_format: Optional[str] = None) -> pd.DataFrame:
        """
        Load OHLCV data for the given symbol and timeframe.
        
        Args:
            symbol: The trading symbol (e.g., 'EURUSD', 'AAPL')
            timeframe: The timeframe of the data (e.g., '1h', '1d')
            start_date: Optional start date for filtering data
            end_date: Optional end date for filtering data
            file_format: Optional file format override (default: uses default_format)
            
        Returns:
            DataFrame containing OHLCV data with datetime index
            
        Raises:
            DataNotFoundError: If the data file is not found
            DataFormatError: If the data format is invalid
            DataError: For other data-related errors
        """
        file_path = self._build_file_path(symbol, timeframe, file_format)
        logger.info(f"Loading data for {symbol} ({timeframe}) from {file_path}")
        
        if not file_path.exists():
            logger.error(f"Data file not found: {file_path}")
            raise DataNotFoundError(
                message=f"Data file not found: {file_path}",
                error_code="DATA-FileNotFound",
                details={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "file_path": str(file_path)
                }
            )
        
        try:
            # Read the CSV file into a DataFrame
            df = pd.read_csv(file_path, index_col=0, parse_dates=True)
            
            # Validate the DataFrame structure
            self._validate_dataframe(df)
            
            # Apply date filters if provided
            df = self._apply_date_filters(df, start_date, end_date)
            
            logger.debug(f"Successfully loaded {len(df)} rows of data for {symbol} ({timeframe})")
            return df
            
        except pd.errors.EmptyDataError:
            logger.error(f"Empty data file: {file_path}")
            raise DataFormatError(
                message=f"Empty data file: {file_path}",
                error_code="DATA-EmptyFile",
                details={"file_path": str(file_path)}
            )
        except pd.errors.ParserError as e:
            log_error(e, logger=logger, extra={"file_path": str(file_path)})
            raise DataFormatError(
                message=f"Invalid CSV format in file: {file_path}",
                error_code="DATA-InvalidFormat",
                details={"file_path": str(file_path), "parser_error": str(e)}
            )
        except Exception as e:
            log_error(e, logger=logger, extra={"file_path": str(file_path)})
            raise DataError(
                message=f"Error reading data file {file_path}: {str(e)}",
                error_code="DATA-ReadError",
                details={"file_path": str(file_path), "error": str(e)}
            )
    
    @retry_with_backoff(
        retryable_exceptions=[IOError, OSError],
        config=None,
        logger=logger
    )
    @log_data_operation(operation="save", data_type="price data", logger=logger)
    @log_entry_exit(logger=logger, log_args=True)
    def save(self, 
             df: pd.DataFrame, 
             symbol: str, 
             timeframe: str,
             file_format: Optional[str] = None) -> Path:
        """
        Save OHLCV data to a CSV file.
        
        Args:
            df: DataFrame containing OHLCV data with datetime index
            symbol: The trading symbol (e.g., 'EURUSD', 'AAPL')
            timeframe: The timeframe of the data (e.g., '1h', '1d')
            file_format: Optional file format override (default: uses default_format)
            
        Returns:
            Path object representing the saved file path
            
        Raises:
            DataFormatError: If the DataFrame format is invalid
            DataError: For other data-related errors
        """
        # Validate the DataFrame before saving
        try:
            self._validate_dataframe(df)
        except DataFormatError as e:
            log_error(e, logger=logger)
            raise
        
        file_path = self._build_file_path(symbol, timeframe, file_format)
        logger.info(f"Saving data for {symbol} ({timeframe}) to {file_path}")
        
        try:
            # Create directory if it doesn't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save DataFrame to CSV
            df.to_csv(file_path)
            logger.debug(f"Successfully saved {len(df)} rows of data to {file_path}")
            
            return file_path
            
        except PermissionError as e:
            log_error(e, logger=logger, extra={"file_path": str(file_path)})
            raise DataError(
                message=f"Permission denied when saving data to {file_path}",
                error_code="DATA-SavePermissionDenied",
                details={"file_path": str(file_path)}
            ) from e
        except Exception as e:
            log_error(e, logger=logger, extra={"file_path": str(file_path)})
            raise DataError(
                message=f"Error saving data to {file_path}: {str(e)}",
                error_code="DATA-SaveError",
                details={
                    "file_path": str(file_path),
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "rows": len(df) if isinstance(df, pd.DataFrame) else "unknown"
                }
            ) from e
    
    @with_context(operation_name="validate_dataframe")
    def _validate_dataframe(self, df: pd.DataFrame) -> None:
        """
        Validate that the DataFrame has the required OHLCV structure.
        
        Args:
            df: DataFrame to validate
            
        Raises:
            DataFormatError: If the DataFrame doesn't have the required columns or structure
        """
        # Check for required columns
        missing_columns = [col for col in self.REQUIRED_COLUMNS if col not in df.columns]
        if missing_columns:
            logger.error(f"DataFrame missing required columns: {', '.join(missing_columns)}")
            raise DataFormatError(
                message=f"DataFrame missing required columns: {', '.join(missing_columns)}",
                error_code="DATA-MissingColumns",
                details={"missing_columns": missing_columns, "required_columns": self.REQUIRED_COLUMNS}
            )
        
        # Check that index is datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            logger.error("DataFrame index must be a DatetimeIndex")
            raise DataFormatError(
                message="DataFrame index must be a DatetimeIndex",
                error_code="DATA-InvalidIndex",
                details={"index_type": str(type(df.index))}
            )
        
        # Check that the DataFrame has data
        if df.empty:
            logger.error("DataFrame is empty")
            raise DataFormatError(
                message="DataFrame is empty",
                error_code="DATA-EmptyDataFrame",
                details={}
            )
    
    def _apply_date_filters(self, 
                           df: pd.DataFrame, 
                           start_date: Optional[Union[str, datetime]], 
                           end_date: Optional[Union[str, datetime]]) -> pd.DataFrame:
        """
        Filter DataFrame by start and end dates.
        
        Args:
            df: DataFrame to filter
            start_date: Optional start date
            end_date: Optional end date
            
        Returns:
            Filtered DataFrame
        """
        if start_date is not None:
            if isinstance(start_date, str):
                start_date = pd.to_datetime(start_date)
            df = df[df.index >= start_date]
            
        if end_date is not None:
            if isinstance(end_date, str):
                end_date = pd.to_datetime(end_date)
            df = df[df.index <= end_date]
            
        return df
    
    @fallback(
        strategy=FallbackStrategy.DEFAULT_VALUE,
        default_value=[],
        logger=logger
    )
    @log_entry_exit(logger=logger)
    def get_available_data_files(self) -> List[Tuple[str, str]]:
        """
        Get a list of available data files in the data directory.
        
        Returns:
            List of tuples containing (symbol, timeframe) for available data files
        """
        result = []
        
        try:
            if not self.data_dir.exists():
                logger.warning(f"Data directory does not exist: {self.data_dir}")
                return result
                
            logger.debug(f"Searching for data files in {self.data_dir}")
            
            for file_path in self.data_dir.glob(f"*.{self.default_format}"):
                filename = file_path.name
                # Parse the filename to extract symbol and timeframe
                parts = filename.rsplit('.', 1)[0].split('_')
                if len(parts) >= 2:
                    symbol = parts[0]
                    timeframe = parts[1]
                    result.append((symbol, timeframe))
            
            logger.info(f"Found {len(result)} available data files")
            return result
            
        except PermissionError as e:
            log_error(e, logger=logger)
            raise DataError(
                message=f"Permission denied when accessing data directory: {self.data_dir}",
                error_code="DATA-PermissionDenied",
                details={"path": str(self.data_dir)}
            ) from e
        except Exception as e:
            log_error(e, logger=logger)
            raise DataError(
                message=f"Error getting available data files: {str(e)}",
                error_code="DATA-ListError",
                details={"path": str(self.data_dir)}
            ) from e
    
    @retry_with_backoff(
        retryable_exceptions=[IOError, OSError],
        config=None,
        logger=logger
    )
    @log_performance(threshold_ms=100, logger=logger)
    def get_data_date_range(self, 
                           symbol: str, 
                           timeframe: str,
                           file_format: Optional[str] = None) -> Optional[Tuple[datetime, datetime]]:
        """
        Get the date range for a specific data file without loading the entire file.
        
        Args:
            symbol: The trading symbol (e.g., 'EURUSD', 'AAPL')
            timeframe: The timeframe of the data (e.g., '1h', '1d')
            file_format: Optional file format override (default: uses default_format)
            
        Returns:
            Tuple of (start_date, end_date) or None if file doesn't exist
            
        Raises:
            DataFormatError: If the file exists but has invalid format
        """
        file_path = self._build_file_path(symbol, timeframe, file_format)
        logger.debug(f"Checking date range for {symbol} ({timeframe}) in {file_path}")
        
        if not file_path.exists():
            logger.debug(f"File does not exist: {file_path}")
            return None
            
        try:
            # Read just the first and last rows to get date range
            first_row = pd.read_csv(file_path, nrows=1, index_col=0, parse_dates=True)
            
            # Use pandas options to read from the end of the file
            with pd.option_context('display.max_rows', None):
                # Determine the file size and number of lines
                file_size = os.path.getsize(file_path)
                
                # For large files, only read the last chunk
                if file_size > 10_000:  # If file is larger than 10KB
                    logger.debug(f"Large file detected ({file_size} bytes), reading only tail portion")
                    last_rows = pd.read_csv(file_path, index_col=0, parse_dates=True, skipfooter=0, 
                                           nrows=5, skiprows=lambda x: 0 < x < max(0, sum(1 for _ in open(file_path)) - 5))
                else:
                    # For small files, just load everything
                    logger.debug(f"Small file detected ({file_size} bytes), loading entire file")
                    df = pd.read_csv(file_path, index_col=0, parse_dates=True)
                    first_row = df.iloc[[0]]
                    last_rows = df.iloc[[-1]]
            
            start_date = first_row.index[0]
            end_date = last_rows.index[-1]
            
            logger.info(f"Data for {symbol} ({timeframe}) covers period from {start_date.date()} to {end_date.date()}")
            return start_date, end_date
            
        except pd.errors.EmptyDataError:
            logger.error(f"Empty data file: {file_path}")
            raise DataFormatError(
                message=f"Empty data file: {file_path}",
                error_code="DATA-EmptyFile",
                details={"file_path": str(file_path)}
            )
        except pd.errors.ParserError as e:
            log_error(e, logger=logger, extra={"file_path": str(file_path)})
            raise DataFormatError(
                message=f"Invalid CSV format in file: {file_path}",
                error_code="DATA-InvalidFormat",
                details={"file_path": str(file_path), "parser_error": str(e)}
            )
        except Exception as e:
            log_error(e, logger=logger, extra={"file_path": str(file_path)})
            raise DataFormatError(
                message=f"Error extracting date range from {file_path}: {str(e)}",
                error_code="DATA-DateRangeError",
                details={"file_path": str(file_path), "error": str(e)}
            )
