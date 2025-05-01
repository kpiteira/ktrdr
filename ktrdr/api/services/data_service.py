"""
Data service for the KTRDR API.

This module provides services for accessing OHLCV data and related functionality,
bridging the API endpoints with the core KTRDR data modules.
"""
import logging
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
import pandas as pd

from ktrdr import get_logger, log_entry_exit, log_performance, log_data_operation
from ktrdr.data import DataManager
from ktrdr.errors import (
    DataError,
    DataNotFoundError,
    retry_with_backoff,
    RetryConfig
)

# Setup module-level logger
logger = get_logger(__name__)

class DataService:
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
        self.data_manager = DataManager(data_dir=data_dir)
        logger.info("DataService initialized")
        
    @log_entry_exit(logger=logger, log_args=True)
    @log_performance(threshold_ms=500, logger=logger)
    @retry_with_backoff(
        retryable_exceptions=[DataError],
        config=RetryConfig(
            max_retries=3,
            base_delay=1.0,
            backoff_factor=2.0
        ),
        logger=logger,
        is_retryable=lambda e: isinstance(e, DataError) and not isinstance(e, DataNotFoundError)
    )
    def load_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        include_metadata: bool = True
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
                repair=False
            )
            
            # Convert DataFrame to API response format
            result = self._convert_df_to_api_format(df, symbol, timeframe, include_metadata)
            
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
                details={"symbol": symbol, "timeframe": timeframe}
            ) from e
            
    def _convert_df_to_api_format(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        include_metadata: bool = True
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
                "metadata": {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "points": 0
                }
            }
        
        # Format the dates as ISO strings
        dates = df.index.strftime('%Y-%m-%dT%H:%M:%S').tolist()
        
        # Extract OHLCV data as nested list
        ohlcv = df[['open', 'high', 'low', 'close', 'volume']].values.tolist()
        
        # Create the result dictionary
        result = {
            "dates": dates,
            "ohlcv": ohlcv
        }
        
        # Add metadata if requested
        if include_metadata:
            result["metadata"] = {
                "symbol": symbol,
                "timeframe": timeframe,
                "start": df.index.min().isoformat(),
                "end": df.index.max().isoformat(),
                "points": len(df)
            }
            
        return result
    
    @log_entry_exit(logger=logger)
    def get_available_symbols(self) -> List[Dict[str, Any]]:
        """
        Get list of available symbols with metadata.
        
        Returns:
            List of symbol information dictionaries
        """
        # Get available data files from the data_loader
        available_files = self.data_manager.data_loader.get_available_data_files()
        
        # Extract unique symbols from the available files
        symbols = sorted(set(symbol for symbol, _ in available_files))
        
        result = []
        for symbol in symbols:
            # Get timeframes available for this symbol
            timeframes = self.get_available_timeframes_for_symbol(symbol)
            
            # Get a sample data file to extract more information
            sample_timeframe = timeframes[0] if timeframes else None
            
            if sample_timeframe:
                try:
                    # Try to get summary information
                    summary = self.data_manager.get_data_summary(symbol, sample_timeframe)
                    
                    symbol_info = {
                        "symbol": symbol,
                        "name": symbol,  # Using symbol as name for now
                        "type": "unknown",  # Could be enhanced with symbol type detection
                        "exchange": "unknown",  # Could be enhanced with exchange information
                        "available_timeframes": timeframes
                    }
                    result.append(symbol_info)
                except Exception as e:
                    logger.warning(f"Error getting information for {symbol}: {str(e)}")
                    # Still include the symbol with minimal information
                    result.append({
                        "symbol": symbol,
                        "name": symbol,
                        "type": "unknown",
                        "exchange": "unknown",
                        "available_timeframes": timeframes
                    })
            else:
                # Include symbol with empty timeframes
                result.append({
                    "symbol": symbol,
                    "name": symbol,
                    "type": "unknown",
                    "exchange": "unknown",
                    "available_timeframes": []
                })
        
        logger.info(f"Retrieved {len(result)} available symbols")
        return result
    
    @log_entry_exit(logger=logger)
    def get_available_timeframes_for_symbol(self, symbol: str) -> List[str]:
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
        timeframes = sorted(timeframe for file_symbol, timeframe in available_files if file_symbol == symbol)
        
        logger.debug(f"Found {len(timeframes)} available timeframes for {symbol}")
        return timeframes
    
    @log_entry_exit(logger=logger)
    def get_available_timeframes(self) -> List[Dict[str, str]]:
        """
        Get list of available timeframes with metadata.
        
        Returns:
            List of timeframe information dictionaries
        """
        # Define standard timeframes with metadata
        timeframes = [
            {
                "id": "1m",
                "name": "1 Minute",
                "description": "One-minute interval data"
            },
            {
                "id": "5m",
                "name": "5 Minutes",
                "description": "Five-minute interval data"
            },
            {
                "id": "15m",
                "name": "15 Minutes",
                "description": "Fifteen-minute interval data"
            },
            {
                "id": "30m",
                "name": "30 Minutes",
                "description": "Thirty-minute interval data"
            },
            {
                "id": "1h",
                "name": "1 Hour",
                "description": "One-hour interval data"
            },
            {
                "id": "2h",
                "name": "2 Hours",
                "description": "Two-hour interval data"
            },
            {
                "id": "4h",
                "name": "4 Hours",
                "description": "Four-hour interval data"
            },
            {
                "id": "1d",
                "name": "Daily",
                "description": "Daily interval data"
            },
            {
                "id": "1w",
                "name": "Weekly",
                "description": "Weekly interval data"
            },
            {
                "id": "1M",
                "name": "Monthly",
                "description": "Monthly interval data"
            }
        ]
        
        logger.info(f"Retrieved {len(timeframes)} available timeframes")
        return timeframes
    
    @log_entry_exit(logger=logger, log_args=True)
    def get_data_range(self, symbol: str, timeframe: str) -> Dict[str, Any]:
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
            # Get data summary from the data manager
            summary = self.data_manager.get_data_summary(symbol, timeframe)
            
            result = {
                "symbol": symbol,
                "timeframe": timeframe,
                "start_date": summary["start_date"],
                "end_date": summary["end_date"],
                "point_count": summary["rows"]
            }
            
            logger.info(f"Retrieved date range for {symbol} ({timeframe})")
            return result
            
        except DataNotFoundError:
            logger.error(f"Data not found for {symbol} ({timeframe})")
            raise
        except Exception as e:
            logger.error(f"Error getting date range for {symbol} ({timeframe}): {str(e)}")
            raise DataError(
                message=f"Failed to get date range for {symbol} ({timeframe}): {str(e)}",
                error_code="DATA-RangeError",
                details={"symbol": symbol, "timeframe": timeframe}
            ) from e