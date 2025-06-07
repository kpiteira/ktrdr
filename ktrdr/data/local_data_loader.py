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
    with_context,
)
from ktrdr.utils.timezone_utils import TimestampManager

from ktrdr.config import ConfigLoader, InputValidator, sanitize_parameter
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
    with_partial_results,
    ValidationError,
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
    REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]

    # Standard datetime format for file names
    DATE_FORMAT = "%Y%m%d"

    def __init__(self, data_dir: Optional[str] = None, default_format: str = "csv"):
        """
        Initialize the LocalDataLoader.

        Args:
            data_dir: Path to the directory containing data files.
                      If None, will use the path from configuration.
            default_format: Default file format (default: 'csv')

        Raises:
            DataError: If the data directory path exists but is not a directory
            ValidationError: If the default_format is invalid
        """
        # Validate default_format using the new validation utilities
        try:
            default_format = InputValidator.validate_string(
                default_format, allowed_values={"csv"}
            )
        except ValidationError as e:
            raise DataError(
                message=f"Invalid file format: {e.message}",
                error_code="DATA-InvalidFormat",
                details={"format": default_format},
            )

        if data_dir is None:
            # Load from configuration
            try:
                config_loader = ConfigLoader()
                config = config_loader.load("config/settings.yaml")
                data_dir = config.data.directory
                logger.info(f"Using data directory from config: {data_dir}")
            except Exception as e:
                logger.warning(f"Failed to load configuration: {e}")
                data_dir = "./data"  # Fallback to default
                logger.info(f"Using fallback data directory: {data_dir}")

        # Sanitize data_dir path
        data_dir = sanitize_parameter("data_dir", data_dir)
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
                    details={"path": str(self.data_dir)},
                )
        except PermissionError as e:
            log_error(e, logger=logger)
            raise DataError(
                message=f"Permission denied when creating data directory: {self.data_dir}",
                error_code="DATA-PermissionDenied",
                details={"path": str(self.data_dir)},
            ) from e

    def _build_file_path(
        self, symbol: str, timeframe: str, file_format: Optional[str] = None
    ) -> Path:
        """
        Build the file path for a given symbol and timeframe.

        Args:
            symbol: The trading symbol (e.g., 'EURUSD', 'AAPL')
            timeframe: The timeframe of the data (e.g., '1h', '1d')
            file_format: The file format (default: None, uses self.default_format)

        Returns:
            Path object representing the file path

        Raises:
            ValidationError: If inputs fail validation
        """
        # Validate inputs using the new validation utilities
        try:
            symbol = InputValidator.validate_string(
                symbol, min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_\-\.]+$"
            )

            timeframe = InputValidator.validate_string(
                timeframe,
                min_length=1,
                max_length=10,
                pattern=r"^[0-9]+[mhdwM]$|^[1-9][0-9]*\s+[a-zA-Z]+$",
            )

            if file_format is not None:
                file_format = InputValidator.validate_string(
                    file_format, allowed_values={"csv"}
                )
        except ValidationError as e:
            logger.error(f"Validation error in _build_file_path: {e}")
            raise

        format_to_use = file_format if file_format is not None else self.default_format
        filename = f"{symbol}_{timeframe}.{format_to_use}"
        return self.data_dir / filename

    @retry_with_backoff(
        retryable_exceptions=[IOError, OSError], config=None, logger=logger
    )
    @fallback(strategy=FallbackStrategy.LAST_KNOWN_GOOD, logger=logger)
    @log_data_operation(operation="load", data_type="price data", logger=logger)
    @log_entry_exit(logger=logger, log_args=True)
    def load(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        file_format: Optional[str] = None,
    ) -> pd.DataFrame:
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
            ValidationError: If input validation fails
        """
        # Validate date parameters if provided
        try:
            # Convert string dates to datetime objects
            start_dt = None
            end_dt = None

            if start_date is not None:
                start_dt = (
                    pd.to_datetime(start_date)
                    if isinstance(start_date, str)
                    else start_date
                )

            if end_date is not None:
                end_dt = (
                    pd.to_datetime(end_date) if isinstance(end_date, str) else end_date
                )

            # Ensure end_date is after start_date if both are provided
            if start_dt is not None and end_dt is not None:
                if end_dt < start_dt:
                    raise ValidationError("End date must be after start date")

            # Update start_date and end_date with the datetime objects for later use
            start_date = start_dt
            end_date = end_dt

        except ValidationError as e:
            logger.error(f"Date validation error: {e}")
            raise DataValidationError(
                message=f"Invalid date parameter: {e}",
                error_code="DATA-InvalidDateRange",
                details={
                    "start_date": str(start_date) if start_date else None,
                    "end_date": str(end_date) if end_date else None,
                },
            )
        except ValueError as e:
            # Handle date parsing errors
            logger.error(f"Date parsing error: {e}")
            raise DataValidationError(
                message=f"Invalid date format: {e}",
                error_code="DATA-InvalidDateFormat",
                details={
                    "start_date": str(start_date) if start_date else None,
                    "end_date": str(end_date) if end_date else None,
                },
            )

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
                    "file_path": str(file_path),
                },
            )

        try:
            # First try the standard approach with index_col=0
            df = pd.read_csv(file_path, index_col=0, parse_dates=True)

            # If df is empty or doesn't have a DatetimeIndex, try alternate approach
            if df.empty or not isinstance(df.index, pd.DatetimeIndex):
                logger.warning(
                    f"Standard loading approach failed, trying alternate method"
                )

                # Try again with explicit date column
                df = pd.read_csv(file_path)

                # Check for date column with various possible names
                date_col = None
                for col in [
                    "date",
                    "Date",
                    "DATE",
                    "timestamp",
                    "Timestamp",
                    "time",
                    "Time",
                ]:
                    if col in df.columns:
                        date_col = col
                        break

                if date_col:
                    # Convert date column to datetime and set as index
                    df[date_col] = pd.to_datetime(df[date_col], errors="coerce", utc=True)
                    df.set_index(date_col, inplace=True)
                    logger.info(f"Successfully parsed date column: {date_col}")
                else:
                    logger.warning(f"No date column found, using default index")

            # Handle cases where the index still isn't a DatetimeIndex
            if not isinstance(df.index, pd.DatetimeIndex):
                logger.warning("Index is not a DatetimeIndex after parsing attempts")

                # Create a dummy index as a last resort
                df.index = pd.date_range(start="2023-01-01", periods=len(df), freq="D")
                logger.warning(f"Created dummy date index for {len(df)} rows")

            # Make sure column names are all lowercase for consistency
            df.columns = [col.lower() for col in df.columns]
            
            # Convert to UTC timezone using TimestampManager for consistent handling
            if isinstance(df.index, pd.DatetimeIndex):
                logger.debug(f"Converting CSV timestamps to UTC for {symbol}")
                df.index = TimestampManager.to_utc_series(df.index)

            # Validate the DataFrame structure (with more tolerance)
            try:
                self._validate_dataframe(df)
            except DataFormatError as e:
                # If validation fails due to missing columns but we have data,
                # try to create minimal required columns with default values
                if len(df) > 0:
                    for col in self.REQUIRED_COLUMNS:
                        if col not in df.columns:
                            logger.warning(f"Creating missing column: {col}")
                            if col in ["open", "high", "low", "close"]:
                                # For price columns, use a default value if any price column exists
                                price_cols = [
                                    c
                                    for c in df.columns
                                    if c in ["open", "high", "low", "close"]
                                ]
                                if price_cols:
                                    df[col] = df[price_cols[0]]
                                else:
                                    df[col] = 100.0  # Default value
                            elif col == "volume":
                                df[col] = 0  # Default volume

                    # Validate again after adding missing columns
                    self._validate_dataframe(df)
                else:
                    # If df is truly empty, re-raise the original error
                    raise

            # Apply date filters if provided
            df = self._apply_date_filters(df, start_date, end_date)

            logger.debug(
                f"Successfully loaded {len(df)} rows of data for {symbol} ({timeframe})"
            )
            return df

        except pd.errors.EmptyDataError:
            logger.error(f"Empty data file: {file_path}")
            raise DataFormatError(
                message=f"Empty data file: {file_path}",
                error_code="DATA-EmptyFile",
                details={"file_path": str(file_path)},
            )
        except pd.errors.ParserError as e:
            log_error(e, logger=logger, extra={"file_path": str(file_path)})
            raise DataFormatError(
                message=f"Invalid CSV format in file: {file_path}",
                error_code="DATA-InvalidFormat",
                details={"file_path": str(file_path), "parser_error": str(e)},
            )
        except Exception as e:
            log_error(e, logger=logger, extra={"file_path": str(file_path)})
            raise DataError(
                message=f"Error reading data file {file_path}: {str(e)}",
                error_code="DATA-ReadError",
                details={"file_path": str(file_path), "error": str(e)},
            )

    @retry_with_backoff(
        retryable_exceptions=[IOError, OSError], config=None, logger=logger
    )
    @log_data_operation(operation="save", data_type="price data", logger=logger)
    @log_entry_exit(logger=logger, log_args=True)
    def save(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        file_format: Optional[str] = None,
    ) -> Path:
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
                details={"file_path": str(file_path)},
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
                    "rows": len(df) if isinstance(df, pd.DataFrame) else "unknown",
                },
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
        missing_columns = [
            col for col in self.REQUIRED_COLUMNS if col not in df.columns
        ]
        if missing_columns:
            logger.error(
                f"DataFrame missing required columns: {', '.join(missing_columns)}"
            )
            raise DataFormatError(
                message=f"DataFrame missing required columns: {', '.join(missing_columns)}",
                error_code="DATA-MissingColumns",
                details={
                    "missing_columns": missing_columns,
                    "required_columns": self.REQUIRED_COLUMNS,
                },
            )

        # Check that index is datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            logger.error("DataFrame index must be a DatetimeIndex")
            raise DataFormatError(
                message="DataFrame index must be a DatetimeIndex",
                error_code="DATA-InvalidIndex",
                details={"index_type": str(type(df.index))},
            )

        # Check that the DataFrame has data
        if df.empty:
            logger.error("DataFrame is empty")
            raise DataFormatError(
                message="DataFrame is empty",
                error_code="DATA-EmptyDataFrame",
                details={},
            )

    def _apply_date_filters(
        self,
        df: pd.DataFrame,
        start_date: Optional[Union[str, datetime]],
        end_date: Optional[Union[str, datetime]],
    ) -> pd.DataFrame:
        """
        Filter DataFrame by start and end dates with timezone compatibility.

        Args:
            df: DataFrame to filter
            start_date: Optional start date (may be timezone-aware)
            end_date: Optional end date (may be timezone-aware)

        Returns:
            Filtered DataFrame
        """
        if start_date is not None:
            if isinstance(start_date, str):
                start_date = pd.to_datetime(start_date)

            # Convert start_date to UTC for consistent comparison
            start_date_utc = TimestampManager.to_utc(start_date)
            if start_date_utc is not None:
                # Both df.index and start_date are now UTC timezone-aware
                df = df[df.index >= start_date_utc]

        if end_date is not None:
            if isinstance(end_date, str):
                end_date = pd.to_datetime(end_date)

            # Convert end_date to UTC for consistent comparison  
            end_date_utc = TimestampManager.to_utc(end_date)
            if end_date_utc is not None:
                # Both df.index and end_date are now UTC timezone-aware
                df = df[df.index <= end_date_utc]

        return df

    @fallback(strategy=FallbackStrategy.DEFAULT_VALUE, default_value=[], logger=logger)
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

            logger.debug(f"Searching for data files in {self.data_dir} (format: symbol_timeframe.csv)")

            for file_path in self.data_dir.glob(f"*.{self.default_format}"):
                filename = file_path.name
                # Parse the filename to extract symbol and timeframe
                parts = filename.rsplit(".", 1)[0].split("_")
                if len(parts) >= 2:
                    symbol = parts[0]
                    timeframe = parts[1]
                    result.append((symbol, timeframe))

            logger.info(f"Found {len(result)} data files (will be aggregated by symbol for unique symbols)")
            return result

        except PermissionError as e:
            log_error(e, logger=logger)
            raise DataError(
                message=f"Permission denied when accessing data directory: {self.data_dir}",
                error_code="DATA-PermissionDenied",
                details={"path": str(self.data_dir)},
            ) from e
        except Exception as e:
            log_error(e, logger=logger)
            raise DataError(
                message=f"Error getting available data files: {str(e)}",
                error_code="DATA-ListError",
                details={"path": str(self.data_dir)},
            ) from e

    @retry_with_backoff(
        retryable_exceptions=[IOError, OSError], config=None, logger=logger
    )
    @log_performance(threshold_ms=100, logger=logger)
    def get_data_date_range(
        self, symbol: str, timeframe: str, file_format: Optional[str] = None
    ) -> Optional[Tuple[datetime, datetime]]:
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
            # More efficient approach that doesn't scan the entire file
            # Read just the first row to get the start date
            with open(file_path, "r") as f:
                # Read the header line
                header = f.readline().strip()
                # Read the first data line
                first_line = f.readline().strip()

            # For the last line, use a more efficient approach
            last_line = ""
            with open(file_path, "rb") as f:
                # Seek to the end of the file
                try:
                    f.seek(-2, os.SEEK_END)  # Go to the 2nd last byte
                    # Keep seeking backwards until we find a newline
                    while f.read(1) != b"\n":
                        f.seek(-2, os.SEEK_CUR)
                except OSError:
                    # In case the file is too small, just seek to the beginning
                    f.seek(0)

                # Now read the last line
                last_line = f.readline().decode().strip()

            # If we couldn't get the last line, fall back to reading the whole file
            if not last_line:
                logger.debug(
                    "Couldn't read last line efficiently, falling back to pandas"
                )
                df = pd.read_csv(file_path, index_col=0, parse_dates=True)
                return df.index[0], df.index[-1]

            # Parse the CSV lines manually
            # First determine the column index of the date
            headers = header.split(",")
            date_col_idx = 0  # Default to first column

            # Get the values from the first and last lines
            first_values = first_line.split(",")
            last_values = last_line.split(",")

            # Parse the dates
            try:
                start_date = pd.to_datetime(first_values[date_col_idx])
                end_date = pd.to_datetime(last_values[date_col_idx])

                logger.info(
                    f"Data for {symbol} ({timeframe}) covers period from {start_date.date()} to {end_date.date()}"
                )
                return start_date, end_date
            except (ValueError, IndexError) as e:
                logger.warning(
                    f"Error parsing dates from CSV: {e}, falling back to pandas"
                )

                # Fall back to pandas if we can't parse the dates
                df = pd.read_csv(file_path, index_col=0, parse_dates=True, nrows=1)
                first_row = df

                # For the last row, just read the entire file but only the last row
                last_row = pd.read_csv(
                    file_path,
                    index_col=0,
                    parse_dates=True,
                    skiprows=lambda x: x > 0
                    and x < max(0, sum(1 for _ in open(file_path)) - 1),
                )

                start_date = first_row.index[0]
                end_date = last_row.index[-1]

                logger.info(
                    f"Data for {symbol} ({timeframe}) covers period from {start_date.date()} to {end_date.date()}"
                )
                return start_date, end_date

        except pd.errors.EmptyDataError:
            logger.error(f"Empty data file: {file_path}")
            raise DataFormatError(
                message=f"Empty data file: {file_path}",
                error_code="DATA-EmptyFile",
                details={"file_path": str(file_path)},
            )
        except pd.errors.ParserError as e:
            log_error(e, logger=logger, extra={"file_path": str(file_path)})
            raise DataFormatError(
                message=f"Invalid CSV format in file: {file_path}",
                error_code="DATA-InvalidFormat",
                details={"file_path": str(file_path), "parser_error": str(e)},
            )
        except Exception as e:
            log_error(e, logger=logger, extra={"file_path": str(file_path)})
            raise DataFormatError(
                message=f"Error extracting date range from {file_path}: {str(e)}",
                error_code="DATA-DateRangeError",
                details={"file_path": str(file_path), "error": str(e)},
            )
