"""
Data transformation layer for the KTRDR visualization module.

This module provides functionality to transform pandas DataFrames into
format compatible with TradingView's lightweight-charts library.
"""

from datetime import datetime
from typing import Any, Optional

import pandas as pd

from ktrdr import get_logger
from ktrdr.errors import DataError

logger = get_logger(__name__)


class DataAdapter:
    """
    Transforms pandas DataFrames into the format required by lightweight-charts.

    This class provides static methods to convert different types of financial data
    (OHLC, line series, histogram) from pandas DataFrames to JSON format compatible
    with TradingView's lightweight-charts library.
    """

    @staticmethod
    def _ensure_date_column(
        df: pd.DataFrame, time_column: str = "date"
    ) -> pd.DataFrame:
        """
        Ensure the DataFrame has a date column, handling common date column issues.

        This helper method handles:
        1. Date as index
        2. Case-insensitive date column names
        3. "Date" vs "date" naming inconsistencies

        Args:
            df: DataFrame to process
            time_column: Expected name of the time column

        Returns:
            DataFrame with guaranteed time column

        Raises:
            DataError: If no suitable date column can be found
        """
        # Make a copy to avoid modifying the original
        df = df.copy()

        # Check if the index is a DatetimeIndex and add as a column if needed
        if isinstance(df.index, pd.DatetimeIndex):
            logger.debug(
                f"Found DatetimeIndex in DataFrame, using as '{time_column}' column"
            )
            df[time_column] = df.index
            return df

        # Check for case-insensitive match (date vs Date)
        col_map = {col.lower(): col for col in df.columns}
        if time_column.lower() in col_map:
            actual_column = col_map[time_column.lower()]
            if actual_column != time_column:
                logger.debug(
                    f"Found case-insensitive match for '{time_column}': '{actual_column}'"
                )
                df[time_column] = df[actual_column]
            return df

        # If we still don't have a date column, report the error
        raise DataError(
            message=f"No suitable date column found. Expected '{time_column}' or similar.",
            error_code="DATA-MissingTimeColumn",
            details={"available_columns": list(df.columns)},
        )

    @staticmethod
    def transform_ohlc(
        df: pd.DataFrame,
        time_column: str = "date",
        open_col: str = "open",
        high_col: str = "high",
        low_col: str = "low",
        close_col: str = "close",
    ) -> list[dict[str, Any]]:
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

            # Ensure date column is available
            df = DataAdapter._ensure_date_column(df, time_column)

            # Handle case-insensitive matching for OHLC columns
            col_map = {col.lower(): col for col in df.columns}
            ohlc_cols = {}
            for col_name, expected in [
                (open_col, "open"),
                (high_col, "high"),
                (low_col, "low"),
                (close_col, "close"),
            ]:
                if col_name.lower() in col_map:
                    ohlc_cols[expected] = col_map[col_name.lower()]
                else:
                    ohlc_cols[expected] = col_name

            # Check if all required columns exist
            missing_cols = [
                col
                for col, mapped_col in ohlc_cols.items()
                if mapped_col not in df.columns
            ]
            if missing_cols:
                raise DataError(
                    message=f"Missing required columns for OHLC transformation: {missing_cols}",
                    error_code="DATA-MissingColumns",
                    details={"available_columns": list(df.columns)},
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
                        details={"timestamp_type": str(type(time_value))},
                    )

                # Create OHLC entry using the mapped column names
                entry = {
                    "time": unix_time,  # Unix timestamp in seconds
                    "open": float(row[ohlc_cols["open"]]),
                    "high": float(row[ohlc_cols["high"]]),
                    "low": float(row[ohlc_cols["low"]]),
                    "close": float(row[ohlc_cols["close"]]),
                }
                result.append(entry)

            logger.debug(f"Transformed {len(result)} OHLC data points")
            return result

        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error transforming OHLC data: {str(e)}")
            raise DataError(
                message="Failed to transform OHLC data",
                error_code="DATA-TransformationFailed",
                details={"original_error": str(e)},
            ) from e

    @staticmethod
    def transform_line(
        df: pd.DataFrame, time_column: str = "date", value_column: str = "value"
    ) -> list[dict[str, Any]]:
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

            # Ensure date column is available
            df = DataAdapter._ensure_date_column(df, time_column)

            # Handle case-insensitive matching for value column
            col_map = {col.lower(): col for col in df.columns}
            actual_value_col = col_map.get(value_column.lower(), value_column)

            # Check if required columns exist (after case-insensitive matching)
            if actual_value_col not in df.columns:
                raise DataError(
                    message=f"Missing required column for line transformation: {value_column}",
                    error_code="DATA-MissingColumns",
                    details={
                        "available_columns": list(df.columns),
                        "required_column": value_column,
                    },
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
                        details={"timestamp_type": str(type(time_value))},
                    )

                # Create line series entry
                value = row[actual_value_col]
                # Handle NaN values
                if pd.isna(value):
                    logger.debug(f"Skipping NaN value at timestamp {time_value}")
                    continue

                entry = {
                    "time": unix_time,  # Unix timestamp in seconds
                    "value": float(value),
                }
                result.append(entry)

            logger.debug(f"Transformed {len(result)} line data points")
            return result

        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error transforming line data: {str(e)}")
            raise DataError(
                message="Failed to transform line data",
                error_code="DATA-TransformationFailed",
                details={"original_error": str(e)},
            ) from e

    @staticmethod
    def transform_histogram(
        df: pd.DataFrame,
        time_column: str = "date",
        value_column: str = "value",
        color_column: Optional[str] = None,
        positive_color: str = "#26a69a",
        negative_color: str = "#ef5350",
        neutral_color: str = "#999999",
    ) -> list[dict[str, Any]]:
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

            # Ensure date column is available
            df = DataAdapter._ensure_date_column(df, time_column)

            # Handle case-insensitive matching for value column
            col_map = {col.lower(): col for col in df.columns}
            actual_value_col = col_map.get(value_column.lower(), value_column)

            # Check if required columns exist (after case-insensitive matching)
            if actual_value_col not in df.columns:
                raise DataError(
                    message=f"Missing required column for histogram transformation: {value_column}",
                    error_code="DATA-MissingColumns",
                    details={
                        "available_columns": list(df.columns),
                        "required_column": value_column,
                    },
                )

            # If color_column is specified, try case-insensitive match
            actual_color_col = None
            if color_column:
                actual_color_col = col_map.get(color_column.lower(), color_column)
                if actual_color_col not in df.columns:
                    logger.warning(
                        f"Color column '{color_column}' not found, using value-based coloring instead"
                    )
                    actual_color_col = None

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
                        details={"timestamp_type": str(type(time_value))},
                    )

                # Create histogram entry
                value = row[actual_value_col]
                # Handle NaN values
                if pd.isna(value):
                    logger.debug(f"Skipping NaN value at timestamp {time_value}")
                    continue

                value = float(value)
                entry: dict[str, Any] = {
                    "time": unix_time,
                    "value": value,
                }  # Unix timestamp in seconds

                # Determine color
                if actual_color_col:
                    # Ensure the color is a proper string for LightweightCharts
                    if isinstance(row[actual_color_col], bool):
                        # Handle boolean values for color selection
                        entry["color"] = (
                            positive_color if row[actual_color_col] else negative_color
                        )
                    elif isinstance(row[actual_color_col], str):
                        # Use string color directly
                        entry["color"] = row[actual_color_col]
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
                details={"original_error": str(e)},
            ) from e
