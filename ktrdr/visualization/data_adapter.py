"""
Data transformation layer for the KTRDR visualization module.

This module provides functionality to transform pandas DataFrames into
format compatible with TradingView's lightweight-charts library.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Union, Any

import pandas as pd
import numpy as np

from ktrdr.errors import DataError
from ktrdr import get_logger

logger = get_logger(__name__)


class DataAdapter:
    """
    Transforms pandas DataFrames into the format required by lightweight-charts.
    
    This class provides static methods to convert different types of financial data
    (OHLC, line series, histogram) from pandas DataFrames to JSON format compatible
    with TradingView's lightweight-charts library.
    """
    
    @staticmethod
    def transform_ohlc(
        df: pd.DataFrame, 
        time_column: str = "date", 
        open_col: str = "open", 
        high_col: str = "high", 
        low_col: str = "low", 
        close_col: str = "close"
    ) -> List[Dict[str, Any]]:
        """
        Transform OHLC data from DataFrame to lightweight-charts format.
        
        Args:
            df: DataFrame containing OHLC data
            time_column: Name of the column containing the timestamp
            open_col: Name of the column containing the open price
            high_col: Name of the column containing the high price
            low_col: Name of the column containing the low price
            close_col: Name of the column containing the close price
            
        Returns:
            List of dictionaries with the format required by lightweight-charts
            
        Raises:
            DataError: If input DataFrame is missing required columns or has invalid data
        """
        try:
            logger.debug(f"Transforming OHLC data with shape {df.shape}")
            
            # Check if required columns exist
            required_cols = [time_column, open_col, high_col, low_col, close_col]
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                raise DataError(
                    message=f"Missing required columns for OHLC transformation: {missing_cols}",
                    error_code="DATA-MissingColumns",
                    details={"available_columns": list(df.columns), "required_columns": required_cols}
                )
            
            # Convert timestamps to UNIX timestamps (seconds for lightweight-charts v4.1.1)
            result = []
            for _, row in df.iterrows():
                # Handle timestamp conversion
                time_value = row[time_column]
                
                if isinstance(time_value, (pd.Timestamp, datetime)):
                    # Convert to Unix timestamp in seconds (not milliseconds)
                    unix_time = int(time_value.timestamp())
                elif isinstance(time_value, (int, float)):
                    # Assume it's already a UNIX timestamp in seconds
                    unix_time = int(time_value)
                elif isinstance(time_value, str):
                    # Try to parse as datetime
                    unix_time = int(pd.Timestamp(time_value).timestamp())
                else:
                    raise DataError(
                        message=f"Unsupported timestamp format: {type(time_value)}",
                        error_code="DATA-InvalidTimestamp",
                        details={"timestamp_type": str(type(time_value))}
                    )
                
                # Create OHLC entry
                entry = {
                    "time": unix_time,  # Unix timestamp in seconds
                    "open": float(row[open_col]),
                    "high": float(row[high_col]),
                    "low": float(row[low_col]),
                    "close": float(row[close_col])
                }
                result.append(entry)
            
            logger.debug(f"Transformed {len(result)} OHLC data points")
            return result
            
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error transforming OHLC data: {str(e)}")
            raise DataError(
                message="Failed to transform OHLC data",
                error_code="DATA-TransformationFailed",
                details={"original_error": str(e)}
            ) from e
    
    @staticmethod
    def transform_line(
        df: pd.DataFrame, 
        time_column: str = "date", 
        value_column: str = "value"
    ) -> List[Dict[str, Any]]:
        """
        Transform line series data from DataFrame to lightweight-charts format.
        
        Args:
            df: DataFrame containing line series data
            time_column: Name of the column containing the timestamp
            value_column: Name of the column containing the values
            
        Returns:
            List of dictionaries with the format required by lightweight-charts
            
        Raises:
            DataError: If input DataFrame is missing required columns or has invalid data
        """
        try:
            logger.debug(f"Transforming line data with shape {df.shape}")
            
            # Check if required columns exist
            required_cols = [time_column, value_column]
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                raise DataError(
                    message=f"Missing required columns for line transformation: {missing_cols}",
                    error_code="DATA-MissingColumns",
                    details={"available_columns": list(df.columns), "required_columns": required_cols}
                )
            
            # Convert timestamps to UNIX timestamps (seconds for lightweight-charts v4.1.1)
            result = []
            for _, row in df.iterrows():
                # Handle timestamp conversion
                time_value = row[time_column]
                if isinstance(time_value, (pd.Timestamp, datetime)):
                    # Convert to Unix timestamp in seconds (not milliseconds)
                    unix_time = int(time_value.timestamp())
                elif isinstance(time_value, (int, float)):
                    # Assume it's already a UNIX timestamp in seconds
                    unix_time = int(time_value)
                elif isinstance(time_value, str):
                    # Try to parse as datetime
                    unix_time = int(pd.Timestamp(time_value).timestamp())
                else:
                    raise DataError(
                        message=f"Unsupported timestamp format: {type(time_value)}",
                        error_code="DATA-InvalidTimestamp",
                        details={"timestamp_type": str(type(time_value))}
                    )
                
                # Create line series entry
                value = row[value_column]
                # Handle NaN values
                if pd.isna(value):
                    logger.debug(f"Skipping NaN value at timestamp {time_value}")
                    continue
                    
                entry = {
                    "time": unix_time,  # Unix timestamp in seconds
                    "value": float(value)
                }
                result.append(entry)
            
            logger.debug(f"Transformed {len(result)} line data points")
            return result
            
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error transforming line data: {str(e)}")
            raise DataError(
                message="Failed to transform line data",
                error_code="DATA-TransformationFailed",
                details={"original_error": str(e)}
            ) from e
    
    @staticmethod
    def transform_histogram(
        df: pd.DataFrame, 
        time_column: str = "date", 
        value_column: str = "value",
        color_column: Optional[str] = None,
        positive_color: str = "#26a69a",
        negative_color: str = "#ef5350",
        neutral_color: str = "#999999"
    ) -> List[Dict[str, Any]]:
        """
        Transform histogram data from DataFrame to lightweight-charts format.
        
        Args:
            df: DataFrame containing histogram data
            time_column: Name of the column containing the timestamp
            value_column: Name of the column containing the values
            color_column: Optional name of the column determining color
            positive_color: Color for positive values if no color_column specified
            negative_color: Color for negative values if no color_column specified
            neutral_color: Color for zero values if no color_column specified
            
        Returns:
            List of dictionaries with the format required by lightweight-charts
            
        Raises:
            DataError: If input DataFrame is missing required columns or has invalid data
        """
        try:
            logger.debug(f"Transforming histogram data with shape {df.shape}")
            
            # Check if required columns exist
            required_cols = [time_column, value_column]
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                raise DataError(
                    message=f"Missing required columns for histogram transformation: {missing_cols}",
                    error_code="DATA-MissingColumns",
                    details={"available_columns": list(df.columns), "required_columns": required_cols}
                )
            
            # If color_column is specified, make sure it exists
            if color_column and color_column not in df.columns:
                logger.warning(f"Color column '{color_column}' not found, using value-based coloring instead")
                color_column = None
            
            # Convert timestamps to UNIX timestamps (seconds for lightweight-charts v4.1.1)
            result = []
            for _, row in df.iterrows():
                # Handle timestamp conversion
                time_value = row[time_column]
                if isinstance(time_value, (pd.Timestamp, datetime)):
                    # Convert to Unix timestamp in seconds (not milliseconds)
                    unix_time = int(time_value.timestamp())
                elif isinstance(time_value, (int, float)):
                    # Assume it's already a UNIX timestamp in seconds
                    unix_time = int(time_value)
                elif isinstance(time_value, str):
                    # Try to parse as datetime
                    unix_time = int(pd.Timestamp(time_value).timestamp())
                else:
                    raise DataError(
                        message=f"Unsupported timestamp format: {type(time_value)}",
                        error_code="DATA-InvalidTimestamp",
                        details={"timestamp_type": str(type(time_value))}
                    )
                
                # Create histogram entry
                value = row[value_column]
                # Handle NaN values
                if pd.isna(value):
                    logger.debug(f"Skipping NaN value at timestamp {time_value}")
                    continue
                
                value = float(value)
                entry = {
                    "time": unix_time,  # Unix timestamp in seconds
                    "value": value
                }
                
                # Determine color
                if color_column:
                    # Ensure the color is a proper string for LightweightCharts
                    if isinstance(row[color_column], bool):
                        # Handle boolean values for color selection
                        entry["color"] = positive_color if row[color_column] else negative_color
                    elif isinstance(row[color_column], str):
                        # Use string color directly
                        entry["color"] = row[color_column]
                    else:
                        # For other types, default to value-based coloring
                        if value > 0:
                            entry["color"] = positive_color
                        elif value < 0:
                            entry["color"] = negative_color
                        else:
                            entry["color"] = neutral_color
                else:
                    # Assign color based on value
                    if value > 0:
                        entry["color"] = positive_color
                    elif value < 0:
                        entry["color"] = negative_color
                    else:
                        entry["color"] = neutral_color
                
                result.append(entry)
            
            logger.debug(f"Transformed {len(result)} histogram data points")
            return result
            
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error transforming histogram data: {str(e)}")
            raise DataError(
                message="Failed to transform histogram data",
                error_code="DATA-TransformationFailed",
                details={"original_error": str(e)}
            ) from e