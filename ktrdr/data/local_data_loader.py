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

from ktrdr.config import ConfigLoader


class DataError(Exception):
    """Base exception for data-related errors."""
    pass


class DataFormatError(DataError):
    """Exception raised when data format is invalid."""
    pass


class DataNotFoundError(DataError):
    """Exception raised when data file is not found."""
    pass


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
        """
        if data_dir is None:
            # Load from configuration
            config_loader = ConfigLoader()
            config = config_loader.load('config/settings.yaml')
            data_dir = config.data.directory
        
        self.data_dir = Path(data_dir)
        self.default_format = default_format
        
        # Create data directory if it doesn't exist
        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True)
        elif not self.data_dir.is_dir():
            raise DataError(f"Data path exists but is not a directory: {self.data_dir}")
    
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
        
        if not file_path.exists():
            raise DataNotFoundError(f"Data file not found: {file_path}")
        
        try:
            # Read the CSV file into a DataFrame
            df = pd.read_csv(file_path, index_col=0, parse_dates=True)
            
            # Validate the DataFrame structure
            self._validate_dataframe(df)
            
            # Apply date filters if provided
            df = self._apply_date_filters(df, start_date, end_date)
            
            return df
            
        except pd.errors.EmptyDataError:
            raise DataFormatError(f"Empty data file: {file_path}")
        except pd.errors.ParserError:
            raise DataFormatError(f"Invalid CSV format in file: {file_path}")
        except Exception as e:
            raise DataError(f"Error reading data file {file_path}: {str(e)}")
    
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
        self._validate_dataframe(df)
        
        file_path = self._build_file_path(symbol, timeframe, file_format)
        
        try:
            # Create directory if it doesn't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save DataFrame to CSV
            df.to_csv(file_path)
            
            return file_path
            
        except Exception as e:
            raise DataError(f"Error saving data to {file_path}: {str(e)}")
    
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
            raise DataFormatError(
                f"DataFrame missing required columns: {', '.join(missing_columns)}"
            )
        
        # Check that index is datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            raise DataFormatError("DataFrame index must be a DatetimeIndex")
        
        # Check that the DataFrame has data
        if df.empty:
            raise DataFormatError("DataFrame is empty")
    
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
    
    def get_available_data_files(self) -> List[Tuple[str, str]]:
        """
        Get a list of available data files in the data directory.
        
        Returns:
            List of tuples containing (symbol, timeframe) for available data files
        """
        result = []
        
        if not self.data_dir.exists():
            return result
            
        for file_path in self.data_dir.glob(f"*.{self.default_format}"):
            filename = file_path.name
            # Parse the filename to extract symbol and timeframe
            parts = filename.rsplit('.', 1)[0].split('_')
            if len(parts) >= 2:
                symbol = parts[0]
                timeframe = parts[1]
                result.append((symbol, timeframe))
                
        return result
    
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
        
        if not file_path.exists():
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
                    last_rows = pd.read_csv(file_path, index_col=0, parse_dates=True, skipfooter=0, 
                                           nrows=5, skiprows=lambda x: 0 < x < max(0, sum(1 for _ in open(file_path)) - 5))
                else:
                    # For small files, just load everything
                    df = pd.read_csv(file_path, index_col=0, parse_dates=True)
                    first_row = df.iloc[[0]]
                    last_rows = df.iloc[[-1]]
            
            start_date = first_row.index[0]
            end_date = last_rows.index[-1]
            
            return start_date, end_date
            
        except Exception as e:
            raise DataFormatError(f"Error extracting date range from {file_path}: {str(e)}")
